from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .attention import fetch_attention_feeds
from .corpus import (
    artifact_alias_map,
    build_corpus,
    exact_artifact_key,
    organizations_for_item,
)
from .models import RadarRun
from .pipeline import match_proximity_rule
from .rubric import (
    SCORING_VERSION,
    legacy_rubric_reference,
    rubric_reference,
)

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, SCHEMA_VERSION}

# Mirrors the `required: true` sources in config.yml: the connectors that need
# no optional secret and whose failure `run_pipeline` already treats as fatal
# to the run. `coverage_gaps` below also flags optional sources (brave,
# openalex, ...), which fail on every run without their API key and would
# make a "degraded" signal fire constantly if used for that instead of this.
REQUIRED_SOURCES = {"arxiv", "huggingface", "github"}


class SnapshotError(ValueError):
    """Raised when persisted public data does not match the supported schema."""


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def snapshot_for_run(run: RadarRun) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "date": run.generated_at.astimezone(UTC).date().isoformat(),
        "generated_at": _iso_utc(run.generated_at),
        "since": _iso_utc(run.since),
        "evidence_items": [item.to_dict() for item in run.items],
        "attention": {
            "observations": [observation.to_dict() for observation in run.attention],
        },
        "ingest_health": [
            health.to_dict() for health in [*run.health, *run.attention_ingest_health]
        ],
        "producer_health": [health.to_dict() for health in run.producer_health],
        "selection": run.selection,
        "discovery_state": run.discovery_state,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_time(value: Any, *, source: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as error:
        raise SnapshotError(f"{source}: invalid {field}") from error


def _validate_evidence_items(items: Any, *, source: str) -> None:
    if not isinstance(items, list):
        raise SnapshotError(f"{source}: evidence_items must be an array")
    item_fields = {
        "source",
        "source_id",
        "title",
        "url",
        "published_at",
        "event_kind",
        "categories",
        "metrics",
        "evidence_score",
        "relevance_score",
        "recency_score",
        "adoption_score",
        "total_score",
        "rationale",
    }
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SnapshotError(f"{source}: evidence item {index} must be an object")
        if "raw" in item:
            raise SnapshotError(
                f"{source}: evidence item {index} must not expose raw source payloads"
            )
        item_missing = sorted(item_fields - item.keys())
        if item_missing:
            raise SnapshotError(
                f"{source}: evidence item {index} missing fields: {', '.join(item_missing)}"
            )
        if not str(item["url"]).startswith(("https://", "http://")):
            raise SnapshotError(f"{source}: evidence item {index} URL must be HTTP(S)")
        _validate_time(
            item["published_at"],
            source=source,
            field=f"evidence item {index} published_at",
        )
        for field in ("updated_at", "discovered_at"):
            if item.get(field):
                _validate_time(
                    item[field],
                    source=source,
                    field=f"evidence item {index} {field}",
                )
        if item.get("retrieved_at"):
            _validate_time(
                item["retrieved_at"],
                source=source,
                field=f"evidence item {index} retrieved_at",
            )
        if item.get("raw_payload_hash") and not re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(item["raw_payload_hash"])
        ):
            raise SnapshotError(f"{source}: evidence item {index} raw_payload_hash must use sha256")


def _validate_health(values: Any, *, source: str, field: str) -> None:
    if not isinstance(values, list):
        raise SnapshotError(f"{source}: {field} must be an array")
    for index, health in enumerate(values):
        if (
            not isinstance(health, dict)
            or not {
                "source",
                "ok",
                "item_count",
            }
            <= health.keys()
        ):
            raise SnapshotError(f"{source}: {field} {index} is invalid")


