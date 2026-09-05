#!/usr/bin/env python3
"""Validate and analyze the issue #455 agent weakness evidence table."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import yaml

STUDY_SCHEMA_VERSION = 1
DEFAULT_SOURCE = Path("data/agent_weakness_evidence.yml")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

_REQUIRED_STUDY_FIELDS = (
    "issue",
    "snapshot_date",
    "repository_commit_input",
    "evidence_cutoff",
    "preregistration_url",
    "statuses",
    "fine_taxonomy",
    "coarse_grouping",
    "demonstrated_family_scope",
    "excluded_families",
    "measurement_counterexample_only",
)
_REQUIRED_ROW_FIELDS = (
    "id",
    "benchmark_family_id",
    "benchmark_family_name",
    "radar_query",
    "task_or_protocol",
    "status",
    "primary_code",
    "authoritative_source_kind",
    "source_url",
    "evidence_location",
    "published_date",
    "observed_evidence",
    "limitations",
    "plausible_counter_reading",
    "counterexample",
    "counterexample_location",
    "review",
)
_EXPECTED_STATUSES = ("demonstrated", "design_implied", "unmeasured")
_REPLAYABLE_EVIDENCE_TOKENS = (
    "table",
    "figure",
    "line ",
    "lines ",
    "paragraph",
    "p id",
    "abstract paragraph",
    "caption",
    "cell",
    "row",
    "page",
)
DEFAULT_BENCHMARK_INDEX = Path("site/data/benchmark-index.json")


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _require_nonempty_string(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _require_date(value: Any, *, label: str) -> str:
    if type(value) is date:
        return value.isoformat()
    text = str(value or "").strip()
    if not _ISO_DATE.fullmatch(text):
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{label} is not a real calendar date") from error
    return text


def _date_value(value: str) -> date:
    return date.fromisoformat(value)


def _require_http_url(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if not text.startswith(("https://", "http://")):
        raise ValueError(f"{label} must be an HTTP(S) URL")
    return text


def _normalized_secondary_code(value: Any, fine_taxonomy: set[str], *, label: str) -> str | None:
    if value is None:
        return None
    text = _require_nonempty_string(value, label=label)
    if text not in fine_taxonomy:
        raise ValueError(f"{label} must be one of the declared fine taxonomy codes")
    return text


def _coarse_lookup(grouping: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for coarse_group, fine_codes in grouping.items():
        seen_in_group: set[str] = set()
        for fine_code in fine_codes:
            if fine_code in seen_in_group:
                raise ValueError(
                    f"coarse_grouping[{coarse_group!r}] contains duplicates, "
                    f"including {fine_code!r}"
                )
            seen_in_group.add(fine_code)
            if fine_code in lookup and lookup[fine_code] != coarse_group:
                raise ValueError(f"fine code {fine_code!r} appears in multiple coarse groups")
            lookup[fine_code] = coarse_group
    return lookup


def _require_string_list(value: Any, *, label: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        expected = "a list" if allow_empty else "a non-empty list"
        raise ValueError(f"{label} must be {expected}")
    normalized = [_require_nonempty_string(item, label=f"{label} entry") for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} must not contain duplicates")
    return normalized


def _require_replayable_evidence_location(value: Any, *, label: str) -> str:
    text = _require_nonempty_string(value, label=label)
    lowered = text.lower()
    if any(token in lowered for token in _REPLAYABLE_EVIDENCE_TOKENS):
        return text
    raise ValueError(f"{label} must include a replayable table/figure/line/paragraph anchor")


def _validate_benchmark_family_identity(rows: list[dict[str, Any]], *, path: Path) -> None:
    family_name_by_id: dict[str, str] = {}
    family_id_by_name: dict[str, str] = {}
    for row in rows:
        family_id = row["benchmark_family_id"]
        family_name = row["benchmark_family_name"]

        prior_name = family_name_by_id.setdefault(family_id, family_name)
        if prior_name != family_name:
            raise ValueError(
                f"{path}: benchmark family identity mismatch: id {family_id!r} maps to both "
                f"{prior_name!r} and {family_name!r}"
            )

        prior_id = family_id_by_name.setdefault(family_name, family_id)
        if prior_id != family_id:
            raise ValueError(
                f"{path}: benchmark family identity mismatch: name {family_name!r} maps to both "
                f"{prior_id!r} and {family_id!r}"
            )


def _validate_null_radar_queries(rows: list[dict[str, Any]], *, path: Path) -> None:
    """Require demonstrated rows without IDs to resolve through local search."""
    if not DEFAULT_BENCHMARK_INDEX.exists():
        return
    try:
        payload = json.loads(DEFAULT_BENCHMARK_INDEX.read_text(encoding="utf-8"))
        records = payload.get("benchmarks", [])
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: cannot read generated benchmark index") from error
    for row in rows:
        if row["status"] != "demonstrated" or row["radar_record_id"] is not None:
            continue
        query = row["radar_query"].casefold()
        matches = [
            record
            for record in records
            if query
            and query
            in " ".join(
                str(record.get(field) or "") for field in ("name", "description", "key")
            ).casefold()
        ]
        if not matches:
            raise ValueError(
                f"{path}: demonstrated row {row['id']} has no Radar search result for "
                f"radar_query {row['radar_query']!r}; supply a resolvable query or record id"
            )


def load_study(path: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"{path}: study file not found")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document = _require_mapping(document, label=f"{path}: study document")

    version = document.get("schema_version")
    if version != STUDY_SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported schema_version {version!r}")

    study = _require_mapping(document.get("study"), label=f"{path}: study")
    missing = [field for field in _REQUIRED_STUDY_FIELDS if field not in study]
    if missing:
        raise ValueError(f"{path}: study is missing fields: {', '.join(missing)}")

    statuses = study.get("statuses")
    if not isinstance(statuses, list):
        raise ValueError(f"{path}: statuses must be a list")
    normalized_statuses = [
        _require_nonempty_string(item, label=f"{path}: statuses entry") for item in statuses
    ]
    if tuple(normalized_statuses) != _EXPECTED_STATUSES:
        raise ValueError(
            f"{path}: statuses must declare demonstrated, design_implied, and unmeasured"
        )

    fine_taxonomy = study.get("fine_taxonomy")
    if not isinstance(fine_taxonomy, list) or not fine_taxonomy:
        raise ValueError(f"{path}: fine_taxonomy must be a non-empty list")
    normalized_taxonomy = [
        _require_nonempty_string(item, label=f"{path}: fine_taxonomy entry")
        for item in fine_taxonomy
    ]
    fine_taxonomy_set = set(normalized_taxonomy)
    if len(fine_taxonomy_set) != len(normalized_taxonomy):
        raise ValueError(f"{path}: fine_taxonomy must not contain duplicates")

    coarse_grouping_raw = _require_mapping(
        study.get("coarse_grouping"), label=f"{path}: coarse_grouping"
    )
    coarse_grouping: dict[str, list[str]] = {}
    for coarse_group, codes in coarse_grouping_raw.items():
        coarse_name = _require_nonempty_string(coarse_group, label=f"{path}: coarse_grouping key")
        if not isinstance(codes, list) or not codes:
            raise ValueError(f"{path}: coarse_grouping[{coarse_name!r}] must be a non-empty list")
        normalized_codes = [
            _require_nonempty_string(code, label=f"{path}: coarse_grouping[{coarse_name!r}] code")
            for code in codes
        ]
        unknown = sorted(set(normalized_codes) - fine_taxonomy_set)
        if unknown:
            raise ValueError(
                f"{path}: coarse_grouping[{coarse_name!r}] references unknown fine codes: "
                f"{', '.join(unknown)}"
            )
        coarse_grouping[coarse_name] = normalized_codes
    coarse_lookup = _coarse_lookup(coarse_grouping)
    missing_fine_codes = sorted(fine_taxonomy_set - set(coarse_lookup))
    if missing_fine_codes:
        raise ValueError(
            f"{path}: coarse_grouping must cover every fine_taxonomy code exactly once; "
            f"missing {', '.join(missing_fine_codes)}"
        )

    snapshot_date = _require_date(study.get("snapshot_date"), label=f"{path}: snapshot_date")
    evidence_cutoff = _require_date(study.get("evidence_cutoff"), label=f"{path}: evidence_cutoff")
    evidence_cutoff_value = _date_value(evidence_cutoff)

    demonstrated_family_scope = _require_string_list(
        study.get("demonstrated_family_scope"),
        label=f"{path}: demonstrated_family_scope",
    )
    excluded_families = _require_string_list(
        study.get("excluded_families"),
        label=f"{path}: excluded_families",
    )
    measurement_counterexample_only = _require_string_list(
        study.get("measurement_counterexample_only"),
        label=f"{path}: measurement_counterexample_only",
        allow_empty=True,
    )

    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: rows must be a non-empty list")

    normalized_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_statuses: set[str] = set()
    declared_statuses = set(normalized_statuses)
    for index, raw_row in enumerate(rows):
        row = _require_mapping(raw_row, label=f"{path}: row {index}")
        missing = [field for field in _REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            raise ValueError(f"{path}: row {index} is missing fields: {', '.join(missing)}")

        row_id = _require_nonempty_string(row.get("id"), label=f"{path}: row {index} id")
        if row_id in seen_ids:
            raise ValueError(f"{path}: duplicate row id {row_id!r}")
        seen_ids.add(row_id)

        status = _require_nonempty_string(row.get("status"), label=f"{path}: row {row_id} status")
        if status not in declared_statuses:
            raise ValueError(f"{path}: row {row_id} status must be one of the declared statuses")
        seen_statuses.add(status)

        primary_code = _require_nonempty_string(
            row.get("primary_code"), label=f"{path}: row {row_id} primary_code"
        )
        if primary_code not in fine_taxonomy_set:
            raise ValueError(f"{path}: row {row_id} primary_code must be in fine_taxonomy")

        benchmark_family_id = _require_nonempty_string(
            row.get("benchmark_family_id"), label=f"{path}: row {row_id} benchmark_family_id"
        )
        radar_record_id = row.get("radar_record_id")
        if radar_record_id is not None:
            radar_record_id = _require_nonempty_string(
                radar_record_id, label=f"{path}: row {row_id} radar_record_id"
            )

        source_url = _require_http_url(
            _require_nonempty_string(
                row.get("source_url"),
                label=f"{path}: row {row_id} authoritative source URL",
            ),
            label=f"{path}: row {row_id} authoritative source",
        )

        evidence_location = _require_replayable_evidence_location(
            row.get("evidence_location"),
            label=f"{path}: row {row_id} evidence_location",
        )
        published_date = _require_date(
            row.get("published_date"), label=f"{path}: row {row_id} published_date"
        )
        if _date_value(published_date) > evidence_cutoff_value:
            raise ValueError(
                f"{path}: row {row_id} published_date {published_date} is later than "
                f"evidence_cutoff {evidence_cutoff}"
            )

        review = _require_mapping(row.get("review"), label=f"{path}: row {row_id} review")
        sampled = review.get("sampled_for_secondary_review")
        if not isinstance(sampled, bool):
            raise ValueError(
                f"{path}: row {row_id} review.sampled_for_secondary_review must be a boolean"
            )
        secondary_code_raw = review.get("secondary_code")
        if not sampled and secondary_code_raw not in (None, ""):
            raise ValueError(
                f"{path}: row {row_id} review.secondary_code requires "
                f"sampled_for_secondary_review to be true"
            )
        secondary_code = _normalized_secondary_code(
            secondary_code_raw,
            fine_taxonomy_set,
            label=f"{path}: row {row_id} review.secondary_code",
        )
        if secondary_code is not None and not str(review.get("secondary_note") or "").strip():
            raise ValueError(
                f"{path}: row {row_id} review.secondary_note is required when "
                "secondary_code is present"
            )

        normalized_rows.append(
            {
                "id": row_id,
                "benchmark_family_id": benchmark_family_id,
                "benchmark_family_name": _require_nonempty_string(
                    row.get("benchmark_family_name"),
                    label=f"{path}: row {row_id} benchmark_family_name",
                ),
                "radar_query": _require_nonempty_string(
                    row.get("radar_query"), label=f"{path}: row {row_id} radar_query"
                ),
                "radar_record_id": radar_record_id,
                "task_or_protocol": _require_nonempty_string(
                    row.get("task_or_protocol"), label=f"{path}: row {row_id} task_or_protocol"
                ),
                "status": status,
                "primary_code": primary_code,
                "coarse_group": coarse_lookup[primary_code],
                "authoritative_source_kind": _require_nonempty_string(
                    row.get("authoritative_source_kind"),
                    label=f"{path}: row {row_id} authoritative_source_kind",
                ),
                "source_url": source_url,
                "evidence_location": evidence_location,
                "published_date": published_date,
                "observed_evidence": _require_nonempty_string(
                    row.get("observed_evidence"), label=f"{path}: row {row_id} observed_evidence"
                ),
                "limitations": _require_nonempty_string(
                    row.get("limitations"), label=f"{path}: row {row_id} limitations"
                ),
                "plausible_counter_reading": _require_nonempty_string(
                    row.get("plausible_counter_reading"),
                    label=f"{path}: row {row_id} plausible_counter_reading",
                ),
                "counterexample": _require_nonempty_string(
                    row.get("counterexample"), label=f"{path}: row {row_id} counterexample"
                ),
                "counterexample_location": _require_nonempty_string(
                    row.get("counterexample_location"),
                    label=f"{path}: row {row_id} counterexample_location",
                ),
                "review": {
                    "sampled_for_secondary_review": sampled,
                    "secondary_code": secondary_code,
                    "secondary_note": (
                        str(review.get("secondary_note")).strip()
                        if review.get("secondary_note") is not None
                        else None
                    ),
                },
            }
        )

    if seen_statuses != set(normalized_statuses):
        raise ValueError(f"{path}: rows must cover all declared statuses")

    _validate_benchmark_family_identity(normalized_rows, path=path)
    _validate_null_radar_queries(normalized_rows, path=path)

    excluded_family_overlap = sorted(
        set(excluded_families) & {row["benchmark_family_name"] for row in normalized_rows}
    )
    if excluded_family_overlap:
        raise ValueError(
            f"{path}: excluded_families must be disjoint from coded row families: "
            f"{', '.join(excluded_family_overlap)}"
        )

    demonstrated_family_names = {
        row["benchmark_family_name"] for row in normalized_rows if row["status"] == "demonstrated"
    }
    declared_scope = set(demonstrated_family_scope)
    missing_families = sorted(declared_scope - demonstrated_family_names)
    extra_families = sorted(demonstrated_family_names - declared_scope)
    if missing_families or extra_families:
        parts: list[str] = []
        if missing_families:
            parts.append(f"missing {', '.join(missing_families)}")
        if extra_families:
            parts.append(f"extra {', '.join(extra_families)}")
        raise ValueError(f"{path}: demonstrated family scope mismatch: {'; '.join(parts)}")

    counterexample_demonstrated = sorted(
        demonstrated_family_names & set(measurement_counterexample_only)
    )
    if counterexample_demonstrated:
        raise ValueError(
            f"{path}: measurement counterexample families cannot be demonstrated: "
            f"{', '.join(counterexample_demonstrated)}"
        )
    unmeasured_family_names = {
        row["benchmark_family_name"] for row in normalized_rows if row["status"] == "unmeasured"
    }
    missing_counterexample_rows = sorted(
        set(measurement_counterexample_only) - unmeasured_family_names
    )
    if missing_counterexample_rows:
        raise ValueError(
            f"{path}: measurement counterexample families require unmeasured rows: "
            f"{', '.join(missing_counterexample_rows)}"
        )

    normalized_study = {
        **study,
        "snapshot_date": snapshot_date,
        "evidence_cutoff": evidence_cutoff,
        "repository_commit_input": _require_nonempty_string(
            study.get("repository_commit_input"),
            label=f"{path}: repository_commit_input",
        ),
        "preregistration_url": _require_http_url(
            study.get("preregistration_url"), label=f"{path}: preregistration_url"
        ),
        "statuses": normalized_statuses,
        "fine_taxonomy": normalized_taxonomy,
        "coarse_grouping": coarse_grouping,
        "demonstrated_family_scope": demonstrated_family_scope,
        "excluded_families": excluded_families,
        "measurement_counterexample_only": measurement_counterexample_only,
    }
    return {"study": normalized_study, "rows": normalized_rows, "path": str(path)}


def _cohens_kappa(primary: list[str], secondary: list[str], categories: list[str]) -> float | None:
    if not primary:
        return None
    observed = sum(
        1 for left, right in zip(primary, secondary, strict=True) if left == right
    ) / len(primary)
    primary_distribution = Counter(primary)
    secondary_distribution = Counter(secondary)
    expected = sum(
        (primary_distribution.get(category, 0) / len(primary))
        * (secondary_distribution.get(category, 0) / len(secondary))
        for category in categories
    )
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def analyze_study(study: dict[str, Any]) -> dict[str, Any]:
    meta = study["study"]
    rows = study["rows"]
    fine_taxonomy = meta["fine_taxonomy"]
    coarse_grouping = meta["coarse_grouping"]

    demonstrated_rows = [row for row in rows if row["status"] == "demonstrated"]
    demonstrated_family_ids = {row["benchmark_family_id"] for row in demonstrated_rows}

    fine_recurrence: dict[str, dict[str, Any]] = {}
    for code in fine_taxonomy:
        family_ids = {
            row["benchmark_family_id"] for row in demonstrated_rows if row["primary_code"] == code
        }
        fine_recurrence[code] = {
            "family_count": len(family_ids),
            "family_share": (
                len(family_ids) / len(demonstrated_family_ids) if demonstrated_family_ids else 0.0
            ),
            "family_ids": sorted(family_ids),
        }

    coarse_recurrence: dict[str, dict[str, Any]] = {}
    for coarse_group, codes in coarse_grouping.items():
        family_ids = {
            row["benchmark_family_id"] for row in demonstrated_rows if row["primary_code"] in codes
        }
        coarse_recurrence[coarse_group] = {
            "family_count": len(family_ids),
            "family_share": (
                len(family_ids) / len(demonstrated_family_ids) if demonstrated_family_ids else 0.0
            ),
            "family_ids": sorted(family_ids),
        }

    sampled_rows = [row for row in rows if row["review"]["sampled_for_secondary_review"]]
    completed_rows = [row for row in sampled_rows if row["review"]["secondary_code"]]
    pending_rows = [row for row in sampled_rows if not row["review"]["secondary_code"]]
    primary_codes = [row["primary_code"] for row in completed_rows]
    secondary_codes = [row["review"]["secondary_code"] for row in completed_rows]
    percent_agreement = (
        sum(1 for left, right in zip(primary_codes, secondary_codes, strict=True) if left == right)
        / len(completed_rows)
        if completed_rows
        else None
    )
    agreement = {
        "sampled_row_count": len(sampled_rows),
        "completed_row_count": len(completed_rows),
        "pending_row_count": len(pending_rows),
        "pending_row_ids": [row["id"] for row in pending_rows],
        "percent_agreement": percent_agreement,
        "cohens_kappa": _cohens_kappa(primary_codes, secondary_codes, fine_taxonomy),
        "disagreements": [
            {
                "id": row["id"],
                "primary_code": row["primary_code"],
                "secondary_code": row["review"]["secondary_code"],
            }
            for row in completed_rows
            if row["primary_code"] != row["review"]["secondary_code"]
        ],
    }

    status_counts = {status: 0 for status in meta["statuses"]}
    for row in rows:
        status_counts[row["status"]] += 1

    family_rows: dict[str, dict[str, str]] = {}
    for row in demonstrated_rows:
        family_rows.setdefault(
            row["benchmark_family_id"],
            {
                "benchmark_family_id": row["benchmark_family_id"],
                "benchmark_family_name": row["benchmark_family_name"],
                "radar_query": row["radar_query"],
                "radar_record_id": row["radar_record_id"],
            },
        )

    return {
        "snapshot_date": meta["snapshot_date"],
        "repository_commit_input": meta["repository_commit_input"],
        "study_issue": meta["issue"],
        "evidence_cutoff": meta["evidence_cutoff"],
        "demonstrated_family_scope": meta["demonstrated_family_scope"],
        "excluded_families": meta["excluded_families"],
        "measurement_counterexample_only": meta["measurement_counterexample_only"],
        "status_counts": status_counts,
        "demonstrated_family_count": len(demonstrated_family_ids),
        "demonstrated_families": sorted(
            family_rows.values(), key=lambda item: item["benchmark_family_name"]
        ),
        "fine_recurrence": fine_recurrence,
        "coarse_recurrence": coarse_recurrence,
        "agreement": agreement,
        "design_implied_rows": [
            {
                "id": row["id"],
                "benchmark_family_id": row["benchmark_family_id"],
                "primary_code": row["primary_code"],
            }
            for row in rows
            if row["status"] == "design_implied"
        ],
        "missing_measurements": [
            {
                "id": row["id"],
                "benchmark_family_id": row["benchmark_family_id"],
                "benchmark_family_name": row["benchmark_family_name"],
                "primary_code": row["primary_code"],
                "source_url": row["source_url"],
            }
            for row in rows
            if row["status"] == "unmeasured"
        ],
        "counterexamples": [
            {
                "id": row["id"],
                "benchmark_family_id": row["benchmark_family_id"],
                "benchmark_family_name": row["benchmark_family_name"],
                "status": row["status"],
                "counterexample": row["counterexample"],
                "counterexample_location": row["counterexample_location"],
            }
            for row in rows
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "benchmark_family_id",
        "benchmark_family_name",
        "radar_query",
        "radar_record_id",
        "task_or_protocol",
        "status",
        "primary_code",
        "coarse_group",
        "authoritative_source_kind",
        "source_url",
        "evidence_location",
        "published_date",
        "observed_evidence",
        "limitations",
        "plausible_counter_reading",
        "counterexample",
        "counterexample_location",
        "sampled_for_secondary_review",
        "secondary_code",
        "secondary_note",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{
                        key: row.get(key)
                        for key in fieldnames
                        if key
                        not in {
                            "sampled_for_secondary_review",
                            "secondary_code",
                            "secondary_note",
                        }
                    },
                    "sampled_for_secondary_review": row["review"]["sampled_for_secondary_review"],
                    "secondary_code": row["review"]["secondary_code"],
                    "secondary_note": row["review"]["secondary_note"],
                }
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--csv-output", type=Path, default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    study = load_study(args.source)
    analysis = analyze_study(study)
    if args.json_output:
        _write_json(args.json_output, analysis)
    if args.csv_output:
        _write_csv(args.csv_output, study["rows"])
    print(json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
