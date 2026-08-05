import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from benchmark_radar import cli
from benchmark_radar.briefing import BriefingError
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


def test_second_pass_reuses_the_stored_briefing_without_calling_the_api(
    monkeypatch, tmp_path, capsys
):
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    calls = []

    def fake_generate(current, previous, api_key):
        calls.append(api_key)
        return ["The day's only briefing."]

    monkeypatch.setattr("benchmark_radar.cli.generate_daily_briefing", fake_generate)
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()
    cli.main()

    # One UTC day holds exactly one briefing, so the second pass over the same
    # day must not spend another API call or overwrite the stored text.
    assert calls == ["secret"]
    assert "Reusing the briefing already stored" in capsys.readouterr().out
    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["briefing"]["bullets"] == ["The day's only briefing."]


def test_a_later_pass_retries_after_the_briefing_call_failed(monkeypatch, tmp_path):
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    attempts = []

    def flaky_generate(current, previous, api_key):
        attempts.append(api_key)
        if len(attempts) == 1:
            raise BriefingError("upstream refused")
        return ["Recovered on the retry."]

    monkeypatch.setattr("benchmark_radar.cli.generate_daily_briefing", flaky_generate)
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()
    cli.main()

    # The first pass stored nothing, so the day still needs a briefing and the
    # next pass tries again rather than leaving the day permanently blank.
    assert len(attempts) == 2
    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["briefing"]["bullets"] == ["Recovered on the retry."]


def test_a_briefing_stored_for_an_earlier_day_is_not_reused(monkeypatch, tmp_path):
    now = datetime.now(UTC)
    _stub_sources(monkeypatch, now)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    # A snapshot from a previous day that already carries its own briefing.
    stale = RadarRun(
        generated_at=now - timedelta(days=1),
        since=now - timedelta(days=1, hours=48),
        items=[],
        health=[],
        daily_briefing=["Yesterday's summary."],
    )
    write_snapshot(stale, tmp_path / "snapshots")
    generated = []

    def fake_generate(current, previous, api_key):
        generated.append(api_key)
        return ["Today's summary."]

    monkeypatch.setattr("benchmark_radar.cli.generate_daily_briefing", fake_generate)
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()

    # Reuse requires the stored briefing to be dated today, not merely present,
    # so yesterday's text is never published beside today's listings.
    assert generated == ["secret"]
    today = now.date().isoformat()
    stored = json.loads((tmp_path / "snapshots" / f"{today}.json").read_text(encoding="utf-8"))
    assert stored["briefing"] == {"date": today, "bullets": ["Today's summary."]}
