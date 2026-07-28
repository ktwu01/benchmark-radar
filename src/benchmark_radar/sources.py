from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from .describe import github_summary, huggingface_summary
from .http import get_json, get_text
from .models import RadarItem


def _date(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _arxiv_source_id(value: str) -> str:
    identifier = value.rsplit("/", 1)[-1].replace("oai:arXiv.org:", "")
    return re.sub(r"v\d+$", "", identifier)


def _fetch_arxiv_rss(
    config: dict[str, Any],
    *,
    overlap_since: datetime,
    limit: int,
) -> list[RadarItem]:
    namespaces = {
        "arxiv": "http://arxiv.org/schemas/atom",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    keywords = [
        str(keyword).casefold()
        for keyword in config.get(
            "rss_keywords",
            [
                "benchmark",
                "evaluation",
                "leaderboard",
                "dataset",
                "test set",
                "data contamination",
                "benchmark leakage",
                "data quality",
            ],
        )
    ]
    found: dict[str, RadarItem] = {}
    for category in config.get("rss_categories", ["cs.AI", "cs.CL", "cs.CV"]):
        root = ET.fromstring(get_text(f"https://rss.arxiv.org/rss/{category}"))
        for entry in root.findall("./channel/item"):
            title = " ".join((entry.findtext("title") or "").split())
            description = " ".join((entry.findtext("description") or "").split())
            if keywords and not any(
                keyword in f"{title} {description}".casefold() for keyword in keywords
            ):
                continue
            published_text = entry.findtext("pubDate")
            if not published_text:
                continue
            published = parsedate_to_datetime(published_text).astimezone(UTC)
            if published < overlap_since:
                continue
            url = (entry.findtext("link") or "").replace("http:", "https:")
            guid = entry.findtext("guid") or url
            source_id = _arxiv_source_id(guid)
            if not source_id or not url:
                continue
            announce_type = (
                entry.findtext("arxiv:announce_type", namespaces=namespaces) or ""
            ).casefold()
            summary = (
                description.split("Abstract:", 1)[-1].strip()
                if "Abstract:" in description
                else description
            )
            creators = entry.findtext("dc:creator", namespaces=namespaces) or ""
            found[source_id] = RadarItem(
                source="arXiv",
                source_id=source_id,
                title=title,
                url=url,
                published_at=published,
                updated_at=published,
                summary=summary,
                event_kind="updated" if announce_type == "replace" else "released",
                authors=[author.strip() for author in creators.split(",") if author.strip()],
            )
    return sorted(
        found.values(),
        key=lambda item: (item.updated_at or item.published_at, item.source_id),
        reverse=True,
    )[:limit]


def fetch_arxiv(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    found: dict[str, RadarItem] = {}
    # arXiv's Atom `published` timestamp is the v1 submission time, not the
    # announcement time. A strict 48-hour cutoff misses papers submitted before
    # a weekend and announced afterward, so fetch an explicit overlap and use
    # durable discovery state in the pipeline to suppress repeats.
    overlap_since = since - timedelta(hours=int(config.get("overlap_hours", 120)))
    queries = config.get("queries", [])
    request_delay = float(config.get("request_delay_seconds", 3))
    atom_error: Exception | None = None
    if config.get("atom_enabled", True):
        try:
            for query_index, query in enumerate(queries):
                if query_index and request_delay > 0:
                    time.sleep(request_delay)
                xml = get_text(
                    "https://export.arxiv.org/api/query",
                    params={
                        "search_query": query,
                        "start": 0,
                        "max_results": limit,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                    },
                )
                root = ET.fromstring(xml)
                for entry in root.findall("atom:entry", namespace):
                    published = _date(entry.findtext("atom:published", namespaces=namespace))
                    updated = _date(entry.findtext("atom:updated", namespaces=namespace))
                    if max(published, updated) < overlap_since:
                        continue
                    url = (entry.findtext("atom:id", namespaces=namespace) or "").replace(
                        "http:", "https:"
                    )
                    source_id = _arxiv_source_id(url)
                    title = " ".join(
                        (entry.findtext("atom:title", namespaces=namespace) or "").split()
                    )
                    summary = " ".join(
                        (entry.findtext("atom:summary", namespaces=namespace) or "").split()
                    )
                    authors = [
                        name.text or ""
                        for name in entry.findall("atom:author/atom:name", namespace)
                        if name.text
                    ]
                    found[source_id] = RadarItem(
                        source="arXiv",
                        source_id=source_id,
                        title=title,
                        url=url,
                        published_at=published,
                        updated_at=updated,
                        summary=summary,
                        event_kind="updated" if updated > published else "released",
                        authors=authors,
                    )
        except Exception as error:
            atom_error = error

    if atom_error or not found:
        rss_items = _fetch_arxiv_rss(
            config,
            overlap_since=overlap_since,
            limit=limit,
        )
        if rss_items:
            return rss_items
        if atom_error:
            raise atom_error
    return sorted(
        found.values(),
        key=lambda item: (item.updated_at or item.published_at, item.source_id),
        reverse=True,
    )[:limit]


def fetch_huggingface(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    found: dict[str, RadarItem] = {}
    for kind in config.get("kinds", ["datasets"]):
        for search in config.get("searches", []):
            rows = get_json(
                f"https://huggingface.co/api/{kind}",
                params={
                    "search": search,
                    "sort": "lastModified",
                    "direction": -1,
                    "limit": limit,
                    "full": "true",
                },
            )
            for row in rows:
                changed = _date(row.get("lastModified") or row.get("createdAt"))
                if changed < since:
                    continue
                item_id = row.get("id") or row.get("modelId")
                if not item_id:
                    continue
                found[item_id] = RadarItem(
                    source="Hugging Face",
                    source_id=item_id,
                    title=item_id,
                    url=f"https://huggingface.co/{kind}/{item_id}",
                    published_at=changed,
                    # Never synthesize prose here: `score_item` reads `summary`,
                    # so a template would let the pipeline score itself on its
                    # own words. "" means the repo shipped no card.
                    summary=huggingface_summary(row, item_id),
                    event_kind=("released" if _date(row.get("createdAt")) >= since else "updated"),
                    metrics={
                        "downloads": float(row.get("downloads") or 0),
                        "likes": float(row.get("likes") or 0),
                    },
                    raw=row,
                )
    return list(found.values())


def fetch_github(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    found: dict[str, RadarItem] = {}
    date_filter = since.date().isoformat()
    for query in config.get("queries", []):
        payload = get_json(
            "https://api.github.com/search/repositories",
            params={
                "q": f"{query} pushed:>={date_filter}",
                "sort": "updated",
                "order": "desc",
                "per_page": min(limit, 100),
            },
            headers=headers,
        )
        for row in payload.get("items", []):
            changed = _date(row.get("pushed_at") or row.get("updated_at"))
            if changed < since:
                continue
            full_name = row["full_name"]
            found[full_name] = RadarItem(
                source="GitHub",
                source_id=full_name,
                title=full_name,
                url=row["html_url"],
                published_at=changed,
                summary=github_summary(row),
                event_kind=("released" if _date(row.get("created_at")) >= since else "updated"),
                metrics={
                    "stars": float(row.get("stargazers_count") or 0),
                    "forks": float(row.get("forks_count") or 0),
                },
                raw=row,
            )
    return list(found.values())


def fetch_openalex(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    api_key = os.getenv("OPENALEX_API_KEY")
    if not api_key:
        raise RuntimeError("OPENALEX_API_KEY is not configured")
    found: dict[str, RadarItem] = {}
    for search in config.get("searches", []):
        payload = get_json(
            "https://api.openalex.org/works",
            params={
                "api_key": api_key,
                "search": search,
                "filter": f"from_publication_date:{since.date().isoformat()}",
                "sort": "publication_date:desc",
                "per_page": min(limit, 100),
                "select": "id,doi,display_name,publication_date,authorships,"
                "cited_by_count,primary_location,type",
            },
        )
        for row in payload.get("results", []):
            source_id = row["id"].rsplit("/", 1)[-1]
            authors = [
                authorship.get("author", {}).get("display_name", "")
                for authorship in row.get("authorships", [])
            ]
            primary = row.get("primary_location") or {}
            url = row.get("doi") or primary.get("landing_page_url") or row["id"]
            found[source_id] = RadarItem(
                source="OpenAlex",
                source_id=source_id,
                title=row["display_name"],
                url=url,
                published_at=_date(row.get("publication_date")),
                event_kind="released",
                authors=[author for author in authors if author],
                metrics={"citations": float(row.get("cited_by_count") or 0)},
                raw=row,
            )
    return list(found.values())


def fetch_brave(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not configured")
    found: dict[str, RadarItem] = {}
    for query in config.get("searches", []):
        payload = get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                "freshness": f"{since.date().isoformat()}to{datetime.now(UTC).date().isoformat()}",
                "count": min(limit, 20),
                "extra_snippets": "true",
            },
            headers={"X-Subscription-Token": api_key},
        )
        for row in payload.get("web", {}).get("results", []):
            url = row.get("url")
            if not url:
                continue
            source_id = re.sub(r"\W+", "-", url).strip("-")[-120:]
            found[url] = RadarItem(
                source="Brave Web",
                source_id=source_id,
                title=row.get("title") or url,
                url=url,
                published_at=_date(row.get("page_age")),
                summary=" ".join([row.get("description") or "", *row.get("extra_snippets", [])]),
                event_kind="discovered",
                raw=row,
            )
    return list(found.values())


SOURCE_FETCHERS = {
    "arxiv": fetch_arxiv,
    "huggingface": fetch_huggingface,
    "github": fetch_github,
    "openalex": fetch_openalex,
    "brave": fetch_brave,
}


def default_since(hours: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)