def _validate_attention(attention: Any, *, source: str) -> None:
    if not isinstance(attention, dict) or not isinstance(attention.get("observations"), list):
        raise SnapshotError(f"{source}: attention.observations must be an array")
    required = {
        "observation_id",
        "producer",
        "source",
        "source_id",
        "title",
        "url",
        "published_at",
        "discovered_at",
        "observed_at",
        "event_kind",
        "categories",
        "metrics",
        "rationale",
        "quality_scored",
    }
    for index, observation in enumerate(attention["observations"]):
        if not isinstance(observation, dict):
            raise SnapshotError(f"{source}: attention observation {index} must be an object")
        missing = sorted(required - observation.keys())
        if missing:
            raise SnapshotError(
                f"{source}: attention observation {index} missing fields: {', '.join(missing)}"
            )
        if observation["quality_scored"] is not False:
            raise SnapshotError(
                f"{source}: attention observation {index} must set quality_scored false"
            )
        if not str(observation["url"]).startswith(("https://", "http://")):
            raise SnapshotError(f"{source}: attention observation {index} URL must be HTTP(S)")
        for field in ("published_at", "discovered_at", "observed_at"):
            _validate_time(
                observation[field],
                source=source,
                field=f"attention observation {index} {field}",
            )
        for supporting_index, supporting in enumerate(
            observation.get("supporting_observations") or []
        ):
            if (
                not isinstance(supporting, dict)
                or not {
                    "source",
                    "source_id",
                    "url",
                    "published_at",
                    "metrics",
                }
                <= supporting.keys()
            ):
                raise SnapshotError(
                    f"{source}: attention observation {index} supporting observation "
                    f"{supporting_index} is invalid"
                )
            if not str(supporting["url"]).startswith(("https://", "http://")):
                raise SnapshotError(
                    f"{source}: attention observation {index} supporting observation "
                    f"{supporting_index} URL must be HTTP(S)"
                )
            _validate_time(
                supporting["published_at"],
                source=source,
                field=(
                    f"attention observation {index} supporting observation "
                    f"{supporting_index} published_at"
                ),
            )


def validate_snapshot(snapshot: dict[str, Any], *, source: str = "snapshot") -> None:
    version = snapshot.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SnapshotError(f"{source}: unsupported schema_version {version!r}")
    if version == 1:
        required = {"schema_version", "date", "generated_at", "since", "items", "health"}
    else:
        required = {
            "schema_version",
            "date",
            "generated_at",
            "since",
            "evidence_items",
            "attention",
            "ingest_health",
            "producer_health",
            "discovery_state",
        }
    missing = sorted(required - snapshot.keys())
    if missing:
        raise SnapshotError(f"{source}: missing fields: {', '.join(missing)}")
    generated = _validate_time(snapshot["generated_at"], source=source, field="generated_at")
    since = _validate_time(snapshot["since"], source=source, field="since")
    expected_date = generated.date().isoformat()
    if snapshot["date"] != expected_date:
        raise SnapshotError(
            f"{source}: date {snapshot['date']!r} does not match generated_at UTC date"
        )
    if since > generated:
        raise SnapshotError(f"{source}: since must not be after generated_at")
    if version == 1:
        _validate_evidence_items(snapshot["items"], source=source)
        _validate_health(snapshot["health"], source=source, field="health")
        return
    _validate_evidence_items(snapshot["evidence_items"], source=source)
    _validate_attention(snapshot["attention"], source=source)
    _validate_health(snapshot["ingest_health"], source=source, field="ingest_health")
    _validate_health(snapshot["producer_health"], source=source, field="producer_health")
    if not isinstance(snapshot["discovery_state"], dict):
        raise SnapshotError(f"{source}: discovery_state must be an object")
    # Optional: snapshots written before per-stage counts were tracked stay valid.
    if "selection" in snapshot and not isinstance(snapshot["selection"], dict):
        raise SnapshotError(f"{source}: selection must be an object")


