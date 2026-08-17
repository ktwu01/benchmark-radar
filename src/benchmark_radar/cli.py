from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from .authors import contacts_csv
from .authors import survey as author_survey
from .briefing import BriefingError, current_day_snapshot, daily_report_run, generate_daily_briefing
from .export import DEFAULT_TABLE_LIMIT, write_exports
from .findings import daily_findings
from .http import RequestError
from .kw_bench_store import STORE_FILENAME as KW_BENCH_STORE_FILENAME
from .kw_bench_tracks import DEFAULT_BATCH_SIZE
from .kw_bench_tracks import backfill as backfill_classifications
from .pipeline import _failure_streak_key, run_pipeline, simulate_backfill
from .questions import QA_SCHEMA_VERSION, generate_daily_questions
from .report import render_markdown
from .snapshots import (
    load_snapshots,
    migrate_snapshot_history,
    rebuild_dashboard,
    rescore_snapshot_history,
    write_snapshot,
)
from .social import (
    build_insight_sentence,
    collect_git_changes,
    load_channels,
    load_post_sample,
    merge_checked,
    render_social_section,
    summarize_repo_changes,
)

DEFAULT_DASHBOARD_OUTPUT = Path("site/data/radar.json")
DEFAULT_FEED_OUTPUT = Path("site/feed.xml")


