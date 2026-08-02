from datetime import UTC, datetime

from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.report import render_markdown


def test_report_contains_evidence_and_health():
    record = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="Benchmark | Suite",
        url="https://github.com/org/repo",
        published_at=datetime(2026, 7, 27, tzinfo=UTC),
        categories=["benchmark"],
        total_score=3.1,
        evidence_score=2,
        relevance_score=3,
        recency_score=4,
        rationale=["Primary source: GitHub"],
    )
    report = render_markdown(
        RadarRun(
            generated_at=datetime(2026, 7, 27, tzinfo=UTC),
            since=datetime(2026, 7, 25, tzinfo=UTC),
            items=[record],
            health=[SourceHealth(source="github", ok=True, item_count=1)],
        )
    )
    assert "Benchmark \\| Suite" in report
    assert "Primary source" in report
    assert "Source health" in report


def _record(index: int, **overrides) -> RadarItem:
    values = {
        "source": "GitHub",
        "source_id": f"org/repo{index}",
        "title": f"Benchmark suite {index}",
        "url": f"https://github.com/org/repo{index}",
        "published_at": datetime(2026, 7, 27, tzinfo=UTC),
        "categories": ["benchmark"],
        "total_score": 3.0,
    }
    values.update(overrides)
    return RadarItem(**values)


def _run(items) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        since=datetime(2026, 7, 25, tzinfo=UTC),
        items=items,
        health=[],
    )


def test_report_leads_with_watchlist_hits():
    tracked = _record(1, watchlist="MLE-bench", watchlist_note="ML engineering tasks.")

    report = render_markdown(_run([tracked, _record(2)]))

    assert "## Watchlist" in report
    assert "**MLE-bench**" in report
    assert "ML engineering tasks." in report


def test_report_truncates_the_issue_but_states_the_true_total():
    records = [_record(index) for index in range(10)]

    report = render_markdown(_run(records), issue_item_limit=3)

    assert "## Today's signals (top 3 of 10)" in report
    assert "7 further ranked records" in report
    assert "Benchmark suite 9" not in report


def test_report_shows_the_selection_funnel():
    run = _run([_record(1)])
    run.selection = {
        "fetched": 316,
        "deduplicated": 300,
        "qualified": 120,
        "published": 30,
        "minimum_score": 2.0,
    }

    report = render_markdown(run)

    assert "**316** fetched" in report
    assert "**30** published" in report


def test_report_accounts_for_future_dated_quarantine_in_the_funnel():
    run = _run([_record(1)])
    run.selection = {
        "fetched": 2,
        "suppressed_future_dated": 1,
        "deduplicated": 1,
        "qualified": 1,
        "published": 1,
        "minimum_score": 0,
    }

    report = render_markdown(run)

    assert "**2** fetched → **1** future-dated records quarantined" in report
    assert "→ **1** after dedupe" in report


def test_funnel_excludes_watchlist_bypasses_from_the_threshold_count():
    # A lone bypass must not read as "1 qualified (at or above 99)": nothing
    # met the threshold, so the two counts are reported separately.
    run = _run([_record(1, watchlist="MLE-bench")])
    run.selection = {"fetched": 5, "qualified": 1, "watchlisted": 1, "minimum_score": 99}

    report = render_markdown(run)

    assert "**1** qualified (0 at or above 99, 1 by watchlist)" in report


def test_report_links_to_date_filtered_dashboard():
    run = RadarRun(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        since=datetime(2026, 7, 25, tzinfo=UTC),
        items=[],
        health=[],
    )

    report = render_markdown(run, dashboard_url="https://example.test/radar/")

    assert (
        "[Explore this day on the dashboard](https://example.test/radar/?date=2026-07-27)" in report
    )
