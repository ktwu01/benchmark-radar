"""Translate source-specific snapshot rows into the catalog row contract."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

SCORE_SERIES_POLICIES = frozenset({"observed_only", "preserve_empty"})


class CatalogSnapshotAdapterError(ValueError):
    """Raised when an adapter cannot translate a registered snapshot row."""


def _json_object(value: Any, *, label: str) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str):
        raise CatalogSnapshotAdapterError(f"{label} must be a JSON object")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise CatalogSnapshotAdapterError(f"{label} is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise CatalogSnapshotAdapterError(f"{label} must be a JSON object")
    return parsed


def _identity(
    row: Mapping[str, Any], *, options: Mapping[str, Any], snapshot_id: str
) -> dict[str, Any]:
    if options:
        raise CatalogSnapshotAdapterError(f"{snapshot_id}: identity adapter accepts no options")
    adapted = dict(row)
    source_id = str(adapted.get("benchmark_id") or "").strip()
    metadata = _json_object(
        adapted.get("extra_json"), label=f"{snapshot_id}:{source_id}:extra_json"
    )
    if metadata:
        adapted["source_metadata"] = metadata
    return adapted


def _claire_radar_v1(
    row: Mapping[str, Any], *, options: Mapping[str, Any], snapshot_id: str
) -> dict[str, Any]:
    adapted = _identity(row, options={}, snapshot_id=snapshot_id)
    source_id = str(adapted.get("benchmark_id") or "").strip()
    evidence = options.get("first_public_evidence") or {}
    if not isinstance(evidence, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in evidence.items()
    ):
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}: first_public_evidence must map source ids to URLs"
        )
    unknown_options = set(options) - {"first_public_evidence", "carried_forward"}
    if unknown_options:
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}: unsupported adapter options: {', '.join(sorted(unknown_options))}"
        )

    # Rows the exporter carried forward from an earlier snapshot were collected
    # then, not in this crawl, which no longer listed them. Keep that crawl time
    # so `collected_at` does not claim a fresh collection. Each crawl that rows
    # were last seen in is its own cohort, so a later refresh appends a cohort
    # rather than relabelling the rows an earlier one already carried.
    cohorts = options.get("carried_forward") or []
    if not isinstance(cohorts, list) or any(
        not isinstance(cohort, Mapping)
        or not isinstance(cohort.get("crawled_at"), str)
        or not isinstance(cohort.get("from_snapshot"), str)
        or not isinstance(cohort.get("benchmark_ids"), list)
        for cohort in cohorts
    ):
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}: carried_forward must list cohorts with from_snapshot, "
            "crawled_at and benchmark_ids"
        )
    matches = [cohort for cohort in cohorts if source_id in cohort["benchmark_ids"]]
    if len(matches) > 1:
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}:{source_id}: listed in more than one carried_forward cohort"
        )
    if matches:
        adapted["crawled_at"] = matches[0]["crawled_at"]

    metadata = adapted.get("source_metadata") or {}
    release_dates = metadata.get("releaseDates") or {}
    if not isinstance(release_dates, Mapping):
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}:{source_id}: releaseDates must be an object"
        )

    first_public = release_dates.get("firstPublicAt")
    if isinstance(first_public, str) and first_public.strip():
        adapted["released"] = first_public.strip()
        adapted["released_basis"] = "first_public"
        adapted["released_source_url"] = (
            str(evidence.get(source_id) or "").strip()
            or str(adapted.get("detail_source_url") or "").strip()
            or None
        )

    paper_date = release_dates.get("paperV1At")
    paper_url = str(adapted.get("paper_url") or "").strip()
    if isinstance(paper_date, str) and paper_date.strip() and paper_url:
        adapted["publication_dates"] = [
            {
                "date": paper_date.strip(),
                "basis": "paper_first_version",
                "source_url": paper_url,
            }
        ]
    return adapted


Adapter = Callable[..., dict[str, Any]]
CATALOG_ADAPTERS: dict[str, Adapter] = {
    "identity": _identity,
    "claire_radar_v1": _claire_radar_v1,
}


def adapt_catalog_row(
    row: Mapping[str, Any],
    *,
    adapter: str,
    adapter_options: Mapping[str, Any],
    snapshot_id: str,
) -> dict[str, Any]:
    """Return one source row expressed in the common catalog input contract."""
    try:
        implementation = CATALOG_ADAPTERS[adapter]
    except KeyError as error:
        raise CatalogSnapshotAdapterError(
            f"{snapshot_id}: unsupported catalog_adapter {adapter!r}"
        ) from error
    return implementation(row, options=adapter_options, snapshot_id=snapshot_id)
