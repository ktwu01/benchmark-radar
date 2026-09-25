import importlib.util
from pathlib import Path

from benchmark_radar.catalog import normalize_snapshot
from benchmark_radar.leaderboard_snapshots import load_snapshots

ROOT = Path(__file__).resolve().parents[1]


def _export_module():
    path = ROOT / "scripts" / "export_claire_radar_snapshot.py"
    spec = importlib.util.spec_from_file_location("export_claire_radar_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_includes_only_admitted_records_with_exact_source_ids():
    module = _export_module()
    document = {
        "records": [
            {
                "id": "accepted",
                "name": "Accepted Bench",
                "displayEligible": True,
                "releasedAt": "2026-09-24",
                "source": {
                    "id": "github:owner/accepted",
                    "type": "github",
                    "url": "https://github.com/owner/accepted",
                },
                "curation": {
                    "state": "ai-reviewed",
                    "reviewedAt": "2026-09-24T12:00:00Z",
                    "model": "claude-haiku",
                },
            },
            {
                "id": "deferred",
                "name": "Deferred Bench",
                "displayEligible": False,
                "source": {
                    "id": "github:owner/deferred",
                    "type": "github",
                    "url": "https://github.com/owner/deferred",
                },
                "curation": {"state": "ai-name-audit-deferred"},
            },
        ]
    }

    rows = module.export_rows(document)

    assert [row["benchmark_id"] for row in rows] == ["github:owner/accepted"]
    assert rows[0]["review_model"] == "claude-haiku"
    assert len(rows[0]["record_sha256"]) == 64


def test_registered_snapshot_preserves_review_provenance_and_links():
    snapshots = load_snapshots()
    snapshot = next(row for row in snapshots["snapshots"] if row["id"] == "claire_radar_2026-09-25")

    normalized = normalize_snapshot(snapshot)

    assert normalized["validation"]["source_record_count"] == 477
    assert normalized["validation"]["score_observation_count"] == 0
    record = next(
        row
        for row in normalized["source_records"]
        if row["source_benchmark_id"] == "github:liningbest/apitest"
    )
    assert record["key"] == "claire-radar:github:liningbest/apitest"
    assert record["released"] == "2026-09-13"
    assert record["provenance"]["review_state"] == "ai-reviewed"
    assert record["provenance"]["origin_source"] == "github"
    assert {item["kind"] for item in record["artifacts"]} == {"repo"}
