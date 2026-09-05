import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from benchmark_radar import rubric
from benchmark_radar.feed import SITE_URL
from benchmark_radar.model_cards import ModelCardRegistryError
from benchmark_radar.models import (
    AttentionObservation,
    ProducerHealth,
    RadarItem,
    RadarRun,
    SourceHealth,
)
from benchmark_radar.snapshots import (
    SnapshotError,
    load_snapshots,
    migrate_snapshot_history,
    rebuild_dashboard,
    records_badge,
    rescore_snapshot_history,
    snapshot_for_run,
    validate_snapshot,
    write_snapshot,
)
from benchmark_radar.sources import GITHUB_RELEASE_PARSER_VERSION


def radar_run(day: int = 27, *, title: str = "A New Evaluation Benchmark") -> RadarRun:
    generated = datetime(2026, 7, day, 12, 15, tzinfo=UTC)
    return RadarRun(
        generated_at=generated,
        since=generated - timedelta(hours=48),
        items=[
            RadarItem(
                source="arXiv",
                source_id=f"2607.{day:04d}",
                title=title,
                url=f"https://arxiv.org/abs/2607.{day:04d}",
                published_at=generated - timedelta(hours=3),
                summary="A fixture-backed benchmark release.",
                event_kind="released",
                authors=["Radar Author"],
                categories=["benchmark", "evaluation"],
                metrics={"citations": 2},
                evidence_score=2.5,
                relevance_score=2.9,
                recency_score=3.8,
                adoption_score=0.3,
                total_score=2.7,
                rationale=["Matched: benchmark", "Primary record: arXiv"],
            )
        ],
        health=[
            SourceHealth(source="arxiv", ok=True, item_count=1),
            SourceHealth(source="brave", ok=False, error="API key unavailable"),
        ],
        attention=[
            AttentionObservation(
                observation_id=f"producer:hacker-news:{day}",
                producer="fixture-producer",
                source="Hacker News",
                source_id=str(day),
                title="Public benchmark discussion",
                url=f"https://news.ycombinator.com/item?id={day}",
                published_at=generated - timedelta(hours=2),
                discovered_at=generated - timedelta(hours=1),
                observed_at=generated,
                categories=["benchmark"],
                metrics={"points": 4},
                rationale=["Attention only"],
                supporting_observations=[
                    {
                        "source": "Hacker News",
                        "source_id": f"{day}-supporting",
                        "url": f"https://news.ycombinator.com/item?id={day}-supporting",
                        "published_at": generated.isoformat(),
                        "metrics": {"points": 1},
                    }
                ],
            )
        ],
        attention_ingest_health=[
            SourceHealth(
                source="Fixture feed",
                kind="attention",
                ok=True,
                item_count=1,
            )
        ],
        producer_health=[
            ProducerHealth(
                producer="fixture-producer",
                source="Hacker News",
                ok=True,
                item_count=1,
            )
        ],
    )


def test_snapshot_has_version_and_public_evidence_fields():
    snapshot = snapshot_for_run(radar_run())

    validate_snapshot(snapshot)

    assert snapshot["schema_version"] == 2
    assert snapshot["date"] == "2026-07-27"
    assert snapshot["evidence_items"][0]["event_kind"] == "released"
    assert "raw" not in snapshot["evidence_items"][0]
    assert snapshot["evidence_items"][0]["parser_version"] == "radar-item/1"
    assert snapshot["evidence_items"][0]["raw_payload_hash"].startswith("sha256:")
    assert snapshot["attention"]["observations"][0]["quality_scored"] is False
    assert (
        snapshot["attention"]["observations"][0]["supporting_observations"][0]["source"]
        == "Hacker News"
    )


def test_same_utc_day_unions_both_runs(tmp_path):
    # Issue #104: the radar runs twice a day into the same dated file. The
    # second pass used to replace the first, so on 2026-08-02 the published day
    # lost 21 records the morning pass had already committed. Each pass is
    # truncated at `max_items_per_source`, so neither is the whole day.
    first = radar_run(title="First run")
    second = radar_run(title="Second run")
    second.items[0].source_id = "2607.9999"
    second.items[0].url = "https://arxiv.org/abs/2607.9999"
    second.attention[0].observation_id = "producer:hacker-news:9999"
    second.attention[0].source_id = "9999"
    second.attention[0].url = "https://news.ycombinator.com/item?id=9999"
    second.generated_at = first.generated_at + timedelta(hours=6)
    second.since = second.generated_at - timedelta(hours=12)
    first.selection = {"fetched": 10, "qualified": 1, "published": 1}
    second.selection = {"fetched": 12, "qualified": 1, "published": 1}

    first_path = write_snapshot(first, tmp_path)
    second_path = write_snapshot(second, tmp_path)

    assert first_path == second_path
    assert len(list(tmp_path.glob("*.json"))) == 1
    merged = load_snapshots(tmp_path)[0]
    assert sorted(item["title"] for item in merged["evidence_items"]) == [
        "First run",
        "Second run",
    ]
    assert {
        observation["observation_id"] for observation in merged["attention"]["observations"]
    } == {"producer:hacker-news:27", "producer:hacker-news:9999"}
    # The union covers the wider of the two windows, so `since` is the earlier.
    assert merged["since"] == first.since.isoformat()
    # One count describes the file. Every other counter describes the last
    # pass alone, and the two scopes stay separate rather than being blended
    # into a funnel that reads as one chain.
    assert merged["selection"]["published_total"] == 2
    assert merged["selection"]["published"] == 1
    assert merged["selection"]["qualified"] == 1
    assert merged["selection"]["fetched"] == 12
    assert merged["selection"]["merged_from"] == sorted(
        [first.generated_at.isoformat(), second.generated_at.isoformat()]
    )


def test_same_utc_day_prefers_the_newer_record_on_collision(tmp_path):
    # Both passes see the long-lived artifacts. The newer pass observed them
    # more recently, so its metrics are the fresher reading, and the artifact
    # must appear once rather than twice.
    first = radar_run(title="Stale reading")
    second = radar_run(title="Fresh reading")
    second.items[0].metrics = {"citations": 9}

    write_snapshot(first, tmp_path)
    write_snapshot(second, tmp_path)

    merged = load_snapshots(tmp_path)[0]
    assert len(merged["evidence_items"]) == 1
    assert merged["evidence_items"][0]["title"] == "Fresh reading"
    assert merged["evidence_items"][0]["metrics"] == {"citations": 9}


def test_same_utc_day_rejects_stale_retry_metadata_as_the_newest_pass(tmp_path):
    newer = radar_run(title="Newer reading")
    newer.generated_at = datetime(2026, 7, 27, 18, tzinfo=UTC)
    newer.selection = {"fetched": 80, "published": 1}
    newer.items[0].metrics = {"citations": 9}
    stale_retry = radar_run(title="Stale retry")
    stale_retry.generated_at = datetime(2026, 7, 27, 6, tzinfo=UTC)
    stale_retry.selection = {"fetched": 40, "published": 1}

    write_snapshot(newer, tmp_path)
    write_snapshot(stale_retry, tmp_path)

    merged = load_snapshots(tmp_path)[0]
    assert merged["generated_at"] == newer.generated_at.isoformat()
    assert merged["selection"]["fetched"] == 80
    assert merged["evidence_items"][0]["title"] == "Newer reading"
    assert merged["evidence_items"][0]["metrics"] == {"citations": 9}


