"""Release evidence must reach the rebuilt chart without changing the corpus."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from benchmark_radar.catalog import CatalogError, build_benchmark_index
from benchmark_radar.catalog_dates import apply_benchmark_dates, load_benchmark_dates
from benchmark_radar.catalog_identity import IdentityIndex, apply_inherited_identity


def release_fact(**changes):
    return {
        "released": "2024-02-29",
        "basis": "paper_first_version",
        "source_url": "https://example.org/benchmark-paper",
        "note": "First version introducing this benchmark.",
        **changes,
    }


def first_score_fact(**changes):
    return {
        "first_score_reported_at": "2023-12-31",
        "basis": "score_publication",
        "source_url": "https://example.org/benchmark-results",
        "note": "Earliest numeric LLM result in the retained source history.",
        "score_evidence": {
            "model": "Example LLM",
            "value": 0,
            "metric": "accuracy",
            "locator": "Table 2, Example LLM row",
        },
        **changes,
    }


def test_release_enrichment_keeps_records_scores_and_existing_dates(tmp_path):
    records = [
        {"key": "source:a", "slug": "a", "name": "A", "source": "source", "released": None},
        {"key": "source:b", "slug": "b", "name": "B", "source": "source", "released": "2024-01-01"},
        {"key": "source:c", "slug": "c", "name": "C", "source": "source", "released": None},
    ]
    original = deepcopy(records)
    path = tmp_path / "dates.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": {
                    "source:a": release_fact(),
                    "source:b": release_fact(),
                },
            }
        )
    )
    enriched = apply_benchmark_dates(records, load_benchmark_dates(records, path))
    assert records == original, "immutable crawl records are not patched"
    assert [r["key"] for r in enriched] == [r["key"] for r in records]
    assert enriched[0]["released"] == "2024-02-29"
    assert enriched[1] == records[1], "an existing source release wins"
    assert enriched[2] == records[2], "no date or score is invented for missing evidence"
    index = {r["key"]: r for r in build_benchmark_index(enriched)}
    assert index["source:a"]["released_reference"]["source_url"] == release_fact()["source_url"]
    assert index["source:a"]["score_count"] == 0
    assert index["source:a"]["first_score_record"] is None


@pytest.mark.parametrize(
    "key, changes, error",
    [
        ("absent", {}, "unknown benchmark key"),
        ("source:a", {"released": "2024-02-30"}, "exact ISO date"),
        ("source:a", {"released": "2024-02"}, "exact ISO date"),
        ("source:a", {"basis": "crawl"}, "unsupported release-date basis"),
        ("source:a", {"source_url": ""}, "primary-source HTTPS URL"),
        ("source:a", {"note": ""}, "explain which event"),
    ],
)
def test_invalid_release_evidence_fails_visibly(tmp_path, key, changes, error):
    path = tmp_path / "dates.yml"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "benchmarks": {key: release_fact(**changes)}})
    )
    with pytest.raises(CatalogError, match=error):
        load_benchmark_dates([{"key": "source:a"}], path)


@pytest.mark.parametrize(
    "evidence",
    [None, [], "score", {}, {"value": 70}, {"value": True}, {"value": float("nan")}],
)
def test_first_score_date_requires_numeric_model_evidence(tmp_path, evidence):
    path = tmp_path / "dates.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": {"source:a": first_score_fact(score_evidence=evidence)},
            }
        )
    )
    with pytest.raises(CatalogError, match="numeric LLM score evidence"):
        load_benchmark_dates([{"key": "source:a"}], path)


def test_first_score_date_is_earliest_publication_not_a_highest_score(tmp_path):
    records = [{"key": "source:a", "slug": "a", "name": "A", "source": "source"}]
    path = tmp_path / "dates.yml"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "benchmarks": {"source:a": first_score_fact()}})
    )
    facts = load_benchmark_dates(records, path)
    enriched = apply_benchmark_dates(records, facts)
    row = build_benchmark_index(enriched)[0]
    assert row["released"] is None
    assert row["first_score_reported_at"] == "2023-12-31", "do not advance old scores into 2024"
    assert row["first_score_source_reference"]["score_evidence"]["value"] == 0
    assert row["score_count"] == 0, "a date citation does not become a highest-score archive"
    assert row["score_summary"] is None
    assert row["first_score_record"] is None, "actual publication is not a model-release proxy"

    for reported_at in ("2023-06-01", "2024-06-01"):
        series = {"source:a": {"first_score_report": {"reported_at": reported_at}}}
        row = build_benchmark_index(enriched, series)[0]
        assert row["first_score_reported_at"] == min(reported_at, "2023-12-31")

    older = {**enriched[0], "first_score_reported_at": "2022-01-01"}
    assert apply_benchmark_dates([older], facts)[0] == older


def test_inherited_release_keeps_its_own_citation():
    donor = {
        "key": "a",
        "source": "a",
        "name": "A",
        "released": "2024-01-01",
        "released_reference": {"source_url": "https://example.org/a"},
    }
    recipients = [{"key": "b", "released": None}, {"key": "c", "released": "2025-01-01"}]
    inheritance = {
        "donor_key": "a",
        "group_id": "g",
        "reviewed_by": "test",
        "reviewed_at": "2026-09-07",
    }
    identity = IdentityIndex(inheritance_by_key={"b": inheritance, "c": inheritance})
    rows = {r["key"]: r for r in apply_inherited_identity([donor, *recipients], identity)}
    assert rows["b"]["released_reference"] == donor["released_reference"]
    assert rows["c"]["released"] == "2025-01-01"
    assert "released_reference" not in rows["c"], "the donor cannot cite a different recipient date"


def test_rebuilt_catalog_exposes_release_evidence():
    import json

    index = json.loads(Path("site/data/benchmark-index.json").read_text())["benchmarks"]
    by_key = {r["key"]: r for r in index}
    facts = load_benchmark_dates(index)
    for key, fact in facts.items():
        row = by_key[key]
        field = "released" if "released" in fact else "first_score_reported_at"
        reference = "released_reference" if field == "released" else "first_score_source_reference"
        assert row[field], f"{key}: recovered dates must reach the chart input"
        if row[field] == fact[field]:
            assert row[reference]["source_url"] == fact["source_url"]
        shard = json.loads(Path(f"site/data/benchmarks/{row['slug']}.json").read_text())
        assert fact["source_url"] in json.dumps(shard)


def test_retrospectively_scored_models_do_not_date_new_benchmarks_before_2024():
    import json

    index = json.loads(Path("site/data/benchmark-index.json").read_text())["benchmarks"]
    by_key = {r["key"]: r for r in index}
    for key, released in {
        "artificial-analysis:humanitys-last-exam": "2025-01-23",
        "artificial-analysis:scicode": "2024-07-18",
        "artificial-analysis:critpt": "2025-11-21",
    }.items():
        row = by_key[key]
        assert row["first_score_record"]["reported_at"] < "2024-01-01"
        assert row["first_score_record"]["date_precision"] == "model_announcement"
        assert row["released"] == released
        assert row["released_reference"]["source_url"]
        assert row["score_summary"]["model_count"] > 200
    for row in index:
        count = (row.get("score_summary") or {}).get("model_count")
        if row["source"] == "artificial_analysis" and count and count >= 200:
            assert row["released"], (
                f"{row['key']}: audit benchmark age before relying on an old model release"
            )


def test_the_four_undated_vbench_family_reports_carry_their_reviewed_release_dates():
    """The registry's undated visual-generation entries reach the chart dated.

    These four have no crawl record to inherit from, so nothing but this archive
    can date them, and an entry with no `released` is dropped from every dated
    leaderboard era. The dates are the first version of the paper each
    benchmark's own repository cites; the maintainer confirmed the four arXiv
    listings resolve in the review of #583.
    """
    import json

    index = json.loads(Path("site/data/benchmark-index.json").read_text())["benchmarks"]
    by_key = {row["key"]: row for row in index}
    for key, released in {
        "model-reports:vbench_plus_plus": "2024-11-20",
        "model-reports:vbench_2_0": "2025-03-27",
        "model-reports:evaluation_agent": "2024-12-10",
        "model-reports:uni_mmmu": "2025-10-15",
    }.items():
        row = by_key[key]
        assert row["released"] == released
        reference = row["released_reference"]
        assert reference["basis"] == "paper_first_version"
        assert reference["source_url"].startswith("https://arxiv.org/abs/")
    # Inheritance is the other way a registry record can acquire a date, and
    # these four have no donor to inherit one from. Asserting that against the
    # index row would be vacuous, because the index drops the provenance key the
    # shard keeps, so check the mechanism instead: no reviewed group names them.
    identity = yaml.safe_load(Path("data/catalog/identity.yml").read_text(encoding="utf-8"))
    grouped = {
        member
        for relation in identity.values()
        if isinstance(relation, list)
        for group in relation
        for member in (group.get("members") or [])
    }
    assert grouped.isdisjoint(
        {
            "model-reports:vbench_plus_plus",
            "model-reports:vbench_2_0",
            "model-reports:evaluation_agent",
            "model-reports:uni_mmmu",
        }
    )
