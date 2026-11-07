"""The website's catalog search must agree with QueryService (issue #710).

The site matched one folded substring and never read descriptions, so
"weather forecasting" returned 0 of 0 on the Saturation tab while the CLI found
RealBench. docs/query-surfaces.md forbids interface-specific ranking, so the
site now runs a port of QueryService's lexical ranking. These tests run both
implementations over the same records and require the same candidates in the
same order, which is what stops the port from drifting.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from benchmark_radar.query import _build_search_corpus, _match, _unique_query_tokens

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "catalog_search_harness.mjs"
INDEX = ROOT / "site" / "data" / "benchmark-index.json"


def site_ranking(records: list[dict], queries: list[str]) -> dict[str, list[str]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, str(HARNESS)],
        input=json.dumps({"records": records, "queries": queries}),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)


def service_ranking(records: list[dict], query: str) -> dict[str, list[str]]:
    """QueryService.search without filters or a result limit: ranked keys, and
    the keys with no missing query token (full rather than partial matches)."""
    query_tokens = _unique_query_tokens(" ".join(query.split()))
    if not query_tokens:
        return {"keys": [], "full": []}
    corpus = _build_search_corpus(records)
    scored = []
    for document in corpus.documents:
        match = _match(document, query_tokens=query_tokens, corpus=corpus)
        if match is not None:
            scored.append((match[0], document.record["key"], not match[1]["missing_tokens"]))
    scored.sort(key=lambda value: value[0])
    return {
        "keys": [key for _, key, _ in scored],
        "full": [key for _, key, full in scored if full],
    }


def record(key: str, name: str, **fields) -> dict:
    return {"key": key, "slug": key, "name": name, "aliases": [], **fields}


# Each record exercises one rule a port could get wrong: description-only
# matches, aliases as name evidence, name tiers, phrase bonus, CJK bigrams,
# casefolding and accents, and the completeness and name-length tie-breakers.
SYNTHETIC = [
    record(
        "a",
        "RealBench",
        description="Evaluates numerical weather forecasting models.",
        categories=["General AI"],
        source="Claire Radar",
    ),
    record(
        "b",
        "RESCAST-100K",
        description="Residential load forecasting with weather inputs.",
        categories=["General AI"],
        publisher="Lab",
    ),
    record(
        "c",
        "WeatherBench 2",
        aliases=["WB2"],
        description="Medium-range weather prediction.",
        categories=["Science"],
        released="2023-08-01",
        has_paper=True,
    ),
    record(
        "d",
        "MMLU",
        description="Multitask language understanding.",
        categories=["Knowledge"],
        modality="text",
    ),
    record(
        "e",
        "MMLU-Pro",
        aliases=["MMLU Pro"],
        description="A harder MMLU.",
        categories=["Knowledge"],
        modality="text",
        has_repo=True,
    ),
    record(
        "f",
        "C-Eval",
        description="中文知识评测，覆盖多个学科。",
        languages=["zh"],
        categories=["Knowledge"],
    ),
    record(
        "g",
        "Straße Bench",
        description="Évaluation de la compréhension du français.",
        categories=["Multilingual"],
    ),
    record(
        "h",
        "R2HandoverSim",
        description="Robot-to-human handovers: planning feasibility and grasp stability.",
        categories=["Robotics"],
    ),
    record("i", "Grasp", description="", categories=[]),
    record("k", "Humanity's Last Exam", description="Expert questions.", categories=["Knowledge"]),
    record("l", "SafetyBench", description="", categories=[]),
    record(
        "m", "Chat Arena", description="Votes from human raters on model safety.", categories=[]
    ),
    record("j", "Planning Grasp Robot", description="", categories=["Robotics"]),
]

QUERIES = [
    "weather forecasting",
    "weather",
    "mmlu",
    "MMLU pro",
    "wb2",
    "知识评测",
    "中文",
    "strasse",
    "evaluation francais",
    "robot grasp planning",
    "grasp",
    "  Robot   GRASP ",
    "absent-term",
    "!!!",
    "saf",
    "safe",
    "hu",
    "human",
    "robot gra",
    "x",
    "gra robot gra",
    # Issue #432: every record matches at most one of these two words, in
    # description only, so the floor drops them all on both implementations.
    "forecasting prediction",
]


def test_site_search_matches_queryservice_on_rule_cases():
    site = site_ranking(SYNTHETIC, QUERIES)
    for query in QUERIES:
        assert site[query] == service_ranking(SYNTHETIC, query), query


def test_description_only_matches_are_found_on_the_site():
    # The regression in #710: these records match only through prose.
    site = site_ranking(SYNTHETIC, ["weather forecasting", "robot grasp planning"])
    assert site["weather forecasting"]["keys"][0] == "a"
    assert "h" in site["robot grasp planning"]["keys"]


def test_partial_candidates_are_distinguished_from_full_matches():
    # Search keeps records sharing one query word; only records containing every
    # word are full matches, as QueryService's missing_tokens reports.
    # Issue #432: WeatherBench 2 ("c") matched only "weather", in description
    # only, for a two-word query. That weakest tier no longer qualifies, so
    # it is dropped instead of kept as a partial candidate.
    site = site_ranking(SYNTHETIC, ["weather forecasting"])["weather forecasting"]
    assert site["full"] == ["a", "b"]
    assert "c" not in site["keys"]


def test_a_partly_typed_word_matches_words_that_start_with_it():
    # Issue #883: the search box searches as you type, so `saf` and `hu` showed
    # an empty page and `human` ranked a name that starts with it below prose.
    ranked = site_ranking(SYNTHETIC, ["saf", "hu", "human", "robot gra", "x"])
    assert ranked["saf"]["keys"] == ["l", "m"]
    assert ranked["hu"]["keys"][0] == "k" and set(ranked["hu"]["keys"]) == {"k", "m", "h"}
    assert ranked["human"]["keys"][0] == "k"
    assert "j" in ranked["robot gra"]["keys"]
    assert ranked["x"]["keys"] == []


def test_a_repeated_last_word_is_still_the_word_being_typed():
    # "gra robot gra" dedupes to two words; the prefix must stay on "gra", the
    # word the user typed last, so Grasp (which only "gra" reaches) still matches.
    assert _unique_query_tokens("gra robot gra") == ("robot", "gra")
    ranked = site_ranking(SYNTHETIC, ["gra robot gra"])["gra robot gra"]
    assert "i" in ranked["keys"]


ISSUE_883_QUERIES = ["saf", "safe", "safety", "human", "hu"]


def fixture_queries() -> list[str]:
    queries: list[str] = []
    for name in ("search_evaluation.yml", "search_relevance.yml"):
        payload = yaml.safe_load((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))
        for case in payload.get("cases") or payload.get("queries") or []:
            if isinstance(case, dict) and case.get("query"):
                queries.append(case["query"])
    return list(dict.fromkeys(queries))


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_site_search_matches_queryservice_on_the_published_catalog():
    records = json.loads(INDEX.read_text(encoding="utf-8"))["benchmarks"]
    queries = list(dict.fromkeys(fixture_queries() + ISSUE_883_QUERIES))
    assert queries
    site = site_ranking(records, queries)
    for query in queries:
        assert site[query] == service_ranking(records, query), query


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_issue_883_queries_return_records_on_the_published_catalog():
    records = json.loads(INDEX.read_text(encoding="utf-8"))["benchmarks"]
    site = site_ranking(records, ISSUE_883_QUERIES)
    for query in ("saf", "hu"):
        assert len(site[query]["keys"]) > 0, query
    names = {item["key"]: item["name"] for item in records}
    first_page = [names[key] for key in site["human"]["keys"][:50]]
    assert "Humanity's Last Exam" in first_page
