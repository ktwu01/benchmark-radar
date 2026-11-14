"""Runs tests/share_queue_harness.mjs (issue #1162)."""

import shutil
import subprocess

import pytest


def test_share_queue_records_only_real_posts_and_round_trips_the_log():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "tests/share_queue_harness.mjs"], capture_output=True, text=True, check=True
    )
    assert "share queue harness ok" in result.stdout
