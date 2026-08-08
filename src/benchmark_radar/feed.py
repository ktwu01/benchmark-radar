"""Generate the public RSS feed from the committed daily snapshot history."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SITE_URL = "https://ktwu01.github.io/benchmark-radar"
FEED_URL = f"{SITE_URL}/feed.xml"
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"

ET.register_namespace("atom", ATOM_NAMESPACE)


def _rss_date(value: datetime) -> str:
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _snapshot_summary(snapshot: dict[str, Any]) -> str:
    evidence = snapshot.get("evidence_items") or []
    attention = (snapshot.get("attention") or {}).get("observations") or []
    sources = {str(item.get("source") or "").strip() for item in evidence}
    sources.discard("")
    categories = Counter(
        str(category)
        for item in evidence
        for category in (item.get("categories") or [])
        if str(category).strip()
    )

    parts = [
        f"{_count_phrase(len(evidence), 'evidence observation')} "
        f"from {_count_phrase(len(sources), 'source')}",
        _count_phrase(len(attention), "public-attention signal"),
    ]
    if categories:
        counts = ", ".join(f"{name}: {count}" for name, count in sorted(categories.items()))
        parts.append(f"categories — {counts}")
    return "; ".join(parts) + "."


def rss_tree(snapshots: list[dict[str, Any]]) -> ET.ElementTree:
    """Build one stable RSS item per daily snapshot, newest first."""
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Benchmark Radar"
    ET.SubElement(channel, "link").text = SITE_URL + "/"
    ET.SubElement(
        channel, "description"
    ).text = "Daily evidence-first updates on AI benchmarks, evaluations, and datasets."
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(
        channel,
        f"{{{ATOM_NAMESPACE}}}link",
        {"href": FEED_URL, "rel": "self", "type": "application/rss+xml"},
    )

    if snapshots:
        generated = max(
            datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00"))
            for snapshot in snapshots
        )
        ET.SubElement(channel, "lastBuildDate").text = _rss_date(generated)

    for snapshot in sorted(snapshots, key=lambda value: str(value["date"]), reverse=True):
        day = str(snapshot["date"])
        link = f"{SITE_URL}/?date={day}"
        published = datetime.combine(date.fromisoformat(day), time.min, tzinfo=UTC)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Benchmark Radar — {day}"
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = link
        ET.SubElement(item, "pubDate").text = _rss_date(published)
        ET.SubElement(item, "description").text = _snapshot_summary(snapshot)

    return ET.ElementTree(root)


def write_feed(snapshots: list[dict[str, Any]], output: Path) -> None:
    """Write a deterministic UTF-8 RSS document."""
    output.parent.mkdir(parents=True, exist_ok=True)
    tree = rss_tree(snapshots)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
