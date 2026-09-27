"""Small, explicit retrieval contract for the shipped lexical catalog.

These cases test user-visible intent, not implementation scores. A source
refresh may add a genuinely relevant benchmark. Known Catalog gaps still return
inspectable partial evidence; the query service must not mislabel retrieval as a
final suitability judgment. Review changed expectations against the underlying
benchmark records instead of mechanically updating snapshots.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from benchmark_radar.query import QueryService

FIXTURE_PATH = Path("tests/fixtures/search_relevance.yml")
FIXTURE = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
CASES = FIXTURE["cases"]
POSITIVE_CASES = [case for case in CASES if case["kind"] == "topical"]
GAP_CASES = [case for case in CASES if case["kind"] == "catalog_gap"]


def test_relevance_fixture_has_a_stable_schema_and_unique_ids() -> None:
    assert FIXTURE["schema_version"] == 2
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    assert POSITIVE_CASES
    assert GAP_CASES


@pytest.mark.parametrize(
    "case",
    POSITIVE_CASES,
    ids=lambda case: case["id"],
)
def test_positive_queries_surface_known_relevant_records(case: dict) -> None:
    result = QueryService().search(case["query"], scope=case["scope"], limit=20)
    returned = {record["name"] for record in result["results"]}

    assert result["search_status"] == "full_matches_found"
    assert set(case["must_include"]) <= returned
    assert all(record["match"]["matched_tokens"] for record in result["results"])


@pytest.mark.parametrize(
    "case",
    GAP_CASES,
    ids=lambda case: case["id"],
)
def test_catalog_gap_queries_return_inspectable_candidates_without_false_full_matches(
    case: dict,
) -> None:
    result = QueryService().search(case["query"], scope=case["scope"], limit=10)

    assert result["search_status"] == case["expected_status"]
    assert result["candidate_count"] >= case["minimum_candidates"]
    assert result["total_matches"] == result["candidate_count"]
    returned = {record["name"] for record in result["results"]}
    assert set(case["must_include_candidates"]) <= returned
    if case["expected_status"] == "partial_candidates_only":
        assert result["results"]
        assert result["full_match_count"] == 0
        assert result["partial_match_count"] == result["total_matches"]
        assert all(record["match"]["missing_tokens"] for record in result["results"])
        assert all(record["match"]["query_coverage"] < 1.0 for record in result["results"])
    else:
        assert result["candidate_count"] == 0
        assert result["full_match_count"] == 0
        assert result["partial_match_count"] == 0
        assert result["results"] == []


def test_opencompass_source_text_makes_opaque_names_discoverable() -> None:
    result = QueryService().search("scientific fact checking charts", scope="catalog", limit=5)

    assert result["results"][0]["name"] == "ClimateViz"
    assert result["results"][0]["source"] == "opencompass_hub"
    assert result["results"][0]["match"]["matched_tokens"] == [
        "charts",
        "checking",
        "fact",
        "scientific",
    ]


def test_single_token_name_search_never_returns_an_empty_token_explanation() -> None:
    result = QueryService().search("CASP", scope="all", limit=20)

    assert all(record["match"]["matched_tokens"] for record in result["results"])


@pytest.mark.parametrize("name", ["CoWorkBench", "Legal Agent Benchmark", "AetherCode"])
def test_previous_topical_examples_remain_discoverable_by_name(name: str) -> None:
    result = QueryService().search(name, scope="catalog", limit=10)
    assert name in {record["name"] for record in result["results"]}