def test_same_utc_day_joins_records_through_any_exact_identifier(tmp_path):
    first = radar_run(title="DOI and arXiv observation")
    first.items[0].source = "Semantic Scholar"
    first.items[0].source_id = "S2-bridge"
    first.items[0].url = "https://www.semanticscholar.org/paper/S2-bridge"
    first.items[0].artifact_urls = [
        "https://doi.org/10.1000/radar",
        "https://arxiv.org/abs/2607.0027",
    ]
    second = radar_run(title="Fresh arXiv observation")
    second.generated_at = first.generated_at + timedelta(hours=6)

    write_snapshot(first, tmp_path)
    write_snapshot(second, tmp_path)

    merged = load_snapshots(tmp_path)[0]
    assert len(merged["evidence_items"]) == 1
    assert merged["evidence_items"][0]["title"] == "Fresh arXiv observation"


def test_a_pass_that_fetched_nothing_keeps_the_day_and_reports_an_honest_funnel(tmp_path):
    # A source outage can hand us a pass with no items at all. Merging it must
    # keep the day's existing records, and must not leave the file claiming it
    # fetched nothing yet published dozens: the per-pass funnel stays
    # internally consistent, and the file's own count lives in
    # `published_total`.
    first = radar_run(title="Morning run")
    first.selection = {"fetched": 10, "qualified": 1, "published": 1}
    write_snapshot(first, tmp_path)

    outage = radar_run(title="Outage run")
    outage.items = []
    outage.generated_at = first.generated_at + timedelta(hours=6)
    outage.since = outage.generated_at - timedelta(hours=12)
    outage.selection = {"fetched": 0, "qualified": 0, "published": 0}
    write_snapshot(outage, tmp_path)

    merged = load_snapshots(tmp_path)[0]
    assert [item["title"] for item in merged["evidence_items"]] == ["Morning run"]
    selection = merged["selection"]
    assert selection["published_total"] == 1
    assert selection["fetched"] == 0
    # The impossible funnel this guards against: `fetched: 0` sitting beside a
    # `published` that counts records the pass never saw.
    assert selection["published"] == 0
    assert selection["published"] <= selection["fetched"]


def test_writing_the_same_run_twice_changes_nothing(tmp_path):
    write_snapshot(radar_run(), tmp_path)
    first_bytes = (tmp_path / "2026-07-27.json").read_bytes()
    write_snapshot(radar_run(), tmp_path)

    assert (tmp_path / "2026-07-27.json").read_bytes() == first_bytes
    assert len(load_snapshots(tmp_path)[0]["evidence_items"]) == 1


def test_rebuild_is_deterministic(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)
    output = tmp_path / "radar.json"

    first = rebuild_dashboard(snapshot_dir, output)
    first_bytes = output.read_bytes()
    second = rebuild_dashboard(snapshot_dir, output)

    assert first == second
    assert first_bytes == output.read_bytes()
    assert first["facets"]["dates"] == ["2026-07-26", "2026-07-27"]
    assert first["days"][0]["category_counts"] == {"benchmark": 1, "evaluation": 1}
    assert first["days"][0]["evidence_count"] == 1
    assert first["days"][0]["attention"]["new_count"] == 1
    assert first["days"][0]["attention"]["active_count"] == 1


def test_rebuild_writes_a_small_latest_day_bootstrap(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)
    output = tmp_path / "site" / "data" / "radar.json"

    dashboard = rebuild_dashboard(snapshot_dir, output)

    bootstrap_path = output.with_name("radar-bootstrap.json")
    assert bootstrap_path.exists()
    bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    assert bootstrap["bootstrap"] is True
    assert [day["date"] for day in bootstrap["days"]] == ["2026-07-27"]
    assert bootstrap["facets"]["dates"] == ["2026-07-26", "2026-07-27"]
    assert bootstrap["corpus"] == {"aggregates": dashboard["corpus"]["aggregates"]}
    # The leaderboard's score panel renders straight off this payload and
    # nothing upgrades it to the full bundle first, so the progression ships.
    assert bootstrap["benchmark_score_progression"] == dashboard["benchmark_score_progression"]
    assert bootstrap_path.stat().st_size < output.stat().st_size

    trends_path = output.with_name("radar-trends.json")
    assert trends_path.exists()
    trends = json.loads(trends_path.read_text(encoding="utf-8"))
    assert [day["date"] for day in trends["days"]] == ["2026-07-26", "2026-07-27"]
    assert all("evidence_items" not in day for day in trends["days"])
    assert all("briefing" not in day for day in trends["days"])
    assert all("questions" not in day for day in trends["days"])
    assert trends["days"][-1]["evidence_count"] == dashboard["days"][-1]["evidence_count"]
    assert trends["corpus"] == {"aggregates": dashboard["corpus"]["aggregates"]}
    assert trends_path.stat().st_size < output.stat().st_size
    assert trends_path.stat().st_size <= bootstrap_path.stat().st_size or len(trends["days"]) > len(
        bootstrap["days"]
    )


def test_rebuild_can_publish_the_feed_from_the_same_snapshot_history(tmp_path, site_shell):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)
    feed_output = tmp_path / "site" / "feed.xml"
    site_shell(tmp_path / "site")

    rebuild_dashboard(
        snapshot_dir,
        tmp_path / "site" / "data" / "radar.json",
        feed_output=feed_output,
    )

    root = ET.parse(feed_output).getroot()
    assert [item.findtext("title") for item in root.findall("./channel/item")] == [
        "Benchmark Radar — 2026-07-27",
        "Benchmark Radar — 2026-07-26",
    ]


