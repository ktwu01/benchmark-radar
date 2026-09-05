"""The shared site chrome, extracted for the daily brief blog.

``site/index.html`` is the single hand-maintained source of the site's
masthead, section navigation, and footer. Every dashboard route is that same
document served at its own path by ``app_pages.py``; the blog joins it here by
extracting those three regions at build time, so a menubar item, badge, or
footer line can no longer exist on the dashboard but not on a brief.

A blog page is still a static document outside the single-page app, so the
extracted chrome carries a small, explicit set of transforms, each of which
exists because the SPA machinery it referenced is absent:

* the Today control is a view-switching button in the SPA and becomes the
  plain link to ``/`` it already is for crawlers;
* view-only attributes (``data-view``, ``aria-controls``, ``aria-expanded``)
  are dropped from the section nav, and the blog's own link is marked active.
  The CLI id stays because styles.css uses it for the dialog-trigger treatment;
* the Contact button opens a sheet that only exists inside the SPA, so it
  becomes a link to ``/#contact`` — the dashboard deep link that opens the
  same sheet on load;
* the masthead RSS badge keeps the site-wide feed but with a root-relative
  href, so a locally served preview (or any non-canonical mirror) stays on
  the serving host; canonical and ``og:`` URLs keep the absolute SITE_URL;
* the language toggle ships on every page, because the chrome itself is
  always translatable: ``blog.js`` drives it with the same visible
  contract ``app.js`` uses (title, glyph, aria-pressed) and applies the
  same reviewed translations to the chrome — the app.js ``I18N`` table is
  parsed at build time and the subset the chrome needs is baked into the
  page, so a Chinese reader sees 联系作者 and the ⓘ tooltips on a brief
  too. A body without a stored translation simply stays English;
* the footer's build date is baked from the day the page describes.

Nothing here writes files. It owns the record a brief is built into and the
chrome that wraps it, so ``blog_content.py`` can turn snapshots into posts
and ``blog.py`` can decide which pages exist without either of them
restating the masthead.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .feed import SITE_URL
from .site_shell import esc, json_ld

BLOG_PATH = "/blog/"
BLOG_ARCHIVE_PATH = "/blog/archive/"
BLOG_FEED_PATH = "/blog/feed.xml"

# The SPA's Today control maps to the dashboard root; every other section is
# already a real anchor whose href is the server-rendered page.
_TODAY_HREFS = {"today": "/"}


@dataclass(frozen=True)
class BlogPost:
    """One published brief, with its body already rendered.

    ``body_zh`` is None when the snapshot carries no stored translation. That
    absence is what suppresses the language toggle: a toggle that switches to a
    page identical to the one already shown is a broken control, and machine
    translating here would publish text nobody reviewed.
    """

    slug: str
    title: str
    description: str
    published: str
    updated: str
    kind: str
    tags: tuple[str, ...]
    sources: tuple[tuple[str, str, str], ...]
    body_en: str
    body_zh: str | None
    title_zh: str | None
    description_zh: str | None

    @property
    def path(self) -> str:
        return f"{BLOG_PATH}{self.slug}/"

    @property
    def canonical(self) -> str:
        return SITE_URL + self.path

    @property
    def translated(self) -> bool:
        return self.body_zh is not None


@dataclass(frozen=True)
class SiteChrome:
    """The masthead, section nav, and footer extracted from ``index.html``."""

    header: str
    navigation: str
    footer: str


def _region(dashboard_html: str, pattern: str, what: str) -> str:
    found = re.search(pattern, dashboard_html, re.S)
    if not found:
        raise ValueError(
            f"cannot extract the {what} from site/index.html: "
            "the dashboard source changed shape; update the blog chrome extractor"
        )
    return found.group(0)


def _strip_comments(fragment: str) -> str:
    without = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    return re.sub(r"\n[ \t]*\n", "\n", without)


def _drop_spa_attributes(fragment: str) -> str:
    # The CLI id stays on purpose: styles.css uses it to distinguish the dialog
    # trigger from dashboard view links.
    return re.sub(r'\s(?:data-view|aria-controls|aria-expanded)="[^"]*"', "", fragment)


def _ensure_outline_icon(inner: str) -> str:
    """Guarantee the first SVG in ``inner`` carries ``outline-icon``.

    Matches the class anywhere in the attribute so extra classes or a
    different attribute order do not look like a missing icon. If the SVG
    already has a class list, append; if it has none, add one.
    """
    svg = re.search(r"<svg\b([^>]*)>", inner)
    if not svg:
        raise ValueError("the contact button has no svg to carry outline-icon")
    attrs = svg.group(1)
    class_attr = re.search(r'\bclass="([^"]*)"', attrs)
    if class_attr:
        classes = class_attr.group(1).split()
        if "outline-icon" in classes:
            return inner
        replacement = f'class="{class_attr.group(1)} outline-icon"'
        tagged_attrs = attrs[: class_attr.start()] + replacement + attrs[class_attr.end() :]
    else:
        tagged_attrs = attrs + ' class="outline-icon"'
    return inner[: svg.start()] + f"<svg{tagged_attrs}>" + inner[svg.end() :]


def _today_link(button: str) -> str:
    view = re.search(r'data-view="([^"]*)"', button)
    label = re.sub(r"<[^>]+>", "", button).strip()
    if not view or view.group(1) not in _TODAY_HREFS or not label:
        raise ValueError(
            "the dashboard nav contains a button this extractor cannot turn "
            f"into a link: {button[:120]!r}"
        )
    href = _TODAY_HREFS[view.group(1)]
    return f'<a href="{href}" data-i18n="{esc(label)}">{esc(label)}</a>'


def _adapt_navigation(nav: str) -> str:
    nav = _strip_comments(nav)
    nav = re.sub(r"<button\b[^>]*>.*?</button>", lambda m: _today_link(m.group(0)), nav, flags=re.S)
    nav = _drop_spa_attributes(nav)
    # The blog's own entry is the current page everywhere the blog renders.
    marked = re.sub(
        r'<a href="' + BLOG_PATH + '"',
        f'<a class="nav-active" aria-current="page" href="{BLOG_PATH}"',
        nav,
    )
    if marked == nav:
        raise ValueError(
            "the dashboard nav no longer links to the blog at "
            f"{BLOG_PATH!r}; the blog pages cannot mark their section active"
        )
    return marked


def _adapt_header(header: str) -> str:
    header = _strip_comments(header)
    # Same host-relative rule as the section nav: the badge keeps the site
    # feed, but a local preview or mirror must not eject to the canonical
    # domain on click.
    header = header.replace(f'href="{SITE_URL}/feed.xml"', 'href="/feed.xml"', 1)
    contact = re.search(r'<button\b([^>]*\bid="badge-contact"[^>]*)>(.*?)</button>', header, re.S)
    if not contact:
        raise ValueError(
            "the dashboard masthead no longer carries the contact button; "
            "the blog chrome cannot link to /#contact"
        )
    attrs, inner = contact.group(1), contact.group(2)
    title = re.search(r'title="([^"]*)"', attrs)
    i18n_title = re.search(r'data-i18n-title="([^"]*)"', attrs)
    # The chat-bubble svg carries the outline-icon class from index.html. Ensure
    # it is present when the button is transformed into an anchor badge.
    inner = _ensure_outline_icon(inner)
    header = header.replace(
        contact.group(0),
        '<a class="repo-badge" href="/#contact" aria-haspopup="dialog"'
        + (f' title="{esc(title.group(1))}"' if title else "")
        + (f' data-i18n-title="{esc(i18n_title.group(1))}"' if i18n_title else "")
        + f">{inner}</a>",
        1,
    )
    return header


def _page_footer(footer: str, updated: str) -> str:
    stamped, count = re.subn(
        r'(<p id="build-meta">)Updated —(</p>)',
        rf'\g<1><span data-i18n="Updated">Updated</span> {esc(updated)}\g<2>',
        footer,
    )
    if count != 1:
        raise ValueError(
            "the dashboard footer no longer has the 'Updated —' placeholder; "
            "the blog pages cannot bake their build date"
        )
    return stamped


def extract_site_chrome(dashboard_html: str) -> SiteChrome:
    """Pull the shared masthead, nav, and footer out of ``site/index.html``."""
    header = _region(dashboard_html, r'<header class="masthead">.*?</header>', "masthead")
    navigation = _region(dashboard_html, r'<nav class="view-nav".*?</nav>', "section nav")
    footer = _region(dashboard_html, r"<footer>.*?</footer>", "footer")
    return SiteChrome(
        header=_adapt_header(header),
        navigation=_adapt_navigation(navigation),
        footer=_strip_comments(footer),
    )


def render_page(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    chrome: SiteChrome,
    updated: str,
    chrome_i18n: dict[str, str] | None = None,
    schemas: Iterable[dict[str, Any]] = (),
    og_type: str = "website",
) -> str:
    """Wrap one rendered body in the extracted site chrome."""
    schema_blocks = "".join(
        f'<script type="application/ld+json">{json_ld(payload)}</script>' for payload in schemas
    )
    i18n_block = (
        '<script type="application/json" id="chrome-i18n">'
        + json.dumps(chrome_i18n, ensure_ascii=False, sort_keys=True)
        + "</script>"
        if chrome_i18n
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(description)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<title>{esc(title)}</title>
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:site_name" content="Benchmark Radar">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{SITE_URL}/assets/og-card.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{SITE_URL}/assets/og-card.png">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="Benchmark Radar daily brief"
      href="{BLOG_FEED_PATH}">
<link rel="stylesheet" href="/assets/styles.css">
<link rel="stylesheet" href="/assets/blog.css">
{schema_blocks}
{i18n_block}
<script src="/assets/blog.js" defer></script>
</head>
<body class="blog-page">
<a class="skip-link" href="#main-content">Skip to content</a>
{chrome.header}
{chrome.navigation}
<main id="main-content" tabindex="-1"><div class="blog-view">{body}</div></main>
{_page_footer(chrome.footer, updated)}
</body>
</html>
"""
