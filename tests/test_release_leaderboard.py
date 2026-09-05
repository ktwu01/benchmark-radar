from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from benchmark_radar.release_leaderboard import (
    METHOD_VERSION,
    build_latest_releases_leaderboard,
    compute_window_ranking,
    filter_release_cohort,
    is_dedicated_benchmark_repo,
)
from benchmark_radar.snapshots import SnapshotError, validate_snapshot


def make_snapshot(
    date_str: str,
    generated_at_str: str,
    evidence_items: list[dict[str, Any]] | None = None,
    benchmark_attention: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "schema_version": 2,
        "date": date_str,
        "generated_at": generated_at_str,
        "since": f"{date_str}T00:00:00+00:00",
        "evidence_items": evidence_items or [],
        "attention": {"observations": []},
        "ingest_health": [],
        "producer_health": [],
        "discovery_state": {},
    }
    if benchmark_attention is not None:
        snapshot["benchmark_attention"] = benchmark_attention
    return snapshot


def test_snapshot_benchmark_attention_validation():
    base_time = "2026-09-01T12:00:00+00:00"
    valid_attention = {
        "schema_version": 1,
        "observed_at": base_time,
        "observations": [
            {
                "canonical_artifact_id": "artifact:arxiv:2608.12345",
                "source": "github",
                "metric": "stars",
                "value": 150,
                "value_kind": "cumulative",
                "source_url": "https://github.com/example/bench",
                "status": "fresh",
            }
        ],
        "health": [],
    }
    snapshot = make_snapshot("2026-09-01", base_time, benchmark_attention=valid_attention)
    validate_snapshot(snapshot)

    # Missing schema_version
    invalid = make_snapshot("2026-09-01", base_time, benchmark_attention={"observations": []})
    with pytest.raises(SnapshotError, match="benchmark_attention"):
        validate_snapshot(invalid)

    # Invalid URL in observation
    invalid_url = {
        "schema_version": 1,
        "observed_at": base_time,
        "observations": [
            {
                "canonical_artifact_id": "artifact:arxiv:2608.12345",
                "source": "github",
                "metric": "stars",
                "value": 150,
                "value_kind": "cumulative",
                "source_url": "ftp://example/bench",
                "status": "fresh",
            }
        ],
        "health": [],
    }
    with pytest.raises(SnapshotError, match="HTTP"):
        validate_snapshot(make_snapshot("2026-09-01", base_time, benchmark_attention=invalid_url))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "huggingface", "metric/source mismatch"),
        ("metric", "downloads_30d", "metric/source mismatch"),
        ("value", True, "non-negative number or null"),
        ("value_kind", "rolling_30d", "value_kind is invalid"),
        (
            "source_url",
            "https://github.com/example/monorepo/tree/main/bench",
            "exact metric resource",
        ),
    ],
)
def test_snapshot_benchmark_attention_rejects_misattributed_signals(
    field: str, value: Any, message: str
):
    observed_at = "2026-09-01T12:00:00+00:00"
    attention = {
        "schema_version": 1,
        "observed_at": observed_at,
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:example/bench",
                "source": "github",
                "metric": "stars",
                "value": 150,
                "value_kind": "cumulative",
                "source_url": "https://github.com/example/bench",
                "status": "fresh",
            }
        ],
        "health": [],
    }
    invalid = deepcopy(attention)
    invalid["observations"][0][field] = value

    with pytest.raises(SnapshotError, match=message):
        validate_snapshot(make_snapshot("2026-09-01", observed_at, benchmark_attention=invalid))


