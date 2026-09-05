"""Static per-benchmark pages: one crawlable URL per benchmark (issue #424).

The dashboard provides collection-level views, while each catalog benchmark
still needs its own crawlable URL. Each per-benchmark shard already answers the
reader's questions about one benchmark, but only as JSON consumed by
JavaScript. This module renders that same evidence as plain HTML, one page per
slug, readable with JavaScript disabled. Every benchmark gets its own title,
description, canonical URL, and structured data, and the sitemap publishes all
of them.

The pages derive from the shards exactly as the shards derive from the crawl
CSVs, so they are generated and gitignored, never committed. The build calls
this right after `normalize-external` writes the shards, and the sitemap build
scans the same shard directory for the URLs to list. A page never invents
values: missing fields are omitted from the HTML, never shown as a zero, an
empty string, or the literal word for a missing value. Scores stay partitioned
by the source that reported them, the same rule the shards enforce in JSON.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from .feed import SITE_URL

DEFAULT_SHARD_DIR = Path("site/data/benchmarks")
DEFAULT_PAGES_DIR = Path("site/benchmarks")

_DESCRIPTION_LIMIT = 155

_DIR_DESCRIPTION = (
    "Every benchmark in the Benchmark Radar catalog, each with its own page "
    "covering what it tests, who published it, and which scores are on record."
)

_BENCH_CSS = """\
:root { color-scheme: light; --ink: #15242a; --muted: #5f7078; --line: #bdc9ce; }
body { margin: 0; font-family: Avenir Next, Avenir, Segoe UI, sans-serif;
  color: var(--ink); line-height: 1.55; }
nav.site { padding: 1rem max(1rem, calc((100% - 900px) / 2));
  border-bottom: 1px solid var(--line); display: flex; gap: 1rem; flex-wrap: wrap; }
main { max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }
h1 { font-size: 2rem; margin: 0.25rem 0 0.5rem; }
.lede { color: var(--muted); font-size: 1.05rem; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.4rem 1rem;
  margin: 1.5rem 0; }
dt { font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin: 0.75rem 0 1.5rem;
  font-size: 0.95rem; }
th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--line); }
th { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--muted); }
.caveat { color: var(--muted); font-size: 0.9rem; }
"""

_DIR_CSS = """\
:root { color-scheme: light; --ink: #15242a; --line: #bdc9ce; }
body { margin: 0; font-family: Avenir Next, Avenir, Segoe UI, sans-serif;
  color: var(--ink); line-height: 1.55; }
nav.site { padding: 1rem max(1rem, calc((100% - 900px) / 2));
  border-bottom: 1px solid var(--line); display: flex; gap: 1rem; flex-wrap: wrap; }
main { max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }
ul { columns: 3; gap: 0.5rem 2rem; padding: 0; list-style: none; }
li { break-inside: avoid; margin: 0.2rem 0; }
@media (max-width: 700px) { ul { columns: 1; } }
"""


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _text(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _description(record: dict[str, Any]) -> str:
    """A human sentence for the page, never empty, at most one line.

    The shard's own description wins when it exists. Otherwise the fallback is
    assembled from fields the record actually carries, so two benchmarks with
    nothing but a name do not share identical copy.
    """
    raw = record.get("description") or {}
    own = raw.get("en")
    if isinstance(own, str) and own.strip():
        text = own.strip().replace("\n", " ")
    else:
        name = _text(record, "name") or "This benchmark"
        parts = [name]
        categories = record.get("categories") or []
        if categories:
            parts.append(f"covers {', '.join(str(c) for c in categories)}")
        source = _text(record, "source")
        if source:
            parts.append(f"with evidence collected daily by Benchmark Radar from {source}")
        else:
            parts.append("with evidence collected daily by Benchmark Radar")
        text = ", ".join(parts)
    if len(text) <= _DESCRIPTION_LIMIT:
        return text
    return text[:_DESCRIPTION_LIMIT].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _canonical(slug: str) -> str:
    return f"{SITE_URL}/benchmarks/{slug}/"


def _facts(record: dict[str, Any], scores_by_source: dict[str, Any]) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    publisher = _text(record, "publisher")
    if publisher:
        facts.append(("Publisher", publisher))
    released = _text(record, "released")
    if released:
        facts.append(("Released", released))
    modality = _text(record, "modality")
    if modality:
        facts.append(("Modality", modality))
    categories = record.get("categories") or []
    if categories:
        facts.append(("Categories", ", ".join(str(c) for c in categories)))
    openness = record.get("openness") or {}
    status = openness.get("status")
    if isinstance(status, str) and status:
        facts.append(("Openness", status))
    source = _text(record, "source")
    if source:
        facts.append(("Source", source))
    score_count = sum(
        len(source_data.get("rows") or []) for source_data in scores_by_source.values()
    )
    facts.append(("Reported scores", str(score_count)))
    return facts


def _json_ld(payload: dict[str, Any]) -> str:
    """Serialize structured data for a <script> block.

    JSON may legally contain the substring `</`, which would close the script
    tag early no matter how valid the JSON is. Escaping the slash keeps the
    block intact and is valid JSON for every consumer.
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def _webpage_jsonld(slug: str, name: str, description: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": _canonical(slug),
        "name": f"{name} · Benchmark Radar",
        "url": _canonical(slug),
        "description": description,
        "inLanguage": ["en", "zh-Hans"],
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "about": {"@type": "Thing", "name": name, "description": description},
    }
    return _json_ld(payload)


def _breadcrumb_jsonld(slug: str, name: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "@id": f"{_canonical(slug)}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Benchmark Radar", "item": f"{SITE_URL}/"},
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Benchmark directory",
                "item": f"{SITE_URL}/benchmarks/",
            },
            {"@type": "ListItem", "position": 3, "name": name, "item": _canonical(slug)},
        ],
    }
    return _json_ld(payload)


