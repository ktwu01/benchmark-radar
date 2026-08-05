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
        discovery_state={
            "source_failure_streaks": {'["producer","fixture-producer","Hacker News"]': 3}
        },
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


def test_actions_escape_remote_source_names(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    source = "safe%name\r\n::error::injected"
    run = RadarRun(
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
        since=datetime(2026, 7, 31, tzinfo=UTC),
        items=[],
        health=[],
        producer_health=[ProducerHealth(producer="fixture-producer", source=source, ok=False)],
        discovery_state={
            "source_failure_streaks": {
                json.dumps(
                    ["producer", "fixture-producer", source],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ): 3
            }
        },
    )

    cli._emit_persistent_source_warnings(run, {"radar": {}, "sources": {}})

    assert capsys.readouterr().out == (
        "::warning title=Persistent optional source failure::"
        "safe%25name%0D%0A::error::injected has failed for 3 consecutive runs\n"
    )


def test_required_discovery_name_does_not_exempt_attention_failure(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    run = RadarRun(
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
        since=datetime(2026, 7, 31, tzinfo=UTC),
        items=[],
        health=[],
        producer_health=[ProducerHealth(producer="fixture-producer", source="github", ok=False)],
        discovery_state={"source_failure_streaks": {'["producer","fixture-producer","github"]': 3}},
    )
    config = {"radar": {}, "sources": {"github": {"required": True}}}

    cli._emit_persistent_source_warnings(run, config)

    assert "github has failed for 3 consecutive runs" in capsys.readouterr().out


def _briefing_argv(tmp_path: Path) -> list[str]:
    return [
        "benchmark-radar",
        "--config",
        str(_config_path(tmp_path)),
        "--snapshot-dir",
        str(tmp_path / "snapshots"),
        "--output",
        str(tmp_path / "report.md"),
        "--json-output",
        str(tmp_path / "items.json"),
        "--dashboard-output",
        str(tmp_path / "radar.json"),
    ]


def _stub_sources(monkeypatch, day: datetime) -> None:
    item = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="A benchmark repository for evaluation",
        url="https://github.com/org/repo",
        published_at=day,
        summary="Benchmark suite for language model evaluation.",
    )
    monkeypatch.setitem(SOURCE_FETCHERS, "github", lambda config, since, limit: [item])
    monkeypatch.setitem(SOURCE_FETCHERS, "arxiv", lambda config, since, limit: [item])
    monkeypatch.setitem(SOURCE_FETCHERS, "huggingface", lambda config, since, limit: [item])


def test_every_pass_over_a_day_derives_the_same_briefing(monkeypatch, tmp_path):
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()
    first = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))[
        "briefing"
    ]
    cli.main()
    second = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))[
        "briefing"
    ]

    # Findings are computed from the corpus, so there is nothing to reuse or
    # retry: every pass over the same day derives the same text. The reuse and
    # retry machinery the LLM path needed is gone with it.
    assert first == second
    assert first["bullets"]


def test_a_briefing_is_written_without_any_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    # The briefing no longer depends on a credential, so a day can never be
    # left blank because a key was missing.
    assert stored["briefing"]["bullets"]


def test_a_thin_day_reports_insufficient_volume_rather_than_a_pattern(monkeypatch, tmp_path):
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    bullets = " ".join(stored["briefing"]["bullets"])
    # One stubbed item is far below the volume a composition claim needs, and a
    # single day has no baseline. Saying so is the correct output: a quota would
    # be an incentive to manufacture significance.
    assert "Insufficient" in bullets or "No material pattern" in bullets