def test_window_boundaries_utc():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)

    # 30-day window: [2026-08-02 12:00:00, 2026-09-01 12:00:00]
    in_window_exact_start = generated_at - timedelta(days=30)
    in_window_mid = generated_at - timedelta(days=15)
    in_window_exact_end = generated_at
    outside_before = in_window_exact_start - timedelta(seconds=1)
    outside_after = generated_at + timedelta(seconds=1)

    items = [
        {
            "id": "bench-start",
            "url": "https://github.com/org/bench-start",
            "title": "Bench Start",
            "event_kind": "released",
            "discovered_at": in_window_exact_start.isoformat(),
            "source": "GitHub",
            "source_id": "org/bench-start",
        },
        {
            "id": "bench-mid",
            "url": "https://github.com/org/bench-mid",
            "title": "Bench Mid",
            "event_kind": "released",
            "discovered_at": in_window_mid.isoformat(),
            "source": "GitHub",
            "source_id": "org/bench-mid",
        },
        {
            "id": "bench-end",
            "url": "https://github.com/org/bench-end",
            "title": "Bench End",
            "event_kind": "released",
            "discovered_at": in_window_exact_end.isoformat(),
            "source": "GitHub",
            "source_id": "org/bench-end",
        },
        {
            "id": "bench-before",
            "url": "https://github.com/org/bench-before",
            "title": "Bench Before",
            "event_kind": "released",
            "discovered_at": outside_before.isoformat(),
            "source": "GitHub",
            "source_id": "org/bench-before",
        },
        {
            "id": "bench-after",
            "url": "https://github.com/org/bench-after",
            "title": "Bench After",
            "event_kind": "released",
            "discovered_at": outside_after.isoformat(),
            "source": "GitHub",
            "source_id": "org/bench-after",
        },
    ]

    snapshots = [make_snapshot("2026-09-01", generated_at.isoformat(), evidence_items=items)]
    cohort = filter_release_cohort(
        snapshots, window_days=30, as_of=generated_at, include_unconfirmed=True
    )
    cohort_ids = {entry["canonical_artifact_id"] for entry in cohort}

    assert "artifact:github:org/bench-start" in cohort_ids
    assert "artifact:github:org/bench-mid" in cohort_ids
    assert "artifact:github:org/bench-end" in cohort_ids
    assert "artifact:github:org/bench-before" not in cohort_ids
    assert "artifact:github:org/bench-after" not in cohort_ids


def test_released_versus_updated_eligibility():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)

    # An old benchmark released 60 days ago, with routine update 5 days ago
    old_release_time = (generated_at - timedelta(days=60)).isoformat()
    recent_update_time = (generated_at - timedelta(days=5)).isoformat()
    new_release_time = (generated_at - timedelta(days=10)).isoformat()

    items = [
        # Routine update only in window: should be EXCLUDED from release cohort
        {
            "id": "routine-update",
            "url": "https://github.com/org/old-bench",
            "title": "Old Bench Update v2.0",
            "event_kind": "updated",
            "discovered_at": recent_update_time,
            "published_at": recent_update_time,
            "source": "GitHub",
            "source_id": "org/old-bench",
        },
        # Genuine release in window: should be INCLUDED
        {
            "id": "new-release",
            "url": "https://github.com/org/new-bench",
            "title": "New Bench v1.0",
            "event_kind": "released",
            "discovered_at": new_release_time,
            "published_at": new_release_time,
            "source": "GitHub",
            "source_id": "org/new-bench",
        },
        # Discovered only (no verified release event): should be EXCLUDED
        {
            "id": "discovered-only",
            "url": "https://github.com/org/discovered-bench",
            "title": "Discovered Bench",
            "event_kind": "discovered",
            "discovered_at": new_release_time,
            "published_at": new_release_time,
            "source": "GitHub",
            "source_id": "org/discovered-bench",
        },
    ]

    snapshots = [
        make_snapshot(
            "2026-07-03",
            old_release_time,
            evidence_items=[
                {
                    "id": "routine-update-orig",
                    "url": "https://github.com/org/old-bench",
                    "title": "Old Bench v1.0",
                    "event_kind": "released",
                    "discovered_at": old_release_time,
                    "published_at": old_release_time,
                    "source": "GitHub",
                    "source_id": "org/old-bench",
                }
            ],
        ),
        make_snapshot("2026-09-01", generated_at.isoformat(), evidence_items=items),
    ]

    cohort = filter_release_cohort(
        snapshots, window_days=30, as_of=generated_at, include_unconfirmed=True
    )
    cohort_ids = {entry["canonical_artifact_id"] for entry in cohort}

    assert "artifact:github:org/new-bench" in cohort_ids
    assert "artifact:github:org/old-bench" not in cohort_ids
    assert "artifact:github:org/discovered-bench" not in cohort_ids


