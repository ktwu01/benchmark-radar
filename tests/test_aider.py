"""Aider's three leaderboards as a catalog source (#1317)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reshape_aider as reshape  # noqa: E402

from benchmark_radar.catalog import _observation  # noqa: E402


def test_committed_snapshot_is_the_reshape_of_the_committed_upstream_files():
    benchmarks, scores, dropped = reshape.reshape()
    assert [row["benchmark_id"] for row in benchmarks] == ["polyglot", "edit", "refactor"]
    assert len(scores) == 167
    counts = {b: sum(1 for row in scores if row["benchmark_id"] == b) for b in reshape.LEADERBOARDS}
    assert counts == {"polyglot": 63, "edit": 93, "refactor": 11}
    # Every drop is a run over a different exercise set than its leaderboard's.
    assert len(dropped) == 14
    assert all("exercises, not" in line for line in dropped)
    for rows, path in ((benchmarks, reshape.BENCHMARKS), (scores, reshape.SCORES)):
        with path.open(encoding="utf-8", newline="") as handle:
            assert list(csv.DictReader(handle)) == rows


def test_each_leaderboard_keeps_its_own_score_field_and_scale():
    benchmarks, scores, _ = reshape.reshape()
    fields = {row["benchmark_id"]: json.loads(row["extra_json"]) for row in benchmarks}
    assert fields["polyglot"]["score_field"] == "pass_rate_2"
    assert fields["edit"]["score_field"] == "pass_rate_2"
    assert fields["refactor"]["score_field"] == "pass_rate_1"
    assert all(row["max_score"] == "100" and row["unit"] == "percent" for row in benchmarks)
    assert all(0 <= float(row["benchmark_score"]) <= 100 for row in scores)
    # Aider names models, not who made them, so no organization is guessed.
    assert all(row["organization_name"] == "" for row in scores)
    assert all(row["measured_by"] == "Aider" and row["self_reported"] == "false" for row in scores)


def test_a_run_over_a_partial_exercise_set_is_dropped_not_kept(tmp_path, monkeypatch):
    runs = [
        {
            "dirname": "full",
            "model": "m",
            "test_cases": 89,
            "pass_rate_1": 50.0,
            "date": "2024-05-04",
        },
        {
            "dirname": "part",
            "model": "m",
            "test_cases": 88,
            "pass_rate_1": 60.0,
            "date": "2024-05-05",
        },
        {
            "dirname": "blank",
            "model": "m",
            "test_cases": 89,
            "pass_rate_1": None,
            "date": "2024-05-06",
        },
    ]
    (tmp_path / "refactor.yml").write_text(json.dumps(runs), encoding="utf-8")
    monkeypatch.setattr(reshape, "IN_DIR", tmp_path)
    monkeypatch.setattr(
        reshape, "LEADERBOARDS", {"refactor": ("refactor.yml", "R", "metric", "pass_rate_1", 89)}
    )
    _, scores, dropped = reshape.reshape()
    assert [row["run_id"] for row in scores] == ["full"]
    assert [row["model_id"] for row in scores] == [""]
    assert dropped == [
        "refactor: part: 88 exercises, not 89",
        "refactor: blank: no numeric pass_rate_1",
    ]


def _row(**extra: str) -> dict[str, str]:
    row = {
        "benchmark_id": "b",
        "model_id": "m1",
        "model_name": "Model 1",
        "benchmark_score": "50",
        "announcement_date": "2024-01-01",
    }
    row.update(extra)
    return row


def test_a_run_date_dates_the_observation_by_the_day_it_was_measured():
    obs = _observation(
        _row(score_date="2024-06-01", measured_by="Aider", self_reported="false"),
        key="aider:b",
        series_id="aider:b:default",
        crawled_at="2026-11-27T15:40:00Z",
        source="aider",
    )
    assert obs["reported_date"] == "2024-06-01"
    assert obs["date_precision"] == "measurement"
    assert obs["measured_by"] == "Aider"
    assert obs["reported_by"] == "third_party"


def test_a_row_without_a_run_date_keeps_the_model_announcement_date():
    obs = _observation(
        _row(),
        key="llm_stats:b",
        series_id="llm_stats:b:default",
        crawled_at="2026-08-17T00:00:00Z",
        source="llm_stats",
    )
    assert obs["reported_date"] == "2024-01-01"
    assert obs["date_precision"] == "model_announcement"
    assert obs["measured_by"] is None


def test_the_site_shards_carry_the_three_leaderboards():
    index = json.loads(Path("site/data/benchmark-index.json").read_text(encoding="utf-8"))
    keys = sorted(record["key"] for record in index["benchmarks"] if record["source"] == "aider")
    assert keys == ["aider:edit", "aider:polyglot", "aider:refactor"]
    shard = json.loads(Path("site/data/benchmarks/aider-refactor.json").read_text(encoding="utf-8"))
    rows = shard["scores_by_source"]["aider"]["rows"]
    assert len(rows) == 11
    assert all(
        row["measured_by"] == "Aider" and row["date_precision"] == "measurement" for row in rows
    )


def test_an_upstream_file_with_changed_bytes_is_refused(tmp_path, monkeypatch):
    # edit_leaderboard.yml mixes CRLF and LF lines; a copy that normalized
    # them parses identically but is no longer upstream's file.
    original = (reshape.IN_DIR / "edit_leaderboard.yml").read_bytes()
    assert b"\r\n" in original
    for name in reshape.UPSTREAM_SHA256:
        (tmp_path / name).write_bytes((reshape.IN_DIR / name).read_bytes())
    (tmp_path / "edit_leaderboard.yml").write_bytes(original.replace(b"\r\n", b"\n"))
    monkeypatch.setattr(reshape, "IN_DIR", tmp_path)
    with pytest.raises(SystemExit, match="edit_leaderboard.yml is not upstream"):
        reshape.reshape()


def test_runs_are_observations_not_models():
    series = {
        json.loads(line)["series_id"]: json.loads(line)
        for line in Path("data/catalog/aider_score_series.jsonl").read_text().splitlines()
    }
    polyglot = series["aider:polyglot:default"]
    assert polyglot["unit"] == "percent"
    # 63 runs, but a run directory is not a model and Aider names no
    # organization, so no model count is claimed.
    assert polyglot["observation_count"] == 63
    assert polyglot["score_summary"]["model_count"] is None


def test_two_runs_of_one_model_say_which_setting_made_each_score():
    _, scores, _ = reshape.reshape()
    qwen = sorted(
        (row["benchmark_score"], row["protocol"])
        for row in scores
        if row["benchmark_id"] == "polyglot" and row["model_name"] == "Qwen2.5-Coder-32B-Instruct"
    )
    assert qwen == [
        ("16.4", "edit format whole · aider 0.69.2.dev"),
        ("8.0", "edit format diff · aider 0.69.2.dev"),
    ]
    assert all(row["protocol"].startswith("edit format ") for row in scores)


def test_aider_licence_ships_with_the_third_party_notices():
    notices = Path("LICENSE-CONTENT.md").read_text(encoding="utf-8")
    licence = (reshape.IN_DIR / "LICENSE.txt").read_text(encoding="utf-8").strip("\n")
    assert reshape.COMMIT in notices
    assert licence in notices
