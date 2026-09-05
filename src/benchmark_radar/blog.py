"""Publish one page per collection day under /blog/.

The site already had two ways to look at the daily corpus: the dashboard's
Today view, which shows one day at a time behind JavaScript, and feed.xml,
which lists a one-line count summary per day. Neither is a page. The briefing
text, the six question answers, the cited statistics and the counter-views that
the pipeline writes into every snapshot were stored and never displayed
anywhere a reader or a crawler could reach them, so the most readable thing the
project produces was also its least visible.

This module gives each committed snapshot a URL. Every page is derived from the
snapshot and only from the snapshot, so the output directory is generated,
gitignored, and replaced wholesale on each build rather than patched. A day
that leaves the history loses its page in the same run, which is why the whole
tree is staged and swapped instead of written in place: a half-written blog
that still serves last build's pages under this build's sitemap is worse than
no blog.

Calendar days with no snapshot get no page. Inventing an empty post for a day
the collector did not run would put a URL in the sitemap that reports nothing,
and the gap in the archive is itself accurate: it says the radar did not
collect that day.
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, date, datetime, time
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .blog_content import build_post
from .blog_shell import (
    BLOG_ARCHIVE_PATH,
    BLOG_FEED_PATH,
    BLOG_PATH,
    BlogPost,
    SiteChrome,
    extract_site_chrome,
    render_page,
)
from .feed import ATOM_NAMESPACE, SITE_URL
from .site_shell import breadcrumb_schema, esc, webpage_schema

LATEST_POST_LIMIT = 30

# The dashboard's toggle and star count translate these at runtime; the
# chrome's own data-i18n keys cover everything else.
_TOGGLE_I18N_KEYS = ("Switch to Chinese (中文)", "Switch to English")
_BADGE_I18N_KEYS = ("Star this repository on GitHub. {count} stars",)
# The footer's build date prefix is baked in per page, after the keys were
# collected from the raw extracted chrome, so it is listed here.
_FOOTER_I18N_KEYS = ("Updated",)

_INDEX_TITLE = "AI benchmark daily brief | Benchmark Radar"
_INDEX_HEADING = "What changed in AI evaluation, and why it matters"
_INDEX_DESCRIPTION = (
    "One page per collection day: what new benchmarks and evaluations appeared, "
    "how strong the evidence was, and which claims the record does not support."
)
_ARCHIVE_TITLE = "Daily brief archive | Benchmark Radar"
_ARCHIVE_HEADING = "Every collection day on record"
_ARCHIVE_DESCRIPTION = (
    "The complete archive of Benchmark Radar daily briefs, one page for every "
    "day the radar collected evidence."
)


def _post_page(post: BlogPost, chrome: SiteChrome, chrome_i18n: dict[str, str]) -> str:
    tags = "".join(f'<span class="blog-chip">{esc(tag)}</span>' for tag in post.tags)

    def language_body(language: str, content: str, *, hidden: bool) -> str:
        title = post.title_zh if language == "zh" and post.title_zh else post.title
        description = (
            post.description_zh if language == "zh" and post.description_zh else post.description
        )
        hidden_attr = " hidden" if hidden else ""
        return f"""<div data-lang-content="{language}"{hidden_attr}>
<header class="blog-hero">
  <p class="eyebrow">{esc(post.kind)}</p>
  <h1>{esc(title)}</h1>
  <p class="blog-lede">{esc(description)}</p>
  <p class="blog-meta"><time datetime="{esc(post.published)}">{esc(post.published)}</time></p>
  <div class="blog-tags">{tags}</div>
</header>
<div class="blog-prose">{content}</div>
</div>"""

    body = language_body("en", post.body_en, hidden=False)
    if post.body_zh is not None:
        body += language_body("zh", post.body_zh, hidden=True)
    posting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "@id": post.canonical,
        "headline": post.title,
        "description": post.description,
        "url": post.canonical,
        "mainEntityOfPage": post.canonical,
        "datePublished": post.published,
        "dateModified": post.updated,
        "inLanguage": ["en", "zh-Hans"] if post.translated else "en",
        "author": {"@type": "Organization", "name": "Benchmark Radar"},
        "publisher": {"@id": f"{SITE_URL}/#organization"},
        "isPartOf": {"@id": SITE_URL + BLOG_PATH},
        "citation": [url for _, _, url in post.sources],
        "keywords": list(post.tags),
    }
    return render_page(
        title=f"{post.title} | Benchmark Radar",
        description=post.description,
        canonical=post.canonical,
        body=body,
        chrome=chrome,
        chrome_i18n=chrome_i18n,
        updated=post.updated,
        schemas=(
            posting,
            breadcrumb_schema(
                ("Benchmark Radar", f"{SITE_URL}/"),
                ("Blog", SITE_URL + BLOG_PATH),
                (post.title, post.canonical),
                canonical=post.canonical,
            ),
        ),
        og_type="article",
    )


def _post_card(post: BlogPost) -> str:
    return f"""<li><article class="blog-card">
  <div><span class="blog-chip">{esc(post.kind)}</span>
  <h2><a href="{esc(post.path)}">{esc(post.title)}</a></h2></div>
  <time class="blog-meta" datetime="{esc(post.published)}">{esc(post.published)}</time>
  <p>{esc(post.description)}</p>
