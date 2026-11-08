from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmark_radar.snapshots import dashboard_search_index


def main() -> None:
    dashboard_path, index_path = map(Path, sys.argv[1:3])
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    index_path.write_text(
        json.dumps(dashboard_search_index(dashboard)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
