"""The Library view merged from benchmark-radar.com (#420)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import _library_seed

ROOT = Path(__file__).resolve().parents[1]

TAXONOMY = {
    "groups": [{"id": "reasoning", "name": "Reasoning & Knowledge"}],
    "categories": [
        {"id": "math", "group": "reasoning", "name": "Math Reasoning"},
        {"id": "science", "group": "reasoning", "name": "Science"},
    ],
}


def test_library_behaviour_runs_against_the_production_functions():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/library_harness.mjs"], check=True, timeout=60, cwd=ROOT)


def test_seed_publishes_crawlable_direction_links_and_newest_rows():
    records = [
        {
            "slug": "old",
            "key": "k:old",
            "name": "Old <Bench>",
            "source": "model_reports",
            "released": "2024-01-01",
            "description": "Older.",
            "library_direction": {"primary": "math", "categories": ["math", "science"]},
        },
        {
            "slug": "new",
            "key": "k:new",
            "name": "New Bench",
            "source": "claire_radar",
            "released": "2026-10-01",
            "description": "",
            "library_direction": None,
        },
    ]

    seeds = _library_seed(records, TAXONOMY)
    nav, rows, status = seeds.values()

    assert '<a class="library-direction" href="/library/?dir=math">' in nav
    assert '<span class="library-direction-count">1</span>' in nav
    # Newest first, each row a link to the benchmark's own page, names escaped.
    assert rows.index("/benchmarks/new/") < rows.index("/benchmarks/old/")
    assert "Old &lt;Bench&gt;" in rows
    # Every filed direction, as the live row shows it, not only the primary.
    assert "Math Reasoning · Science" in rows
    assert "2 of 2 benchmarks" in status


def test_seed_breaks_release_date_ties_like_the_live_list():
    # libraryCompare sorts the date descending, then name and key ascending by
    # code point; the seed must list the same first page in the same order.
    records = [
        {"slug": s, "key": f"k:{s}", "name": n, "source": "x", "released": "2026-01-01"}
        for s, n in (("z", "beta"), ("y", "Alpha"), ("x", "alpha"))
    ]
    rows = _library_seed(records, TAXONOMY)['<div id="library-list" class="library-list"></div>']
    assert (
        rows.index("/benchmarks/y/") < rows.index("/benchmarks/x/") < rows.index("/benchmarks/z/")
    )


def test_no_taxonomy_publishes_no_library_page():
    assert _library_seed([{"slug": "a", "name": "A", "source": "x"}], None) == {}


def test_directions_are_kept_apart_from_searchable_categories():
    # The direction is a reviewed classification, so it must never feed the
    # source categories that search ranks on.
    script = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    search = ROOT / "site" / "assets" / "catalog-search.js"
    rows = script.split("function libraryMatches()", 1)[1].split("\n}", 1)[0]
    assert "searchBenchmarkIndex(records, state.libraryQuery)" in rows
    if search.exists():
        assert "library_direction" not in search.read_text(encoding="utf-8")
