"""Validated ingest of committed aggregator crawl snapshots.

This module reads `data/leaderboard_snapshots.yml` and the CSV files it
declares, and certifies that what is on disk is what the registry says is on
disk. It does not interpret, merge, or publish anything: `catalog.py`
turns the validated rows into the per-source catalog records and score
observations the site consumes.

WHY COMPLETENESS IS CERTIFIED RATHER THAN ASSUMED

Each registry entry declares the row counts its files must contain, and the
loader refuses a file whose count drifts from the declaration. A truncated
copy, a partial rerun, or an accidental append would otherwise be
indistinguishable from a complete snapshot, and a snapshot whose completeness
cannot be stated is not a snapshot.

`columns` maps this project's vocabulary onto each source file's header, so the
loader never guesses which column means what. A renamed upstream header fails
loudly here instead of silently producing empty fields downstream.

WHAT THIS MODULE DELIBERATELY NO LONGER DOES

An earlier version of this file also built the published payload, keyed by
canonical benchmark id, with external benchmarks that matched no canonical id
surviving only as an integer count. That projection discarded roughly 87% of
the llm-stats catalog and every OpenCompass identity column on the way to the
site, which is the defect issue #240 exists to fix. The projection is gone;
only the ingest contract remains. Records are now addressed by their own
`source:source_benchmark_id` key, whether or not they map to anything curated.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SNAPSHOTS_SCHEMA_VERSION = 1

DEFAULT_SNAPSHOTS_PATH = Path("data/leaderboard_snapshots.yml")

_REQUIRED_SNAPSHOT_FIELDS = (
    "id",
    "source",
    "source_url",
    "crawled_at",
    "benchmark_file",
    "benchmark_count",
    "columns",
)
_REQUIRED_COLUMN_FIELDS = ("benchmark_id", "benchmark_name")


class LeaderboardSnapshotError(ValueError):
    """Raised when the snapshot registry or a declared file is inconsistent."""


def _require(value: Any, fields: tuple[str, ...], *, label: str) -> None:
    if not isinstance(value, dict):
        raise LeaderboardSnapshotError(f"{label} must be a mapping")
    missing = [
        field
        for field in fields
        if value.get(field) is None or (isinstance(value[field], str) and not value[field].strip())
    ]
    if missing:
        raise LeaderboardSnapshotError(f"{label} is missing fields: {', '.join(missing)}")


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    except (OSError, csv.Error) as error:
        raise LeaderboardSnapshotError(f"{path}: cannot read CSV: {error}") from error
    if not header or not rows:
        raise LeaderboardSnapshotError(f"{path}: CSV has no header or no data rows")
    return header, rows


def _require_column(header: list[str], column: str, *, path: Path, label: str) -> None:
    if column not in header:
        raise LeaderboardSnapshotError(f"{path}: {label} column {column!r} missing from header")


def _verify_sha256(path: Path, expected: Any, *, label: str) -> None:
    if expected is None:
        return
    digest = str(expected).strip().casefold()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise LeaderboardSnapshotError(f"{label} must be a 64-character SHA-256 digest")
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise LeaderboardSnapshotError(f"{path}: cannot verify {label}: {error}") from error
    if actual != digest:
        raise LeaderboardSnapshotError(
            f"{path}: SHA-256 mismatch for {label}: expected {digest}, got {actual}"
        )


def _finite_float(value: str, *, path: Path, label: str) -> float | None:
    if not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as error:
        raise LeaderboardSnapshotError(
            f"{path}: {label} value {value!r} is not a number"
        ) from error
    if not math.isfinite(parsed):
        raise LeaderboardSnapshotError(f"{path}: {label} value {value!r} is not finite")
    return parsed


def _require_iso_timestamp(value: str, *, label: str) -> str:
    if not value.strip():
        raise LeaderboardSnapshotError(f"{label} must not be empty")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise LeaderboardSnapshotError(f"{label} {value!r} is not an ISO timestamp") from error
    return value


def _load_snapshot_files(snapshot: dict[str, Any], base: Path) -> dict[str, Any]:
    """Load and validate one declared snapshot's committed CSV files.

    Row counts are certified against the registry declaration, so a truncated
    copy, a partial rerun, or an accidental append fails loudly instead of
    publishing a snapshot whose completeness cannot be stated.
    """
    path = base / str(snapshot["benchmark_file"])
    _verify_sha256(path, snapshot.get("benchmark_sha256"), label="benchmark_sha256")
    header, rows = _read_csv_rows(path)
    columns = snapshot["columns"]
    benchmark_columns = snapshot.get("benchmark_columns") or columns
    _require_column(header, str(benchmark_columns["benchmark_id"]), path=path, label="benchmark_id")
    _require_column(
        header, str(benchmark_columns["benchmark_name"]), path=path, label="benchmark_name"
    )
    expected = int(snapshot["benchmark_count"])
    if len(rows) != expected:
        raise LeaderboardSnapshotError(f"{path}: {len(rows)} rows, registry declares {expected}")
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        benchmark_id = row[str(benchmark_columns["benchmark_id"])].strip()
        if not benchmark_id:
            raise LeaderboardSnapshotError(f"{path}: row {index} has an empty benchmark id")
        if benchmark_id in seen_ids:
            raise LeaderboardSnapshotError(f"{path}: duplicate benchmark id {benchmark_id!r}")
        seen_ids.add(benchmark_id)
    benchmark_rows = rows

    score_rows: list[dict[str, str]] | None = None
    if snapshot.get("scores_file"):
        scores_path = base / str(snapshot["scores_file"])
        _verify_sha256(scores_path, snapshot.get("scores_sha256"), label="scores_sha256")
        score_header, score_rows = _read_csv_rows(scores_path)
        _require_column(
            score_header, str(columns["benchmark_id"]), path=scores_path, label="benchmark_id"
        )
        _require_column(
            score_header, str(columns["benchmark_name"]), path=scores_path, label="benchmark_name"
        )
        _require_column(score_header, str(columns["model"]), path=scores_path, label="model")
        _require_column(
            score_header, str(columns["organization"]), path=scores_path, label="organization"
        )
        _require_column(score_header, str(columns["score"]), path=scores_path, label="score")
        if "score_row_count" not in snapshot:
            raise LeaderboardSnapshotError(
                f"{scores_path}: scores_file declared without score_row_count"
            )
        expected_scores = int(snapshot["score_row_count"])
        if len(score_rows) != expected_scores:
            raise LeaderboardSnapshotError(
                f"{scores_path}: {len(score_rows)} rows, registry declares {expected_scores}"
            )
        # Row identity is (benchmark_id, model_id) when the source carries an
        # id, because distinct dated checkpoints can share a display name. The
        # name is display vocabulary; the id is what a row actually is.
        model_key = str(columns.get("model_id") or columns["model"])
        pairs: set[tuple[str, str]] = set()
        for index, row in enumerate(score_rows):
            benchmark_id = row[str(columns["benchmark_id"])].strip()
            model = row[model_key].strip()
            if not benchmark_id or not model:
                raise LeaderboardSnapshotError(
                    f"{scores_path}: row {index} has an empty benchmark id or model"
                )
            pair = (benchmark_id, model)
            if pair in pairs:
                raise LeaderboardSnapshotError(
                    f"{scores_path}: duplicate row for benchmark {benchmark_id!r} model {model!r}"
                )
            pairs.add(pair)
            score_value = row[str(columns["score"])]
            if not score_value.strip():
                raise LeaderboardSnapshotError(f"{scores_path}: row {index} has an empty score")
            _finite_float(score_value, path=scores_path, label=f"row {index} score")
            normalized = row.get(str(columns.get("normalized_score") or ""))
            if normalized:
                _finite_float(normalized, path=scores_path, label=f"row {index} normalized_score")
            rank = row.get(str(columns.get("rank") or ""))
            if rank and not rank.strip().isdigit():
                raise LeaderboardSnapshotError(
                    f"{scores_path}: row {index} rank {rank!r} is not a positive integer"
                )

    return {"benchmark_rows": benchmark_rows, "score_rows": score_rows}


def load_snapshots(path: Path = DEFAULT_SNAPSHOTS_PATH) -> dict[str, Any]:
    """Read and validate the snapshot registry and every file it declares."""
    if not path.exists():
        raise LeaderboardSnapshotError(f"{path}: snapshot registry not found")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise LeaderboardSnapshotError(f"{path}: snapshot registry must be a mapping")
    version = document.get("schema_version")
    if version != SNAPSHOTS_SCHEMA_VERSION:
        raise LeaderboardSnapshotError(f"{path}: unsupported schema_version {version!r}")

    snapshots = document.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise LeaderboardSnapshotError(f"{path}: snapshots must be a non-empty array")

    base = path.parent
    loaded: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(snapshots):
        label = f"{path}: snapshot {index}"
        _require(entry, _REQUIRED_SNAPSHOT_FIELDS, label=label)
        snapshot_id = str(entry["id"])
        if snapshot_id in seen_ids:
            raise LeaderboardSnapshotError(f"{label} repeats snapshot id {snapshot_id!r}")
        seen_ids.add(snapshot_id)
        columns = entry["columns"]
        benchmark_columns = entry.get("benchmark_columns") or columns
        _require(columns, _REQUIRED_COLUMN_FIELDS, label=f"{label} columns")
        _require(benchmark_columns, _REQUIRED_COLUMN_FIELDS, label=f"{label} benchmark_columns")
        _require_iso_timestamp(str(entry["crawled_at"]), label=f"{label} crawled_at")
        files = _load_snapshot_files(entry, base)
        loaded.append(
            {
                "id": snapshot_id,
                "source": str(entry["source"]),
                "source_url": str(entry["source_url"]),
                "crawled_at": str(entry["crawled_at"]),
                "description": str(entry.get("description") or ""),
                "benchmark_file": str(entry["benchmark_file"]),
                "benchmark_count": int(entry["benchmark_count"]),
                "scores_file": str(entry["scores_file"]) if entry.get("scores_file") else None,
                "score_row_count": int(entry["score_row_count"]) if entry.get("scores_file") else 0,
                "columns": {str(key): str(value) for key, value in columns.items()},
                "benchmark_columns": {
                    str(key): str(value) for key, value in benchmark_columns.items()
                },
                "benchmark_rows": files["benchmark_rows"],
                "score_rows": files["score_rows"],
            }
        )

    return {"schema_version": SNAPSHOTS_SCHEMA_VERSION, "snapshots": loaded}
