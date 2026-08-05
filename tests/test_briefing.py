from datetime import UTC, datetime

from benchmark_radar.briefing import (
    current_day_snapshot,
    daily_report_run,
    markdown_bullet,
    previous_calendar_day,
)
from benchmark_radar.models import AttentionObservation, RadarItem, RadarRun
from benchmark_radar.snapshots import merge_snapshots, snapshot_for_run


def _item(index: int, *, title: str | None = None) -> RadarItem:
    return RadarItem(
        source="GitHub",
        source_id=f"org/repo-{index}",
        title=title or f"Benchmark {index}",
        url=f"https://github.com/org/repo-{index}",
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
    )


def _attention(index: int) -> AttentionObservation:
    observed = datetime(2026, 8, 4, tzinfo=UTC)
    return AttentionObservation(
        observation_id=f"producer:{index}",
        producer="producer",
        source="Hacker News",
        source_id=str(index),
        title=f"Discussion {index}",
        url=f"https://news.ycombinator.com/item?id={index}",
        published_at=observed,
        discovered_at=observed,
        observed_at=observed,
    )


def _run(items=None) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 8, 4, 12, tzinfo=UTC),
        since=datetime(2026, 8, 2, 12, tzinfo=UTC),
        items=items or [],
        health=[],
        selection={"taxonomy_version": "taxonomy-v2"},
    )


def test_previous_calendar_day_ignores_same_day_and_older_gap():
    snapshots = [
        {"date": "2026-08-01"},
        {"date": "2026-08-03"},
        {"date": "2026-08-04"},
    ]

    assert previous_calendar_day(snapshots, _run()) == {"date": "2026-08-03"}
    assert previous_calendar_day([snapshots[0], snapshots[2]], _run()) is None


def test_current_day_snapshot_merges_both_scheduled_passes():
    morning = snapshot_for_run(_run([_item(1)]))
    afternoon = _run([_item(2)])

    merged = current_day_snapshot([morning], afternoon)

    assert {item["source_id"] for item in merged["evidence_items"]} == {
        "org/repo-1",
        "org/repo-2",
    }


def test_current_day_snapshot_reranks_the_merged_items():
    morning_item = _item(1)
    morning_item.total_score = 50
    afternoon_item = _item(2)
    afternoon_item.total_score = 90

    merged = current_day_snapshot(
        [snapshot_for_run(_run([morning_item]))],
        _run([afternoon_item]),
    )

    assert [item["source_id"] for item in merged["evidence_items"]] == [
        "org/repo-2",
        "org/repo-1",
    ]


def test_current_day_snapshot_unions_attention_from_both_passes():
    morning_run = _run([_item(1)])
    morning_run.attention = [_attention(1)]
    afternoon_run = _run([_item(2)])
    afternoon_run.attention = [_attention(2)]

    merged = current_day_snapshot([snapshot_for_run(morning_run)], afternoon_run)

    assert {item["observation_id"] for item in merged["attention"]["observations"]} == {
        "producer:1",
        "producer:2",
    }


def test_daily_report_run_uses_the_merged_snapshot_scope():
    morning = snapshot_for_run(_run([_item(1)]))
    merged = current_day_snapshot([morning], _run([_item(2)]))

    report_run = daily_report_run(merged, _run([_item(2)]))

    assert {item.source_id for item in report_run.items} == {"org/repo-1", "org/repo-2"}
    assert report_run.selection["published_total"] == 2


def test_snapshot_for_run_persists_the_briefing_with_its_day():
    run = _run([_item(1)])
    run.daily_briefing = ["One new benchmark.", "Evidence rose."]

    snapshot = snapshot_for_run(run)

    assert snapshot["briefing"] == {
        "date": "2026-08-04",
        "bullets": ["One new benchmark.", "Evidence rose."],
    }


def test_snapshot_for_run_omits_the_briefing_when_the_day_has_none():
    # An absent key is what tells a later pass the day still needs one, so it
    # must not be written as an empty placeholder.
    assert "briefing" not in snapshot_for_run(_run([_item(1)]))


def test_merge_snapshots_keeps_the_first_briefing_of_the_day():
    run = _run([_item(1)])
    run.daily_briefing = ["First pass."]
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_briefing = ["Second pass."]

    merged = merge_snapshots(existing, snapshot_for_run(later))

    # One briefing per day: the earlier pass committed the day's text and a
    # later pass must not overwrite it.
    assert merged["briefing"]["bullets"] == ["First pass."]


def test_merge_snapshots_accepts_a_briefing_when_the_day_had_none():
    existing = snapshot_for_run(_run([_item(1)]))
    retried = _run([_item(2)])
    retried.daily_briefing = ["Recovered on a later pass."]

    merged = merge_snapshots(existing, snapshot_for_run(retried))

    # The first pass failed the call or had no key, so a later pass supplies it.
    assert merged["briefing"]["bullets"] == ["Recovered on a later pass."]


def test_merge_snapshots_leaves_no_briefing_key_when_neither_pass_had_one():
    merged = merge_snapshots(snapshot_for_run(_run([_item(1)])), snapshot_for_run(_run([_item(2)])))

    assert "briefing" not in merged


def test_markdown_bullet_escapes_interpolated_values():
    # Findings are computed rather than written by a model, but the bullets still
    # interpolate upstream-derived values. A category or source name is data and
    # must not become Markdown or HTML in the published issue body.
    assert markdown_bullet("data_quality rose 5%") == "data\\_quality rose 5%"
    assert markdown_bullet("<img src=x> [link](http://evil.test)") == (
        "&lt;img src=x&gt; \\[link\\]\\(http://evil\\.test\\)"
    )
