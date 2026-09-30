"""Theme browse page: discovery records grouped by their source taxonomy.

Issue #380 part three. The XBsleepy digest tags each agent-benchmark paper
with capability themes, and ``fetch_xbsleepy`` carries them through as
``xbsleepy:``-prefixed categories. This page turns those tags into a
browsable index: pick a theme, see every tagged record, newest first. The
page renders whatever categories arrive rather than hardcoding a taxonomy,
so another source can join by prefixing its own categories.
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
    "No tagged records yet. The theme page fills in as tagged records "
    "arrive in the daily snapshots."
)

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


def build_theme_groups(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group every categorized record across snapshots by its category.

    Returns theme groups sorted by record count then name, each with its
    records newest first. Records without categories are the dashboard's
    job, not this page's.
    """
    groups: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for snapshot in snapshots:
        for item in _items_of(snapshot):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            categories = item.get("categories")
            if not title or not url or not isinstance(categories, list):
                continue
            source_id = str(item.get("source_id") or url)
            published = str(
                item.get("updated_at") or item.get("published_at") or snapshot.get("date") or ""
            )[:10]
            summary = " ".join(str(item.get("summary") or "").split())[:_SUMMARY_CLIP]
            for category in categories:
                tag = str(category).strip()
                if not tag:
                    continue
                key = (tag, source_id)
                if key in seen:
                    continue
                seen.add(key)
                group = groups.setdefault(
                    tag, {"category": tag, "count": 0, "records": []}
                )
                group["records"].append(
                    {
                        "source_id": source_id,
                        "title": title,
                        "url": url,
                        "source": str(item.get("source") or "").strip(),
                        "date": published,
                        "summary": summary,
                    }
                )
                group["count"] += 1
    ordered = sorted(groups.values(), key=lambda group: (-group["count"], group["category"]))
    for group in ordered:
        group["records"].sort(key=lambda record: record["date"], reverse=True)
    return ordered


def _record_card(record: dict[str, Any], *, hidden: bool = False) -> str:
    meta = " · ".join(part for part in (record["source"], record["date"]) if part)
    summary_text = " ".join(str(record.get("summary") or "").split())[:_SUMMARY_CLIP]
    summary = (
        f'<p class="theme-card-summary">{esc(summary_text)}</p>' if summary_text else ""
    )
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


def _themes_page(
    groups: list[dict[str, Any]],
    chrome: SiteChrome,
    chrome_i18n: dict[str, str],
    updated: str | None,
) -> str:
    total_records = len({row["source_id"] for group in groups for row in group["records"]})
    chips = "".join(
        f'<button type="button" class="theme-chip" data-target="theme-{_slug(group["category"])}">'
        f'{esc(group["category"])} <span class="n">{group["count"]}</span></button>'
        for group in groups
    )
    sections = []
    for group in groups:
        slug = _slug(group["category"])
        records = group["records"]
        cards = "".join(_record_card(record) for record in records[:_SLICE])
        more = ""
        if len(records) > _SLICE:
            cards += "".join(
                _record_card(record, hidden=True) for record in records[_SLICE:]
            )
            more = (
                f'<button type="button" class="theme-more" data-section="{slug}">'
                f"Show all {len(records)} records</button>"
            )
        sections.append(
            f'<section class="theme-section" id="theme-{slug}" data-slug="{slug}">'
            f"<header><h2>{esc(group['category'])}</h2>"
            f'<span class="theme-count">{group["count"]} records</span></header>'
            f'<div class="theme-grid">{cards}</div>{more}</section>'
        )
    body_sections = "".join(sections)
    empty = f'<div class="themes-empty">{esc(_EMPTY_STATE)}</div>' if not groups else ""
    body = f"""{_PAGE_STYLE}
<div class="themes-page">
  <h1>Browse benchmarks by theme</h1>
  <p class="themes-lede">Every discovery record that carries a source taxonomy tag,
  grouped for browsing. Tags arrive from the source that knows the record best —
  the XBsleepy digest's capability themes ride in as <code>xbsleepy:</code>
  categories, and other sources can join the same convention.</p>
  <p class="themes-lede-zh" lang="zh-Hans">按主题浏览带来源标签的记录，标签随来源自带。</p>
  <div class="themes-toolbar">
    <label class="themes-filter">
      <span class="visually-hidden">Filter records by title or summary</span>
      <input id="theme-filter" type="search" placeholder="Filter by title, source, summary…"
        autocomplete="off">
    </label>
    {chips}
  </div>
  {body_sections}
  {empty}
</div>
<script>
(() => {{
  const filter = document.getElementById("theme-filter");
  const sections = Array.from(document.querySelectorAll(".theme-section"));
  const chips = Array.from(document.querySelectorAll(".theme-chip"));

  sections.forEach((section) => {{
    const grid = section.querySelector(".theme-grid");
    const extra = Array.from(grid.querySelectorAll(".theme-card[hidden]"));
    const button = section.querySelector(".theme-more");
    if (!button || !extra.length) return;
    button.addEventListener("click", () => {{
      extra.forEach((card) => card.removeAttribute("hidden"));
      button.remove();
    }});
  }});

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
    schemas = [
        webpage_schema(
            title="Browse benchmarks by theme | Benchmark Radar",
            description="Discovery records grouped by their source taxonomy themes.",
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
        title="Browse benchmarks by theme | Benchmark Radar",
        description=(
            "Discovery records grouped by their source taxonomy themes — "
            f"{total_records} records across {len(groups)} themes."
        ),
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
    groups = build_theme_groups(snapshots)
    updated = next(
        (group["records"][0]["date"] for group in groups if group["records"]), None
    )
    page = _themes_page(groups, chrome, chrome_i18n, updated)
    output_dir = site_dir / "themes"
    staging = site_dir / "themes.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(page, encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    total_records = len({row["source_id"] for group in groups for row in group["records"]})
    return {
        "path": THEMES_PATH,
        "categories": len(groups),
        "records": total_records,
        "sitemap_entries": [(THEMES_PATH, updated)],
    }
