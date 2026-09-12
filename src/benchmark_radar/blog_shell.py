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
    """The masthead and footer extracted from ``index.html``."""

    header: str
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


def _mark_active(html: str, active_path: str) -> tuple[str, bool]:
    """Mark the link to ``active_path`` as the current page, if this region has it.

    The dashboard writes an anchor's attributes across several lines once it
    carries more than a couple of them, so href is matched after any run of
    whitespace rather than after a single space.
    """
    marked, count = re.subn(
        r'<a\s+href="' + re.escape(active_path) + '"',
        f'<a class="nav-active" aria-current="page" href="{active_path}"',
        html,
        count=1,
    )
    return marked, count == 1


def _adapt_navigation(nav: str, active_path: str) -> tuple[str, bool]:
    nav = _strip_comments(nav)
    nav = re.sub(r"<button\b[^>]*>.*?</button>", lambda m: _today_link(m.group(0)), nav, flags=re.S)
    nav = _drop_spa_attributes(nav)
    # Whichever section this page belongs to is the current one everywhere it
    # renders, so the chrome marks it rather than the page patching the nav back.
    # A miss is not an error here: documents like /blog/ and /about/ are linked
    # from the footer nav instead, so the caller is told and checks there too.
    return _mark_active(nav, active_path)


def _adapt_header(header: str, active_path: str) -> tuple[str, bool]:
    header = _strip_comments(header)
    navigation = _region(header, r'<nav class="view-nav".*?</nav>', "section nav")
    marked, in_nav = _adapt_navigation(navigation, active_path)
    header = header.replace(navigation, marked, 1)
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
    return header, in_nav


def _page_footer(footer: str, updated: str | None) -> str:
    """Bake the build date into the dashboard footer's placeholder.

    ``updated`` is None when the corpus has no history to date the build by.
    The whole line is then dropped rather than left half-written: a footer
    reading "Updated" with nothing after it claims a date the build lacks.
    """
    replacement = (
        rf'\g<1><span data-i18n="Updated">Updated</span> {esc(updated)}\g<2>' if updated else ""
    )
    stamped, count = re.subn(
        r'(<p id="build-meta">)Updated —(</p>)',
        replacement,
        footer,
    )
    if count != 1:
        raise ValueError(
            "the dashboard footer no longer has the 'Updated —' placeholder; "
            "the blog pages cannot bake their build date"
        )
    return stamped


def extract_site_chrome(dashboard_html: str, *, active_path: str = BLOG_PATH) -> SiteChrome:
    """Pull the shared masthead and footer out of ``site/index.html``.

    ``active_path`` is the nav entry this page belongs under. It must be a link
    the dashboard already carries, in the view row or in the footer's document
    nav, so a standalone page cannot claim a section the site does not have.
    """
    header = _region(dashboard_html, r'<header class="masthead">.*?</header>', "masthead")
    footer = _region(dashboard_html, r"<footer>.*?</footer>", "footer")
    header, in_nav = _adapt_header(header, active_path)
    footer, in_footer = _mark_active(_strip_comments(footer), active_path)
    if not in_nav and not in_footer:
        raise ValueError(
            "the dashboard no longer links to "
            f"{active_path!r} from its view row or its footer nav; "
            "pages in that section cannot mark it active"
        )
    return SiteChrome(header=header, footer=footer)


# The dashboard's toggle and star count translate these at runtime; the
# chrome's own data-i18n keys cover everything else.
_TOGGLE_I18N_KEYS = ("Switch to Chinese (中文)", "Switch to English")
_BADGE_I18N_KEYS = ("Star this repository on GitHub. {count} stars",)
# The footer's build date prefix is baked in per page, after the keys were
# collected from the raw extracted chrome, so it is listed here.
_FOOTER_I18N_KEYS = ("Updated",)


def parse_zh_table(app_js: str) -> dict[str, str]:
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


def chrome_i18n_table(chrome: SiteChrome, app_js: str) -> dict[str, str]:
    """Bake the reviewed zh subset the chrome needs from app.js's I18N table.

    The dashboard translates its chrome in place from the same table; the blog
    has no app.js, so the needed entries ship with the page and blog.js applies
    them with the same contract. Keys come from the chrome itself, so a new
    badge or nav label is covered without touching this function.
    """
    chrome_html = chrome.header + chrome.footer
    keys = set(re.findall(r'data-i18n(?:-title|-aria)?="([^"]+)"', chrome_html))
    keys.update(_TOGGLE_I18N_KEYS)
    keys.update(_BADGE_I18N_KEYS)
    keys.update(_FOOTER_I18N_KEYS)
    table = parse_zh_table(app_js)
    # Keys the table does not carry (short nav labels like Blog and Trends)
    # stay English on the dashboard too — t() falls back to the key itself —
    # so the blog mirrors that instead of inventing translations.
    return {key: table[key] for key in sorted(keys) if key in table}


def render_page(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    chrome: SiteChrome,
    updated: str | None,
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
<main id="main-content" tabindex="-1"><div class="blog-view">{body}</div></main>
{_page_footer(chrome.footer, updated)}
</body>
</html>
"""
