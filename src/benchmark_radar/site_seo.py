"""Generate sitemap.xml for the published site (issues #236 and #424).

Each dashboard view and utility sheet is a real page at its own path, written by
app_pages.py from the same document the dashboard is served from. The old
query/hash permalinks still work and are rewritten to the matching path in the
browser, so they are not listed here: a sitemap entry for a URL that immediately
becomes a different URL is a duplicate, not a second page. Filter permutations
are left out for the same reason.

Only views that were actually written are listed. A build without the curated
registry publishes no /leaderboard/, and a sitemap that names a page nobody can
fetch is a 404 the site volunteered.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    ("Leaderboard", "/leaderboard/"),
    ("Saturation", "/saturation/"),
    ("Trends", "/trends/"),
    ("Explore", "/explore/"),
    ("CLI", "/cli/"),
    ("Publications", "/cite/"),
    ("Scoring rubric", "/rubric/"),
)

BENCHMARK_DIRECTORY_PATH = "/benchmarks/"

ET.register_namespace("sm", SITEMAP_NAMESPACE)


def site_lastmod(snapshots: list[dict[str, Any]]) -> str | None:
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


def sitemap_tree(
    snapshots: list[dict[str, Any]],
    benchmark_entries: Sequence[tuple[str, str | None]] = (),
    *,
    view_paths: Sequence[str] | None = None,
    blog_entries: Sequence[tuple[str, str | None]] = (),
    page_entries: Sequence[tuple[str, str | None]] = (),
) -> ET.ElementTree:
    """Build one stable urlset covering views, benchmark pages and daily briefs.

    ``view_paths`` is what the build actually wrote. Passing None lists every
    view, which is what a caller that does not write pages at all wants.

    ``page_entries`` is for standalone documents that are neither a dashboard
    view nor a brief, such as /about/. They are listed separately because
    ``INDEXABLE_VIEWS`` is the set of pages app.js owns the metadata for, and a
    hand-written page has no entry in its SEO tables.

    ``benchmark_entries`` and ``blog_entries`` each carry their own lastmod
    rather than the site-wide one: a benchmark whose newest score is two years
    old, and a brief for a day three weeks ago, did not change when today's
    snapshot landed, and telling a crawler otherwise asks it to refetch the
    whole catalog on every deploy. A build that writes no blog passes nothing
    and lists nothing, the same rule the views follow.
    """
    root = ET.Element(_q("urlset"))
    lastmod = site_lastmod(snapshots)
    published = None if view_paths is None else {"/", *view_paths}
    entries = [
        (path, lastmod) for _, path in INDEXABLE_VIEWS if published is None or path in published
    ]
    entries.append((BENCHMARK_DIRECTORY_PATH, lastmod))
    entries.extend(benchmark_entries)
    entries.extend(blog_entries)
    entries.extend(page_entries)
    seen: set[str] = set()
    for path, entry_lastmod in entries:
        if path in seen:
            continue
        seen.add(path)
        url = ET.SubElement(root, _q("url"))
        ET.SubElement(url, _q("loc")).text = SITE_URL + path
        if entry_lastmod:
            ET.SubElement(url, _q("lastmod")).text = entry_lastmod
    return ET.ElementTree(root)


def write_sitemap(
    snapshots: list[dict[str, Any]],
    output: Path,
    benchmark_entries: Sequence[tuple[str, str | None]] = (),
    *,
    view_paths: Sequence[str] | None = None,
    blog_entries: Sequence[tuple[str, str | None]] = (),
    page_entries: Sequence[tuple[str, str | None]] = (),
) -> Path:
    """Write a deterministic UTF-8 sitemap beside the published data."""
    output.parent.mkdir(parents=True, exist_ok=True)
    tree = sitemap_tree(
        snapshots,
        benchmark_entries,
        view_paths=view_paths,
        blog_entries=blog_entries,
        page_entries=page_entries,
    )
    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output