def test_canonical_identity_deduplication():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    rel_time = (generated_at - timedelta(days=8)).isoformat()

    # Two records for the same benchmark: one arXiv paper and one GitHub repository,
    # linked transitively via artifact_urls.
    items = [
        {
            "id": "paper-record",
            "url": "https://arxiv.org/abs/2608.99999",
            "artifact_urls": ["https://github.com/meta-eval/agent-bench"],
            "title": "AgentBench Paper",
            "event_kind": "released",
            "discovered_at": rel_time,
            "published_at": rel_time,
            "source": "arXiv",
            "source_id": "2608.99999",
        },
        {
            "id": "repo-record",
            "url": "https://github.com/meta-eval/agent-bench",
            "artifact_urls": ["https://arxiv.org/abs/2608.99999"],
            "title": "meta-eval/agent-bench",
            "event_kind": "released",
            "discovered_at": rel_time,
            "published_at": rel_time,
            "source": "GitHub",
            "source_id": "meta-eval/agent-bench",
            "metrics": {"stars": 420},
        },
    ]

    snapshots = [make_snapshot("2026-09-01", generated_at.isoformat(), evidence_items=items)]
    cohort = filter_release_cohort(
        snapshots, window_days=30, as_of=generated_at, include_unconfirmed=True
    )

    # Must collapse to exactly 1 canonical release entity
    assert len(cohort) == 1
    entity = cohort[0]
    assert entity["canonical_artifact_id"] in {
        "artifact:arxiv:2608.99999",
        "artifact:github:meta-eval/agent-bench",
    }


def test_dedicated_vs_hosting_repo_stars():
    # Dedicated repository: counts
    assert is_dedicated_benchmark_repo("https://github.com/my-org/my-benchmark") is True
    assert is_dedicated_benchmark_repo("https://github.com/my-org/my-benchmark.git") is True

    # Hosting repo (benchmark in subdirectory / tree / blob): must NOT inherit parent stars
    assert (
        is_dedicated_benchmark_repo(
            "https://github.com/big-framework/framework/tree/main/benchmarks/my-bench"
        )
        is False
    )
    assert (
        is_dedicated_benchmark_repo(
            "https://github.com/big-framework/framework/blob/main/evals/my-bench"
        )
        is False
    )
    assert is_dedicated_benchmark_repo(None) is False