def _cell(*candidates: Any) -> str:
    for candidate in candidates:
        if candidate is not None and candidate != "":
            return _esc(str(candidate))
    return "—"


def _scores_sections(scores_by_source: dict[str, Any]) -> str:
    sections: list[str] = []
    for source in sorted(scores_by_source):
        rows = sorted(
            (scores_by_source[source].get("rows") or []),
            key=lambda row: (
                str(row.get("model_name") or "").lower(),
                str(row.get("reported_date") or ""),
            ),
        )
        body = "".join(
            "<tr>"
            f"<td>{_cell(row.get('model_name'), row.get('model_id'))}</td>"
            f"<td>{_cell(row.get('organization'))}</td>"
            f"<td>{_cell(row.get('raw_value'), row.get('value'))}</td>"
            f"<td>{_cell(row.get('reported_date'))}</td>"
            f'<td><a href="{_esc(str(row.get("source_url") or SITE_URL))}">evidence</a></td>'
            "</tr>"
            for row in rows
        )
        if not body:
            continue
        sections.append(
            "<section>"
            f"<h2>{_esc(source)}</h2>"
            "<table><thead><tr><th>Model</th><th>Organization</th>"
            "<th>Reported value</th><th>Reported</th><th>Evidence</th></tr></thead>"
            f"<tbody>{body}</tbody></table></section>"
        )
    return "".join(sections)


def _benchmark_nav(interactive: str) -> str:
    return (
        '<nav class="site">'
        f'<a href="{SITE_URL}/">Benchmark Radar</a> '
        f'<a href="{SITE_URL}/benchmarks/">Benchmark directory</a> '
        f'<a href="{interactive}">Interactive view</a></nav>'
    )


