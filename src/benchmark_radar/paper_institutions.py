"""Institutions behind an arXiv paper, read from OpenAlex or the paper itself (#1120).

OpenAlex's linked institutions come first: they are normalized names, so one
institution reads the same on every card and can be counted. OpenAlex lags new
papers by days to weeks, so a paper it does not hold yet falls back to the
affiliations its own arXiv HTML prints, cleaned but otherwise as written. The
basis travels with the names, and only the OpenAlex basis feeds any count.

arXiv's HTML marks affiliations in two ways this module reads:

* ``ltx_role_affiliation`` contact spans, one per author;
* numbered lines under the author list (``<sup>1</sup> Nanjing University``),
  which some templates render as a table. A line counts only when it starts
  with a single number or letter marker: an author's own marker follows the
  name (``Yang Chen<sup>1,2</sup>``), so a name is never read as a place.

A paper whose HTML lost its affiliations in conversion (arXiv then prints a
bare ``[``) returns nothing rather than a guess.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from typing import Any

SHOWN_INSTITUTIONS = 3

BASIS_OPENALEX = "openalex_linked_institutions"
BASIS_ARXIV_HTML = "arxiv_html_affiliations"

# New-style arXiv ids, with or without a version, in an abs/pdf/html URL, an
# `arxiv:` artifact id, or the DOI arXiv registers (10.48550/arXiv.<id>).
_ARXIV_ID = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv[:.])(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE
)

_AFFILIATION_SPAN = re.compile(r'<span class="ltx_contact ltx_role_affiliation">')
_SPAN_TAG = re.compile(r"<(/?)span\b[^>]*>")
_AUTHORS_BLOCK = re.compile(r'<div class="ltx_authors[^"]*"[^>]*>')
_LINE_BREAK = re.compile(
    r"<br\b[^>]*>|<(?:div|p)\b[^>]*>"
    r'|<span\b[^>]*class="[^"]*\b(?:ltx_tr|ltx_td|ltx_p|ltx_break|ltx_contact)\b[^"]*"[^>]*>'
)
_MARKER = re.compile(r"[0-9]{1,2}|[a-z]")
_LETTER = re.compile(r"[^\W\d_]")


def arxiv_id(text: str | None) -> str | None:
    """The new-style arXiv id a URL or artifact id names, without its version."""
    match = _ARXIV_ID.search(str(text or ""))
    return match.group(1) if match else None


def clean_affiliation(text: str) -> str | None:
    """One affiliation as a reader should see it, or None when it names nothing.

    Collapses whitespace, trims the separators templates leave around a name
    (``Duke University;``), and drops strings with no letter (``[``), e-mail
    addresses, and fragments too short or too long to be an institution.
    """
    value = " ".join(html.unescape(str(text or "")).split())
    value = value.strip(" ,;:.·|-–—*†‡∗")
    value = re.sub(r"\s+,", ",", value)
    if not _LETTER.search(value) or "@" in value:
        return None
    if len(value) < 3 or len(value) > 160:
        return None
    return value


def _unique(values: list[str | None]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def _element_end(page: str, start: int) -> int:
    """Index just past the element that opens at ``start``, counting nesting."""
    name = re.match(r"<(\w+)", page[start:])
    if not name:
        return len(page)
    depth = 0
    for tag in re.finditer(rf"<(/?){name.group(1)}\b[^>]*>", page[start:]):
        if tag.group(0).endswith("/>"):
            continue
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return start + tag.end()
    return len(page)


def _without(block: str, css_class: str) -> str:
    """``block`` with every span or div carrying ``css_class`` removed whole."""
    pattern = re.compile(rf'<(?:span|div)\b[^>]*class="[^"]*\b{css_class}\b[^"]*"[^>]*>')
    kept, position = [], 0
    while match := pattern.search(block, position):
        kept.append(block[position : match.start()])
        position = _element_end(block, match.start())
    kept.append(block[position:])
    return "".join(kept)


def _contact_affiliations(page: str) -> list[str]:
    found: list[str | None] = []
    for match in _AFFILIATION_SPAN.finditer(page):
        depth, end = 1, match.end()
        for tag in _SPAN_TAG.finditer(page, match.end()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.start()
                break
        inner = re.sub(r'<span class="ltx_contact_name">.*?</span>', "", page[match.end() : end])
        text = re.sub(r"<[^>]+>", " ", inner)
        found.append(clean_affiliation(html.unescape(text).removeprefix("Affiliation:")))
    return _unique(found)


def _numbered_affiliations(page: str) -> list[str]:
    opening = _AUTHORS_BLOCK.search(page)
    if not opening:
        return []
    # Source newlines are layout, not lines: only tags start a new line below.
    block = re.sub(r"\s+", " ", page[opening.start() : _element_end(page, opening.start())])
    block = _without(block, "ltx_note")
    block = _without(block, "ltx_role_email")
    block = re.sub(
        r"<sup\b[^>]*>(.*?)</sup>",
        lambda sup: "\x00" + re.sub(r"<[^>]+>", "", sup.group(1)).strip() + "\x01",
        block,
        flags=re.DOTALL,
    )
    text = html.unescape(re.sub(r"<[^>]+>", " ", _LINE_BREAK.sub("\n", block)))
    found: list[str | None] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("\x00"):
            continue
        for marker, body in re.findall(r"\x00([^\x01]*)\x01([^\x00]*)", line):
            if _MARKER.fullmatch(marker.strip()):
                found.append(clean_affiliation(body))
    return _unique(found)


def arxiv_html_affiliations(page: str) -> list[str]:
    """Affiliations an arXiv HTML page prints, in order, cleaned."""
    return _contact_affiliations(page) or _numbered_affiliations(page)


def openalex_institutions(work: dict[str, Any]) -> list[str]:
    """OpenAlex's linked institutions for a work, in first-appearance order."""
    return _unique(
        [
            str(institution.get("display_name") or "").strip() or None
            for authorship in work.get("authorships") or []
            for institution in authorship.get("institutions") or []
        ]
    )


def lookup(
    paper: str,
    *,
    fetch_json: Callable[[str], Any],
    fetch_text: Callable[[str], Any],
) -> dict[str, Any] | None:
    """Institutions for one arXiv paper with the basis and URL they were read from.

    Returns None when neither OpenAlex nor the paper's HTML names any. Lookup
    errors propagate, so a caller can tell "not found" from "not reachable".
    """
    try:
        work = fetch_json(f"https://api.openalex.org/works/doi:10.48550/arXiv.{paper}")
    except Exception as error:  # noqa: BLE001 - OpenAlex 404s every paper it lacks
        if "404" not in str(error):
            raise
        work = {}
    names = openalex_institutions(work or {})
    if names:
        return {
            "basis": BASIS_OPENALEX,
            "source_url": str(work.get("id") or f"https://doi.org/10.48550/arXiv.{paper}"),
            "institutions": names,
        }
    url = f"https://arxiv.org/html/{paper}"
    try:
        page = fetch_text(url)
    except Exception as error:  # noqa: BLE001 - papers without HTML 404
        if "404" not in str(error):
            raise
        return None
    names = arxiv_html_affiliations(str(page or ""))
    if not names:
        return None
    return {"basis": BASIS_ARXIV_HTML, "source_url": url, "institutions": names}