def test_missing_signal_is_unknown_and_weights_not_redistributed():
    # In Ranking v1, missing components contribute 0 to the sum, and missing
    # weight is NOT redistributed.
    # Formula: log1p(val) / log1p(max)
    # Target benchmark with only githubStars=100 (max=100 -> norm=1.0)
    # Weights: Stars=0.55, Upvotes=0.30, Downloads=0.15
    # If upvotes and downloads are missing, score should be:
    # 0.55 * 1.0 = 0.55 -> 55 points (out of 100), NOT 100 points!
    candidates = [
        {
            "canonical_artifact_id": "artifact:github:org/bench-a",
            "name": "Bench A",
            "purpose": "Evaluation suite A",
            "release_date": "2026-08-20T10:00:00Z",
            "signals": {
                "github_stars": {
                    "value": 100,
                    "status": "fresh",
                    "source_url": "https://github.com/org/bench-a",
                },
                "hf_paper_upvotes": {"value": None, "status": "unknown", "source_url": None},
                "hf_dataset_downloads": {"value": None, "status": "unknown", "source_url": None},
            },
        }
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    entry = ranking["entries"][0]

    assert entry["score"] == 55
    assert entry["coverage"] == 0.55
    assert entry["components"]["github_stars"]["normalized"] == 1.0
    assert entry["components"]["hf_paper_upvotes"]["normalized"] is None
    assert entry["components"]["hf_paper_upvotes"]["status"] == "unknown"
    assert entry["components"]["hf_dataset_downloads"]["normalized"] is None


def test_stale_signal_cannot_cross_ranking_threshold():
    # Benchmark with stale githubStars=1000 and fresh upvotes=10.
    # Ranking threshold requires fresh durable signal and >= 0.45 fresh weight.
    # Since stars is stale, fresh weight is only upvotes (0.30) < 0.45.
    # Therefore, this candidate must have rank=None and status="limited_signals".
    candidates = [
        {
            "canonical_artifact_id": "artifact:github:org/stale-bench",
            "name": "Stale Bench",
            "purpose": "A benchmark with stale stats",
            "release_date": "2026-08-15T10:00:00Z",
            "signals": {
                "github_stars": {
                    "value": 1000,
                    "status": "stale",
                    "last_successful_date": "2026-08-10",
                    "source_url": "https://github.com/org/stale-bench",
                },
                "hf_paper_upvotes": {
                    "value": 10,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/papers/2608.12345",
                },
                "hf_dataset_downloads": {"value": None, "status": "unknown", "source_url": None},
            },
        }
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    entry = ranking["entries"][0]

    assert entry["rank"] is None
    assert entry["status"] == "limited_signals"
    assert entry["components"]["github_stars"]["status"] == "stale"
    assert entry["components"]["github_stars"]["last_successful_date"] == "2026-08-10"


def test_hf_upvotes_only_cannot_receive_formal_rank():
    # Issue 530: "In the 30- and 90-day views, HF votes alone produce a visible
    # score but no formal rank; a dedicated repository or exact dataset signal is required."
    candidates = [
        {
            "canonical_artifact_id": "artifact:arxiv:2608.11111",
            "name": "Paper Only Bench",
            "purpose": "Paper with upvotes only",
            "release_date": "2026-08-20T10:00:00Z",
            "signals": {
                "github_stars": {"value": None, "status": "unknown", "source_url": None},
                "hf_paper_upvotes": {
                    "value": 50,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/papers/2608.11111",
                },
                "hf_dataset_downloads": {"value": None, "status": "unknown", "source_url": None},
            },
        }
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    entry = ranking["entries"][0]

    assert entry["rank"] is None
    assert entry["status"] == "limited_signals"
    assert entry["score"] == 30
    assert entry["coverage"] == 0.30


def test_formal_rank_with_durable_github_and_sufficient_weight():
    # Benchmark with fresh GitHub stars=500 (weight 0.55 >= 0.45, durable).
    # Qualifies for rank #1.
    candidates = [
        {
            "canonical_artifact_id": "artifact:github:org/top-bench",
            "name": "Top Bench",
            "purpose": "State-of-the-art agent benchmark",
            "release_date": "2026-08-22T10:00:00Z",
            "signals": {
                "github_stars": {
                    "value": 500,
                    "status": "fresh",
                    "source_url": "https://github.com/org/top-bench",
                },
                "hf_paper_upvotes": {
                    "value": 20,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/papers/2608.22222",
                },
                "hf_dataset_downloads": {
                    "value": 1000,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/datasets/org/top-bench-data",
                },
            },
        }
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    assert ranking["ranked_count"] == 1
    entry = ranking["entries"][0]
    assert entry["rank"] == 1
    assert entry["status"] == "ranked"
    assert entry["confidence"] == "High"
    assert entry["coverage"] == 1.0
    assert entry["score"] == 100


def test_deterministic_sorting_and_tie_breaking():
    # Two benchmarks with identical scores: tie-breaker should use release_date desc, then name asc
    candidates = [
        {
            "canonical_artifact_id": "artifact:github:org/bench-b",
            "name": "Bench B",
            "purpose": "Purpose B",
            "release_date": "2026-08-15T00:00:00Z",
            "signals": {
                "github_stars": {
                    "value": 100,
                    "status": "fresh",
                    "source_url": "https://github.com/org/bench-b",
                },
                "hf_paper_upvotes": {"value": None, "status": "unknown", "source_url": None},
                "hf_dataset_downloads": {"value": None, "status": "unknown", "source_url": None},
            },
        },
        {
            "canonical_artifact_id": "artifact:github:org/bench-a",
            "name": "Bench A",
            "purpose": "Purpose A",
            "release_date": "2026-08-20T00:00:00Z",  # newer release
            "signals": {
                "github_stars": {
                    "value": 100,
                    "status": "fresh",
                    "source_url": "https://github.com/org/bench-a",
                },
                "hf_paper_upvotes": {"value": None, "status": "unknown", "source_url": None},
                "hf_dataset_downloads": {"value": None, "status": "unknown", "source_url": None},
            },
        },
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    entries = ranking["entries"]
    assert entries[0]["name"] == "Bench A"
    assert entries[0]["rank"] == 1
    assert entries[1]["name"] == "Bench B"
    assert entries[1]["rank"] == 2


def test_build_latest_releases_leaderboard_payload():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    rel_time_recent = (generated_at - timedelta(days=5)).isoformat()
    rel_time_older = (generated_at - timedelta(days=20)).isoformat()

    items = [
        {
            "id": "bench-1",
            "url": "https://github.com/org/fast-bench",
            "title": "Fast Bench",
            "event_kind": "released",
            "discovered_at": rel_time_recent,
            "source": "GitHub",
            "source_id": "org/fast-bench",
            "metrics": {"stars": 200},
        },
        {
            "id": "bench-2",
            "url": "https://github.com/org/slow-bench",
            "title": "Slow Bench",
            "event_kind": "released",
            "discovered_at": rel_time_older,
            "source": "GitHub",
            "source_id": "org/slow-bench",
            "metrics": {"stars": 100},
        },
    ]

    attention = {
        "schema_version": 1,
        "observed_at": generated_at.isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/fast-bench",
                "source": "github",
                "metric": "stars",
                "value": 200,
                "value_kind": "cumulative",
                "source_url": "https://github.com/org/fast-bench",
                "status": "fresh",
            },
            {
                "canonical_artifact_id": "artifact:github:org/slow-bench",
                "source": "github",
                "metric": "stars",
                "value": 100,
                "value_kind": "cumulative",
                "source_url": "https://github.com/org/slow-bench",
                "status": "fresh",
            },
        ],
        "health": [],
    }

    snapshots = [
        make_snapshot(
            "2026-09-01",
            generated_at.isoformat(),
            evidence_items=items,
            benchmark_attention=attention,
        )
    ]
    payload = build_latest_releases_leaderboard(snapshots, as_of=generated_at)

    assert payload["schema_version"] == 1
    assert payload["method_version"] == METHOD_VERSION
    assert payload["default_window"] == "30d"
    assert "7d" in payload["windows"]
    assert "30d" in payload["windows"]
    assert "90d" in payload["windows"]

    # 7d window only has bench-1 (5 days old)
    w7d = payload["windows"]["7d"]
    assert w7d["ranked_count"] == 1
    assert len(w7d["entries"]) == 1
    assert w7d["entries"][0]["name"] == "Fast Bench"

    # 30d window has both bench-1 and bench-2
    w30d = payload["windows"]["30d"]
    assert w30d["ranked_count"] == 2
    assert len(w30d["entries"]) == 2
    assert w30d["entries"][0]["name"] == "Fast Bench"
    assert w30d["entries"][1]["name"] == "Slow Bench"


def test_evidence_item_fallback_without_attention_or_reviewed_does_not_rank():
    # Issue #530 / Review blocker 1:
    # Ordinary keyword/category discovery with connector metrics must NOT establish formal rank.
    # Without dated benchmark_attention or reviewed benchmark status, items remain unranked.
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    rel_time = (generated_at - timedelta(days=10)).isoformat()

    items = [
        {
            "id": "unreviewed-discovery",
            "url": "https://github.com/random/discovered-tool",
            "title": "Random Discovered Tool",
            "event_kind": "released",
            "discovered_at": rel_time,
            "published_at": rel_time,
            "source": "GitHub",
            "source_id": "random/discovered-tool",
            "metrics": {"stars": 999},  # Historical connector metric
        }
    ]

    # No benchmark_attention block
    snapshots = [make_snapshot("2026-09-01", generated_at.isoformat(), evidence_items=items)]
    # By default, unreviewed discoveries do not enter the leaderboard payload at all
    default_payload = build_latest_releases_leaderboard(
        snapshots, as_of=generated_at, reviewed_benchmark_ids=set()
    )
    assert default_payload["windows"]["30d"]["total_cohort_count"] == 0
    assert default_payload["windows"]["30d"]["ranked_count"] == 0

    # If unconfirmed items are explicitly retained for inspection, they remain unranked
    payload = build_latest_releases_leaderboard(
        snapshots,
        as_of=generated_at,
        reviewed_benchmark_ids=set(),
        include_unconfirmed=True,
    )

    w30d = payload["windows"]["30d"]
    assert w30d["ranked_count"] == 0
    assert w30d["total_cohort_count"] == 1
    entry = w30d["entries"][0]
    assert entry["rank"] is None
    assert entry["status"] == "limited_signals"


def test_newer_unavailable_observation_makes_signal_stale_and_unranked():
    # Issue #530 / Review blocker 2:
    # When a newer observation reports value: null with status: unavailable,
    # the latest source status must govern the signal. The last-known value is
    # retained as stale with last_successful_date, and cannot cross the ranking threshold.
    generated_at_1 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
    generated_at_2 = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    rel_time = (generated_at_2 - timedelta(days=20)).isoformat()

    items = [
        {
            "id": "bench-refresh-failed",
            "url": "https://github.com/org/refresh-failed",
            "title": "Refresh Failed Bench",
            "event_kind": "released",
            "discovered_at": rel_time,
            "published_at": rel_time,
            "source": "GitHub",
            "source_id": "org/refresh-failed",
        }
    ]

    # Snapshot 1: fresh observation (stars = 500)
    att_1 = {
        "schema_version": 1,
        "observed_at": generated_at_1.isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/refresh-failed",
                "source": "github",
                "metric": "stars",
                "value": 500,
                "value_kind": "cumulative",
                "source_url": "https://github.com/org/refresh-failed",
                "status": "fresh",
            }
        ],
        "health": [],
    }

    # Snapshot 2: failed refresh (status: unavailable, value: null)
    att_2 = {
        "schema_version": 1,
        "observed_at": generated_at_2.isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/refresh-failed",
                "source": "github",
                "metric": "stars",
                "value": None,
                "value_kind": "cumulative",
                "source_url": "https://github.com/org/refresh-failed",
                "status": "unavailable",
            }
        ],
        "health": [],
    }

    snapshots = [
        make_snapshot(
            "2026-08-15",
            generated_at_1.isoformat(),
            evidence_items=items,
            benchmark_attention=att_1,
        ),
        make_snapshot(
            "2026-09-01",
            generated_at_2.isoformat(),
            evidence_items=items,
            benchmark_attention=att_2,
        ),
    ]

    payload = build_latest_releases_leaderboard(snapshots, as_of=generated_at_2)
    w30d = payload["windows"]["30d"]

    # Must NOT receive formal rank because the signal is now stale
    assert w30d["ranked_count"] == 0
    entry = w30d["entries"][0]
    assert entry["rank"] is None
    assert entry["status"] == "limited_signals"

    # Retained signal is marked stale with date
    stars_comp = entry["components"]["github_stars"]
    assert stars_comp["value"] == 500
    assert stars_comp["status"] == "stale"
    assert "2026-08-15" in stars_comp["last_successful_date"]