def _emit_persistent_source_warnings(run, config: dict) -> None:
    """Raise visible Actions warnings for optional sources that keep failing."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    threshold = max(
        1,
        int(config.get("radar", {}).get("optional_source_failure_warning_runs", 3)),
    )
    required = {
        name
        for name, source_config in config.get("sources", {}).items()
        if source_config.get("enabled", True) and source_config.get("required", False)
    }
    streaks = run.discovery_state.get("source_failure_streaks") or {}

    def emit(health, *, layer: str, required_source: bool = False) -> None:
        streak_key = _failure_streak_key(layer, health)
        streak = int(streaks.get(streak_key, 0) or 0)
        if not health.ok and not required_source and streak >= threshold:
            source = health.source.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(
                "::warning title=Persistent optional source failure::"
                f"{source} has failed for {streak} consecutive runs"
            )

    for health in run.health:
        emit(health, layer="evidence", required_source=health.source in required)
    for health in run.attention_ingest_health:
        emit(health, layer="attention")
    for health in run.producer_health:
        emit(health, layer="producer")


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a daily AI benchmark and data radar.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=(
            "run",
            "rebuild",
            "backfill",
            "migrate",
            "rescore",
            "simulate-history",
            "export",
            "classify",
            "authors",
            "social",
        ),
        default="run",
        help=(
            "Collect a daily run, rebuild/backfill cumulative data from saved snapshots, "
            "migrate snapshot schemas, rescore stored taxonomy categories against the "
            "current config, simulate missing historical snapshots, export the "
            "Model Card Adoption Rank as standalone citable files, classify canonical "
            "benchmark tracks against the KW-Bench L0-L5 capability rubric, survey "
            "the public profiles of authors behind popular benchmark repositories, "
            "or render the daily social post section from the day's evidence and git history."
        ),
    )
    parser.add_argument(
        "--author-output",
        type=Path,
        default=Path("out/benchmark-authors.json"),
        help="Where `authors` writes its shareable survey of public profiles.",
    )
    parser.add_argument(
        "--author-contacts",
        type=Path,
        default=Path("out/benchmark-author-contacts.csv"),
        help=(
            "Where `authors --author-emails` writes harvested commit emails. Kept "
            "out of the survey and untracked: publishing addresses people did not "
            "knowingly share invites spam regardless of intent."
        ),
    )
    parser.add_argument("--author-repo-limit", type=int, default=40)
    parser.add_argument("--author-contributors", type=int, default=20)
    parser.add_argument(
        "--author-emails",
        action="store_true",
        help="Also collect commit emails into the untracked contacts file (issue #156).",
    )
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--output", type=Path, default=Path("out/report.md"))
    parser.add_argument("--json-output", type=Path, default=Path("out/items.json"))
    parser.add_argument(
        "--social-output",
        type=Path,
        default=Path("out/social.md"),
        help="social only: where the rendered social post section is written.",
    )
    parser.add_argument(
        "--items",
        type=Path,
        default=Path("out/items.json"),
        help="social only: the day's evidence records (out/items.json).",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="social only: repository whose git history feeds the repo-change sentence.",
    )
    parser.add_argument(
        "--channels",
        type=Path,
        default=Path("config/social.yml"),
        help="social only: channel checklist source (config/social.yml).",
    )
    parser.add_argument(
        "--existing-body",
        type=Path,
        default=None,
        help=(
            "social only: body of the already-created issue for this day, so "
            "channels already ticked stay ticked on re-renders."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="social only: ISO start of the git window (defaults to 24 hours ago).",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="social only: ISO end of the git window (defaults to now).",
    )
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--dashboard-output", type=Path, default=DEFAULT_DASHBOARD_OUTPUT)
    parser.add_argument(
        "--feed-output",
        type=Path,
        default=None,
        help=(
            "Public RSS feed generated from the daily snapshot history. Defaults to "
            "site/feed.xml when the default dashboard output is used; custom dashboard "
            "builds publish no feed unless this option is passed."
        ),
    )
    parser.add_argument(
        "--model-cards",
        type=Path,
        default=Path("data/model_cards.yml"),
        help=(
            "Curated model card registry powering the Model Card Adoption Rank "
            "(issue #83). A missing file omits the leaderboard; an invalid one "
            "fails the build rather than publishing a stale ranking."
        ),
    )
    parser.add_argument(
        "--benchmark-scores",
        type=Path,
        default=None,
        help=(
            "Curated score observations powering the saturation reading (issue "
            "#91). Every row cites a source_id that must be a document in the "
            "registry beside it, so the two files are a matched pair: this "
            "defaults to data/benchmark_scores.yml only when --model-cards is "
            "also the default. Pass it explicitly to pair scores with a custom "
            "registry; omit it there for an adoption-only rebuild."
        ),
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("site/data"),
        help=(
            "export only: directory for the standalone leaderboard artifacts "
            "(issue #88). Defaults inside the published site so the JSON, CSV, "
            "Markdown table, and Shields badge endpoint are fetchable at a "
            "stable URL rather than only reachable from a release asset."
        ),
    )
    parser.add_argument(
        "--export-table-limit",
        type=int,
        default=DEFAULT_TABLE_LIMIT,
        help=(
            "export only: rows in the paste-ready Markdown table. 0 emits every "
            "tracked benchmark; the truncation is always stated in the output."
        ),
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=30,
        help=(
            "simulate-history only: total snapshot files to reach (issue #35's "
            "30-replay coverage), counting real snapshots already on disk."
        ),
    )
    parser.add_argument(
        "--kw-bench-store",
        type=Path,
        default=Path("data") / KW_BENCH_STORE_FILENAME,
        help=(
            "KW-Bench L0-L5 classification layer (issue #153). Append-only JSONL "
            "keyed by canonical artifact and track. Read by every rebuild to "
            "publish the shadow capability layer; written by `classify`."
        ),
    )
    parser.add_argument(
        "--kw-bench-batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "classify only: tracks per committed batch. Work is durable per "
            "batch, so an interrupted run keeps everything already written."
        ),
    )
    parser.add_argument(
        "--kw-bench-limit",
        type=int,
        default=None,
        help=(
            "classify only: stop after this many tracks that still need work. "
            "Bounds a first backfill pass; the next run picks up where it "
            "stopped rather than re-selecting the same prefix."
        ),
    )
    parser.add_argument(
        "--kw-bench-refresh-after",
        default=None,
        help=(
            "classify only: re-extract tracks classified before this ISO "
            "timestamp. An upstream README edit that leaves a track's metadata "
            "unchanged is invisible to the cache by design, since detecting it "
            "means fetching the source; this is how those are picked up."
        ),
    )
    args = parser.parse_args()
    feed_output = args.feed_output
    if feed_output is None and args.dashboard_output == DEFAULT_DASHBOARD_OUTPUT:
        feed_output = DEFAULT_FEED_OUTPUT

    if args.command == "authors":
        result = author_survey(
            load_snapshots(args.snapshot_dir),
            repo_limit=args.author_repo_limit,
            per_repo=args.author_contributors,
            include_emails=args.author_emails,
        )
        report = result["report"]
        args.author_output.parent.mkdir(parents=True, exist_ok=True)
        args.author_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Surveyed {report['repository_count']} popular repositories and "
            f"{report['author_count']} contributors"
        )
        print(f"  {report['data_author_count']} describe data work in their own profile")
        print(f"  report: {args.author_output}")
        if result["contacts"]:
            # Untracked by design: a committed list of harvested addresses is a
            # spam vector no matter why it was gathered.
            args.author_contacts.parent.mkdir(parents=True, exist_ok=True)
            args.author_contacts.write_text(contacts_csv(result["contacts"]), encoding="utf-8")
            print(f"  contacts: {args.author_contacts} (gitignored, {len(result['contacts'])})")
        for failure in report["failures"][:5]:
            print(f"  ::warning:: {failure}")
        return

    if args.command == "classify":
        summary = backfill_classifications(
            load_snapshots(args.snapshot_dir),
            store_path=args.kw_bench_store,
            classified_at=datetime.now(UTC).isoformat(),
            batch_size=args.kw_bench_batch_size,
            limit=args.kw_bench_limit,
            refresh_before=args.kw_bench_refresh_after,
        )
        dashboard = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            feed_output=feed_output,
            registry_path=args.model_cards,
            scores_path=args.benchmark_scores,
            kw_bench_store_path=args.kw_bench_store,
        )
        report = dashboard["kw_bench"]["coverage"]
        print(
            f"Derived {summary['tracks_derived']} canonical tracks against KW-Bench "
            f"{summary['kw_bench_version']} (extractor: {summary['extractor']})"
        )
        print(
            f"  classified {summary['classified']}, reused {summary['reused_from_cache']} "
            f"from cache, {summary['superseded']} superseded"
        )
        for level, count in report["level_counts"].items():
            print(f"  {level:14s} {count}")
        rate = report["classified_rate"]
        print(
            "  coverage      "
            + (f"{rate:.1%} of tracks carry a level" if rate is not None else "no tracks yet")
        )
        if report["awaiting_human_review"]:
            print(
                f"  {report['awaiting_human_review']} record(s) await human review "
                "and are withheld from published counts"
            )
        return

    if args.command in {"rebuild", "backfill"}:
        data = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            feed_output=feed_output,
            registry_path=args.model_cards,
            scores_path=args.benchmark_scores,
            kw_bench_store_path=args.kw_bench_store,
        )
        action = "Backfilled" if args.command == "backfill" else "Rebuilt"
        print(f"{action} {args.dashboard_output} from {data['snapshot_count']} daily snapshots")
        return

    if args.command == "social":
        # Config-independent: dispatched before load_config so the command
        # works against explicit --items/--repo/--channels paths outside the
        # repository without needing an unrelated radar config.yml.
        items: list[dict] = []
        if args.items.exists():
            payload = json.loads(args.items.read_text(encoding="utf-8"))
            items = payload.get("evidence_items") or []
        now = datetime.now(UTC)
        until = args.until or now.isoformat()
        since = args.since or (now - timedelta(hours=24)).isoformat()
        changes = collect_git_changes(args.repo, since, until)
        repo_sentence, commit_subjects = summarize_repo_changes(changes)
        section = render_social_section(
            build_insight_sentence(items),
            repo_sentence,
            commit_subjects,
            load_channels(args.channels, daily_only=False),
            post_sample=load_post_sample(args.channels),
            today=now.date(),
        )
        if args.existing_body and args.existing_body.exists():
            section = merge_checked(section, args.existing_body.read_text(encoding="utf-8"))
        args.social_output.parent.mkdir(parents=True, exist_ok=True)
        args.social_output.write_text(section + "\n", encoding="utf-8")
        print(
            f"Wrote {args.social_output} from {len(items)} evidence items "
            f"and {len(changes)} commits"
        )
        return

    config = load_config(args.config)

    if args.command == "export":
        dashboard_url = config.get("publish", {}).get("dashboard_url")
        # `?view=leaderboard` rather than the dashboard root: a reader arriving
        # from a cited CSV is looking for the ranking, and the root opens on the
        # daily Today list instead.
        source_url = f"{dashboard_url}?view=leaderboard" if dashboard_url else None
        written = write_exports(
            args.export_dir,
            registry_path=args.model_cards,
            # 0 means "no limit" on a command line, where passing None is not
            # expressible. Negative values collapse to the same intent rather
            # than silently producing an empty table through a slice.
            table_limit=(None if args.export_table_limit <= 0 else args.export_table_limit),
            source_url=source_url,
        )
        for name in sorted(written):
            print(f"Wrote {written[name]}")
        return

    if args.command == "simulate-history":
        existing = load_snapshots(args.snapshot_dir)
        existing_dates = {snapshot["date"] for snapshot in existing}
        missing = max(0, args.target_count - len(existing))
        earliest = (
            datetime.fromisoformat(min(existing_dates)).replace(tzinfo=UTC)
            if existing_dates
            else datetime.now(UTC)
        )
        dates = []
        for day_offset in range(missing, 0, -1):
            candidate = earliest - timedelta(days=day_offset)
            if candidate.date().isoformat() not in existing_dates:
                dates.append(candidate)
        if not dates:
            print(f"Already have {len(existing)} snapshots, target is {args.target_count}")
            return
        runs = simulate_backfill(
            config,
            dates,
            previous_snapshot=existing[0] if existing else None,
        )
        # Every connector here is recency-sorted with no per-day cursor
        # (GitHub's search API, HF Hub's `sort=lastModified`), so one broad
        # fetch structurally favors the days nearest today and thins out fast
        # going further back. A day with nothing after that thinning point is
        # not "confirmed empty," it is "not reached" -- publishing it as a
        # zero-item snapshot would misrepresent history rather than admit the
        # gap, so it is skipped and reported rather than written.
        written = [run for run in runs if run.items]
        skipped = len(runs) - len(written)
        for run in written:
            write_snapshot(run, args.snapshot_dir)
        dashboard = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            feed_output=feed_output,
            registry_path=args.model_cards,
            scores_path=args.benchmark_scores,
            kw_bench_store_path=args.kw_bench_store,
        )
        print(
            f"Simulated {len(written)} historical snapshots with coverage "
            f"({skipped} of {len(runs)} candidate days had no reachable records and were "
            "skipped rather than published empty; arXiv excluded from simulation, see issue "
            f"#35 known limitations); {dashboard['snapshot_count']} total daily snapshots"
        )
        return
    if args.command == "rescore":
        summary = rescore_snapshot_history(config, args.snapshot_dir)
        dashboard = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            feed_output=feed_output,
            registry_path=args.model_cards,
            scores_path=args.benchmark_scores,
            kw_bench_store_path=args.kw_bench_store,
        )
        print(
            f"Rescored {summary['snapshots']} snapshots against taxonomy "
            f"{summary['taxonomy_version']}; "
            f"{summary['records_changed']} records changed category"
        )
        for category in sorted({*summary["before"], *summary["after"]}):
            was = summary["before"].get(category, 0)
            now_count = summary["after"].get(category, 0)
            marker = "" if was == now_count else f"  <- was {was}"
            print(f"  {category:14s} {now_count}{marker}")
        if summary["schema_migrated"]:
            print(
                f"Note: {len(summary['schema_migrated'])} snapshot(s) were also upgraded "
                f"from an older schema: {', '.join(summary['schema_migrated'])}"
            )
        print(f"Rebuilt {args.dashboard_output} from {dashboard['snapshot_count']} snapshots")
        return
    if args.command == "migrate":
        snapshots = migrate_snapshot_history(config, args.snapshot_dir)
        dashboard = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            feed_output=feed_output,
            registry_path=args.model_cards,
            scores_path=args.benchmark_scores,
            kw_bench_store_path=args.kw_bench_store,
        )
        print(
            f"Migrated {len(snapshots)} snapshots to schema {dashboard['schema_version']} "
            f"and rebuilt {args.dashboard_output}"
        )
        return

    snapshots = load_snapshots(args.snapshot_dir)
    run = run_pipeline(
        config,
        previous_snapshot=snapshots[-1] if snapshots else None,
    )
    _emit_persistent_source_warnings(run, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    dashboard_url = config.get("publish", {}).get("dashboard_url")
    issue_item_limit = config.get("radar", {}).get("issue_item_limit")
    daily_snapshot = current_day_snapshot(snapshots, run)
    report_run = daily_report_run(daily_snapshot, run)
    today = run.generated_at.astimezone(UTC).date().isoformat()
    history = [*(s for s in snapshots if s["date"] != today), daily_snapshot]
    deterministic_findings = daily_findings(history, config)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    briefing_required = os.getenv("OPENAI_BRIEFING_REQUIRED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    # Issue #231: optional Simplified Chinese rendering of the day's GPT prose,
    # one extra call each. Each flag is independent of its generation flag, so
    # a run can translate the briefing without translating the Q&A and vice
    # versa. A failed translation never fails the run: the zh fields are absent
    # and the dashboard shows English.
    briefing_zh = os.getenv("OPENAI_BRIEFING_ZH", "").lower() in {"1", "true", "yes"}
    questions_zh = os.getenv("OPENAI_QUESTIONS_ZH", "").lower() in {"1", "true", "yes"}
    daily_briefing = deterministic_findings
    briefing_metadata: dict = {
        "generator": "deterministic-fallback",
        "reason": "OPENAI_API_KEY is not configured",
    }
    if api_key:
        try:
            generated = generate_daily_briefing(
                history,
                daily_snapshot,
                deterministic_findings,
                api_key,
                model=os.getenv("OPENAI_BRIEFING_MODEL", "").strip() or "gpt-5.6",
                translate_zh=briefing_zh,
            )
            daily_briefing = generated.bullets
            briefing_metadata = generated.metadata
        except (BriefingError, RequestError, ValueError) as error:
            if briefing_required:
                raise RuntimeError(f"required OpenAI briefing failed: {error}") from error
            briefing_metadata["reason"] = f"{type(error).__name__}: {error}"
            print(f"::warning title=GPT briefing fell back::{error}")
    elif briefing_required:
        raise RuntimeError("OPENAI_BRIEFING_REQUIRED is true but OPENAI_API_KEY is missing")

    # The daily Q&A is opt-in: it costs one API call per question group. By
    # default a failure here must never cost the run its briefing or its
    # snapshot, but OPENAI_QUESTIONS_REQUIRED lets production demand it the
    # same way OPENAI_BRIEFING_REQUIRED demands the briefing.
    questions_enabled = os.getenv("OPENAI_QUESTIONS", "").lower() in {"1", "true", "yes"}
    questions_required = os.getenv("OPENAI_QUESTIONS_REQUIRED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    daily_questions: dict | None = None
    if questions_enabled and api_key:
        try:
            daily_questions = generate_daily_questions(
                history,
                daily_snapshot,
                deterministic_findings,
                api_key,
                model=os.getenv("OPENAI_BRIEFING_MODEL", "").strip() or "gpt-5.6",
                config=config,
                translate_zh=questions_zh,
            )
        except (BriefingError, RequestError, ValueError) as error:
            if questions_required:
                raise RuntimeError(f"required daily questions failed: {error}") from error
            print(f"::warning title=Daily questions skipped::{error}")
            daily_questions = {
                "schema_version": QA_SCHEMA_VERSION,
                "date": today,
                "status": "error",
                "reason": f"{type(error).__name__}: {error}",
            }
    elif questions_required:
        raise RuntimeError(
            "OPENAI_QUESTIONS_REQUIRED is true but OPENAI_QUESTIONS is not enabled "
            "or OPENAI_API_KEY is missing"
        )
    elif not questions_enabled:
        daily_questions = {
            "schema_version": QA_SCHEMA_VERSION,
            "date": today,
            "status": "disabled",
            "reason": "OPENAI_QUESTIONS is not enabled",
        }
    elif not api_key:
        daily_questions = {
            "schema_version": QA_SCHEMA_VERSION,
            "date": today,
            "status": "disabled",
            "reason": "OPENAI_API_KEY is not configured",
        }

    # Attach before writing so the snapshot, the dashboard payload, and the
    # Markdown report all describe the same briefing.
    run.daily_briefing = daily_briefing
    run.daily_briefing_metadata = briefing_metadata
    run.daily_questions = daily_questions
    args.output.write_text(
        render_markdown(
            report_run,
            dashboard_url=dashboard_url,
            issue_item_limit=int(issue_item_limit) if issue_item_limit else None,
            daily_briefing=daily_briefing,
            daily_briefing_metadata=briefing_metadata,
            daily_questions=daily_questions,
        ),
        encoding="utf-8",
    )
    args.json_output.write_text(
        json.dumps(
            {
                # The report and snapshot describe the merged UTC-day union, not
                # the latest pass alone: a same-day rerun must not replace the
                # day's evidence with a subset (issue #88 social insight reads
                # this file).
                "generated_at": report_run.generated_at.isoformat(),
                "since": report_run.since.isoformat(),
                "evidence_items": [item.to_dict() for item in report_run.items],
                "attention": {
                    "observations": [item.to_dict() for item in report_run.attention],
                },
                "ingest_health": [
                    health.to_dict() for health in [*run.health, *run.attention_ingest_health]
                ],
                "producer_health": [health.to_dict() for health in run.producer_health],
                "selection": report_run.selection,
                # Day-scoped like the evidence above: the briefing describes the
                # whole UTC day and is shared by every pass over it. Omitted
                # when the day has none.
                **(
                    {
                        "briefing": {
                            "date": today,
                            "bullets": daily_briefing,
                            **briefing_metadata,
                        }
                    }
                    if daily_briefing
                    else {}
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_path = write_snapshot(run, args.snapshot_dir)
    dashboard = rebuild_dashboard(
        args.snapshot_dir,
        args.dashboard_output,
        feed_output=feed_output,
        registry_path=args.model_cards,
        scores_path=args.benchmark_scores,
        kw_bench_store_path=args.kw_bench_store,
    )
    print(
        f"Wrote {len(run.items)} items, snapshot {snapshot_path}, and dashboard data "
        f"for {dashboard['snapshot_count']} days"
    )


if __name__ == "__main__":
    main()