</article></li>"""


def _index_page(
    posts: list[BlogPost], *, archive: bool, chrome: SiteChrome, chrome_i18n: dict[str, str]
) -> str:
    canonical = SITE_URL + (BLOG_ARCHIVE_PATH if archive else BLOG_PATH)
    shown = posts if archive else posts[:LATEST_POST_LIMIT]
    cards = "".join(_post_card(post) for post in shown) or (
        '<li class="blog-panel">No collection days are on record yet.</li>'
    )
    if archive:
        title, heading, description = _ARCHIVE_TITLE, _ARCHIVE_HEADING, _ARCHIVE_DESCRIPTION
        action = f'<a class="secondary-link" href="{BLOG_PATH}">Latest briefs</a>'
        crumb = "Blog archive"
    else:
        title, heading, description = _INDEX_TITLE, _INDEX_HEADING, _INDEX_DESCRIPTION
        action = f'<a class="secondary-link" href="{BLOG_ARCHIVE_PATH}">Full archive</a>'
        crumb = "Blog"
    count = (
        f"{len(shown)} of {len(posts)} collection days"
        if not archive and len(shown) < len(posts)
        else f"{len(posts)} collection days"
    )
    body = f"""<header class="blog-hero">
  <p class="eyebrow">Daily brief</p><h1>{esc(heading)}</h1>
  <p class="blog-lede">{esc(description)}</p>
  <p class="blog-meta">{esc(count)}</p>
  <div class="blog-actions">{action}
    <a class="secondary-link" href="{BLOG_FEED_PATH}">RSS</a></div>
