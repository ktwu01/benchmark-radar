"""Build human-readable descriptions from source metadata.

The radar must never present a templated sentence as if it were a description.
Boilerplate is worse than an empty string for two reasons:

1. It tells the reader nothing that the source and event chips do not already say.
2. `score_item` reads `summary`, so a template that contains taxonomy words
   ("dataset", "benchmark") makes the pipeline score itself on its own prose and
   inflates relevance for every record from that source.

So every helper here returns text drawn from the upstream payload, or "" when the
upstream genuinely published nothing. Callers must treat "" as "no description
available" rather than substituting a filler sentence.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Any

# Card text arrives as rendered markdown: tabs, collapsed headings, badge alt
# text. Keep the first real sentence(s) and drop the scaffolding.
_WHITESPACE = re.compile(r"\s+")
# Images first: a badge is often an image wrapped in a link, and removing the
# inner image leaves the outer link matchable rather than a stray "](url)".
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_NOISE = re.compile(
    r"""
    \[([^\]]*)\]\([^)]*\)   # links: keep the visible label, drop the target
    | <[^>]+>               # inline html
    | ^\s*[#>*-]+\s*        # heading / quote / bullet markers
    | [*_`]{1,3}            # emphasis and code ticks
    """,
    re.VERBOSE | re.MULTILINE,
)
# YAML front matter in a dataset card is metadata, not description prose.
_FRONT_MATTER = re.compile(r"\A\s*---.*?\n---\s*", re.DOTALL)

# Keep enough upstream prose for useful inline expansion while bounding the
# static payload. The UI links to the full source/card for anything beyond it.
MAX_SUMMARY_CHARS = 2_000


def clean_card_text(text: str | None) -> str:
    """Reduce a dataset/model card to plain prose, or "" if nothing survives."""
    if not text:
        return ""
    stripped = _FRONT_MATTER.sub("", text)
    stripped = _MARKDOWN_IMAGE.sub(" ", stripped)
    # Link labels are real prose, so keep group 1; other alternatives have no
    # group and collapse to a space.
    stripped = _MARKDOWN_NOISE.sub(lambda match: match.group(1) or " ", stripped)
    collapsed = _WHITESPACE.sub(" ", stripped).strip()
    if len(collapsed) <= MAX_SUMMARY_CHARS:
        return collapsed
    # Prefer a sentence boundary so the text does not end mid-word.
    window = collapsed[: MAX_SUMMARY_CHARS + 1]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut > MAX_SUMMARY_CHARS // 3:
        return window[: cut + 1].strip()
    return collapsed[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0].strip() + "…"


def _echoes_title(text: str, title: str) -> bool:
    """True when the card opens by repeating its own repo name and says no more."""
    slug = title.rsplit("/", 1)[-1]
    normalize = lambda value: re.sub(r"[^a-z0-9]+", "", value.lower())  # noqa: E731
    return normalize(text) == normalize(slug)


def strip_title_echo(text: str, title: str) -> str:
    """Drop a leading repeat of the repo name, which carries no new information."""
    if not text:
        return ""
    slug = title.rsplit("/", 1)[-1]
    pattern = re.compile(rf"\A{re.escape(slug)}\s*[:.\-–]?\s*", re.IGNORECASE)
    trimmed = pattern.sub("", text).strip()
    return "" if _echoes_title(trimmed, title) or not trimmed else trimmed


# A Hub Space template ships a filled-in `short_description`, and a Space
# started from one keeps that line until its maintainer rewrites it. The text
# describes the template rather than the repo, so it fails the same test as a
# generated summary even when it arrives as genuine upstream text.
TEMPLATE_DESCRIPTIONS = frozenset(
    {
        # gradio-templates/leaderboard, and every leaderboard duplicated from it
        "duplicate this leaderboard to initialize your own!",
        # the Streamlit Space template's placeholder card
        "streamlit template space",
    }
)

# Two owners are enough to call a line inherited rather than authored: the same
# sentence cannot be specific to repos that have nothing but a template parent
# in common.
SHARED_DESCRIPTION_OWNERS = 2


def is_template_description(text: str | None) -> bool:
    """True when the text is Hub template scaffolding rather than a description."""
    return (text or "").strip().casefold() in TEMPLATE_DESCRIPTIONS


def inherited_short_descriptions(
    entries: Iterable[tuple[str, str, datetime | None]],
    *,
    min_owners: int = SHARED_DESCRIPTION_OWNERS,
) -> frozenset[str]:
    """Return the repo ids whose one-line card came from a parent, not its owner.

    Duplicating a Space copies its `short_description`, so the parent's line
    reappears verbatim on a child that it says nothing about. The sharing is not
    symmetric: the owner who created the earliest repo carrying the line wrote
    it and keeps it, while a later owner carrying it verbatim duplicated the
    parent. Keying the author by owner rather than by repo also leaves one
    maintainer's matched dataset and leaderboard pair intact, since one owner
    describing two halves of their own artifact with one sentence wrote that
    sentence.

    Each text must be the line as the Hub published it, before any rendering
    this module does: two owners whose different cards happen to render alike
    copied nothing. A repo with no creation date cannot be placed on either
    side of the order, so it neither claims authorship nor loses its line.
    """
    copies: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for repo_id, text, created in entries:
        normalized = text.strip().casefold()
        if normalized and created is not None:
            copies[normalized].append((created, repo_id))
    inherited: set[str] = set()
    for group in copies.values():
        owner = lambda repo_id: repo_id.split("/", 1)[0].casefold()  # noqa: E731
        if len({owner(repo_id) for _, repo_id in group}) < min_owners:
            continue
        # The repo id breaks a timestamp tie so the choice is reproducible.
        group.sort()
        author = owner(group[0][1])
        inherited.update(repo_id for _, repo_id in group if owner(repo_id) != author)
    return frozenset(inherited)


def huggingface_summary(row: dict[str, Any], title: str) -> str:
    """Describe a Hugging Face repo using only what its maintainer published.

    Returns "" when the repo has no prose. Structured tags remain available in
    the raw payload for future typed fields, but must not be rewritten into a
    sentence that can influence relevance scoring.
    """
    prose = strip_title_echo(clean_card_text(row.get("description")), title)
    if prose:
        return prose
    # Spaces expose their maintainer-written short description in cardData
    # instead of the dataset/model description field. It remains direct upstream
    # text, so using it preserves the no-generated-summary rule.
    card_data = row.get("cardData") or {}
    if isinstance(card_data, dict):
        short = strip_title_echo(clean_card_text(card_data.get("short_description")), title)
        return "" if is_template_description(short) else short
    return ""


def github_summary(row: dict[str, Any]) -> str:
    """GitHub repo description, or "" when the owner left it blank."""
    return clean_card_text(row.get("description"))
