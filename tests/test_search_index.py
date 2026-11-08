import sys
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory

ROOT = Path(__file__).parent.parent


def test_search_index_matches_archive_filtering():
    with TemporaryDirectory() as directory:
        dashboard = Path(directory) / "dashboard.json"
        index = Path(directory) / "search-index.json"
        run(
            ["node", "tests/search_index_parity_harness.mjs", "--write-dashboard", str(dashboard)],
            check=True,
            cwd=ROOT,
            timeout=30,
        )
        run(
            [sys.executable, "tests/generate_search_index.py", str(dashboard), str(index)],
            check=True,
            cwd=ROOT,
            timeout=30,
        )
        run(
            ["node", "tests/search_index_parity_harness.mjs", "--index", str(index)],
            check=True,
            cwd=ROOT,
            timeout=30,
        )