def test_rebuild_writes_the_sitemap_at_the_site_root(tmp_path, site_shell):
    """The Pages build must publish the URL advertised by robots.txt."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    data_output = tmp_path / "site" / "data" / "radar.json"
    feed_output = tmp_path / "site" / "feed.xml"
    site_shell(tmp_path / "site")
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    for slug in ("alpha-bench", "zeta-bench"):
        (shard_dir / f"{slug}.json").write_text("{}", encoding="utf-8")

    rebuild_dashboard(
        snapshot_dir,
        data_output,
        feed_output=feed_output,
        benchmark_shard_dir=shard_dir,
    )

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_output = tmp_path / "site" / "sitemap.xml"
    assert sitemap_output.exists()
    assert not (data_output.parent / "sitemap.xml").exists()
    for slug in ("leaderboard", "trends", "explore", "cli", "cite", "rubric"):
        assert (tmp_path / "site" / slug / "index.html").exists()
    root = ET.parse(sitemap_output).getroot()
    urls = [node.text for node in root.findall("sm:url/sm:loc", ns)]
    assert urls == [
        f"{SITE_URL}/",
        f"{SITE_URL}/leaderboard/",
        f"{SITE_URL}/trends/",
        f"{SITE_URL}/explore/",
        f"{SITE_URL}/cli/",
        f"{SITE_URL}/cite/",
        f"{SITE_URL}/rubric/",
        f"{SITE_URL}/benchmarks/",
        f"{SITE_URL}/benchmarks/alpha-bench/",
        f"{SITE_URL}/benchmarks/zeta-bench/",
        f"{SITE_URL}/blog/",
        f"{SITE_URL}/blog/archive/",
        f"{SITE_URL}/blog/2026-07-27/",
    ]
    lastmods = [node.text for node in root.findall("sm:url/sm:lastmod", ns)]
    assert lastmods == ["2026-07-27"] * len(urls)


def test_rescore_applies_a_new_category_to_older_snapshots(tmp_path):
    """Regression for issue #52: snapshots are append-only, so a category
    added on day N stayed absent from every earlier day and the dashboard
    divided a one-day numerator by a nine-day denominator. That published
    `agentic: 3` when the same corpus re-scored yielded far more."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26, title="A Benchmark for Web Agents"), snapshot_dir)
    write_snapshot(radar_run(27, title="A Benchmark for Web Agents"), snapshot_dir)
    stored = load_snapshots(snapshot_dir)
    assert "agentic" not in stored[0]["evidence_items"][0]["categories"]

    config = {
        "taxonomy": {
            "benchmark": ["benchmark"],
            "agentic": {
                "within": 15,
                "any_of": ["agent", "agents", "agentic"],
                "near": ["benchmark", "evaluation"],
            },
        }
    }
    summary = rescore_snapshot_history(config, snapshot_dir)

    rescored = load_snapshots(snapshot_dir)
    assert summary["snapshots"] == 2
    assert summary["after"]["agentic"] == 2
    assert all("agentic" in day["evidence_items"][0]["categories"] for day in rescored)


def test_rescore_matches_terms_like_the_daily_pipeline_does(tmp_path):
    """Regression: the rescore pass used a bare substring test, so `corpora`
    matched inside "incorporates" and the rewritten snapshot diverged from what
    the daily pipeline (word-start anchored, pipeline.match_phrase) scored on
    the day. The rewrite must use the same matcher as live scoring."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(
        radar_run(26, title="A Toolchain that Incorporates Benchmark Results"),
        snapshot_dir,
    )
    config = {"taxonomy": {"dataset": ["corpora"]}}

    summary = rescore_snapshot_history(config, snapshot_dir)

    assert summary["after"].get("dataset", 0) == 0


def test_rescore_preserves_the_scores_the_run_actually_recorded(tmp_path):
    """Only categories are rewritten. Scores and timestamps describe what the
    pipeline did on the day it ran; rewriting them would turn an audit trail
    into a fiction."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    before = load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    rescore_snapshot_history({"taxonomy": {"benchmark": ["benchmark"]}}, snapshot_dir)
    after = load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    assert after["total_score"] == before["total_score"]
    assert after["published_at"] == before["published_at"]
    assert after["url"] == before["url"]


def test_rescore_is_idempotent(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    config = {"taxonomy": {"benchmark": ["benchmark"], "evaluation": ["evaluat"]}}

    first = rescore_snapshot_history(config, snapshot_dir)
    first_bytes = sorted(path.read_bytes() for path in snapshot_dir.glob("*.json"))
    second = rescore_snapshot_history(config, snapshot_dir)

    assert second["records_changed"] == 0
    assert first["after"] == second["after"]
    assert first_bytes == sorted(path.read_bytes() for path in snapshot_dir.glob("*.json"))


def test_records_badge_reports_the_corpus_observation_count(tmp_path):
    # The README used to hand-type "4,000+ records" and let it drift out of
    # date. The badge must derive the number from the corpus it is built
    # beside, so it can only ever state what was actually collected (issue
    # #197).
    snapshot_dir = tmp_path / "snapshots"
    for day in range(1, 6):
        write_snapshot(radar_run(day), snapshot_dir)
    output = tmp_path / "radar.json"
    dashboard = rebuild_dashboard(snapshot_dir, output)

    document = json.loads(records_badge(dashboard))
    assert document["schemaVersion"] == 1
    assert document["label"] == "benchmark records collected"
    # 5 days x one record each, with the expected denominators.
    assert document["message"] == f"{dashboard['corpus']['observation_count']} records · 5 days"
    assert str(dashboard["corpus"]["observation_count"]) in document["message"]


def test_records_badge_writes_beside_the_dashboard(tmp_path):
    # The badge is a standalone artefact that deploys with radar.json, so a
    # hyperlink citation of it can never disagree with the dashboard the page
    # renders (issue #197).
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(1), snapshot_dir)
    output = tmp_path / "site" / "data" / "radar.json"

    rebuild_dashboard(snapshot_dir, output)

    badge_path = tmp_path / "site" / "data" / "records-badge.json"
    assert badge_path.exists()
    document = json.loads(badge_path.read_text(encoding="utf-8"))
    assert "records" in document["message"]


