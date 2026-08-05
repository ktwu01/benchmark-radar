import json
from datetime import UTC, datetime

from benchmark_radar.briefing import (
    MAX_HIGHLIGHTS,
    MAX_INPUT_CHARS,
    briefing_input,
    generate_daily_briefing,
    previous_calendar_day,
)
from benchmark_radar.models import RadarItem, RadarRun


def _item(index: int, *, title: str | None = None) -> RadarItem:
    return RadarItem(
        source="GitHub",
        source_id=f"org/repo-{index}",
        title=title or f"Benchmark {index}",
        url=f"https://github.com/org/repo-{index}",
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
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
    value = briefing_input(_run(items), None)
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

    assert "categories" not in briefing_input(_run([_item(2)]), previous)["change"]
    previous["selection"]["taxonomy_version"] = "taxonomy-v2"
    assert briefing_input(_run([_item(2)]), previous)["change"]["categories"] == {}


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

    bullets = generate_daily_briefing(_run([_item(1)]), None, "secret")

    assert bullets == ["One new benchmark.", "Evidence rose."]
    assert captured["payload"]["max_output_tokens"] == 220
    assert len(captured["payload"]["input"]) <= MAX_INPUT_CHARS
    assert captured["kwargs"]["attempts"] == 2
    assert captured["kwargs"]["timeout"] == 10.0
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer secret"}
