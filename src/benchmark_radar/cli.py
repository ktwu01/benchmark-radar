from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from .export import DEFAULT_TABLE_LIMIT, write_exports
from .pipeline import _failure_streak_key, run_pipeline, simulate_backfill
from .report import render_markdown
from .snapshots import (
    load_snapshots,
    migrate_snapshot_history,
    rebuild_dashboard,
    rescore_snapshot_history,
    write_snapshot,
)


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
        choices=("run", "rebuild", "backfill", "migrate", "rescore", "simulate-history", "export"),
        default="run",
        help=(
            "Collect a daily run, rebuild/backfill cumulative data from saved snapshots, "
            "migrate snapshot schemas, rescore stored taxonomy categories against the "
            "current config, simulate missing historical snapshots, or export the "
            "Model Card Adoption Rank as standalone citable files."
        ),
    )
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--output", type=Path, default=Path("out/report.md"))
    parser.add_argument("--json-output", type=Path, default=Path("out/items.json"))
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--dashboard-output", type=Path, default=Path("site/data/radar.json"))
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
    args = parser.parse_args()

    if args.command in {"rebuild", "backfill"}:
        data = rebuild_dashboard(
            args.snapshot_dir,
            args.dashboard_output,
            registry_path=args.model_cards,
        )
        action = "Backfilled" if args.command == "backfill" else "Rebuilt"
        print(f"{action} {args.dashboard_output} from {data['snapshot_count']} daily snapshots")
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
            registry_path=args.model_cards,
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
            registry_path=args.model_cards,
        )
        print(
            f"Rescored {summary['snapshots']} snapshots against the current taxonomy; "
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
            registry_path=args.model_cards,
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
    args.output.write_text(
        render_markdown(
            run,
            dashboard_url=dashboard_url,
            issue_item_limit=int(issue_item_limit) if issue_item_limit else None,
        ),
        encoding="utf-8",
    )
    args.json_output.write_text(
        json.dumps(
            {
                "generated_at": run.generated_at.isoformat(),
                "since": run.since.isoformat(),
                "evidence_items": [item.to_dict() for item in run.items],
                "attention": {
                    "observations": [item.to_dict() for item in run.attention],
                },
                "ingest_health": [
                    health.to_dict() for health in [*run.health, *run.attention_ingest_health]
                ],
                "producer_health": [health.to_dict() for health in run.producer_health],
                "selection": run.selection,
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
        registry_path=args.model_cards,
    )
    print(
        f"Wrote {len(run.items)} items, snapshot {snapshot_path}, and dashboard data "
        f"for {dashboard['snapshot_count']} days"
    )


if __name__ == "__main__":
    main()
