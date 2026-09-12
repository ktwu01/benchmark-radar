"""The /about/ page and the alias paths that redirect into /cite/ (issue #593).

Two gaps this closes. The project's own story lived only in the GitHub README,
so a reader who arrived from search had no page explaining what the catalog is,
who collects it, or where else the work is published; and the citation sheet
sits at /cite/, a path nobody searches for, while "publications" is the word a
researcher actually types and clicks.

The about page is a static document rather than a dashboard route, because it is
prose rather than a view over the corpus: it reuses the blog's chrome extractor
so the masthead, nav, and footer stay the single copy that lives in
``site/index.html``.

The aliases are HTML redirects, not server rules. GitHub Pages serves static
files and has no rewrite layer, so ``/publications/`` ships a document that
refreshes to ``/cite/`` and points its canonical there. The canonical does the
consolidating on its own: Google's canonicalization guidance is that ``noindex``
blocks a page from Search entirely rather than folding it into its canonical, so
an alias that carried both would throw away the signal it exists to pass on.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .blog_shell import SiteChrome, chrome_i18n_table, extract_site_chrome, render_page
from .feed import SITE_URL
from .site_shell import breadcrumb_schema, esc, organization_reference, website_reference

ABOUT_PATH = "/about/"
CITE_PATH = "/cite/"
# Both the singular and the plural, because a reader types either one and a
# 404 on the second is a lost citation.
ALIAS_PATHS: tuple[tuple[str, str], ...] = (
    ("/publications/", CITE_PATH),
    ("/publication/", CITE_PATH),
)

# The project's published name, from the technical report. The title tag takes
# no "| Benchmark Radar" suffix because the brand is already its first word,
# and the h1 is the same sentence so a reader lands on the heading they clicked.
ABOUT_TITLE = (
    "Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and Evaluation"
)
ABOUT_HEADING = ABOUT_TITLE
# The description is written for the search result and names the kinds of
# evaluation someone might be looking for. The lede is written for the reader
# who already clicked, so it says what the page hands them rather than saying
# the heading directly above it a second time.
ABOUT_DESCRIPTION = (
    "An open, daily-updated database and search engine for AI benchmarks: LLM, agent, "
    "multimodal, coding, safety and AI-for-science evaluations, each with the paper, "
    "code and scores it has."
)
ABOUT_LEDE = (
    "Every benchmark the catalog has found, with the paper, code, dataset and scores on "
    "record for it. Collected from public sources and rebuilt every day, so a number here "
    "is never older than the last run."
)

# Every place this project publishes. External links are part of the point:
# a reader who wants the data, the code, the paper, or the build log should
# reach it from here rather than from a search that may not find it.
_ELSEWHERE: tuple[tuple[str, str, str], ...] = (
    (
        "Source code on GitHub",
        "https://github.com/ktwu01/benchmark-radar",
        "The collector, the catalog contract, the site build, and the issue tracker.",
    ),
    (
        "Technical report",
        "https://arxiv.org/abs/2609.11115",
        "How the catalog is collected, scored, and kept current, written up on arXiv.",
    ),
    (
        "Download the full dataset",
        "https://github.com/ktwu01/benchmark-radar/releases/download/cli-data/"
        "benchmark-radar-data.zip",
        "The benchmark catalog, detail records, and daily discovery snapshots in one ZIP.",
    ),
    (
        "Build log: every day of this project, written up",
        "https://koutian.is-a.dev/year-archive/",
        "Koutian Wu's blog, with a post for each day of work from day 1 onward.",
    ),
    (
        "Benchmark Radar: an evidence-first daily radar for AI benchmarks",
        "https://koutian.is-a.dev/posts/2026/07/benchmark-radar/",
        "The post that started it, explaining the idea before any of it was built.",
    ),
    (
        "Why hard benchmarks should not become coding tricks",
        "https://koutian.is-a.dev/posts/2026/07/hard-benchmarks-should-not-be-coding-tricks/",
        "What goes wrong when a benchmark rewards the harness instead of the ability.",
    ),
    (
        "The value of benchmarks and the ability to frame questions",
        "https://koutian.is-a.dev/posts/2026/07/"
        "benchmark-value-market-and-scientific-question-setting/",
        "Whether building benchmarks counts as research, argued out in full.",
    ),
    (
        "Google Scholar",
        "https://scholar.google.com/citations?user=s9w1k-cAAAAJ&hl=en",
        "Other work by the author.",
    ),
)

# Where a reader goes next, inside the site. The about page is a hub, so it
# links to the surfaces a first-time visitor would otherwise have to find.
_INSIDE: tuple[tuple[str, str], ...] = (
    ("/benchmarks/", "Browse every benchmark in the catalog, one page each"),
    ("/leaderboard/", "Compare reported scores across the benchmark frontier"),
    ("/saturation/", "Watch scores on a benchmark climb toward saturation"),
    ("/blog/", "Read the daily brief: what appeared today and what it means"),
    ("/cli/", "Query the whole catalog offline from the command line"),
    (CITE_PATH, "Cite the technical report, or read the publications behind it"),
)

_STORY = (
    (
        "Why it exists",
        "I kept running into new benchmarks while doing benchmark research. There was no "
        "one place that listed them, said what each one tests, and showed which models "
        "had been measured on it. So I built a collector that reads public sources every "
        "day and writes down what it finds, with the evidence attached.",
    ),
    (
        "What it collects",
        "Two things, kept apart. Every day the collector reads arXiv, GitHub, Hugging Face, "
        "OpenReview, Semantic Scholar, Hacker News, and the labs' own release feeds, and "
        "writes down the benchmark work that appeared that day. Separately, the scored "
        "catalog is built from registered leaderboards and model reports: OpenCompass Hub, "
        "LLM Stats, Artificial Analysis, and the evaluation tables labs publish with a "
        "model. Each benchmark in that catalog keeps its own page with the paper, code, "
        "and dataset links it has, plus every score on record.",
    ),
    (
        "The rule the whole project follows",
        "A number is only worth as much as the document it came from. Scores stay "
        "partitioned by the source that reported them and are never merged into a single "
        "ranking, because those sources measure under different conditions and say so. "
        "Where a field is missing, the page leaves it out rather than filling it in.",
    ),
    (
        "Who makes it",
        "Benchmark Radar is built by Koutian Wu and open to contributions. The code is "
        "MIT-licensed, the data is downloadable in full, and every page is generated from "
        "the same public corpus, so anyone can check a claim against its source.",
    ),
)


def _section(heading: str, body: str) -> str:
    return f"<section><h2>{esc(heading)}</h2><p>{esc(body)}</p></section>"


def _link_list(items: tuple[tuple[str, str, str], ...]) -> str:
    rows = "".join(
        f'<li><a href="{esc(url)}" rel="noopener">{esc(label)}</a>'
        f' <span class="blog-meta">{esc(note)}</span></li>'
        for label, url, note in items
    )
    return f'<ul class="blog-links">{rows}</ul>'


def _inside_list() -> str:
    rows = "".join(f'<li><a href="{esc(path)}">{esc(note)}</a></li>' for path, note in _INSIDE)
    return f'<ul class="blog-links">{rows}</ul>'


def about_body() -> str:
    story = "".join(_section(heading, body) for heading, body in _STORY)
    return f"""<header class="blog-hero">
  <h1>{esc(ABOUT_HEADING)}</h1>
  <p class="blog-lede">{esc(ABOUT_LEDE)}</p>
