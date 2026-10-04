"""Per-benchmark shards: one JSON file per source record for the detail panel.

DISPLAY-PLAN.md step 1. The search index answers "which benchmark", a shard
answers the reader's four questions about one of them: who made it, is it open,
how big is it, what scores exist. One shard per source record, addressed by the
record's own slug, so all 1,148 rows have a URL and none is merged away.

WHY `scores_by_source` IS A KEYED OBJECT

The shard partitions scores by source in the payload itself:

    {"record": {...}, "siblings": [...],
     "scores_by_source": {"llm_stats": {"series": {...}, "rows": [...]}}}

This is the enforcement point for "no cross-source ranking", not a note asking
the renderer to behave. A flat array with a `source` field on each row is one
`.sort()` away from a merged leaderboard; a keyed object is not sortable into
one without deliberately writing the merge. So the shape is load-bearing and is
not flattened for convenience.

WHY A FRESH DIRECTORY IS SWAPPED IN

Benchmarks leave the crawl. If a removed record's shard were left behind, its
URL would keep serving last month's data as if it were current. So shards are
written to a sibling directory and swapped in atomically, and the old directory
is deleted, so the set of live shards is exactly the set of current records.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .catalog import CATALOG_SCHEMA_VERSION
from .catalog_identity import IdentityIndex

DEFAULT_SHARD_DIR = Path("site/data/benchmarks")


def _scores_by_source(
    record: dict[str, Any],
    series_by_key: dict[str, dict[str, Any]],
    observations_by_key: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """The keyed score partition for one record.

    The key is the record's own `source`, never a constant: llm-stats and
    Artificial Analysis both supply observations, and filing one under the
    other's name would be the cross-source merge this shape exists to prevent.

    Only sources that actually recorded a score for this key, or that declared
    a score series for it, get a key here. A source with a declared series but
    no observations yet ships its declared scale with empty rows, so "not
    measured" stays distinguishable from "not comparable". An OpenCompass
    record, which has neither, gets `{}` rather than a source key holding an
    empty list, so the absence is visible as absence.
    """
    key = record["key"]
    series = series_by_key.get(key)
    rows = observations_by_key.get(key)
    if not series and not rows:
        return {}
    return {
        record["source"]: {
            "series": series or {},
            "rows": rows or [],
        }
    }


def build_shard(
    record: dict[str, Any],
    *,
    identity: IdentityIndex,
    series_by_key: dict[str, dict[str, Any]],
    observations_by_key: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """One shard: the record, its identity siblings, and its scores by source."""
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "record": record,
        "siblings": identity.siblings_for(record["key"]),
        "scores_by_source": _scores_by_source(record, series_by_key, observations_by_key),
    }


def write_shards(
    records: list[dict[str, Any]],
    *,
    identity: IdentityIndex,
    series: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    output_dir: Path = DEFAULT_SHARD_DIR,
) -> dict[str, Any]:
    """Write one shard per record, swapping a fresh directory in atomically.

    Returns the shard count and total byte size so a build can report them
    without re-walking the directory.
    """
    series_by_key = {item["key"]: item for item in series}
    observations_by_key: dict[str, list[dict[str, Any]]] = {}
    for obs in observations:
        observations_by_key.setdefault(obs["key"], []).append(obs)

    staging = output_dir.with_name(output_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    total_bytes = 0
    for record in records:
        shard = build_shard(
            record,
            identity=identity,
            series_by_key=series_by_key,
            observations_by_key=observations_by_key,
        )
        payload = json.dumps(shard, ensure_ascii=False, sort_keys=True) + "\n"
        path = staging / f"{record['slug']}.json"
        path.write_text(payload, encoding="utf-8")
        total_bytes += len(payload.encode("utf-8"))

    # Swap: remove the live directory only once the fresh one is fully written,
    # so a crash mid-build never leaves a half-populated live directory.
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)

    return {"shard_count": len(records), "total_bytes": total_bytes, "output_dir": output_dir}
