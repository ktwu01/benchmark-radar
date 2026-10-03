from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from .http import get_json

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


def _fetch_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    payload = get_json(url, params=params)
    if not isinstance(payload, dict):
        raise ValueError("Hacker News search returned a non-object response")
    return payload


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def match_categories(title: str, taxonomy: dict[str, list[str]]) -> list[str]:
    haystack = title.casefold()
    return sorted(
        category
        for category, terms in taxonomy.items()
        if any(re.search(rf"\b{re.escape(str(term).casefold())}", haystack) for term in terms)
    )


def normalized_title(title: str) -> str:
    # Dropping non-ASCII words collapsed unrelated submissions into one
    # engagement total. Keep Unicode words, with canonical spelling normalized
    # so composed and decomposed accents still identify the same title.
    title = unicodedata.normalize("NFC", title.casefold())
    words = "".join(
        character if character.isalnum() or unicodedata.category(character).startswith("M") else " "
        for character in title
    )
    return " ".join(words.split())


def _numeric_id_sort_key(value: dict[str, Any]) -> tuple[bool, int]:
    """Sort by numeric HN object ID, not lexicographic string order.

    HN IDs are numeric but variable-length strings, so a string comparison
    puts "100" before "99" and would pick the wrong canonical observation for
    a cluster. Non-numeric IDs (never produced by this collector) sort last
    rather than crashing the whole cluster.
    """
    text = str(value["source_id"])
    return (not text.isdigit(), int(text) if text.isdigit() else 0)


def cluster_observations(
    observations: list[dict[str, Any]],
    *,
    preferred_source_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Cluster repeated titles while keeping the cluster identity immutable.

    A previous primary wins when present so IDs created by the standalone
    collector survive the migration. New clusters use the smallest immutable
    HN object ID; mutable points and comment counts never select identity.
    """
    preferred_source_ids = preferred_source_ids or set()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for observation in observations:
        key = (observation["source"], normalized_title(observation["title"]))
        groups.setdefault(key, []).append(observation)

    clustered: list[dict[str, Any]] = []
    for group in groups.values():
        preferred = [value for value in group if str(value["source_id"]) in preferred_source_ids]
        primary = min(preferred or group, key=_numeric_id_sort_key)
        result = {
            **primary,
            "categories": sorted({category for value in group for category in value["categories"]}),
            "metrics": {
                "points": sum(float(value["metrics"].get("points", 0)) for value in group),
                "comments": sum(float(value["metrics"].get("comments", 0)) for value in group),
                "submissions": float(len(group)),
            },
            "rationale": sorted({reason for value in group for reason in value["rationale"]}),
        }
        supporting = sorted(
            (value for value in group if value["source_id"] != primary["source_id"]),
            key=lambda value: (value["published_at"], value["source_id"]),
            reverse=True,
        )
        if supporting:
            result["rationale"].append(
                f"Clustered {len(group)} public submissions with the same normalized title"
            )
            result["supporting_observations"] = [
                {
                    "source_id": value["source_id"],
                    "url": value["url"],
                    "published_at": value["published_at"],
                    "metrics": value["metrics"],
                    **(
                        {"primary_artifact_url": value["primary_artifact_url"]}
                        if value.get("primary_artifact_url")
                        else {}
                    ),
                }
                for value in supporting
            ]
        clustered.append(result)
    return sorted(
        clustered,
        key=lambda value: (value["published_at"], value["source_id"]),
        reverse=True,
    )


def collect_hacker_news(
    config: dict[str, Any],
    now: datetime,
    fetcher: Callable[[str, dict[str, Any]], dict[str, Any]] = _fetch_json,
    *,
    preferred_source_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect public HN stories without treating attention as quality evidence."""
    now = now.astimezone(UTC)
    since = now - timedelta(hours=int(config.get("lookback_hours", 72)))
    limit = max(1, min(int(config.get("items_per_query", 30)), 100))
    found: dict[str, dict[str, Any]] = {}
    try:
        queries = config["queries"]
        taxonomy = config["taxonomy"]
        if not isinstance(queries, list) or not isinstance(taxonomy, dict):
            raise ValueError("Hacker News queries and taxonomy must be configured")
        for query in queries:
            payload = fetcher(
                HN_SEARCH_URL,
                {
                    "query": str(query),
                    "tags": "story",
                    "numericFilters": f"created_at_i>{int(since.timestamp())}",
                    "hitsPerPage": limit,
                },
            )
            hits = payload.get("hits")
            if not isinstance(hits, list):
                raise ValueError("Hacker News search response is missing a hits array")
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                source_id = str(hit.get("objectID") or "")
                title = str(hit.get("title") or "").strip()
                created_at = hit.get("created_at")
                if not source_id or not title or not created_at:
                    continue
                published = parse_time(str(created_at))
                if not since <= published <= now:
                    continue
                categories = match_categories(title, taxonomy)
                if not categories:
                    continue
                discussion_url = f"https://news.ycombinator.com/item?id={source_id}"
                artifact_url = hit.get("url")
                artifact_host = (
                    urlsplit(artifact_url).netloc
                    if isinstance(artifact_url, str)
                    and artifact_url.startswith(("https://", "http://"))
                    else ""
                )
                rationale = [
                    f"Public Hacker News story matched query: {query}",
                    "Attention signal only; not scientific-quality evidence",
                ]
                observation = found.get(source_id)
                if observation:
                    observation["categories"] = sorted(
                        set(observation["categories"]) | set(categories)
                    )
                    observation["rationale"] = sorted(
                        set(observation["rationale"]) | set(rationale)
                    )
                    continue
                observation = {
                    "id": f"hacker-news:{source_id}",
                    "source": "Hacker News",
                    "source_id": source_id,
                    "title": title,
                    "url": discussion_url,
                    "published_at": published.isoformat(),
                    "discovered_at": now.isoformat(),
                    "summary": (
                        f"Public Hacker News discussion linking to {artifact_host}."
                        if artifact_host
                        else "Public discussion submitted to Hacker News."
                    ),
                    "event_kind": "discussed",
                    "categories": categories,
                    "metrics": {
                        "points": float(hit.get("points") or 0),
                        "comments": float(hit.get("num_comments") or 0),
                    },
                    "rationale": rationale,
                }
                if artifact_host:
                    observation["primary_artifact_url"] = artifact_url
                found[source_id] = observation
    except Exception as error:
        return [], {
            "source": "Hacker News",
            "ok": False,
            "item_count": 0,
            "error": f"{type(error).__name__}: {error}",
        }
    observations = cluster_observations(
        list(found.values()),
        preferred_source_ids=preferred_source_ids,
    )
    return observations, {
        "source": "Hacker News",
        "ok": True,
        "item_count": len(observations),
        "error": None,
    }
