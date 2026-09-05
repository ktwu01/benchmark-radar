#!/usr/bin/env python3
"""Reproduce and stress-test the technical report's vendor-attention claim."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from benchmark_radar.model_cards import load_registry

DEFAULT_REGISTRY = Path("data/model_cards.yml")
DEFAULT_SPEC = Path("data/vendor_attention_audit.yml")
DEFAULT_OUTPUT_DIR = Path("docs/technical-report/vendor-attention-audit")
PRIMARY_SCENARIO_ID = "canonical_all_t6"
ANALYSIS_END_DATE = "2026-08-31"
EXPECTED_SPEC_SHA256 = "66b64ce9b8f423ae5f161672099ded01e5ba93e020087d91da3dd190d3b9747e"
ORIGINAL_CLAIM_TEXT = "Vendor attention has converged on a small reporting core."
ORIGINAL_SELECTION_TEXT = "Eight benchmarks appear in documents from at least six organizations."
ORIGINAL_CLAIM_IDS = (
    "gpqa_diamond",
    "hle",
    "swe_bench_verified",
    "terminal_bench",
    "aime",
    "livecodebench",
    "mmlu_pro",
    "browsecomp",
)
REQUIRED_SCENARIO_DEFINITIONS = {
    "canonical_all_t5": ("canonical", 5, (), None, False, False),
    "canonical_all_t6": ("canonical", 6, (), None, False, False),
    "canonical_all_t7": ("canonical", 7, (), None, False, False),
    "model_cards_only_t6": ("canonical", 6, ("model_card",), None, False, False),
    "latest_per_organization_t6": ("canonical", 6, (), None, True, False),
    "trailing_365d_t6": ("canonical", 6, (), 365, False, False),
    "trailing_180d_t6": ("canonical", 6, (), 180, False, False),
    "trailing_90d_t6": ("canonical", 6, (), 90, False, False),
    "reviewed_families_t6": ("family", 6, (), None, False, False),
    "drop_newest_per_organization_t6": ("canonical", 6, (), None, False, True),
}
REQUIRED_SCENARIO_IDS = frozenset(REQUIRED_SCENARIO_DEFINITIONS)


class VendorAttentionAuditError(ValueError):
    """Raised when reviewed audit inputs are incomplete or contradictory."""


def _iso_date(value: Any, *, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise VendorAttentionAuditError(f"{label} must be YYYY-MM-DD") from error


def load_audit_spec(path: Path = DEFAULT_SPEC) -> dict[str, Any]:
    raw_spec = path.read_bytes()
    payload = yaml.safe_load(raw_spec.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise VendorAttentionAuditError("vendor-attention spec must use schema_version 1")
    audit = payload.get("audit")
    scenarios = payload.get("scenarios")
    families = payload.get("families")
    if not isinstance(audit, dict) or not isinstance(scenarios, list) or not scenarios:
        raise VendorAttentionAuditError("spec requires audit metadata and scenarios")
    if not isinstance(families, list):
        raise VendorAttentionAuditError("spec families must be a list")
    required = {
        "issue_number",
        "issue_url",
        "preregistration_url",
        "source_commit",
        "source_sha256",
        "as_of",
        "contributor",
        "primary_scenario",
        "original_claim",
        "decision_rule",
    }
    missing = sorted(required - audit.keys())
    if missing:
        raise VendorAttentionAuditError(f"spec audit metadata missing: {', '.join(missing)}")
    _iso_date(audit["as_of"], label="audit.as_of")
    if str(audit["as_of"]) != ANALYSIS_END_DATE:
        raise VendorAttentionAuditError(
            f"audit.as_of must be the preregistered cutoff {ANALYSIS_END_DATE}"
        )
    source_commit = str(audit["source_commit"])
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise VendorAttentionAuditError(
            "source_commit must be a full 40-character commit object ID"
        )
    original_claim = audit["original_claim"]
    if not isinstance(original_claim, dict):
        raise VendorAttentionAuditError("original_claim must be a mapping")
    actual_claim = (
        str(original_claim.get("text") or ""),
        str(original_claim.get("selection_text") or ""),
        tuple(map(str, original_claim.get("listed_benchmark_ids") or [])),
    )
    expected_claim = (ORIGINAL_CLAIM_TEXT, ORIGINAL_SELECTION_TEXT, ORIGINAL_CLAIM_IDS)
    if actual_claim != expected_claim:
        raise VendorAttentionAuditError("original_claim does not match the preregistered claim")
    scenario_ids = [str(row.get("id") or "") for row in scenarios]
    if any(not value for value in scenario_ids) or len(scenario_ids) != len(set(scenario_ids)):
        raise VendorAttentionAuditError("scenario ids must be non-empty and unique")
    missing_scenarios = sorted(REQUIRED_SCENARIO_IDS - set(scenario_ids))
    if missing_scenarios:
        raise VendorAttentionAuditError(
            "spec is missing required scenarios: " + ", ".join(missing_scenarios)
        )
    extra_scenarios = sorted(set(scenario_ids) - REQUIRED_SCENARIO_IDS)
    if extra_scenarios:
        raise VendorAttentionAuditError(
            "spec contains unregistered scenarios: " + ", ".join(extra_scenarios)
        )
    scenarios_by_id = {str(row["id"]): row for row in scenarios}
    for scenario_id, expected in REQUIRED_SCENARIO_DEFINITIONS.items():
        row = scenarios_by_id[scenario_id]
        actual = (
            str(row.get("identity") or "canonical"),
            int(row.get("min_organizations") or 0),
            tuple(map(str, row.get("document_types") or [])),
            int(row["trailing_days"]) if row.get("trailing_days") is not None else None,
            bool(row.get("latest_per_organization")),
            bool(row.get("drop_newest_per_organization")),
        )
        if actual != expected:
            raise VendorAttentionAuditError(
                f"scenario {scenario_id} definition mismatch: expected {expected}, got {actual}"
            )
    if audit["primary_scenario"] not in scenario_ids:
        raise VendorAttentionAuditError("primary_scenario must name a declared scenario")
    if audit["primary_scenario"] != PRIMARY_SCENARIO_ID:
        raise VendorAttentionAuditError(
            f"primary_scenario must be {PRIMARY_SCENARIO_ID}, got {audit['primary_scenario']}"
        )
    actual_spec_sha256 = hashlib.sha256(raw_spec).hexdigest()
    if actual_spec_sha256 != EXPECTED_SPEC_SHA256:
        raise VendorAttentionAuditError(
            "audit spec SHA-256 does not match the preregistered definition: "
            f"expected {EXPECTED_SPEC_SHA256}, got {actual_spec_sha256}"
        )
    return payload


def effective_card_date(card: dict[str, Any]) -> date:
    value = card.get("revised") or card.get("published")
    if not value:
        raise VendorAttentionAuditError(f"model card {card.get('id')} has no effective date")
    return _iso_date(value, label=f"model card {card.get('id')} effective date")


def _fold_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in normalized if character.isalnum())


def build_alias_collision_index(registry: dict[str, Any]) -> dict[str, list[str]]:
    identities: dict[str, set[str]] = defaultdict(set)
    for benchmark in registry["benchmarks"]:
        benchmark_id = str(benchmark["id"])
        for value in [str(benchmark["name"]), *map(str, benchmark.get("aliases") or [])]:
            folded = _fold_identity(value)
            if folded:
                identities[folded].add(benchmark_id)
    return {
        identity: sorted(benchmark_ids)
        for identity, benchmark_ids in sorted(identities.items())
        if len(benchmark_ids) > 1
    }


def compile_family_projection(
    registry: dict[str, Any], spec: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str], list[dict[str, Any]]]:
    benchmark_ids = {str(row["id"]) for row in registry["benchmarks"]}
    projection = {benchmark_id: benchmark_id for benchmark_id in benchmark_ids}
    names = {str(row["id"]): str(row["name"]) for row in registry["benchmarks"]}
    reviewed_families: list[dict[str, Any]] = []
    assigned: dict[str, str] = {}
    family_ids: set[str] = set()
    for family in spec["families"]:
        family_id = str(family.get("id") or "")
        family_name = str(family.get("name") or "")
        members = [str(value) for value in family.get("benchmark_ids") or []]
        evidence = [str(value) for value in family.get("evidence") or []]
        if not family_id or not family_name or not members or not evidence:
            raise VendorAttentionAuditError(
                "every reviewed family requires id, name, benchmark_ids, and evidence"
            )
        if family_id in benchmark_ids:
            raise VendorAttentionAuditError(
                f"family id {family_id} collides with a canonical benchmark id"
            )
        if family_id in family_ids:
            raise VendorAttentionAuditError(f"duplicate family id: {family_id}")
        family_ids.add(family_id)
        unknown = sorted(set(members) - benchmark_ids)
        if unknown:
            raise VendorAttentionAuditError(
                f"family {family_id} references unknown benchmarks: {', '.join(unknown)}"
            )
        if len(members) < 2:
            # Single-member mappings remain canonical singletons; only multi-ID
            # projections count as reviewed families in the sensitivity output.
            continue
        for benchmark_id in members:
            if benchmark_id in assigned:
                raise VendorAttentionAuditError(
                    f"benchmark {benchmark_id} belongs to both "
                    f"{assigned[benchmark_id]} and {family_id}"
                )
            assigned[benchmark_id] = family_id
            projection[benchmark_id] = family_id
        names[family_id] = family_name
        reviewed_families.append(
            {
                "family_id": family_id,
                "family_name": family_name,
                "benchmark_ids": sorted(members),
                "evidence": evidence,
                "note": str(family.get("note") or ""),
            }
        )

    collisions = build_alias_collision_index(registry)
    unresolved = {
        alias: members
        for alias, members in collisions.items()
        if len({projection[member] for member in members}) != 1
    }
    if unresolved:
        detail = "; ".join(f"{alias}: {','.join(ids)}" for alias, ids in unresolved.items())
        raise VendorAttentionAuditError(
            "ambiguous aliases must be resolved by one reviewed family: " + detail
        )
    return projection, names, reviewed_families


def select_cards(
    registry: dict[str, Any], scenario: dict[str, Any], *, analysis_end: date
) -> list[dict[str, Any]]:
    cards = [card for card in registry["model_cards"] if effective_card_date(card) <= analysis_end]
    allowed_types = {str(value) for value in scenario.get("document_types") or []}
    if allowed_types:
        cards = [
            card
            for card in cards
            if str(card.get("document_type") or "model_card") in allowed_types
        ]
    if scenario.get("trailing_days") is not None:
        days = int(scenario["trailing_days"])
        if days <= 0:
            raise VendorAttentionAuditError("trailing_days must be positive")
        start = analysis_end - timedelta(days=days - 1)
        cards = [card for card in cards if effective_card_date(card) >= start]

    def newest_by_organization(values: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        newest: dict[str, dict[str, Any]] = {}
        for card in values:
            organization = str(card["organization"])
            current = newest.get(organization)
            key = (effective_card_date(card), str(card["id"]))
            if current is None or key > (effective_card_date(current), str(current["id"])):
                newest[organization] = card
        return newest

    if scenario.get("latest_per_organization"):
        cards = list(newest_by_organization(cards).values())
    elif scenario.get("drop_newest_per_organization"):
        excluded = {str(card["id"]) for card in newest_by_organization(cards).values()}
        cards = [card for card in cards if str(card["id"]) not in excluded]
    return sorted(cards, key=lambda card: (effective_card_date(card), str(card["id"])))


def build_document_edges(
    cards: list[dict[str, Any]],
    registry: dict[str, Any],
    *,
    projection: dict[str, str] | None = None,
    resolved_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    benchmarks = {str(row["id"]): row for row in registry["benchmarks"]}
    projection = projection or {benchmark_id: benchmark_id for benchmark_id in benchmarks}
    resolved_names = resolved_names or {
        benchmark_id: str(row["name"]) for benchmark_id, row in benchmarks.items()
    }
    rows: list[dict[str, Any]] = []
    for card in cards:
        for benchmark_id in sorted({str(value) for value in card["benchmarks"]}):
            resolved_id = projection[benchmark_id]
            rows.append(
                {
                    "document_id": str(card["id"]),
                    "document_url": str(card["url"]),
                    "organization": str(card["organization"]),
                    "model": str(card["model"]),
                    "document_type": str(card.get("document_type") or "model_card"),
                    "effective_date": effective_card_date(card).isoformat(),
                    "retrieved_at": str(card.get("retrieved_at") or ""),
                    "raw_benchmark_id": benchmark_id,
                    "raw_benchmark_name": str(benchmarks[benchmark_id]["name"]),
                    "resolved_benchmark_id": resolved_id,
                    "resolved_benchmark_name": resolved_names[resolved_id],
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["organization"],
            row["resolved_benchmark_id"],
            row["document_id"],
            row["raw_benchmark_id"],
        ),
    )


def build_positive_organization_matrix(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        grouped[(edge["organization"], edge["resolved_benchmark_id"])].append(edge)
    rows = []
    for (organization, benchmark_id), values in sorted(grouped.items()):
        document_ids = sorted({row["document_id"] for row in values})
        document_urls = sorted({row["document_url"] for row in values})
        rows.append(
            {
                "organization": organization,
                "resolved_benchmark_id": benchmark_id,
                "resolved_benchmark_name": values[0]["resolved_benchmark_name"],
                "reported_status": "reported",
                "support_document_count": len(document_ids),
                "supporting_document_ids": "|".join(document_ids),
                "supporting_document_urls": "|".join(document_urls),
                "latest_effective_date": max(row["effective_date"] for row in values),
            }
        )
    return rows


def build_complete_organization_matrix(
    positive_rows: list[dict[str, Any]],
    *,
    organizations: list[str],
    benchmark_names: dict[str, str],
) -> list[dict[str, Any]]:
    observed = {(row["organization"], row["resolved_benchmark_id"]): row for row in positive_rows}
    rows = []
    for organization in sorted(organizations):
        for benchmark_id, benchmark_name in sorted(benchmark_names.items()):
            row = observed.get((organization, benchmark_id))
            rows.append(
                row
                or {
                    "organization": organization,
                    "resolved_benchmark_id": benchmark_id,
                    "resolved_benchmark_name": benchmark_name,
                    # The registry is a reviewed convenience sample. No observed
                    # edge is not evidence that the vendor omitted the benchmark.
                    "reported_status": "not_observed",
                    "support_document_count": 0,
                    "supporting_document_ids": "",
                    "supporting_document_urls": "",
                    "latest_effective_date": "",
                }
            )
    return rows


def _support_maps(
    edges: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    organizations: dict[str, set[str]] = defaultdict(set)
    documents: dict[str, set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for edge in edges:
        benchmark_id = edge["resolved_benchmark_id"]
        organizations[benchmark_id].add(edge["organization"])
        documents[benchmark_id].add(edge["document_id"])
        names[benchmark_id] = edge["resolved_benchmark_name"]
    return organizations, documents, names


def summarize_scenario(
    scenario: dict[str, Any],
    cards: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    benchmark_count: int,
    baseline_members: set[str] | None = None,
) -> dict[str, Any]:
    organization_support, document_support, names = _support_maps(edges)
    threshold = int(scenario["min_organizations"])
    members = sorted(
        (
            benchmark_id
            for benchmark_id, organizations in organization_support.items()
            if len(organizations) >= threshold
        ),
        key=lambda benchmark_id: (
            -len(organization_support[benchmark_id]),
            -len(document_support[benchmark_id]),
            names[benchmark_id],
        ),
    )
    member_set = set(members)
    baseline_members = baseline_members if baseline_members is not None else member_set
    union = baseline_members | member_set
    jaccard = len(baseline_members & member_set) / len(union) if union else 1.0
    organizations = sorted({str(card["organization"]) for card in cards})
    return {
        "scenario_id": str(scenario["id"]),
        "label": str(scenario.get("label") or scenario["id"]),
        "threshold": threshold,
        "identity": str(scenario.get("identity") or "canonical"),
        "document_types": "|".join(map(str, scenario.get("document_types") or [])),
        "trailing_days": scenario.get("trailing_days") or "",
        "latest_per_organization": bool(scenario.get("latest_per_organization")),
        "drop_newest_per_organization": bool(scenario.get("drop_newest_per_organization")),
        "document_count": len(cards),
        "organization_count": len(organizations),
        "model_count": len({(str(card["organization"]), str(card["model"])) for card in cards}),
        "benchmark_count": benchmark_count,
        "document_benchmark_edge_count": len(edges),
        "organization_benchmark_edge_count": sum(
            len(value) for value in organization_support.values()
        ),
        "core_count": len(members),
        "core_members": members,
        "core_member_names": [names[member] for member in members],
        "jaccard_vs_baseline": round(jaccard, 4),
        "active_orgs_threshold_ok": len(organizations) >= threshold,
    }


def build_leave_one_out_membership(
    cards: list[dict[str, Any]],
    registry: dict[str, Any],
    *,
    baseline_members: set[str],
    threshold: int,
) -> dict[str, dict[str, Any]]:
    baseline_edges = build_document_edges(cards, registry)
    org_support, doc_support, names = _support_maps(baseline_edges)
    all_organizations = sorted({str(card["organization"]) for card in cards})
    all_documents = sorted({str(card["id"]) for card in cards})
    by_benchmark: dict[str, dict[str, Any]] = {}
    for benchmark_id in sorted(baseline_members):
        org_counts = []
        for removed in all_organizations:
            remaining = org_support[benchmark_id] - {removed}
            org_counts.append(len(remaining))
        doc_counts = []
        supporting_edges = [
            edge for edge in baseline_edges if edge["resolved_benchmark_id"] == benchmark_id
        ]
        for removed in all_documents:
            remaining_edges = [edge for edge in supporting_edges if edge["document_id"] != removed]
            doc_counts.append(len({edge["organization"] for edge in remaining_edges}))
        by_benchmark[benchmark_id] = {
            "benchmark_id": benchmark_id,
            "benchmark_name": names[benchmark_id],
            "baseline_organization_count": len(org_support[benchmark_id]),
            "baseline_document_count": len(doc_support[benchmark_id]),
            "leave_one_org_min": min(org_counts),
            "leave_one_org_max": max(org_counts),
            "leave_one_org_survival_count": sum(count >= threshold for count in org_counts),
            "leave_one_org_scenario_count": len(org_counts),
            "leave_one_doc_min": min(doc_counts),
            "leave_one_doc_max": max(doc_counts),
            "leave_one_doc_survival_count": sum(count >= threshold for count in doc_counts),
            "leave_one_doc_scenario_count": len(doc_counts),
            "survives_every_org_omission": all(count >= threshold for count in org_counts),
            "survives_every_document_omission": all(count >= threshold for count in doc_counts),
        }
    return by_benchmark


def _scenario_membership_rows(
    scenario: dict[str, Any],
    edges: list[dict[str, Any]],
    *,
    threshold: int,
    benchmark_names: dict[str, str],
) -> list[dict[str, Any]]:
    org_support, doc_support, _observed_names = _support_maps(edges)
    return [
        {
            "scenario_id": str(scenario["id"]),
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark_names[benchmark_id],
            "organization_count": len(org_support.get(benchmark_id, set())),
            "document_count": len(doc_support.get(benchmark_id, set())),
            "in_core": len(org_support.get(benchmark_id, set())) >= threshold,
        }
        for benchmark_id in sorted(benchmark_names, key=lambda value: benchmark_names[value])
    ]


def decide_recommendation(
    *,
    original_members: set[str],
    baseline_members: set[str],
    median_jaccard: float,
    every_document_survives: bool,
    scenario_summaries: list[dict[str, Any]],
    decision_rule: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    exact_membership_is_robust = (
        original_members == baseline_members
        and median_jaccard >= float(decision_rule["exact_membership_median_jaccard"])
        and (
            every_document_survives
            or not decision_rule["retain_requires_every_single_document_omission"]
        )
    )
    adequately_observed = [row for row in scenario_summaries if row["active_orgs_threshold_ok"]]
    high_support_group_persists = bool(adequately_observed) and all(
        row["core_count"] > 0 for row in adequately_observed
    )
    if exact_membership_is_robust:
        recommendation = "retain"
    elif (
        high_support_group_persists
        and decision_rule["narrow_when_group_persists_but_membership_changes"]
    ):
        recommendation = "narrow"
    elif baseline_members:
        recommendation = "replace"
    else:
        recommendation = "remove"
    return recommendation, {
        "exact_membership_is_robust": exact_membership_is_robust,
        "high_support_group_persists": high_support_group_persists,
    }


def verify_registry_provenance(registry_path: Path, audit: dict[str, Any]) -> str:
    actual_registry_sha256 = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    expected_registry_sha256 = str(audit["source_sha256"])
    if actual_registry_sha256 != expected_registry_sha256:
        raise VendorAttentionAuditError(
            "registry SHA-256 does not match the pre-registered source: "
            f"expected {expected_registry_sha256}, got {actual_registry_sha256}"
        )
    source_path = Path(str(audit["source_path"]))
    expected_registry_path = (Path.cwd() / source_path).resolve()
    if registry_path.resolve() != expected_registry_path:
        raise VendorAttentionAuditError(
            f"registry path must match the pre-registered source_path {source_path}"
        )
    source_commit = str(audit["source_commit"])
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise VendorAttentionAuditError(
            "source_commit must be a full 40-character commit object ID"
        )
    git_result = subprocess.run(
        ["git", "show", f"{source_commit}:{source_path.as_posix()}"],
        cwd=Path.cwd(),
        check=False,
        capture_output=True,
    )
    if git_result.returncode != 0:
        raise VendorAttentionAuditError(
            f"unable to read pre-registered registry at commit {source_commit}"
        )
    commit_registry_sha256 = hashlib.sha256(git_result.stdout).hexdigest()
    if commit_registry_sha256 != expected_registry_sha256:
        raise VendorAttentionAuditError(
            "source_commit registry bytes do not match source_sha256: "
            f"expected {expected_registry_sha256}, got {commit_registry_sha256}"
        )
    return actual_registry_sha256


def generate_vendor_attention_audit(
    *, registry_path: Path = DEFAULT_REGISTRY, spec_path: Path = DEFAULT_SPEC
) -> dict[str, Any]:
    spec = load_audit_spec(spec_path)
    audit = spec["audit"]
    actual_registry_sha256 = verify_registry_provenance(registry_path, audit)
    registry = load_registry(registry_path)
    analysis_end = _iso_date(audit["as_of"], label="audit.as_of")
    family_projection, family_names, reviewed_families = compile_family_projection(registry, spec)
    reviewed_family_ids = {row["family_id"] for row in reviewed_families}
    canonical_names = {str(row["id"]): str(row["name"]) for row in registry["benchmarks"]}
    scenario_payloads: dict[str, dict[str, Any]] = {}
    scenarios = {str(row["id"]): row for row in spec["scenarios"]}
    primary_id = str(audit["primary_scenario"])

    def run_scenario(scenario: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        cards = select_cards(registry, scenario, analysis_end=analysis_end)
        if scenario.get("identity") == "family":
            edges = build_document_edges(
                cards,
                registry,
                projection=family_projection,
                resolved_names=family_names,
            )
        else:
            edges = build_document_edges(cards, registry)
        return cards, edges

    primary_cards, primary_edges = run_scenario(scenarios[primary_id])
    primary_summary = summarize_scenario(
        scenarios[primary_id],
        primary_cards,
        primary_edges,
        benchmark_count=len(canonical_names),
    )
    baseline_members = set(primary_summary["core_members"])
    scenario_summaries = []
    membership_rows = []
    for scenario in spec["scenarios"]:
        cards, edges = (
            (primary_cards, primary_edges)
            if scenario["id"] == primary_id
            else run_scenario(scenario)
        )
        benchmark_count = (
            len(set(family_projection.values()))
            if scenario.get("identity") == "family"
            else len(canonical_names)
        )
        comparison_members = (
            {family_projection[benchmark_id] for benchmark_id in baseline_members}
            if scenario.get("identity") == "family"
            else baseline_members
        )
        summary = summarize_scenario(
            scenario,
            cards,
            edges,
            benchmark_count=benchmark_count,
            baseline_members=comparison_members,
        )
        if scenario.get("identity") == "family":
            summary["core_explicit_family_count"] = sum(
                member in reviewed_family_ids for member in summary["core_members"]
            )
            summary["core_singleton_count"] = (
                summary["core_count"] - summary["core_explicit_family_count"]
            )
        else:
            summary["core_explicit_family_count"] = ""
            summary["core_singleton_count"] = ""
        scenario_summaries.append(summary)
        scenario_benchmark_names = (
            {
                benchmark_id: family_names[benchmark_id]
                for benchmark_id in set(family_projection.values())
            }
            if scenario.get("identity") == "family"
            else canonical_names
        )
        membership_rows.extend(
            _scenario_membership_rows(
                scenario,
                edges,
                threshold=int(scenario["min_organizations"]),
                benchmark_names=scenario_benchmark_names,
            )
        )
        scenario_payloads[str(scenario["id"])] = {"cards": cards, "edges": edges}

    loo = build_leave_one_out_membership(
        primary_cards,
        registry,
        baseline_members=baseline_members,
        threshold=int(scenarios[primary_id]["min_organizations"]),
    )
    drop_members = set(
        next(
            row["core_members"]
            for row in scenario_summaries
            if row["scenario_id"] == "drop_newest_per_organization_t6"
        )
    )
    for row in membership_rows:
        if row["scenario_id"] == primary_id and row["benchmark_id"] in loo:
            row.update(loo[row["benchmark_id"]])
            row["survives_drop_newest_per_org"] = row["benchmark_id"] in drop_members

    summary_by_id = {row["scenario_id"]: row for row in scenario_summaries}
    robustness_ids = [
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
    median_jaccard = statistics.median(
        summary_by_id[scenario_id]["jaccard_vs_baseline"] for scenario_id in robustness_ids
    )
    median_jaccard_excluding_baseline = statistics.median(
        summary_by_id[scenario_id]["jaccard_vs_baseline"]
        for scenario_id in robustness_ids
        if scenario_id != primary_id
    )
    every_document_survives = all(row["survives_every_document_omission"] for row in loo.values())
    original_ids = set(audit["original_claim"]["listed_benchmark_ids"])
    primary_threshold = int(scenarios[primary_id]["min_organizations"])
    recommendation, decision_state = decide_recommendation(
        original_members=original_ids,
        baseline_members=baseline_members,
        median_jaccard=median_jaccard,
        every_document_survives=every_document_survives,
        scenario_summaries=scenario_summaries,
        decision_rule=audit["decision_rule"],
    )
    replacement_claim = (
        f"In the reviewed sample through {analysis_end.isoformat()}, "
        f"{primary_summary['core_count']} canonical benchmark IDs were reported by at least "
        f"{primary_threshold} organizations across the full history; the trailing 365-day "
        f"window contained {summary_by_id['trailing_365d_t6']['core_count']}, and retaining "
        f"only each organization's latest document contained "
        f"{summary_by_id['latest_per_organization_t6']['core_count']}. A recurring reporting "
        "group is visible, but its boundary depends on the time window, document selection, "
        "identity grouping, and support threshold."
    )
    claim_audit = {
        "schema_version": 1,
        "issue_number": audit["issue_number"],
        "issue_url": audit["issue_url"],
        "preregistration_url": audit["preregistration_url"],
        "contributor": audit["contributor"],
        "source_path": str(audit["source_path"]),
        "source_commit": audit["source_commit"],
        "source_sha256": actual_registry_sha256,
        "source_commit_verified": True,
        "analysis_end": analysis_end.isoformat(),
        "registry_counts": {
            "documents": len(registry["model_cards"]),
            "organizations": len({str(card["organization"]) for card in registry["model_cards"]}),
            "benchmarks": len(registry["benchmarks"]),
        },
        "primary_definition": {
            "counted_document_identity": "model_card.id with validated unique URL",
            "support_unit": "distinct organization strings in the reviewed registry",
            "benchmark_identity": "canonical benchmark_id",
            "minimum_organizations": primary_threshold,
            "score_tracks_used": False,
        },
        "original_claim": audit["original_claim"],
        "original_list_equals_threshold_set": original_ids == baseline_members,
        "original_list_is_subset_of_threshold_set": original_ids < baseline_members,
        "baseline_core": primary_summary,
        "scenarios": scenario_summaries,
        "reviewed_families": reviewed_families,
        "alias_collisions": build_alias_collision_index(registry),
        "robustness": {
            "scenario_ids": robustness_ids,
            "median_jaccard": round(median_jaccard, 4),
            "baseline_self_comparison_included": primary_id in robustness_ids,
            "median_jaccard_excluding_baseline": round(median_jaccard_excluding_baseline, 4),
            "required_median_jaccard": audit["decision_rule"]["exact_membership_median_jaccard"],
            "every_baseline_member_survives_single_document_omission": every_document_survives,
            **decision_state,
        },
        "recommendation": recommendation,
        "replacement_claim": replacement_claim,
        "reasoning": [
            "The eight named benchmarks are a strict subset of the 16 IDs "
            "satisfying the stated six-organization rule.",
            "Core size changes under predeclared time-window and document-selection rules.",
            "Several baseline boundary members fail at least one leave-one-out stress test.",
            "Family grouping changes mention identity but never merges score tracks or protocols.",
        ],
        "limitations": [
            "The reviewed registry is a convenience sample, not a census of all vendor reports.",
            "A not-observed matrix cell may reflect a missing or unread report and is not "
            "evidence of absence.",
            "Organization labels are publisher strings rather than audited corporate-parent "
            "identities.",
            "Living documents may change after retrieval; revised dates are used only when "
            "explicitly recorded.",
            "Family sensitivity concerns mention edges only; score instruments and protocols "
            "remain separate.",
        ],
    }

    baseline_positive = build_positive_organization_matrix(primary_edges)
    baseline_matrix = build_complete_organization_matrix(
        baseline_positive,
        organizations=sorted({str(card["organization"]) for card in primary_cards}),
        benchmark_names=canonical_names,
    )
    return {
        "document_edges": primary_edges,
        "organization_matrix": baseline_matrix,
        "scenario_summaries": scenario_summaries,
        "membership_rows": membership_rows,
        "claim_audit": claim_audit,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            output = dict(row)
            for key, value in output.items():
                if isinstance(value, list):
                    output[key] = "|".join(map(str, value))
                elif isinstance(value, bool):
                    output[key] = str(value).lower()
            writer.writerow(output)


def write_vendor_attention_artifacts(
    result: dict[str, Any], *, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output_dir / "document-benchmark-edges.csv",
        result["document_edges"],
        [
            "document_id",
            "document_url",
            "organization",
            "model",
            "document_type",
            "effective_date",
            "retrieved_at",
            "raw_benchmark_id",
            "raw_benchmark_name",
            "resolved_benchmark_id",
            "resolved_benchmark_name",
        ],
    )
    _write_csv(
        output_dir / "organization-benchmark-matrix.csv",
        result["organization_matrix"],
        [
            "organization",
            "resolved_benchmark_id",
            "resolved_benchmark_name",
            "reported_status",
            "support_document_count",
            "supporting_document_ids",
            "supporting_document_urls",
            "latest_effective_date",
        ],
    )
    _write_csv(
        output_dir / "scenario-summary.csv",
        result["scenario_summaries"],
        [
            "scenario_id",
            "label",
            "threshold",
            "identity",
            "document_types",
            "trailing_days",
            "latest_per_organization",
            "drop_newest_per_organization",
            "document_count",
            "organization_count",
            "model_count",
            "benchmark_count",
            "document_benchmark_edge_count",
            "organization_benchmark_edge_count",
            "core_count",
            "core_explicit_family_count",
            "core_singleton_count",
            "core_members",
            "core_member_names",
            "jaccard_vs_baseline",
            "active_orgs_threshold_ok",
        ],
    )
    membership_fields = [
        "scenario_id",
        "benchmark_id",
        "benchmark_name",
        "organization_count",
        "document_count",
        "in_core",
        "baseline_organization_count",
        "baseline_document_count",
        "leave_one_org_min",
        "leave_one_org_max",
        "leave_one_org_survival_count",
        "leave_one_org_scenario_count",
        "leave_one_doc_min",
        "leave_one_doc_max",
        "leave_one_doc_survival_count",
        "leave_one_doc_scenario_count",
        "survives_every_org_omission",
        "survives_every_document_omission",
        "survives_drop_newest_per_org",
    ]
    _write_csv(
        output_dir / "sensitivity-membership.csv",
        result["membership_rows"],
        membership_fields,
    )
    (output_dir / "claim-audit.json").write_text(
        json.dumps(result["claim_audit"], indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = generate_vendor_attention_audit(
        registry_path=args.registry,
        spec_path=args.spec,
    )
    write_vendor_attention_artifacts(result, output_dir=args.output_dir)
    audit = result["claim_audit"]
    print(
        f"Vendor-attention audit: {audit['baseline_core']['core_count']} baseline members; "
        f"recommendation={audit['recommendation']} -> {args.output_dir}"
    )


if __name__ == "__main__":
    main()
