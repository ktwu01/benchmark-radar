"""Today search must distinguish partial candidates from full matches (#863)."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_today_search_reports_partial_candidates_with_the_production_helpers():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run(
        [node, "tests/today_benchmark_search_harness.mjs"],
        check=True,
        timeout=60,
        cwd=Path(__file__).resolve().parents[1],
    )
