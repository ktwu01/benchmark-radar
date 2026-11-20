"""The homepage's registry search reads a compact catalog file (#1305)."""

import json
import re
import subprocess
from pathlib import Path

from benchmark_radar.catalog import BENCHMARK_SEARCH_FIELDS, benchmark_search_payload

ROOT = Path(__file__).parent.parent
RANKING = (ROOT / "site/assets/catalog-search.js").read_text(encoding="utf-8")
APP = (ROOT / "site/assets/app.js").read_text(encoding="utf-8")


def test_the_compact_file_keeps_every_field_the_ranking_and_rows_read():
    # A field the ranking reads but the file drops would silently change
    # homepage results, so the list is checked against the code that reads it.
    order = re.search(r"const FIELD_ORDER = \[([^\]]*)\]", RANKING).group(1)
    read = set(re.findall(r'"(\w+)"', order))
    read |= set(re.findall(r"\brecord\.(\w+)", RANKING))
    # Completeness counts fields named in lists, as ["publisher", ...].filter.
    for names in re.findall(r"\[((?:\"\w+\",? ?)+)\]\.filter", RANKING):
        read |= set(re.findall(r'"(\w+)"', names))
    row = APP.split("function benchmarkResultRow(", 1)[1].split("\n}\n", 1)[0]
    read |= set(re.findall(r"\brecord\.(\w+)", row))
    assert read <= set(BENCHMARK_SEARCH_FIELDS), read - set(BENCHMARK_SEARCH_FIELDS)


def test_the_compact_file_ranks_exactly_like_the_full_catalog(tmp_path):
    index_path = ROOT / "site/data/benchmark-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))["benchmarks"]
    payload = benchmark_search_payload(index)
    # Every record is kept: the full-corpus rule applies to this search too.
    assert payload["count"] == len(index) == len(payload["records"])
    search_path = tmp_path / "benchmark-search.json"
    search_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    subprocess.run(
        ["node", "tests/benchmark_search_parity_harness.mjs", str(index_path), str(search_path)],
        check=True,
        cwd=ROOT,
        timeout=300,
    )
