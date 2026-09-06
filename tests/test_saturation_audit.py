import json
from pathlib import Path

from benchmark_radar.saturation_audit import (
    _claim_recommendation,
    _selected_protocol_series,
    build_saturation_audit,
)


def test_section_6_2_audit_separates_raw_and_repeated_protocol_evidence() -> None:
    audit = build_saturation_audit()
    rows = {row["benchmark_id"]: row for row in audit["benchmarks"]}

    assert audit["schema_version"] == 2
    assert audit["benchmark_count"] == 8
    assert audit["summary"] == {
        "raw_best_repeated": 0,
        "raw_best_isolated": 8,
        "repeated_setup_available": 4,
        "repeated_setup_unknown": 4,
    }
    assert rows["aime"]["raw_headroom"] == 0.8
    assert rows["aime"]["repeat_controlled_headroom"] == 20.2
    assert rows["aime"]["recommendation"] == "replace"
    assert rows["hmmt"]["repeat_controlled_headroom"] == 4.8
    assert rows["hmmt"]["recommendation"] == "qualify"
    assert rows["math_500"]["recommendation"] == "qualify"
    assert rows["swe_bench_verified"]["repeat_controlled_headroom"] == 19.4
    assert rows["tau2_bench"]["recommendation"] == "qualify"
    assert all(not row["raw_best_stratum"]["connectable"] for row in rows.values())
    assert all(row["recommended_wording"] for row in rows.values())

    raw = audit["threshold_sensitivity"]["raw"]
    repeated = audit["threshold_sensitivity"]["repeated_protocol_series"]
    assert raw == {
        "eligible": 8,
        "unknown": 0,
        "hits": {"<=5": 8, "<=3": 4, "<=2": 3},
    }
    assert repeated == {
        "eligible": 4,
        "unknown": 4,
        "hits": {"<=5": 1, "<=3": 0, "<=2": 0},
    }


def test_claim_recommendations_follow_the_predeclared_rule() -> None:
    assert _claim_recommendation(raw_best_repeated=True, repeated_headroom=20.0) == "retain"
    assert _claim_recommendation(raw_best_repeated=False, repeated_headroom=None) == "qualify"
    assert _claim_recommendation(raw_best_repeated=False, repeated_headroom=4.0) == "qualify"
    assert _claim_recommendation(raw_best_repeated=False, repeated_headroom=6.0) == "replace"


def test_section_6_2_json_artifact_matches_the_helper() -> None:
    path = Path("docs/technical-report/saturation-audit-6.2.json")
    assert json.loads(path.read_text(encoding="utf-8")) == build_saturation_audit()


def test_unjoinable_observations_are_explicitly_excluded() -> None:
    audit = build_saturation_audit()
    rows = {row["benchmark_id"]: row for row in audit["benchmarks"]}
    for benchmark_id in ("math_500", "mathvision", "tau2_bench"):
        row = rows[benchmark_id]
        assert row["selected_repeated_series"] is None
        assert len(row["exclusions"]) == len(row["score_ids"])
        assert all("no instrument+protocol" in item["reason"] for item in row["exclusions"])
    assert rows["aime"]["counterexamples"][0]["value"] == 99.2
    assert rows["swe_bench_verified"]["counterexamples"][0]["value"] == 96.0


def test_selected_repeated_evidence_keeps_its_scope_limit() -> None:
    audit = build_saturation_audit()
    rows = {row["benchmark_id"]: row for row in audit["benchmarks"]}

    for benchmark_id in ("aime", "arena_hard", "hmmt", "swe_bench_verified"):
        selected = rows[benchmark_id]["selected_repeated_series"]
        assert selected["dated_points"] == 2
        assert selected["organization_count"] == 1
        assert selected["single_organization"] is True
        assert "paired comparison" in rows[benchmark_id]["uncertainty"][-1]


def test_lower_is_better_selects_the_lowest_series_best() -> None:
    def series(value: float, key: str) -> dict:
        return {
            "connectable": True,
            "dated_points": 2,
            "point_count": 2,
            "last_reported_at": "2026-08-01",
            "instrument": key,
            "protocol": "p",
            "points": [
                {
                    "value": value,
                    "reported_at": "2026-08-01",
                    "observation_id": key,
                    "organization": key,
                    "model": key,
                }
            ],
        }

    record = {
        "direction": "lower_is_better",
        "series": [series(9.0, "weak"), series(3.0, "strong")],
    }
    assert _selected_protocol_series(record)["instrument"] == "strong"
