"""Choose the day's benchmarks to share and name who made them (issue #671).

The daily run writes a ``share`` block into the day's snapshot; the images in
ktwu01/benchmark-radar-cards are rendered from that block alone. Choosing and
looking up happen once, here, so the same snapshot always renders the same
images.

Which benchmarks: the LLM daily briefing already picks the day's benchmarks and
says in its first sentence what each one tests. Its bullets, in its order, are
the cards; the first three are the top-3 image. A day without a model-written
briefing falls back to the radar's own score, with the filters that keep that
list from repeating itself: a version release of a tool is not a new
benchmark, a paper the radar showed on an earlier day is not news, and three
rows from one uploader read as one row.

Who made them: the item's own authors and institutions when its source names
them (papers, DataCite, Crossref). GitHub and Hugging Face items only carry the
owner handle, so the handle is resolved to the name and affiliation its public
profile states. arXiv items carry authors but no institutions: OpenAlex has
them once it indexes the paper, which can take days, and until then the
paper's own arXiv HTML has them when its LaTeX template marks affiliations. An
affiliation neither states is left off rather than guessed.
"""

from __future__ import annotations

import html
import http.client
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cards import CARDS_SITE_URL
from .corpus import organizations_for_item
from .http import RequestError, get_json, get_text
from .snapshots import _write_json, load_snapshots, validate_snapshot

# A lookup that fails in any of these ways costs the card one fact. An
# IncompleteRead or a reset connection escapes http.py as itself, not as
# RequestError, and a failed lookup must never cost the day its snapshot.
_LOOKUP_ERRORS = (RequestError, OSError, http.client.HTTPException)

DEFAULT_LIMIT = 3
SHARE_SCHEMA_VERSION = 1

# Version tags of tracked tools (mteb 2.26.15, garak v0.17.1) arrive as
# event_kind "released" too, and the release cadence of a busy repository would
# put the same project on the image every day.
_EXCLUDED_SOURCES = frozenset({"GitHub Release"})

# Sources whose `organizations` field holds the owner handle, not an
# institution the item reported.
_HANDLE_SOURCES = frozenset({"Hugging Face", "GitHub", "GitHub Organization", "Kaggle Dataset"})

_ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})")
_AFFILIATION_SPAN = re.compile(r'<span class="ltx_contact ltx_role_affiliation">')
_SPAN_TAG = re.compile(r"<(/?)span\b[^>]*>")

Fetch = Callable[..., Any]

# One rate-limited API answering Retry-After: 60 to each retry would hold the
# daily run for many minutes over facts a card can omit, so all of a day's
# lookups share one deadline and never retry.
LOOKUP_BUDGET_SECONDS = 90.0
_LOOKUP_TIMEOUT_SECONDS = 10.0


def budgeted_fetchers(seconds: float = LOOKUP_BUDGET_SECONDS) -> tuple[Fetch, Fetch]:
    """Return JSON and text fetchers that fail fast once ``seconds`` have passed."""
    deadline = time.monotonic() + seconds

    def guard(get: Fetch) -> Fetch:
        def call(url: str, **kwargs: Any) -> Any:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestError("creator lookup budget spent")
            timeout = min(_LOOKUP_TIMEOUT_SECONDS, remaining)
            return get(url, timeout=timeout, attempts=1, **kwargs)

        return call

    return guard(get_json), guard(get_text)


def _identities(item: dict[str, Any]) -> set[str]:
    # Exact identity only: the same link, or the same title up to case and
    # spacing. A similar title is a different benchmark until reviewed.
    keys = {f"url:{item.get('url')}"} if item.get("url") else set()
    title = " ".join(str(item.get("title") or "").casefold().split())
    if title:
        keys.add(f"title:{title}")
    return keys


def _owner_key(item: dict[str, Any]) -> str:
    # Raw snapshots keep a Hugging Face or GitHub owner only in source_id
    # ("utahnlp/knows-benchmark"); the dashboard derives it the same way.
    organizations = organizations_for_item(item)
    if item.get("source") in _HANDLE_SOURCES and organizations:
        return str(organizations[0]).casefold()
    authors = item.get("authors") or []
    return str(authors[0] if authors else item.get("title") or "").casefold()


