"""Evaluation metrics for sparse, reviewable search relevance judgments."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .query import SEARCH_SCOPES, QueryService

_QUERY_KINDS = {"catalog_gap", "navigational", "topical"}


def load_dataset(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"{path} must be a search evaluation dataset with schema_version 1")
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        raise ValueError(f"{path} name must be a non-empty string")
    cutoffs = value.get("cutoffs")
    if not isinstance(cutoffs, dict) or any(
        not isinstance(cutoffs.get(name), int) or cutoffs[name] < 1 for name in ("hit", "recall")
    ):
        raise ValueError(f"{path} cutoffs.hit and cutoffs.recall must be positive integers")
    thresholds = value.get("thresholds")
    if not isinstance(thresholds, dict) or not all(
        isinstance(thresholds.get(direction), dict) for direction in ("minimum", "maximum")
    ):
        raise ValueError(f"{path} thresholds must declare minimum and maximum objects")
    required_metrics = {
        f"catalog_gap_full_match_rate_at_{cutoffs['recall']}",
        f"catalog_gap_partial_retention_at_{cutoffs['recall']}",
        f"hit_rate_at_{cutoffs['hit']}",
        f"macro_recall_at_{cutoffs['recall']}",
        f"mrr_at_{cutoffs['recall']}",
        "navigational_hit_rate_at_1",
    }
    threshold_metrics = set(thresholds["minimum"]) | set(thresholds["maximum"])
    if threshold_metrics != required_metrics:
        raise ValueError(f"{path} thresholds must declare exactly {sorted(required_metrics)}")
    for direction in ("minimum", "maximum"):
        for metric, threshold in thresholds[direction].items():
            if not isinstance(threshold, int | float) or isinstance(threshold, bool):
                raise ValueError(f"{path} threshold {direction}.{metric} must be numeric")
            if not 0.0 <= float(threshold) <= 1.0:
                raise ValueError(f"{path} threshold {direction}.{metric} must be between 0 and 1")
    queries = value.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError(f"{path} queries must be a non-empty array")
    ids: set[str] = set()
    for position, case in enumerate(queries):
        label = f"{path} query {position}"
        if not isinstance(case, dict):
            raise ValueError(f"{label} must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in ids:
            raise ValueError(f"{label} id must be a unique non-empty string")
        ids.add(case_id)
        if case.get("kind") not in _QUERY_KINDS:
            raise ValueError(f"{label} kind must be one of {sorted(_QUERY_KINDS)}")
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError(f"{label} query must be a non-empty string")
        if not isinstance(case.get("intent"), str) or not case["intent"].strip():
            raise ValueError(f"{label} intent must be a non-empty string")
        if case.get("scope") not in SEARCH_SCOPES:
            raise ValueError(f"{label} scope must be one of {SEARCH_SCOPES}")
        relevant = case.get("relevant_keys")
        if not isinstance(relevant, list) or not all(
            isinstance(key, str) and key.strip() for key in relevant
        ):
            raise ValueError(f"{label} relevant_keys must be an array of non-empty strings")
        if len(relevant) != len(set(relevant)):
            raise ValueError(f"{label} relevant_keys must not contain duplicates")
        if case["kind"] == "catalog_gap" and relevant:
            raise ValueError(f"{label} catalog_gap must not declare relevant_keys")
        if case["kind"] != "catalog_gap" and not relevant:
            raise ValueError(f"{label} positive query must declare relevant_keys")
        expected_partial = case.get("expected_partial_keys")
        if case["kind"] == "catalog_gap":
            if not isinstance(expected_partial, list) or not all(
                isinstance(key, str) and key.strip() for key in expected_partial
            ):
                raise ValueError(
                    f"{label} expected_partial_keys must be an array of non-empty strings"
                )
            if len(expected_partial) != len(set(expected_partial)):
                raise ValueError(f"{label} expected_partial_keys must not contain duplicates")
        elif expected_partial is not None:
            raise ValueError(f"{label} positive query must not declare expected_partial_keys")
    return value


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate(service: QueryService, dataset: dict[str, Any]) -> dict[str, Any]:
    hit_cutoff = int(dataset["cutoffs"]["hit"])
    recall_cutoff = int(dataset["cutoffs"]["recall"])
    limit = max(hit_cutoff, recall_cutoff)
    positive_cases: list[dict[str, Any]] = []
    gap_cases: list[dict[str, Any]] = []

    for case in dataset["queries"]:
        result = service.search(case["query"], scope=case["scope"], limit=limit)
        ranks = {row["key"]: row["rank"] for row in result["results"]}
        relevant = list(case["relevant_keys"])
        if case["kind"] == "catalog_gap":
            recall_rows = [row for row in result["results"] if row["rank"] <= recall_cutoff]
            full_matches = [row["key"] for row in recall_rows if not row["match"]["missing_tokens"]]
            partial_keys = {row["key"] for row in recall_rows if row["match"]["missing_tokens"]}
            expected_partial = list(case["expected_partial_keys"])
            retained_partial = sum(key in partial_keys for key in expected_partial)
            gap_cases.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "intent": case["intent"],
                    "candidate_count": result["candidate_count"],
                    "full_match_keys": full_matches,
                    f"partial_retention_at_{recall_cutoff}": (
                        retained_partial / len(expected_partial) if expected_partial else None
                    ),
                    "missing_expected_partial_keys": sorted(set(expected_partial) - partial_keys),
                }
            )
            continue

        if not relevant:
            raise ValueError(f"positive query {case['id']} must declare relevant_keys")
        relevant_ranks = sorted(ranks[key] for key in relevant if key in ranks)
        first_rank = relevant_ranks[0] if relevant_ranks else None
        recalled = sum(1 for key in relevant if ranks.get(key, limit + 1) <= recall_cutoff)
        positive_cases.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "query": case["query"],
                "intent": case["intent"],
                "first_relevant_rank": first_rank,
                f"hit_at_{hit_cutoff}": first_rank is not None and first_rank <= hit_cutoff,
                f"recall_at_{recall_cutoff}": recalled / len(relevant),
                "missing_relevant_keys": sorted(set(relevant) - set(ranks)),
            }
        )

    metrics = {
        f"hit_rate_at_{hit_cutoff}": _mean(
            [float(case[f"hit_at_{hit_cutoff}"]) for case in positive_cases]
        ),
        f"mrr_at_{recall_cutoff}": _mean(
            [
                1.0 / case["first_relevant_rank"]
                if case["first_relevant_rank"] and case["first_relevant_rank"] <= recall_cutoff
                else 0.0
                for case in positive_cases
            ]
        ),
        f"macro_recall_at_{recall_cutoff}": _mean(
            [case[f"recall_at_{recall_cutoff}"] for case in positive_cases]
        ),
        "navigational_hit_rate_at_1": _mean(
            [
                float(case["first_relevant_rank"] == 1)
                for case in positive_cases
                if case["kind"] == "navigational"
            ]
        ),
        f"catalog_gap_full_match_rate_at_{recall_cutoff}": _mean(
            [float(bool(case["full_match_keys"])) for case in gap_cases]
        ),
        f"catalog_gap_partial_retention_at_{recall_cutoff}": _mean(
            [
                case[f"partial_retention_at_{recall_cutoff}"]
                for case in gap_cases
                if case[f"partial_retention_at_{recall_cutoff}"] is not None
            ]
        ),
    }
    metrics = {name: round(value, 6) for name, value in metrics.items()}

    failures: list[str] = []
    for name, threshold in dataset["thresholds"]["minimum"].items():
        if metrics[name] < threshold:
            failures.append(f"{name}={metrics[name]} is below minimum {threshold}")
    for name, threshold in dataset["thresholds"]["maximum"].items():
        if metrics[name] > threshold:
            failures.append(f"{name}={metrics[name]} is above maximum {threshold}")

    return {
        "schema_version": 1,
        "dataset": dataset["name"],
        "query_count": len(dataset["queries"]),
        "positive_query_count": len(positive_cases),
        "catalog_gap_query_count": len(gap_cases),
        "metrics": metrics,
        "thresholds": dataset["thresholds"],
        "passed": not failures,
        "failures": failures,
        "cases": positive_cases + gap_cases,
    }
