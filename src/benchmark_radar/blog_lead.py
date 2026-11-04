"""Name a daily post after the benchmark it leads with (#593).

A search result titled "Daily AI benchmark brief: 2026-11-03" names nothing a
reader searches for. These helpers pick the same benchmarks as the day's share
cards and turn the first into a short, faithful title.
"""

from __future__ import annotations

import re
from typing import Any

# "AgentPhishing: A Benchmark of LLM Email Agents" leads with its name, as the
# Today card does (splitBenchmarkTitle in app.js). A prefix under four
# characters is not a name a reader knows, so the whole title stays.
_NAMED_TITLE = re.compile(r"^(.{2,40}?):\s+(.{8,})$")
_LEAD_NAME_LIMIT = 60
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# The Today card's SLUG_TITLE: "owner/name", optionally followed by a version.
_REPO_TITLE = re.compile(r"^[^\s/]+/([^\s/]+)(\s+\S+)?$")
_NATURAL_BREAK = re.compile(r"(?<=\?)\s|:\s|\s[-–—]\s")


def _lead_name(title: str) -> str:
    """The shortest faithful name: a benchmark's own name, else its first clause."""
    text = " ".join(str(title or "").split())
    repo = _REPO_TITLE.match(text)
    if repo:
        return repo.group(1) + (repo.group(2) or "")
    match = _NAMED_TITLE.match(text)
    if match and len(match.group(1).strip()) >= 4:
        return match.group(1).strip()
    if len(text) <= _LEAD_NAME_LIMIT:
        return text
    # "Is Your Long-Horizon Benchmark Really Deep? Measuring ..." ends its
    # question first; cutting mid-phrase reads as broken in a search result.
    clause = _NATURAL_BREAK.search(text)
    if clause and 8 <= clause.start() <= _LEAD_NAME_LIMIT:
        return text[: clause.start()].rstrip(" :")
    return text[:_LEAD_NAME_LIMIT].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"


def _lead_picks(
    snapshot: dict[str, Any], days: list[dict[str, Any]] | None
) -> list[tuple[str, str]]:
    """The day's picks: its share cards, else the rule the share step would apply.

    Share blocks exist only from 2026-10-25. Older days get the same choice the
    share step makes (``daily_top.build_share_block``): the daily briefing's
    benchmarks, else the radar-score top new releases, one per owner.
    Each pick is (title, URL); a pick without a title is dropped.
    """
    cards = (snapshot.get("share") or {}).get("cards") or []
    if cards:
        return _titled(cards)
    # Imported here: daily_top imports snapshots, which imports this module.
    from .daily_top import DEFAULT_LIMIT, briefing_items, select_top_items

    picked = _titled(item for item, _ in briefing_items(snapshot))
    if not picked and days is not None:
        picked = _titled(
            select_top_items(days, str(snapshot.get("date") or ""), limit=DEFAULT_LIMIT)
        )
    return picked


def _titled(items: Any) -> list[tuple[str, str]]:
    picks = ((str(item.get("title") or "").strip(), str(item.get("url") or "")) for item in items)
    return [(title, url) for title, url in picks if title]


def _lead_titles(
    snapshot: dict[str, Any],
    day: str,
    days: list[dict[str, Any]] | None = None,
    *,
    picks: list[tuple[str, str]] | None = None,
) -> tuple[str, str] | None:
    """Title a day after its lead benchmark, the same pick as its top share card.

    A search result titled "Daily AI benchmark brief: 2026-11-03" says nothing a
    reader can search for; "MemHarmBench and 4 more in AI benchmark news" names
    the day's lead benchmark (#593). The share block is the daily briefing's
    benchmarks, or the radar-score top three on a day without a briefing.
    A day with no pick keeps its dated title.
    """
    if picks is None:
        picks = _lead_picks(snapshot, days)
    name = _lead_name(picks[0][0]) if picks else ""
    if not name:
        return None
    try:
        year, month, date_of_month = (int(part) for part in day.split("-"))
        when = f"{_MONTHS[month - 1]} {date_of_month}, {year}"
    except (ValueError, IndexError):
        when = day
    # Picks include tool updates and audits as well as releases, so the title
    # says "AI benchmark news", never "new AI benchmarks".
    more = len(picks) - 1
    english = (
        f"{name} and {more} more in AI benchmark news · {when}"
        if more
        else f"AI benchmark news: {name} · {when}"
    )
    chinese = (
        f"{name} 等 {len(picks)} 条 AI benchmark 动态 · {day}"
        if more
        else f"AI benchmark 动态：{name} · {day}"
    )
    return english, chinese
