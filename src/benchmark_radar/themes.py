"""Theme browse page: discovery records grouped by the themes their source tagged.

Issue #380 part three. The XBsleepy digest classifies each agent-benchmark paper
by capability theme, and ``fetch_xbsleepy`` carries those through in
``RadarItem.source_tags``, namespaced by source. This page renders that
classification: pick a theme, see every record carrying it, newest first. It
groups whatever tags arrive rather than hardcoding a taxonomy, so another source
joins by namespacing its own.

The population is the daily discovery snapshots, not the benchmark catalog in
``benchmark-index.json``. It answers "what themes are arriving" rather than "how
many benchmarks does the product cover", so it states no catalog count and must
not be read as one (``principle.md``). Every record it is built from stays
accounted for on the page: records no source has themed yet are listed under
their own heading instead of being dropped.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .blog_shell import (
    SiteChrome,
    chrome_i18n_table,
    extract_site_chrome,
    render_page,
)
from .feed import SITE_URL
from .site_shell import breadcrumb_schema, esc, webpage_schema

THEMES_PATH = "/themes/"

_SUMMARY_CLIP = 220

_EMPTY_STATE = (
    "No source has tagged a record with a theme yet. The themes fill in as "
    "tagged records arrive in the daily snapshots; everything collected so far "
    "is listed under “No theme tag yet” below."
)

# Records no source has themed. Shown rather than dropped so the page accounts
# for every record it was built from.
_UNTHEMED = "No theme tag yet"

# Sections render the first slice of their grid and hand the rest to a
# "show all" control -- a theme with several thousand records must not paint
# them all before a reader scrolls past the first screen.
_SLICE = 60

_PAGE_STYLE = """
<style>
.themes-page{max-width:72rem;margin:0 auto;padding:1.2rem 0 3rem}
.themes-page h1{font-size:clamp(1.5rem,3vw,2rem);margin:.2rem 0 .5rem}
.themes-lede{color:var(--muted);margin:.3rem 0;max-width:52rem}
.themes-lede-zh{color:var(--muted);font-size:.92rem;margin:.2rem 0 0}
.themes-ledger{color:var(--muted);font-size:.85rem;margin:.4rem 0 0}
.themes-toolbar{position:sticky;top:.6rem;z-index:5;display:flex;flex-wrap:wrap;
  gap:.5rem;align-items:center;background:var(--panel);border:1px solid var(--edge);
  border-radius:var(--radius);padding:.7rem .8rem;margin:1.1rem 0 1.3rem;
  box-shadow:0 2px 10px rgba(21,36,42,.06)}
.themes-filter{flex:1 1 15rem}
.themes-filter input{width:100%;padding:.55rem .75rem;border:1px solid var(--ink);
  border-radius:var(--radius-sm);background:var(--canvas,#fff);color:var(--ink);font:inherit}
.theme-chip{border:1px solid var(--edge);border-radius:999px;background:var(--panel);
  color:var(--ink);padding:.32rem .7rem;font:inherit;font-size:.82rem;cursor:pointer}
.theme-chip:hover{border-color:var(--ink)}
.theme-chip.active{background:var(--ink);color:var(--panel);border-color:var(--ink)}
.theme-chip .n{opacity:.65;font-size:.78rem}
.theme-section{margin:1.6rem 0}
.theme-section>header{display:flex;align-items:baseline;gap:.5rem;margin:0 0 .7rem}
.theme-section h2{font-size:1.1rem;margin:0}
.theme-count{color:var(--muted);font-size:.85rem}
.theme-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(19rem,1fr));gap:.7rem}
.theme-card{display:flex;flex-direction:column;gap:.3rem;background:var(--panel);
  border:1px solid var(--edge);border-radius:var(--radius);padding:.75rem .85rem}
.theme-card-title{color:var(--ink);font-weight:600;text-decoration:none;line-height:1.35}
.theme-card-title:hover{text-decoration:underline}
.theme-card-meta{font-size:.78rem;color:var(--muted)}
.theme-card-summary{margin:0;font-size:.87rem}
.theme-more{margin-top:.7rem;border:1px solid var(--edge);border-radius:var(--radius-sm);
  background:var(--panel);color:var(--ink);padding:.4rem .8rem;font:inherit;
  font-size:.85rem;cursor:pointer}
.theme-more:hover{border-color:var(--ink)}
.themes-empty{background:var(--panel);border:1px solid var(--edge);
  border-radius:var(--radius);padding:1.2rem;margin:1.4rem 0}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap}
