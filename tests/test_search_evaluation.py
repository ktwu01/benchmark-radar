from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from test_query_surfaces import _catalog

from benchmark_radar.query import QueryService
from benchmark_radar.search_evaluation import evaluate, load_dataset

DATASET_PATH = Path("tests/fixtures/search_evaluation.yml")


def test_search_evaluation_dataset_is_explicit_and_not_self_scoring() -> None:
    # Regression: treating every unlisted result as negative makes sparse judgments
    # look like complete labels and produces misleading precision or NDCG numbers.
    dataset = load_dataset(DATASET_PATH)

    assert "Unlisted records are unjudged, not negative" in dataset["description"]
    assert {case["kind"] for case in dataset["queries"]} == {
        "catalog_gap",
        "navigational",
        "topical",
    }
    assert all("relevant_keys" in case for case in dataset["queries"])
    assert all(case["intent"].strip() for case in dataset["queries"])


def test_search_evaluation_rejects_duplicate_query_ids(tmp_path: Path) -> None:
    # Regression: duplicate IDs made a changed query look like the same stable
    # evaluation case in review output, hiding which judgment actually moved.
    dataset = yaml.safe_load(DATASET_PATH.read_text(encoding="utf-8"))
    dataset["queries"][1]["id"] = dataset["queries"][0]["id"]
    path = tmp_path / "duplicate.yml"
    path.write_text(yaml.safe_dump(dataset), encoding="utf-8")

    with pytest.raises(ValueError, match="id must be a unique non-empty string"):
        load_dataset(path)


def test_evaluation_respects_recall_cutoff_when_hit_cutoff_is_larger(tmp_path):
    service = QueryService(_catalog(tmp_path))
    rows = service.search("agent", scope="catalog", limit=10)["results"]
    assert len(rows) >= 2
    second = rows[1]["key"]
    gap_rows = service.search("agent absent", scope="catalog", limit=10)["results"]
    assert len(gap_rows) >= 2
    assert all(row["match"]["missing_tokens"] for row in gap_rows)
    dataset = {
        "name": "unequal-cutoffs",
        "cutoffs": {"hit": 10, "recall": 1},
        "thresholds": {"minimum": {}, "maximum": {}},
        "queries": [
            {
                "id": "positive",
                "kind": "topical",
                "query": "agent",
                "scope": "catalog",
                "intent": "Agent benchmarks",
                "relevant_keys": [second],
            },
            {
                "id": "gap",
                "kind": "catalog_gap",
                "query": "agent absent",
                "scope": "catalog",
                "intent": "Missing feature",
                "relevant_keys": [],
                "expected_partial_keys": [gap_rows[1]["key"]],
            },
        ],
    }
    result = evaluate(service, dataset)
    assert result["metrics"]["hit_rate_at_10"] == 1.0
    assert result["metrics"]["macro_recall_at_1"] == 0.0
    assert result["metrics"]["mrr_at_1"] == 0.0
    assert result["metrics"]["catalog_gap_partial_retention_at_1"] == 0.0
