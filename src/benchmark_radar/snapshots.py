from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .attention import fetch_attention_feeds
from .benchmark_scores import DEFAULT_SCORES_PATH, load_scores, score_progression
from .corpus import (
    artifact_alias_map,
    build_corpus,
    exact_artifact_key,
    organizations_for_item,
)
from .insights import build_insights
from .model_cards import DEFAULT_REGISTRY_PATH, adoption_rank, load_registry
from .models import RadarRun
from .pipeline import match_proximity_rule
from .rubric import (
    SCORING_VERSION,
    legacy_rubric_reference,
    rubric_reference,
    taxonomy_version,
)

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, SCHEMA_VERSION}
# Mirrors briefing.MAX_BULLETS. Defined here rather than imported because
# `briefing` imports this module, and a validator cannot depend on its caller.
MAX_BRIEFING_BULLETS = 3

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
    date = run.generated_at.astimezone(UTC).date().isoformat()
    briefing = {"date": date, "bullets": list(run.daily_briefing)} if run.daily_briefing else None
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date,
        "generated_at": _iso_utc(run.generated_at),
        "since": _iso_utc(run.since),
        # Omitted entirely when the day has no briefing, so an absent key means
        # "not generated yet" and a later pass knows to retry.
        **({"briefing": briefing} if briefing else {}),
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


def _validate_briefing(briefing: Any, *, source: str, date: str) -> None:
    if not isinstance(briefing, dict):
        raise SnapshotError(f"{source}: briefing must be an object")
    if briefing.get("date") != date:
        raise SnapshotError(
            f"{source}: briefing date {briefing.get('date')!r} "
            f"does not match snapshot date {date!r}"
        )
    bullets = briefing.get("bullets")
    if not isinstance(bullets, list) or not bullets:
        raise SnapshotError(f"{source}: briefing.bullets must be a non-empty array")
    if len(bullets) > MAX_BRIEFING_BULLETS:
        raise SnapshotError(
            f"{source}: briefing.bullets holds {len(bullets)} entries, "
            f"more than the {MAX_BRIEFING_BULLETS} a briefing may carry"
        )
    for bullet in bullets:
        if not isinstance(bullet, str) or not bullet.strip():
            raise SnapshotError(f"{source}: briefing.bullets entries must be non-empty strings")


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
    # Optional: snapshots written before the briefing was persisted stay valid.
    # An extra key passing the required-field check is not enough, because a
    # briefing carrying the wrong date would be reused as if it described this
    # day. A mismatch is a bug in whatever wrote the file, not a day to
    # silently regenerate, so it fails loudly here.
    if "briefing" in snapshot:
        _validate_briefing(snapshot["briefing"], source=source, date=snapshot["date"])


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