def _page_html(slug: str, shard: dict[str, Any]) -> str:
    record = shard.get("record") or {}
    scores_by_source = shard.get("scores_by_source") or {}
    name = _text(record, "name") or slug
    description = _description(record)
    canonical = _canonical(slug)
    title = f"{name} · Benchmark Radar"
    facts = "".join(
        f"<dt>{_esc(label)}</dt><dd>{_esc(value)}</dd>"
        for label, value in _facts(record, scores_by_source)
    )
    scores = _scores_sections(scores_by_source)
    if scores:
        scores_html = (
            f"<section><h2>Reported scores</h2>{scores}</section>"
            '<p class="caveat">Scores are partitioned by the source that reported '
            "them and are never merged into a single cross-source ranking, because "
            "the sources measure different things and say so.</p>"
        )
    else:
        scores_html = (
            '<p class="caveat">No reported scores are on record for this benchmark yet.</p>'
        )
    interactive = f"{SITE_URL}/leaderboard/?lfrontier={slug}"
    nav = _benchmark_nav(interactive)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{_esc(description)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<title>{_esc(title)}</title>
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Benchmark Radar">
<meta property="og:title" content="{_esc(title)}">
<meta property="og:description" content="{_esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE_URL}/assets/og-card.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{_webpage_jsonld(slug, name, description)}</script>
<script type="application/ld+json">{_breadcrumb_jsonld(slug, name)}</script>
<style>{_BENCH_CSS}</style>
</head>
<body>
{nav}
<main>
  <p class="eyebrow">Benchmark</p>
  <h1>{_esc(name)}</h1>
  <p class="lede">{_esc(description)}</p>
  <dl>{facts}</dl>
  {scores_html}
</main>
{nav}
</body>
</html>
"""


def _directory_html(entries: list[tuple[str, str]]) -> str:
    """Directory page: title, canonical, schema, and the full listing."""
    canonical = f"{SITE_URL}/benchmarks/"
    payload = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": canonical,
        "name": "Benchmark directory · Benchmark Radar",
        "url": canonical,
        "description": _DIR_DESCRIPTION,
        "inLanguage": ["en", "zh-Hans"],
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Benchmark Radar", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Benchmark directory", "item": canonical},
        ],
    }
    links = "".join(f'<li><a href="{_esc(url)}">{_esc(name)}</a></li>' for name, url in entries)
    count = f"{len(entries)} benchmarks"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{_esc(_DIR_DESCRIPTION)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<title>Benchmark directory · Benchmark Radar</title>
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Benchmark Radar">
<meta property="og:title" content="Benchmark directory · Benchmark Radar">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE_URL}/assets/og-card.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{_json_ld(payload)}</script>
<script type="application/ld+json">{_json_ld(breadcrumb)}</script>
<style>{_DIR_CSS}</style>
</head>
<body>
<nav class="site">
  <a href="{SITE_URL}/">Benchmark Radar</a>
  <a href="{SITE_URL}/benchmarks/">Benchmark directory</a>
</nav>
<main>
  <h1>Benchmark directory</h1>
  <p class="lede">Every benchmark in the catalog, each with its own page covering
    what it tests, who published it, and which scores are on record. The
    interactive dashboard is <a href="{SITE_URL}/leaderboard/">here</a>.</p>
  <p class="count">{count}</p>
  <ul>{links}</ul>
</main>
</body>
</html>
"""


def _load_shard(path: Path) -> tuple[str, dict[str, Any]]:
    shard = json.loads(path.read_text(encoding="utf-8"))
    record = shard.get("record") or {}
    slug = record.get("slug")
    if (
        not isinstance(slug, str)
        or not slug
        or slug in {".", ".."}
        or any(ch in slug for ch in "/\\")
    ):
        raise ValueError(f"unsafe slug in {path.name}")
    return slug, shard


def benchmark_slugs(shard_dir: Path) -> list[str]:
    """Stable sorted slugs of every shard, for the sitemap."""
    if not shard_dir.is_dir():
        return []
    return sorted(path.stem for path in shard_dir.glob("*.json"))


def benchmark_page_urls(shard_dir: Path) -> list[str]:
    """Canonical benchmark page URLs in stable slug order."""
    return [_canonical(slug) for slug in benchmark_slugs(shard_dir)]


def write_benchmark_pages(
    shard_dir: Path = DEFAULT_SHARD_DIR,
    output_dir: Path = DEFAULT_PAGES_DIR,
) -> dict[str, Any]:
    """Render one static page per shard plus the directory page, atomically.

    Fails loudly when the shard directory is missing or empty: an empty build
    must never silently wipe the published benchmark pages.
    """
    if not shard_dir.is_dir():
        raise FileNotFoundError(
            f"{shard_dir} holds no benchmark shards; run `benchmark-radar normalize-external` first"
        )
    shard_paths = sorted(shard_dir.glob("*.json"))
    if not shard_paths:
        raise ValueError(f"{shard_dir} holds no benchmark shards; refusing to write empty pages")

    staging = output_dir.with_name(output_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    entries: list[tuple[str, str]] = []
    for path in shard_paths:
        slug, shard = _load_shard(path)
        page_dir = staging / slug
        page_dir.mkdir(parents=True)
        (page_dir / "index.html").write_text(_page_html(slug, shard), encoding="utf-8")
        name = _text(shard.get("record") or {}, "name") or slug
        entries.append((name, _canonical(slug)))

    entries.sort(key=lambda item: (item[0].lower(), item[1]))
    (staging / "index.html").write_text(_directory_html(entries), encoding="utf-8")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    return {"page_count": len(shard_paths), "output_dir": output_dir}
