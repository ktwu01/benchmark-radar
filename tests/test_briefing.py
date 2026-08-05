import json
from datetime import UTC, datetime

from benchmark_radar.briefing import (
    MAX_HIGHLIGHTS,
    MAX_INPUT_CHARS,
    briefing_input,
    current_day_snapshot,
    daily_report_run,
    generate_daily_briefing,
    previous_calendar_day,
)
from benchmark_radar.models import AttentionObservation, RadarItem, RadarRun
from benchmark_radar.snapshots import snapshot_for_run


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


def test_briefing_input_is_bounded_and_uses_structured_highlights_only():
    items = [_item(index, title="x" * 1_000) for index in range(30)]
    value = briefing_input(snapshot_for_run(_run(items)), None)
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    assert len(encoded) <= MAX_INPUT_CHARS
    assert len(value["highlights"]) == MAX_HIGHLIGHTS
    assert all(len(item["title"]) == 160 for item in value["highlights"])
    assert "summary" not in encoded


def test_categories_compare_only_under_the_same_taxonomy():
    previous = {
        "date": "2026-08-03",
        "evidence_items": [_item(1).to_dict()],
        "attention": {"observations": []},
        "selection": {"taxonomy_version": "older-taxonomy"},
    }

    current = snapshot_for_run(_run([_item(2)]))
    assert "categories" not in briefing_input(current, previous)["change"]
    previous["selection"]["taxonomy_version"] = "taxonomy-v2"
    assert briefing_input(current, previous)["change"]["categories"] == {}


def test_current_day_snapshot_merges_both_scheduled_passes():
    morning = snapshot_for_run(_run([_item(1)]))
    afternoon = _run([_item(2)])

    merged = current_day_snapshot([morning], afternoon)

    assert {item["source_id"] for item in merged["evidence_items"]} == {
        "org/repo-1",
        "org/repo-2",
    }


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


def test_new_items_use_cross_source_artifact_identity():
    prior_item = _item(1).to_dict()
    current_item = RadarItem(
        source="Semantic Scholar",
        source_id="paper-1",
        title="The same benchmark",
        url="https://www.semanticscholar.org/paper/paper-1",
        artifact_urls=[prior_item["url"]],
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
    )
    previous = snapshot_for_run(_run([_item(1)]))
    previous["date"] = "2026-08-03"

    value = briefing_input(snapshot_for_run(_run([current_item])), previous)

    assert value["new_item_count"] == 0
    assert value["highlights"] == []


def test_new_items_are_unique_after_alias_resolution():
    repository = _item(1)
    paper = RadarItem(
        source="arXiv",
        source_id="2608.00001",
        title="Paper for the repository",
        url="https://arxiv.org/abs/2608.00001",
        artifact_urls=[repository.url],
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
    )

    value = briefing_input(snapshot_for_run(_run([repository, paper])), None)

    assert value["new_item_count"] == 1
    assert len(value["highlights"]) == 1


def test_generate_daily_briefing_caps_api_and_sanitizes_output(monkeypatch):
    captured = {}

    def fake_post(url, payload, **kwargs):
        captured.update(url=url, payload=payload, kwargs=kwargs)
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                "## Briefing\n- One new benchmark.\n"
                                "<!-- hidden -->\n2. Evidence rose."
                            ),
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr("benchmark_radar.briefing.post_json", fake_post)

    bullets = generate_daily_briefing(snapshot_for_run(_run([_item(1)])), None, "secret")

    assert bullets == ["One new benchmark.", "Evidence rose."]
    assert captured["payload"]["max_output_tokens"] == 220
    assert len(captured["payload"]["input"]) <= MAX_INPUT_CHARS
    assert captured["kwargs"]["attempts"] == 2
    assert captured["kwargs"]["timeout"] == 10.0
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer secret"}
