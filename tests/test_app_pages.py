"""The published view pages must be the dashboard, and must say what they are.

The bug these guard against is not a crash. It is a page that loads fine and
describes something else: a `/leaderboard/` carrying the homepage's title, or a
thin summary served under a canonical that points search traffic at it. Every
assertion below is about agreement between what a page claims and what it shows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from benchmark_radar.app_pages import (
    AppPageError,
    load_category_colors,
    load_utility_seo,
    load_view_seo,
    render_app_page,
    write_app_pages,
)
from benchmark_radar.feed import SITE_URL
from benchmark_radar.site_shell import esc

SITE = Path(__file__).resolve().parents[1] / "site"


def _dashboard() -> dict:
    return {
        "model_card_leaderboard": {
            "measures": "How many curated model cards report each benchmark.",
            "entries": [
                {"rank": 1, "name": "Alpha & Reasoning", "card_count": 20},
                {"rank": 2, "name": "Beta Bench", "card_count": 10},
                {"rank": 3, "name": "Gamma", "card_count": 1},
                {"rank": 4, "name": "Unreported", "card_count": 0},
            ],
        },
        "days": [
            {
                "date": "2026-08-30",
                "category_trends": {
                    "benchmark": {
                        "count": 7,
                        "total_count": 9,
                        "delta": 3,
                        "baseline": 4.5,
                        "momentum": 0.5,
                        "cumulative": 1234,
                    },
                    "agentic": {
                        "count": 2,
                        "total_count": 2,
                        "delta": None,
                        "baseline": None,
                        "momentum": None,
                        "cumulative": 40,
                    },
                },
                "selection": {"recommendation_score": 40},
            }
        ],
        "corpus": {
            "aggregates": {
                "entity_types": {
                    "artifact": 4645,
                    "organization": 1775,
                    "person": 13907,
                    "source": 12,
                    "topic": 5,
                },
                "topics": [
                    {"topic": "data_quality", "entity_count": 8, "source_breadth": 1},
                    {"topic": "agentic", "entity_count": 40, "source_breadth": 6},
                ],
                # "arXiv" against "OpenAI" is the tie the browser and Python
                # order differently: localeCompare folds case, a codepoint sort
                # does not, so the seed would list them the other way round.
                "sources": {"arXiv": 9, "OpenAI": 9, "Hugging Face": 30},
                "organizations": {"Anthropic": 12, "Google": 4},
            }
        },
        "rubric": {
            "scoring_version": 5,
            "score_max": 100,
            "formula": "0.35 × relevance + 0.20 × evidence + 0.20 × recency + 0.25 × adoption",
            "components": [
                {
                    "key": "relevance",
                    "label": "Relevance",
                    "weight": 0.35,
                    "summary": "How squarely the record matches the taxonomy.",
                    "bands": ["100 for a direct match", "0 for no match"],
                },
                {
                    "key": "evidence",
                    "label": "Evidence",
                    "weight": 0.2,
                    "summary": "How directly the record is attested.",
                    "bands": ["Primary sources rank highest"],
                },
                {
                    "key": "recency",
                    "label": "Recency",
                    "weight": 0.2,
                    "summary": "How recently the artifact was published.",
                    "bands": ["100 at first discovery"],
                },
                {
                    "key": "adoption",
                    "label": "Adoption",
                    "weight": 0.25,
                    "summary": "The strongest available public adoption signal.",
                    "bands": ["Uses the strongest normalized counter"],
                },
            ],
            "limits": ["Priority is not benchmark quality."],
        },
    }


def _write(tmp_path: Path, dashboard: dict) -> dict:
    (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
    for name in ("app.js", "glyphs.js"):
        (tmp_path / "assets" / name).write_text(
            (SITE / "assets" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "index.html").write_text(
        (SITE / "index.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return write_app_pages(dashboard, tmp_path)


def test_view_seo_is_read_from_the_script_the_browser_uses():
    seo = load_view_seo(SITE / "assets" / "app.js")
    assert {view: entry["canonical"] for view, entry in seo.items()} == {
        "today": "/",
        "leaderboard": "/leaderboard/",
        "trends": "/trends/",
        "map": "/explore/",
    }
    assert all(entry["title"] and entry["description"] for entry in seo.values())


def test_category_palette_is_read_from_the_script_the_browser_uses():
    colors, fallbacks = load_category_colors(SITE / "assets" / "glyphs.js")
    assert colors["benchmark"].startswith("#")
    assert fallbacks and all(color.startswith("#") for color in fallbacks)


def test_utility_seo_is_read_from_the_script_the_browser_uses():
    seo = load_utility_seo(SITE / "assets" / "app.js")
    assert {page: entry["canonical"] for page, entry in seo.items()} == {
        "cli": "/cli/",
        "cite": "/cite/",
        "rubric": "/rubric/",
    }
    assert all(entry["title"] and entry["description"] for entry in seo.values())


def test_utility_seo_parser_does_not_depend_on_two_space_indentation(tmp_path):
    script = tmp_path / "app.js"
    script.write_text(
        """const UTILITY_SEO = {
    cli: {
        title: "CLI",
        description: "Local search",
        canonical: "/cli/"
    },
    cite: {
        title: "Cite",
        description: "Citation formats",
        canonical: "/cite/"
    },
    rubric: {
        title: "Rubric",
        description: "Scoring method",
        canonical: "/rubric/",
    }
};
""",
        encoding="utf-8",
    )
    seo = load_utility_seo(script)
    assert {page: entry["canonical"] for page, entry in seo.items()} == {
        "cli": "/cli/",
        "cite": "/cite/",
        "rubric": "/rubric/",
    }


def test_every_view_is_published_at_its_own_path(tmp_path):
    report = _write(tmp_path, _dashboard())
    assert report["paths"] == [
        "/leaderboard/",
        "/trends/",
        "/explore/",
        "/cli/",
        "/cite/",
        "/rubric/",
    ]
    for path in report["paths"]:
        assert (tmp_path / path.strip("/") / "index.html").exists()
    assert not list(tmp_path.glob("*/index.html.tmp"))


def test_each_page_declares_the_url_it_is_served_at(tmp_path):
    _write(tmp_path, _dashboard())
    view_seo = load_view_seo(SITE / "assets" / "app.js")
    utility_seo = load_utility_seo(SITE / "assets" / "app.js")
    generated_seo = {
        page: seo for page, seo in {**view_seo, **utility_seo}.items() if seo["canonical"] != "/"
    }
    for page_name, seo in generated_seo.items():
        path = seo["canonical"]
        page = (tmp_path / path.strip("/") / "index.html").read_text(encoding="utf-8")
        canonical = f'<link rel="canonical" href="{SITE_URL}{path}">'
        assert page.count(canonical) == 1
        assert page.count("<title>") == 1
        assert f"<title>{esc(seo['title'])}</title>" in page, page_name
        assert f'<meta property="og:url" content="{SITE_URL}{path}">' in page


def test_only_the_named_view_is_open(tmp_path):
    _write(tmp_path, _dashboard())
    for path, open_id in (
        ("leaderboard", "leaderboard-view"),
        ("trends", "trends-view"),
        ("explore", "map-view"),
    ):
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        sections = re.findall(r'<section class="view" id="([\w-]+)"([^>]*)>', page)
        assert sections, "no view sections found"
        visible = [name for name, attrs in sections if "hidden" not in attrs]
        assert visible == [open_id]


def test_each_generated_page_marks_its_navigation_entry_current(tmp_path):
    _write(tmp_path, _dashboard())
    ids = {
        "leaderboard": 'data-view="leaderboard"',
        "trends": 'data-view="trends"',
        "cli": 'id="cli-nav"',
        "cite": 'id="cite-open"',
    }
    for path, identifying_attribute in ids.items():
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        opening = re.search(
            rf"<(?:a|button)\b(?=[^>]*{re.escape(identifying_attribute)})[^>]*>", page
        )
        assert opening
        assert 'class="' in opening.group(0) and "nav-active" in opening.group(0)
        assert 'aria-current="page"' in opening.group(0)
        if path in {"cli", "cite", "rubric"}:
            assert 'aria-expanded="true"' in opening.group(0)


def test_unlisted_explore_and_rubric_routes_have_no_false_current_tab(tmp_path):
    _write(tmp_path, _dashboard())
    for path in ("explore", "rubric"):
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        nav = re.search(r'<nav class="view-nav".*?</nav>', page, re.S).group(0)
        assert 'aria-current="page"' not in nav
    explore = (tmp_path / "explore" / "index.html").read_text(encoding="utf-8")
    rubric = (tmp_path / "rubric" / "index.html").read_text(encoding="utf-8")
    assert '<section class="view" id="map-view"' in explore
    assert '<dialog id="rubric-dialog"' in rubric and " open" in rubric


def test_exactly_one_heading_is_visible_per_page(tmp_path):
    """Four h1s live in the document, one per view, and three are inside hidden
    sections. A page with two visible h1s or none is a page whose outline lies."""
    _write(tmp_path, _dashboard())
    for path in ("leaderboard", "trends", "explore"):
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        open_section = re.search(
            r'<section class="view" id="[\w-]+"(?![^>]*hidden)[^>]*>(.*?)\n      </section>',
            page,
            re.DOTALL,
        )
        assert open_section, f"no open view section in /{path}/"
        assert len(re.findall(r"<h1[ >]", open_section.group(1))) == 1


def test_pages_carry_breadcrumb_and_webpage_schema(tmp_path):
    _write(tmp_path, _dashboard())
    page = (tmp_path / "leaderboard" / "index.html").read_text(encoding="utf-8")
    blocks = [
        json.loads(block)
        for block in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', page, re.DOTALL
        )
    ]
    types = {block.get("@type") for block in blocks}
    assert {"WebPage", "BreadcrumbList"} <= types
    crumb = next(block for block in blocks if block["@type"] == "BreadcrumbList")
    assert [item["item"] for item in crumb["itemListElement"]] == [
        f"{SITE_URL}/",
        f"{SITE_URL}/leaderboard/",
    ]


def test_utility_schema_names_the_clean_route(tmp_path):
    _write(tmp_path, _dashboard())
    for utility, label in (("cli", "CLI"), ("cite", "Cite"), ("rubric", "Scoring rubric")):
        page = (tmp_path / utility / "index.html").read_text(encoding="utf-8")
        blocks = [
            json.loads(block)
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', page, re.DOTALL
            )
        ]
        webpage = next(block for block in blocks if block.get("@type") == "WebPage")
        breadcrumb = next(block for block in blocks if block.get("@type") == "BreadcrumbList")
        assert webpage["url"] == f"{SITE_URL}/{utility}/"
        assert breadcrumb["itemListElement"][-1]["name"] == label
        assert breadcrumb["itemListElement"][-1]["item"] == f"{SITE_URL}/{utility}/"


def test_utility_pages_ship_the_existing_dialog_open_with_content(tmp_path):
    _write(tmp_path, _dashboard())
    expected = {
        "cli": ("Query it locally (CLI version)", "npx skills add ktwu01/benchmark-radar"),
        "cite": ("Cite this work", "@techreport{Wu_Benchmark_Radar"),
        "rubric": ("How priority is scored", "Priority is not benchmark quality."),
    }
    for utility, phrases in expected.items():
        page = (tmp_path / utility / "index.html").read_text(encoding="utf-8")
        dialog = re.search(
            rf'<dialog\b(?=[^>]*id="{utility}-dialog")[^>]*>(.*?)</dialog>',
            page,
            re.DOTALL,
        )
        assert dialog
        opening = dialog.group(0).split(">", 1)[0]
        assert " open" in opening
        assert " data-seed" in opening
        assert all(phrase in dialog.group(1) for phrase in phrases)


def test_seeded_copy_controls_have_names_values_and_fallback_hints(tmp_path):
    _write(tmp_path, _dashboard())
    for utility, count in (("cli", 1), ("cite", 3)):
        page = (tmp_path / utility / "index.html").read_text(encoding="utf-8")
        buttons = re.findall(r'<button class="copy-target"([^>]*)>(.*?)</button>', page, re.DOTALL)
        assert len(buttons) == count
        for attributes, content in buttons:
            assert 'aria-label="' in attributes
            assert '<code class="copy-text">' in content
            assert '<span class="copy-status">' in content


def test_no_page_ships_a_second_url_for_itself(tmp_path):
    _write(tmp_path, _dashboard())
    for path in ("leaderboard", "trends", "explore", "cli", "cite", "rubric"):
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        assert "?view=" not in page


def test_seeded_rows_match_what_the_renderer_would_draw(tmp_path):
    _write(tmp_path, _dashboard())
    page = (tmp_path / "leaderboard" / "index.html").read_text(encoding="utf-8")
    rows = re.findall(r'<li class="leaderboard-top-row">(.*?)</li>', page)
    # The zero-count entry is filtered out, exactly as renderLeaderboardTop does.
    assert len(rows) == 3
    assert "Alpha &amp; Reasoning" in rows[0]
    assert "20 model cards" in rows[0]
    assert "width:100.0%" in rows[0]
    assert "width:50.0%" in rows[1]
    # Singular noun at one, same as metricLabel.
    assert "1 model card<" in rows[2]
    assert "How many curated model cards report each benchmark." in page


def test_seeded_ranking_exposes_the_same_named_more_control_as_the_renderer(tmp_path):
    dashboard = _dashboard()
    dashboard["model_card_leaderboard"]["entries"].extend(
        [
            {"rank": 4, "name": "Delta", "card_count": 1},
            {"rank": 5, "name": "Epsilon", "card_count": 1},
            {"rank": 6, "name": "Zeta", "card_count": 1},
        ]
    )
    _write(tmp_path, dashboard)
    page = (tmp_path / "leaderboard" / "index.html").read_text(encoding="utf-8")
    button = re.search(r'<button\s+class="leaderboard-top-more".*?</button>', page, re.DOTALL)
    assert button
    assert "hidden" not in button.group(0)
    assert "data-seed" in button.group(0)
    assert 'aria-label="Show all 6 benchmarks ↓"' in button.group(0)
    assert "Show all 6 benchmarks ↓" in button.group(0)


def test_seeded_domain_cards_match_what_the_renderer_would_draw(tmp_path):
    _write(tmp_path, _dashboard())
    page = (tmp_path / "trends" / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'<article class="domain-card([^"]*)">(.*?)</article>', page)
    assert [state for state, _ in cards] == [" is-up", ""]
    benchmark, agentic = (body for _, body in cards)
    assert "<h3>benchmark</h3>" in benchmark
    assert "<dd>+3</dd>" in benchmark
    assert "<dd>4.50</dd>" in benchmark
    assert "<dd>+50%</dd>" in benchmark
    assert "<dd>1,234</dd>" in benchmark
    assert "<dd>2</dd>" in benchmark  # also updated, not counted above
    # A null delta claims no direction and no baseline.
    assert "<dd>not comparable</dd>" in agentic
    assert "<dd>not enough history</dd>" in agentic


def test_seeded_overview_matches_what_the_renderer_would_draw(tmp_path):
    _write(tmp_path, _dashboard())
    page = (tmp_path / "explore" / "index.html").read_text(encoding="utf-8")
    card = re.search(r'<article class="map-insight-card">(.*?)</article>', page)
    assert card
    assert "<h2>At a glance</h2>" in card.group(1)
    assert "<span>Authors</span><strong>13,907</strong>" in card.group(1)


def test_a_view_with_no_data_is_not_published(tmp_path):
    """A URL that describes a ranking nobody can see is worse than no URL."""
    dashboard = _dashboard()
    dashboard["model_card_leaderboard"] = {}
    report = _write(tmp_path, dashboard)
    assert report["paths"] == ["/trends/", "/explore/", "/cli/", "/cite/", "/rubric/"]
    assert not (tmp_path / "leaderboard").exists()


def test_rubric_route_is_not_published_without_a_rubric(tmp_path):
    dashboard = _dashboard()
    dashboard["rubric"] = {}
    report = _write(tmp_path, dashboard)
    assert "/rubric/" not in report["paths"]
    assert not (tmp_path / "rubric").exists()
    assert {"/cli/", "/cite/"} <= set(report["paths"])


def test_a_moved_anchor_fails_the_build_instead_of_shipping(tmp_path):
    seo = load_view_seo(SITE / "assets" / "app.js")
    document = (SITE / "index.html").read_text(encoding="utf-8")
    template = document.replace("<!-- br:page-jsonld -->", "")
    with pytest.raises(AppPageError, match="page JSON-LD marker"):
        render_app_page(template, "leaderboard", seo["leaderboard"], {})


def test_a_missing_seed_container_fails_the_build(tmp_path):
    seo = load_view_seo(SITE / "assets" / "app.js")
    template = (SITE / "index.html").read_text(encoding="utf-8")
    with pytest.raises(AppPageError, match="leaderboard seed container"):
        render_app_page(template, "leaderboard", seo["leaderboard"], {"<ol id='gone'></ol>": "x"})


def test_rebuilding_the_same_data_produces_the_same_bytes(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _write(first, _dashboard())
    _write(second, _dashboard())
    for path in ("leaderboard", "trends", "explore", "cli", "cite", "rubric"):
        assert (first / path / "index.html").read_bytes() == (
            second / path / "index.html"
        ).read_bytes()


def test_a_failed_boot_keeps_the_seeded_rows_and_leads_with_the_error():
    """A data outage must not turn a published URL into an empty page.

    /leaderboard/ promises a ranking in its title, its canonical and the
    sitemap. Hiding every view on a fetch failure would leave a shell behind
    that promise: a broken page to a reader, a missing page to a crawler. The
    rows the page shipped with are still true, so they stay, and the banner
    moves above them so nobody reads them as fresh.
    """
    script = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    # The boot handler is the one that reveals the error state.
    catch = next(
        block
        for block in script.split("} catch (error) {")[1:]
        if "banner.hidden = false;" in block.split("\n  }", 1)[0]
    ).split("\n  }", 1)[0]

    # A view survives only when it is the one being shown and it carries a seed.
    assert 'section.id === `${state.view}-view` && section.querySelector("[data-seed]")' in catch
    assert "section.hidden = !seeded;" in catch
    assert "banner.hidden = false;" in catch
    # Above every view, not above the one that survived: the reader can still
    # navigate, and a banner parked in front of one section would sit below the
    # next one they open.
    assert "if (survivor) banner.parentElement.prepend(banner);" in catch


def test_only_a_working_refresh_retires_the_boot_error_banner():
    """The banner says to refresh, so a refresh that works is what retires it.

    Navigating is not recovering. A boot that threw stopped before it settled
    the date filter, so Today can come up filtered to a date the payload does
    not carry and list nothing. Dropping the warning on a view change would
    call that page healthy. refreshData refetches, revalidates, resettles the
    date and redraws, and only then is "Dashboard unavailable" no longer true.
    """
    script = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    refresh = script.split("async function refreshData() {", 1)[1].split("\n}", 1)[0]
    hide = 'byId("error-state").hidden = true;'

    assert script.count(hide) == 1, "something other than a successful refresh hides the banner"
    assert hide in refresh
    # Inside the try, after the redraw: a refresh that throws leaves it standing.
    assert refresh.index(hide) > refresh.index("rerenderCurrentView();")
    assert refresh.index(hide) < refresh.index("} catch (error) {")

    handler = script.split("const view = item.dataset.view;", 1)[1].split("\n    });", 1)[0]
    assert "error-state" not in handler


def test_explore_ships_every_card_the_renderer_draws(tmp_path):
    """Four cards on screen and one in the first response is a page with two faces.

    renderMapInsights always draws coverage, topics, sources and organizations.
    A seed carrying only the first would hand a crawler a quarter of the page,
    under a canonical claiming to be the page itself.
    """
    _write(tmp_path, _dashboard())
    page = (tmp_path / "explore" / "index.html").read_text(encoding="utf-8")
    insights = page.split('id="map-insights"', 1)[1].split("</div>", 1)[0]

    assert insights.count('<article class="map-insight-card">') == 4
    for title in ("At a glance", "What it is about", "Where we found it", "Who appears most"):
        assert f"<h2>{title}</h2>" in insights

    # Ranked by count, ties broken the way the browser breaks them.
    assert "AI agents" in insights and "data quality" in insights
    assert insights.index("AI agents") < insights.index("data quality")
    assert "40 items · 6 sources" in insights
    assert "8 items · 1 source" in insights
    assert insights.index("arXiv") < insights.index("OpenAI")
    assert "30 times found" in insights


def test_trends_names_the_scan_its_cards_count(tmp_path):
    """The domain cards are one day's numbers, so the page has to say which day."""
    _write(tmp_path, _dashboard())
    page = (tmp_path / "trends" / "index.html").read_text(encoding="utf-8")

    assert '<span id="domain-date" data-seed>Aug 30, 2026</span>' in page


