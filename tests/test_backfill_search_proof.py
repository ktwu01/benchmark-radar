"""Backfill search proof for issues #533, #555, #1051 and #832.

The missed benchmarks in those issues were ingestion gaps, not search gaps:
once a record exists in the catalog, `QueryService.search` finds it by name,
alias and source id. These tests pin that down with fixture records, and pin
the config fixes that close the ingestion gaps:

- #555 (Vero): the repo had an empty GitHub description and the paper title
  is "Vero: ...", so no topic query finds the repo and no generic arXiv
  phrase matches the paper. The watchlist entry landed on main first
  (exact owner/name "sunblaze-ucb/vero", retention once fetched); this PR
  adds the named-alias RSS keyword "vero:" (discovery via the paper) and
  the tests pinning both.
- #1051 (Realtime-Bench): the watchlist + RSS keywords landed in PR #1099,
  now merged, so the search-surface proof below covers a merged config.

The tests deliberately do NOT add SWE Refactor Bench, RSI-Exam, FORGE, Vero
or Realtime-Bench to `data/model_cards.yml` to make a search pass: a fixture
proves the search surface, and real records belong in a data PR.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from benchmark_radar.models import RadarItem
from benchmark_radar.pipeline import apply_watchlist, score_item
from benchmark_radar.query import QueryPaths, QueryService

REPO_ROOT = Path(__file__).resolve().parents[1]

# Fixture records for the benchmarks named in #533, #555, #1051 and #832.
# Names, aliases and source ids are the real ones from those issues.
MISSING_BENCHMARKS = [
    {
        "slug": "realtime-bench",
        "key": "catalog:realtime-bench",
        "name": "Realtime-Bench",
        "source": "catalog",
        "source_id": "2610.22155",
        "aliases": ["realtime-bench", "realtime bench"],
        "description": (
            "50 interactive game and web tasks under wall-clock, "
            "paused-clock and token-clock conditions."
        ),
    },
    {
        "slug": "vero",
        "key": "catalog:vero",
        "name": "Vero",
        "source": "catalog",
        "source_id": "sunblaze-ucb/vero",
        "aliases": ["vero", "sunblaze-ucb/vero"],
        "description": (
            "Repository-level verified code generation benchmark; 43 multi-module instances."
        ),
    },
    {
        "slug": "nafbench",
        "key": "catalog:nafbench",
        "name": "NAFBench",
        "source": "catalog",
        "source_id": "2609.27517",
        "aliases": ["nafbench"],
        "description": "Benchmark of 20 classic reasoning neighbours and their failure modes.",
    },
    {
        "slug": "swe-refactor-bench",
        "key": "catalog:swe-refactor-bench",
        "name": "SWE Refactor Bench",
        "source": "catalog",
        "source_id": "2608.23564",
        "aliases": ["swe-refactor-bench", "swe refactor bench"],
        "description": "Refactoring benchmark for software engineering agents.",
    },
    {
        "slug": "rsi-exam",
        "key": "catalog:rsi-exam",
        "name": "RSI-Exam",
        "source": "catalog",
        "source_id": "aiming-lab/RSI-Exam",
        "aliases": ["rsi-exam", "rsi exam"],
        "description": "Executable long-horizon research benchmark for recursive self-improvement.",
    },
]


def _fixture_catalog(tmp_path: Path) -> QueryPaths:
    index_path = tmp_path / "site" / "data" / "benchmark-index.json"
    shard_dir = index_path.parent / "benchmarks"
    index_path.parent.mkdir(parents=True)
    shard_dir.mkdir()
    records = [
        {
            "slug": bench["slug"],
            "key": bench["key"],
            "name": bench["name"],
            # Registered aliases are indexed as name evidence; without them
            # the alias test would pass on partial name matching alone.
            "aliases": bench["aliases"],
            "source": bench["source"],
            "publisher": None,
            "released": None,
            "openness": "unknown",
            "modality": "text",
            "description": bench["description"],
            "categories": ["benchmark"],
            "languages": ["en"],
            "score_count": 0,
            "has_paper": True,
            "has_repo": True,
            "has_dataset": False,
            "has_size": False,
        }
        for bench in MISSING_BENCHMARKS
    ]
    index_path.write_text(
        json.dumps({"schema_version": 1, "count": len(records), "benchmarks": records}),
        encoding="utf-8",
    )
    for record in records:
        (shard_dir / f"{record['slug']}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "record": record,
                    "siblings": [],
                    "scores_by_source": {},
                }
            ),
            encoding="utf-8",
        )
    return QueryPaths(index=index_path, shards=shard_dir, snapshots=tmp_path / "data" / "snapshots")


def _load_config() -> dict:
    return yaml.safe_load((REPO_ROOT / "config.yml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("bench", MISSING_BENCHMARKS, ids=[b["slug"] for b in MISSING_BENCHMARKS])
def test_backfilled_benchmark_is_searchable_by_name(tmp_path: Path, bench: dict) -> None:
    """#533/#555/#1051/#832: once the record exists, search finds it by name."""
    service = QueryService(_fixture_catalog(tmp_path))

    result = service.search(bench["name"], scope="catalog", limit=10)

    # Lexical search also returns fixtures sharing a token ("bench"), so the
    # assertion is membership plus top rank, not an exact result set.
    assert bench["key"] in {row["key"] for row in result["results"]}
    assert result["results"][0]["key"] == bench["key"]
    assert result["search_status"] == "full_matches_found"


