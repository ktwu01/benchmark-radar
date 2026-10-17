import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from benchmark_radar.catalog import artifact_identifier, normalize_snapshot
from benchmark_radar.leaderboard_snapshots import load_snapshots

ROOT = Path(__file__).resolve().parents[1]


def test_claire_artifact_urls_use_catalog_identity_anchors():
    assert artifact_identifier("https://arxiv.org/abs/2406.01574v2") == "arxiv:2406.01574"
    assert artifact_identifier("https://arxiv.org/pdf/2406.01574.pdf") == "arxiv:2406.01574"
    assert artifact_identifier("https://github.com/TIGER-AI-Lab/MMLU-Pro") == (
        "gh:tiger-ai-lab/mmlu-pro"
    )
    assert artifact_identifier("https://huggingface.co/datasets/xai-org/RealworldQA") == (
        "hf:xai-org/realworldqa"
    )
    assert artifact_identifier("https://github.com/org/repo/tree/main/data") is None


def _export_module():
    path = ROOT / "scripts" / "export_claire_radar_snapshot.py"
    spec = importlib.util.spec_from_file_location("export_claire_radar_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_preserves_every_record_with_exact_source_ids_and_review_states():
    module = _export_module()
    document = {
        "records": [
            {
                "id": "accepted",
                "name": "Accepted Bench",
                "displayEligible": True,
                "releasedAt": "2026-09-24",
                "aliases": ["Accepted Evaluation"],
                "whyItMatters": "A fixture-only extra field.",
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
            {
                "id": "unreviewed",
                "name": "Unreviewed Bench",
                "source": {
                    "id": "2609.99999",
                    "type": "arxiv",
                    "url": "https://arxiv.org/abs/2609.99999",
                },
            },
        ]
    }

    rows = module.export_rows(document)

    assert [row["benchmark_id"] for row in rows] == [
        "2609.99999",
        "github:owner/accepted",
        "github:owner/deferred",
    ]
    by_id = {row["benchmark_id"]: row for row in rows}
    assert by_id["github:owner/accepted"]["review_model"] == "claude-haiku"
    assert by_id["github:owner/accepted"]["aliases"] == '["Accepted Evaluation"]'
    assert (
        json.loads(by_id["github:owner/accepted"]["extra_json"])["whyItMatters"]
        == "A fixture-only extra field."
    )
    assert by_id["github:owner/accepted"]["display_eligible"] == "true"
    assert by_id["github:owner/deferred"]["review_state"] == "ai-name-audit-deferred"
    assert by_id["github:owner/deferred"]["display_eligible"] == "false"
    assert by_id["2609.99999"]["review_state"] == "unreviewed"
    assert by_id["2609.99999"]["display_eligible"] == "unknown"
    assert all(len(row["record_sha256"]) == 64 for row in rows)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8737",
        "http://sub.localhost/path",
        "http://127.0.0.2",
        "http://127.1",
        "http://2130706433",
        "http://0x7f000001",
        "http://0177.0.0.1",
        "http://127.0.0.1.",
        "http://2130706433.",
        "http://0x7f000001.",
        "http://0177.0.0.1.",
        "http://127%2e0%2e0%2e1",
        "http://127.0.0.1%2e",
        "http://127。0。0。1/",
        "http://１２７.０.０.１/",
        "http://ｌｏｃａｌｈｏｓｔ/",
        "http://ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/",
        "http://127%E3%80%820%E3%80%820%E3%80%821/",
        "http://exa mple.com/",
        "http://example.com:bad/",
        "http://example.com%00.evil/",
        "http://127.0.0.1\\@example.com/",
        "http://localhost\\@example.com/",
        "http://2130706433\\@example.com/",
        "http://0x7f000001\\@example.com/",
        "http://127%2e0%2e0%2e1\\@example.com/",
        "http://example.com:",
        f"http://{'1' * 4301}",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "http://0.0.0.0",
        "http://[::]",
        "http://[",
    ],
)
def test_export_rejects_local_or_malformed_project_links(url):
    module = _export_module()
    document = {
        "records": [
            {
                "id": "local-project",
                "name": "Local Project Bench",
                "source": {
                    "id": "github:owner/local-project",
                    "type": "github",
                    "url": "https://github.com/owner/local-project",
                },
                "links": {"project": url},
            }
        ]
    }

    [row] = module.export_rows(document)

    assert row["project_url"] == ""


