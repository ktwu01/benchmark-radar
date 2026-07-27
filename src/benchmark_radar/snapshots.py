from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import RadarRun

SCHEMA_VERSION = 1


class SnapshotError(ValueError):
    """Raised when persisted public data does not match the supported schema."""


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def snapshot_for_run(run: RadarRun) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": run.generated_at.astimezone(UTC).date().isoformat(),
        "generated_at": _iso_utc(run.generated_at),
        "since": _iso_utc(run.since),
        "items": [item.to_dict() for item in run.items],
        "health": [
            {
                "source": health.source,
                "ok": health.ok,
                "item_count": health.item_count,
                "error": health.error,
            }
            for health in run.health
        ],
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_snapshot(snapshot: dict[str, Any], *, source: str = "snapshot") -> None:
    required = {"schema_version", "date", "generated_at", "since", "items", "health"}
    missing = sorted(required - snapshot.keys())
    if missing:
        raise SnapshotError(f"{source}: missing fields: {', '.join(missing)}")
    if snapshot["schema_version"] != SCHEMA_VERSION:
        raise SnapshotError(f"{source}: unsupported schema_version {snapshot['schema_version']!r}")
    try:
        generated = datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00"))
        since = datetime.fromisoformat(str(snapshot["since"]).replace("Z", "+00:00"))
        expected_date = generated.astimezone(UTC).date().isoformat()
    except ValueError as error:
        raise SnapshotError(f"{source}: invalid timestamp: {error}") from error
    if snapshot["date"] != expected_date:
        raise SnapshotError(
            f"{source}: date {snapshot['date']!r} does not match generated_at UTC date"
        )
    if since > generated:
        raise SnapshotError(f"{source}: since must not be after generated_at")
    if not isinstance(snapshot["items"], list) or not isinstance(snapshot["health"], list):
        raise SnapshotError(f"{source}: items and health must be arrays")

    item_fields = {
        "source",
        "source_id",
        "title",
        "url",
        "published_at",
        "event_kind",
        "categories",
        "metrics",
        "evidence_score",
        "relevance_score",
        "recency_score",
        "adoption_score",
        "total_score",
        "rationale",
    }
    for index, item in enumerate(snapshot["items"]):
        if not isinstance(item, dict):
            raise SnapshotError(f"{source}: item {index} must be an object")
        if "raw" in item:
            raise SnapshotError(f"{source}: item {index} must not expose raw source payloads")
        item_missing = sorted(item_fields - item.keys())
        if item_missing:
            raise SnapshotError(f"{source}: item {index} missing fields: {', '.join(item_missing)}")
        if not str(item["url"]).startswith(("https://", "http://")):
            raise SnapshotError(f"{source}: item {index} URL must be HTTP(S)")
        try:
            datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
        except ValueError as error:
            raise SnapshotError(f"{source}: item {index} has invalid published_at") from error

    for index, health in enumerate(snapshot["health"]):
        if not isinstance(health, dict) or not {"source", "ok", "item_count"} <= health.keys():
            raise SnapshotError(f"{source}: health {index} is invalid")


def write_snapshot(run: RadarRun, snapshot_dir: Path) -> Path:
    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)
    path = snapshot_dir / f"{snapshot['date']}.json"
    _write_json(path, snapshot)
    return path


def load_snapshots(snapshot_dir: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SnapshotError(f"{path}: invalid JSON: {error}") from error
        validate_snapshot(snapshot, source=str(path))
        snapshots.append(snapshot)
    snapshots.sort(key=lambda value: (value["date"], value["generated_at"]))
    return snapshots


def dashboard_data(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    categories: set[str] = set()
    sources: set[str] = set()
    event_kinds: set[str] = set()
    for snapshot in snapshots:
        category_counts = Counter(
            category for item in snapshot["items"] for category in item["categories"]
        )
        source_counts = Counter(item["source"] for item in snapshot["items"])
        event_counts = Counter(item["event_kind"] for item in snapshot["items"])
        categories.update(category_counts)
        sources.update(source_counts)
        event_kinds.update(event_counts)
        days.append(
            {
                "date": snapshot["date"],
                "generated_at": snapshot["generated_at"],
                "since": snapshot["since"],
                "item_count": len(snapshot["items"]),
                "category_counts": dict(sorted(category_counts.items())),
                "source_counts": dict(sorted(source_counts.items())),
                "event_kind_counts": dict(sorted(event_counts.items())),
                "items": snapshot["items"],
                "health": snapshot["health"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "latest_date": days[-1]["date"] if days else None,
        "snapshot_count": len(days),
        "generated_at": days[-1]["generated_at"] if days else None,
        "facets": {
            "dates": [day["date"] for day in days],
            "categories": sorted(categories),
            "sources": sorted(sources),
            "event_kinds": sorted(event_kinds),
        },
        "days": days,
    }


def rebuild_dashboard(snapshot_dir: Path, output: Path) -> dict[str, Any]:
    value = dashboard_data(load_snapshots(snapshot_dir))
    _write_json(output, value)
    return value
