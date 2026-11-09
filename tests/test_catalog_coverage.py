"""Coverage and evidence contracts shared by the website and installed clients."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from benchmark_radar.benchmark_scores import load_scores
from benchmark_radar.catalog import _observation
from benchmark_radar.catalog_evidence import attach_evidence, document_registry
from benchmark_radar.export import write_exports
from benchmark_radar.model_cards import load_registry
from benchmark_radar.score_summary import score_summary


@pytest.fixture(scope="module")
def catalog():
    return json.loads(Path("site/data/benchmark-index.json").read_text())


def test_every_report_benchmark_joins_the_catalog_even_without_scores(catalog):
    registered = load_registry(Path("data/model_cards.yml"))
    expected = {row["id"] for row in registered["benchmarks"]}
    actual = {row["slug"] for row in catalog["benchmarks"] if row["source"] == "model_reports"}
    assert actual == expected
    assert len(catalog["benchmarks"]) >= 1259
    assert len({row["source"] for row in catalog["benchmarks"]}) >= 4
    assert any(
        row["source"] == "model_reports" and row["score_count"] == 0
        for row in catalog["benchmarks"]
    )


def test_index_shards_offline_release_and_exports_have_identical_records(catalog, tmp_path):
    expected = {row["slug"] for row in catalog["benchmarks"]}
    assert len(expected) == catalog["count"]
    assert {path.stem for path in Path("site/data/benchmarks").glob("*.json")} == expected
    bundles = list(Path("site/data/cli").glob("benchmark-radar-data-*.zip"))
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        offline = json.loads(archive.read("benchmark-index.json"))
        assert offline == catalog
        assert {
            Path(name).stem for name in archive.namelist() if name.startswith("benchmarks/")
        } == expected
    exported = write_exports(tmp_path)
    ranking = json.loads(exported["json"].read_text())
    assert {row["benchmark_id"] for row in ranking["entries"]} == expected


def test_documents_and_scores_retain_common_citation_edges(catalog):
    source_counts = Counter()
    for record in catalog["benchmarks"]:
        shard = json.loads(Path(f"site/data/benchmarks/{record['slug']}.json").read_text())
        documents = {doc["id"]: doc for doc in shard["record"]["documents"]}
        assert record["evidence_summary"]["document_count"] == (len(documents) or None)
        for document in documents.values():
            assert document["source"] == record["source"]
            assert document["source_url"] and document["document_type"]
            source_counts[document["source"]] += 1
        for payload in shard["scores_by_source"].values():
            for observation in payload["rows"]:
                assert observation["source"] == record["source"]
                assert observation["document_id"] in documents
                assert (
                    documents[observation["document_id"]]["source_url"] == observation["source_url"]
                )
    assert set(source_counts) == {row["source"] for row in catalog["benchmarks"]}


@pytest.mark.parametrize(
    ("slug", "count"),
    [
        ("artificial-analysis-humanitys-last-exam", 577),
        ("artificial-analysis-scicode", 577),
        ("artificial-analysis-critpt", 492),
    ],
)
def test_large_model_counts_reach_the_shared_index(catalog, slug, count):
    record = next(row for row in catalog["benchmarks"] if row["slug"] == slug)
    assert record["score_summary"]["model_count"] == count
    assert record["evidence_summary"]["model_count"] == count
    # One source page can document hundreds of independently identified models.
    assert record["evidence_summary"]["document_count"] == 1


@pytest.mark.parametrize("source", ["model_reports", "llm_stats", "opencompass_hub"])
def test_repeated_scores_do_not_create_documents_or_models(source):
    record = {
        "key": "example:benchmark",
        "slug": "example",
        "name": "Example",
        "source": source,
        "provenance": {"source_url": "https://example.test/report"},
    }
    observations = [
        {
            "key": record["key"],
            "model_id": "one",
            "value": value,
            "source_url": "https://example.test/report",
        }
        for value in (12, 15, 15)
    ]
    summary = score_summary(observations)
    result = attach_evidence(
        [record], [{"key": record["key"], "score_summary": summary}], observations
    )
    assert result[0]["evidence_summary"] == {
        "document_count": 1,
        "model_count": 1,
        "model_count_basis": "source_model_id",
    }
    assert document_registry(result)["entries"][0]["document_count"] == 1
    assert len({row["document_id"] for row in observations}) == 1


def test_missing_source_model_id_keeps_the_observation_without_guessing_a_count():
    row = _observation(
        {"benchmark_id": "example", "model_name": "A display name", "benchmark_score": "0"},
        key="source:example",
        series_id="source:example:default",
        crawled_at="2026-01-01",
        source="example",
    )
    assert row["model_id"] is None
    assert row["value"] == 0
    assert row["obs_id"]
    summary = score_summary([row])
    assert summary["numeric_count"] == 1
    assert summary["model_count"] is None


def test_export_refuses_a_document_registry_missing_catalog_records(catalog, tmp_path):
    incomplete = {**catalog, "document_registry": {**catalog["document_registry"], "entries": []}}
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(incomplete))
    with pytest.raises(ValueError, match="complete benchmark catalog"):
        write_exports(tmp_path / "out", catalog_path=path)


def test_swe_refactor_bench_results_table_reports_all_table_3_scores():
    """Issue #379: Table 3 of arXiv:2608.23564 has 26 configurations; every
    Score is filed, and the best (Claude Opus 5, xhigh effort) is 47.0."""
    registry = load_registry(Path("data/model_cards.yml"))
    assert any(row["id"] == "swe_refactor_bench" for row in registry["benchmarks"])
    scores = load_scores(Path("data/benchmark_scores.yml"))
    rows = [row for row in scores["results"] if row["benchmark_id"] == "swe_refactor_bench"]
    assert len(rows) == 26
    assert {row["model"] for row in rows} == {
        "Claude Opus 5",
        "GPT-5.6 Sol",
        "Kimi K3",
        "Claude Sonnet 5",
        "GPT-5.6 Luna",
        "Qwen 3.8 Max",
        "DeepSeek V4 Flash",
        "GLM 5.2",
    }
    assert all(row["source_id"] == "swe_refactor_bench_results_table" for row in rows)
    assert all(row["measurement_kind"] == "benchmark_publisher_run" for row in rows)
    best = max(rows, key=lambda row: row["value"])
    assert (best["model"], best["value"]) == ("Claude Opus 5", 47.0)
    assert "xhigh" in best["protocol"]
