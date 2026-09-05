import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from benchmark_radar import cli
from benchmark_radar.briefing import GeneratedBriefing
from benchmark_radar.models import ProducerHealth, RadarItem, RadarRun
from benchmark_radar.pipeline import SOURCE_FETCHERS
from benchmark_radar.snapshots import write_snapshot


@pytest.fixture(autouse=True)
def _isolate_openai_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BRIEFING_REQUIRED", raising=False)
    monkeypatch.delenv("OPENAI_QUESTIONS", raising=False)
    monkeypatch.delenv("OPENAI_QUESTIONS_REQUIRED", raising=False)


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


@pytest.mark.parametrize(
    ("dashboard_url", "expected"),
    [
        ("https://benchmark-radar.org/", "https://benchmark-radar.org/leaderboard/"),
        (
            "https://example.test/benchmark-radar",
            "https://example.test/benchmark-radar/leaderboard/",
        ),
        (None, None),
    ],
)
def test_leaderboard_url_joins_root_and_subpath_deployments(dashboard_url, expected):
    assert cli._leaderboard_url(dashboard_url) == expected


def test_default_dashboard_build_also_publishes_the_feed(monkeypatch, tmp_path, site_shell):
    _real_snapshot(tmp_path, datetime(2026, 7, 30, tzinfo=UTC))
    site_shell(tmp_path / "site")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "rebuild",
            "--snapshot-dir",
            str(tmp_path / "snapshots"),
        ],
    )

    cli.main()

    assert (tmp_path / "site" / "data" / "radar.json").exists()
    assert (tmp_path / "site" / "feed.xml").exists()
    assert (tmp_path / "site" / "sitemap.xml").exists()
    assert not (tmp_path / "site" / "data" / "sitemap.xml").exists()


def test_custom_dashboard_does_not_overwrite_the_default_feed(monkeypatch, tmp_path):
    _real_snapshot(tmp_path, datetime(2026, 7, 30, tzinfo=UTC))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "rebuild",
            "--snapshot-dir",
            str(tmp_path / "snapshots"),
            "--dashboard-output",
            str(tmp_path / "custom-radar.json"),
        ],
    )

    cli.main()

    assert (tmp_path / "custom-radar.json").exists()
    assert not (tmp_path / "site" / "feed.xml").exists()


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


def test_items_json_keeps_the_merged_day_evidence_on_a_same_day_rerun(monkeypatch, tmp_path):
    """Issue #88: the social insight reads out/items.json, so a same-day rerun
    must not replace the day's evidence with the latest pass alone. The merged
    union keeps both passes' items (issue #104 identity rule)."""
    first = RadarItem(
        source="GitHub",
        source_id="org/repo",
        title="First benchmark",
        url="https://github.com/org/repo",
        published_at=datetime.now(UTC),
        summary="Benchmark suite for language model evaluation.",
    )
    second = RadarItem(
        source="GitHub",
        source_id="org/repo-2",
        title="Second benchmark",
        url="https://github.com/org/repo-2",
        published_at=datetime.now(UTC),
        summary="Benchmark suite for language model evaluation.",
    )
    monkeypatch.setitem(SOURCE_FETCHERS, "github", lambda config, since, limit: [first])
    monkeypatch.setitem(SOURCE_FETCHERS, "arxiv", lambda config, since, limit: [first])
    monkeypatch.setitem(SOURCE_FETCHERS, "huggingface", lambda config, since, limit: [first])
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()
    monkeypatch.setitem(SOURCE_FETCHERS, "github", lambda config, since, limit: [second])
    monkeypatch.setitem(SOURCE_FETCHERS, "arxiv", lambda config, since, limit: [second])
    monkeypatch.setitem(SOURCE_FETCHERS, "huggingface", lambda config, since, limit: [second])
    cli.main()

    payload = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    titles = {item["title"] for item in payload["evidence_items"]}
    assert {"First benchmark", "Second benchmark"} <= titles


def test_a_briefing_is_written_without_any_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["briefing"]["bullets"]
    assert stored["briefing"]["generator"] == "deterministic-fallback"


