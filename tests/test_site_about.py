"""The /about/ page and the /publication(s)/ aliases (issue #593)."""

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
    report = write_about(site, updated="2026-09-11")
    assert report["paths"] == ["/about/"]
    return (site / "about" / "index.html").read_text(encoding="utf-8")


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
    assert active == ["/about/"]


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
    for path in ("/benchmarks/", "/leaderboard/", "/blog/", "/cite/"):
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
    report = write_about(site, updated="2026-09-11")
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
    write_about(site, updated="2026-09-11")
    stale = site / "about" / "stale.html"
    stale.write_text("old", encoding="utf-8")
    write_about(site, updated="2026-09-12")
    assert not stale.exists()


def test_about_is_byte_deterministic(tmp_path: Path):
    first = _site(tmp_path / "a")
    second = _site(tmp_path / "b")
    write_about(first, updated="2026-09-11")
    write_about(second, updated="2026-09-11")
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


def test_about_is_written_even_before_the_corpus_has_a_date(tmp_path: Path):
    """The nav links to /about/ from every page, so it can never be skipped."""
    site = _site(tmp_path)
    write_about(site, updated=None)
    page = (site / "about" / "index.html").read_text(encoding="utf-8")
    assert "<h1>" in page
    # No date means no stamp, rather than a footer that says "Updated" and stops.
    assert '<p id="build-meta">' not in page
