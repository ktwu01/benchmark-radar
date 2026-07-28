from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .attention import fetch_attention_feeds
from .models import RadarItem, RadarRun, SourceHealth
from .sources import SOURCE_FETCHERS

TRACKING_PARAMETERS = {"ref", "source", "utm_campaign", "utm_content", "utm_medium", "utm_source"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMETERS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalized_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def deduplicate(items: list[RadarItem]) -> list[RadarItem]:
    kept: dict[str, RadarItem] = {}
    for item in sorted(
        items,
        key=lambda value: value.updated_at or value.published_at,
        reverse=True,
    ):
        title_key = normalized_title(item.title)
        if len(title_key) >= 24:
            key = hashlib.sha256(title_key.encode()).hexdigest()
        else:
            key = hashlib.sha256(canonical_url(item.url).encode()).hexdigest()
        existing = kept.get(key)
        if existing:
            if item.url not in existing.artifact_urls:
                existing.artifact_urls.append(item.url)
            existing.metrics.update(
                {
                    metric: max(value, existing.metrics.get(metric, 0))
                    for metric, value in item.metrics.items()
                }
            )
            existing.rationale.append(f"Also found via {item.source}")
        else:
            kept[key] = item
    return list(kept.values())


def score_item(
    item: RadarItem,
    taxonomy: dict[str, list[str]],
    now: datetime | None = None,
) -> RadarItem:
    now = now or datetime.now(UTC)
    # Only match against text a human actually wrote about the artifact. If a
    # fetcher ever reintroduces a generated summary, the words in it must not
    # earn relevance -- otherwise the pipeline scores itself on its own prose.
    haystack = f"{item.title} {item.summary}".lower()
    categories = []
    matched_terms: list[str] = []
    for category, terms in taxonomy.items():
        matches = [term for term in terms if term.lower() in haystack]
        if matches:
            categories.append(category)
            matched_terms.extend(matches[:2])
    item.categories = categories
    item.relevance_score = min(4.0, 1.25 * len(categories) + 0.2 * len(matched_terms))

    evidence = 0.5
    if item.source in {"arXiv", "OpenAlex"}:
        evidence += 1.5
    if item.source in {"GitHub", "Hugging Face"}:
        evidence += 1.0
    if item.authors:
        evidence += 0.5
    if item.artifact_urls:
        evidence += 0.5
    item.evidence_score = min(evidence, 4.0)

    activity_at = item.updated_at or item.published_at
    age_hours = max(0.0, (now - activity_at).total_seconds() / 3600)
    item.recency_score = max(0.0, 4.0 - age_hours / 24)

    adoption = (
        math.log10(1 + item.metrics.get("stars", 0)) * 0.8
        + math.log10(1 + item.metrics.get("downloads", 0)) * 0.6
        + math.log10(1 + item.metrics.get("likes", 0)) * 0.5
        + math.log10(1 + item.metrics.get("citations", 0)) * 0.7
    )
    item.adoption_score = min(adoption, 4.0)
    item.total_score = round(
        0.4 * item.relevance_score
        + 0.25 * item.evidence_score
        + 0.2 * item.recency_score
        + 0.15 * item.adoption_score,
        2,
    )
    if matched_terms:
        item.rationale.append(f"Matched: {', '.join(sorted(set(matched_terms)))}")
    item.rationale.append(f"Primary record: {item.source}")
    return item


BOILERPLATE_THRESHOLD = 3


def assert_no_boilerplate_summaries(items: list[RadarItem]) -> None:
    """Fail the run when a fetcher emits one summary for many different records.

    A summary repeated across unrelated artifacts is templated text, not a
    description. It misleads the reader and, because `score_item` reads
    `summary`, it also inflates relevance for every record from that source.
    This is a hard error rather than a warning: a silently boilerplated report
    looks successful, which is how the defect survived unnoticed before.
    """
    counts = Counter(item.summary.strip().lower() for item in items if item.summary.strip())
    repeated = {text: n for text, n in counts.items() if n >= BOILERPLATE_THRESHOLD}
    if repeated:
        worst = max(repeated.items(), key=lambda pair: pair[1])
        raise RuntimeError(
            f"Refusing to publish templated descriptions: {worst[1]} records share the "
            f"summary {worst[0]!r}. Derive summaries from source metadata (see describe.py) "
            "and leave them empty when the source publishes none."
        )


def _date(value: str | None, *, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _apply_arxiv_discovery_state(
    fetched: list[RadarItem],
    *,
    now: datetime,
    state: dict[str, Any],
) -> list[RadarItem]:
    arxiv_state = state.setdefault("arxiv", {})
    changed: list[RadarItem] = []
    for item in fetched:
        previous = arxiv_state.get(item.source_id) or {}
        activity_at = item.updated_at or item.published_at
        item.discovered_at = _date(previous.get("discovered_at"), fallback=now)
        previous_activity = _date(
            previous.get("last_activity_at"),
            fallback=datetime.min.replace(tzinfo=UTC),
        )
        if not previous or activity_at > previous_activity:
            changed.append(item)
        arxiv_state[item.source_id] = {
            "discovered_at": item.discovered_at.astimezone(UTC).isoformat(),
            "last_activity_at": activity_at.astimezone(UTC).isoformat(),
        }
    return changed


def run_pipeline(
    config: dict[str, Any],
    now: datetime | None = None,
    *,
    previous_snapshot: dict[str, Any] | None = None,
) -> RadarRun:
    now = now or datetime.now(UTC)
    settings = config["radar"]
    since = now - timedelta(hours=int(settings["lookback_hours"]))
    limit = int(settings["max_items_per_source"])
    items: list[RadarItem] = []
    health: list[SourceHealth] = []
    discovery_state = deepcopy((previous_snapshot or {}).get("discovery_state") or {})
    for source_name, source_config in config["sources"].items():
        if not source_config.get("enabled", True):
            continue
        fetcher = SOURCE_FETCHERS[source_name]
        try:
            fetched = fetcher(source_config, since, limit)
            health.append(SourceHealth(source=source_name, ok=True, item_count=len(fetched)))
            if source_name == "arxiv":
                items.extend(
                    _apply_arxiv_discovery_state(
                        fetched,
                        now=now,
                        state=discovery_state,
                    )
                )
            else:
                for item in fetched:
                    item.discovered_at = now
                items.extend(fetched)
        except Exception as error:  # a partial report is preferable; health exposes the gap
            health.append(
                SourceHealth(
                    source=source_name,
                    ok=False,
                    error=f"{type(error).__name__}: {error}",
                )
            )
    required = {
        name
        for name, source_config in config["sources"].items()
        if source_config.get("enabled", True) and source_config.get("required", False)
    }
    required_health = {source.source: source for source in health if source.source in required}
    unavailable_required = []
    for source in sorted(required):
        source_health = required_health.get(source)
        if source_health is None:
            unavailable_required.append(f"{source} was not checked")
        elif not source_health.ok:
            unavailable_required.append(
                f"{source} failed" + (f" ({source_health.error})" if source_health.error else "")
            )
        elif source_health.item_count == 0:
            unavailable_required.append(f"{source} returned no records")
    if unavailable_required:
        raise RuntimeError(
            "Required discovery sources failed or returned no records: "
            + ", ".join(unavailable_required)
        )
    unique = deduplicate(items)
    scored = [score_item(item, config["taxonomy"], now) for item in unique]
    selected = [
        item
        for item in scored
        if item.total_score >= float(settings["minimum_score"]) and item.categories
    ]
    selected.sort(key=lambda item: (item.total_score, item.published_at), reverse=True)
    published = selected[: int(settings["report_limit"])]
    assert_no_boilerplate_summaries(published)
    attention, attention_health, producer_health, attention_state = fetch_attention_feeds(
        config.get("attention") or {},
        observed_at=now,
        previous_state=((previous_snapshot or {}).get("discovery_state") or {}).get("attention")
        or {},
    )
    return RadarRun(
        generated_at=now,
        since=since,
        items=published,
        health=health,
        attention=attention,
        attention_ingest_health=attention_health,
        producer_health=producer_health,
        discovery_state={
            **discovery_state,
            "attention": attention_state,
        },
    )
