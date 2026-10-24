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

from benchmark_radar.query import _build_search_corpus, _match, _tokens

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
    query_tokens = tuple(dict.fromkeys(_tokens(" ".join(query.split()))))
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
    site = site_ranking(SYNTHETIC, ["weather forecasting"])["weather forecasting"]
    assert site["full"] == ["a", "b"]
    assert "c" in site["keys"] and "c" not in site["full"]


def fixture_queries() -> list[str]:
    queries: list[str] = []
    for name in ("search_evaluation.yml", "search_relevance.yml"):
        payload = yaml.safe_load((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))
        for case in payload.get("cases") or payload.get("queries") or []:
            if isinstance(case, dict) and case.get("query"):
                queries.append(case["query"])
    return list(dict.fromkeys(queries))


def _prefix_catalog() -> list[dict]:
    """Records that separate a typed word-start from an exact token.

    SafetyBench and Safe Harbor contain no standalone "saf" token. Humanity's
    Last Exam only contains "human" inside a sentence, while fifty-five other
    records repeat that word. A whole-word gate therefore returns nothing for
    "saf" and "hu", and buries the exam name past the first page of "human".
    """
    records = [
        record(
            "safetybench",
            "SafetyBench",
            description="Refusal and harmful-content measurements.",
            categories=["Safety"],
        ),
        record(
            "safe-harbor",
            "Safe Harbor",
            description="A narrow protocol.",
            categories=["Protocol"],
        ),
        record(
            "translation",
            "Translation Bench",
            description="English to French quality.",
            categories=["Language"],
        ),
        record(
            "hle",
            "Humanity's Last Exam",
            description="A closed exam. The notes mention one human rater.",
            categories=["Knowledge"],
            has_paper=True,
        ),
        record(
            "humaneval",
            "HumanEval",
            description="Docstring code generation.",
            categories=["Code"],
            has_repo=True,
        ),
    ]
    records.extend(
        record(
            f"mention-{index:02d}",
            f"Mention {index:02d}",
            description="human " * 12,
            categories=["General"],
        )
        for index in range(55)
    )
    return records


def test_partial_words_find_records_whose_words_start_with_them():
    # Issue #883: the search box searches as you type. A whole-word gate shows
    # an empty catalog for "saf" and "hu", and ranks Humanity's Last Exam off
    # the first page of "human" because the name token is "humanity".
    records = _prefix_catalog()
    queries = ["saf", "safe", "safety", "human", "hu"]
    site = site_ranking(records, queries)
    for query in queries:
        assert site[query] == service_ranking(records, query), query

    assert set(service_ranking(records, "saf")["keys"]) == {"safetybench", "safe-harbor"}
    # "safe" is already a whole word, so it stays on Safe Harbor and does not
    # recruit SafetyBench. "safety" is not a whole word here, so it does.
    safe_keys = set(service_ranking(records, "safe")["keys"])
    assert "safe-harbor" in safe_keys
    assert "safetybench" not in safe_keys
    assert "translation" not in safe_keys
    assert service_ranking(records, "safety")["keys"] == ["safetybench"]
    human = service_ranking(records, "human")["keys"]
    assert human.index("hle") < 50
    hu = service_ranking(records, "hu")["keys"]
    assert {"hle", "humaneval"} <= set(hu)


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_site_search_matches_queryservice_on_the_published_catalog():
    records = json.loads(INDEX.read_text(encoding="utf-8"))["benchmarks"]
    queries = fixture_queries()
    assert queries
    site = site_ranking(records, queries)
    for query in queries:
        assert site[query] == service_ranking(records, query), query
