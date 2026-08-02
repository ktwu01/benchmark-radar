import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from benchmark_radar import cli
from benchmark_radar.models import ProducerHealth, RadarItem, RadarRun
from benchmark_radar.pipeline import SOURCE_FETCHERS
from benchmark_radar.snapshots import write_snapshot


def _config_path(tmp_path: Path) -> Path:
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 300,
            "report_limit": 300,
            "issue_item_limit": 40,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {
            "arxiv": {"enabled": True, "required": True},
            "github": {"enabled": True, "required": True},
            "huggingface": {"enabled": True, "required": True},
        },
    }
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _real_snapshot(tmp_path: Path, date: datetime) -> None:
    run = RadarRun(
        generated_at=date,
        since=date - timedelta(hours=48),
        items=[],
        health=[],
    )
    write_snapshot(run, tmp_path / "snapshots")


def test_simulate_history_skips_days_with_no_reachable_records(monkeypatch, tmp_path):
    # Regression: GitHub/HF search APIs are recency-sorted with no per-day
    # cursor, so a single broad fetch thins out fast going further back. A
    # naive implementation wrote every candidate day, including empty ones,
    # which misrepresented history as "confirmed nothing happened" rather
    # than "not reached" (issue #35).
    recent = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="A benchmark repository for evaluation",
        url="https://github.com/org/repo",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        summary="Benchmark suite for language model evaluation.",
    )
    monkeypatch.setitem(SOURCE_FETCHERS, "github", lambda config, since, limit: [recent])
    monkeypatch.setitem(SOURCE_FETCHERS, "huggingface", lambda config, since, limit: [])

    _real_snapshot(tmp_path, datetime(2026, 7, 30, tzinfo=UTC))
    config_path = _config_path(tmp_path)
    dashboard_output = tmp_path / "radar.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "simulate-history",
            "--config",
            str(config_path),
            "--snapshot-dir",
            str(tmp_path / "snapshots"),
            "--dashboard-output",
            str(dashboard_output),
            "--target-count",
            "5",
        ],
    )

    cli.main()

    snapshot_dir = tmp_path / "snapshots"
    written = sorted(p.name for p in snapshot_dir.glob("*.json"))
    # 2026-07-30 is the real snapshot; only the day the fake fetcher actually
    # returned a record for (2026-07-29) should be added, not the other three
    # empty candidate days between it and the target count.
    assert written == ["2026-07-29.json", "2026-07-30.json"]

    dashboard = json.loads(dashboard_output.read_text(encoding="utf-8"))
    assert dashboard["snapshot_count"] == 2


def test_simulate_history_marks_written_snapshots_as_simulated(monkeypatch, tmp_path):
    recent = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="A benchmark repository for evaluation",
        url="https://github.com/org/repo",
        published_at=datetime(2026, 7, 29, tzinfo=UTC),
        summary="Benchmark suite for language model evaluation.",
    )
    monkeypatch.setitem(SOURCE_FETCHERS, "github", lambda config, since, limit: [recent])
    monkeypatch.setitem(SOURCE_FETCHERS, "huggingface", lambda config, since, limit: [])

    _real_snapshot(tmp_path, datetime(2026, 7, 30, tzinfo=UTC))
    config_path = _config_path(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "simulate-history",
            "--config",
            str(config_path),
            "--snapshot-dir",
            str(tmp_path / "snapshots"),
            "--dashboard-output",
            str(tmp_path / "radar.json"),
            "--target-count",
            "5",
        ],
    )

    cli.main()

    simulated = json.loads((tmp_path / "snapshots" / "2026-07-29.json").read_text(encoding="utf-8"))
    assert simulated["selection"]["simulated"] is True


def test_actions_warn_after_repeated_optional_source_failures(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    run = RadarRun(
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
        since=datetime(2026, 7, 31, tzinfo=UTC),
        items=[],
        health=[],
        producer_health=[
            ProducerHealth(
                producer="fixture-producer",
                source="Hacker News",
                ok=False,
                error="HTTP 503",
            )
        ],
        discovery_state={"source_failure_streaks": {"Hacker News": 3}},
    )
    config = {
        "radar": {"optional_source_failure_warning_runs": 3},
        "sources": {},
    }

    cli._emit_persistent_source_warnings(run, config)

    assert capsys.readouterr().out == (
        "::warning title=Persistent optional source failure::"
        "Hacker News has failed for 3 consecutive runs\n"
    )