def test_registered_snapshot_preserves_review_provenance_and_links():
    snapshots = load_snapshots()
    snapshot = next(row for row in snapshots["snapshots"] if row["id"] == "claire_radar_2026-10-14")

    normalized = normalize_snapshot(snapshot)

    assert normalized["validation"]["source_record_count"] == 2447
    assert normalized["validation"]["score_observation_count"] == 0
    assert normalized["validation"]["score_series_count"] == 0
    assert len(normalized["validation"]["benchmarks_with_zero_observations"]) == 2447
    record = next(
        row
        for row in normalized["source_records"]
        if row["source_benchmark_id"] == "github:liningbest/apitest"
    )
    assert record["key"] == "claire-radar:github:liningbest/apitest"
    assert record["released"] == "2026-09-13"
    assert record["released_reference"]["source_url"] == "https://github.com/liningbest/apitest"
    # Upstream re-reviewed this record between the 2026-09-25 and 2026-10-14
    # exports; the snapshot carries its current state.
    assert record["provenance"]["review_state"] == "ai-name-audit-deferred"
    assert record["provenance"]["origin_source"] == "github"
    assert record["provenance"]["display_eligible"] == "false"
    assert {item["kind"] for item in record["artifacts"]} == {"repo"}
    assert record["artifacts"][0]["id"] == "gh:liningbest/apitest"
    assert record["source_metadata"]["claire_radar"]["id"] == "bm_apitest_7d8e6901"
    assert record["source_metadata"]["claire_radar"]["whyItMatters"]

    unreviewed = next(
        row for row in normalized["source_records"] if row["source_benchmark_id"] == "2608.16081"
    )
    assert unreviewed["name"] == "SafeGesture"
    assert unreviewed["provenance"]["review_state"] == "unreviewed"
    assert unreviewed["provenance"]["display_eligible"] == "unknown"
    for item in normalized["source_records"]:
        assert all("localhost" not in artifact["url"] for artifact in item["artifacts"])
        assert all("127.0.0.1" not in artifact["url"] for artifact in item["artifacts"])


def test_registered_snapshot_declares_source_neutral_normalization_contract():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )

    assert snapshot["score_series_policy"] == "observed_only"
    assert snapshot["catalog_adapter"] == "claire_radar_v1"
    assert snapshot["adapter_options"]["first_public_evidence"] == {
        "2607.05155": "https://edge-bench.org/",
        "2607.07946": "https://datacurve.ai/research",
        "2608.00267": "https://github.com/microsoft/Loopsbench",
    }
    assert "release_evidence" not in snapshot


def test_claire_adapter_translates_every_private_release_date():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )
    records = {
        row["source_benchmark_id"]: row for row in normalize_snapshot(snapshot)["source_records"]
    }
    rows_with_dates = {
        row["benchmark_id"]: json.loads(row["extra_json"])["releaseDates"]
        for row in snapshot["benchmark_rows"]
        if (json.loads(row["extra_json"]).get("releaseDates") or {}).get("firstPublicAt")
    }

    assert len(rows_with_dates) == 6
    for source_id, dates in rows_with_dates.items():
        record = records[source_id]
        assert record["released"] == dates["firstPublicAt"]
        assert record["released_reference"]["basis"] == "first_public"
        if dates.get("paperV1At"):
            assert record["publication_dates"][0]["date"] == dates["paperV1At"]
            assert record["publication_dates"][0]["basis"] == "paper_first_version"


def test_catalog_normalizer_contains_no_claire_private_schema_or_series_branch():
    source = (ROOT / "src" / "benchmark_radar" / "catalog.py").read_text(encoding="utf-8")

    assert "releaseDates" not in source
    assert "firstPublicAt" not in source
    assert "paperV1At" not in source
    assert 'source != "claire_radar"' not in source


def test_claire_dates_distinguish_first_public_evidence_from_paper_dates():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )
    records = {row["name"]: row for row in normalize_snapshot(snapshot)["source_records"]}

    expected = {
        "DeepSWE": ("2026-05-18", "2026-07-08", "https://datacurve.ai/research"),
        "LoopsBench": ("2026-07-03", "2026-07-31", "https://github.com/microsoft/Loopsbench"),
        "EdgeBench": ("2026-07-02", "2026-07-06", "https://edge-bench.org/"),
    }
    for name, (released, paper_date, source_url) in expected.items():
        record = records[name]
        assert record["source_metadata"]["claire_radar"]["releaseDates"] == {
            "firstPublicAt": released,
            "paperV1At": paper_date,
        }
        assert record["released"] == released
        assert record["released_reference"] == {
            "source_key": record["key"],
            "source_url": source_url,
            "basis": "first_public",
        }
        assert record["publication_dates"] == [
            {
                "date": paper_date,
                "basis": "paper_first_version",
                "source_url": next(
                    artifact["url"]
                    for artifact in record["artifacts"]
                    if artifact["kind"] == "paper"
                ),
            }
        ]


