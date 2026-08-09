from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from .describe import clean_card_text, github_summary, huggingface_summary
from .http import get_json, get_text
from .models import RadarItem


class ConnectorPayloadError(ValueError):
    """Raised when a source returns a successful but incompatible payload."""


FUTURE_TIMESTAMP_TOLERANCE = timedelta(minutes=5)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _feed_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if _xml_local_name(child.tag) == name), None)


def _feed_text(element: ET.Element, *names: str) -> str:
    for name in names:
        child = _feed_child(element, name)
        if child is not None:
            text = " ".join("".join(child.itertext()).split())
            if text:
                return text
    return ""


def _feed_date(value: str) -> datetime | None:
    if not value:
        return None
    parsed = _optional_date(value)
    if parsed is not None:
        return parsed
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _feed_link(entry: ET.Element) -> str:
    # RSS puts the URL in the node text; Atom uses an href attribute and may
    # include alternate, self, and enclosure links.
    for child in entry:
        if _xml_local_name(child.tag) != "link":
            continue
        href = str(child.get("href") or child.text or "").strip()
        if href and child.get("rel", "alternate") == "alternate":
            return href
    return ""


def fetch_first_party_feeds(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    """Collect relevant announcements from an explicit first-party RSS/Atom allowlist."""
    keywords = [
        str(value).casefold()
        for value in config.get(
            "keywords",
            [
                "benchmark",
                "evaluation",
                "evals",
                "leaderboard",
                "dataset",
                "test set",
                "data contamination",
            ],
        )
        if str(value).strip()
    ]
    feeds = config.get("feeds") or []
    if not isinstance(feeds, list):
        raise ConnectorPayloadError("First-party feeds must be an array")
    found: dict[str, RadarItem] = {}
    for feed in feeds:
        if not isinstance(feed, dict) or not feed.get("name") or not feed.get("url"):
            raise ConnectorPayloadError("First-party feed is missing name or url")
        name = str(feed["name"]).strip()
        feed_url = str(feed["url"]).strip()
        root = ET.fromstring(get_text(feed_url, **_request_options(config)))
        root_name = _xml_local_name(root.tag)
        if root_name == "rss":
            channel = _feed_child(root, "channel")
            entries = (
                []
                if channel is None
                else [child for child in channel if _xml_local_name(child.tag) == "item"]
            )
        elif root_name == "feed":
            entries = [child for child in root if _xml_local_name(child.tag) == "entry"]
        else:
            raise ConnectorPayloadError(f"{name} returned an incompatible feed document")
        for entry in entries:
            title = _feed_text(entry, "title")
            summary = clean_card_text(_feed_text(entry, "description", "summary", "content"))
            haystack = f"{title} {summary}".casefold()
            if not title or (keywords and not any(keyword in haystack for keyword in keywords)):
                continue
            url = _feed_link(entry)
            source_id = _feed_text(entry, "id", "guid") or url
            published = _feed_date(_feed_text(entry, "published", "pubDate", "date"))
            updated = _feed_date(_feed_text(entry, "updated")) or published
            activity = updated or published
            if not url or not source_id or published is None or activity is None:
                raise ConnectorPayloadError(f"{name} feed item is missing required fields")
            identity = f"{name}:{source_id}"
            if activity < since or _reject_future(config, identity, published, updated):
                continue
            found[identity] = RadarItem(
                source="First-party feed",
                source_id=identity,
                title=title,
                url=url,
                published_at=published,
                updated_at=updated,
                summary=summary,
                event_kind="updated" if updated > published else "released",
                raw={"xml": ET.tostring(entry, encoding="unicode")},
                parser_version="first-party-rss-atom/1",
            )
    return sorted(
        found.values(),
        key=lambda item: (item.updated_at or item.published_at, item.source_id),
        reverse=True,
    )[:limit]


def _latest_allowed(config: dict[str, Any]) -> datetime:
    collection_now = config.get("_collection_now")
    if not isinstance(collection_now, datetime):
        collection_now = datetime.now(UTC)
    return collection_now.astimezone(UTC) + FUTURE_TIMESTAMP_TOLERANCE


def _reject_future(
    config: dict[str, Any],
    identity: str,
    *timestamps: datetime | None,
) -> bool:
    if not any(value is not None and value > _latest_allowed(config) for value in timestamps):
        return False
    identities = config.setdefault("_future_rejection_ids", set())
    identities.add(identity)
    config["_future_rejections"] = len(identities)
    return True


def _payload_dict(payload: Any, source: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConnectorPayloadError(f"{source} returned a non-object payload")
    return payload


def _payload_rows(payload: Any, key: str, source: str) -> list[dict[str, Any]]:
    parsed = _payload_dict(payload, source)
    if key not in parsed:
        raise ConnectorPayloadError(f"{source} response is missing {key}")
    value = parsed[key]
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ConnectorPayloadError(f"{source} returned invalid {key}")
    return value


def _request_options(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempts": int(config.get("attempts", 3)),
        "timeout": float(config.get("timeout_seconds", 30)),
    }


def _openreview_value(content: dict[str, Any], key: str, default: Any = None) -> Any:
    value = content.get(key, default)
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _milliseconds(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _optional_date(value: str | None) -> datetime | None:
    """Parse a timestamp, or report its absence rather than inventing one."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _date(value: str | None) -> datetime:
    """Parse a timestamp, substituting the current time when it is missing.

    Callers that feed a recency score must use :func:`_optional_date` instead: a
    missing timestamp resolved to "now" is indistinguishable from a genuinely
    fresh record, so the substitution silently awards maximum recency to a
    record whose age is unknown.
    """
    parsed = _optional_date(value)
    return datetime.now(UTC) if parsed is None else parsed


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
        channel = root.find("channel") if root.tag == "rss" else None
        if channel is None:
            raise ConnectorPayloadError("arXiv RSS returned an incompatible document")
        for entry in channel.findall("item"):
            title = " ".join((entry.findtext("title") or "").split())
            description = " ".join((entry.findtext("description") or "").split())
            published_text = entry.findtext("pubDate")
            url = (entry.findtext("link") or "").replace("http:", "https:")
            guid = entry.findtext("guid") or url
            source_id = _arxiv_source_id(guid)
            if not title or not description or not published_text or not url or not source_id:
                raise ConnectorPayloadError("arXiv RSS item is missing required fields")
            if keywords and not any(
                keyword in f"{title} {description}".casefold() for keyword in keywords
            ):
                continue
            published = parsedate_to_datetime(published_text).astimezone(UTC)
            if published < overlap_since or _reject_future(config, source_id, published):
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
                raw={"xml": ET.tostring(entry, encoding="unicode")},
                parser_version="arxiv-rss/1",
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
                        "search_query": (
                            f"({query}) AND lastUpdatedDate:"
                            f"[{overlap_since:%Y%m%d%H%M} TO "
                            f"{_latest_allowed(config):%Y%m%d%H%M}]"
                        ),
                        "start": 0,
                        "max_results": limit,
                        "sortBy": "lastUpdatedDate",
                        "sortOrder": "descending",
                    },
                )
                root = ET.fromstring(xml)
                for entry in root.findall("atom:entry", namespace):
                    url = (entry.findtext("atom:id", namespaces=namespace) or "").replace(
                        "http:", "https:"
                    )
                    source_id = _arxiv_source_id(url)
                    published = _date(entry.findtext("atom:published", namespaces=namespace))
                    updated = _date(entry.findtext("atom:updated", namespaces=namespace))
                    if max(published, updated) < overlap_since or _reject_future(
                        config, source_id, published, updated
                    ):
                        continue
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
                        raw={"xml": ET.tostring(entry, encoding="unicode")},
                        parser_version="arxiv-atom/1",
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
                    # The Hub API has no upper-date filter. Fetch extra rows so
                    # malformed future timestamps cannot consume the local cap
                    # before they are rejected below.
                    "limit": min(1000, max(limit * 2, limit + 50)),
                    "full": "true",
                },
            )
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ConnectorPayloadError("Hugging Face Hub returned a non-array payload")
            for row in rows:
                item_id = row.get("id") or row.get("modelId")
                if not item_id:
                    continue
                # An undated repo is skipped rather than dated "now": the
                # substitution both invented freshness and slipped past the
                # `since` check below, which is what it was meant to enforce.
                changed = _optional_date(row.get("lastModified") or row.get("createdAt"))
                if (
                    changed is None
                    or changed < since
                    or _reject_future(config, str(item_id), changed)
                ):
                    continue
                created = _optional_date(row.get("createdAt"))
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
                    event_kind=(
                        "released" if created is not None and created >= since else "updated"
                    ),
                    metrics={
                        "downloads": float(row.get("downloads") or 0),
                        "likes": float(row.get("likes") or 0),
                    },
                    raw=row,
                    parser_version="huggingface-hub/1",
                )
    # `limit` is applied per request, and this fetcher issues one per kind per
    # search, so the union could reach kinds x searches x limit. Trimming to the
    # most recently changed keeps the source's reported count comparable with
    # every other connector's.
    return sorted(found.values(), key=lambda item: item.published_at, reverse=True)[:limit]


def fetch_github(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    found: dict[str, RadarItem] = {}
    date_filter = since.date().isoformat()
    # The search API returns at most 100 rows per request, so a bare
    # `per_page=limit` silently truncates any query that matches more. Page
    # until the query is exhausted or the per-source limit is reached.
    page_size = 100
    max_pages = max(1, -(-limit // page_size))
    # Search is rate-limited to 10 requests/minute unauthenticated and 30
    # authenticated. Paging every query to exhaustion can exceed that and
    # trip a 403, which fails a required source and aborts the whole run, so
    # bound the total requests and space them out when running tokenless.
    queries = list(config.get("queries", []))
    budget = int(config.get("max_requests", 30 if token else 8))
    delay = float(config.get("request_delay_seconds", 0 if token else 6.5))
    requests_made = 0
    # Page round-robin rather than query-by-query. Draining the first query to
    # the source limit would spend the whole budget on it and never issue the
    # evaluation, dataset and contamination searches at all, quietly dropping
    # entire topics from the scan.
    exhausted: set[int] = set()
    for page in range(1, max_pages + 1):
        if len(exhausted) == len(queries):
            break
        for index, query in enumerate(queries):
            if index in exhausted or requests_made >= budget:
                continue
            if requests_made and delay > 0:
                time.sleep(delay)
            requests_made += 1
            payload = get_json(
                "https://api.github.com/search/repositories",
                params={
                    "q": (
                        f"{query} pushed:{date_filter}.."
                        f"{_latest_allowed(config).date().isoformat()}"
                    ),
                    "sort": "updated",
                    "order": "desc",
                    "per_page": min(limit, page_size),
                    "page": page,
                },
                headers=headers,
            )
            rows = _payload_rows(payload, "items", "GitHub Search")
            for row in rows:
                full_name = row["full_name"]
                changed = _date(row.get("pushed_at") or row.get("updated_at"))
                if changed < since or _reject_future(config, full_name, changed):
                    continue
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
                    parser_version="github-search/1",
                )
            if len(rows) < min(limit, page_size):
                exhausted.add(index)
        if requests_made >= budget:
            break
    # Round-robin can overshoot the per-source cap on its final sweep, since
    # every query contributes before the total is known. Trim to the most
    # recently active repositories so `max_items_per_source` stays honest.
    return sorted(found.values(), key=lambda item: item.published_at, reverse=True)[:limit]


def fetch_openreview(
    config: dict[str, Any],
    since: datetime,
    limit: int,
) -> list[RadarItem]:
    """Fetch recent public conference/workshop submissions from API v2."""
    found: dict[str, RadarItem] = {}
    venues = [str(value) for value in config.get("venues", []) if str(value).strip()]
    page_size = min(1000, max(1, int(config.get("page_size", 250))))
    budget = max(1, int(config.get("max_requests", len(venues) or 1)))
    requests_made = 0
    for venue in venues:
        offset = 0
        while requests_made < budget and len(found) < limit:
            payload = get_json(
                "https://api2.openreview.net/notes",
                params={
                    "venueid": venue,
                    "limit": min(page_size, limit - len(found)),
                    "offset": offset,
                    "sort": "mdate:desc",
                },
                **_request_options(config),
            )
            requests_made += 1
            rows = _payload_rows(payload, "notes", "OpenReview")
            if not rows:
                break
            oldest: datetime | None = None
            for row in rows:
                content = row.get("content")
                if not isinstance(content, dict):
                    raise ConnectorPayloadError("OpenReview note content must be an object")
                note_id = str(row.get("forum") or row.get("id") or "").strip()
                title = str(_openreview_value(content, "title", "") or "").strip()
                created = _milliseconds(row.get("cdate") or row.get("pdate"))
                modified = _milliseconds(row.get("mdate")) or created
                activity = modified or created
                if not note_id or not title or not created or not activity:
                    continue
                oldest = min(oldest or activity, activity)
                if activity < since or _reject_future(config, note_id, activity):
                    continue
                abstract = str(_openreview_value(content, "abstract", "") or "").strip()
                authors = _openreview_value(content, "authors", []) or []
                if isinstance(authors, str):
                    authors = [authors]
                if not isinstance(authors, list):
                    raise ConnectorPayloadError("OpenReview authors must be an array")
                artifact_urls = []
                for key in ("code", "dataset", "project", "supplementary_material"):
                    value = _openreview_value(content, key)
                    values = value if isinstance(value, list) else [value]
                    artifact_urls.extend(
                        str(url)
                        for url in values
                        if isinstance(url, str) and url.startswith(("https://", "http://"))
                    )
                found[note_id] = RadarItem(
                    source="OpenReview",
                    source_id=note_id,
                    title=title,
                    url=f"https://openreview.net/forum?id={note_id}",
                    published_at=created,
                    updated_at=modified,
                    summary=abstract,
                    event_kind="updated" if modified and modified > created else "released",
                    authors=[str(author) for author in authors if str(author).strip()],
                    artifact_urls=sorted(set(artifact_urls)),
                    raw=row,
                    parser_version="openreview-api-v2/1",
                )
            offset += len(rows)
            if len(rows) < min(page_size, limit - len(found)) or (
                oldest is not None and oldest < since
            ):
                break
        if requests_made >= budget or len(found) >= limit:
            break
    return sorted(
        found.values(),
        key=lambda item: (item.updated_at or item.published_at, item.source_id),
        reverse=True,
    )[:limit]


def fetch_semantic_scholar(
    config: dict[str, Any],
    since: datetime,
    limit: int,
) -> list[RadarItem]:
    """Fetch structured scholarly records with exact external identifiers."""
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    headers = {"x-api-key": api_key} if api_key else {}
    found: dict[str, RadarItem] = {}
    searches = [str(value) for value in config.get("searches", []) if str(value).strip()]
    budget = max(1, int(config.get("max_requests", len(searches) or 1)))
    page_size = min(100, max(1, int(config.get("page_size", 100))))
    # An individual Semantic Scholar key starts at one request per second.
    # Pace proactively instead of making every request after the first rely on
    # a 429 and retry. Anonymous callers remain on the shared pool and retain
    # the old no-delay default unless the configuration says otherwise.
    request_delay = max(
        0.0,
        float(config.get("request_delay_seconds", 1.1 if api_key else 0.0)),
    )
    requests_made = 0
    for search in searches:
        offset = 0
        while requests_made < budget and len(found) < limit:
            if requests_made and request_delay:
                time.sleep(request_delay)
            payload = get_json(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": search,
                    "publicationDateOrYear": (
                        f"{since.date().isoformat()}:{_latest_allowed(config).date().isoformat()}"
                    ),
                    "offset": offset,
                    "limit": min(page_size, limit - len(found)),
                    "fields": (
                        "paperId,externalIds,url,title,abstract,publicationDate,"
                        "authors,citationCount,influentialCitationCount,openAccessPdf"
                    ),
                },
                headers=headers,
                **_request_options(config),
            )
            requests_made += 1
            rows = _payload_rows(payload, "data", "Semantic Scholar")
            if not rows:
                break
            for row in rows:
                paper_id = str(row.get("paperId") or "").strip()
                title = str(row.get("title") or "").strip()
                published_text = row.get("publicationDate")
                if not paper_id or not title or not published_text:
                    continue
                published = _date(str(published_text))
                if published < since or _reject_future(config, paper_id, published):
                    continue
                external = row.get("externalIds") or {}
                if not isinstance(external, dict):
                    raise ConnectorPayloadError("Semantic Scholar externalIds must be an object")
                artifact_urls = []
                if external.get("DOI"):
                    artifact_urls.append(f"https://doi.org/{external['DOI']}")
                if external.get("ArXiv"):
                    artifact_urls.append(f"https://arxiv.org/abs/{external['ArXiv']}")
                open_access = row.get("openAccessPdf") or {}
                if not isinstance(open_access, dict):
                    raise ConnectorPayloadError("Semantic Scholar openAccessPdf must be an object")
                if str(open_access.get("url") or "").startswith(("https://", "http://")):
                    artifact_urls.append(str(open_access["url"]))
                authors = row.get("authors") or []
                if not isinstance(authors, list):
                    raise ConnectorPayloadError("Semantic Scholar authors must be an array")
                found[paper_id] = RadarItem(
                    source="Semantic Scholar",
                    source_id=paper_id,
                    title=title,
                    url=str(row.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"),
                    published_at=published,
                    updated_at=published,
                    summary=str(row.get("abstract") or "").strip(),
                    event_kind="released",
                    authors=[
                        str(author.get("name"))
                        for author in authors
                        if isinstance(author, dict) and author.get("name")
                    ],
                    artifact_urls=sorted(set(artifact_urls)),
                    metrics={
                        "citations": float(row.get("citationCount") or 0),
                        "influential_citations": float(row.get("influentialCitationCount") or 0),
                    },
                    raw=row,
                    parser_version="semantic-scholar-graph/1",
                )
            next_offset = _payload_dict(payload, "Semantic Scholar").get("next")
            if next_offset is None or len(rows) < min(page_size, limit - len(found)):
                break
            try:
                offset = int(next_offset)
            except (TypeError, ValueError) as error:
                raise ConnectorPayloadError(
                    "Semantic Scholar returned an invalid next offset"
                ) from error
        if requests_made >= budget or len(found) >= limit:
            break
    return sorted(found.values(), key=lambda item: item.published_at, reverse=True)[:limit]


def fetch_github_releases(
    config: dict[str, Any],
    since: datetime,
    limit: int,
) -> list[RadarItem]:
    """Fetch published releases from a bounded first-party repository allowlist."""
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    }
    repositories = [
        str(value).strip()
        for value in config.get("repositories", [])
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(value).strip())
    ]
    page_size = min(100, max(1, int(config.get("page_size", 30))))
    max_pages = max(1, int(config.get("max_pages_per_repository", 2)))
    budget = max(1, int(config.get("max_requests", len(repositories) or 1)))
    replacement_budget = max(0, int(config.get("future_replacement_requests", 2)))
    regular_requests = 0
    replacement_requests = 0
    found: dict[str, RadarItem] = {}
    failures: list[Exception] = []
    for repository in repositories:
        page = 1
        page_limit = max_pages
        while page <= page_limit:
            is_replacement = page > max_pages
            if (
                (is_replacement and replacement_requests >= replacement_budget)
                or (not is_replacement and regular_requests >= budget)
                or len(found) >= limit
            ):
                break
            try:
                payload = get_json(
                    f"https://api.github.com/repos/{repository}/releases",
                    params={"per_page": min(page_size, limit - len(found)), "page": page},
                    headers=headers,
                    **_request_options(config),
                )
            except Exception as error:
                # Degrade per repository: one renamed, archived, or temporarily
                # unavailable project must not erase every healthy release.
                warnings = config.setdefault("_source_warnings", [])
                warnings.append(f"{repository}: {type(error).__name__}: {error}")
                failures.append(error)
                break
            if is_replacement:
                replacement_requests += 1
            else:
                regular_requests += 1
            if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
                raise ConnectorPayloadError("GitHub Releases returned a non-array payload")
            if not payload:
                break
            oldest: datetime | None = None
            rejected_on_page = 0
            for row in payload:
                if row.get("draft"):
                    continue
                published_text = row.get("published_at") or row.get("created_at")
                if not published_text:
                    continue
                published = _date(str(published_text))
                oldest = min(oldest or published, published)
                if published < since:
                    continue
                tag = str(row.get("tag_name") or "").strip()
                url = str(row.get("html_url") or "").strip()
                if not tag or not url:
                    continue
                if _reject_future(config, f"{repository}@{tag}", published):
                    rejected_on_page += 1
                    continue
                author = row.get("author") or {}
                assets = row.get("assets") or []
                if not isinstance(assets, list) or not all(
                    isinstance(asset, dict) for asset in assets
                ):
                    raise ConnectorPayloadError("GitHub release assets must be an array")
                found[f"{repository}@{tag}"] = RadarItem(
                    source="GitHub Release",
                    source_id=f"{repository}@{tag}",
                    title=str(row.get("name") or f"{repository} {tag}").strip(),
                    url=url,
                    published_at=published,
                    updated_at=published,
                    summary=clean_card_text(row.get("body")),
                    event_kind="prereleased" if row.get("prerelease") else "released",
                    authors=(
                        [str(author["login"])]
                        if isinstance(author, dict) and author.get("login")
                        else []
                    ),
                    artifact_urls=[f"https://github.com/{repository}"],
                    metrics={
                        "downloads": float(
                            sum(
                                int(asset.get("download_count") or 0)
                                for asset in assets
                                if isinstance(asset, dict)
                            )
                        )
                    },
                    raw=row,
                    parser_version="github-releases/1",
                )
            if len(payload) < min(page_size, limit - len(found)) or (
                oldest is not None and oldest < since
            ):
                break
            if rejected_on_page:
                page_limit += 1
            page += 1
        if regular_requests >= budget or len(found) >= limit:
            break
    warnings = config.get("_source_warnings") or []
    if repositories and len(warnings) == len(repositories):
        raise failures[0]
    return sorted(found.values(), key=lambda item: item.published_at, reverse=True)[:limit]


def fetch_openalex(
    config: dict[str, Any],
    since: datetime,
    limit: int,
    *,
    now: datetime | None = None,
) -> list[RadarItem]:
    # OpenAlex replaced its mailto-based polite pool with free API keys in
    # February 2026. Anonymous calls still have a small compatibility budget,
    # but they are not the documented production path.
    api_key = os.getenv("OPENALEX_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENALEX_API_KEY is not configured")
    now = now or _latest_allowed(config) - FUTURE_TIMESTAMP_TOLERANCE
    config.setdefault("_collection_now", now)
    found: dict[str, RadarItem] = {}
    for search in config.get("searches", []):
        payload = get_json(
            "https://api.openalex.org/works",
            params={
                "api_key": api_key,
                "search": search,
                # The lower bound alone lets erroneous future records sort to
                # the front and crowd real current work out of the first page.
                "filter": (
                    f"from_publication_date:{since.date().isoformat()},"
                    f"to_publication_date:{now.date().isoformat()}"
                ),
                "sort": "publication_date:desc",
                "per_page": min(limit, 100),
                "select": "id,doi,display_name,publication_date,authorships,"
                "cited_by_count,primary_location,type",
            },
        )
        # `payload.get("results", [])` treated a `{}` response as a successful
        # empty fetch, so a malformed reply was indistinguishable from a day
        # with no matching works.
        for row in _payload_rows(payload, "results", "OpenAlex"):
            source_id = row["id"].rsplit("/", 1)[-1]
            authors = [
                authorship.get("author", {}).get("display_name", "")
                for authorship in row.get("authorships", [])
            ]
            primary = row.get("primary_location") or {}
            url = row.get("doi") or primary.get("landing_page_url") or row["id"]
            # OpenAlex publishes a date, not a timestamp, so an exact cutoff
            # against `since` would drop every paper dated the since-day. The
            # comparison stays date-granular to match the field's real
            # resolution; an undated row is skipped rather than dated "now",
            # which would have handed it maximum recency.
            published = _optional_date(row.get("publication_date"))
            # OpenAlex serves `display_name: null` for works whose metadata is
            # incomplete or withdrawn. Every other connector coerces its title,
            # so this was the one path that could hand a None title to the
            # shared scorer, where normalized_title() crashed the whole daily
            # run on it. An untitled work cannot be deduplicated by title or
            # given a heading a reader could act on, and unlike Brave or GitHub
            # Release there is no second human-meaningful field to fall back to,
            # so it is dropped the same way an undated work is.
            title = str(row.get("display_name") or "").strip()
            # Keep a defensive client-side bound as well as the API filter: a
            # malformed or ignored upstream filter must not grant future work
            # maximum recency in the shared scorer.
            if (
                not title
                or published is None
                or published.date() < since.date()
                or _reject_future(config, source_id, published)
            ):
                continue
            found[source_id] = RadarItem(
                source="OpenAlex",
                source_id=source_id,
                title=title,
                url=url,
                published_at=published,
                event_kind="released",
                authors=[author for author in authors if author],
                metrics={"citations": float(row.get("cited_by_count") or 0)},
                raw=row,
                parser_version="openalex-works/1",
            )
    return list(found.values())


# Brave's freshness range is date-granular and inclusive. `since` plus the
# longest lookback the radar runs with, rounded up, keeps today inside the range
# without reading the clock.
_BRAVE_RANGE_DAYS = 7


def fetch_brave(config: dict[str, Any], since: datetime, limit: int) -> list[RadarItem]:
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not configured")
    found: dict[str, RadarItem] = {}
    freshness_end = min(
        since + timedelta(days=_BRAVE_RANGE_DAYS),
        _latest_allowed(config),
    ).date()
    for query in config.get("searches", []):
        payload = get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                # Anchored to `since` rather than wall-clock now, so replaying a
                # run reconstructs the same query. The end is padded past the
                # lookback so the present day stays inside the range: reading
                # the clock here made the request depend on when it was issued.
                "freshness": (f"{since.date().isoformat()}to{freshness_end.isoformat()}"),
                "count": min(limit, 20),
                "extra_snippets": "true",
            },
            headers={"X-Subscription-Token": api_key},
        )
        # Same reasoning as OpenAlex: a `{}` reply must not read as a genuine
        # zero-result day. Brave nests its rows under `web`, so the wrapper is
        # validated before the rows are.
        web = _payload_dict(payload, "Brave Web").get("web")
        if not isinstance(web, dict):
            raise ConnectorPayloadError("Brave Web response is missing web")
        for row in _payload_rows(web, "results", "Brave Web"):
            url = row.get("url")
            if not url:
                continue
            source_id = re.sub(r"\W+", "-", url).strip("-")[-120:]
            # Brave omits page_age for many results. Dating those "now" claimed
            # a freshness the response never asserted and awarded them full
            # recency, so an undated result is skipped instead.
            published = _optional_date(row.get("page_age"))
            if published is None or _reject_future(config, url, published):
                continue
            found[url] = RadarItem(
                source="Brave Web",
                source_id=source_id,
                title=row.get("title") or url,
                url=url,
                published_at=published,
                summary=" ".join([row.get("description") or "", *row.get("extra_snippets", [])]),
                event_kind="discovered",
                raw=row,
                parser_version="brave-web-search/1",
            )
    return list(found.values())


SOURCE_FETCHERS = {
    "arxiv": fetch_arxiv,
    "huggingface": fetch_huggingface,
    "github": fetch_github,
    "openreview": fetch_openreview,
    "semantic_scholar": fetch_semantic_scholar,
    "github_releases": fetch_github_releases,
    "first_party_feeds": fetch_first_party_feeds,
    "openalex": fetch_openalex,
    "brave": fetch_brave,
}


def default_since(hours: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)
