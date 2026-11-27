"""Reshape Aider's published leaderboards into the snapshot registry's format.

Aider (Apache-2.0, repository Aider-AI/aider) keeps each leaderboard it
publishes as a YAML file of benchmark runs in aider/website/_data/. Every run
names the model, the edit format, the aider version, the run date and the pass
rates. The three files are committed verbatim, with Aider's licence, under
data/leaderboard_snapshots/aider/, at upstream commit COMMIT (#1317).

WHAT THE RESHAPE HAS TO DECIDE

Each leaderboard is its own benchmark, so the three are never pooled:

    polyglot  225 exercises in six languages     score: pass_rate_2
    edit      133 Python exercises (the older)    score: pass_rate_2
    refactor  89 refactoring exercises            score: pass_rate_1

The score is the leaderboard's headline "percent correct", so each benchmark
declares a maximum of 100 and stays on the percent scale. The refactoring runs
allow one attempt, so they record only pass_rate_1.

A run counts only when it covered its leaderboard's full exercise set. A run
over fewer (or, once, a polyglot-sized run filed in the edit file) measured a
different denominator, so it is dropped and listed when the script runs, never
repaired.

Aider ran every model itself, so each score is third_party and measured_by
Aider. Each run keeps its own date as score_date, the day the run was made.
The run's directory name is unique per run and becomes run_id, so one model
tried with two edit formats stays two observations. It is not a model id, so
model_id stays empty and two runs never count as two models. Aider names
models but not their organizations, so organization_name stays empty rather
than guessed.

The upstream files are pinned by SHA-256 and checked before anything is read.
edit_leaderboard.yml has CRLF line endings on some lines, and a patch or an
editor that normalizes them changes the bytes; the reshape then stops instead
of reading a file that is no longer upstream's.

Usage, from the repository root:

    python scripts/reshape_aider.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import yaml

COMMIT = "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"
UPSTREAM_DIR = "aider/website/_data"
IN_DIR = Path("data/leaderboard_snapshots/aider")
OUT_DIR = Path("data/leaderboard_snapshots")
BENCHMARKS = OUT_DIR / "aider_benchmarks_2026-11-27.csv"
SCORES = OUT_DIR / "aider_benchmark_scores_2026-11-27.csv"

UPSTREAM_SHA256 = {
    "polyglot_leaderboard.yml": "85a50b25953512d18ba4bb0c23c0b8e626fcf9a5b52d287644b8a0b44b9535de",
    "edit_leaderboard.yml": "4c437c9e22c7fff8b0d61cb8fd4bf9bdf44370783ac9b00a840a80c81319d36e",
    "refactor_leaderboard.yml": "e01b88adf869b88501d48f9b041dbbb37e77e464e1bed886bb62f6b335c60561",
}

# id: (file, display name, metric, score field, full exercise set)
LEADERBOARDS = {
    "polyglot": (
        "polyglot_leaderboard.yml",
        "Aider Polyglot",
        "Percent correct after two attempts (pass_rate_2)",
        "pass_rate_2",
        225,
    ),
    "edit": (
        "edit_leaderboard.yml",
        "Aider Code Editing",
        "Percent correct after two attempts (pass_rate_2)",
        "pass_rate_2",
        133,
    ),
    "refactor": (
        "refactor_leaderboard.yml",
        "Aider Refactoring",
        "Percent correct in one attempt (pass_rate_1)",
        "pass_rate_1",
        89,
    ),
}


def upstream_url(filename: str) -> str:
    return f"https://github.com/Aider-AI/aider/blob/{COMMIT}/{UPSTREAM_DIR}/{filename}"


def reshape() -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    benchmarks: list[dict[str, str]] = []
    scores: list[dict[str, str]] = []
    dropped: list[str] = []
    for benchmark_id, (filename, name, metric, field, full) in LEADERBOARDS.items():
        raw = (IN_DIR / filename).read_bytes()
        expected = UPSTREAM_SHA256.get(filename)
        if expected and hashlib.sha256(raw).hexdigest() != expected:
            raise SystemExit(
                f"{IN_DIR / filename} is not upstream's file at {COMMIT}: its SHA-256 "
                f"differs from {expected}. Restore it byte for byte from {upstream_url(filename)}."
            )
        runs = yaml.safe_load(raw.decode("utf-8"))
        url = upstream_url(filename)
        kept = 0
        for run in runs:
            run_id = str(run["dirname"])
            cases = run.get("test_cases")
            score = run.get(field)
            run_date = run.get("date")
            if cases != full:
                dropped.append(f"{benchmark_id}: {run_id}: {cases} exercises, not {full}")
                continue
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                dropped.append(f"{benchmark_id}: {run_id}: no numeric {field}")
                continue
            if not isinstance(run_date, (str, date)):
                dropped.append(f"{benchmark_id}: {run_id}: no run date")
                continue
            scores.append(
                {
                    "benchmark_id": benchmark_id,
                    "benchmark_name": name,
                    "rank": "",
                    # The directory names a run, not a model: a model tried
                    # with two edit formats is two runs of one model.
                    "model_id": "",
                    "run_id": run_id,
                    "model_name": str(run["model"]),
                    "organization_name": "",
                    "benchmark_score": str(score),
                    "self_reported": "false",
                    "measured_by": "Aider",
                    "score_date": str(run_date),
                    "source_url": url,
                }
            )
            kept += 1
        benchmarks.append(
            {
                "benchmark_id": benchmark_id,
                "name": name,
                "metric": metric,
                # Every score is a percentage of the exercises solved.
                "max_score": "100",
                "unit": "percent",
                "detail_source_url": url,
                "extra_json": json.dumps(
                    {
                        "exercises": full,
                        "score_field": field,
                        "runs_published": len(runs),
                        "runs_kept": kept,
                        "upstream_commit": COMMIT,
                    },
                    sort_keys=True,
                ),
            }
        )
    return benchmarks, scores, dropped


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    benchmarks, scores, dropped = reshape()
    write(BENCHMARKS, benchmarks)
    write(SCORES, scores)
    print(f"{len(benchmarks)} benchmarks, {len(scores)} score rows -> {OUT_DIR}")
    for line in dropped:
        print(f"dropped {line}")


if __name__ == "__main__":
    main()