def test_exact_45_percent_eligibility_boundary_hf_upvotes_plus_dataset_downloads():
    # Issue #530 / Review blocker 3:
    # 0.30 (HF upvotes) + 0.15 (HF dataset downloads) evaluates to
    # 0.44999999999999996 in binary floating point.
    # The threshold check must be numerically stable so that exactly 45% weight qualifies
    # for rank #1.
    candidates = [
        {
            "canonical_artifact_id": "artifact:hf:org/dual-hf-bench",
            "name": "Dual HF Bench",
            "purpose": "A benchmark with HF paper upvotes and HF dataset downloads",
            "release_date": "2026-08-20T10:00:00Z",
            "has_dated_attention": True,
            "signals": {
                "github_stars": {"value": None, "status": "unknown", "source_url": None},
                "hf_paper_upvotes": {
                    "value": 50,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/papers/2608.55555",
                },
                "hf_dataset_downloads": {
                    "value": 1200,
                    "status": "fresh",
                    "source_url": "https://huggingface.co/datasets/org/dual-hf-bench",
                },
            },
        }
    ]

    ranking = compute_window_ranking(candidates, window_days=30)
    assert ranking["ranked_count"] == 1
    entry = ranking["entries"][0]
    assert entry["rank"] == 1
    assert entry["status"] == "ranked"
    assert entry["coverage"] == 0.45
    assert entry["score"] == 45
    assert entry["components"]["hf_paper_upvotes"]["status"] == "fresh"
    assert entry["components"]["hf_dataset_downloads"]["status"] == "fresh"


