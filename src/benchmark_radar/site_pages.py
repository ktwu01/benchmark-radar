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
this right after `normalize-catalog` writes the shards, and the sitemap build
scans the same shard directory for the URLs to list. A page never invents
values: missing fields are omitted from the HTML, never shown as a zero, an
empty string, or the literal word for a missing value. Scores stay partitioned
by the source that reported them, the same rule the shards enforce in JSON.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .feed import SITE_URL
from .site_shell import SOURCE_LABELS, website_reference

DEFAULT_SHARD_DIR = Path("site/data/benchmarks")
DEFAULT_PAGES_DIR = Path("site/benchmarks")

# Lowercase, digits, and the two separators the shard writers use. Nothing
# else has ever appeared in a slug, and nothing else is safe in a URL.
_SAFE_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]*")

_DESCRIPTION_LIMIT = 160

# A reader looking for a benchmark rarely searches the catalog's name for it.
# They search the benchmark plus the artifact they need: "GPQA paper", "SWE-bench
# dataset", "OSWorld results". These are the artifact kinds the records carry,
# in the order a title lists them, with the words those searches actually use.
_ARTIFACT_ORDER = ("paper", "repo", "dataset", "website")
_ARTIFACT_LABELS = {
    "paper": "Paper",
    "repo": "Code",
    "dataset": "Dataset",
    "website": "Website",
}
# A website link is a real artifact but not a search intent of its own, so it is
# listed on the page and left out of the title.
_TITLE_FACETS = ("paper", "repo", "dataset")
_RELATED_LIMIT = 8
_DOCUMENT_LIMIT = 12

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
h2 { font-size: 1.25rem; margin: 2rem 0 0.5rem; }
h3 { font-size: 1rem; margin: 1.25rem 0 0.25rem; }
ul.links { list-style: none; padding: 0; }
ul.links li { padding: 0.3rem 0; border-bottom: 1px solid var(--line); word-break: break-word; }
.artifact-kind { display: inline-block; min-width: 5rem; font-weight: 600; }
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


@dataclass(frozen=True)
class CatalogContext:
    """What one page can only know by looking at the whole catalog.

    Two things need it. A name shared by several sources needs the source in its
    title, or 121 names in this catalog publish pages that claim to be each
    other. And a page cannot link to its neighbours without knowing who they
    are, which is the internal linking that lets a crawler reach a benchmark
    nobody links to from outside.
    """

    shared_names: frozenset[str] = frozenset()
    by_category: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)


def _source_label(record: dict[str, Any]) -> str | None:
    source = _text(record, "source")
    if not source:
        return None
    return SOURCE_LABELS.get(source, source.replace("_", " "))


def _category_words(record: dict[str, Any]) -> str:
    """Category slugs as words, because `coding_agent` is not a search term."""
    categories = [str(item).replace("_", " ").strip() for item in (record.get("categories") or [])]
    return ", ".join(item for item in categories if item)


