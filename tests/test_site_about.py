"""The /about/ and /media/ pages and the /publication(s)/ aliases (issues #593, #906)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from benchmark_radar.feed import SITE_URL
from benchmark_radar.site_about import ALIAS_PATHS, write_about

DASHBOARD = Path("site/index.html")
APP_JS = Path("site/assets/app.js")


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text(DASHBOARD.read_text(encoding="utf-8"), encoding="utf-8")
    (site / "assets" / "app.js").write_text(APP_JS.read_text(encoding="utf-8"), encoding="utf-8")
    return site


@pytest.fixture
def about(tmp_path: Path) -> str:
    site = _site(tmp_path)
    report = write_about(site)
    assert report["paths"] == ["/about/", "/media/"]
    return (site / "about" / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def media(tmp_path: Path) -> str:
    site = _site(tmp_path / "media-build")
    write_about(site)
    return (site / "media" / "index.html").read_text(encoding="utf-8")


def test_about_carries_its_own_head_metadata(about: str):
    assert (
        "<title>Benchmark Radar: A Living Database and Search Engine for AI Benchmarks "
        "and Evaluation</title>" in about
    )
    assert f'<link rel="canonical" href="{SITE_URL}/about/">' in about
    description = re.search(r'<meta name="description" content="([^"]+)">', about)
    assert description and 70 <= len(description.group(1)) <= 200


def test_about_has_one_h1_and_no_placeholder_text(about: str):
    assert about.count("<h1>") == 1
    for placeholder in ("undefined", "NaN", ">None<", ">null<"):
        assert placeholder not in about


def test_about_marks_its_own_nav_entry_active(about: str):
    """The chrome is the dashboard's, so About must not arrive under Blog."""
    active = re.findall(r'<a class="nav-active"[^>]*href="([^"]+)"', about)
    # The masthead and the footer's Project column both link to /about/.
    assert set(active) == {"/about/"}
    header = re.search(r'<nav class="view-nav".*?</nav>', about, re.S).group(0)
    assert 'aria-current="page" href="/about/"' in header
    assert re.findall(r'href="([^"]+)"', header)[-1] == "/about/"


def test_media_contains_every_coverage_link_from_issue_626(media: str, about: str):
    coverage = re.search(r'<section id="coverage">.*?</section>', media, re.S).group(0)
    for path in (
        "paperswithcode.co/paper/2609.11115",
        "www.arxivdaily.com/universities/sjtu",
        "www.moltbook.com/post/a65591a2-d28d-4f3d-b381-fe2836c4e4c3",
        "www.themoonlight.io/en/review/benchmark-radar-a-living-database-and-search-engine-"
        "for-ai-benchmarks-and-evaluation",
        "www.linkedin.com/posts/chiefscientist_typesafe-ai-daily-benchmark-radar-a-living-"
        "share-7504531089483309056-9uO7/",
        "collected.ga/typesafe-ai-daily-benchmark-radar-a-living-database-and-search-engine-"
        "for-ai-benchmarks-and-eval/",
        "www.alphaxiv.org/abs/2609.11115",
        "x.com/SciFi/status/2098817718036127993",
        "x.com/HuggingPapers/status/2099412410264060340",
        "geepity.com/2609.11115/",
        "x.com/marcel_butucea/status/2098914581204680765",
        "isfahan-ai.ir/news/1248",
        "www.linkedin.com/posts/benchmark-radar-launches-as-centralized-ai-share-"
        "7504478957413527552-jdN_/",
        "dailyaiwire.news/article/benchmark-radar-ai-evaluation-database-search-engine",
        "huggingface.co/papers/2609.11115",
    ):
        assert f'href="https://{path}"' in coverage
    build_log = re.search(
        r"<section><h2>Benchmark Radar elsewhere</h2>.*?</section>", about, re.S
    ).group(0)
    assert 'href="https://koutian.is-a.dev/posts/2026/09/benchmark-radar-day47/"' in build_log
    assert "benchmark-radar-day47" not in coverage
    # One list, one page: About points to Media rather than repeating it.
    assert 'id="coverage"' not in about


def test_media_names_the_contact_for_press(media: str):
    lede = re.search(r'<p class="blog-lede">.*?</p>', media, re.S).group(0)
    assert 'href="mailto:ktwu@utexas.edu"' in lede
    assert "media inquiries" in lede
    assert f'<link rel="canonical" href="{SITE_URL}/media/">' in media
    assert media.count("<h1>") == 1
    active = re.findall(r'<a class="nav-active"[^>]*href="([^"]+)"', media)
    assert set(active) == {"/media/"}


def test_about_links_out_to_the_project_and_the_build_log(about: str):
    for url in (
        "https://github.com/ktwu01/benchmark-radar",
        "https://arxiv.org/abs/2609.11115",
        "https://koutian.is-a.dev/year-archive/",
        "https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en",
    ):
        assert url in about


def test_about_links_into_the_catalog(about: str):
    """An About page that is a dead end wastes the only prose page on the site."""
    for path in ("/benchmarks/", "/leaderboard/", "/blog/", "/cite/", "/media/"):
        assert f'href="{path}"' in about


def test_about_declares_itself_an_about_page(about: str):
    blocks = [
        json.loads(block)
        for block in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', about, re.DOTALL
        )
    ]
    types = {block["@type"] for block in blocks}
    assert types == {"AboutPage", "BreadcrumbList"}
    page = next(block for block in blocks if block["@type"] == "AboutPage")
    # Node references resolve off the homepage only when they carry their type.
    assert page["isPartOf"]["@type"] == "WebSite"
    assert page["about"]["@type"] == "Organization"


def test_publication_aliases_point_at_cite_without_competing_with_it(tmp_path: Path):
    site = _site(tmp_path)
    report = write_about(site)
    assert report["aliases"] == [alias for alias, _ in ALIAS_PATHS]
    for alias, target in ALIAS_PATHS:
        page = (site / alias.strip("/") / "index.html").read_text(encoding="utf-8")
        assert f'content="0; url={target}"' in page
        assert f'<link rel="canonical" href="{SITE_URL}{target}">' in page
        # No noindex beside that canonical. Google's canonicalization guidance
        # is that noindex drops a page from Search rather than folding it into
        # its canonical, which would discard the signal the alias forwards.
        assert "noindex" not in page
        # A reader with no JavaScript and a stalled refresh still has a link.
        assert f'<a href="{target}">' in page


def test_about_is_rewritten_rather_than_merged(tmp_path: Path):
    site = _site(tmp_path)
    write_about(site)
    stale = site / "about" / "stale.html"
    stale.write_text("old", encoding="utf-8")
    write_about(site)
    assert not stale.exists()


def test_about_is_byte_deterministic(tmp_path: Path):
    first = _site(tmp_path / "a")
    second = _site(tmp_path / "b")
    write_about(first)
    write_about(second)
    assert (first / "about" / "index.html").read_bytes() == (
        second / "about" / "index.html"
    ).read_bytes()


def test_the_menu_bar_says_publications_and_keeps_the_cite_path():
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    nav = re.search(r'<nav class="view-nav".*?</nav>', dashboard, re.S).group(0)
    assert 'href="/cite/"' in nav
    assert 'data-i18n="Publications"' in nav
    assert "Publications\n" in nav
    assert 'data-i18n="Cite"' not in nav


def test_the_footer_carries_no_build_stamp(about: str):
    """A build time tells a reader nothing, so the footer dropped it (issue #906)."""
    footer = re.search(r"<footer>.*?</footer>", about, re.S).group(0)
    assert "build-meta" not in footer
    assert "Updated" not in footer
