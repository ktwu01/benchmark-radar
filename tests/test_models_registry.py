"""Model reports and registry observations use the same model evidence contract."""

from __future__ import annotations

import csv
import json
import runpy
from pathlib import Path

import pytest

from benchmark_radar.models_registry import (
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
        assert set(record.provenance_sources) <= {
            "model_reports",
            "llm_stats",
            "artificial_analysis",
            "opencompass",
        }


@needs_corpus
def test_a_model_reported_by_multiple_sources_carries_each_source():
    registry = _registry()
    both = [r for r in registry.values() if len(r.provenance_sources) > 1]

    assert len(both) >= 10, "expected models reported by multiple sources"
    for record in both:
        assert set(record.provenance_sources) == {s.source for s in record.sources}


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
            assert entry.source in (
                "model_reports",
                "llm_stats",
                "artificial_analysis",
                "opencompass",
            )
            assert entry.evidence_id
            if entry.source in ("llm_stats", "artificial_analysis"):
                # Never promoted onto the record itself.
                assert entry.payload.get("comparable_group") is None
                assert "url" not in entry.payload or entry.payload.get("source_url")

    # And the record carries no field that only one layer could support.
    sample = next(iter(registry.values()))
    assert set(sample.to_dict()) == {
        "key",
        "model",
        "organization",
        "provenance_sources",
        "sources",
    }


def test_the_key_is_stable_and_safe():
    assert model_key("MiMo-V2.5-Pro", "Xiaomi") == "xiaomi-mimo-v2-5-pro"
    assert model_key("Gemini 3.1 Pro", "Google") == "google-gemini-3-1-pro"
    # Same name from two organizations is two models, not one.
    assert model_key("Nova", "Amazon") != model_key("Nova", "Meta")


@needs_corpus
def test_the_published_registry_matches_what_the_builder_produces():
    published = json.loads(Path("site/data/models.json").read_text(encoding="utf-8"))
    report = summarize(_registry())

    for field in ("model_count", "source_counts", "multiple_sources"):
        assert published[field] == report[field], field
    assert len(published["models"]) == published["model_count"]
    # The published form is an index: identity and layer, not embedded payloads.
    assert set(published["models"][0]) == {
        "key",
        "model",
        "organization",
        "provenance_sources",
        "source_counts",
    }


@needs_corpus
def test_the_logo_registry_and_models_json_cannot_disagree(rebuilt_logo_registry):
    """One answer to "which models exist".

    build_logo_registry.py used to walk radar.json and the shards itself,
    making it a second answer -- and the two disagreed, 357 against 355,
    because it keyed on the display name where models.json keys on (name,
    organization). It now reads models.json and only decides what each entry is
    called in review.
    """
    models = json.loads(Path("site/data/models.json").read_text(encoding="utf-8"))
    logos = rebuilt_logo_registry

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


def test_the_logo_generator_preserves_a_retired_high_water_mark(tmp_path, monkeypatch):
    """A retired maximum survives even when no live entry still carries it."""
    script = Path("scripts/build_logo_registry.py").resolve()
    data_dir = tmp_path / "site" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "models.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model": "Model One",
                        "organization": "Org One",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "logo-registry.json").write_text(
        json.dumps(
            {
                "high_water": {"O": 68, "M": 1048},
                "organizations": {"Org One": "O-01"},
                "models": {"Model One␟Org One": "M-01"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(script), run_name="__main__")

    generated = json.loads((data_dir / "logo-registry.json").read_text(encoding="utf-8"))
    assert generated["high_water"] == {"O": 68, "M": 1048}


def test_slug_twins_that_are_both_live_get_distinct_logo_ids(tmp_path, monkeypatch):
    """Rename inheritance must not hand a live label's ID to its slug twin.

    models.json keeps "Gemini 2.5 Flash" and "Gemini-2.5-Flash" as separate
    records; inheriting from the still-live twin gave 36 cards a shared ID.
    A retired label's ID is still inherited by its renamed successor.
    """
    script = Path("scripts/build_logo_registry.py").resolve()
    data_dir = tmp_path / "site" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "models.json").write_text(
        json.dumps(
            {
                "models": [
                    {"model": "Gemini 2.5 Flash", "organization": "Google"},
                    {"model": "Gemini-2.5-Flash", "organization": "Google"},
                    {"model": "Grok 4", "organization": "xAI"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "logo-registry.json").write_text(
        json.dumps(
            {
                "high_water": {"O": 2, "M": 2},
                "organizations": {"Google": "O-01", "xAI": "O-02"},
                "models": {"Gemini 2.5 Flash␟Google": "M-01", "Grok-4␟xAI": "M-02"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(script), run_name="__main__")

    models = json.loads((data_dir / "logo-registry.json").read_text(encoding="utf-8"))["models"]
    assert models == {
        "Gemini 2.5 Flash␟Google": "M-01",
        "Grok 4␟xAI": "M-02",
        "Gemini-2.5-Flash␟Google": "M-03",
    }


def test_a_missing_shard_directory_refuses_to_write_a_curated_only_registry(tmp_path):
    """The 321-model drop this module opens on, reachable again since the
    shards stopped being committed.

    They are derived and untracked, so a fresh checkout has none until
    `normalize-catalog` writes them, and `_crawled_models()` reaches them with
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

    with pytest.raises(FileNotFoundError, match="normalize-catalog"):
        write_model_registry(radar, tmp_path / "absent-shards", output)

    # Refusing means refusing: a stale models.json is not overwritten with a
    # shorter one on the way out.
    assert not output.exists()


def test_an_empty_shard_directory_refuses_to_write_a_curated_only_registry(tmp_path):
    """Same short registry, reached a different way.

    An interrupted `normalize-catalog` leaves the directory behind with
    nothing in it, and a directory that exists is not the same as a directory
    that has shards: the glob answers "nothing" either way.
    """
    radar = tmp_path / "radar.json"
    radar.write_text(json.dumps({"model_card_leaderboard": {"model_cards": []}}), encoding="utf-8")
    output = tmp_path / "models.json"
    shard_dir = tmp_path / "empty-shards"
    shard_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="normalize-catalog"):
        write_model_registry(radar, shard_dir, output)

    assert not output.exists()


def registry_for(tmp_path, identities):
    rows = [
        {
            "obs_id": f"observation-{index}",
            "model_name": model,
            "organization": organization,
        }
        for index, (organization, model) in enumerate(identities)
    ]
    (tmp_path / "benchmark.json").write_text(
        json.dumps({"scores_by_source": {"llm_stats": {"rows": rows}}})
    )
    return build_registry({}, tmp_path)


@pytest.mark.parametrize(
    "identities",
    [
        [("Cohere", "Command A"), ("Cohere", "Command A+")],
        [("A", "B C"), ("A B", "C")],
        [("研究所", "模型甲"), ("研究所", "模型乙")],
        [("Org", "A/B"), ("Org", "A B")],
    ],
)
def test_slug_collisions_keep_model_evidence_separate(tmp_path, identities):
    # Command A+ currently shares a slug with Command A. The registry dropped
    # the '+' and attributed the newer model's evidence to the older model.
    registry = registry_for(tmp_path, identities)
    assert {(r.organization, r.model) for r in registry.values()} == set(identities)
    assert len(registry) == len(identities)
    for record in registry.values():
        assert len(record.sources) == 1
        assert record.sources[0].payload["model_name"] == record.model
        assert record.sources[0].payload["organization"] == record.organization
    assert all(key.isascii() for key in registry)


def test_collision_keys_and_labels_are_independent_of_input_order(tmp_path):
    identities = [("Cohere", "Command A"), ("Cohere", "Command A+")]
    first = registry_for(tmp_path, identities)
    second = registry_for(tmp_path, list(reversed(identities)))

    def project(registry):
        return [(k, r.organization, r.model) for k, r in registry.items()]

    assert project(first) == project(second)


def test_case_only_spellings_keep_a_deterministic_label(tmp_path):
    identities = [("Cohere", "Command A"), ("COHERE", "COMMAND A")]
    first = registry_for(tmp_path, identities)
    second = registry_for(tmp_path, list(reversed(identities)))
    assert len(first) == len(second) == 1
    assert [(k, r.organization, r.model) for k, r in first.items()] == [
        (k, r.organization, r.model) for k, r in second.items()
    ]


def test_immutable_scores_distinguish_command_a_and_command_a_plus(tmp_path):
    identities = set()
    for path in Path("data/leaderboard_snapshots").glob("*scores*.csv"):
        with path.open() as stream:
            for row in csv.DictReader(stream):
                if row["model_name"] in {"Command A", "Command A+"}:
                    identities.add((row["organization_name"], row["model_name"]))
    assert identities == {("Cohere", "Command A"), ("Cohere", "Command A+")}
    assert len(registry_for(tmp_path, sorted(identities))) == 2
