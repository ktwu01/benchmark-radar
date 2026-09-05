from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from benchmark_radar.model_cards import load_registry

SCRIPT = Path("scripts/analyze_vendor_attention.py")
SPEC = Path("data/vendor_attention_audit.yml")
REGISTRY = Path("data/model_cards.yml")
COMMITTED_OUTPUT = Path("docs/technical-report/vendor-attention-audit")


def _load_module():
    spec = importlib.util.spec_from_file_location("vendor_attention_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shipped_audit_reproduces_primary_counts_and_sensitivity():
    module = _load_module()
    result = module.generate_vendor_attention_audit(registry_path=REGISTRY, spec_path=SPEC)
    audit = result["claim_audit"]
    scenarios = {row["scenario_id"]: row for row in result["scenario_summaries"]}

    assert audit["source_commit"] == "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae"
    assert audit["source_sha256"] == (
        "8b3c59a0d4c236c06e106fca474e27df665ecc33b339bca57799258805fd6e6d"
    )
    assert audit["source_commit_verified"] is True
    assert audit["analysis_end"] == "2026-08-31"
    assert audit["registry_counts"] == {
        "documents": 37,
        "organizations": 12,
        "benchmarks": 110,
    }
    assert scenarios["canonical_all_t5"]["core_count"] == 21
    assert scenarios["canonical_all_t6"]["core_count"] == 16
    assert scenarios["canonical_all_t7"]["core_count"] == 10
    assert scenarios["model_cards_only_t6"]["core_count"] == 4
    assert scenarios["latest_per_organization_t6"]["core_count"] == 3
    assert scenarios["trailing_365d_t6"]["core_count"] == 6
    assert scenarios["trailing_180d_t6"]["core_count"] == 4
    assert scenarios["trailing_90d_t6"]["core_count"] == 4
    assert scenarios["drop_newest_per_organization_t6"]["core_count"] == 9
    assert scenarios["reviewed_families_t6"]["core_count"] == 13
    assert scenarios["reviewed_families_t6"]["core_explicit_family_count"] == 5
    assert scenarios["reviewed_families_t6"]["core_singleton_count"] == 8
    assert scenarios["reviewed_families_t6"]["core_member_names"] == [
        "GPQA family",
        "SWE-bench family",
        "Humanity's Last Exam",
        "Terminal-Bench",
        "MMLU family",
        "AIME",
        "LiveCodeBench",
        "MMMU family",
        "IFEval",
        "BrowseComp family",
        "MATH-500",
        "HumanEval",
        "GSM8K",
    ]
    assert scenarios["reviewed_families_t6"]["core_members"] == [
        "gpqa_family",
        "swe_bench_family",
        "hle",
        "terminal_bench",
        "mmlu_family",
        "aime",
        "livecodebench",
        "mmmu_family",
        "ifeval",
        "browsecomp_family",
        "math_500",
        "humaneval",
        "gsm8k",
    ]

    assert audit["original_list_equals_threshold_set"] is False
    assert audit["original_list_is_subset_of_threshold_set"] is True
    assert audit["recommendation"] == "narrow"
    assert "boundary depends" in audit["replacement_claim"]
    assert audit["primary_definition"]["score_tracks_used"] is False
    assert audit["robustness"]["scenario_ids"] == [
        "canonical_all_t5",
        "canonical_all_t6",
        "canonical_all_t7",
        "model_cards_only_t6",
        "latest_per_organization_t6",
        "trailing_365d_t6",
        "trailing_180d_t6",
        "trailing_90d_t6",
        "reviewed_families_t6",
        "drop_newest_per_organization_t6",
    ]
    assert audit["robustness"]["median_jaccard"] == 0.4688
    assert audit["robustness"]["baseline_self_comparison_included"] is True
    assert audit["robustness"]["median_jaccard_excluding_baseline"] == 0.375

    membership_by_scenario = {}
    for row in result["membership_rows"]:
        membership_by_scenario.setdefault(row["scenario_id"], []).append(row)
    for scenario_id, scenario in scenarios.items():
        assert len(membership_by_scenario[scenario_id]) == scenario["benchmark_count"]
    assert len(membership_by_scenario["model_cards_only_t6"]) == 110
    assert len(membership_by_scenario["reviewed_families_t6"]) == 97
    assert any(
        row["organization_count"] == 0 and row["in_core"] is False
        for row in membership_by_scenario["model_cards_only_t6"]
    )


def test_document_edges_and_matrix_keep_provenance_and_unknowns_honest():
    module = _load_module()
    result = module.generate_vendor_attention_audit(registry_path=REGISTRY, spec_path=SPEC)

    assert result["document_edges"]
    assert all(row["document_id"] and row["document_url"] for row in result["document_edges"])
    assert all(row["raw_benchmark_id"] for row in result["document_edges"])
    assert len(result["organization_matrix"]) == 12 * 110
    statuses = {row["reported_status"] for row in result["organization_matrix"]}
    assert statuses == {"reported", "not_observed"}
    assert not any(row["reported_status"] == "absent" for row in result["organization_matrix"])

    repeated = [
        row
        for row in result["organization_matrix"]
        if row["reported_status"] == "reported" and row["support_document_count"] > 1
    ]
    assert repeated, "the fixture must exercise multiple documents from one organization"
    keys = [
        (row["organization"], row["resolved_benchmark_id"]) for row in result["organization_matrix"]
    ]
    assert len(keys) == len(set(keys)), "organization support is binary per benchmark"


def test_alias_collisions_must_resolve_through_an_explicit_reviewed_family():
    module = _load_module()
    registry = load_registry(REGISTRY)
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["families"] = [row for row in spec["families"] if row["id"] != "mmmu_family"]
    with pytest.raises(module.VendorAttentionAuditError, match="ambiguous aliases"):
        module.compile_family_projection(registry, spec)


def test_registry_content_must_match_the_pre_registered_source_hash(tmp_path):
    module = _load_module()
    changed_registry = tmp_path / "model_cards.yml"
    changed_registry.write_bytes(REGISTRY.read_bytes() + b"\n")

    with pytest.raises(module.VendorAttentionAuditError, match="registry SHA-256"):
        module.generate_vendor_attention_audit(
            registry_path=changed_registry,
            spec_path=SPEC,
        )


def test_absolute_registry_argument_emits_the_canonical_source_path():
    module = _load_module()

    result = module.generate_vendor_attention_audit(
        registry_path=REGISTRY.resolve(),
        spec_path=SPEC,
    )

    assert result["claim_audit"]["source_path"] == "data/model_cards.yml"


def test_source_commit_must_be_an_immutable_oid_resolving_to_the_registry_bytes():
    module = _load_module()
    audit = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["audit"]
    audit["source_commit"] = "deadbeef" * 5

    with pytest.raises(module.VendorAttentionAuditError, match="unable to read"):
        module.verify_registry_provenance(REGISTRY, audit)

    audit["source_commit"] = "HEAD"
    with pytest.raises(module.VendorAttentionAuditError, match="full 40-character"):
        module.verify_registry_provenance(REGISTRY, audit)


def test_original_claim_is_locked_to_the_pre_registered_eight_items(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["audit"]["original_claim"]["listed_benchmark_ids"].append("mmlu")
    path = tmp_path / "audit.yml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    with pytest.raises(module.VendorAttentionAuditError, match="preregistered claim"):
        module.load_audit_spec(path)


def test_cutoff_and_all_other_spec_bytes_are_locked_to_preregistration(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["audit"]["as_of"] = "2026-08-30"
    cutoff_path = tmp_path / "cutoff.yml"
    cutoff_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    with pytest.raises(module.VendorAttentionAuditError, match="preregistered cutoff"):
        module.load_audit_spec(cutoff_path)

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["scenarios"][0]["label"] = "Unregistered editorial change"
    hash_path = tmp_path / "hash.yml"
    hash_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    with pytest.raises(module.VendorAttentionAuditError, match="spec SHA-256"):
        module.load_audit_spec(hash_path)


def test_spec_rejects_a_missing_implementation_scenario_before_analysis(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["scenarios"] = [
        row for row in spec["scenarios"] if row["id"] != "drop_newest_per_organization_t6"
    ]
    path = tmp_path / "audit.yml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    with pytest.raises(module.VendorAttentionAuditError, match="missing required scenarios"):
        module.load_audit_spec(path)


def test_spec_rejects_a_required_scenario_with_mislabeled_semantics(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    scenario = next(row for row in spec["scenarios"] if row["id"] == "trailing_365d_t6")
    scenario["trailing_days"] = 180
    path = tmp_path / "audit.yml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    with pytest.raises(module.VendorAttentionAuditError, match="definition mismatch"):
        module.load_audit_spec(path)


def test_spec_rejects_an_extra_scenario_that_could_change_the_decision(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["scenarios"].append(
        {
            "id": "unregistered_threshold_12",
            "label": "Unregistered threshold",
            "identity": "canonical",
            "min_organizations": 12,
        }
    )
    path = tmp_path / "audit.yml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    with pytest.raises(module.VendorAttentionAuditError, match="unregistered scenarios"):
        module.load_audit_spec(path)


def test_spec_requires_the_canonical_t6_scenario_as_primary(tmp_path):
    module = _load_module()
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["audit"]["primary_scenario"] = "canonical_all_t5"
    path = tmp_path / "audit.yml"
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    with pytest.raises(module.VendorAttentionAuditError, match="primary_scenario must be"):
        module.load_audit_spec(path)


def test_family_ids_are_unique_and_disjoint_from_canonical_ids():
    module = _load_module()
    registry = load_registry(REGISTRY)
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["families"][0]["id"] = "mmlu"
    with pytest.raises(module.VendorAttentionAuditError, match="canonical benchmark id"):
        module.compile_family_projection(registry, spec)

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    spec["families"].append(dict(spec["families"][0]))
    with pytest.raises(module.VendorAttentionAuditError, match="duplicate family id"):
        module.compile_family_projection(registry, spec)


def test_time_window_is_inclusive_and_uses_revised_date():
    module = _load_module()
    registry = {
        "model_cards": [
            {
                "id": "inside",
                "organization": "A",
                "model": "M1",
                "published": "2026-08-01",
                "revised": "2026-08-31",
                "benchmarks": ["b"],
            },
            {
                "id": "boundary",
                "organization": "B",
                "model": "M2",
                "published": "2026-08-30",
                "benchmarks": ["b"],
            },
            {
                "id": "outside",
                "organization": "C",
                "model": "M3",
                "published": "2026-08-29",
                "benchmarks": ["b"],
            },
        ]
    }

    selected = module.select_cards(
        registry,
        {"trailing_days": 2},
        analysis_end=module.date.fromisoformat("2026-08-31"),
    )

    assert [row["id"] for row in selected] == ["boundary", "inside"]


def test_leave_one_out_results_expose_boundary_instability():
    module = _load_module()
    result = module.generate_vendor_attention_audit(registry_path=REGISTRY, spec_path=SPEC)
    baseline_rows = {
        row["benchmark_id"]: row
        for row in result["membership_rows"]
        if row["scenario_id"] == "canonical_all_t6" and row["in_core"]
    }

    assert len(baseline_rows) == 16
    assert any(not row["survives_every_org_omission"] for row in baseline_rows.values())
    assert any(not row["survives_every_document_omission"] for row in baseline_rows.values())
    assert all(
        row["leave_one_doc_min"] <= row["organization_count"] for row in baseline_rows.values()
    )


def test_cli_writes_deterministic_machine_readable_artifacts(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    command = [
        sys.executable,
        str(SCRIPT),
        "--registry",
        str(REGISTRY),
        "--spec",
        str(SPEC),
    ]
    subprocess.run([*command, "--output-dir", str(first)], check=True)
    subprocess.run([*command, "--output-dir", str(second)], check=True)

    expected = {
        "document-benchmark-edges.csv",
        "organization-benchmark-matrix.csv",
        "scenario-summary.csv",
        "sensitivity-membership.csv",
        "claim-audit.json",
    }
    assert {path.name for path in first.iterdir()} == expected
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    audit = json.loads((first / "claim-audit.json").read_text(encoding="utf-8"))
    assert audit["recommendation"] == "narrow"
    with (first / "scenario-summary.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert (
        next(row for row in rows if row["scenario_id"] == "canonical_all_t6")["core_count"] == "16"
    )


def test_committed_artifacts_match_a_fresh_rebuild(tmp_path):
    module = _load_module()
    result = module.generate_vendor_attention_audit(registry_path=REGISTRY, spec_path=SPEC)
    module.write_vendor_attention_artifacts(result, output_dir=tmp_path)

    for committed in sorted(COMMITTED_OUTPUT.iterdir()):
        assert committed.read_bytes() == (tmp_path / committed.name).read_bytes()


def test_pre_registered_decision_rule_controls_the_recommendation():
    module = _load_module()
    rule = {
        "exact_membership_median_jaccard": 0.8,
        "retain_requires_every_single_document_omission": True,
        "narrow_when_group_persists_but_membership_changes": True,
    }
    stable_scenarios = [{"active_orgs_threshold_ok": True, "core_count": 2}]

    retained, retained_state = module.decide_recommendation(
        original_members={"a", "b"},
        baseline_members={"a", "b"},
        median_jaccard=0.9,
        every_document_survives=True,
        scenario_summaries=stable_scenarios,
        decision_rule=rule,
    )
    narrowed, narrowed_state = module.decide_recommendation(
        original_members={"a"},
        baseline_members={"a", "b"},
        median_jaccard=0.5,
        every_document_survives=False,
        scenario_summaries=stable_scenarios,
        decision_rule=rule,
    )
    replaced, _ = module.decide_recommendation(
        original_members={"a"},
        baseline_members={"a", "b"},
        median_jaccard=0.5,
        every_document_survives=False,
        scenario_summaries=[{"active_orgs_threshold_ok": True, "core_count": 0}],
        decision_rule=rule,
    )
    removed, _ = module.decide_recommendation(
        original_members=set(),
        baseline_members=set(),
        median_jaccard=0.0,
        every_document_survives=False,
        scenario_summaries=[{"active_orgs_threshold_ok": True, "core_count": 0}],
        decision_rule=rule,
    )

    assert retained == "retain"
    assert retained_state["exact_membership_is_robust"] is True
    assert narrowed == "narrow"
    assert narrowed_state["high_support_group_persists"] is True
    assert replaced == "replace"
    assert removed == "remove"
