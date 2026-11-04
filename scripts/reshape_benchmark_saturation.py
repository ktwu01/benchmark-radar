"""Reshape the Benchmark Saturation annotation table into the snapshot registry's format.

The Benchmark Saturation study (Akhtar et al., arXiv:2602.16763; MIT, repository
evaleval/benchmark-saturation) annotates 60 benchmarks by hand: a release date,
the five top-performing models with their scores, and a saturation index. Every
other crawl in `data/leaderboard_snapshots.yml` is two CSVs with the llm-stats
header vocabulary, so this table is reshaped to fit the registry rather than
the registry widened to fit it (#636).

WHAT THE RESHAPE HAS TO DECIDE

The upstream file has 106 lines of data, but only 60 carry an ID. The other 46
are spreadsheet residue holding one value in one column and nothing else; the
reshape fails if a blank row ever holds anything more.

Each record keeps the upstream ID as its source id. No name is joined to any
other catalog record: overlaps go through identity candidates and the reviewed
`data/catalog/identity.yml`.

The top five arrive twice: as "model: score" text (`top5_models_extracted`) and
as five numeric columns. A score is kept only when both agree at the same
position (the text value, rounded to the column's precision, equals the
column). The text carries the model name, so its value is the one recorded. A
position that disagrees, does not parse, or is marked approximate ("~ 89%") is
dropped and listed when the script runs; it is never repaired by hand.

The source names models, not model ids, and one name can fill two positions
(two settings of one model). The row identity is therefore the position, and
`model_id` stays empty: inventing an id would claim the source said which
model run it was.

The saturation index is the study's own stated value. It is carried as source
metadata, as written, and nothing in this project ranks by it.

Usage, from the repository root:

    python scripts/reshape_benchmark_saturation.py \\
        data/leaderboard_snapshots/benchmark_saturation/manual_annotation_data.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

COMMIT = "6285e3dda145f575a0ccb3f7f4d70cd429832add"
SOURCE_URL = (
    f"https://github.com/evaleval/benchmark-saturation/blob/{COMMIT}"
    "/data/manual_annotation_data.csv"
)
OUT_DIR = Path("data/leaderboard_snapshots")
BENCHMARKS = OUT_DIR / "benchmark_saturation_benchmarks_2026-11-04.csv"
SCORES = OUT_DIR / "benchmark_saturation_benchmark_scores_2026-11-04.csv"
# The one column the blank spreadsheet rows still fill.
RESIDUE_COLUMN = "Time since benchmark release (in months)"
STATED = {
    "saturation_index": "Saturation Index",
    "saturation_index_interpreted": "Saturation Index (interpreted) ",
    "metric": "Metric",
    "test_samples": "Quantity of test samples",
    "dataset_issues": "Dataset-related issues",
}
_ENTRY = re.compile(
    r"^(?P<name>.+?)\s*(?::|\s-\s|\s)\s*(?P<approx>~\s*)?(?P<value>-?\d+(?:\.\d+)?)\s*%?$"
)


def _text(value: str | None) -> str:
    return " ".join((value or "").split())


def entries(text: str) -> list[tuple[str, str] | None]:
    """Each "model: score" entry in order; None where an entry does not parse."""
    parsed: list[tuple[str, str] | None] = []
    for piece in re.split(r"[;\n]", text or ""):
        piece = _text(piece)
        if not piece:
            continue
        match = _ENTRY.match(piece)
        raw = match.group("name") if match else ""
        name = raw.strip(" :-~")
        # "~ 89%" is the study saying it is not sure of the number; recording it
        # would state an approximation as an exact score.
        exact = bool(match) and not match.group("approx") and not raw.rstrip(" :-").endswith("~")
        parsed.append((name, match.group("value")) if match and name and exact else None)
    return parsed


def agrees(value: str, column: str) -> bool:
    """True when ``value`` rounded to the column's precision equals the column."""
    column = column.strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", column):
        return False
    places = Decimal(column).as_tuple().exponent
    rounded = Decimal(value).quantize(Decimal(1).scaleb(places), rounding=ROUND_HALF_UP)
    return rounded == Decimal(column)


def reshape(source: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    benchmarks: list[dict[str, str]] = []
    scores: list[dict[str, str]] = []
    dropped: list[str] = []
    for index, row in enumerate(rows):
        source_id = (row.get("ID") or "").strip()
        if not source_id:
            filled = {key for key, value in row.items() if key and _text(value)}
            if filled - {RESIDUE_COLUMN}:
                raise SystemExit(f"row {index} has no ID but fills {sorted(filled)}")
            continue
        name = _text(row["Name"])
        released = ""
        if _text(row["Released Date"]):
            released = datetime.strptime(_text(row["Released Date"]), "%m/%d/%Y").date().isoformat()
        stated = {key: _text(row.get(column)) for key, column in STATED.items()}
        benchmarks.append(
            {
                "benchmark_id": source_id,
                "name": name,
                "released": released,
                "detail_source_url": SOURCE_URL,
                "extra_json": json.dumps(
                    {key: value for key, value in stated.items() if value},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
        for position, entry in enumerate(entries(row["top5_models_extracted"]), start=1):
            column = row.get(f"top model {position}") or ""
            if entry is None or not agrees(entry[1], column):
                dropped.append(f"{source_id} {name}: position {position} {entry} vs {column!r}")
                continue
            scores.append(
                {
                    "benchmark_id": source_id,
                    "benchmark_name": name,
                    "rank": str(position),
                    "model_name": entry[0],
                    "organization_name": "",
                    "benchmark_score": entry[1],
                    "source_url": SOURCE_URL,
                }
            )
    return benchmarks, scores, dropped


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("source", type=Path, help="upstream manual_annotation_data.csv")
    args = parser.parse_args()
    benchmarks, scores, dropped = reshape(args.source)
    _write(BENCHMARKS, benchmarks)
    _write(SCORES, scores)
    print(f"{len(benchmarks)} benchmarks, {len(scores)} scores, {len(dropped)} positions dropped")
    for line in dropped:
        print(f"  dropped {line}")


if __name__ == "__main__":
    main()