def test_attention_observation_joins_through_canonical_alias():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    released_at = (generated_at - timedelta(days=5)).isoformat()
    paper_url = "https://arxiv.org/abs/2608.99999"
    repo_url = "https://github.com/example/identity-bench"
    items = [
        {
            "url": paper_url,
            "artifact_urls": [repo_url],
            "title": "Identity Bench",
            "event_kind": "released",
            "published_at": released_at,
            "source": "arXiv",
            "source_id": "2608.99999",
            "metrics": {},
        },
        {
            "url": repo_url,
            "artifact_urls": [paper_url],
            "title": "Identity Bench",
            "event_kind": "released",
            "published_at": released_at,
            "source": "GitHub",
            "source_id": "example/identity-bench",
            "metrics": {},
        },
    ]
    attention = {
        "schema_version": 1,
        "observed_at": generated_at.isoformat(),
        "observations": [
            {
                # The paper becomes the stronger canonical identity. The dated
                # observation written against the repository identity must
                # still follow the same alias edge.
                "canonical_artifact_id": "artifact:github:example/identity-bench",
                "source": "github",
                "metric": "stars",
                "value": 50,
                "value_kind": "cumulative",
                "source_url": repo_url,
                "status": "fresh",
            }
        ],
        "health": [],
    }

    cohort = filter_release_cohort(
        [
            make_snapshot(
                "2026-09-01",
                generated_at.isoformat(),
                evidence_items=items,
                benchmark_attention=attention,
            )
        ],
        window_days=30,
        as_of=generated_at,
        reviewed_benchmark_ids=set(),
    )

    assert len(cohort) == 1
    assert cohort[0]["canonical_artifact_id"] == "artifact:arxiv:2608.99999"
    assert cohort[0]["has_dated_attention"] is True
    assert cohort[0]["signals"]["github_stars"] == {
        "value": 50,
        "status": "fresh",
        "source_url": repo_url,
    }