def test_cli_persists_real_gpt_briefing_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))
    monkeypatch.setattr(
        cli,
        "generate_daily_briefing",
        lambda *args, **kwargs: GeneratedBriefing(
            bullets=["A real GPT synthesis. Evidence: E001."],
            metadata={
                "generator": "openai-responses",
                "model": "gpt-5.6",
                "response_id": "resp_real",
                "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
                "input": {"evidence_items": 30},
                "citations": [],
            },
        ),
    )

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["briefing"]["generator"] == "openai-responses"
    assert stored["briefing"]["response_id"] == "resp_real"
    assert stored["briefing"]["usage"]["total_tokens"] == 8200


def test_questions_are_skipped_and_marked_disabled_without_the_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["questions"]["status"] == "disabled"
    assert "OPENAI_QUESTIONS" in stored["questions"]["reason"]


def test_daily_radar_yml_enables_and_requires_questions_in_production():
    """Issue #159: production ran Q&A-eligible days with no Q&A because the
    workflow set OPENAI_API_KEY and OPENAI_BRIEFING_REQUIRED but never set
    OPENAI_QUESTIONS, so the CLI skipped question generation by design."""
    workflow_path = Path(".github/workflows/daily-radar.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    collect_step = next(
        step
        for step in workflow["jobs"]["build-report"]["steps"]
        if step.get("name") == "Collect evidence and public attention"
    )
    env = collect_step["env"]
    assert str(env.get("OPENAI_QUESTIONS")).lower() == "true"
    assert str(env.get("OPENAI_QUESTIONS_REQUIRED")).lower() == "true"


