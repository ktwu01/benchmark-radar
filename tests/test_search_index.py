from pathlib import Path
from subprocess import run

ROOT = Path(__file__).parent.parent


def test_search_index_matches_archive_filtering():
    run(
        ["node", "tests/search_index_parity_harness.mjs"],
        check=True,
        cwd=ROOT,
        timeout=30,
    )
