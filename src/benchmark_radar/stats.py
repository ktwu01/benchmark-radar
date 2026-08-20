"""Deterministic daily statistics with stable IDs, computed before any model call.

Every number the daily Q&A publishes is computed here and referenced by ID.
The model receives statements like `S007` and cites them; the renderer prints
the value from this registry, never from model prose. A model that invents
"downloads tripled" cannot get that number published, because publication reads
the registry and an unknown ID fails validation.

This is the same discipline `findings.py` applies to composition shifts, applied
to the whole answer surface. The gates there are reused rather than reimplemented:
a statistic derived from a window `findings.comparable_window` refuses to certify
is not published, because two days measured under different taxonomies or with a
connector missing are not measuring the same thing.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import findings
from .corpus import build_corpus

STATS_SCHEMA_VERSION = 1

# A tracked artifact needs corroboration from more than one connector before its
# movement is described as independently observed. One connector listing the
# same artifact twice is one observation, not two.
CORROBORATION_SOURCES = 2
# Topic velocity is noise below this many distinct artifacts.
MIN_TOPIC_ENTITIES = 3


class Stat:
    """One computed number, its wording, and what it was derived from."""

    __slots__ = ("id", "label", "value", "unit", "window", "evidence_ids", "detail")

    def __init__(
        self,
        stat_id: str,
        label: str,
        value: float | int,
        *,
        unit: str = "count",
        window: str = "today",
        evidence_ids: list[str] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.id = stat_id
        self.label = label
        self.value = value
        self.unit = unit
        self.window = window
        self.evidence_ids = evidence_ids or []
        self.detail = detail or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "window": self.window,
            "evidence_ids": self.evidence_ids,
            **({"detail": self.detail} if self.detail else {}),
        }


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def build_registry(
    history: list[dict[str, Any]],
    current: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute every publishable statistic for one day.

    Returns the registry plus the comparability verdict. A caller that finds
    `comparable` false must not publish trend language: the window could not be
    certified, and "rising" would be a claim the data does not support.
    """
    stats: list[Stat] = []
    counter = iter(range(1, 10_000))

    def add(label: str, value: float | int, **kwargs: Any) -> Stat:
        stat = Stat(f"S{next(counter):03d}", label, value, **kwargs)
        stats.append(stat)
        return stat

    items = list(current.get("evidence_items") or [])
    attention = list((current.get("attention") or {}).get("observations") or [])
    total = len(items)

    add("evidence records captured today", total)
    add("public attention observations captured today", len(attention))

    events = Counter(str(item.get("event_kind") or "unknown") for item in items)
    for event, count in events.most_common():
        add(
            f"records with event kind {event}",
            count,
            detail={"share_pct": _pct(count, total), "denominator": total},
        )

    sources = Counter(str(item.get("source") or "unknown") for item in items)
    for source, count in sources.most_common():
        add(
            f"records contributed by {source}",
            count,
            detail={"share_pct": _pct(count, total), "denominator": total},
        )

    # Category shares are multi-label: a record carrying both `benchmark` and
    # `agentic` counts in both, so these do not sum to the record total and must
    # never be presented as a partition.
    categories = Counter(str(value) for item in items for value in (item.get("categories") or []))
    for category, count in categories.most_common(12):
        add(
            f"records tagged {category}",
            count,
            unit="count (multi-label)",
            detail={
                "share_of_records_pct": _pct(count, total),
                "denominator": total,
                "note": "categories overlap; shares do not sum to 100%",
            },
        )

    fresh = findings.first_seen_items(history)
    add("artifacts first observed by the radar today", len(fresh))

    corpus_stats, tracked = _corpus_statistics(history, current, add)

    window = findings.comparable_window(history, config)
    comparable = window is not None
    shift = findings.composition_shift(history, config) if comparable else None
    if shift:
        add(
            f"composition shift in {shift.get('category')}",
            round(float(shift.get("recent_share") or 0.0), 1),
            unit="percent of daily records",
            window=f"{len(window[0])}-day recent vs {len(window[1])}-day baseline",
            detail={
                "baseline_share_pct": round(float(shift.get("baseline_share") or 0.0), 1),
                "shift_points": round(float(shift.get("shift_points") or 0.0), 1),
                "direction": "rising" if shift.get("rising") else "falling",
                "contributing_sources": shift.get("sources_moved"),
            },
        )

    return {
        "schema_version": STATS_SCHEMA_VERSION,
        "date": current.get("date"),
        "comparable": comparable,
        "comparability_note": (
            "Windows certified by findings.comparable_window: every day clears the "
            "item floor, data source coverage, and identical measurement settings."
            if comparable
            else "No certified comparison window today. Do not use trend language: "
            "differences between days may be collection changes rather than field changes."
        ),
        "stats": [stat.as_dict() for stat in stats],
        "tracked_artifacts": tracked,
        **corpus_stats,
    }


