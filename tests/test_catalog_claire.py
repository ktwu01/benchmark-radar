import copy
import json
from pathlib import Path

from benchmark_radar.catalog import build_benchmark_index
from benchmark_radar.catalog_claire import anchor, folded, load_bundle, merge_library, selected


def existing(key="llm-stats:sample"):
    return {
        "key": key,
        "slug": "sample",
        "name": "Sample",
        "source": "llm_stats",
        "source_benchmark_id": "sample",
        "categories": ["existing"],
        "aliases": [],
        "artifacts": [],
        "description": {"en": "Source text"},
        "released": "2024-01-01",
    }


def bundle(*rows):
    return {
        "public_revision": "abc",
        "inputs": [],
        "manifests": {},
        "records": [
            {"id": row["id"], "versions": {"public/library_index.json": row}} for row in rows
        ],
    }


def test_exact_catalog_match_keeps_old_scores_and_complete_new_fields():
    old = existing()
    original = copy.deepcopy(old)
    incoming = {
        "id": "c1",
        "name": "Sample",
        "catalogSources": [{"catalog": "llm-stats", "sourceId": "sample"}],
        "libraryCategories": ["science"],
        "releasedAt": "2025-02-03",
        "attention": {"githubStars": 123},
        "unknown_future_field": {"arbitrary": [1, 2]},
        "description": "AI generated prose",
        "displayEligible": False,
    }
    records, report = merge_library([old], bundle(incoming))
    assert len(records) == 1
    assert old == original
    assert records[0]["released"] == "2024-01-01"
    assert records[0]["description"] == {"en": "Source text"}
    assert records[0]["categories"] == ["existing", "science"]
    assert (
        records[0]["extensions"]["claire_radar"]["records"][0]["versions"][
            "public/library_index.json"
        ]
        == incoming
    )
    assert report["conflicts"][0]["field"] == "released"


def test_punctuation_versions_and_one_shared_paper_do_not_merge():
    assert folded("HumanEval-X++") != folded("HumanEval-X")
    old = existing()
    old["artifacts"] = [
        {"kind": "paper", "id": "arxiv:2601.12345", "url": "https://arxiv.org/abs/2601.12345"}
    ]
    records, report = merge_library(
        [old],
        bundle(
            {
                "id": "c1",
                "name": "Sample",
                "links": {"paper": "https://arxiv.org/pdf/2601.12345v2.pdf"},
            }
        ),
    )
    assert len(records) == 2
    assert report["actions"] == {"add": 1}


def test_multiple_exact_targets_remain_inspectable_without_transferring_scores():
    records, report = merge_library(
        [existing("llm-stats:a"), existing("llm-stats:b")],
        bundle(
            {
                "id": "c1",
                "name": "Sample",
                "catalogSources": [
                    {"catalog": "llm-stats", "sourceId": "a"},
                    {"catalog": "llm-stats", "sourceId": "b"},
                ],
            }
        ),
    )
    assert len(records) == 3
    assert report["actions"] == {"add_ambiguous": 1}


def test_duplicate_exact_identity_keeps_both_inputs_and_category_union():
    rows = [
        {
            "id": key,
            "name": "Sample",
            "source": {"type": "arxiv", "id": "2601.12345"},
            "topics": [key],
        }
        for key in ["a", "b"]
    ]
    records, report = merge_library([], bundle(*rows))
    assert len(records) == 1
    assert records[0]["categories"] == ["a", "b"]
    assert len(records[0]["extensions"]["claire_radar"]["records"]) == 2
    assert report["actions"] == {"add": 1, "deduplicate_import": 1}


def test_frozen_import_has_total_field_and_category_coverage():
    frozen = load_bundle()
    records, report = merge_library([], frozen)
    recovered = {
        entry["id"]: entry
        for record in records
        for entry in record["extensions"]["claire_radar"]["records"]
    }
    assert recovered == {entry["id"]: entry for entry in frozen["records"]}
    assert sum(report["actions"].values()) == report["input_count"]
    targets = {r["key"]: r for r in records}
    for decision in report["decisions"]:
        assert set(decision["categories"]) <= set(targets[decision["target_key"]]["categories"])
    for record in records:
        if record["provenance"]["local_only"]:
            assert record["provenance"]["source_revision"] == "working-tree"
    index = build_benchmark_index(records)
    assert len(index) == len(records)
    assert len({r["slug"] for r in index}) == len(index)


