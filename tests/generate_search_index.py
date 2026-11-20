from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmark_radar.search_index import write_search_index
from benchmark_radar.snapshots import dashboard_search_index


def main() -> None:
    dashboard_path, output_dir = map(Path, sys.argv[1:3])
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    write_search_index(
        output_dir / "radar-search.json",
        dashboard,
        dashboard_search_index(dashboard)["observations"],
    )


if __name__ == "__main__":
    main()
