"""The collector behind the Latest Releases leaderboard's signals (issue #530).

Before it existed nothing wrote `benchmark_attention`, so every window of the
leaderboard collapsed to hand-reviewed registry entries with `unknown`
signals (issue #589). Each test names the failure it protects against.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from benchmark_radar.benchmark_attention import (
    collect_benchmark_attention,
    merge_benchmark_attention,
    select_targets,
)
from benchmark_radar.briefing import daily_report_run
from benchmark_radar.http import RequestError
from benchmark_radar.models import RadarItem, SourceHealth
from benchmark_radar.pipeline import run_pipeline
from benchmark_radar.release_leaderboard import build_latest_releases_leaderboard
from benchmark_radar.snapshots import (
    SCHEMA_VERSION,
    merge_snapshots,
    snapshot_for_run,
    validate_snapshot,
)

NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
REPO = "https://github.com/org/bench"
PAPER = "https://huggingface.co/papers/2609.01234"
DATASET = "https://huggingface.co/datasets/org/bench-data"

CONFIG = {
    "enabled": True,
    "window_days": 90,
    "github": {"max_requests": 10, "request_delay_seconds": 0.0},
    "huggingface": {"max_requests": 10, "request_delay_seconds": 0.0},
    "attempts": 1,
    "timeout_seconds": 5,
}


def _item(url, *, days_ago, event_kind="released", artifact_urls=(), source="GitHub"):
    published = NOW - timedelta(days=days_ago)
    return RadarItem(
        source=source,
        source_id=url,
        title=f"Bench {url}",
        url=url,
        published_at=published,
        updated_at=published,
        discovered_at=published,
        event_kind=event_kind,
        artifact_urls=list(artifact_urls),
    ).to_dict()


def _snapshot(generated_at, evidence_items=(), benchmark_attention=None):
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "date": generated_at.date().isoformat(),
        "generated_at": generated_at.isoformat(),
        "since": (generated_at - timedelta(hours=48)).isoformat(),
        "evidence_items": list(evidence_items),
        "attention": {"observations": []},
        "ingest_health": [],
        "producer_health": [],
        "discovery_state": {},
        "selection": {},
    }
    if benchmark_attention is not None:
        snapshot["benchmark_attention"] = benchmark_attention
    return snapshot


def _observation(canonical_id, value, *, url=REPO, status="fresh"):
    return {
        "canonical_artifact_id": canonical_id,
        "source": "github",
        "metric": "stars",
        "value": value,
        "value_kind": "cumulative",
        "source_url": url,
        "status": status,
    }


class FakeApi:
    """Answer each resource URL with a payload or raise the configured error."""

    def __init__(self, responses):
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        response = self.responses.get(url)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise RequestError(f"HTTP 404 from {url}")
        return response


GITHUB_API = "https://api.github.com/repos/org/bench"
PAPER_API = "https://huggingface.co/api/papers/2609.01234"
DATASET_API = "https://huggingface.co/api/datasets/org/bench-data"


def test_a_clone_url_reads_the_repository_rather_than_a_404():
    # Authors paste clone URLs into a `code` field, and the exactness rule
    # accepts one because it names the same repository. api.github.com has no
    # repository whose name ends in `.git`, so the unstripped path 404s and a
    # live repository would be recorded as `unavailable` -- the misreading this
    # module exists to prevent, made permanent because only fresh and stale
    # readings are ever carried forward. The reported source_url stays the URL
    # as deposited.
    api = FakeApi({GITHUB_API: {"stargazers_count": 150}})
    block = collect_benchmark_attention(
        CONFIG,
        [
            _item(
                "https://arxiv.org/abs/2609.01234",
                days_ago=3,
                artifact_urls=[f"{REPO}.git"],
                source="arXiv",
            )
        ],
        observed_at=NOW,
        get_json=api,
    )[0]

    assert api.calls == [GITHUB_API]
    observation = block["observations"][0]
    assert (observation["value"], observation["status"]) == (150, "fresh")
    assert observation["source_url"] == f"{REPO}.git"


def test_a_capitalised_github_host_does_not_abort_the_run():
    # The exactness predicate matched the host case-insensitively and then
    # split the URL case-sensitively, so a capitalised link raised IndexError.
    # The collector calls that predicate inside run_pipeline, where one such
    # link in historical evidence would abort the whole daily run rather than
    # skip one resource.
    api = FakeApi({"https://api.github.com/repos/Org/Bench": {"stargazers_count": 7}})
    block = collect_benchmark_attention(
        CONFIG,
        [_item("https://GitHub.com/Org/Bench", days_ago=3)],
        observed_at=NOW,
        get_json=api,
    )[0]

    assert [observation["value"] for observation in block["observations"]] == [7]


def test_select_targets_groups_by_identity_and_keeps_only_exact_resources():
    # The ranking groups occurrences by alias-mapped exact key and dates the
    # release by its earliest `released` observation. A paper item carrying
    # the repository URL and the repository's own item must become one target
    # whose release date is the older of the two, or a re-announcement would
    # move a benchmark back into a window it has left.
    linked = "https://github.com/org/linked"
    items = [
        _item("https://arxiv.org/abs/2609.01234", days_ago=3, artifact_urls=[REPO], source="arXiv"),
        _item(REPO, days_ago=5),
        _item(DATASET, days_ago=1, source="Hugging Face"),
        # A subdirectory of a hosting repository is not the benchmark's own
        # repository; crediting the host's stars would be misattribution.
        _item("https://github.com/org/monorepo/tree/main/bench", days_ago=2),
        # Routine updates are not releases.
        _item("https://github.com/org/updated", days_ago=1, event_kind="updated"),
        # Outside the widest window the ranking shows.
        _item("https://github.com/org/ancient", days_ago=120),
        # A paper released without a repository, whose repository's own
        # `updated` record links back to it: the update supplies the resource
        # but must not supply the release date.
        _item("https://arxiv.org/abs/2609.05555", days_ago=4, source="arXiv"),
        _item(
            linked,
            days_ago=1,
            event_kind="updated",
            artifact_urls=["https://arxiv.org/abs/2609.05555"],
        ),
    ]

    targets = select_targets(items, as_of=NOW, window_days=90)

    assert [target.resources for target in targets] == [
        {"hf_dataset_downloads": DATASET},
        {"github_stars": linked},
        {"github_stars": REPO},
    ]
    assert targets[1].released_at == NOW - timedelta(days=4)
    assert targets[2].released_at == NOW - timedelta(days=5)


def test_collector_writes_a_block_the_snapshot_validator_accepts():
    api = FakeApi(
        {
            GITHUB_API: {"stargazers_count": 150, "forks_count": 3},
            PAPER_API: {"upvotes": 20},
            DATASET_API: {"downloads": 1000, "downloadsAllTime": 99999},
        }
    )
    items = [
        _item(
            "https://arxiv.org/abs/2609.01234",
            days_ago=3,
            artifact_urls=[REPO, PAPER],
            source="arXiv",
        ),
        _item(DATASET, days_ago=1, source="Hugging Face"),
    ]

    block, health = collect_benchmark_attention(CONFIG, items, observed_at=NOW, get_json=api)

    by_metric = {observation["metric"]: observation for observation in block["observations"]}
    assert by_metric["stars"]["value"] == 150 and by_metric["stars"]["value_kind"] == "cumulative"
    # Counters stay whole numbers in the snapshot; 150 must not become 150.0.
    assert all(isinstance(o["value"], int) for o in block["observations"])
    assert by_metric["upvotes"]["value"] == 20 and by_metric["upvotes"]["source"] == "huggingface"
    # The Hub's `downloads` is the rolling 30-day figure the ranking weights,
    # not the all-time counter.
    assert by_metric["downloads_30d"]["value"] == 1000
    assert by_metric["downloads_30d"]["value_kind"] == "rolling_30d"
    assert {observation["status"] for observation in block["observations"]} == {"fresh"}
    assert all(row["ok"] and row["item_count"] == 1 for row in block["health"])
    assert [row.kind for row in health] == ["attention"] * 3
    validate_snapshot(_snapshot(NOW, benchmark_attention=block))


def test_missing_resource_is_unavailable_not_zero():
    # A deleted repository must not rank below a live one with a single star;
    # the ranking treats null as "no signal", zero as a reading.
    api = FakeApi({GITHUB_API: RequestError(f"HTTP 404 from {GITHUB_API}")})

    block, health = collect_benchmark_attention(
        CONFIG, [_item(REPO, days_ago=2)], observed_at=NOW, get_json=api
    )

    (observation,) = block["observations"]
    assert observation["status"] == "unavailable" and observation["value"] is None
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is True and stars_health["item_count"] == 1
    validate_snapshot(_snapshot(NOW, benchmark_attention=block))


def test_transient_failure_carries_the_last_reading_forward_as_stale():
    # A rate limit on one repository is not a fact about that benchmark. The
    # ranking reports whatever the newest observation says, so writing
    # nothing would leave yesterday's reading reported as fresh: the last
    # reading is written again as stale, dated by the day it was read. `ok`
    # stays true, because a failed health event at the same instant as fresh
    # observations would demote all of them to stale.
    other = "https://github.com/org/other"
    api = FakeApi(
        {
            GITHUB_API: RequestError(f"HTTP 429 from {GITHUB_API} after 3 attempts"),
            "https://api.github.com/repos/org/other": {"stargazers_count": 7},
        }
    )
    items = [_item(REPO, days_ago=1), _item(other, days_ago=2)]
    yesterday = NOW - timedelta(days=1)
    previous = {
        "schema_version": 1,
        "observed_at": yesterday.isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/bench",
                "source": "github",
                "metric": "stars",
                "value": 140,
                "value_kind": "cumulative",
                "source_url": REPO,
                "status": "fresh",
                "observed_at": yesterday.isoformat(),
            }
        ],
        "health": [],
    }

    block, health = collect_benchmark_attention(
        CONFIG, items, observed_at=NOW, previous_block=previous, get_json=api
    )

    by_url = {observation["source_url"]: observation for observation in block["observations"]}
    assert by_url[other]["status"] == "fresh" and by_url[other]["value"] == 7
    assert by_url[REPO]["status"] == "stale" and by_url[REPO]["value"] == 140
    assert by_url[REPO]["last_successful_date"] == yesterday.date().isoformat()
    assert by_url[REPO]["observed_at"] == NOW.isoformat()
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is True and stars_health["item_count"] == 1
    assert stars_health["error"].startswith("1 of 2 requests failed; last: RequestError: HTTP 429")
    validate_snapshot(_snapshot(NOW, benchmark_attention=block))

    # Two days later the reading is still dated by the day it was read, so a
    # chain of failures cannot make an old counter look recent.
    later = NOW + timedelta(days=1)
    chained, _ = collect_benchmark_attention(
        CONFIG, items, observed_at=later, previous_block=block, get_json=api
    )
    carried = next(o for o in chained["observations"] if o["source_url"] == REPO)
    assert carried["status"] == "stale"
    assert carried["last_successful_date"] == yesterday.date().isoformat()

    # With nothing to carry forward, a failure writes nothing: a null reading
    # would admit the artifact to the cohort with no signal to rank on.
    bare, _ = collect_benchmark_attention(CONFIG, items, observed_at=NOW, get_json=api)
    assert [observation["source_url"] for observation in bare["observations"]] == [other]


def test_the_ranking_reports_the_carried_reading_as_stale():
    # End to end through `_resolve_attention_metric`: the day after a failure
    # the leaderboard shows the old value marked stale, not fresh.
    evidence = [_item(REPO, days_ago=5)]
    first, _ = collect_benchmark_attention(
        CONFIG,
        evidence,
        observed_at=NOW - timedelta(days=1),
        get_json=FakeApi({GITHUB_API: {"stargazers_count": 150}}),
    )
    second, _ = collect_benchmark_attention(
        CONFIG,
        evidence,
        observed_at=NOW,
        previous_block=first,
        get_json=FakeApi({GITHUB_API: RequestError(f"HTTP 503 from {GITHUB_API}")}),
    )
    snapshots = [
        _snapshot(NOW - timedelta(days=1), evidence_items=evidence, benchmark_attention=first),
        _snapshot(NOW, evidence_items=evidence, benchmark_attention=second),
    ]

    payload = build_latest_releases_leaderboard(snapshots, as_of=NOW, reviewed_benchmark_ids=set())

    stars = payload["windows"]["30d"]["entries"][0]["components"]["github_stars"]
    assert (stars["value"], stars["status"]) == (150, "stale")
    assert stars["last_successful_date"] == (NOW - timedelta(days=1)).date().isoformat()


def test_a_source_is_paused_after_consecutive_failures():
    # An outage answers every request the same way; waiting out the timeout
    # for each of a thousand resources would outlive the daily workflow. The
    # source is not asked again this run, its unread resources keep their
    # stale readings, and the other source is unaffected.
    repos = [f"https://github.com/org/r{index}" for index in range(8)]
    api = FakeApi(
        {
            **{
                f"https://api.github.com/repos/org/r{index}": RequestError("HTTP 502 from x")
                for index in range(8)
            },
            DATASET_API: {"downloads": 3},
        }
    )
    items = [
        *(_item(url, days_ago=index + 1) for index, url in enumerate(repos)),
        _item(DATASET, days_ago=20, source="Hugging Face"),
    ]
    previous = {
        "schema_version": 1,
        "observed_at": (NOW - timedelta(days=1)).isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/r7",
                "source": "github",
                "metric": "stars",
                "value": 9,
                "value_kind": "cumulative",
                "source_url": repos[7],
                "status": "fresh",
            }
        ],
        "health": [],
    }
    config = {**CONFIG, "max_consecutive_failures": 3}

    block, _ = collect_benchmark_attention(
        config, items, observed_at=NOW, previous_block=previous, get_json=api
    )

    assert len([call for call in api.calls if "api.github.com" in call]) == 3
    assert DATASET_API in api.calls
    by_url = {observation["source_url"]: observation for observation in block["observations"]}
    assert set(by_url) == {repos[7], DATASET}
    assert by_url[repos[7]]["status"] == "stale"
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is False
    assert "github paused after 3 consecutive failures" in stars_health["error"]
    assert "5 resources not read, 1 carried forward as stale" in stars_health["error"]
    # A success resets the streak: three failures spread across successes do
    # not pause the source.
    spread = FakeApi(
        {
            f"https://api.github.com/repos/org/r{index}": (
                RequestError("HTTP 502 from x") if index % 2 else {"stargazers_count": 1}
            )
            for index in range(8)
        }
    )
    collect_benchmark_attention(config, items[:-1], observed_at=NOW, get_json=spread)
    assert len(spread.calls) == 8


def test_every_request_failing_marks_the_signal_unhealthy():
    api = FakeApi({GITHUB_API: RequestError(f"HTTP 403 from {GITHUB_API}")})

    block, health = collect_benchmark_attention(
        CONFIG, [_item(REPO, days_ago=1)], observed_at=NOW, get_json=api
    )

    assert block["observations"] == []
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is False and stars_health["item_count"] == 0
    assert next(row for row in health if row.source == "GitHub stars").ok is False
    validate_snapshot(_snapshot(NOW, benchmark_attention=block))


def test_malformed_payload_is_a_failure_not_a_reading():
    # A payload without the counter is a parsing gap, not a benchmark with
    # zero stars; and a response that is not JSON at all, or any other
    # exception from one resource, must not abort the readings after it.
    other = "https://github.com/org/other"
    api = FakeApi(
        {
            GITHUB_API: {"full_name": "org/bench"},
            "https://api.github.com/repos/org/other": json.JSONDecodeError("bad", "<html>", 0),
            "https://api.github.com/repos/org/third": {"stargazers_count": 4},
        }
    )
    items = [
        _item(REPO, days_ago=1),
        _item(other, days_ago=2),
        _item("https://github.com/org/third", days_ago=3),
    ]

    block, _ = collect_benchmark_attention(CONFIG, items, observed_at=NOW, get_json=api)

    assert [observation["value"] for observation in block["observations"]] == [4]
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is True
    assert stars_health["error"].startswith("2 of 3 requests failed; last: JSONDecodeError")


def test_budget_is_spent_newest_first_and_the_unread_tail_is_carried_forward():
    # A budget below the cohort must refresh the releases the leaderboard
    # shows by default before the 90-day tail; a paper and the repository it
    # names are one artifact and cost one request; and the release the budget
    # did not reach keeps its last reading as stale instead of vanishing.
    newest = "https://github.com/org/newest"
    oldest = "https://github.com/org/oldest"
    api = FakeApi(
        {
            "https://api.github.com/repos/org/newest": {"stargazers_count": 1},
            GITHUB_API: {"stargazers_count": 2},
            "https://api.github.com/repos/org/oldest": {"stargazers_count": 3},
        }
    )
    items = [
        _item(oldest, days_ago=30),
        _item(newest, days_ago=1),
        _item(REPO, days_ago=10),
        _item(
            "https://arxiv.org/abs/2609.09999", days_ago=10, artifact_urls=[REPO], source="arXiv"
        ),
    ]
    config = {**CONFIG, "github": {"max_requests": 2, "request_delay_seconds": 0.0}}
    previous = {
        "schema_version": 1,
        "observed_at": (NOW - timedelta(days=1)).isoformat(),
        "observations": [
            {
                "canonical_artifact_id": "artifact:github:org/oldest",
                "source": "github",
                "metric": "stars",
                "value": 2,
                "value_kind": "cumulative",
                "source_url": oldest,
                "status": "fresh",
            }
        ],
        "health": [],
    }

    block, _ = collect_benchmark_attention(
        config, items, observed_at=NOW, previous_block=previous, get_json=api
    )

    assert api.calls == [
        "https://api.github.com/repos/org/newest",
        GITHUB_API,
    ]
    by_url = {observation["source_url"]: observation for observation in block["observations"]}
    assert {url: o["status"] for url, o in by_url.items()} == {
        newest: "fresh",
        REPO: "fresh",
        oldest: "stale",
    }
    assert by_url[oldest]["value"] == 2
    stars_health = next(row for row in block["health"] if row["metric"] == "stars")
    assert stars_health["ok"] is True
    assert stars_health["error"] == "1 resources not read, 1 carried forward as stale"
    validate_snapshot(_snapshot(NOW, benchmark_attention=block))


def test_disabled_collector_writes_nothing():
    assert collect_benchmark_attention({"enabled": False}, [], observed_at=NOW) == (None, [])
    assert collect_benchmark_attention({}, [], observed_at=NOW) == (None, [])


def test_merge_unions_readings_and_the_newer_pass_wins():
    # Issue #104 rule applied to signals: a second pass that ran out of budget
    # must not erase the counters the first pass observed.
    first = {
        "schema_version": 1,
        "observed_at": "2026-09-10T03:00:00+00:00",
        "observations": [
            {"canonical_artifact_id": "a", "metric": "stars", "source_url": REPO, "value": 10},
            {
                "canonical_artifact_id": "b",
                "metric": "stars",
                "source_url": "https://github.com/o/b",
                "value": 5,
            },
        ],
        "health": [
            {"source": "github", "metric": "stars", "ok": True, "item_count": 2, "error": None}
        ],
    }
    second = {
        "schema_version": 1,
        "observed_at": "2026-09-10T15:00:00+00:00",
        "observations": [
            {"canonical_artifact_id": "a", "metric": "stars", "source_url": REPO, "value": 12},
        ],
        "health": [
            {"source": "github", "metric": "stars", "ok": True, "item_count": 1, "error": None}
        ],
    }

    merged = merge_benchmark_attention(first, second)

    assert merged["observed_at"] == "2026-09-10T15:00:00+00:00"
    assert {(o["canonical_artifact_id"], o["value"]) for o in merged["observations"]} == {
        ("a", 12),
        ("b", 5),
    }
    assert merged["health"] == second["health"]
    assert merge_benchmark_attention(None, None) is None
    assert merge_benchmark_attention(first, None) is first

    # A reading the later pass only carried forward as stale must not replace
    # the reading the earlier pass made that day.
    carried = {
        **second,
        "observations": [
            {
                "canonical_artifact_id": "a",
                "metric": "stars",
                "source_url": REPO,
                "value": 10,
                "status": "stale",
            }
        ],
    }
    kept = {
        o["canonical_artifact_id"]: o
        for o in merge_benchmark_attention(first, carried)["observations"]
    }
    assert kept["a"]["value"] == 10 and "status" not in kept["a"]
    assert merge_benchmark_attention(carried, second)["observations"][0]["value"] == 12

    existing = _snapshot(NOW - timedelta(hours=12), benchmark_attention=first)
    incoming = _snapshot(NOW, benchmark_attention=second)
    assert len(merge_snapshots(existing, incoming)["benchmark_attention"]["observations"]) == 2
    without = merge_snapshots(_snapshot(NOW - timedelta(hours=12)), _snapshot(NOW))
    assert "benchmark_attention" not in without


def test_pipeline_observes_releases_across_the_history_and_writes_the_block(monkeypatch):
    # The counters of a three-week-old release keep moving, so the collector
    # must see the committed history, not only today's items; and the block
    # must reach the snapshot with its health rows in the attention list.
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"])
    today = RadarItem(
        source="GitHub",
        source_id="org/today",
        title="Today Bench",
        url="https://github.com/org/today",
        published_at=NOW,
        updated_at=NOW,
        event_kind="released",
        summary="A benchmark released today.",
    )
    monkeypatch.setitem(pipeline.SOURCE_FETCHERS, "github", lambda config, since, limit: [today])
    monkeypatch.setattr(
        pipeline,
        "fetch_attention_feeds",
        lambda *args, **kwargs: ([], [], [], {}),
    )
    seen: dict[str, object] = {}

    def fake_collect(config, items, *, observed_at, previous_block=None):
        seen["items"] = items
        seen["previous_block"] = previous_block
        block = {
            "schema_version": 1,
            "observed_at": observed_at.isoformat(),
            "observations": [_observation("artifact:github:org/today", 1)],
            "health": [],
        }
        return block, [SourceHealth(source="GitHub stars", ok=True, kind="attention")]

    monkeypatch.setattr(pipeline, "collect_benchmark_attention", fake_collect)
    yesterday_block = {
        "schema_version": 1,
        "observed_at": (NOW - timedelta(days=1)).isoformat(),
        "observations": [_observation("artifact:github:org/bench", 140)],
        "health": [],
    }
    history = [
        _snapshot(NOW - timedelta(days=20), evidence_items=[_item(REPO, days_ago=20)]),
        _snapshot(NOW - timedelta(days=1), benchmark_attention=yesterday_block),
    ]
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True}},
        "benchmark_attention": {"enabled": True},
    }

    run = run_pipeline(config, NOW, previous_snapshot=history[-1], snapshots=history)

    assert {item["url"] for item in seen["items"]} == {REPO, "https://github.com/org/today"}
    # Yesterday's readings are what today's failures carry forward.
    assert seen["previous_block"] is yesterday_block
    assert run.benchmark_attention["schema_version"] == 1
    assert [health.source for health in run.attention_ingest_health] == ["GitHub stars"]
    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)
    assert snapshot["benchmark_attention"] is run.benchmark_attention
    # A day merged from two passes reports the merged block, not this pass's.
    earlier_pass = _snapshot(
        NOW - timedelta(hours=6),
        benchmark_attention={
            **yesterday_block,
            "observations": [_observation("artifact:github:org/other", 5)],
        },
    )
    merged = merge_snapshots(earlier_pass, snapshot)
    reported = daily_report_run(merged, run).benchmark_attention
    assert reported is not run.benchmark_attention
    assert {o["canonical_artifact_id"] for o in reported["observations"]} == {
        "artifact:github:org/other",
        "artifact:github:org/today",
    }


def test_disabled_collector_leaves_the_snapshot_without_a_block(monkeypatch):
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"])
    monkeypatch.setitem(pipeline.SOURCE_FETCHERS, "github", lambda config, since, limit: [])
    monkeypatch.setattr(pipeline, "fetch_attention_feeds", lambda *a, **k: ([], [], [], {}))
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True}},
    }

    run = run_pipeline(config, NOW)

    assert run.benchmark_attention is None
    assert "benchmark_attention" not in snapshot_for_run(run)


def test_leaderboard_ranks_a_release_from_the_collected_block():
    # End to end: an unreviewed release with a dedicated repository enters the
    # 30-day cohort only because the collector observed it, and ranks
    # formally because GitHub stars are a durable signal above the 45% floor.
    api = FakeApi({GITHUB_API: {"stargazers_count": 150}})
    evidence = [_item(REPO, days_ago=5)]
    block, _ = collect_benchmark_attention(CONFIG, evidence, observed_at=NOW, get_json=api)
    snapshots = [_snapshot(NOW, evidence_items=evidence, benchmark_attention=block)]

    payload = build_latest_releases_leaderboard(snapshots, as_of=NOW, reviewed_benchmark_ids=set())

    window = payload["windows"]["30d"]
    assert window["ranked_count"] == 1
    entry = window["entries"][0]
    assert entry["status"] == "ranked"
    stars = entry["components"]["github_stars"]
    assert (stars["value"], stars["status"], stars["source_url"]) == (150, "fresh", REPO)
    # Without the block the same release is invisible: this is the failure
    # issue #589 reported.
    bare = build_latest_releases_leaderboard(
        [_snapshot(NOW, evidence_items=evidence)], as_of=NOW, reviewed_benchmark_ids=set()
    )
    assert bare["windows"]["30d"]["entries"] == []