def test_daily_radar_runs_after_the_arxiv_rss_bulletin():
    """Issue #379: a 01:00 UTC run could precede arXiv's 04:00 UTC feed."""
    workflow_path = Path(".github/workflows/daily-radar.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))

    schedules = trigger["schedule"]
    assert len(schedules) == 1
    minute, hour, *_ = schedules[0]["cron"].split()
    assert minute == "0"
    assert int(hour) >= 5


def test_pages_rebuilds_when_any_package_module_changes():
    """Dashboard output depends on transitive package imports, not snapshots.py alone."""
    workflow_path = Path(".github/workflows/pages.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    # PyYAML's YAML 1.1 loader parses the GitHub Actions `on` key as True.
    trigger = workflow.get("on", workflow.get(True))
    paths = next(iter(trigger.values()))["paths"]
    assert "src/benchmark_radar/**" in paths


def test_pages_custom_domain_stays_on_the_actions_artifact():
    """A root CNAME switches Pages toward a legacy main:/ deployment, but the
    only complete website artifact is the site/ directory built by Actions."""
    assert not Path("CNAME").exists()

    workflow = yaml.safe_load(Path(".github/workflows/pages.yml").read_text(encoding="utf-8"))
    build_steps = workflow["jobs"]["build"]["steps"]
    upload = next(
        step
        for step in build_steps
        if step.get("uses", "").startswith("actions/upload-pages-artifact@")
    )
    assert upload["with"]["path"] == "site/"


def test_daily_radar_persists_only_a_fresh_target_day_snapshot():
    """A queued run must not overlay its full, potentially stale history."""
    workflow_path = Path(".github/workflows/daily-radar.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    build_steps = workflow["jobs"]["build-report"]["steps"]
    checkout = next(
        step for step in build_steps if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["ref"] == "main"
    assert any(step.get("name") == "Isolate the target-day snapshot" for step in build_steps)
    persist_script = next(
        step["run"]
        for step in workflow["jobs"]["persist-snapshot"]["steps"]
        if step.get("name") == "Persist UTC snapshot"
    )
    assert "snapshot-date.txt" in persist_script
    assert "snapshot-${snapshot_date}.json" in persist_script
    assert "Refusing to replace a newer" in persist_script
    assert "generated/data/snapshots/*.json" not in persist_script


def test_daily_radar_yml_enables_chinese_rendering_in_production():
    """Issue #231: production must ask for the zh rendering, or the flags would
    exist but never be set and the Chinese dashboard would always show English."""
    workflow_path = Path(".github/workflows/daily-radar.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    collect_step = next(
        step
        for step in workflow["jobs"]["build-report"]["steps"]
        if step.get("name") == "Collect evidence and public attention"
    )
    env = collect_step["env"]
    assert str(env.get("OPENAI_BRIEFING_ZH")).lower() == "true"
    assert str(env.get("OPENAI_QUESTIONS_ZH")).lower() == "true"


def test_zh_flags_reach_the_briefing_and_questions_generators(monkeypatch, tmp_path):
    """The env flags are read once and passed through as translate_zh so the
    generators own the translation call and its failure handling."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_BRIEFING_ZH", "true")
    monkeypatch.setenv("OPENAI_QUESTIONS", "true")
    monkeypatch.setenv("OPENAI_QUESTIONS_ZH", "true")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))
    captured = {}

    def fake_briefing(*args, **kwargs):
        captured["briefing"] = kwargs.get("translate_zh")
        return GeneratedBriefing(
            bullets=["A real GPT synthesis. Evidence: E001."],
            metadata={
                "generator": "openai-responses",
                "model": "gpt-5.6",
                "response_id": "resp_real",
                "usage": {"input_tokens": 8000, "output_tokens": 200, "total_tokens": 8200},
                "input": {"evidence_items": 30},
                "citations": [],
            },
        )

    def fake_questions(*args, **kwargs):
        captured["questions"] = kwargs.get("translate_zh")
        return {
            "schema_version": 1,
            "date": datetime.now(UTC).date().isoformat(),
            "status": "generated",
            "generator": "openai-responses",
            "model": "gpt-5.6",
            "comparable": False,
            "comparability_note": "no certified window",
            "groups": [],
            "stat_registry": [],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "calls": 3,
            "coverage": {},
        }

    monkeypatch.setattr(cli, "generate_daily_briefing", fake_briefing)
    monkeypatch.setattr(cli, "generate_daily_questions", fake_questions)

    cli.main()

    assert captured == {"briefing": True, "questions": True}


def test_daily_radar_yml_renders_social_material_instead_of_an_issue():
    """Issue #88: the dashboard and site/feed.xml remain the reading surface
    (issue #37), so the daily Issue carries only the social posting checklist.
    The publish-issue job must render out/social.md as the issue body so each
    day gets exactly one checkable posting checklist."""
    workflow_path = Path(".github/workflows/daily-radar.yml")
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    publish_issue = workflow["jobs"].get("publish-issue")
    assert publish_issue is not None
    step = next(
        step
        for step in publish_issue["steps"]
        if step.get("name") == "Create idempotent daily social-checklist issue"
    )
    assert "--social-output generated/out/body.md" in step["run"]
    assert "gh issue create --title" in step["run"]
    assert "--label automated --label traction" in step["run"]
    assert "--add-label automated --add-label traction --remove-label daily-radar" in step["run"]
    assert "--label daily-radar" not in step["run"]
    social_step = next(
        step
        for step in workflow["jobs"]["build-report"]["steps"]
        if step.get("name") == "Render daily social post material"
    )
    assert "--social-output out/social.md" in social_step["run"]


def test_questions_required_raises_without_a_flag_or_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_QUESTIONS_REQUIRED", "true")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))

    with pytest.raises(RuntimeError, match="OPENAI_QUESTIONS_REQUIRED"):
        cli.main()


def test_questions_required_raises_when_generation_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_QUESTIONS", "true")
    monkeypatch.setenv("OPENAI_QUESTIONS_REQUIRED", "true")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))
    monkeypatch.setattr(
        cli,
        "generate_daily_questions",
        lambda *args, **kwargs: (_ for _ in ()).throw(cli.BriefingError("boom")),
    )

    with pytest.raises(RuntimeError, match="required daily questions failed"):
        cli.main()


def test_questions_best_effort_persists_error_status_without_failing_the_run(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_QUESTIONS", "true")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))
    monkeypatch.setattr(
        cli,
        "generate_daily_questions",
        lambda *args, **kwargs: (_ for _ in ()).throw(cli.BriefingError("boom")),
    )

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["questions"]["status"] == "error"
    assert "boom" in stored["questions"]["reason"]


def test_questions_generated_status_is_persisted_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_QUESTIONS", "true")
    _stub_sources(monkeypatch, datetime.now(UTC))
    monkeypatch.setattr("sys.argv", _briefing_argv(tmp_path))
    monkeypatch.setattr(
        cli,
        "generate_daily_questions",
        lambda *args, **kwargs: {
            "schema_version": 1,
            "date": datetime.now(UTC).date().isoformat(),
            "status": "generated",
            "generator": "openai-responses",
            "model": "gpt-5.6",
            "comparable": False,
            "comparability_note": "no certified window",
            "groups": [],
            "stat_registry": [],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "calls": 3,
            "coverage": {},
        },
    )

    cli.main()

    stored = json.loads(next((tmp_path / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["questions"]["status"] == "generated"
    assert stored["questions"]["calls"] == 3


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
