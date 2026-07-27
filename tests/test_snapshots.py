import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.snapshots import (
    SnapshotError,
    load_snapshots,
    rebuild_dashboard,
    snapshot_for_run,
    validate_snapshot,
    write_snapshot,
)


def radar_run(day: int = 27, *, title: str = "A New Evaluation Benchmark") -> RadarRun:
    generated = datetime(2026, 7, day, 12, 15, tzinfo=UTC)
    return RadarRun(
        generated_at=generated,
        since=generated - timedelta(hours=48),
        items=[
            RadarItem(
                source="arXiv",
                source_id=f"2607.{day:04d}",
                title=title,
                url=f"https://arxiv.org/abs/2607.{day:04d}",
                published_at=generated - timedelta(hours=3),
                summary="A fixture-backed benchmark release.",
                event_kind="released",
                authors=["Radar Author"],
                categories=["benchmark", "evaluation"],
                metrics={"citations": 2},
                evidence_score=2.5,
                relevance_score=2.9,
                recency_score=3.8,
                adoption_score=0.3,
                total_score=2.7,
                rationale=["Matched: benchmark", "Primary record: arXiv"],
            )
        ],
        health=[
            SourceHealth(source="arxiv", ok=True, item_count=1),
            SourceHealth(source="brave", ok=False, error="API key unavailable"),
        ],
    )


def test_snapshot_has_version_and_public_evidence_fields():
    snapshot = snapshot_for_run(radar_run())

    validate_snapshot(snapshot)

    assert snapshot["schema_version"] == 1
    assert snapshot["date"] == "2026-07-27"
    assert snapshot["items"][0]["event_kind"] == "released"
    assert "raw" not in snapshot["items"][0]


def test_same_utc_day_is_idempotent(tmp_path):
    first = radar_run(title="First run")
    second = radar_run(title="Replacement run")

    first_path = write_snapshot(first, tmp_path)
    second_path = write_snapshot(second, tmp_path)

    assert first_path == second_path
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert load_snapshots(tmp_path)[0]["items"][0]["title"] == "Replacement run"


def test_rebuild_is_deterministic(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(radar_run(26), snapshot_dir)
    write_snapshot(radar_run(27), snapshot_dir)
    output = tmp_path / "radar.json"

    first = rebuild_dashboard(snapshot_dir, output)
    first_bytes = output.read_bytes()
    second = rebuild_dashboard(snapshot_dir, output)

    assert first == second
    assert first_bytes == output.read_bytes()
    assert first["facets"]["dates"] == ["2026-07-26", "2026-07-27"]
    assert first["days"][0]["category_counts"] == {"benchmark": 1, "evaluation": 1}


def test_validation_rejects_missing_item_fields():
    snapshot = snapshot_for_run(radar_run())
    del snapshot["items"][0]["event_kind"]

    with pytest.raises(SnapshotError, match="event_kind"):
        validate_snapshot(snapshot)


def test_validation_rejects_raw_source_payloads():
    snapshot = snapshot_for_run(radar_run())
    snapshot["items"][0]["raw"] = {"private": "source payload"}

    with pytest.raises(SnapshotError, match="raw source payloads"):
        validate_snapshot(snapshot)


def test_checked_in_dashboard_data_matches_snapshots(tmp_path):
    rebuilt = rebuild_dashboard(
        snapshot_dir=Path("data/snapshots"),
        output=tmp_path / "radar.json",
    )
    checked_in = json.loads(Path("site/data/radar.json").read_text(encoding="utf-8"))

    assert checked_in == rebuilt