def test_later_source_health_failure_marks_retained_value_stale():
    first_at = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    failed_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    released_at = (failed_at - timedelta(days=5)).isoformat()
    repo_url = "https://github.com/example/health-bench"
    item = {
        "url": repo_url,
        "title": "Health Bench",
        "event_kind": "released",
        "published_at": released_at,
        "source": "GitHub",
        "source_id": "example/health-bench",
        "metrics": {},
    }
    fresh_attention = {
        "schema_version": 1,
        "observed_at": first_at.isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:example/health-bench",
                "source": "github",
                "metric": "stars",
                "value": 50,
                "value_kind": "cumulative",
                "source_url": repo_url,
                "status": "fresh",
            }
        ],
        "health": [],
    }
    failed_attention = {
        "schema_version": 1,
        "observed_at": failed_at.isoformat(),
        "observations": [],
        "health": [{"source": "github", "ok": False, "item_count": 0}],
    }
    snapshots = [
        make_snapshot(
            "2026-08-30",
            first_at.isoformat(),
            evidence_items=[item],
            benchmark_attention=fresh_attention,
        ),
        make_snapshot(
            "2026-09-01",
            failed_at.isoformat(),
            evidence_items=[item],
            benchmark_attention=failed_attention,
        ),
    ]

    payload = build_latest_releases_leaderboard(
        snapshots,
        as_of=failed_at,
        reviewed_benchmark_ids=set(),
    )
    entry = payload["windows"]["30d"]["entries"][0]

    assert entry["rank"] is None
    assert entry["score"] is None
    assert entry["components"]["github_stars"]["status"] == "stale"
    assert entry["components"]["github_stars"]["value"] == 50
    assert entry["components"]["github_stars"]["last_successful_date"] == "2026-08-30"