</header>
<ol class="blog-index">{cards}</ol>"""
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "url": post.canonical}
            for index, post in enumerate(shown, start=1)
        ],
    }
    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        body=body,
        chrome=chrome,
        chrome_i18n=chrome_i18n,
        updated=posts[0].updated if posts else "—",
        schemas=(
            webpage_schema(title=title, description=description, canonical=canonical),
            item_list,
            breadcrumb_schema(
                ("Benchmark Radar", f"{SITE_URL}/"),
                (crumb, canonical),
                canonical=canonical,
            ),
        ),
    )


def blog_feed_tree(posts: list[BlogPost]) -> ET.ElementTree:
    """A feed of the blog itself, separate from the site feed.

    ``/feed.xml`` publishes one count summary per collection day and points at
    the dashboard. This one points at the written pages and carries their
    descriptions, so a subscriber to either gets what that feed promised
    instead of two feeds racing to describe the same days differently.
    """
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Benchmark Radar daily brief"
    ET.SubElement(channel, "link").text = SITE_URL + BLOG_PATH
    ET.SubElement(channel, "description").text = _INDEX_DESCRIPTION
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(
        channel,
        f"{{{ATOM_NAMESPACE}}}link",
        {
            "href": SITE_URL + BLOG_FEED_PATH,
            "rel": "self",
            "type": "application/rss+xml",
        },
    )
    if posts:
        newest = max(date.fromisoformat(post.updated) for post in posts)
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(
            datetime.combine(newest, time.min, tzinfo=UTC), usegmt=True
        )
    for post in posts:
        published = datetime.combine(date.fromisoformat(post.published), time.min, tzinfo=UTC)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post.title
        ET.SubElement(item, "link").text = post.canonical
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = post.canonical
        ET.SubElement(item, "pubDate").text = format_datetime(published, usegmt=True)
        ET.SubElement(item, "description").text = post.description
    return ET.ElementTree(root)


def build_posts(snapshots: list[dict[str, Any]]) -> list[BlogPost]:
    """One post per snapshot, newest first, with duplicate days rejected."""
    posts = [build_post(snapshot) for snapshot in snapshots]
    slugs = [post.slug for post in posts]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise ValueError(f"duplicate snapshot dates cannot share a blog URL: {duplicates}")
    posts.sort(key=lambda post: post.slug, reverse=True)
    return posts


def _parse_zh_table(app_js: str) -> dict[str, str]:
    """The reviewed English→Chinese strings from app.js's ``I18N.zh`` table."""
    start = app_js.find("const I18N = {")
    if start == -1:
        raise ValueError(
            "app.js no longer defines `const I18N`; the blog chrome cannot bake its translations"
        )
    open_brace = app_js.find("{", start)
    depth = 0
    end = -1
    for index in range(open_brace, len(app_js)):
        if app_js[index] == "{":
            depth += 1
        elif app_js[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end == -1:
        raise ValueError(
            "app.js's I18N table is unbalanced; the blog chrome cannot bake its translations"
        )
    table: dict[str, str] = {}
    # Object keys are quoted or bare JS identifiers (both appear in the table).
    pair = re.compile(r'(?:"((?:[^"\\]|\\.)*)"|([A-Za-z_$][\w$]*))\s*:\s*"((?:[^"\\]|\\.)*)"')
    for quoted, bare, value in pair.findall(app_js[open_brace:end]):
        table[quoted or bare] = value
    return table


def _chrome_i18n_script(chrome: SiteChrome, app_js: str) -> dict[str, str]:
    """Bake the reviewed zh subset the chrome needs from app.js's I18N table.

    The dashboard translates its chrome in place from the same table; the blog
    has no app.js, so the needed entries ship with the page and blog.js applies
    them with the same contract. Keys come from the chrome itself, so a new
    badge or nav label is covered without touching this function.
    """
    chrome_html = chrome.header + chrome.navigation + chrome.footer
    keys = set(re.findall(r'data-i18n(?:-title|-aria)?="([^"]+)"', chrome_html))
    keys.update(_TOGGLE_I18N_KEYS)
    keys.update(_BADGE_I18N_KEYS)
    keys.update(_FOOTER_I18N_KEYS)
    table = _parse_zh_table(app_js)
    # Keys the table does not carry (short nav labels like Blog and Trends)
    # stay English on the dashboard too — t() falls back to the key itself —
    # so the blog mirrors that instead of inventing translations.
    return {key: table[key] for key in sorted(keys) if key in table}


def write_blog(
    snapshots: list[dict[str, Any]],
    site_dir: Path,
    *,
    dashboard_html: str | None = None,
    app_js: str | None = None,
) -> dict[str, Any]:
    """Write the whole blog tree atomically and report what it published.

    The chrome around every page is extracted from the dashboard source,
    ``site/index.html``, so the site has one masthead, nav, and footer rather
    than two drifting copies. The zh strings the chrome needs are baked from
    app.js's I18N table for the same reason. Tests pass both sources
    explicitly; the defaults read the committed files beside the output
    directory.
    """
    if dashboard_html is None:
        dashboard_source = site_dir / "index.html"
        if not dashboard_source.is_file():
            raise FileNotFoundError(
                "the blog chrome is extracted from the committed dashboard "
                f"source, which is missing at {dashboard_source}"
            )
        dashboard_html = dashboard_source.read_text(encoding="utf-8")
    if app_js is None:
        app_js_source = site_dir / "assets" / "app.js"
        if not app_js_source.is_file():
            raise FileNotFoundError(
                "the blog chrome translations are baked from the committed "
                f"app.js, which is missing at {app_js_source}"
            )
        app_js = app_js_source.read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard_html)
    chrome_i18n = _chrome_i18n_script(chrome, app_js)
    posts = build_posts(snapshots)
    output_dir = site_dir / "blog"
    staging = site_dir / "blog.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(
        _index_page(posts, archive=False, chrome=chrome, chrome_i18n=chrome_i18n),
        encoding="utf-8",
    )
    archive_dir = staging / "archive"
    archive_dir.mkdir()
    (archive_dir / "index.html").write_text(
        _index_page(posts, archive=True, chrome=chrome, chrome_i18n=chrome_i18n),
        encoding="utf-8",
    )
    for post in posts:
        page_dir = staging / post.slug
        page_dir.mkdir()
        (page_dir / "index.html").write_text(
            _post_page(post, chrome, chrome_i18n), encoding="utf-8"
        )
    tree = blog_feed_tree(posts)
    ET.indent(tree, space="  ")
    tree.write(staging / "feed.xml", encoding="utf-8", xml_declaration=True)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)

    lastmod = max((post.updated for post in posts), default=None)
    sitemap_entries: list[tuple[str, str | None]] = [
        (BLOG_PATH, lastmod),
        (BLOG_ARCHIVE_PATH, lastmod),
    ]
    sitemap_entries.extend((post.path, post.updated) for post in posts)
    return {
        "post_count": len(posts),
        "page_count": len(posts) + 2,
        "sitemap_entries": sitemap_entries,
        "output_dir": output_dir,
    }