def _artifacts(record: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(kind, label, url) for every artifact link, in title order, deduplicated."""
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for kind in _ARTIFACT_ORDER:
        for artifact in record.get("artifacts") or []:
            if not isinstance(artifact, dict) or artifact.get("kind") != kind:
                continue
            url = artifact.get("url")
            if not isinstance(url, str) or not url.strip() or url in seen:
                continue
            seen.add(url)
            found.append((kind, _ARTIFACT_LABELS[kind], url.strip()))
    return found


def _facet_kinds(artifacts: list[tuple[str, str, str]]) -> list[str]:
    """The artifact kinds a title and a heading may name, in their listing order."""
    present = {kind for kind, _, _ in artifacts}
    return [kind for kind in _TITLE_FACETS if kind in present]


def _score_count(scores_by_source: dict[str, Any]) -> int:
    return sum(len(source.get("rows") or []) for source in scores_by_source.values())


def _join_words(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} & {items[-1]}"


def _benchmark_phrase(name: str) -> str:
    """`GPQA` becomes `GPQA Benchmark`; `SWE-bench Verified` is left alone.

    The word people type is almost always the name plus "benchmark". Adding it
    to a name that already contains it produces "SWE-bench Benchmark", which
    reads as a mistake and matches nothing extra.
    """
    lowered = name.lower()
    if "bench" in lowered or "eval" in lowered:
        return name
    return f"{name} Benchmark"


def _title(
    name: str,
    record: dict[str, Any],
    artifacts: list[tuple[str, str, str]],
    scores_by_source: dict[str, Any],
    context: CatalogContext,
) -> str:
    """One title covering every search intent the page can actually answer.

    The facet list is built from what this page holds, never from a template:
    promising a dataset link on a page that has none is the kind of title a
    search engine rewrites and a reader resents.
    """
    base = _benchmark_phrase(name)
    if name in context.shared_names:
        label = _source_label(record)
        if label:
            base = f"{base} ({label})"
    facets = [_ARTIFACT_LABELS[kind] for kind in _facet_kinds(artifacts)]
    if scores_by_source:
        facets.append("Results")
    detail = _join_words(facets) if facets else "What It Tests"
    return f"{base}: {detail} | Benchmark Radar"


def _own_description(record: dict[str, Any]) -> str | None:
    raw = record.get("description") or {}
    own = raw.get("en")
    if isinstance(own, str) and own.strip():
        return " ".join(own.split())
    return None


def _evidence_sentence(
    name: str, record: dict[str, Any], artifacts: list[tuple[str, str, str]], score_count: int
) -> str:
    """What Benchmark Radar itself adds, stated only where it is true."""
    if score_count:
        opening = f"Benchmark Radar tracks {score_count} reported scores for {name}"
    else:
        opening = f"Benchmark Radar tracks {name}"
    documents = record.get("documents") or []
    if documents:
        opening += f", cited by {len(documents)} source documents"
    links = [_ARTIFACT_LABELS[kind].lower() for kind in _facet_kinds(artifacts)]
    if links:
        opening += f", with links to its {_join_words(links).replace(' & ', ' and ')}"
    return f"{opening}."


def _summary_sentence(name: str, record: dict[str, Any]) -> str:
    """A first sentence for a record that carries no description of its own."""
    categories = _category_words(record)
    publisher = _text(record, "publisher")
    if categories and publisher:
        return f"{name} is a {categories} benchmark published by {publisher}."
    if categories:
        return f"{name} is an AI benchmark covering {categories}."
    if publisher:
        return f"{name} is an AI benchmark published by {publisher}."
    return f"{name} is an AI benchmark in the Benchmark Radar catalog."


def _description(
    record: dict[str, Any],
    scores_by_source: dict[str, Any] | None = None,
) -> str:
    """A human summary for the page, never empty, at most one line.

    The record's own sentence leads when it has one. A short sentence, or none
    at all, is padded with what the page actually holds rather than left as the
    two-word categories some sources publish: `Coding` describes nothing and
    reads identically on forty other pages.
    """
    scores_by_source = scores_by_source or {}
    name = _text(record, "name") or "This benchmark"
    own = _own_description(record)
    lead = own or _summary_sentence(name, record)
    tail = _evidence_sentence(name, record, _artifacts(record), _score_count(scores_by_source))
    stop = "" if lead.endswith((".", "!", "?")) else "."
    composed = f"{lead}{stop} {tail}"
    if len(composed) <= _DESCRIPTION_LIMIT:
        return composed
    # The padding exists for records whose own sentence says almost nothing.
    # When the record already carries a real sentence, half of it plus half of
    # ours reads worse than all of its own, so the padding is dropped instead.
    if own and len(own) >= 110:
        return _clip(own)
    return _clip(composed)


def _clip(text: str) -> str:
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
    categories = _category_words(record)
    if categories:
        facts.append(("Evaluates", categories))
    openness = record.get("openness") or {}
    status = openness.get("status")
    if isinstance(status, str) and status:
        facts.append(("Openness", status))
    label = _source_label(record)
    if label:
        facts.append(("Catalog source", label))
    facts.append(("Reported scores", str(_score_count(scores_by_source))))
    return facts


def _json_ld(payload: dict[str, Any]) -> str:
    """Serialize structured data for a <script> block.

    JSON may legally contain the substring `</`, which would close the script
    tag early no matter how valid the JSON is. Escaping the slash keeps the
    block intact and is valid JSON for every consumer.
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def _webpage_jsonld(slug: str, name: str, description: str, title: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": _canonical(slug),
        "name": title,
        "url": _canonical(slug),
        "description": description,
        "inLanguage": ["en", "zh-Hans"],
        "isPartOf": website_reference(),
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
            f"<h3>{_esc(SOURCE_LABELS.get(source, source))}</h3>"
            "<table><thead><tr><th>Model</th><th>Organization</th>"
            "<th>Reported value</th><th>Reported</th><th>Evidence</th></tr></thead>"
            f"<tbody>{body}</tbody></table></section>"
        )
    return "".join(sections)


def _artifacts_section(name: str, artifacts: list[tuple[str, str, str]]) -> str:
    """The paper, code and dataset links, under the heading people search for.

    Every one of these URLs was already in the shard and reachable nowhere but
    the dashboard's JavaScript. A page about a benchmark that does not link to
    the benchmark is the thinnest kind of catalog page there is.
    """
    if not artifacts:
        return ""
    labels = [_ARTIFACT_LABELS[kind].lower() for kind in _facet_kinds(artifacts)]
    heading = f"{name} {_join_words(labels).replace(' & ', ' and ')}" if labels else f"{name} links"
    items = "".join(
        f'<li><span class="artifact-kind">{_esc(label)}</span> '
        f'<a href="{_esc(url)}" rel="nofollow noopener">{_esc(url)}</a></li>'
        for _, label, url in artifacts
    )
    return f'<section><h2>{_esc(heading)}</h2><ul class="links">{items}</ul></section>'


def _documents_section(name: str, record: dict[str, Any]) -> str:
    """Which model reports and registry pages cite this benchmark."""
    documents = [item for item in (record.get("documents") or []) if isinstance(item, dict)]
    if not documents:
        return ""
    ordered = sorted(
        documents,
        key=lambda item: (str(item.get("published") or ""), str(item.get("title") or "")),
        reverse=True,
    )
    items = []
    for document in ordered[:_DOCUMENT_LIMIT]:
        title = _text(document, "title") or _text(document, "model_name") or "Source document"
        url = _text(document, "source_url")
        label = _esc(title)
        if url:
            label = f'<a href="{_esc(url)}" rel="nofollow noopener">{label}</a>'
        meta = ", ".join(
            part for part in (_text(document, "organization"), _text(document, "published")) if part
        )
        suffix = f' <span class="caveat">{_esc(meta)}</span>' if meta else ""
        items.append(f"<li>{label}{suffix}</li>")
    more = ""
    if len(ordered) > _DOCUMENT_LIMIT:
        more = f'<p class="caveat">{len(ordered)} source documents cite this benchmark.</p>'
    return (
        f"<section><h2>Which sources cite {_esc(name)}?</h2>"
        f'<ul class="links">{"".join(items)}</ul>{more}</section>'
    )


def _related_section(slug: str, record: dict[str, Any], context: CatalogContext) -> str:
    """Sibling benchmarks in the same capability, as real links.

    Without this every benchmark page is a leaf: reachable from the directory
    and from nowhere else, and offering a reader who wanted "a coding agent
    benchmark" exactly one of them.
    """
    related: list[tuple[str, str]] = []
    seen = {slug}
    for category in record.get("categories") or []:
        for name, other in context.by_category.get(str(category), ()):
            if other in seen:
                continue
            seen.add(other)
            related.append((name, other))
    if not related:
        return ""
    related.sort(key=lambda item: (item[0].lower(), item[1]))
    items = "".join(
        f'<li><a href="{_canonical(other)}">{_esc(name)}</a></li>'
        for name, other in related[:_RELATED_LIMIT]
    )
    words = _category_words(record)
    heading = f"Related {words} benchmarks" if words else "Related benchmarks"
    return f'<section><h2>{_esc(heading)}</h2><ul class="links">{items}</ul></section>'


def _benchmark_nav(interactive: str) -> str:
    return (
        '<nav class="site">'
        f'<a href="{SITE_URL}/">Benchmark Radar</a> '
        f'<a href="{SITE_URL}/benchmarks/">Benchmark directory</a> '
        f'<a href="{interactive}">Interactive view</a></nav>'
    )


def _page_html(slug: str, shard: dict[str, Any], context: CatalogContext | None = None) -> str:
    context = context or CatalogContext()
    record = shard.get("record") or {}
    scores_by_source = shard.get("scores_by_source") or {}
    name = _text(record, "name") or slug
    description = _description(record, scores_by_source)
    canonical = _canonical(slug)
    artifacts = _artifacts(record)
    title = _title(name, record, artifacts, scores_by_source, context)
    facts = "".join(
        f"<dt>{_esc(label)}</dt><dd>{_esc(value)}</dd>"
        for label, value in _facts(record, scores_by_source)
    )
    scores = _scores_sections(scores_by_source)
    if scores:
        scores_html = (
            f"<section><h2>{_esc(name)} results and reported scores</h2>{scores}</section>"
            '<p class="caveat">Scores are partitioned by the source that reported '
            "them and are never merged into a single cross-source ranking, because "
            "the sources measure different things and say so.</p>"
        )
    else:
        scores_html = (
            '<p class="caveat">No reported scores are on record for this benchmark yet.</p>'
        )
    body = (
        f"<section><h2>What is {_esc(name)}?</h2>"
        f'<p class="lede">{_esc(description)}</p>'
        f"<dl>{facts}</dl></section>"
        f"{_artifacts_section(name, artifacts)}"
        f"{scores_html}"
        f"{_documents_section(name, record)}"
        f"{_related_section(slug, record, context)}"
    )
    interactive = f"{SITE_URL}/saturation/?lfrontier={slug}"
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
<script type="application/ld+json">{_webpage_jsonld(slug, name, description, title)}</script>
<script type="application/ld+json">{_breadcrumb_jsonld(slug, name)}</script>
<style>{_BENCH_CSS}</style>
</head>
<body>
{nav}
<main>
  <p class="eyebrow">Benchmark</p>
  <h1>{_esc(_benchmark_phrase(name))}</h1>
  {body}
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
        "isPartOf": website_reference(),
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
    interactive dashboard is <a href="{SITE_URL}/saturation/">here</a>.</p>
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
    # The slug becomes a directory name, a canonical URL, and a query argument
    # on the dashboard link, so it is held to the slug alphabet rather than
    # only to the characters that would escape the output directory. Anything
    # else means the shard was not written by this project, and a page built
    # from it could carry markup straight into an attribute.
    if not isinstance(slug, str) or not _SAFE_SLUG.fullmatch(slug):
        raise ValueError(f"unsafe slug in {path.name}")
    return slug, shard


def benchmark_slugs(shard_dir: Path) -> list[str]:
    """Stable sorted slugs of every shard, for the sitemap."""
    if not shard_dir.is_dir():
        return []
    return sorted(path.stem for path in shard_dir.glob("*.json"))


def _is_calendar_date(value: str) -> bool:
    """True only for a real `YYYY-MM-DD` day.

    Shape alone is not enough: `2023-02-29` matches the pattern and would reach
    the sitemap as an invalid `lastmod`. The round trip also rejects the forms
    `date.fromisoformat` accepts but the sitemap spec does not, such as
    `20230101`.
    """
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _shard_lastmod(shard: dict[str, Any]) -> str | None:
    """Newest date the page's own evidence carries, or None when it carries none.

    A page changes when a score lands on it or when the record itself is dated,
    not when some other benchmark's snapshot arrives. Both fields are stored as
    plain `YYYY-MM-DD`, so the newest one sorts lexically; anything a calendar
    rejects is dropped rather than passed through to the sitemap.
    """
    dates = {
        row.get("reported_date")
        for source in (shard.get("scores_by_source") or {}).values()
        for row in (source or {}).get("rows") or ()
    }
    dates.add((shard.get("record") or {}).get("released"))
    dated = {value for value in dates if isinstance(value, str) and _is_calendar_date(value)}
    return max(dated) if dated else None


def benchmark_sitemap_entries(shard_dir: Path) -> list[tuple[str, str | None]]:
    """Benchmark page paths in stable slug order, each with its own lastmod."""
    if not shard_dir.is_dir():
        return []
    entries = []
    for path in sorted(shard_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        entries.append((f"/benchmarks/{path.stem}/", _shard_lastmod(shard)))
    return entries


def benchmark_page_urls(shard_dir: Path) -> list[str]:
    """Canonical benchmark page URLs in stable slug order."""
    return [_canonical(slug) for slug in benchmark_slugs(shard_dir)]


def _catalog_context(loaded: list[tuple[str, dict[str, Any]]]) -> CatalogContext:
    """Collect the two cross-page facts, in one pass over the already-read shards."""
    counts: dict[str, int] = defaultdict(int)
    by_category: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for slug, shard in loaded:
        record = shard.get("record") or {}
        name = _text(record, "name")
        if not name:
            continue
        counts[name] += 1
        for category in record.get("categories") or []:
            by_category[str(category)].append((name, slug))
    return CatalogContext(
        shared_names=frozenset(name for name, count in counts.items() if count > 1),
        by_category={
            category: tuple(sorted(members, key=lambda item: (item[0].lower(), item[1])))
            for category, members in by_category.items()
        },
    )


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
            f"{shard_dir} holds no benchmark shards; run `benchmark-radar normalize-catalog` first"
        )
    shard_paths = sorted(shard_dir.glob("*.json"))
    if not shard_paths:
        raise ValueError(f"{shard_dir} holds no benchmark shards; refusing to write empty pages")

    staging = output_dir.with_name(output_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    loaded = [_load_shard(path) for path in shard_paths]
    context = _catalog_context(loaded)

    entries: list[tuple[str, str]] = []
    for slug, shard in loaded:
        page_dir = staging / slug
        page_dir.mkdir(parents=True)
        (page_dir / "index.html").write_text(_page_html(slug, shard, context), encoding="utf-8")
        name = _text(shard.get("record") or {}, "name") or slug
        entries.append((name, _canonical(slug)))

    entries.sort(key=lambda item: (item[0].lower(), item[1]))
    (staging / "index.html").write_text(_directory_html(entries), encoding="utf-8")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)
    return {"page_count": len(shard_paths), "output_dir": output_dir}