def normalize_snapshot(snapshot: dict[str, Any], *, source: str = "snapshot") -> dict[str, Any]:
    validate_snapshot(snapshot, source=source)
    if snapshot["schema_version"] == SCHEMA_VERSION:
        return deepcopy(snapshot)
    evidence_items = []
    discovery_state: dict[str, Any] = {}
    for item in snapshot["items"]:
        normalized_item = {
            **item,
            "updated_at": item.get("updated_at"),
            "discovered_at": item.get("discovered_at") or snapshot["generated_at"],
        }
        evidence_items.append(normalized_item)
        if item["source"] == "arXiv":
            discovery_state.setdefault("arxiv", {})[item["source_id"]] = {
                "discovered_at": normalized_item["discovered_at"],
                "last_activity_at": item.get("updated_at") or item["published_at"],
            }
    normalized = {
        "schema_version": SCHEMA_VERSION,
        "date": snapshot["date"],
        "generated_at": snapshot["generated_at"],
        "since": snapshot["since"],
        "evidence_items": evidence_items,
        "attention": {"observations": []},
        "ingest_health": [
            {**health, "kind": health.get("kind") or "evidence"} for health in snapshot["health"]
        ],
        "producer_health": [],
        "discovery_state": discovery_state,
    }
    validate_snapshot(normalized, source=source)
    return normalized


def write_snapshot(run: RadarRun, snapshot_dir: Path) -> Path:
    snapshot = snapshot_for_run(run)
    validate_snapshot(snapshot)
    path = snapshot_dir / f"{snapshot['date']}.json"
    _write_json(path, snapshot)
    return path


def load_snapshots(snapshot_dir: Path) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SnapshotError(f"{path}: invalid JSON: {error}") from error
        snapshots.append(normalize_snapshot(snapshot, source=str(path)))
    snapshots.sort(key=lambda value: (value["date"], value["generated_at"]))
    return snapshots


TREND_BASELINE_DAYS = 7


def _collection_context(day: dict[str, Any]) -> tuple[Any, tuple[str, ...]]:
    return (
        (day.get("selection") or {}).get("report_limit"),
        tuple(day.get("coverage_signature") or []),
    )


def _attach_category_trends(days: list[dict[str, Any]]) -> None:
    """Add per-category deltas, baselines and cumulative totals to each day.

    "How many benchmarks landed today" is only half the question; the other
    half is which domain moved and by how much. Every figure here is a count of
    surfaced records, never a quality judgement.

    Only snapshots collected under the same report limit are compared. Raising
    the cap lifts every count at once, and presenting that as domain momentum
    would report a change in collection policy as a change in the field.

    Cumulative figures count distinct artifacts, not sightings. The scan window
    overlaps by design and only arXiv suppresses repeats, so summing daily
    counts would re-count the same repository every day it stayed in range and
    grow steadily while nothing new was found.

    Identity joins every exact identifier a record carries, not just one
    preferred key or `source:source_id`. A DOI-plus-arXiv observation and a
    later arXiv-only observation are two sightings of the same artifact.

    Deltas, baselines and momentum are built from `category_counts_released`,
    not the raw `category_counts`: a version bump reannounced as "updated" is
    not new activity in the field, so it must not move the 30-day change the
    way a first "released" sighting does (issue #50).
    """
    seen: dict[str, set[str]] = {}
    seen_any: set[str] = set()
    records_seen: list[dict[str, Any]] = []
    for index, day in enumerate(days):
        counts = day["category_counts_released"]
        records_seen.extend(day["evidence_items"])
        aliases = artifact_alias_map(records_seen)
        # A later observation can bridge identifiers previously thought to be
        # separate. Reconcile cumulative sets from this day forward without
        # leaking that later knowledge into already-published historical days.
        seen_any = {aliases.get(identity, identity) for identity in seen_any}
        seen = {
            category: {aliases.get(identity, identity) for identity in identities}
            for category, identities in seen.items()
        }
        for record in day["evidence_items"]:
            identity = aliases[exact_artifact_key(record)]
            seen_any.add(identity)
            for category in record["categories"]:
                seen.setdefault(category, set()).add(identity)
        cumulative = Counter({category: len(ids) for category, ids in seen.items()})
        context = _collection_context(day)
        comparable = [
            entry
            for entry in days[max(0, index - TREND_BASELINE_DAYS) : index]
            if _collection_context(entry) == context
        ]
        prior_day = days[index - 1] if index else None
        if prior_day is not None and _collection_context(prior_day) != context:
            prior_day = None
        previous = prior_day["category_counts_released"] if prior_day else {}
        trends = {}
        for category in sorted({*counts, *previous, *day["category_counts"]}):
            count = counts.get(category, 0)
            history = [entry["category_counts_released"].get(category, 0) for entry in comparable]
            baseline = round(sum(history) / len(history), 2) if history else None
            prior = previous.get(category, 0) if prior_day else None
            trends[category] = {
                "count": count,
                # The all-events figure this released-only count was drawn
                # from, so the UI can show how many re-announced updates were
                # set aside rather than silently dropping them.
                "total_count": day["category_counts"].get(category, 0),
                "previous": prior,
                "delta": None if prior is None else count - prior,
                "baseline": baseline,
                # Momentum compares today with its own recent average, so a
                # category is judged against its normal volume, not the corpus.
                "momentum": (
                    round((count - baseline) / baseline, 2) if baseline not in (None, 0) else None
                ),
                # Distinct artifacts seen in this category up to and including
                # today, so a repository lingering in the window counts once.
                "cumulative": cumulative[category],
                "comparable": prior_day is not None,
            }
        day["category_trends"] = trends
        day["cumulative_category_counts"] = dict(sorted(cumulative.items()))
        day["cumulative_evidence_count"] = len(seen_any)