def select_top_items(
    days: list[dict[str, Any]], date: str, *, limit: int = DEFAULT_LIMIT
) -> list[dict[str, Any]]:
    """Return the highest-scored new items first seen on ``date``, one per owner."""
    earlier: set[str] = set()
    target: dict[str, Any] | None = None
    for day in days:
        if day.get("date") == date:
            target = day
        elif str(day.get("date") or "") < date:
            for item in day.get("evidence_items") or []:
                earlier |= _identities(item)
    if target is None:
        return []
    candidates = [
        item
        for item in target.get("evidence_items") or []
        if item.get("recommended", True)
        and item.get("event_kind") == "released"
        and not item.get("suppression_reasons")
        and item.get("source") not in _EXCLUDED_SOURCES
        and not _identities(item) & earlier
    ]
    candidates.sort(key=lambda item: (-float(item.get("total_score") or 0.0), item["title"]))
    owners: set[str] = set()
    selected: list[dict[str, Any]] = []
    for item in candidates:
        owner = _owner_key(item)
        if owner in owners:
            continue
        owners.add(owner)
        selected.append(item)
        if len(selected) == limit:
            break
    return selected


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _unique_people(names: list[str]) -> list[str]:
    # Merged sources list one person twice: "Toshiharu Ohnuma" from DataCite and
    # "Ohnuma, Toshiharu" from Zenodo. Only a single comma reads as a reversed
    # name; "Smith, Jr., John" and similar are kept as written.
    people: dict[str, str] = {}
    for raw in names:
        name = " ".join(str(raw).split())
        parts = name.split(",")
        if len(parts) == 2 and all(part.strip() for part in parts):
            name = f"{parts[1].strip()} {parts[0].strip()}"
        if name:
            people.setdefault(name.casefold(), name)
    return list(people.values())


def _github_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _openalex_institutions(arxiv_id: str, fetch: Fetch) -> list[str]:
    work = fetch(f"https://api.openalex.org/works/doi:10.48550/arXiv.{arxiv_id}")
    return _unique(
        [
            str(institution.get("display_name") or "")
            for authorship in work.get("authorships") or []
            for institution in authorship.get("institutions") or []
        ]
    )


