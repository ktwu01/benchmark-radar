"""Generate sitemap.xml for the published dashboard (issue #236).

The dashboard is one HTML document whose views are query-string variants of a
single path. Each view is still a page a reader can land on, link, and search,
so each one is listed as its own indexable URL with a canonical that matches
(see `VIEW_SEO` in assets/app.js). Filter permutations are deliberately left
out: a sitemap should tell crawlers which doors exist, not enumerate every
state behind them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .feed import SITE_URL

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"

# One entry per dashboard view, in nav order. logos.html is excluded on
# purpose: it is a maintainer QA page carrying <meta name="robots"
# content="noindex">, so listing it would contradict the page itself.
INDEXABLE_VIEWS: tuple[tuple[str, str], ...] = (
    ("Today", "/"),
    ("Leaderboard", "/?view=leaderboard"),
    ("Trends", "/?view=trends"),
    ("Explore", "/?view=map"),
)

ET.register_namespace("sm", SITEMAP_NAMESPACE)


def _lastmod_date(snapshots: list[dict[str, Any]]) -> str | None:
    """Date of the newest snapshot, or None when there is no history yet.

    Derived from the snapshots rather than the clock so two rebuilds over the
    same history produce byte-identical output; feed.xml's lastBuildDate makes
    the same choice.
    """
    if not snapshots:
        return None
    generated = max(
        datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00"))
        for snapshot in snapshots
    )
    return generated.astimezone(UTC).date().isoformat()


def _q(tag: str) -> str:
    # Tags are written with the qualified name; register_namespace above makes
    # the serializer emit the readable sm: prefix instead of ns0.
    return f"{{{SITEMAP_NAMESPACE}}}{tag}"


def sitemap_tree(snapshots: list[dict[str, Any]]) -> ET.ElementTree:
    """Build one stable urlset covering every indexable view."""
    root = ET.Element(_q("urlset"))
    lastmod = _lastmod_date(snapshots)
    for _, path in INDEXABLE_VIEWS:
        url = ET.SubElement(root, _q("url"))
        ET.SubElement(url, _q("loc")).text = SITE_URL + path
        if lastmod:
            ET.SubElement(url, _q("lastmod")).text = lastmod
    return ET.ElementTree(root)


def write_sitemap(snapshots: list[dict[str, Any]], output: Path) -> Path:
    """Write a deterministic UTF-8 sitemap beside the published data."""
    output.parent.mkdir(parents=True, exist_ok=True)
    tree = sitemap_tree(snapshots)
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output