def dashboard_data(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    categories: set[str] = set()
    sources: set[str] = set()
    organizations: set[str] = set()
    event_kinds: set[str] = set()
    for snapshot in snapshots:
        # Snapshot schema v2 predates scoring-version metadata. Preserve those
        # historical 0-4 values explicitly so a current 0-100 label and formula
        # can never be shown beside arithmetic they did not produce.
        evidence_items = [
            {
                **item,
                "score_version": int(item.get("score_version") or 1),
                "score_max": float(item.get("score_max") or 4.0),
                "organizations": organizations_for_item(item),
            }
            for item in snapshot["evidence_items"]
        ]
        observations = snapshot["attention"]["observations"]
        category_counts = Counter(
            category for item in evidence_items for category in item["categories"]
        )
        # A record re-announced as "updated" (a new version of a paper, a
        # repository pushing again) is not new activity in the field the way a
        # first "released" sighting is. Trend deltas built from the mixed count
        # register a version bump as if it were a fresh benchmark landing.
        category_counts_released = Counter(
            category
            for item in evidence_items
            if item["event_kind"] == "released"
            for category in item["categories"]
        )
        source_counts = Counter(item["source"] for item in evidence_items)
        event_counts = Counter(item["event_kind"] for item in evidence_items)
        attention_source_counts = Counter(item["source"] for item in observations)
        attention_event_counts = Counter(item["event_kind"] for item in observations)
        attention_new_count = sum(
            str(item["observed_at"]).startswith(snapshot["date"]) for item in observations
        )
        categories.update(category_counts)
        categories.update(
            category for item in observations for category in item.get("categories") or []
        )
        sources.update(source_counts)
        sources.update(attention_source_counts)
        organizations.update(
            organization
            for item in evidence_items
            for organization in item.get("organizations") or []
        )
        event_kinds.update(event_counts)
        event_kinds.update(attention_event_counts)
        evidence_health = [
            entry
            for entry in snapshot["ingest_health"]
            if entry.get("kind", "evidence") == "evidence"
        ]
        coverage_signature = sorted(
            f"{entry['source']}:{'ok' if entry['ok'] else 'failed'}" for entry in evidence_health
        )
        coverage_gaps = sorted(entry["source"] for entry in evidence_health if not entry["ok"])
        required_coverage_gaps = sorted(
            entry["source"]
            for entry in evidence_health
            if not entry["ok"] and entry["source"] in REQUIRED_SOURCES
        )
        days.append(
            {
                "date": snapshot["date"],
                "generated_at": snapshot["generated_at"],
                "since": snapshot["since"],
                "item_count": len(evidence_items),
                "evidence_count": len(evidence_items),
                "category_counts": dict(sorted(category_counts.items())),
                "category_counts_released": dict(sorted(category_counts_released.items())),
                "source_counts": dict(sorted(source_counts.items())),
                "event_kind_counts": dict(sorted(event_counts.items())),
                "evidence_items": evidence_items,
                "attention": {
                    "observations": observations,
                    "active_count": len(observations),
                    "new_count": attention_new_count,
                    "source_counts": dict(sorted(attention_source_counts.items())),
                    "event_kind_counts": dict(sorted(attention_event_counts.items())),
                },
                "ingest_health": snapshot["ingest_health"],
                "producer_health": snapshot["producer_health"],
                "selection": snapshot.get("selection") or {},
                "coverage_complete": not coverage_gaps,
                "coverage_gaps": coverage_gaps,
                "coverage_signature": coverage_signature,
                # Required-source health only: unlike coverage_complete above,
                # this ignores optional sources missing an API key so it can
                # drive a "degraded" signal without firing on every run.
                "required_coverage_complete": not required_coverage_gaps,
                "required_coverage_gaps": required_coverage_gaps,
            }
        )
    _attach_category_trends(days)
    corpus = build_corpus(snapshots)
    last_successful = next(
        (day for day in reversed(days) if day["required_coverage_complete"]), None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "latest_date": days[-1]["date"] if days else None,
        "snapshot_count": len(days),
        "generated_at": days[-1]["generated_at"] if days else None,
        # Distinct from `generated_at`: the most recent run where every
        # required source (arxiv, huggingface, github) reported `ok`, vs. the
        # most recent run at all. A stale-data banner needs both to tell "no
        # run happened" apart from "a run happened but a required connector
        # failed" (issue #53). Optional sources missing an API key do not
        # count against this.
        "last_successful_collection_at": (
            last_successful["generated_at"] if last_successful else None
        ),
        "degraded": not days[-1]["required_coverage_complete"] if days else False,
        "facets": {
            "dates": [day["date"] for day in days],
            "categories": sorted(categories),
            "sources": sorted(sources),
            "organizations": sorted(organizations),
            "event_kinds": sorted(event_kinds),
            "kinds": ["evidence", "attention"],
        },
        "days": days,
        "corpus": corpus,
        # Keep every rubric required by the history. The browser selects by
        # each record's score_version, so a v1 score is never explained using
        # v2 arithmetic.
        "rubrics": {
            "1": legacy_rubric_reference(),
            str(SCORING_VERSION): rubric_reference(
                minimum_score=(
                    (days[-1].get("selection") or {}).get("minimum_score")
                    if days
                    and (days[-1].get("selection") or {}).get("score_version") == SCORING_VERSION
                    else None
                ),
                lookback_hours=(
                    (days[-1].get("selection") or {}).get("lookback_hours") or 48 if days else 48
                ),
            ),
        },
        # Backward-compatible alias for the global information button.
        "rubric": rubric_reference(
            minimum_score=(
                (days[-1].get("selection") or {}).get("minimum_score")
                if days
                and (days[-1].get("selection") or {}).get("score_version") == SCORING_VERSION
                else None
            ),
            lookback_hours=(
                (days[-1].get("selection") or {}).get("lookback_hours") or 48 if days else 48
            ),
        ),
    }


def rebuild_dashboard(snapshot_dir: Path, output: Path) -> dict[str, Any]:
    value = dashboard_data(load_snapshots(snapshot_dir))
    _write_json(output, value)
    return value


def rescore_snapshot_history(
    config: dict[str, Any],
    snapshot_dir: Path,
) -> dict[str, Any]:
    """Recompute stored taxonomy categories for every snapshot on disk.

    Snapshots are append-only and were never rewritten when the taxonomy
    changed, so a category added on day N stayed absent from days 1..N-1 and
    the dashboard divided a one-day numerator by a nine-day denominator. That
    alone published `agentic: 3` when re-scoring the same corpus yielded 16
    (issue #52); no keyword change can fix it, because the old days simply
    carry no such tag.

    Only `categories` and the "Matched:" rationale are rewritten. Scores,
    timestamps, selection counts and health are left exactly as recorded: they
    describe what the pipeline did on the day it ran, and rewriting them would
    turn an audit trail into a fiction. The consequence is that a re-scored
    record can carry a category its stored `total_score` never reflected,
    which is the honest trade -- the tag is a property of the artifact, the
    score is a property of the run.
    """
    taxonomy = config["taxonomy"]
    paths = sorted(snapshot_dir.glob("*.json"))
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    changed = 0
    for path in paths:
        snapshot = normalize_snapshot(
            json.loads(path.read_text(encoding="utf-8")),
            source=str(path),
        )
        for record in snapshot.get("evidence_items") or []:
            previous = list(record.get("categories") or [])
            before.update(previous)
            haystack = f"{record.get('title', '')} {record.get('summary', '')}".lower()
            categories: list[str] = []
            matched: list[str] = []
            for category, terms in taxonomy.items():
                if isinstance(terms, dict):
                    hit = match_proximity_rule(haystack, terms)
                    matches = [hit] if hit else []
                else:
                    matches = [term for term in terms if term.lower() in haystack]
                if matches:
                    categories.append(category)
                    matched.extend(str(term) for term in matches[:2])
            after.update(categories)
            if categories != previous:
                changed += 1
            record["categories"] = categories
            rationale = [
                reason
                for reason in record.get("rationale") or []
                if not str(reason).startswith("Matched:")
            ]
            if matched:
                rationale.insert(0, f"Matched: {', '.join(sorted(set(matched)))}")
            record["rationale"] = rationale
        validate_snapshot(snapshot, source=str(path))
        _write_json(path, snapshot)
    return {
        "snapshots": len(paths),
        "records_changed": changed,
        "before": dict(sorted(before.items())),
        "after": dict(sorted(after.items())),
    }


def migrate_snapshot_history(config: dict[str, Any], snapshot_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(snapshot_dir.glob("*.json"))
    snapshots: list[dict[str, Any]] = []
    versions: list[int] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        versions.append(int(raw.get("schema_version") or 0))
        snapshots.append(normalize_snapshot(raw, source=str(path)))
    if snapshots and versions[-1] == 1:
        latest = snapshots[-1]
        observed_at = _validate_time(
            latest["generated_at"],
            source=str(paths[-1]),
            field="generated_at",
        )
        previous_attention = latest["discovery_state"].get("attention") or {}
        observations, ingest_health, producer_health, attention_state = fetch_attention_feeds(
            config.get("attention") or {},
            observed_at=observed_at,
            previous_state=previous_attention,
        )
        latest["attention"] = {
            "observations": [observation.to_dict() for observation in observations]
        }
        latest["ingest_health"] = [
            health for health in latest["ingest_health"] if health.get("kind") != "attention"
        ] + [health.to_dict() for health in ingest_health]
        latest["producer_health"] = [health.to_dict() for health in producer_health]
        latest["discovery_state"]["attention"] = attention_state
    for path, snapshot in zip(paths, snapshots, strict=True):
        validate_snapshot(snapshot, source=str(path))
        _write_json(path, snapshot)
    return snapshots
