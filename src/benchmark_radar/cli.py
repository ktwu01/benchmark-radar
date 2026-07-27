from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .pipeline import run_pipeline
from .report import render_markdown
from .snapshots import rebuild_dashboard, write_snapshot


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a daily AI benchmark and data radar.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "rebuild"),
        default="run",
        help="Collect a daily run or rebuild dashboard data from saved snapshots.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--output", type=Path, default=Path("out/report.md"))
    parser.add_argument("--json-output", type=Path, default=Path("out/items.json"))
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--dashboard-output", type=Path, default=Path("site/data/radar.json"))
    args = parser.parse_args()

    if args.command == "rebuild":
        data = rebuild_dashboard(args.snapshot_dir, args.dashboard_output)
        print(f"Rebuilt {args.dashboard_output} from {data['snapshot_count']} daily snapshots")
        return

    config = load_config(args.config)
    run = run_pipeline(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    dashboard_url = config.get("publish", {}).get("dashboard_url")
    args.output.write_text(
        render_markdown(run, dashboard_url=dashboard_url),
        encoding="utf-8",
    )
    args.json_output.write_text(
        json.dumps(
            {
                "generated_at": run.generated_at.isoformat(),
                "since": run.since.isoformat(),
                "items": [item.to_dict() for item in run.items],
                "health": [
                    {
                        "source": health.source,
                        "ok": health.ok,
                        "item_count": health.item_count,
                        "error": health.error,
                    }
                    for health in run.health
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_path = write_snapshot(run, args.snapshot_dir)
    dashboard = rebuild_dashboard(args.snapshot_dir, args.dashboard_output)
    print(
        f"Wrote {len(run.items)} items, snapshot {snapshot_path}, and dashboard data "
        f"for {dashboard['snapshot_count']} days"
    )


if __name__ == "__main__":
    main()