</header>
<div class="blog-prose">{story}
<section><h2>Where to start</h2>{_inside_list()}</section>
<section><h2>Benchmark Radar elsewhere</h2>{_link_list(_ELSEWHERE)}</section>
</div>"""


def about_page(chrome: SiteChrome, chrome_i18n: dict[str, str], updated: str | None) -> str:
    canonical = SITE_URL + ABOUT_PATH
    about = {
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "@id": canonical,
        "name": ABOUT_TITLE,
        "url": canonical,
        "description": ABOUT_DESCRIPTION,
        "inLanguage": ["en"],
        "isPartOf": website_reference(),
        "about": organization_reference(),
    }
    return render_page(
        title=ABOUT_TITLE,
        description=ABOUT_DESCRIPTION,
        canonical=canonical,
        body=about_body(),
        chrome=chrome,
        chrome_i18n=chrome_i18n,
        updated=updated,
        schemas=(
            about,
            breadcrumb_schema(
                ("Benchmark Radar", f"{SITE_URL}/"),
                ("About", canonical),
                canonical=canonical,
            ),
        ),
    )


def alias_page(target: str) -> str:
    """A crawlable redirect stub that consolidates onto its target."""
    destination = SITE_URL + target
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={esc(target)}">
<link rel="canonical" href="{esc(destination)}">
<title>Publications · Benchmark Radar</title>
</head>
<body>
<p>This page has moved to <a href="{esc(target)}">Publications</a>.</p>
<script>window.location.replace({json.dumps(target)});</script>
</body>
</html>
"""


def write_about(
    site_dir: Path,
    *,
    updated: str | None,
    dashboard_html: str | None = None,
    app_js: str | None = None,
) -> dict[str, Any]:
    """Write /about/ and the alias stubs, reporting the paths the sitemap may list.

    Only the about page is returned as indexable. The aliases exist so a typed
    or linked URL lands somewhere, and a sitemap that advertised them would be
    asking a crawler to index a page that immediately becomes another one.

    ``updated`` is None when the corpus has no history yet. The page is still
    written: it is prose about the project, the site nav links to it from every
    other page, and a build that skipped it would publish a nav item that 404s.
    """
    if dashboard_html is None:
        dashboard_html = (site_dir / "index.html").read_text(encoding="utf-8")
    if app_js is None:
        app_js = (site_dir / "assets" / "app.js").read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard_html, active_path=ABOUT_PATH)
    i18n = chrome_i18n_table(chrome, app_js)

    output = site_dir / ABOUT_PATH.strip("/")
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    (staging / "index.html").write_text(about_page(chrome, i18n, updated), encoding="utf-8")
    if output.exists():
        shutil.rmtree(output)
    staging.rename(output)

    aliases = []
    for alias, target in ALIAS_PATHS:
        alias_dir = site_dir / alias.strip("/")
        alias_dir.mkdir(parents=True, exist_ok=True)
        (alias_dir / "index.html").write_text(alias_page(target), encoding="utf-8")
        aliases.append(alias)
    return {"paths": [ABOUT_PATH], "aliases": aliases}
