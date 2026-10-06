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


def test_report_distinguishes_release_and_update_dates():
    record = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="Updated benchmark suite",
        url="https://github.com/org/repo",
        published_at=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at=datetime(2026, 7, 27, tzinfo=UTC),
        categories=["benchmark"],
    )

    report = render_markdown(_run([record]))

    assert "Published: `2026-06-01`" in report
    assert "Updated: `2026-07-27`" in report
    assert "Published/updated" not in report


def test_source_health_names_each_connectors_collection_method():
    # Issue #174: every row of the Source health table looked the same at a
    # glance, so a stalled RSS feed and a broken search API read as identical
    # failures. The Method column (populated by the pipeline from what a run
    # actually did, see sources.collection_method) surfaces the difference.
    run = RadarRun(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        since=datetime(2026, 7, 25, tzinfo=UTC),
        items=[],
        health=[
            SourceHealth(source="arxiv", ok=True, item_count=0, method="RSS"),
            SourceHealth(
                source="brave",
                ok=False,
                error="RuntimeError: BRAVE_API_KEY is not configured",
                method="API",
            ),
        ],
    )

    report = render_markdown(run)

    assert "| arxiv | RSS |" in report
    assert "| brave | API |" in report


def test_attention_feed_health_layer_is_not_the_ambiguous_radar_ingest_label():
    # Issue #174: the Layer column read the literal string "Radar ingest" for
    # every attention-layer row, which restates the project's own name and
    # tells the reader nothing about what actually ran.
    run = RadarRun(
        generated_at=datetime(2026, 7, 27, tzinfo=UTC),
        since=datetime(2026, 7, 25, tzinfo=UTC),
        items=[],
        health=[],
        attention_ingest_health=[
            SourceHealth(source="Hacker News collector", kind="attention", ok=True, item_count=18)
        ],
    )

    report = render_markdown(run)

    assert "Radar ingest" not in report
    assert "| Attention ingest | Hacker News collector |" in report


def test_empty_report_explains_eligibility_not_recommendation_threshold():
    report = render_markdown(
        RadarRun(
            generated_at=datetime(2026, 7, 27, tzinfo=UTC),
            since=datetime(2026, 7, 25, tzinfo=UTC),
            items=[],
            health=[],
        )
    )

    assert "## No eligible signals" in report
    assert "suppressed or lacked a taxonomy or watchlist match" in report
    assert "relevance threshold" not in report


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


def test_report_names_duplicate_observations_merged_by_dedupe():
    run = _run([_record(1)])
    run.selection = {
        "fetched": 3,
        "merged_as_duplicate": 2,
        "deduplicated": 1,
        "eligible": 1,
        "published": 1,
    }

    report = render_markdown(run)

    assert "**2** duplicate observations merged → **1** after dedupe" in report


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


def test_report_places_escaped_daily_briefing_before_counts():
    report = render_markdown(
        _run([_record(1)]),
        daily_briefing=["One new benchmark | from GitHub", "Evidence rose by 1."],
    )

    assert "- One new benchmark \\| from GitHub" in report
    assert report.index("## Daily briefing") < report.index("## At a glance")


def test_report_proves_the_gpt_call_and_links_only_trusted_citations():
    report = render_markdown(
        _run([_record(1)]),
        daily_briefing=["A grounded finding. Evidence: E001."],
        daily_briefing_metadata={
            "generator": "openai-responses",
            "model": "gpt-5.6",
            "usage": {"input_tokens": 8123, "output_tokens": 241},
            "input": {"evidence_items": 42, "history_days": 10},
            "caveat": "The feed is not a representative sample.",
            "citations": [
                {
                    "id": "E001",
                    "title": "MemoryBench](https://evil.test)",
                    "url": "https://example.test/memory_(safe)",
                    "source": "arXiv",
                }
            ],
        },
    )

    assert "GPT synthesis: gpt-5.6 via OpenAI Responses API" in report
    assert "8,123 input / 241 output tokens" in report
    assert "42 evidence records and 10 history days injected" in report
    assert "[MemoryBench\\]\\(https://evil\\.test\\)]" in report
    assert "(https://example.test/memory_%28safe%29)" in report
    assert "[MemoryBench](https://evil.test)" not in report


def test_report_distinguishes_latest_pass_from_merged_daily_total():
    run = _run([_record(1), _record(2)])
    run.selection = {
        "fetched": 4,
        "deduplicated": 3,
        "qualified": 1,
        "published": 1,
        "published_total": 2,
        "minimum_score": 40,
    }

    report = render_markdown(run)

    assert "Latest-pass selection" in report
    assert "**2** across today's collection passes" in report


def test_the_funnel_shows_why_records_failed_qualification():
    # Issue #124: the rendered funnel stepped from "after dedupe" straight to
    # "qualified", leaving the largest drop in the pipeline unexplained.
    run = _run([_record(1)])
    run.selection = {
        "fetched": 700,
        "deduplicated": 686,
        "scored": 686,
        "qualified": 101,
        "published": 101,
        "suppressed_low_value": 1,
        "suppressed_below_minimum": 562,
        "suppressed_uncategorized": 22,
        "minimum_score": 40.0,
        "watchlisted": 0,
    }

    markdown = render_markdown(run)

    assert "**562** below 40 →" in markdown
    assert "**22** uncategorized →" in markdown


def test_the_funnel_omits_qualification_reasons_on_older_snapshots():
    # Snapshots written before the counters existed cannot attribute the gap, so
    # the renderer says nothing rather than printing a misleading zero.
    run = _run([_record(1)])
    run.selection = {
        "fetched": 700,
        "deduplicated": 686,
        "scored": 686,
        "qualified": 101,
        "published": 101,
        "minimum_score": 40.0,
    }

    markdown = render_markdown(run)

    assert "below 40 →" not in markdown
    assert "uncategorized →" not in markdown


def test_current_funnel_reports_recommendation_without_dropping_records():
    run = _run([_record(1, recommended=True), _record(2)])
    run.selection = {
        "fetched": 3,
        "deduplicated": 3,
        "scored": 3,
        "eligible": 2,
        "qualified": 2,
        "published": 2,
        "suppressed_uncategorized": 1,
        "recommended": 1,
        "not_recommended": 1,
        "recommendation_score": 40,
        "minimum_score": 40,
    }

    markdown = render_markdown(run)

    assert "**2** eligible → **2** retained" in markdown
    assert "**1** score 40 or above; **1** retained without the badge" in markdown
    assert "below 40 →" not in markdown


def test_merged_report_counts_badges_over_the_daily_union():
    run = _run([_record(1, recommended=True)])
    run.selection = {
        "fetched": 0,
        "deduplicated": 0,
        "eligible": 0,
        "published": 0,
        "published_total": 1,
        "recommended": 0,
        "not_recommended": 0,
        "recommendation_score": 40,
    }

    markdown = render_markdown(run)

    assert "**1** ranked evidence items" in markdown
    assert "Recommendation: **1** score 40 or above; **0** retained without the badge" in markdown


def test_ranked_evidence_links_escape_source_labels_and_destinations():
    record = _record(1)
    record.title = "MemoryBench](https://wrong.test)"
    record.url = "https://example.test/bench)version"
    record.artifact_urls = ["https://example.test/data)version"]
    report = render_markdown(_run([record]))
    assert (
        "[MemoryBench\\]\\(https://wrong\\.test\\)](https://example.test/bench%29version)" in report
    )
    assert "[related source](https://example.test/data%29version)" in report
    assert "[MemoryBench](https://wrong.test)" not in report
