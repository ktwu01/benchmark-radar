"""One structure for models, whichever layer reported them.

A curated model card and a crawled score row shared exactly one field name --
`organization` -- because the project modelled the two things that *mention* a
model and never the model itself. Asking "which models do we know about?" meant
walking two structures, and any consumer that forgot the second silently
dropped 321 models: Gemini had a record and MiMo did not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark_radar.models_registry import (
    CRAWLED,
    CURATED,
    build_registry,
    model_key,
    summarize,
    write_model_registry,
)

RADAR = Path("site/data/radar.json")
SHARDS = Path("site/data/benchmarks")

# radar.json is generated and gitignored, so it exists after a local `export`
# and never on a fresh clone. These tests assert against the real corpus on
# purpose (that Gemini AND MiMo both resolve is the regression they exist to
# catch, and a fixture with two hand-written models could not catch it), so
# they skip rather than fail where the corpus is absent. Without this they
# failed on every CI run, which is how CI stayed red long enough for a real
# ruff regression to hide behind it.
needs_corpus = pytest.mark.skipif(
    not RADAR.exists() or not SHARDS.exists(),
    reason="needs generated site/data; run `benchmark-radar export` first",
)


def _registry():
    radar = json.loads(RADAR.read_text(encoding="utf-8"))
    return build_registry(radar, SHARDS)


@needs_corpus
def test_a_model_is_one_record_no_matter_which_layer_reported_it():
    registry = _registry()

    gemini = [r for r in registry.values() if "Gemini" in r.model]
    mimo = [r for r in registry.values() if "MiMo" in r.model]
    assert gemini, "no Gemini record"
    assert mimo, "no MiMo record -- the gap this structure exists to close"

    # Same shape, same fields, same treatment. Neither is a special case.
    for record in gemini + mimo:
        assert record.key and record.model and record.organization
        assert record.sources
        assert set(record.layers) <= {CURATED, CRAWLED}


@needs_corpus
def test_a_model_both_layers_reported_is_one_record_carrying_both():
    """The join the old two-list shape could not express at all.

    Claude Opus 5 and DeepSeek-V3 exist as a curated card AND as crawled rows.
    Stored as two lists they were two unrelated entries; here they are one
    record whose `layers` names both.
    """
    registry = _registry()
    both = [r for r in registry.values() if len(r.layers) > 1]

    assert len(both) >= 10, "expected models present in both layers"
    for record in both:
        assert record.layers == [CURATED, CRAWLED]
        assert {s.layer for s in record.sources} == {CURATED, CRAWLED}


@needs_corpus
def test_evidence_stays_labelled_rather_than_flattened():
    """Unified record, per-source evidence.

    A curated card establishes a document; a crawled row establishes an
    observation with no protocol and no evaluation date. Flattening them would
    let a crawled row inherit a document it does not have, which is the
    confident wrong attribution this codebase refuses to make.
    """
    registry = _registry()

    for record in registry.values():
        for entry in record.sources:
            assert entry.layer in (CURATED, CRAWLED)
            if entry.layer == CRAWLED:
                # Never promoted onto the record itself.
                assert entry.payload.get("comparable_group") is None
                assert "url" not in entry.payload or entry.payload.get("source_url")

    # And the record carries no field that only one layer could support.
    sample = next(iter(registry.values()))
    assert set(sample.to_dict()) == {"key", "model", "organization", "layers", "sources"}


def test_the_key_is_stable_and_safe():
    assert model_key("MiMo-V2.5-Pro", "Xiaomi") == "xiaomi-mimo-v2-5-pro"
    assert model_key("Gemini 3.1 Pro", "Google") == "google-gemini-3-1-pro"
    # Same name from two organizations is two models, not one.
    assert model_key("Nova", "Amazon") != model_key("Nova", "Meta")


@needs_corpus
def test_the_published_registry_matches_what_the_builder_produces():
    published = json.loads(Path("site/data/models.json").read_text(encoding="utf-8"))
    report = summarize(_registry())

    for field in ("model_count", "curated_only", "crawled_only", "both_layers"):
        assert published[field] == report[field], field
    assert len(published["models"]) == published["model_count"]
    # The published form is an index: identity and layer, not embedded payloads.
    assert set(published["models"][0]) == {
        "key",
        "model",
        "organization",
        "layers",
        "source_counts",
    }


@needs_corpus
def test_the_logo_registry_and_models_json_cannot_disagree():
    """One answer to "which models exist".

    build_logo_registry.py used to walk radar.json and the shards itself,
    making it a second answer -- and the two disagreed, 357 against 355,
    because it keyed on the display name where models.json keys on (name,
    organization). It now reads models.json and only decides what each entry is
    called in review.
    """
    models = json.loads(Path("site/data/models.json").read_text(encoding="utf-8"))
    logos = json.loads(Path("site/data/logo-registry.json").read_text(encoding="utf-8"))

    live = {f"{m['model']}␟{m['organization']}" for m in models["models"]}
    assert set(logos["models"]) == live, "logo registry and models.json disagree"
    assert set(logos["organizations"]) == set(models["organizations"])


@needs_corpus
def test_a_retired_id_is_never_handed_to_a_different_model():
    """Dropping an entry frees its card, never its number.

    Two entries survived a rename ("Gemma 4 31B" -> "Gemma 4 (31B)", "Grok-4"
    -> "Grok 4") and kept the registry disagreeing with the data. They are
    dropped now, but their numbers stay retired, or a reviewer's note against
    M-353 would later point at an unrelated model.
    """
    logos = json.loads(Path("site/data/logo-registry.json").read_text(encoding="utf-8"))
    high_water = logos["high_water"]

    for prefix, mapping in (("O", logos["organizations"]), ("M", logos["models"])):
        issued = [int(value.split("-")[1]) for value in mapping.values()]
        assert high_water[prefix] >= max(issued), prefix
    # M's high-water mark exceeds its live count, which is what retirement looks like.
    assert high_water["M"] >= len(logos["models"])


def test_a_missing_shard_directory_refuses_to_write_a_curated_only_registry(tmp_path):
    """The 321-model drop this module opens on, reachable again since the
    shards stopped being committed.

    They are derived and untracked, so a fresh checkout has none until
    `normalize-external` writes them, and `_crawled_models()` reaches them with
    a glob, which answers "nothing" for a missing directory instead of failing.
    `benchmark-radar classify` would then rewrite models.json with the 34
    curated models and exit 0, and the registry test above skips itself when
    the shards are absent, so nothing anywhere would have gone red.

    Writing that file is worse than not writing it: 34 models is a plausible
    number, not an obviously broken one.
    """
    radar = tmp_path / "radar.json"
    radar.write_text(json.dumps({"model_card_leaderboard": {"model_cards": []}}), encoding="utf-8")
    output = tmp_path / "models.json"

    with pytest.raises(FileNotFoundError, match="normalize-external"):
        write_model_registry(radar, tmp_path / "absent-shards", output)

    # Refusing means refusing: a stale models.json is not overwritten with a
    # shorter one on the way out.
    assert not output.exists()
