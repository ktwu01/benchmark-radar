"""Protocol-aware saturation audit for report section 6.2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .benchmark_scores import DEFAULT_SCORES_PATH, build_score_progression
from .model_cards import DEFAULT_REGISTRY_PATH, load_registry

ARTIFACT_SCHEMA_VERSION = 2
DEFAULT_AUDIT_PATH = Path("docs/technical-report/saturation-audit-6.2.json")
SECTION_6_2_BENCHMARK_IDS = (
    "aime",
    "arena_hard",
    "deepsearchqa",
    "hmmt",
    "math_500",
    "mathvision",
    "swe_bench_verified",
    "tau2_bench",
)

_THRESHOLDS = (5.0, 3.0, 2.0)
_NEAR_CEILING_THRESHOLD = 5.0


def _best_row(rows: list[dict[str, Any]], direction: str) -> dict[str, Any]:
    reverse = direction == "higher_is_better"
    return sorted(
        rows,
        key=lambda row: (row["value"], row["reported_at"], row["organization"], row["model"]),
        reverse=reverse,
    )[0]


def _headroom(value: float, *, direction: str, unit: str) -> float | None:
    if unit != "percent":
        return None
    bound = 100.0
    result = bound - value if direction == "higher_is_better" else value
    precision = 0 if float(bound).is_integer() and float(value).is_integer() else 2
    return round(result, precision)


def _series_best(series: dict[str, Any], direction: str) -> dict[str, Any]:
    return _best_row(series["points"], direction)


def _series_summary(series: dict[str, Any], *, direction: str, unit: str) -> dict[str, Any]:
    best = _series_best(series, direction)
    return {
        "instrument": series["instrument"],
        "protocol": series["protocol"],
        "score_ids": [point["observation_id"] for point in series["points"]],
        "point_count": series["point_count"],
        "dated_points": series["dated_points"],
        "organization_count": series["organization_count"],
        "single_organization": series["single_organization"],
        "connectable": series["connectable"],
        "first_reported_at": str(series["first_reported_at"]),
        "last_reported_at": str(series["last_reported_at"]),
        "best_observation_id": best["observation_id"],
        "best_value": best["value"],
        "headroom": _headroom(best["value"], direction=direction, unit=unit),
    }


def _selected_protocol_series(record: dict[str, Any]) -> dict[str, Any] | None:
    """Choose the closest-to-ceiling series among setups repeated on two dates."""

    direction = record["direction"]
    connectable = [series for series in record["series"] if series["connectable"]]
    if not connectable:
        return None
    higher_is_better = direction == "higher_is_better"
    return max(
        connectable,
        key=lambda series: (
            (
                _series_best(series, direction)["value"]
                if higher_is_better
                else -_series_best(series, direction)["value"]
            ),
            series["dated_points"],
            series["point_count"],
            series["last_reported_at"],
        ),
    )


def _threshold_summary(benchmarks: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [benchmark[key] for benchmark in benchmarks if benchmark[key] is not None]
    return {
        "eligible": len(values),
        "unknown": len(benchmarks) - len(values),
        "hits": {
            f"<={int(threshold)}": sum(value <= threshold for value in values)
            for threshold in _THRESHOLDS
        },
    }


def _document_for(registry: dict[str, Any], source_id: str) -> dict[str, Any]:
    card = next(card for card in registry["model_cards"] if str(card["id"]) == source_id)
    return {
        "id": str(card["id"]),
        "name": str(card.get("name") or card["id"]),
        "url": str(card.get("url") or ""),
        "caveat": str(card.get("caveat") or ""),
    }


def _claim_recommendation(*, raw_best_repeated: bool, repeated_headroom: float | None) -> str:
    if raw_best_repeated:
        return "retain"
    if repeated_headroom is None or repeated_headroom <= _NEAR_CEILING_THRESHOLD:
        return "qualify"
    return "replace"


def _recommendation_text(
    *,
    name: str,
    raw_best: dict[str, Any],
    raw_headroom: float,
    raw_best_series: dict[str, Any],
    repeated_series: dict[str, Any] | None,
    recommendation: str,
) -> tuple[str, str]:
    raw_setup = f"the {raw_best['protocol']} setup"
    if recommendation == "retain":
        reason = "The near-ceiling raw best is repeated under the same instrument and protocol."
        wording = (
            f"{name}'s best recorded result is {raw_best['value']:g}, leaving "
            f"{raw_headroom:g} points of headroom under {raw_setup}; that setup spans "
            f"{raw_best_series['dated_points']} dates."
        )
    elif repeated_series is None:
        reason = (
            "The near-ceiling raw best is an isolated setup and no instrument+protocol "
            "stratum spans two dates."
        )
        wording = (
            f"{name}'s {raw_best['value']:g} result leaves {raw_headroom:g} points of "
            "headroom under "
            f"{raw_setup}. No setup spans two dates, so the archive supports only this "
            "protocol-specific reading."
        )
    elif repeated_series["headroom"] <= _NEAR_CEILING_THRESHOLD:
        reason = (
            "The raw best is isolated, but a different repeated setup is also within the "
            "five-point threshold."
        )
        organization_count = repeated_series["organization_count"]
        organization_label = "organization" if organization_count == 1 else "organizations"
        wording = (
            f"{name}'s raw best is an isolated {raw_best['value']:g} result. A separate "
            f"{repeated_series['protocol']} setup spans {repeated_series['dated_points']} "
            f"dates from {organization_count} {organization_label} and leaves "
            f"{repeated_series['headroom']:g} points of headroom. This supports a "
            "protocol-specific paired comparison."
        )
    else:
        reason = (
            "The raw best is isolated and the closest repeated setup falls outside the "
            "five-point threshold."
        )
        wording = (
            f"{name}'s {raw_best['value']:g} raw best leaves {raw_headroom:g} points of "
            "headroom under "
            f"{raw_setup}, but that setup appears on one date. The closest repeated setup "
            f"leaves {repeated_series['headroom']:g} points, outside the five-point threshold."
        )
    return reason, wording


def build_saturation_audit(
    progression: dict[str, Any] | None = None,
    registry: dict[str, Any] | None = None,
    *,
    scores_path: Path = DEFAULT_SCORES_PATH,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    """Return the source-grounded audit rows for report section 6.2."""

    if registry is None:
        registry = load_registry(registry_path)
    if progression is None:
        progression = build_score_progression(scores_path, registry)

    benchmark_rows: list[dict[str, Any]] = []
    for benchmark_id in SECTION_6_2_BENCHMARK_IDS:
        record = progression["benchmarks"][benchmark_id]
        benchmark_card = next(card for card in registry["benchmarks"] if card["id"] == benchmark_id)
        direction = record["direction"]
        unit = record["unit"]
        raw_best = _best_row(record["observations"], direction)
        raw_headroom = record["saturation"]["headroom"]
        raw_series = next(
            series
            for series in record["series"]
            if series["instrument"] == raw_best["instrument"]
            and series["protocol"] == raw_best["protocol"]
        )
        raw_series_summary = _series_summary(raw_series, direction=direction, unit=unit)
        selected_series = _selected_protocol_series(record)
        repeated_summary = (
            _series_summary(selected_series, direction=direction, unit=unit)
            if selected_series is not None
            else None
        )
        repeated_headroom = repeated_summary["headroom"] if repeated_summary else None
        recommendation = _claim_recommendation(
            raw_best_repeated=raw_series["connectable"],
            repeated_headroom=repeated_headroom,
        )
        reason, wording = _recommendation_text(
            name=benchmark_card["name"],
            raw_best=raw_best,
            raw_headroom=raw_headroom,
            raw_best_series=raw_series_summary,
            repeated_series=repeated_summary,
            recommendation=recommendation,
        )

        source_ids = sorted({str(row["source_id"]) for row in record["observations"]})
        all_protocols = sorted({str(series["protocol"]) for series in record["series"]})
        all_instruments = sorted({str(series["instrument"]) for series in record["series"]})
        caveat = str(benchmark_card.get("caveat") or "")
        selected_ids = (
            {point["observation_id"] for point in selected_series["points"]}
            if selected_series is not None
            else set()
        )
        exclusion_reason = (
            "not in the selected repeated instrument+protocol series"
            if selected_series is not None
            else "no instrument+protocol series spans at least two dates"
        )
        excluded_rows = [
            row for row in record["observations"] if row["observation_id"] not in selected_ids
        ]
        exclusions = [
            {
                "observation_id": row["observation_id"],
                "reason": exclusion_reason,
            }
            for row in excluded_rows
        ]
        strongest_excluded = sorted(
            excluded_rows,
            key=lambda row: (row["value"], row["reported_at"], row["organization"], row["model"]),
            reverse=direction == "higher_is_better",
        )[:3]
        counterexamples = [
            {
                "observation_id": row["observation_id"],
                "source_id": row["source_id"],
                "instrument": row["instrument"],
                "protocol": row["protocol"],
                "model": row["model"],
                "organization": row["organization"],
                "reported_at": str(row["reported_at"]),
                "value": row["value"],
                "reason": exclusion_reason,
            }
            for row in strongest_excluded
        ]
        uncertainty = [
            (
                "The raw-best instrument+protocol setup appears on one date; its headroom "
                "is a protocol-specific fact, not repeated evidence."
            )
            if not raw_series["connectable"]
            else "The raw-best setup spans at least two dates."
        ]
        if repeated_summary is None:
            uncertainty.append("No instrument+protocol series spans at least two dates.")
        else:
            uncertainty.append(
                "The selected repeated setup spans "
                f"{repeated_summary['dated_points']} dates and "
                f"{repeated_summary['organization_count']} organization(s); it supports "
                "paired comparison, not a field-wide trend."
            )

        benchmark_rows.append(
            {
                "benchmark_id": benchmark_id,
                "name": benchmark_card["name"],
                "metric": record["metric"],
                "direction": direction,
                "unit": unit,
                "raw_headroom": raw_headroom,
                "repeat_controlled_headroom": repeated_headroom,
                "raw_best": {
                    "observation_id": raw_best["observation_id"],
                    "source_id": raw_best["source_id"],
                    "instrument": raw_best["instrument"],
                    "protocol": raw_best["protocol"],
                    "model": raw_best["model"],
                    "organization": raw_best["organization"],
                    "reported_at": str(raw_best["reported_at"]),
                    "value": raw_best["value"],
                    "read_from": raw_best["read_from"],
                    "reported_by": raw_best["reported_by"],
                },
                "raw_best_stratum": raw_series_summary,
                "selected_repeated_series": repeated_summary,
                "protocol_strata": [
                    _series_summary(series, direction=direction, unit=unit)
                    for series in record["series"]
                ],
                "recommendation": recommendation,
                "recommendation_reason": reason,
                "recommended_wording": wording,
                "source_documents": [
                    _document_for(registry, source_id) for source_id in source_ids
                ],
                "score_ids": [row["observation_id"] for row in record["observations"]],
                "conflicts": [
                    item
                    for item in (
                        (
                            f"instruments: {', '.join(all_instruments)}"
                            if len(all_instruments) > 1
                            else None
                        ),
                        (
                            f"protocols: {', '.join(all_protocols)}"
                            if len(all_protocols) > 1
                            else None
                        ),
                        caveat or None,
                    )
                    if item
                ],
                "uncertainty": uncertainty,
                "exclusions": exclusions,
                "counterexamples": counterexamples,
            }
        )

    repeated_available = sum(row["selected_repeated_series"] is not None for row in benchmark_rows)
    raw_best_repeated = sum(row["raw_best_stratum"]["connectable"] for row in benchmark_rows)
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "sources": {
            "scores": str(scores_path),
            "registry": str(registry_path),
            "canonical_measurement_layer": "data/benchmark_scores.yml",
        },
        "benchmark_count": len(benchmark_rows),
        "summary": {
            "raw_best_repeated": raw_best_repeated,
            "raw_best_isolated": len(benchmark_rows) - raw_best_repeated,
            "repeated_setup_available": repeated_available,
            "repeated_setup_unknown": len(benchmark_rows) - repeated_available,
        },
        "rules": {
            "raw_headroom": (
                "bound minus the best published value; this is a fact about one reading, "
                "not a trend or saturation verdict"
            ),
            "protocol_strata": "scores are grouped only when instrument and protocol match",
            "repeat_controlled_headroom": (
                "closest-to-ceiling best reading among instrument+protocol strata spanning "
                "at least two dates; this supports a paired comparison, not a trend"
            ),
            "claim_decision": (
                "retain when the raw-best setup repeats; qualify when repeated evidence is "
                "missing or separately remains near the ceiling; replace when a repeated "
                "setup exists but falls outside the five-point threshold"
            ),
            "thresholds": list(_THRESHOLDS),
        },
        "threshold_sensitivity": {
            "raw": _threshold_summary(benchmark_rows, "raw_headroom"),
            "repeated_protocol_series": _threshold_summary(
                benchmark_rows, "repeat_controlled_headroom"
            ),
        },
        "benchmarks": benchmark_rows,
    }


def write_saturation_audit(path: Path = DEFAULT_AUDIT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_saturation_audit(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()
    print(write_saturation_audit(args.output))


if __name__ == "__main__":
    main()
