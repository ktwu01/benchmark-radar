#!/usr/bin/env python3
"""Export benchmark-radar.com's attention signals as a pinned catalog input.

Claire Radar observes GitHub stars, Hugging Face paper upvotes and dataset
downloads for its Library records (library_metrics.json), and keeps a sparse
GitHub-star history (signal_history.json, a value stored only when it changes).
They are observations of a repository or paper on a date, not facts about the
benchmark, so they are exported with their dates and joined to catalog records
only through exact identity (library_signals.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark_radar.library_directions import library_record_anchors

SIGNAL_FIELDS = {
    "githubStars": "github_stars",
    "hfPaperUpvotes": "hf_paper_upvotes",
    "hfDatasetDownloads": "hf_dataset_downloads",
}


def export_signals(
    library: dict[str, Any],
    metrics: dict[str, Any],
    history: dict[str, Any],
    *,
    source: dict[str, str],
) -> dict[str, Any]:
    anchors = {record["id"]: library_record_anchors(record) for record in library["records"]}
    stars_history = history.get("records") or {}
    records: dict[str, Any] = {}
    for row in metrics["records"]:
        record_id = row["benchmarkId"]
        values = {
            name: row.get(field)
            for field, name in SIGNAL_FIELDS.items()
            if isinstance(row.get(field), (int, float)) and not isinstance(row.get(field), bool)
        }
        series = (stars_history.get(record_id) or {}).get("githubStars") or []
        if not values and not series:
            continue
        if record_id not in anchors:
            # A metrics row with no Library record has no identity to join on.
            continue
        records[record_id] = {
            **anchors[record_id],
            **values,
            "as_of": row.get("asOf"),
            "github_stars_history": [[str(day), int(value)] for day, value in series],
        }
    return {
        "schema_version": 1,
        "source": source,
        "records": dict(sorted(records.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("library_index", type=Path)
    parser.add_argument("library_metrics", type=Path)
    parser.add_argument("signal_history", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repository", default="https://github.com/Claire1217/benchmark-radar")
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    raws = {
        name: path.read_bytes()
        for name, path in (
            ("library_index", args.library_index),
            ("library_metrics", args.library_metrics),
            ("signal_history", args.signal_history),
        )
    }
    metrics = json.loads(raws["library_metrics"])
    document = export_signals(
        json.loads(raws["library_index"]),
        metrics,
        json.loads(raws["signal_history"]),
        source={
            "repository": args.repository,
            "commit": args.commit,
            "observed_on": str(metrics.get("date") or ""),
            **{f"{name}_sha256": hashlib.sha256(raw).hexdigest() for name, raw in raws.items()},
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"exported signals for {len(document['records'])} records to {args.output}")


if __name__ == "__main__":
    main()