.hidden-by-filter{display:none!important}
</style>
"""


def _items_of(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    # Schema v1 stored discovery records under "items"; v2 renamed them to
    # "evidence_items". write_blog consumes the same mixed list, so the page
    # must read both instead of assuming one.
    for key in ("evidence_items", "items"):
        value = snapshot.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def build_theme_index(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Group every discovery record by the source theme tags it carries.

    Returns the theme groups ordered by record count then name, the records no
    source has themed, and the accounting the page states: distinct records
    read, and how many of those carry at least one theme tag.

    A record is identified by ``(source, source_id)``. Source ids are only
    unique within the source that minted them, so keying on the id alone merges
    two sources' different records into one. The same record recurs across
    daily snapshots; the newest copy supplies the displayed date and summary.
    """
    newest: dict[tuple[str, str], dict[str, Any]] = {}
    members: dict[str, set[tuple[str, str]]] = {}
    tagged: set[tuple[str, str]] = set()

    for snapshot in snapshots:
        for item in _items_of(snapshot):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title or not url:
                continue
            identity = (str(item.get("source") or "").strip(), str(item.get("source_id") or url))
            record = {
                "source": identity[0],
                "source_id": identity[1],
                "title": title,
                "url": url,
                "date": str(
                    item.get("updated_at") or item.get("published_at") or snapshot.get("date") or ""
                )[:10],
                "summary": " ".join(str(item.get("summary") or "").split())[:_SUMMARY_CLIP],
            }
            previous = newest.get(identity)
            if previous is None or record["date"] > previous["date"]:
                newest[identity] = record
            tags = item.get("source_tags")
            if not isinstance(tags, list):
                continue
            for raw_tag in tags:
                tag = str(raw_tag).strip()
                if tag:
                    members.setdefault(tag, set()).add(identity)
                    tagged.add(identity)

    def _ordered(identities: set[tuple[str, str]]) -> list[dict[str, Any]]:
        return sorted(
            (newest[identity] for identity in identities),
            key=lambda row: (row["date"], row["title"]),
            reverse=True,
        )

    groups = [
        {"category": tag, "count": len(identities), "records": _ordered(identities)}
        for tag, identities in sorted(members.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]
    unthemed = _ordered(set(newest) - tagged)
    return {
        "groups": groups,
        "unthemed": unthemed,
        "records": len(newest),
        "tagged": len(tagged),
    }


def _record_card(record: dict[str, Any], *, hidden: bool = False) -> str:
    meta = " · ".join(part for part in (record["source"], record["date"]) if part)
    summary_text = " ".join(str(record.get("summary") or "").split())[:_SUMMARY_CLIP]
    summary = f'<p class="theme-card-summary">{esc(summary_text)}</p>' if summary_text else ""
    hidden_attr = " hidden" if hidden else ""
    return (
        f'<article class="theme-card"{hidden_attr}>'
        f'<a class="theme-card-title" href="{esc(record["url"])}">{esc(record["title"])}</a>'
        f'<p class="theme-card-meta">{esc(meta)}</p>'
        f"{summary}"
        f"</article>"
    )


def _slug(category: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in category).strip("-")


def _section(category: str, records: list[dict[str, Any]]) -> str:
    slug = _slug(category)
    cards = "".join(_record_card(record) for record in records[:_SLICE])
    more = ""
    if len(records) > _SLICE:
        cards += "".join(_record_card(record, hidden=True) for record in records[_SLICE:])
        more = f'<button type="button" class="theme-more">Show all {len(records)} records</button>'
    return (
        f'<section class="theme-section" id="theme-{slug}" data-slug="{slug}">'
        f"<header><h2>{esc(category)}</h2>"
        f'<span class="theme-count">{len(records)} records</span></header>'
        f'<div class="theme-grid">{cards}</div>{more}</section>'
    )


def _themes_page(
    index: dict[str, Any],
    chrome: SiteChrome,
    chrome_i18n: dict[str, str],
    updated: str | None,
) -> str:
    groups = index["groups"]
    unthemed = index["unthemed"]
    sections = [_section(group["category"], group["records"]) for group in groups]
    chips = "".join(
        f'<button type="button" class="theme-chip" data-target="{_slug(group["category"])}">'
        f'{esc(group["category"])} <span class="n">{group["count"]}</span></button>'
        for group in groups
    )
    if unthemed:
        sections.append(_section(_UNTHEMED, unthemed))
        chips += (
            f'<button type="button" class="theme-chip" data-target="{_slug(_UNTHEMED)}">'
            f'{esc(_UNTHEMED)} <span class="n">{len(unthemed)}</span></button>'
        )
    empty = f'<div class="themes-empty">{esc(_EMPTY_STATE)}</div>' if not groups else ""
    ledger = (
        f"{index['records']} discovery records read from the daily snapshots: "
        f"{index['tagged']} carry a source theme tag, {len(unthemed)} do not."
    )
    body = f"""{_PAGE_STYLE}
<div class="themes-page">
  <h1>Browse new arrivals by theme</h1>
  <p class="themes-lede">What the radar's daily discovery keeps finding, grouped by the
  capability theme each record's own source gave it. Tags come from the source that knows
  the record best — the XBsleepy digest's capability themes ride in namespaced as
  <code>xbsleepy:</code>, and any source can join the same convention. This is a view over
  newly discovered papers, repositories and datasets, not a count of the benchmark
  catalog.</p>
  <p class="themes-lede-zh" lang="zh-Hans">按来源自带的能力主题浏览每日新发现的记录，
  不是 benchmark 目录的计数。</p>
  <p class="themes-ledger">{esc(ledger)}</p>
  <div class="themes-toolbar">
    <label class="themes-filter">
      <span class="visually-hidden">Filter records by title or summary</span>
      <input id="theme-filter" type="search" placeholder="Filter by title, source, summary…"
        autocomplete="off">
    </label>
    {chips}
  </div>
  {"".join(sections)}
  {empty}
</div>
<script>
(() => {{
  const filter = document.getElementById("theme-filter");
  const sections = Array.from(document.querySelectorAll(".theme-section"));
  const chips = Array.from(document.querySelectorAll(".theme-chip"));

  sections.forEach((section) => {{
    const extra = Array.from(section.querySelectorAll(".theme-card[hidden]"));
    const button = section.querySelector(".theme-more");
    if (!button || !extra.length) return;
    button.addEventListener("click", () => {{
      extra.forEach((card) => card.removeAttribute("hidden"));
      button.remove();
    }});
  }});

  // Chips pin by the section's own slug. They used to carry a "theme-" prefix
  // the sections did not, so no slug ever matched and one click hid every
  // section on the page.
  let pinned = null;
  chips.forEach((chip) => {{
    chip.addEventListener("click", () => {{
      const target = chip.dataset.target;
      if (pinned === target) {{
        pinned = null;
        chips.forEach((c) => c.classList.remove("active"));
        sections.forEach((s) => s.classList.remove("hidden-by-filter"));
        return;
      }}
      pinned = target;
      chips.forEach((c) => c.classList.toggle("active", c === chip));
      sections.forEach((s) => s.classList.toggle("hidden-by-filter", s.dataset.slug !== target));
      applyFilter();
      window.scrollTo({{ top: 0, behavior: "smooth" }});
    }});
  }});

  function applyFilter() {{
    const query = (filter.value || "").trim().toLowerCase();
    sections.forEach((section) => {{
      if (pinned && section.dataset.slug !== pinned) return;
      let visible = 0;
      section.querySelectorAll(".theme-card").forEach((card) => {{
        const hidden = Boolean(query) && !card.textContent.toLowerCase().includes(query);
        card.classList.toggle("hidden-by-filter", hidden);
        if (!hidden) visible += 1;
      }});
      section.classList.toggle("hidden-by-filter", Boolean(query) && visible === 0);
      const more = section.querySelector(".theme-more");
      if (query && more) more.click();
    }});
  }}
  if (filter) filter.addEventListener("input", applyFilter);
}})();
</script>"""
    canonical = f"{SITE_URL}{THEMES_PATH}"
    title = "Browse new arrivals by theme | Benchmark Radar"
    description = (
        "Daily discovery records grouped by the capability themes their own source "
        f"tagged — {index['tagged']} of {index['records']} records across "
        f"{len(groups)} themes."
    )
    schemas = [
        webpage_schema(
            title=title,
            description="Discovery records grouped by their source's own theme tags.",
            canonical=canonical,
            languages=("en", "zh-Hans"),
        ),
        breadcrumb_schema(
            ("Benchmark Radar", f"{SITE_URL}/"),
            ("Themes", canonical),
            canonical=canonical,
        ),
    ]
    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        body=body,
        chrome=chrome,
        updated=updated,
        chrome_i18n=chrome_i18n,
        schemas=schemas,
    )


