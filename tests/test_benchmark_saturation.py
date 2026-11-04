"""The Benchmark Saturation study as a catalog source (#636)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reshape_benchmark_saturation as reshape  # noqa: E402

UPSTREAM = Path("data/leaderboard_snapshots/benchmark_saturation/manual_annotation_data.csv")


def test_entries_read_each_model_and_score_as_written():
    text = (
        "GPT 4: 87.5; \nCommand R: 85.4;\nKImi K2 - Base 85.32;\nGPT-5.2 (Pro) 29.2%;\n"
        "no score; Gpt 5 thinking ~: 89.0; Gpt-5-main ~ 84.8%"
    )
    assert reshape.entries(text) == [
        ("GPT 4", "87.5"),
        ("Command R", "85.4"),
        ("KImi K2 - Base", "85.32"),
        ("GPT-5.2 (Pro)", "29.2"),
        None,
        # Approximate values are not recorded as exact scores.
        None,
        None,
    ]


def test_a_score_is_kept_only_when_the_text_and_the_column_agree():
    assert reshape.agrees("93.214", "93.2")
    assert reshape.agrees("93.011", "93")
    assert reshape.agrees("28.50", "28.5")
    assert not reshape.agrees("84.5", "0.845")
    assert not reshape.agrees("37.72", "")


def test_blank_rows_may_hold_only_spreadsheet_residue(tmp_path):
    source = tmp_path / "table.csv"
    header = ["ID", "Name", "Released Date", "top5_models_extracted", reshape.RESIDUE_COLUMN]
    with source.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerow(["1", "GSM8K", "10/27/2021", "o3: 99.2", "49"])
        writer.writerow(["", "", "", "", "1512"])
    benchmarks, scores, dropped = reshape.reshape(source)
    assert [row["benchmark_id"] for row in benchmarks] == ["1"]
    # No numeric column to check "o3: 99.2" against, so it is not recorded.
    assert scores == [] and len(dropped) == 1
    with source.open("a", newline="") as handle:
        csv.writer(handle).writerow(["", "Stray name", "", "", ""])
    with pytest.raises(SystemExit):
        reshape.reshape(source)


def test_committed_snapshot_is_the_reshape_of_the_committed_upstream_file(tmp_path):
    benchmarks, scores, dropped = reshape.reshape(UPSTREAM)
    assert len(benchmarks) == 60 and len(scores) == 297
    # MMMLU (ID 22) states two scores as approximate ("~ 89%").
    assert [line.split(" ", 1)[0] for line in dropped] == ["22", "22"]
    for rows, path in ((benchmarks, reshape.BENCHMARKS), (scores, reshape.SCORES)):
        with path.open(encoding="utf-8", newline="") as handle:
            assert list(csv.DictReader(handle)) == rows


def test_every_record_is_one_upstream_row_keyed_by_its_own_id():
    index = json.loads(Path("site/data/benchmark-index.json").read_text(encoding="utf-8"))
    keys = sorted(
        record["key"]
        for record in index["benchmarks"]
        if record["source"] == "benchmark_saturation"
    )
    assert keys == sorted(f"benchmark-saturation:{n}" for n in range(1, 61))
    shard = json.loads(
        Path("site/data/benchmarks/benchmark-saturation-53.json").read_text(encoding="utf-8")
    )
    rows = shard["scores_by_source"]["benchmark_saturation"]["rows"]
    # Names only: no model id, no organization, and no model count invented.
    assert [row["model_name"] for row in rows][:2] == [
        "Gemini 3 pro preview",
        "gpt-5-pro-2025-10-06",
    ]
    assert all(row["model_id"] is None and row["organization"] is None for row in rows)
    assert shard["record"]["evidence_summary"]["model_count"] is None
    assert shard["scores_by_source"]["benchmark_saturation"]["series"]["metric"] == "Accuracy"
    metadata = shard["record"]["source_metadata"]["benchmark_saturation"]
    assert metadata["saturation_index_interpreted"]