def merge_snapshots(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Union two passes over the same UTC day into one snapshot.

    Issue #104: the radar runs twice a day and both passes write the same
    `data/snapshots/<date>.json`. Last-write-wins silently discarded whatever
    the earlier pass had already committed. On 2026-08-02 the two passes
    returned 62 and 68 items with only 41 shared, so the published day lost 21
    real records.

    The cause is fetch truncation, not a narrow lookback. GitHub saturates
    `max_items_per_source` on every pass and `sources.py` keeps the newest
    `[:limit]`, so older-but-still-in-window records fall off the back of one
    pass and not the other. Widening the window would not recover them; only
    unioning the passes on write does.

    Item identity is `exact_artifact_key`, the same exact-identifier rule daily
    dedup and the cumulative corpus already use. On a collision the incoming
    (newer) record wins: it observed the artifact more recently, so its metrics
    and scores are the fresher reading.
    """
    merged_items: dict[str, Any] = {}
    for item in existing["evidence_items"]:
        merged_items[exact_artifact_key(item)] = item
    for item in incoming["evidence_items"]:
        merged_items[exact_artifact_key(item)] = item
    evidence_items = list(merged_items.values())

    # Attention collection normally carries the previous pass forward, but a
    # successful feed can still return a narrower moving window. Persist the
    # explicit union so the canonical day matches the report and remains the
    # complete baseline for tomorrow's briefing. The newer observation wins
    # on collision because its engagement metrics are fresher.
    merged_attention: dict[str, Any] = {}
    for observation in (existing.get("attention") or {}).get("observations") or []:
        merged_attention[observation["observation_id"]] = observation
    for observation in (incoming.get("attention") or {}).get("observations") or []:
        merged_attention[observation["observation_id"]] = observation

    # The funnel counters (fetched, deduplicated, scored, qualified,
    # suppressed_*) each measure rows moving through one pass. They cannot be
    # reconstructed from the union, and summing them would double-count the
    # artifacts both passes saw, so they stay as the newer pass's numbers.
    #
    # That makes them a different scope from the file's contents, and the two
    # must not be read as one funnel. A pass that fetches nothing (an outage,
    # or a quiet day) merged onto a populated file would otherwise report
    # `fetched: 0` beside `published: 62`, which is not a small inaccuracy but
    # an impossible funnel a dashboard would render as fact. So `published`
    # moves out to `published_total`, which is about the file, and the
    # per-pass block keeps its own internally consistent `published`.
    selection = dict(incoming.get("selection") or {})
    existing_selection = existing.get("selection") or {}
    if selection or existing_selection:
        # The one number that describes the file rather than a pass. Every
        # other counter here belongs to the pass named last in `merged_from`.
        selection["published_total"] = len(evidence_items)
        selection["merged_from"] = sorted(
            {
                *(existing_selection.get("merged_from") or [existing["generated_at"]]),
                incoming["generated_at"],
            }
        )

    # One UTC day holds exactly one briefing. `incoming` is a fresh run, so
    # spreading it below would drop a briefing the earlier pass already
    # committed. First success wins: the stored text stays, and a later pass
    # only supplies one when the day still has none. Without this, an earlier
    # pass's briefing would be silently replaced on every subsequent run.
    briefing = existing.get("briefing") or incoming.get("briefing")

    merged = {
        **incoming,
        "evidence_items": evidence_items,
        "attention": {"observations": list(merged_attention.values())},
        # The union covers everything either pass looked at, so the earlier
        # `since` is the honest lower bound on the window it describes.
        "since": min(existing["since"], incoming["since"]),
    }
    if briefing:
        merged["briefing"] = briefing
    else:
        merged.pop("briefing", None)
    if selection or existing_selection:
        merged["selection"] = selection
    # `discovery_state` is cumulative by construction: the later pass loads
    # the earlier snapshot and carries the ledger forward.
    # `ingest_health` and `producer_health` are per-pass and are taken from the
    # incoming pass unmerged, because concatenating them would emit duplicate
    # `source` rows and corrupt the coverage_signature derived from them.
    return merged


def write_snapshot(run: RadarRun, snapshot_dir: Path) -> Path:
    snapshot = snapshot_for_run(run)
    path = snapshot_dir / f"{snapshot['date']}.json"
    if path.exists():
        # Issue #104: a second pass on the same UTC day must add to the day's
        # record, not replace it. A file we cannot read is not an empty day, so
        # fail rather than overwrite evidence that may still be recoverable.
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SnapshotError(f"{path}: cannot read existing snapshot to merge: {error}") from (
                error
            )
        snapshot = merge_snapshots(normalize_snapshot(existing, source=str(path)), snapshot)
    validate_snapshot(snapshot)
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


def _collection_context(day: dict[str, Any]) -> tuple[Any, tuple[str, ...], Any]:
    return (
        (day.get("selection") or {}).get("report_limit"),
        tuple(day.get("coverage_signature") or []),
        # The taxonomy that produced this day's categories (issue #72). Two days
        # classified under different rules are not comparable on a category
        # count, for the same reason two days collected under different report
        # limits are not: the number moved because the measurement changed.
        # PR #67 is the worked example -- it took cumulative `agentic` from 3 to
        # 78 without a single new benchmark, and a trend line spanning that
        # change would report a rules fix as a domain explosion.
        #
        # A day predating this field returns None, which compares equal to
        # other pre-field days and unequal to stamped ones. That is the honest
        # answer: unstamped days were classified by rules nobody recorded, so
        # they can be compared with each other but not asserted comparable to
        # a day whose rules are known.
        (day.get("selection") or {}).get("taxonomy_version"),
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


def _same_file(left: Path, right: Path) -> bool:
    """Whether two paths name one file, comparing resolved forms.

    `Path.samefile` needs both to exist, and the whole point of this check is that
    one of them may not, so it compares resolved paths instead. `strict=False`
    keeps a nonexistent path comparable rather than raising.
    """
    return left.resolve(strict=False) == right.resolve(strict=False)


def _curated_layers(
    registry_path: Path | None,
    scores_path: Path | None,
) -> dict[str, Any]:
    """Build the three curated layers that share one registry read.

    A missing file is not an error: the daily radar's own collection is
    independent of these curated datasets, and a checkout without them should
    still publish a working dashboard. An *invalid* file is a different matter
    and is allowed to fail the build, because a silently-dropped layer would
    leave the previous version on the page with no indication it went stale.

    The registry is read once and passed to both consumers. Reading it twice
    would let the score layer's cross-check pass against a different revision of
    the file than the ranking was built from, which is exactly the disagreement
    the cross-check exists to prevent.
    """
    registry_file = registry_path or DEFAULT_REGISTRY_PATH
    registry = load_registry(registry_file) if registry_file.exists() else None
    leaderboard = adoption_rank(registry) if registry else None

    # The two curated files are a matched pair: every score cites a `source_id`
    # that must be a document in the registry beside it. Defaulting the score
    # file under a *custom* registry therefore pairs scores with a registry that
    # was never meant to hold them, and the provenance cross-check correctly
    # rejects it -- which broke `--model-cards` for every alternate registry that
    # does not happen to contain all nine default score sources.
    #
    # So the default score file is only assumed when the registry is also the
    # default one. A caller supplying a custom registry opts into scores
    # explicitly via `--benchmark-scores`, and gets a working adoption-only
    # rebuild otherwise.
    # Compared by path, not against None: the CLI always supplies a
    # `--model-cards` value (it has a default), so "the caller passed nothing"
    # and "the caller passed the default" have to be treated alike here.
    #
    # Resolved before comparing, because `--model-cards "$PWD/data/model_cards.yml"`
    # names the same file as the relative default and would otherwise be treated
    # as a custom registry, silently dropping scores and insights from a build
    # that should have carried them.
    scores_file = scores_path
    if scores_file is None and _same_file(registry_file, DEFAULT_REGISTRY_PATH):
        scores_file = DEFAULT_SCORES_PATH
    # The score layer cites `source_id`s that must exist in the registry, so it
    # is only built when the registry it cites is present. Publishing scores
    # whose provenance cannot be checked would break the one promise this
    # dataset makes about itself.
    progression = (
        score_progression(load_scores(scores_file), registry)
        if scores_file is not None and scores_file.exists() and registry
        else None
    )

    return {
        "model_card_leaderboard": leaderboard,
        "benchmark_score_progression": progression,
        "benchmark_insights": build_insights(leaderboard, progression),
    }


def dashboard_data(
    snapshots: list[dict[str, Any]],
    *,
    registry_path: Path | None = None,
    scores_path: Path | None = None,
) -> dict[str, Any]:
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
                # Empty object on days generated before the briefing was
                # persisted, or days where the call was skipped or failed. The
                # dashboard renders its own absent state from that.
                "briefing": snapshot.get("briefing") or {},
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
        # Curated and versioned in the repository rather than collected daily:
        # they answer "which benchmarks do vendors report", "how have the
        # readable scores moved", and "what do those two together say", which
        # are different questions from "what was released today" and move on a
        # different clock.
        **_curated_layers(registry_path, scores_path),
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


def rebuild_dashboard(
    snapshot_dir: Path,
    output: Path,
    *,
    registry_path: Path | None = None,
    scores_path: Path | None = None,
) -> dict[str, Any]:
    value = dashboard_data(
        load_snapshots(snapshot_dir),
        registry_path=registry_path,
        scores_path=scores_path,
    )
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
    version = taxonomy_version(taxonomy)
    paths = sorted(snapshot_dir.glob("*.json"))
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    changed = 0
    migrated: list[str] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        snapshot = normalize_snapshot(raw, source=str(path))
        # Normalizing a v1 document renames `items` to `evidence_items` and
        # synthesizes the v2-only blocks, which is a schema migration rather
        # than a rescore. `migrate` exists as its own command precisely so that
        # rewrite is a deliberate act, so report it instead of performing it
        # silently under a summary that reads "0 records changed".
        if int(raw.get("schema_version") or 0) != int(snapshot.get("schema_version") or 0):
            migrated.append(path.name)
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
                # A rewritten category is a third kind of event, alongside
                # "released" and "updated" (issue #72). Without this marker a
                # reclassification is indistinguishable from a fresh sighting
                # once written: PR #67 moved cumulative `agentic` from 3 to 78
                # in a single command, and a reader had no way to tell that
                # from 75 agent benchmarks appearing. `event_kind` is left
                # alone deliberately -- it records what the *source* announced,
                # and rewriting it here would destroy that to describe
                # something the source never did.
                record["reclassified"] = {
                    "from": previous,
                    "to": list(categories),
                    # Which rules did the rewriting. Two reclassification
                    # passes under different taxonomies are different events,
                    # and only the version tells them apart.
                    "taxonomy_version": version,
                }
            else:
                # Cleared when a later pass leaves the categories alone.
                # `rescore` is idempotent and gets re-run routinely, so a marker
                # that is only ever written accumulates: a record reclassified
                # once would carry that claim forever, and a reader auditing a
                # trend would attribute today's count to a rules change that
                # happened weeks ago and has since settled. The marker has to
                # describe this pass or it describes nothing.
                record.pop("reclassified", None)
            record["categories"] = categories
            # Stamped on every record, not only the changed ones. A record
            # whose categories happened not to move was still evaluated by
            # these rules, and "classified by taxonomy X" is what makes a
            # cross-day category count comparable at all.
            record["taxonomy_version"] = version
            rationale = [
                reason
                for reason in record.get("rationale") or []
                if not str(reason).startswith("Matched:")
            ]
            if matched:
                rationale.insert(0, f"Matched: {', '.join(sorted(set(matched)))}")
            record["rationale"] = rationale
        # The snapshot's own selection block records the taxonomy its counts
        # were computed under, so a consumer reading aggregates rather than
        # individual records inherits the same provenance.
        selection = snapshot.get("selection")
        if isinstance(selection, dict):
            selection["taxonomy_version"] = version
        validate_snapshot(snapshot, source=str(path))
        _write_json(path, snapshot)
    return {
        "snapshots": len(paths),
        "records_changed": changed,
        "schema_migrated": migrated,
        "taxonomy_version": version,
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