def _arxiv_html_affiliations(arxiv_id: str, fetch_text: Fetch) -> list[str]:
    page = fetch_text(f"https://arxiv.org/html/{arxiv_id}")
    affiliations: list[str] = []
    for match in _AFFILIATION_SPAN.finditer(page):
        depth, end = 1, match.end()
        for tag in _SPAN_TAG.finditer(page, match.end()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.start()
                break
        inner = re.sub(r'<span class="ltx_contact_name">.*?</span>', "", page[match.end() : end])
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", inner)).split())
        affiliations.append(text.removeprefix("Affiliation:").strip())
    return _unique(affiliations)


def _huggingface_creator(handle: str, fetch: Fetch) -> tuple[list[str], list[str]]:
    # An organization's display name is the institution ("NLP at University of
    # Utah"). A user profile has no affiliation field; its org memberships say
    # who the user follows or joined, not who they work for, so they are unused.
    try:
        org = fetch(f"https://huggingface.co/api/organizations/{handle}/overview")
        return [], _unique([str(org.get("fullname") or handle)])
    except RequestError:
        user = fetch(f"https://huggingface.co/api/users/{handle}/overview")
        return _unique([str(user.get("fullname") or handle)]), []


def _github_creator(handle: str, fetch: Fetch) -> tuple[list[str], list[str]]:
    profile = fetch(f"https://api.github.com/users/{handle}", headers=_github_headers())
    name = str(profile.get("name") or handle)
    if profile.get("type") == "Organization":
        return [], [name]
    return [name], _unique([str(profile.get("company") or "").lstrip("@")])


def resolve_creators(
    item: dict[str, Any], *, fetch: Fetch = get_json, fetch_text: Fetch = get_text
) -> dict[str, list[str]]:
    """Return the authors and affiliations a reader can verify for ``item``.

    A failed lookup keeps whatever the item already carried. The image then
    shows fewer facts, never a guessed one.
    """
    authors = _unique_people([str(name) for name in item.get("authors") or []])
    organizations = _unique(organizations_for_item(item))
    source = str(item.get("source") or "")
    url = str(item.get("url") or "")
    try:
        if source in {"Hugging Face", "GitHub", "GitHub Organization"} and organizations:
            resolve = _huggingface_creator if source == "Hugging Face" else _github_creator
            owner_authors, affiliations = resolve(organizations[0], fetch)
            return {"authors": authors or owner_authors, "affiliations": affiliations}
        if source in _HANDLE_SOURCES:
            return {"authors": authors, "affiliations": []}
        match = _ARXIV_ID.search(url) if source in {"arXiv", "Hugging Face Papers"} else None
        if match and not organizations:
            try:
                organizations = _openalex_institutions(match.group(1), fetch)
            except _LOOKUP_ERRORS:
                organizations = []
            if not organizations:
                organizations = _arxiv_html_affiliations(match.group(1), fetch_text)
    except (*_LOOKUP_ERRORS, AttributeError, TypeError, ValueError) as error:
        print(f"warning: creator lookup failed for {url}: {error}", file=sys.stderr)
        if source in _HANDLE_SOURCES:
            return {"authors": authors, "affiliations": []}
    return {"authors": authors, "affiliations": organizations}


_EVIDENCE_IDS = re.compile(r"Evidence:\s*([^.]*)")
_FIRST_SENTENCE = re.compile(r"^(.+?[.!?])(?:\s|$)")
_MODEL_BRIEFING = "openai-responses"


def _blurb(bullet: str) -> str:
    """The bullet's first sentence, which states what the benchmark tests."""
    text = " ".join(bullet.split())
    match = _FIRST_SENTENCE.match(text)
    return match.group(1) if match else text


def briefing_items(snapshot: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    """Return (evidence item, blurb) for each briefing bullet, in briefing order.

    Each bullet names its evidence ("Evidence: E014."); its first cited item is
    the benchmark the bullet is about. A deterministic fallback briefing has
    no such citations, so it yields nothing and the caller falls back too.
    """
    briefing = snapshot.get("briefing") or {}
    if briefing.get("generator") != _MODEL_BRIEFING:
        return []
    citations = {str(entry.get("id")): entry for entry in briefing.get("citations") or []}
    by_url = {item.get("url"): item for item in snapshot.get("evidence_items") or []}
    picked: list[tuple[dict[str, Any], str]] = []
    seen: set[str] = set()
    for bullet in briefing.get("bullets") or []:
        match = _EVIDENCE_IDS.search(str(bullet))
        ids = re.findall(r"\b[A-Z]\d+\b", match.group(1)) if match else []
        citation = next((citations[i] for i in ids if i in citations), None)
        url = str((citation or {}).get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        item = by_url.get(url) or {
            "title": citation.get("title"),
            "url": url,
            "source": citation.get("source"),
        }
        picked.append((item, _blurb(str(bullet))))
    return picked


def _card(
    item: dict[str, Any],
    blurb: str,
    creators: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "title": item.get("title"),
        "url": item.get("url"),
        "source": item.get("source"),
        "published_at": item.get("published_at"),
        "categories": list(item.get("categories") or []),
        "blurb": blurb or str(item.get("summary") or ""),
        "authors": creators["authors"],
        "affiliations": creators["affiliations"],
    }


def build_share_block(
    days: list[dict[str, Any]],
    date: str,
    *,
    previous: dict[str, Any] | None = None,
    fetch: Fetch | None = None,
    fetch_text: Fetch | None = None,
) -> dict[str, Any] | None:
    """Return the ``share`` block for ``date``, or None without that day's snapshot.

    ``previous`` is the block an earlier pass wrote for the same day. Its cards
    are kept as they are, in their order, so a second pass cannot change a
    card that may already have been posted.
    """
    snapshot = next((day for day in days if day.get("date") == date), None)
    if snapshot is None:
        return None
    picked = briefing_items(snapshot)
    basis = "briefing"
    if not picked:
        basis = "radar_score"
        picked = [(item, "") for item in select_top_items(days, date, limit=DEFAULT_LIMIT)]
    # Cards an earlier pass recorded may already be posted under their file
    # name (card-01.png is the first card), so they keep their place and their
    # content. A later pass only appends benchmarks the day had not carded.
    kept = [dict(card) for card in (previous or {}).get("cards") or [] if card.get("url")]
    carded = {card["url"] for card in kept}
    if fetch is None or fetch_text is None:
        fetch, fetch_text = budgeted_fetchers()
    cards = kept + [
        _card(item, blurb, resolve_creators(item, fetch=fetch, fetch_text=fetch_text))
        for item, blurb in picked
        if item.get("url") not in carded
    ]
    return {
        "schema_version": SHARE_SCHEMA_VERSION,
        "date": date,
        "basis": str((previous or {}).get("basis") or basis) if kept else basis,
        "top": [card["url"] for card in cards[:DEFAULT_LIMIT]],
        "cards": cards,
    }


def card_image_name(index: int) -> str:
    """File name of the ``index``-th (1-based) card in the day's folder."""
    return f"card-{index:02d}.png"


def daily_image_url(date: str, name: str) -> str:
    """Public URL of one of the day's images on the cards site."""
    return f"{CARDS_SITE_URL}/daily/{date}/{name}"


def write_share_block(snapshot_dir: Path, date: str) -> dict[str, Any] | None:
    """Add the ``share`` block to the committed snapshot for ``date``."""
    path = snapshot_dir / f"{date}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    block = build_share_block(load_snapshots(snapshot_dir), date, previous=raw.get("share"))
    if block is None:
        return None
    raw["share"] = block
    validate_snapshot(raw, source=str(path))
    _write_json(path, raw)
    return block