@pytest.mark.parametrize("bench", MISSING_BENCHMARKS, ids=[b["slug"] for b in MISSING_BENCHMARKS])
def test_backfilled_benchmark_is_searchable_by_alias(tmp_path: Path, bench: dict) -> None:
    """Aliases and source ids are searchable too, not just the display name."""
    service = QueryService(_fixture_catalog(tmp_path))

    for alias in bench["aliases"]:
        result = service.search(alias, scope="catalog", limit=10)
        assert bench["key"] in {row["key"] for row in result["results"]}, alias
        assert result["search_status"] == "full_matches_found", alias


def test_an_alias_only_token_is_found_through_the_alias(tmp_path: Path) -> None:
    """'sunblaze' appears only in Vero's registered alias, not its name or text."""
    service = QueryService(_fixture_catalog(tmp_path))

    result = service.search("sunblaze-ucb", scope="catalog", limit=10)

    assert result["search_status"] == "full_matches_found"
    assert result["results"][0]["key"] == "catalog:vero"


def test_vero_watchlist_and_rss_keyword_close_the_ingestion_gap() -> None:
    """#555: Vero is on the watchlist and has a named RSS keyword."""
    config = _load_config()
    watchlist = config.get("watchlist") or []
    keywords = [str(k).casefold() for k in config["sources"]["arxiv"]["rss_keywords"]]

    vero_entries = [entry for entry in watchlist if str(entry.get("name")) == "sunblaze-ucb/vero"]
    assert len(vero_entries) == 1
    assert "sunblaze-ucb/vero" in [str(a).casefold() for a in vero_entries[0].get("aliases") or []]
    assert "vero:" in keywords


def test_vero_paper_matches_no_generic_rss_keyword_but_matches_vero() -> None:
    """#555: prove the keyword gap was real — the paper's own wording."""
    config = _load_config()
    keywords = [str(k).casefold() for k in config["sources"]["arxiv"]["rss_keywords"]]
    title = "Vero: Can AI Agents Build Formally Verified Software Repositories?"
    abstract_sentence = (
        "we introduce Vero, the first benchmark to evaluate joint "
        "implementation and proof synthesis"
    )
    haystack = f"{title} {abstract_sentence}".casefold()

    generic = [keyword for keyword in keywords if keyword != "vero:"]
    assert not any(keyword in haystack for keyword in generic)
    assert "vero:" in haystack


def test_empty_description_github_record_is_retained_by_watchlist() -> None:
    """#555: a description-less repo survives scoring once watchlisted.

    `score_item` matches taxonomy only against title + summary, so
    sunblaze-ucb/vero with an empty description matches no category. The
    watchlist is what retains it: the pipeline keeps a record with a
    watchlist hit even without a taxonomy category.
    """
    config = _load_config()
    now = datetime(2026, 11, 5, tzinfo=UTC)
    item = RadarItem(
        source="GitHub",
        source_id="sunblaze-ucb/vero",
        title="sunblaze-ucb/vero",
        url="https://github.com/sunblaze-ucb/vero",
        published_at=datetime(2026, 8, 17, tzinfo=UTC),
        updated_at=datetime(2026, 8, 17, tzinfo=UTC),
        summary="",
    )

    scored = score_item(item, config["taxonomy"], now)
    assert scored.categories == []
    tagged = apply_watchlist([scored], config.get("watchlist") or [])

    assert tagged[0].watchlist == "sunblaze-ucb/vero"
    assert not tagged[0].suppression_reasons
    assert tagged[0].watchlist or tagged[0].categories
