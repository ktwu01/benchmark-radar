#!/usr/bin/env python3
"""Export Claire Radar's Library research directions as a reviewed catalog input.

benchmark-radar.com files every Library record under one of 36 taxonomy-v5
research directions. That assignment is a model or keyword review, not a fact
from the benchmark's own source, so it is exported here as a separate, pinned
input with its basis kept per record. The catalog joins it onto records only
through exact identity: the Claire Radar record id, the LLM Stats source id the
.com record names, or an exact artifact identifier. A name is never a join key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark_radar.library_directions import library_record_anchors


def export_categories(
    library: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    repository: str,
    commit: str,
    library_sha256: str,
) -> dict[str, Any]:
    records = library.get("records")
    if not isinstance(records, list):
        raise ValueError("library index must contain a records array")
    category_ids = {category["id"] for category in taxonomy["categories"]}

    exported: dict[str, Any] = {}
    for record in records:
        assignment = record.get("categoryAssignment") or {}
        primary = str(assignment.get("primary") or "").strip()
        if not primary:
            # "unclassified" upstream: there is nothing to carry.
            continue
        categories = [str(value) for value in record.get("libraryCategories") or []]
        if primary not in categories:
            categories.insert(0, primary)
        unknown = sorted(set(categories) - category_ids)
        if unknown:
            raise ValueError(f"{record['id']}: categories outside taxonomy-v5: {unknown}")
        anchors = library_record_anchors(record)
        artifacts = anchors["artifacts"]
        llm_stats = anchors["llm_stats_ids"]
        exported[record["id"]] = {
            "primary": primary,
            "categories": categories,
            "basis": str(assignment.get("basis") or "unknown"),
            "artifacts": artifacts,
            "llm_stats_ids": llm_stats,
        }

    return {
        "schema_version": 1,
        "source": {
            "repository": repository,
            "commit": commit,
            "library_index_sha256": library_sha256,
        },
        "taxonomy": {
            "version": taxonomy["version"],
            "groups": [{"id": group["id"], "name": group["name"]} for group in taxonomy["groups"]],
            "categories": [
                {
                    "id": category["id"],
                    "group": category["group"],
                    "name": category["name"],
                    "description": category.get("description") or "",
                }
                for category in taxonomy["categories"]
            ],
        },
        "records": dict(sorted(exported.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("library_index", type=Path)
    parser.add_argument("taxonomy", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repository", default="https://github.com/Claire1217/benchmark-radar")
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    raw = args.library_index.read_bytes()
    document = export_categories(
        json.loads(raw),
        json.loads(args.taxonomy.read_text(encoding="utf-8")),
        repository=args.repository,
        commit=args.commit,
        library_sha256=hashlib.sha256(raw).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"exported {len(document['records'])} research-direction assignments to {args.output}")


if __name__ == "__main__":
    main()