def test_registered_snapshot_retains_every_original_object_losslessly():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )

    originals = []
    for row in snapshot["benchmark_rows"]:
        original = json.loads(row["extra_json"])
        payload = json.dumps(
            original, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        assert hashlib.sha256(payload).hexdigest() == row["record_sha256"]
        assert original["id"] == row["origin_record_id"]
        originals.append(original["id"])

    assert len(originals) == 2447
    assert len(set(originals)) == 2447


def test_refresh_carries_forward_records_the_upstream_window_dropped():
    # The 2026-10-14 upstream export no longer listed 156 reviewed,
    # display-eligible records from the 2026-09-25 export (AgroVG, KGI-Bench,
    # ...). A source that stops repeating a record must not delete it from the
    # corpus, so the exporter copies those rows unchanged.
    module = _export_module()
    exported = [{"benchmark_id": "b", **{field: "new" for field in module.FIELDS[1:]}}]
    previous = [
        {field: "old-a" if field != "benchmark_id" else "a" for field in module.FIELDS},
        {field: "old-b" if field != "benchmark_id" else "b" for field in module.FIELDS},
    ]

    rows = module.carry_forward(exported, previous)

    assert [row["benchmark_id"] for row in rows] == ["a", "b"]
    assert rows[0] == previous[0]
    assert rows[1]["name"] == "new"


def test_registered_snapshot_keeps_every_record_of_the_previous_export():
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )
    ids = {row["benchmark_id"] for row in snapshot["benchmark_rows"]}

    # Records only the previous export listed, kept by carry-forward.
    for source_id in ("2605.22034", "2605.22304", "2605.24043"):
        assert source_id in ids


def test_carried_forward_rows_keep_their_original_crawl_time():
    # The upstream 2026-10-14 export no longer listed these rows, so they were
    # last collected on 2026-09-25; labelling them with the new crawl would
    # claim a collection that never happened.
    snapshot = next(
        row for row in load_snapshots()["snapshots"] if row["id"] == "claire_radar_2026-10-14"
    )
    records = {
        row["source_benchmark_id"]: row for row in normalize_snapshot(snapshot)["source_records"]
    }
    [carried] = snapshot["adapter_options"]["carried_forward"]
    assert len(carried["benchmark_ids"]) == 156
    assert records["2605.22034"]["provenance"]["crawled_at"] == "2026-09-25T04:40:22Z"
    assert records["2608.16081"]["provenance"]["crawled_at"] == "2026-10-14T09:44:51Z"


def test_a_row_in_two_carried_forward_cohorts_is_rejected():
    from benchmark_radar.catalog_snapshot_adapters import (
        CatalogSnapshotAdapterError,
        adapt_catalog_row,
    )

    row = {"benchmark_id": "x", "extra_json": "{}"}
    cohort = {"from_snapshot": "a", "crawled_at": "2026-01-01T00:00:00Z", "benchmark_ids": ["x"]}
    with pytest.raises(CatalogSnapshotAdapterError):
        adapt_catalog_row(
            row,
            adapter="claire_radar_v1",
            adapter_options={"carried_forward": [cohort, {**cohort, "from_snapshot": "b"}]},
            snapshot_id="s",
        )
    adapted = adapt_catalog_row(
        row,
        adapter="claire_radar_v1",
        adapter_options={"carried_forward": [cohort]},
        snapshot_id="s",
    )
    assert adapted["crawled_at"] == "2026-01-01T00:00:00Z"


def test_refresh_moves_returned_records_out_of_old_cohorts():
    # A carried record that upstream lists again was just recollected; leaving
    # it in its old cohort would stamp the fresh row with the old crawl time.
    module = _export_module()
    cohorts = [
        {"from_snapshot": "s1", "crawled_at": "2026-09-25T00:00:00Z", "benchmark_ids": ["a", "b"]}
    ]

    updated = module.update_cohorts(
        cohorts,
        upstream_ids={"b", "x"},
        carried_ids={"a", "c"},
        from_snapshot="s2",
        crawled_at="2026-10-14T00:00:00Z",
    )

    assert updated == [
        {"from_snapshot": "s1", "crawled_at": "2026-09-25T00:00:00Z", "benchmark_ids": ["a"]},
        {"from_snapshot": "s2", "crawled_at": "2026-10-14T00:00:00Z", "benchmark_ids": ["c"]},
    ]
