from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from typing import Any
from urllib.parse import urlsplit

from .hacker_news import collect_hacker_news
from .http import get_json
from .models import AttentionObservation, ProducerHealth, SourceHealth

LEGACY_HACKER_NEWS_PRODUCER = "benchmark-social-signal"


def _metrics(values: Any) -> dict[str, float]:
    # Public feeds must not turn booleans into measurements or persist Infinity,
    # which cannot be read as a JSON number by downstream consumers.
    if not isinstance(values, dict):
        return {}
    normalized = {}
    for key, value in values.items():
        if type(value) not in (int, float):
            continue
        try:
            numeric = float(value)
        except OverflowError:
            continue
        if isfinite(numeric) and numeric >= 0:
            normalized[str(key)] = numeric
    return normalized


def _date(value: str | None, *, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _supporting_observations(
    values: Any,
    *,
    default_source: str,
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    supporting: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        url = _http_url(value.get("url"))
        source_id = str(value.get("source_id") or "").strip()
        published_at = value.get("published_at")
        if not url or not source_id or not published_at:
            continue
        supporting.append(
            {
                "source": str(value.get("source") or default_source),
                "source_id": source_id,
                "url": url,
                "published_at": str(published_at),
                "metrics": _metrics(value.get("metrics")),
                **(
                    {"primary_artifact_url": primary}
                    if (primary := _http_url(value.get("primary_artifact_url")))
                    else {}
                ),
            }
        )
    return supporting


def _normalize_feed(
    payload: dict[str, Any],
    *,
    name: str,
    observed_at: datetime,
    state: dict[str, Any],
) -> tuple[list[AttentionObservation], SourceHealth, list[ProducerHealth], dict[str, Any]]:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("observations"), list):
        raise ValueError("unsupported public observation feed schema")
    producer = str(payload.get("producer") or name)
    staged_state = deepcopy(state)
    staged: dict[str, AttentionObservation] = {}
    for raw in payload["observations"]:
        if not isinstance(raw, dict):
            continue
        raw_id = str(raw.get("id") or "").strip()
        source = str(raw.get("source") or producer).strip()
        source_id = str(raw.get("source_id") or "").strip()
        title = str(raw.get("title") or "").strip()
        record_url = _http_url(raw.get("url"))
        if not raw_id or not source_id or not title or not record_url:
            continue
        observation_id = f"{producer}:{raw_id}"
        previous = staged_state.get(observation_id) or {}
        first_observed = _date(previous.get("observed_at"), fallback=observed_at)
        published = _date(raw.get("published_at"), fallback=observed_at)
        discovered = _date(raw.get("discovered_at"), fallback=observed_at)
        staged[observation_id] = AttentionObservation(
            observation_id=observation_id,
            producer=producer,
            source=source,
            source_id=source_id,
            title=title,
            url=record_url,
            published_at=published,
            discovered_at=discovered,
            observed_at=first_observed,
            summary=str(raw.get("summary") or ""),
            event_kind=str(raw.get("event_kind") or "discussed"),
            authors=[str(author) for author in raw.get("authors") or []],
            primary_artifact_url=_http_url(raw.get("primary_artifact_url")),
            metrics=_metrics(raw.get("metrics")),
            categories=sorted(
                {str(category) for category in raw.get("categories") or [] if category}
            ),
            rationale=[str(reason) for reason in raw.get("rationale") or []],
            supporting_observations=_supporting_observations(
                raw.get("supporting_observations"),
                default_source=source,
            ),
        )
        staged_state[observation_id] = {
            "observed_at": first_observed.astimezone(UTC).isoformat(),
            "last_seen_at": observed_at.astimezone(UTC).isoformat(),
        }
    producer_health = []
    for raw_health in payload.get("health") or []:
        if not isinstance(raw_health, dict):
            continue
        producer_health.append(
            ProducerHealth(
                producer=producer,
                source=str(raw_health.get("source") or producer),
                ok=bool(raw_health.get("ok")),
                item_count=int(raw_health.get("item_count") or 0),
                error=(str(raw_health["error"]) if raw_health.get("error") is not None else None),
            )
        )
    return (
        list(staged.values()),
        SourceHealth(source=name, kind="attention", ok=True, item_count=len(staged)),
        producer_health,
        staged_state,
    )


def _restore_previous(
    values: list[dict[str, Any]],
    *,
    producer: str,
) -> list[AttentionObservation]:
    restored: list[AttentionObservation] = []
    for raw in values:
        if not isinstance(raw, dict) or raw.get("producer") != producer:
            continue
        try:
            restored.append(
                AttentionObservation(
                    observation_id=str(raw["observation_id"]),
                    producer=producer,
                    source=str(raw["source"]),
                    source_id=str(raw["source_id"]),
                    title=str(raw["title"]),
                    url=str(raw["url"]),
                    published_at=_date(str(raw["published_at"]), fallback=datetime.now(UTC)),
                    discovered_at=_date(str(raw["discovered_at"]), fallback=datetime.now(UTC)),
                    observed_at=_date(str(raw["observed_at"]), fallback=datetime.now(UTC)),
                    summary=str(raw.get("summary") or ""),
                    event_kind=str(raw.get("event_kind") or "discussed"),
                    authors=[str(author) for author in raw.get("authors") or []],
                    primary_artifact_url=_http_url(raw.get("primary_artifact_url")),
                    metrics=_metrics(raw.get("metrics")),
                    categories=[str(value) for value in raw.get("categories") or []],
                    rationale=[str(value) for value in raw.get("rationale") or []],
                    supporting_observations=_supporting_observations(
                        raw.get("supporting_observations"),
                        default_source=str(raw["source"]),
                    ),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return restored


def fetch_attention_feeds(
    config: dict[str, Any],
    *,
    observed_at: datetime,
    previous_state: dict[str, Any] | None = None,
    previous_observations: list[dict[str, Any]] | None = None,
) -> tuple[
    list[AttentionObservation],
    list[SourceHealth],
    list[ProducerHealth],
    dict[str, Any],
]:
    observations: dict[str, AttentionObservation] = {}
    ingest_health: list[SourceHealth] = []
    producer_health: list[ProducerHealth] = []
    state = deepcopy(previous_state or {})
    previous_observations = previous_observations or []

    hacker_news = config.get("hacker_news") or {}
    if hacker_news.get("enabled", False):
        name = "Hacker News collector"
        producer = str(hacker_news.get("producer") or LEGACY_HACKER_NEWS_PRODUCER)
        prior_source_ids = {
            str(value.get("source_id"))
            for value in previous_observations
            if isinstance(value, dict) and value.get("producer") == producer
        }
        raw_observations, raw_health = collect_hacker_news(
            hacker_news,
            observed_at,
            preferred_source_ids=prior_source_ids,
        )
        if raw_health.get("ok"):
            payload = {
                "schema_version": 1,
                "producer": producer,
                "generated_at": observed_at.astimezone(UTC).isoformat(),
                "observations": raw_observations,
                "health": [raw_health],
            }
            try:
                parsed, health, reported, state = _normalize_feed(
                    payload,
                    name=name,
                    observed_at=observed_at,
                    state=state,
                )
                observations.update((item.observation_id, item) for item in parsed)
                ingest_health.append(health)
                producer_health.extend(reported)
            except Exception as error:
                raw_health = {
                    "source": "Hacker News",
                    "ok": False,
                    "item_count": 0,
                    "error": f"{type(error).__name__}: {error}",
                }
        if not raw_health.get("ok"):
            error = str(raw_health.get("error") or "Hacker News collection failed")
            ingest_health.append(SourceHealth(source=name, kind="attention", ok=False, error=error))
            producer_health.append(
                ProducerHealth(
                    producer=producer,
                    source=str(raw_health.get("source") or "Hacker News"),
                    ok=False,
                    error=error,
                )
            )
            restored = _restore_previous(previous_observations, producer=producer)
            observations.update((item.observation_id, item) for item in restored)

    for feed_config in config.get("feeds", []):
        if not feed_config.get("enabled", True):
            continue
        name = str(feed_config.get("name") or feed_config.get("url") or "attention feed")
        url = _http_url(feed_config.get("url"))
        if not url:
            ingest_health.append(
                SourceHealth(
                    source=name,
                    kind="attention",
                    ok=False,
                    error="Feed URL must be HTTP(S)",
                )
            )
            continue
        try:
            payload = get_json(url)
            if not isinstance(payload, dict):
                raise ValueError("public observation feed must be an object")
            parsed, health, reported, state = _normalize_feed(
                payload,
                name=name,
                observed_at=observed_at,
                state=state,
            )
            observations.update((item.observation_id, item) for item in parsed)
            ingest_health.append(health)
            producer_health.extend(reported)
        except Exception as error:
            ingest_health.append(
                SourceHealth(
                    source=name,
                    kind="attention",
                    ok=False,
                    error=f"{type(error).__name__}: {error}",
                )
            )

    ordered = sorted(
        observations.values(),
        key=lambda item: (item.observed_at, item.published_at, item.observation_id),
        reverse=True,
    )
    return ordered, ingest_health, producer_health, state