def test_reviewed_fallback_uses_latest_value_but_never_claims_freshness():
    generated_at = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    released_at = (generated_at - timedelta(days=12)).isoformat()
    repo_url = "https://github.com/example/reviewed-bench"

    def item(stars: int) -> dict[str, Any]:
        return {
            "url": repo_url,
            "title": "Reviewed Bench",
            "event_kind": "released",
            "published_at": released_at,
            "source": "GitHub",
            "source_id": "example/reviewed-bench",
            "metrics": {"stars": stars},
        }

    snapshots = [
        make_snapshot("2026-08-20", "2026-08-20T12:00:00+00:00", [item(10)]),
        make_snapshot("2026-09-01", generated_at.isoformat(), [item(100)]),
    ]
    payload = build_latest_releases_leaderboard(
        snapshots,
        as_of=generated_at,
        reviewed_benchmark_ids={"reviewed bench"},
    )
    entry = payload["windows"]["30d"]["entries"][0]

    assert entry["rank"] is None
    assert entry["score"] is None
    assert entry["components"]["github_stars"]["value"] == 100
    assert entry["components"]["github_stars"]["status"] == "unknown"
    assert entry["components"]["github_stars"]["last_successful_date"] == "2026-09-01"


def test_ranking_uses_unrounded_score_before_release_date_tiebreaker():
    candidates = []
    for name, stars, release_date in (
        ("Higher raw score", 100, "2026-08-19T00:00:00Z"),
        ("Lower raw score", 99, "2026-08-20T00:00:00Z"),
    ):
        repo_name = name.replace(" ", "-").lower()
        candidates.append(
            {
                "canonical_artifact_id": name,
                "name": name,
                "purpose": "",
                "release_date": release_date,
                "has_dated_attention": True,
                "signals": {
                    "github_stars": {
                        "value": stars,
                        "status": "fresh",
                        "source_url": f"https://github.com/example/{repo_name}",
                    },
                    "hf_paper_upvotes": {
                        "value": None,
                        "status": "unknown",
                        "source_url": None,
                    },
                    "hf_dataset_downloads": {
                        "value": None,
                        "status": "unknown",
                        "source_url": None,
                    },
                },
            }
        )

    entries = compute_window_ranking(candidates, window_days=30)["entries"]

    assert entries[0]["name"] == "Higher raw score"
    assert entries[0]["rank"] == 1
    assert entries[1]["name"] == "Lower raw score"
    assert entries[1]["rank"] == 2
    assert entries[0]["score"] == entries[1]["score"] == 55


def test_stale_values_are_displayed_but_do_not_change_score_order():
    release_date = "2026-08-20T00:00:00Z"
    candidates = []
    for name, stale_upvotes in (("No stale boost", None), ("Stale context", 1_000)):
        candidates.append(
            {
                "canonical_artifact_id": name,
                "name": name,
                "purpose": "",
                "release_date": release_date,
                "has_dated_attention": True,
                "signals": {
                    "github_stars": {
                        "value": 100,
                        "status": "fresh",
                        "source_url": "https://github.com/example/same-score",
                    },
                    "hf_paper_upvotes": {
                        "value": stale_upvotes,
                        "status": "stale" if stale_upvotes is not None else "unknown",
                        "source_url": (
                            "https://huggingface.co/papers/2608.99999"
                            if stale_upvotes is not None
                            else None
                        ),
                        "last_successful_date": (
                            "2026-08-01" if stale_upvotes is not None else None
                        ),
                    },
                    "hf_dataset_downloads": {
                        "value": None,
                        "status": "unknown",
                        "source_url": None,
                    },
                },
            }
        )

    entries = compute_window_ranking(candidates, window_days=30)["entries"]

    assert [entry["score"] for entry in entries] == [55, 55]
    assert entries[0]["name"] == "No stale boost"
    stale = next(entry for entry in entries if entry["name"] == "Stale context")
    assert stale["components"]["hf_paper_upvotes"]["value"] == 1_000
    assert stale["components"]["hf_paper_upvotes"]["status"] == "stale"