def test_resource_anchor_does_not_treat_repository_subpath_as_whole_repo():
    assert anchor("https://github.com/Owner/Repo") == "gh:owner/repo"
    assert anchor("https://github.com/Owner/Repo/tree/main/variant") is None


def test_raw_source_url_fills_index_projection_without_overwriting_index():
    entry = {
        "id": "a",
        "versions": {
            "public/library_index.json": {
                "name": "Index",
                "source": {"id": "a"},
                "links": {"paper": "https://example.org/paper"},
            },
            "public/benchmarks.json": {
                "name": "Raw",
                "source": {"id": "b", "url": "https://example.org/source"},
                "links": {"code": "https://github.com/example/repo"},
            },
        },
    }
    row = selected(entry)
    assert row["name"] == "Index"
    assert row["source"] == {"id": "a", "url": "https://example.org/source"}
    assert len(row["links"]) == 2


def test_org_category_spelling_primary_order_and_unknown_date_are_preserved():
    old = existing()
    old["categories"] = ["reasoning", "agents"]
    old["released"] = None
    rows, _ = merge_library(
        [old],
        bundle(
            {
                "id": "a",
                "name": "Sample",
                "catalogSources": [{"catalog": "llm-stats", "sourceId": "sample"}],
                "topics": ["Agents", "Reasoning", "Finance"],
                "releasedAt": "2020-01-01",
                "source": {"url": "https://example.org/source"},
            }
        ),
    )
    assert rows[0]["categories"] == ["reasoning", "agents", "Finance"]
    assert rows[0]["released"] is None


def test_two_resource_types_and_exact_name_merge_without_changing_scores():
    old = existing()
    old["scores"] = [{"model": "example", "value": 23.5, "protocol": "original"}]
    old["artifacts"] = [
        {"kind": "paper", "url": "https://arxiv.org/abs/2601.12345"},
        {"kind": "repo", "url": "https://github.com/example/repo"},
    ]
    records, report = merge_library(
        [old],
        bundle(
            {
                "id": "a",
                "name": "Sample",
                "links": {
                    "paper": "https://arxiv.org/pdf/2601.12345",
                    "code": "https://github.com/example/repo",
                },
            }
        ),
    )
    assert len(records) == 1
    assert records[0]["scores"] == old["scores"]
    assert report["decisions"][0]["basis"] == "exact_name_and_two_resource_types"


def test_placeholder_and_imprecise_dates_stay_in_original_fields_only():
    for date, precision in [
        ("0001-01-01", "unknown"),
        ("2025-02-01", "month"),
        ("2025-01-01", "year"),
        ("invalid", None),
    ]:
        records, report = merge_library(
            [],
            bundle({"id": "a", "name": "A", "releasedAt": date, "releaseDatePrecision": precision}),
        )
        assert records[0]["released"] is None
        assert report["unmapped_dates"][0]["value"] == date
        assert (
            records[0]["extensions"]["claire_radar"]["records"][0]["versions"][
                "public/library_index.json"
            ]["releasedAt"]
            == date
        )


def test_published_shards_preserve_every_original_record_and_org_observation():
    shards = [json.loads(path.read_text()) for path in Path("site/data/benchmarks").glob("*.json")]
    assert shards, "Run normalize-catalog before the integration checks"
    by_key = {shard["record"]["key"]: shard for shard in shards}
    recovered = {}
    for shard in shards:
        record = shard["record"]
        if record["source"] == "claire_radar":
            assert not shard["scores_by_source"]
        for entry in record.get("extensions", {}).get("claire_radar", {}).get("records", []):
            assert entry["id"] not in recovered
            recovered[entry["id"]] = entry
    assert recovered == {entry["id"]: entry for entry in load_bundle()["records"]}
    for path in Path("data/catalog").glob("*_source_records.jsonl"):
        for line in path.read_text().splitlines():
            original = json.loads(line)
            record = by_key[original["key"]]["record"]
            for field in ("key", "slug", "source", "source_benchmark_id", "name"):
                assert record[field] == original[field]
            assert set(original.get("categories") or []) <= set(record["categories"])
            if original.get("released"):
                assert record["released"] == original["released"]
    expected = {}
    for path in Path("data/catalog").glob("*_score_observations.jsonl"):
        for line in path.read_text().splitlines():
            observation = json.loads(line)
            expected[observation["obs_id"]] = observation
    actual = {
        row["obs_id"]: row
        for shard in shards
        for partition in shard["scores_by_source"].values()
        for row in partition["rows"]
    }
    assert actual == expected