def _corpus_statistics(
    history: list[dict[str, Any]],
    current: dict[str, Any],
    add: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Cross-day statistics read from the derived corpus graph."""
    if not history:
        return {}, []
    current_date = str(current.get("date") or "")
    corpus = build_corpus(history)
    today_ids = {
        observation["entity_id"]
        for observation in corpus["observations"]
        if observation["snapshot_date"] == current_date
    }
    # Which connectors actually reported each metric, not merely which ones saw
    # the artifact. An artifact found via GitHub and Hugging Face where only
    # Hugging Face publishes downloads has one source for that number.
    metric_sources: dict[tuple[str, str], set[str]] = {}
    for observation in corpus["observations"]:
        for metric in observation.get("metrics") or {}:
            key = (observation["entity_id"], metric)
            metric_sources.setdefault(key, set()).add(observation["source"])
    artifacts = [entity for entity in corpus["entities"] if entity["type"] == "artifact"]
    returning = [
        entity
        for entity in artifacts
        if entity["id"] in today_ids and len(entity.get("seen_days") or []) > 1
    ]
    add("artifacts seen today that the radar had already tracked", len(returning))

    corroborated = [
        entity for entity in returning if len(entity.get("sources") or []) >= CORROBORATION_SOURCES
    ]
    add(
        "tracked artifacts today seen by more than one data source",
        len(corroborated),
        detail={
            "note": (
                "independent sighting of the artifact; a single data source twice is one "
                "observation. This does not mean both data sources measured the same metric: "
                "per-metric corroboration is reported on each movement statistic."
            )
        },
    )

    tracked: list[dict[str, Any]] = []
    for entity in returning:
        # `build_corpus` emits deltas only for metrics present at both
        # endpoints, so a nonzero value here is real movement rather than a
        # field the connector just started publishing.
        deltas = {key: value for key, value in (entity.get("metric_deltas") or {}).items() if value}
        if not deltas:
            continue
        seen_days = list(entity.get("seen_days") or [])
        # Corroboration is per metric. Two connectors seeing the artifact says
        # nothing about whether both measured the number that moved.
        delta_sources = {
            metric: sorted(metric_sources.get((entity["id"], metric)) or ()) for metric in deltas
        }
        tracked.append(
            {
                "entity_id": entity["id"],
                "title": entity.get("label"),
                "url": entity.get("url"),
                "sources": list(entity.get("sources") or []),
                "seen_days": len(seen_days),
                "first_seen_at": entity.get("first_seen_at"),
                "last_seen_at": entity.get("last_seen_at"),
                "metric_deltas": deltas,
                "metric_sources": delta_sources,
                "corroborated": any(
                    len(names) >= CORROBORATION_SOURCES for names in delta_sources.values()
                ),
            }
        )
    tracked.sort(
        key=lambda entry: max(abs(value) for value in entry["metric_deltas"].values()),
        reverse=True,
    )
    for entry in tracked[:8]:
        metric, value = max(entry["metric_deltas"].items(), key=lambda pair: abs(pair[1]))
        span = f"{entry['first_seen_at']} to {entry['last_seen_at']} ({entry['seen_days']} days)"
        stat = add(
            f"{metric} change for {entry['title']}",
            value,
            unit=metric,
            window=span,
            detail={
                "cumulative": True,
                "note": "movement across the whole tracked span, not a one-day change",
                # Connectors that reported THIS metric, not merely the artifact.
                "corroborated": len(entry["metric_sources"].get(metric) or [])
                >= CORROBORATION_SOURCES,
                "sources": entry["metric_sources"].get(metric) or [],
                "url": entry["url"],
            },
        )
        entry["stat_id"] = stat.id

    topics = [
        topic
        for topic in (corpus.get("aggregates") or {}).get("topics") or []
        if topic.get("velocity") is not None and topic.get("entity_count", 0) >= MIN_TOPIC_ENTITIES
    ]
    topics.sort(key=lambda topic: abs(float(topic.get("velocity") or 0)), reverse=True)
    window_days = (corpus.get("aggregates") or {}).get("observed_window_days")
    for topic in topics[:6]:
        add(
            f"daily-average change in {topic['topic']} observations",
            round(float(topic["velocity"]), 2),
            unit="observations per day",
            window=f"{window_days}-day recent vs prior window",
            detail={
                "recent_daily_average": topic.get("recent_daily_average"),
                "baseline_daily_average": topic.get("baseline_daily_average"),
                "distinct_artifacts": topic.get("entity_count"),
                "source_breadth": topic.get("source_breadth"),
                "persistence_days": topic.get("persistence_days"),
            },
        )

    return {
        "corpus_artifact_count": len(artifacts),
        "corpus_observation_count": corpus["observation_count"],
    }, tracked


def stat_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map stat ID to its record, for validating what a model cited."""
    return {stat["id"]: stat for stat in registry.get("stats") or []}