def test_thirty_snapshots_replay_into_one_deterministic_cumulative_entity(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    for day in range(1, 31):
        run = radar_run(day)
        run.items[0].source_id = "2607.0001"
        run.items[0].url = "https://arxiv.org/abs/2607.0001"
        write_snapshot(run, snapshot_dir)
    output = tmp_path / "radar.json"

    first = rebuild_dashboard(snapshot_dir, output)
    first_bytes = output.read_bytes()
    second = rebuild_dashboard(snapshot_dir, output)
    artifacts = [entity for entity in first["corpus"]["entities"] if entity["type"] == "artifact"]
    benchmark = next(
        topic for topic in first["corpus"]["aggregates"]["topics"] if topic["topic"] == "benchmark"
    )

    assert first == second
    assert first_bytes == output.read_bytes()
    assert first["snapshot_count"] == 30
    assert len(artifacts) == 1
    assert artifacts[0]["observation_count"] == 30
    assert len(artifacts[0]["seen_days"]) == 30
    assert benchmark["persistence_days"] == 30
    assert benchmark["velocity"] == 0
    assert first["corpus"]["aggregates"]["provenance"]["primary_source_rate"] >= 0.9
    assert all(
        entity["parser_versions"] and entity["raw_payload_hashes"]
        for entity in first["corpus"]["entities"]
    )
    assert all(
        observation["retrieved_at"]
        and observation["parser_version"]
        and observation["raw_payload_hash"].startswith("sha256:")
        for observation in first["corpus"]["observations"]
    )


def test_dashboard_publishes_the_rubric_that_scored_its_records(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    run = radar_run(27)
    run.selection = {
        "minimum_score": 40.0,
        "report_limit": 30,
        "score_version": 2,
        "score_max": 100,
        "lookback_hours": 48,
    }
    write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    published = data["rubric"]
    assert published["score_max"] == 100.0
    assert [component["key"] for component in published["components"]] == [
        "relevance",
        "evidence",
        "recency",
        "adoption",
    ]
    # Selection policy belongs to the originating day, not the shared scoring
    # rubric used by every v2 record.
    assert "minimum_score" not in published
    assert data["days"][0]["selection"]["minimum_score"] == 40.0


def test_dashboard_publishes_current_threshold_as_recommendation_metadata(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    run = radar_run(27)
    run.selection = {
        "minimum_score": 40.0,
        "recommendation_score": 40.0,
        "score_version": 2,
        "score_max": 100,
        "lookback_hours": 48,
    }
    write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")
    published = data["rubric"]

    assert "recommendation_score" not in published
    assert "minimum_score" not in published
    assert data["days"][0]["selection"]["recommendation_score"] == 40.0
    assert published["limits"]


def test_dashboard_keeps_legacy_scores_on_their_original_rubric(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    run = radar_run(27)
    # The fixture models a snapshot written before score_version was persisted.
    run.items[0].score_version = 1
    run.items[0].score_max = 4
    write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")
    published = data["days"][0]["evidence_items"][0]

    assert published["score_version"] == 1
    assert published["score_max"] == 4
    assert data["rubrics"]["1"]["score_max"] == 4
    assert data["rubrics"]["2"]["score_max"] == 100
    assert data["rubrics"]["4"]["scoring_version"] == 4
    assert data["rubrics"][str(rubric.SCORING_VERSION)]["scoring_version"] == (
        rubric.SCORING_VERSION
    )


def test_dashboard_without_snapshots_publishes_no_cutoff(tmp_path):
    data = rebuild_dashboard(tmp_path / "empty", tmp_path / "radar.json")

    assert "minimum_score" not in data["rubric"]
    assert data["rubric"]["components"]


def test_dashboard_reports_per_category_deltas_and_cumulative(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    first, second = data["days"]
    assert first["category_trends"]["benchmark"]["count"] == 1
    # Nothing precedes the first scan, so no change is claimed.
    assert first["category_trends"]["benchmark"]["delta"] is None
    assert first["category_trends"]["benchmark"]["baseline"] is None
    # Day two matches day one, so the domain is flat but the total accumulates.
    assert second["category_trends"]["benchmark"]["delta"] == 0
    assert second["category_trends"]["benchmark"]["baseline"] == 1.0
    assert second["category_trends"]["benchmark"]["cumulative"] == 2
    assert second["cumulative_evidence_count"] == 2


def test_trend_deltas_exclude_records_reannounced_as_updated(tmp_path):
    # Issue #50: a paper reannounced as an "updated" version is not new
    # activity in the field, so it must not move the 30-day change the way a
    # fresh "released" sighting does.
    snapshot_dir = tmp_path / "snapshots"
    baseline = radar_run(26)
    write_snapshot(baseline, snapshot_dir)
    updated_only = radar_run(27)
    updated_only.items[0].event_kind = "updated"
    write_snapshot(updated_only, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    first, second = data["days"]
    assert first["category_trends"]["benchmark"]["count"] == 1
    trend = second["category_trends"]["benchmark"]
    # The all-events total still shows the record; the release-based trend
    # figures it feeds do not count it as new.
    assert second["category_counts"]["benchmark"] == 1
    assert trend["count"] == 0
    assert trend["delta"] == -1
    assert trend["total_count"] == 1
    # Cumulative corpus coverage is unaffected: the artifact is still real and
    # still in the corpus, whichever event announced it.
    assert trend["cumulative"] == 2


def test_cumulative_counts_artifacts_once_across_overlapping_windows(tmp_path):
    # The scan window overlaps by design, so the same repository appears on
    # adjacent days. Summing daily counts would grow the total while nothing
    # new was actually discovered.
    snapshot_dir = tmp_path / "snapshots"
    for day in (26, 27):
        run = radar_run(day)
        # Same artifact identity on both days.
        run.items[0].source_id = "2607.0001"
        run.items[0].url = "https://arxiv.org/abs/2607.0001"
        write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    second = data["days"][1]
    assert second["category_trends"]["benchmark"]["cumulative"] == 1
    assert second["cumulative_evidence_count"] == 1


def test_trends_do_not_compare_across_a_report_limit_change(tmp_path):
    # Raising the cap lifts every count at once. Reporting that as domain
    # momentum would present a collection-policy change as a change in field.
    snapshot_dir = tmp_path / "snapshots"
    narrow = radar_run(26)
    narrow.selection = {"report_limit": 30}
    wide = radar_run(27)
    wide.selection = {"report_limit": 300}
    write_snapshot(narrow, snapshot_dir)
    write_snapshot(wide, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    after = data["days"][1]["category_trends"]["benchmark"]
    assert after["delta"] is None
    assert after["baseline"] is None
    assert after["comparable"] is False
    # Cumulative totals still accrue: they describe the corpus, not a rate.
    assert after["cumulative"] == 2


def test_trends_compare_snapshots_sharing_a_report_limit(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    for day in (26, 27):
        run = radar_run(day)
        run.selection = {"report_limit": 300}
        write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    after = data["days"][1]["category_trends"]["benchmark"]
    assert after["delta"] == 0
    assert after["comparable"] is True


def test_trends_do_not_compare_when_connector_coverage_changes(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    first = radar_run(26)
    first.selection = {"report_limit": 300}
    second = radar_run(27)
    second.selection = {"report_limit": 300}
    second.health[1] = SourceHealth(source="brave", ok=True, item_count=1)
    write_snapshot(first, snapshot_dir)
    write_snapshot(second, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    before, after = data["days"]
    assert before["coverage_complete"] is False
    assert before["coverage_gaps"] == ["brave"]
    assert after["coverage_complete"] is True
    assert after["category_trends"]["benchmark"]["comparable"] is False


def test_degraded_ignores_optional_source_gaps(tmp_path):
    # The fixture's only failing source (brave) is optional: missing its API
    # key fails every run and must not be reported as "degraded" (issue #53).
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert data["days"][-1]["coverage_complete"] is False
    assert data["days"][-1]["required_coverage_complete"] is True
    assert data["degraded"] is False
    assert data["last_successful_collection_at"] == data["generated_at"]


def test_last_successful_collection_at_skips_required_source_failures(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    healthy = radar_run(26)
    degraded = radar_run(27)
    degraded.health[0] = SourceHealth(source="arxiv", ok=False, error="RequestError: HTTP 500")
    write_snapshot(healthy, snapshot_dir)
    write_snapshot(degraded, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert data["degraded"] is True
    assert data["last_successful_collection_at"] == data["days"][0]["generated_at"]
    assert data["last_successful_collection_at"] != data["generated_at"]


def test_last_successful_collection_at_is_none_when_no_run_ever_had_required_coverage(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    run = radar_run(27)
    run.health[0] = SourceHealth(source="arxiv", ok=False, error="RequestError: HTTP 500")
    write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert data["degraded"] is True
    assert data["last_successful_collection_at"] is None


def test_selection_counts_round_trip_through_the_snapshot(tmp_path):
    run = radar_run(27)
    run.selection = {"fetched": 300, "published": 30, "minimum_score": 2.0}

    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)

    write_snapshot(run, tmp_path / "snapshots")
    data = rebuild_dashboard(tmp_path / "snapshots", tmp_path / "radar.json")
    assert data["days"][-1]["selection"]["fetched"] == 300


def test_snapshots_without_selection_stay_valid():
    snapshot = snapshot_for_run(radar_run())
    snapshot.pop("selection")

    validate_snapshot(snapshot)


def test_validation_rejects_missing_item_fields():
    snapshot = snapshot_for_run(radar_run())
    del snapshot["evidence_items"][0]["event_kind"]

    with pytest.raises(SnapshotError, match="event_kind"):
        validate_snapshot(snapshot)


def test_validation_rejects_raw_source_payloads():
    snapshot = snapshot_for_run(radar_run())
    snapshot["evidence_items"][0]["raw"] = {"private": "source payload"}

    with pytest.raises(SnapshotError, match="raw source payloads"):
        validate_snapshot(snapshot)


def test_schema_one_snapshot_is_normalized_for_rebuild(tmp_path):
    current = snapshot_for_run(radar_run())
    legacy = {
        "schema_version": 1,
        "date": current["date"],
        "generated_at": current["generated_at"],
        "since": current["since"],
        "items": current["evidence_items"],
        "health": current["ingest_health"][:2],
    }
    path = tmp_path / "2026-07-27.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    normalized = load_snapshots(tmp_path)[0]

    assert normalized["schema_version"] == 2
    assert normalized["evidence_items"][0]["discovered_at"] == current["generated_at"]
    assert normalized["attention"] == {"observations": []}


def test_attention_can_never_be_marked_quality_scored():
    snapshot = snapshot_for_run(radar_run())
    snapshot["attention"]["observations"][0]["quality_scored"] = True

    with pytest.raises(SnapshotError, match="quality_scored false"):
        validate_snapshot(snapshot)


def test_supporting_attention_requires_valid_timestamp():
    snapshot = snapshot_for_run(radar_run())
    snapshot["attention"]["observations"][0]["supporting_observations"][0]["published_at"] = (
        "not-a-time"
    )

    with pytest.raises(SnapshotError, match="supporting observation 0 published_at"):
        validate_snapshot(snapshot)


def test_migrate_does_not_refetch_attention_for_schema_two(tmp_path, monkeypatch):
    write_snapshot(radar_run(), tmp_path)
    monkeypatch.setattr(
        "benchmark_radar.snapshots.fetch_attention_feeds",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected refetch")),
    )

    migrated = migrate_snapshot_history({}, tmp_path)

    assert migrated[0]["schema_version"] == 2


def test_migrate_backfills_bare_github_release_titles_idempotently(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot = snapshot_for_run(radar_run())
    record = snapshot["evidence_items"][0]
    record.update(
        {
            "source": "GitHub Release",
            "source_id": "modelscope/evalscope@v1.11.0",
            "title": "v1.11.0",
            "url": "https://github.com/modelscope/evalscope/releases/tag/v1.11.0",
            "parser_version": "github-releases/1",
        }
    )
    original_hash = record["raw_payload_hash"]
    path = snapshot_dir / "2026-07-27.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    migrate_snapshot_history({}, snapshot_dir)
    first_pass = path.read_text(encoding="utf-8")
    dashboard = rebuild_dashboard(snapshot_dir, tmp_path / "site" / "radar.json")

    migrated = json.loads(first_pass)["evidence_items"][0]
    assert migrated["title"] == "modelscope/evalscope v1.11.0"
    assert migrated["parser_version"] == GITHUB_RELEASE_PARSER_VERSION
    assert migrated["raw_payload_hash"] == original_hash
    assert dashboard["days"][0]["evidence_items"][0]["title"] == ("modelscope/evalscope v1.11.0")
    artifact = next(
        entity for entity in dashboard["corpus"]["entities"] if entity["type"] == "artifact"
    )
    assert artifact["label"] == "modelscope/evalscope v1.11.0"

    migrate_snapshot_history({}, snapshot_dir)
    assert path.read_text(encoding="utf-8") == first_pass


def test_cumulative_counts_one_artifact_reported_by_two_sources_once(tmp_path):
    # Identity was `source:source_id`, so the same paper found via arXiv and via
    # a secondary index that links it counted twice, contradicting the
    # "distinct artifacts, not sightings" promise the function documents.
    generated = datetime(2026, 7, 27, 12, 15, tzinfo=UTC)
    run = radar_run(27)
    run.items.append(
        RadarItem(
            source="Semantic Scholar",
            source_id="s2-abc123",
            title="A New Evaluation Benchmark Mirrored Elsewhere",
            url="https://www.semanticscholar.org/paper/s2-abc123",
            published_at=generated - timedelta(hours=3),
            summary="The same release, indexed by a second source.",
            event_kind="released",
            categories=["benchmark"],
            # Links the arXiv record, so both resolve to one artifact.
            artifact_urls=["https://arxiv.org/abs/2607.0027"],
            total_score=2.6,
            rationale=["Matched: benchmark"],
        )
    )
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(run, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")
    day = data["days"][0]

    assert day["category_trends"]["benchmark"]["count"] == 2
    # Two sightings, one artifact.
    assert day["category_trends"]["benchmark"]["cumulative"] == 1
    assert day["cumulative_evidence_count"] == 1


def test_cumulative_counts_transitively_linked_identifiers_once(tmp_path):
    first = radar_run(26)
    first.items[0].source = "Semantic Scholar"
    first.items[0].source_id = "s2-abc123"
    first.items[0].url = "https://www.semanticscholar.org/paper/s2-abc123"
    first.items[0].artifact_urls = [
        "https://doi.org/10.1000/radar",
        "https://arxiv.org/abs/2607.0027",
    ]
    second = radar_run(27)
    second.items[0].source = "OpenAlex"
    second.items[0].source_id = "W1"
    second.items[0].url = "https://openalex.org/W1"
    second.items[0].artifact_urls = ["https://arxiv.org/abs/2607.0027"]
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(first, snapshot_dir)
    write_snapshot(second, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")
    day = data["days"][1]

    assert day["category_trends"]["benchmark"]["cumulative"] == 1
    assert day["cumulative_evidence_count"] == 1


def test_later_alias_bridge_does_not_rewrite_earlier_trend(tmp_path):
    first = radar_run(26)
    first.items.append(
        RadarItem(
            source="OpenAlex",
            source_id="W1",
            title="A DOI-only sighting",
            url="https://openalex.org/W1",
            published_at=first.generated_at - timedelta(hours=2),
            summary="A benchmark.",
            categories=["benchmark"],
            artifact_urls=["https://doi.org/10.1000/radar"],
            total_score=50,
        )
    )
    first.items[0].artifact_urls = ["https://arxiv.org/abs/2607.0026"]
    second = radar_run(27)
    second.items[0].source = "Semantic Scholar"
    second.items[0].source_id = "s2-bridge"
    second.items[0].url = "https://www.semanticscholar.org/paper/s2-bridge"
    second.items[0].artifact_urls = [
        "https://doi.org/10.1000/radar",
        "https://arxiv.org/abs/2607.0026",
    ]
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(first, snapshot_dir)
    write_snapshot(second, snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert data["days"][0]["cumulative_evidence_count"] == 2
    assert data["days"][1]["cumulative_evidence_count"] == 1


def test_dashboard_publishes_the_model_card_adoption_rank(tmp_path):
    # Issue #83: the curated Model Card Adoption Rank rides along in the same
    # published file the dashboard already loads, so the browser needs no second
    # fetch and no second schema.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")
    board = data["model_card_leaderboard"]

    assert board["model_card_count"] > 0
    assert board["entries"][0]["rank"] == 1
    # Asserted as the claim rather than the phrasing. Issue #241 rewrote this
    # for a 16-year-old reader ("vendor attention", "saturated" and
    # "contaminated" were vocabulary a reader had to already have), and a test
    # that pins the old words would force the jargon back.
    #
    # The load-bearing part is that popularity is not quality, and that the
    # statement travels with the data rather than living only in the UI.
    assert "not the same as a good one" in board["measures"]
    assert "how many" in board["measures"].lower()


def test_dashboard_omits_the_leaderboard_when_the_registry_is_absent(tmp_path):
    # A checkout without the curated file still publishes a working dashboard:
    # the daily radar's own collection does not depend on this dataset.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)

    data = rebuild_dashboard(
        snapshot_dir,
        tmp_path / "radar.json",
        registry_path=tmp_path / "absent.yml",
    )

    assert data["model_card_leaderboard"] is None
    assert data["snapshot_count"] == 1


def test_dashboard_fails_rather_than_publishing_a_stale_ranking(tmp_path):
    # An invalid registry must not be swallowed into a missing leaderboard: the
    # previous ranking would stay on the page with nothing signalling it went
    # stale, which is worse than a failed build.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    broken = tmp_path / "model_cards.yml"
    broken.write_text("schema_version: 1\nbenchmarks: []\nmodel_cards: []\n", encoding="utf-8")

    with pytest.raises(ModelCardRegistryError):
        rebuild_dashboard(snapshot_dir, tmp_path / "radar.json", registry_path=broken)


def test_a_custom_registry_does_not_inherit_the_default_score_file(tmp_path):
    # Codex P2. The two curated files are a matched pair: every score cites a
    # source_id that must be a document in the registry beside it. Defaulting the
    # score file under a custom registry paired them with a registry never meant
    # to hold them, so the provenance cross-check correctly refused and every
    # `--model-cards` rebuild against an alternate registry failed.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    registry = tmp_path / "cards.yml"
    registry.write_text(
        "schema_version: 1\n"
        "benchmarks:\n"
        "  - id: alpha\n"
        "    name: Alpha\n"
        "    domain: math\n"
        "    caveat: Test caveat.\n"
        "model_cards:\n"
        "  - id: some_card\n"
        "    organization: Org\n"
        "    model: M\n"
        "    url: https://example.com/card\n"
        "    published: '2025-01-01'\n"
        "    benchmarks: [alpha]\n",
        encoding="utf-8",
    )

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json", registry_path=registry)

    # The adoption ranking still builds; the score layer is simply absent rather
    # than crashing the run or being cited to the wrong documents.
    assert data["model_card_leaderboard"] is not None
    assert data["benchmark_score_progression"] is None
    assert data["benchmark_insights"] is None


def test_the_default_registry_is_recognized_through_an_equivalent_path(tmp_path):
    # Codex P2. `--model-cards "$PWD/data/model_cards.yml"` names the same file as
    # the relative default, so treating it as a custom registry silently dropped
    # scores and insights from a build that should have carried them.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)

    data = rebuild_dashboard(
        snapshot_dir,
        tmp_path / "radar.json",
        registry_path=Path("data/model_cards.yml").resolve(),
    )

    assert data["benchmark_score_progression"] is not None
    assert data["benchmark_insights"] is not None


def test_the_default_registry_still_carries_the_default_scores(tmp_path):
    # The other half of the pairing rule: omitting both paths must still publish
    # all three layers, or the shipped dashboard would silently lose its scores.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert data["model_card_leaderboard"] is not None
    assert data["benchmark_score_progression"] is not None
    assert data["benchmark_insights"] is not None


def test_taxonomy_version_tracks_content_not_a_hand_bumped_constant():
    from benchmark_radar.rubric import taxonomy_version

    # Issue #72 asked for trend values bound to the taxonomy that produced
    # them. A version a maintainer has to remember to increment silently stops
    # being true the first time someone edits a keyword and forgets, which is
    # the exact failure it exists to detect, so it is derived from content.
    taxonomy = {"benchmark": ["benchmark"], "agentic": ["agent"]}

    assert taxonomy_version(taxonomy) == taxonomy_version(dict(reversed(list(taxonomy.items()))))
    assert taxonomy_version(taxonomy) != taxonomy_version(
        {"benchmark": ["benchmark", "leaderboard"], "agentic": ["agent"]}
    )


def test_rescore_records_which_rules_classified_each_record(tmp_path):
    # A category count is only comparable across days classified the same way.
    # Before this, nothing in a snapshot said which rules had run.
    from benchmark_radar.rubric import taxonomy_version

    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    config = {"taxonomy": {"benchmark": ["benchmark"]}}

    summary = rescore_snapshot_history(config, snapshot_dir)
    stored = load_snapshots(snapshot_dir)[0]

    expected = taxonomy_version(config["taxonomy"])
    assert summary["taxonomy_version"] == expected
    # Stamped on every record, not only the ones that moved: a record whose
    # categories happened not to change was still evaluated by these rules.
    assert all(item["taxonomy_version"] == expected for item in stored["evidence_items"])
    # And on the aggregate, so a consumer reading counts rather than records
    # inherits the same provenance.
    assert stored["selection"]["taxonomy_version"] == expected


def test_rescore_marks_a_reclassified_record_as_a_distinct_event(tmp_path):
    # Regression for issue #72: PR #67 moved cumulative `agentic` from 3 to 78
    # in one command. That was a rules change, not 75 new agent benchmarks, and
    # nothing distinguished the two once written.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27, title="A Benchmark for Web Agents"), snapshot_dir)

    # Rescore once under the taxonomy the record was already stored with, so
    # the second pass is the only thing that moves a category. Re-running the
    # same rules must leave no marker, or every record would look reclassified
    # on every pass and the signal would mean nothing.
    settled = {"taxonomy": {"benchmark": ["benchmark"], "evaluation": ["evaluat"]}}
    rescore_snapshot_history(settled, snapshot_dir)
    rescore_snapshot_history(settled, snapshot_dir)
    unchanged = load_snapshots(snapshot_dir)[0]["evidence_items"][0]
    assert "reclassified" not in unchanged

    rescore_snapshot_history(
        {**settled, "taxonomy": {**settled["taxonomy"], "agentic": ["agent"]}}, snapshot_dir
    )
    changed = load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    assert changed["reclassified"]["from"] == unchanged["categories"]
    assert "agentic" in changed["reclassified"]["to"]
    assert changed["categories"] == changed["reclassified"]["to"]
    # Two reclassification passes under different taxonomies are different
    # events, and only the version tells them apart.
    assert changed["reclassified"]["taxonomy_version"] == changed["taxonomy_version"]


def test_rescore_does_not_rewrite_the_event_kind_the_source_announced(tmp_path):
    # `event_kind` records what the *source* said it did. A reclassification is
    # something the radar did to its own records, so overwriting event_kind
    # would destroy a source fact to describe a local one.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    before = load_snapshots(snapshot_dir)[0]["evidence_items"][0]["event_kind"]

    rescore_snapshot_history(
        {"taxonomy": {"benchmark": ["benchmark"], "agentic": ["agent"]}}, snapshot_dir
    )
    after = load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    assert after["event_kind"] == before


def test_trends_refuse_to_compare_across_a_taxonomy_change():
    from benchmark_radar.snapshots import _collection_context

    # The same guard already applied to report_limit: a count that moved
    # because the measurement changed is not domain momentum. A trend line
    # spanning a rules change would report a fix as an explosion.
    base = {"coverage_signature": ["x"]}
    first = {**base, "selection": {"report_limit": 300, "taxonomy_version": "sha256:aaa"}}
    same = {**base, "selection": {"report_limit": 300, "taxonomy_version": "sha256:aaa"}}
    other = {**base, "selection": {"report_limit": 300, "taxonomy_version": "sha256:bbb"}}
    unstamped = {**base, "selection": {"report_limit": 300}}

    assert _collection_context(first) == _collection_context(same)
    assert _collection_context(first) != _collection_context(other)
    # A day predating the field was classified by rules nobody recorded. It can
    # be compared with other such days, but claiming it comparable to a day
    # whose rules are known would assert something unverifiable.
    assert _collection_context(unstamped) != _collection_context(first)
    assert _collection_context(unstamped) == _collection_context({**unstamped})


def test_a_settled_reclassification_marker_does_not_persist(tmp_path):
    # Regression caught while building issue #72's marker: it was written on
    # change but never cleared. `rescore` is idempotent and re-run routinely,
    # so a record reclassified once carried that claim forever, and a reader
    # auditing today's trend would attribute it to a rules change that happened
    # weeks ago and has since settled.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27, title="A Benchmark for Web Agents"), snapshot_dir)

    widened = {"taxonomy": {"benchmark": ["benchmark"], "agentic": ["agent"]}}
    rescore_snapshot_history(widened, snapshot_dir)
    assert "reclassified" in load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    # Same rules again: nothing moved, so nothing is reclassified any more.
    rescore_snapshot_history(widened, snapshot_dir)
    settled = load_snapshots(snapshot_dir)[0]["evidence_items"][0]

    assert "reclassified" not in settled
    # The provenance stamp stays: it says which rules classified the record,
    # which is true on every pass, unlike the marker.
    assert settled["taxonomy_version"]


def test_snapshots_predating_the_taxonomy_stamp_still_compare_to_each_other(tmp_path):
    # Every snapshot already on disk was written before `taxonomy_version`
    # existed. Gating comparability on a field none of them carry would have
    # silently emptied the trend history rather than qualifying it.
    snapshot_dir = tmp_path / "snapshots"
    for day in (25, 26, 27):
        write_snapshot(radar_run(day), snapshot_dir)
    output = tmp_path / "radar.json"

    data = rebuild_dashboard(snapshot_dir, output)

    assert all((day.get("selection") or {}).get("taxonomy_version") is None for day in data["days"])
    assert any(
        trend["comparable"] for day in data["days"] for trend in day["category_trends"].values()
    )


def test_the_first_stamped_day_does_not_compare_across_the_boundary(tmp_path):
    # The transition itself is the risk: the day a taxonomy stamp first appears
    # is a day whose counts came from rules the previous day cannot vouch for.
    # It must break comparison exactly once, then resume.
    snapshot_dir = tmp_path / "snapshots"
    for day in (25, 26, 27):
        write_snapshot(radar_run(day), snapshot_dir)
    paths = sorted(snapshot_dir.glob("*.json"))
    for path in paths[-1:]:
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["selection"]["taxonomy_version"] = "sha256:newrules"
        path.write_text(json.dumps(stored), encoding="utf-8")

    data = rebuild_dashboard(snapshot_dir, tmp_path / "radar.json")

    assert not any(trend["comparable"] for trend in data["days"][-1]["category_trends"].values())
    assert any(trend["comparable"] for trend in data["days"][-2]["category_trends"].values())


def test_validate_snapshot_rejects_a_briefing_from_another_day():
    run = radar_run()
    run.daily_briefing = ["Yesterday's summary."]
    snapshot = snapshot_for_run(run)
    snapshot["briefing"]["date"] = "2026-07-26"

    # A briefing carrying the wrong date would be published as if it described
    # this day. That is a bug in whatever wrote the file, not a day to quietly
    # regenerate, so it fails loudly.
    with pytest.raises(SnapshotError, match="does not match snapshot date"):
        validate_snapshot(snapshot)


def test_validate_snapshot_rejects_unusable_briefing_bullets():
    run = radar_run()
    run.daily_briefing = ["Real bullet."]
    snapshot = snapshot_for_run(run)

    snapshot["briefing"]["bullets"] = []
    with pytest.raises(SnapshotError, match="non-empty array"):
        validate_snapshot(snapshot)

    snapshot["briefing"]["bullets"] = ["   "]
    with pytest.raises(SnapshotError, match="non-empty strings"):
        validate_snapshot(snapshot)

    snapshot["briefing"]["bullets"] = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    with pytest.raises(SnapshotError, match="more than the 10"):
        validate_snapshot(snapshot)


def test_validate_snapshot_accepts_a_day_without_a_briefing():
    # Every snapshot written before the briefing was persisted stays valid.
    validate_snapshot(snapshot_for_run(radar_run()))


def test_snapshot_persists_and_validates_openai_provenance():
    run = radar_run()
    run.daily_briefing = ["Grounded GPT finding. Evidence: E001."]
    run.daily_briefing_metadata = {
        "generator": "openai-responses",
        "model": "gpt-5.6",
        "response_id": "resp_123",
        "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
        "input": {"evidence_items": 40},
        "citations": [
            {
                "id": "E001",
                "title": "MemoryBench",
                "url": "https://example.test/memory",
                "source": "arXiv",
            }
        ],
    }

    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)

    assert snapshot["briefing"]["generator"] == "openai-responses"
    assert snapshot["briefing"]["usage"]["input_tokens"] == 8000


def test_validate_snapshot_accepts_a_briefing_with_chinese_rendering():
    run = radar_run()
    run.daily_briefing = ["Grounded GPT finding. Evidence: E001. High confidence."]
    run.daily_briefing_metadata = {
        "generator": "openai-responses",
        "model": "gpt-5.6",
        "response_id": "resp_123",
        "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
        "input": {"evidence_items": 40},
        "citations": [
            {
                "id": "E001",
                "title": "MemoryBench",
                "url": "https://example.test/memory",
                "source": "arXiv",
            }
        ],
        "bullets_zh": ["有据可依的 GPT 发现。Evidence: E001. High confidence."],
        "caveat_zh": "仅注入部分记录。",
        "zh_translation": {
            "model": "gpt-5.6-2026-08-01",
            "response_id": "resp_zh",
            "usage": {"input_tokens": 500, "output_tokens": 300, "total_tokens": 800},
        },
    }

    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)

    assert snapshot["briefing"]["bullets_zh"] == [
        "有据可依的 GPT 发现。Evidence: E001. High confidence."
    ]


def test_validate_snapshot_rejects_a_mismatched_zh_bullet_array():
    run = radar_run()
    run.daily_briefing = ["Grounded GPT finding. Evidence: E001.", "Second finding."]
    run.daily_briefing_metadata = {
        "generator": "openai-responses",
        "model": "gpt-5.6",
        "response_id": "resp_123",
        "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
        "input": {"evidence_items": 40},
        "citations": [],
        "bullets_zh": ["只有一条。"],
    }

    snapshot = snapshot_for_run(run)
    with pytest.raises(SnapshotError, match="matching bullets in count"):
        validate_snapshot(snapshot)


def test_validate_snapshot_rejects_an_empty_zh_caveat():
    run = radar_run()
    run.daily_briefing = ["Grounded GPT finding. Evidence: E001."]
    run.daily_briefing_metadata = {
        "generator": "openai-responses",
        "model": "gpt-5.6",
        "response_id": "resp_123",
        "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
        "input": {"evidence_items": 40},
        "citations": [],
        "bullets_zh": ["有据可依的 GPT 发现。Evidence: E001."],
        "caveat_zh": "   ",
    }

    snapshot = snapshot_for_run(run)
    with pytest.raises(SnapshotError, match="caveat_zh must be a non-empty string"):
        validate_snapshot(snapshot)


def test_validate_snapshot_accepts_generated_questions_with_chinese_fields():
    run = radar_run()
    snapshot = snapshot_for_run(run)
    snapshot["questions"] = {
        "schema_version": 1,
        "date": snapshot["date"],
        "status": "generated",
        "generator": "openai-responses",
        "model": "gpt-5.6",
        "groups": [
            {
                "id": "arrivals",
                "title": "What arrived",
                "answers": [
                    {
                        "question": "Q1?",
                        "signal": "One.",
                        "plain_english": "One.",
                        "takeaway": "One.",
                        "counter_view": "None.",
                        "signal_zh": "一个。",
                        "plain_chinese": "一个。",
                        "takeaway_zh": "一个。",
                        "counter_view_zh": "无。",
                    }
                ],
            }
        ],
        "zh_translation": {
            "model": "gpt-5.6-2026-08-01",
            "response_id": "resp_zh",
            "usage": {"input_tokens": 500, "output_tokens": 300, "total_tokens": 800},
        },
    }
    validate_snapshot(snapshot)


def test_validate_snapshot_rejects_an_empty_zh_answer_field():
    run = radar_run()
    snapshot = snapshot_for_run(run)
    snapshot["questions"] = {
        "schema_version": 1,
        "date": snapshot["date"],
        "status": "generated",
        "groups": [
            {
                "id": "arrivals",
                "answers": [
                    {
                        "question": "Q1?",
                        "signal": "One.",
                        "plain_chinese": "  ",
                    }
                ],
            }
        ],
    }

    with pytest.raises(SnapshotError, match="plain_chinese must be a non-empty string"):
        validate_snapshot(snapshot)


def test_validate_snapshot_accepts_questions_written_before_the_zh_feature():
    # Snapshots written before issue #231 never carried zh answer fields; they
    # must keep validating.
    run = radar_run()
    snapshot = snapshot_for_run(run)
    snapshot["questions"] = {
        "schema_version": 1,
        "date": snapshot["date"],
        "status": "generated",
        "groups": [
            {
                "id": "arrivals",
                "answers": [
                    {
                        "question": "Q1?",
                        "signal": "One.",
                        "plain_english": "One.",
                        "takeaway": "One.",
                        "counter_view": "None.",
                    }
                ],
            }
        ],
    }
    validate_snapshot(snapshot)


def test_write_snapshot_preserves_the_briefing_across_passes(tmp_path):
    morning = radar_run()
    morning.daily_briefing = ["Committed by the first pass."]
    write_snapshot(morning, tmp_path)

    afternoon = radar_run(title="Another Evaluation Benchmark")
    write_snapshot(afternoon, tmp_path)

    stored = json.loads((tmp_path / f"{snapshot_for_run(morning)['date']}.json").read_text())
    # The second pass generated no briefing, so the day keeps the one it has
    # rather than losing it to the incoming spread.
    assert stored["briefing"]["bullets"] == ["Committed by the first pass."]


def test_rebuild_dashboard_publishes_the_briefing_for_the_day(tmp_path):
    run = radar_run()
    run.daily_briefing = ["What changed today."]
    write_snapshot(run, tmp_path)
    output = tmp_path / "radar.json"

    rebuild_dashboard(tmp_path, output)

    day = json.loads(output.read_text())["days"][0]
    assert day["briefing"]["bullets"] == ["What changed today."]
    assert day["briefing"]["date"] == day["date"]


def test_rebuild_dashboard_uses_an_empty_briefing_when_the_day_has_none(tmp_path):
    write_snapshot(radar_run(), tmp_path)
    output = tmp_path / "radar.json"

    rebuild_dashboard(tmp_path, output)

    # The dashboard renders its own absent state from this.
    assert json.loads(output.read_text())["days"][0]["briefing"] == {}


def test_rebuild_publishes_a_brief_for_every_snapshot_and_lists_them(tmp_path, site_shell):
    """The blog is built in the same run as the dashboard, from the same history."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)
    site_dir = tmp_path / "site"
    site_shell(site_dir)

    rebuild_dashboard(
        snapshot_dir,
        site_dir / "data" / "radar.json",
        feed_output=site_dir / "feed.xml",
    )

    for day in ("2026-07-26", "2026-07-27"):
        assert (site_dir / "blog" / day / "index.html").exists()
    assert (site_dir / "blog" / "index.html").exists()
    assert (site_dir / "blog" / "archive" / "index.html").exists()

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [
        node.text
        for node in ET.parse(site_dir / "sitemap.xml").getroot().findall("sm:url/sm:loc", ns)
    ]
    assert f"{SITE_URL}/blog/" in urls
    assert f"{SITE_URL}/blog/archive/" in urls
    assert f"{SITE_URL}/blog/2026-07-27/" in urls


def test_the_site_feed_and_the_blog_feed_stay_separate(tmp_path, site_shell):
    """/feed.xml keeps pointing at the dashboard; /blog/feed.xml points at the pages."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    site_dir = tmp_path / "site"
    site_shell(site_dir)

    rebuild_dashboard(
        snapshot_dir,
        site_dir / "data" / "radar.json",
        feed_output=site_dir / "feed.xml",
    )

    site_feed = ET.parse(site_dir / "feed.xml").getroot()
    blog_feed = ET.parse(site_dir / "blog" / "feed.xml").getroot()
    assert site_feed.findtext("./channel/title") == "Benchmark Radar"
    assert [item.findtext("link") for item in site_feed.findall("./channel/item")] == [
        f"{SITE_URL}/?date=2026-07-27"
    ]
    assert blog_feed.findtext("./channel/title") == "Benchmark Radar daily brief"
    assert [item.findtext("link") for item in blog_feed.findall("./channel/item")] == [
        f"{SITE_URL}/blog/2026-07-27/"
    ]


def test_a_data_only_rebuild_writes_no_blog(tmp_path):
    """No feed output means no site build, so no pages and no blog URLs listed."""
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(27), snapshot_dir)
    output = tmp_path / "data" / "radar.json"

    rebuild_dashboard(snapshot_dir, output)

    assert not (tmp_path / "data" / "blog").exists()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [
        node.text
        for node in ET.parse(output.parent / "sitemap.xml").getroot().findall("sm:url/sm:loc", ns)
    ]
    assert not [url for url in urls if "/blog/" in url]
