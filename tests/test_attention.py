import json
from datetime import UTC, datetime

from benchmark_radar.attention import fetch_attention_feeds

LOCAL_CONFIG = {
    "hacker_news": {
        "enabled": True,
        "producer": "benchmark-social-signal",
    }
}


def local_observation(now):
    return {
        "id": "hacker-news:1",
        "source": "Hacker News",
        "source_id": "1",
        "title": "Benchmark discussion",
        "url": "https://news.ycombinator.com/item?id=1",
        "published_at": "2026-07-26T12:00:00+00:00",
        "discovered_at": now.isoformat(),
        "event_kind": "discussed",
        "categories": ["benchmark"],
        "metrics": {"points": 2},
        "rationale": ["Attention signal only"],
    }


def test_integrated_collector_preserves_legacy_observation_ids(monkeypatch):
    observed = datetime(2026, 7, 27, 12, tzinfo=UTC)
    monkeypatch.setattr(
        "benchmark_radar.attention.collect_hacker_news",
        lambda config, now, **kwargs: (
            [local_observation(now)],
            {"source": "Hacker News", "ok": True, "item_count": 1, "error": None},
        ),
    )

    observations, ingest, producer, _ = fetch_attention_feeds(
        LOCAL_CONFIG,
        observed_at=observed,
    )

    assert observations[0].observation_id == "benchmark-social-signal:hacker-news:1"
    assert observations[0].quality_scored is False
    assert ingest[0].source == "Hacker News collector"
    assert ingest[0].ok is True
    assert producer[0].producer == "benchmark-social-signal"


def test_failed_integrated_collection_carries_forward_last_healthy_observations(monkeypatch):
    observed = datetime(2026, 7, 27, 12, tzinfo=UTC)
    monkeypatch.setattr(
        "benchmark_radar.attention.collect_hacker_news",
        lambda config, now, **kwargs: (
            [local_observation(now)],
            {"source": "Hacker News", "ok": True, "item_count": 1, "error": None},
        ),
    )
    first, _, _, state = fetch_attention_feeds(LOCAL_CONFIG, observed_at=observed)
    previous = [first[0].to_dict()]
    monkeypatch.setattr(
        "benchmark_radar.attention.collect_hacker_news",
        lambda config, now, **kwargs: (
            [],
            {
                "source": "Hacker News",
                "ok": False,
                "item_count": 0,
                "error": "TimeoutError: fixture timeout",
            },
        ),
    )

    restored, ingest, producer, next_state = fetch_attention_feeds(
        LOCAL_CONFIG,
        observed_at=observed.replace(day=28),
        previous_state=state,
        previous_observations=previous,
    )

    assert [item.to_dict() for item in restored] == previous
    assert ingest[0].ok is False
    assert "TimeoutError" in ingest[0].error
    assert producer[0].ok is False
    assert next_state == state


def test_feed_is_normalized_without_quality_scores(monkeypatch):
    payload = {
        "schema_version": 1,
        "producer": "fixture",
        "observations": [
            {
                "id": "hacker-news:1",
                "source": "Hacker News",
                "source_id": "1",
                "title": "Benchmark discussion",
                "url": "https://news.ycombinator.com/item?id=1",
                "published_at": "2026-07-26T12:00:00+00:00",
                "discovered_at": "2026-07-27T10:00:00+00:00",
                "event_kind": "discussed",
                "categories": ["benchmark"],
                "metrics": {"points": 2},
                "rationale": ["Attention only"],
                "supporting_observations": [
                    {
                        "source_id": "2",
                        "url": "https://news.ycombinator.com/item?id=2",
                        "published_at": "2026-07-26T11:00:00+00:00",
                        "metrics": {"points": 1},
                    }
                ],
            }
        ],
        "health": [{"source": "Hacker News", "ok": True, "item_count": 1}],
    }
    monkeypatch.setattr("benchmark_radar.attention.get_json", lambda url: payload)
    observed = datetime(2026, 7, 27, 12, tzinfo=UTC)

    observations, ingest, producer, state = fetch_attention_feeds(
        {"feeds": [{"name": "Fixture", "url": "https://example.test/feed.json"}]},
        observed_at=observed,
    )

    assert observations[0].observation_id == "fixture:hacker-news:1"
    assert observations[0].quality_scored is False
    assert observations[0].observed_at == observed
    assert observations[0].supporting_observations[0]["source"] == "Hacker News"
    assert ingest[0].kind == "attention"
    assert producer[0].producer == "fixture"
    assert state["fixture:hacker-news:1"]["observed_at"] == observed.isoformat()


def test_first_observed_time_survives_reingestion(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.attention.get_json",
        lambda url: {
            "schema_version": 1,
            "producer": "fixture",
            "observations": [
                {
                    "id": "one",
                    "source": "Forum",
                    "source_id": "1",
                    "title": "Evaluation",
                    "url": "https://example.test/1",
                    "published_at": "2026-07-20T00:00:00Z",
                    "discovered_at": "2026-07-21T00:00:00Z",
                    "event_kind": "discussed",
                    "categories": [],
                    "metrics": {},
                    "rationale": [],
                }
            ],
            "health": [],
        },
    )
    first = "2026-07-25T12:00:00+00:00"

    observations, _, _, _ = fetch_attention_feeds(
        {"feeds": [{"name": "Fixture", "url": "https://example.test/feed.json"}]},
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        previous_state={"fixture:one": {"observed_at": first}},
    )

    assert observations[0].observed_at.isoformat() == first


def test_feed_metrics_preserve_measured_zero_but_cannot_emit_non_json_numbers(monkeypatch):
    # A producer's overflowing JSON number became Infinity in the public snapshot;
    # booleans also acquired a fabricated numeric measurement of one.
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    invalid = {
        "points": float("inf"),
        "flag": True,
        "zero": 0,
        "valid": 2.5,
        "nan": float("nan"),
        "huge": 10**400,
        "negative": -1,
    }
    raw = local_observation(now)
    raw["metrics"] = invalid
    raw["supporting_observations"] = [
        {
            "source_id": "2",
            "url": "https://news.ycombinator.com/item?id=2",
            "published_at": raw["published_at"],
            "metrics": invalid,
        }
    ]
    payload = {"schema_version": 1, "producer": "fixture", "observations": [raw], "health": []}
    monkeypatch.setattr("benchmark_radar.attention.get_json", lambda url: payload)
    observations, health, _, _ = fetch_attention_feeds(
        {"feeds": [{"url": "https://example.test/feed.json"}]}, observed_at=now
    )
    assert health[0].ok
    assert observations[0].metrics == {"zero": 0.0, "valid": 2.5}
    assert observations[0].supporting_observations[0]["metrics"] == observations[0].metrics
    json.dumps(observations[0].to_dict(), allow_nan=False)


def test_failed_collector_sanitizes_metrics_from_legacy_observations(monkeypatch):
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    monkeypatch.setattr(
        "benchmark_radar.attention.collect_hacker_news",
        lambda *args, **kwargs: ([], {"ok": False, "error": "offline"}),
    )
    previous = {
        **local_observation(now),
        "producer": "benchmark-social-signal",
        "observation_id": "benchmark-social-signal:hacker-news:1",
        "observed_at": now.isoformat(),
        "metrics": {"points": float("inf"), "flag": True, "zero": 0},
    }
    restored, health, _, _ = fetch_attention_feeds(
        LOCAL_CONFIG, observed_at=now, previous_observations=[previous]
    )
    assert not health[0].ok
    assert restored[0].metrics == {"zero": 0.0}
    json.dumps(restored[0].to_dict(), allow_nan=False)