def write_themes(
    snapshots: list[dict[str, Any]],
    site_dir: Path,
    *,
    dashboard_html: str | None = None,
    app_js: str | None = None,
) -> dict[str, Any]:
    """Write the theme browse page atomically and report what it published.

    The chrome is extracted from the committed dashboard source for the same
    reason the blog's is: one masthead, nav, and footer rather than two
    drifting copies. ``extract_site_chrome`` requires the dashboard footer to
    link ``/themes/``, so a page cannot claim a section the site does not
    have. Tests pass both sources explicitly; the defaults read the committed
    files beside the output directory.
    """
    if dashboard_html is None:
        dashboard_source = site_dir / "index.html"
        if not dashboard_source.is_file():
            raise FileNotFoundError(
                "the themes chrome is extracted from the committed dashboard "
                f"source, which is missing at {dashboard_source}"
            )
        dashboard_html = dashboard_source.read_text(encoding="utf-8")
    if app_js is None:
        app_js_source = site_dir / "assets" / "app.js"
        if not app_js_source.is_file():
            raise FileNotFoundError(
                "the themes chrome translations are baked from the committed "
                f"app.js, which is missing at {app_js_source}"
            )
        app_js = app_js_source.read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard_html, active_path=THEMES_PATH)
    chrome_i18n = chrome_i18n_table(chrome, app_js)
    index = build_theme_index(snapshots)
    newest = next(
        (
            group["records"][0]["date"]
            for group in sorted(
                [*index["groups"], {"records": index["unthemed"]}],
                key=lambda group: len(group["records"]),
                reverse=True,
            )
            if group["records"]
        ),
        None,
    )
    page = _themes_page(index, chrome, chrome_i18n, newest)
    output_dir = site_dir / "themes"
    staging = site_dir / "themes.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(page, encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    return {
        "path": THEMES_PATH,
        "categories": len(index["groups"]),
        "records": index["records"],
        "tagged": index["tagged"],
        "unthemed": len(index["unthemed"]),
        "sitemap_entries": [(THEMES_PATH, newest)],
    }
