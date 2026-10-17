"""Trends' research-direction table (#420): one computation, two languages."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import _direction_trends_seed
from benchmark_radar.library_directions import direction_trend_rows, discovery_anchor

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "site" / "data" / "benchmark-index.json"
TAXONOMY = {
    "groups": [{"id": "g", "name": "Group"}],
    "categories": [
        {"id": "math", "group": "g", "name": "Math"},
        {"id": "science", "group": "g", "name": "Science"},
    ],
}


def record(released, categories=None, source="claire_radar", collected_at="2026-10-14T09:44:51Z"):
    return {
        "released": released,
        "source": source,
        "collected_at": collected_at,
        "library_direction": {"primary": categories[0], "categories": categories}
        if categories
        else None,
    }


def site_rows(records, taxonomy, anchor, windows):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "tests/direction_trends_harness.mjs"],
        input=json.dumps(
            {"records": records, "taxonomy": taxonomy, "anchor": anchor, "windows": windows}
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)["models"]


def site_anchor(records):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    completed = subprocess.run(
        [node, "tests/direction_trends_harness.mjs"],
        input=json.dumps(
            {"records": records, "taxonomy": TAXONOMY, "anchor": "2026-10-14", "windows": []}
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        cwd=ROOT,
    )
    return json.loads(completed.stdout)["anchor"]


def as_python(model):
    return {
        "anchor": model["anchor"],
        "window_days": model["windowDays"],
        "discovery_since": model["discoverySince"],
        "comparable": model["comparable"],
        "rows": model["rows"],
    }


def test_windows_count_secondary_directions_and_unclassified_records():
    records = [
        record("2026-10-14", ["math", "science"]),
        record("2026-09-20", ["math"]),
        record("2026-10-01"),
        record("2026-05-01", ["math"]),
        record("2026-10-20", ["math"]),  # after the anchor: not yet released
    ]
    model = direction_trend_rows(records, TAXONOMY, "2026-10-14", 30)
    rows = {row["id"]: row for row in model["rows"]}
    assert model["discovery_since"] == "2026-05-01"
    assert rows["math"]["current"] == 2
    assert rows["science"]["current"] == 1
    assert rows["unclassified"]["current"] == 1
    assert model["rows"][-1]["id"] == "unclassified"
    assert rows["math"]["weekly"][-1] == 1


def test_no_comparison_or_bar_before_the_discovery_stream_starts():
    # A previous window that starts before the stream would undercount and
    # fake growth, so it is absent rather than zero.
    records = [record("2026-09-01", ["math"]), record("2026-10-10", ["math"])]
    model = direction_trend_rows(records, TAXONOMY, "2026-10-14", 30)
    rows = {row["id"]: row for row in model["rows"]}
    assert model["comparable"] is False
    assert rows["math"]["previous"] is None
    assert rows["math"]["weekly"][0] is None
    assert rows["math"]["weekly"][-1] == 1


def test_site_and_python_agree_on_rule_cases():
    records = [
        record("2026-10-14", ["math", "science"]),
        record("2026-09-20", ["math"]),
        record("2026-10-01"),
        record("2026-05-01", ["math"]),
        record("2026-01-01", ["science"], source="opencompass_hub"),
    ]
    for model in site_rows(records, TAXONOMY, "2026-10-14", [30, 60, 90]):
        assert as_python(model) == direction_trend_rows(
            records, TAXONOMY, "2026-10-14", model["windowDays"]
        )


@pytest.mark.skipif(not INDEX.exists(), reason="build the data release first")
def test_site_and_python_agree_on_the_published_catalog():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    taxonomy = index["library_taxonomy"]
    anchor = discovery_anchor(index["benchmarks"])
    assert site_anchor(index["benchmarks"]) == anchor
    for model in site_rows(index["benchmarks"], taxonomy, anchor, [30, 60, 90]):
        assert as_python(model) == direction_trend_rows(
            index["benchmarks"], taxonomy, anchor, model["windowDays"]
        )


def test_seed_shows_the_section_with_default_window_rows():
    seeds = _direction_trends_seed({}, [record("2026-10-10", ["math"])], TAXONOMY)
    note, section, body = seeds.values()
    # The caveats travel with the seeded numbers.
    assert "30 days to Oct 14, 2026" in note
    assert "rows overlap and do not add up" in note
    assert "hidden" not in section
    assert '<a href="/library/?dir=math">Math</a>' in body
    # The sixteen weekly values are text for screen readers, not only bars.
    assert '<span class="visually-hidden">Weekly new records, oldest first:' in body
    # Without a discovery crawl there is no window to anchor.
    assert _direction_trends_seed({}, [record("2026-10-10", ["math"], source="x")], TAXONOMY) == {}


def test_undated_records_are_counted_not_dropped():
    model = direction_trend_rows(
        [record(None, ["math"]), record("2026-10-10", ["math"])], TAXONOMY, "2026-10-14", 30
    )
    math = next(row for row in model["rows"] if row["id"] == "math")
    assert (math["current"], math["undated"]) == (1, 1)


def test_windows_end_at_the_discovery_crawl_not_the_daily_run():
    # The radar advances daily while the catalog stays pinned to its crawl;
    # anchoring to the crawl keeps windows from sliding over unchanged data.
    records = [
        record("2026-10-10", ["math"], collected_at="2026-10-14T09:44:51Z"),
        record("2026-05-20", ["math"], collected_at="2026-09-25T04:40:22Z"),
        record("2026-10-01", ["math"], source="llm_stats", collected_at="2026-10-30T00:00:00Z"),
    ]
    assert discovery_anchor(records) == "2026-10-14"
    assert site_anchor(records) == "2026-10-14"