def test_the_ranking_ships_with_the_caveat_that_keeps_it_honest(tmp_path):
    """An adoption count read as a quality score is the opposite conclusion.

    The (i) beside the ranking carries the correction. A page that shipped the
    five rows without it would publish the misreading and withhold the fix.
    """
    _write(tmp_path, _dashboard())
    page = (tmp_path / "leaderboard" / "index.html").read_text(encoding="utf-8")
    info = page.split('id="leaderboard-top-info"', 1)[1].split("</span>", 1)[0]

    assert 'class="info-disclosure"' in info
    assert "How many curated model cards report each benchmark." in info
    assert "A report counts once per test" in info


def test_a_view_that_lost_its_data_loses_its_page(tmp_path):
    """A dropped view must not stay servable at the URL this build stopped listing.

    Skipping the write is not enough: the previous build's copy is still on
    disk, still carrying the leaderboard's canonical, and still answering a
    request that the sitemap no longer advertises.
    """
    _write(tmp_path, _dashboard())
    assert (tmp_path / "leaderboard" / "index.html").exists()

    without = _dashboard()
    without["model_card_leaderboard"] = {"entries": []}
    report = _write(tmp_path, without)

    assert "/leaderboard/" not in report["paths"]
    assert not (tmp_path / "leaderboard" / "index.html").exists()
    assert (tmp_path / "trends" / "index.html").exists()


def test_every_seeded_container_is_one_the_renderer_already_owns(tmp_path):
    """The seed has to land in the host the renderer writes to.

    Seeding anywhere else would leave a second copy on screen once the data
    loads, because the renderers replace their host's children rather than
    merging into them.
    """
    _write(tmp_path, _dashboard())
    script = (SITE / "assets" / "app.js").read_text(encoding="utf-8")

    seen = set()
    for path in ("leaderboard", "trends", "explore"):
        page = (tmp_path / path / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'id="([a-z-]+)"[^>]*\bdata-seed\b', page)
        assert ids, path
        seen.update(ids)
    for element_id in sorted(seen):
        assert f'byId("{element_id}")' in script or f'"{element_id}"' in script, element_id
