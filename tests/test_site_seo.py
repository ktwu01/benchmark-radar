import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from benchmark_radar.blog_shell import BLOG_ARCHIVE_PATH, BLOG_PATH
from benchmark_radar.citation import ARXIV_ID, ARXIV_URL, TITLE
from benchmark_radar.feed import SITE_URL
from benchmark_radar.site_about import ABOUT_PATH, ALIAS_PATHS
from benchmark_radar.site_seo import (
    BENCHMARK_DIRECTORY_PATH,
    INDEXABLE_VIEWS,
    sitemap_tree,
    write_sitemap,
)

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def test_sitemap_covers_every_indexable_view():
    tree = sitemap_tree([{"generated_at": "2026-08-21T02:17:00+00:00", "date": "2026-08-21"}])
    root = tree.getroot()
    urls = [node.text for node in root.findall("sm:url/sm:loc", NS)]
    assert urls == [
        f"{SITE_URL}/",
        f"{SITE_URL}/leaderboard/",
        f"{SITE_URL}/saturation/",
        f"{SITE_URL}/trends/",
        f"{SITE_URL}/explore/",
        f"{SITE_URL}/cli/",
        f"{SITE_URL}/cite/",
        f"{SITE_URL}/rubric/",
        f"{SITE_URL}/benchmarks/",
    ]


def test_sitemap_only_lists_app_routes_written_by_this_build():
    root = sitemap_tree(
        [{"generated_at": "2026-08-21T02:17:00+00:00"}],
        view_paths=["/leaderboard/", "/cli/", "/cite/"],
    ).getroot()
    urls = [node.text for node in root.findall("sm:url/sm:loc", NS)]
    assert urls == [
        f"{SITE_URL}/",
        f"{SITE_URL}/leaderboard/",
        f"{SITE_URL}/cli/",
        f"{SITE_URL}/cite/",
        f"{SITE_URL}/benchmarks/",
    ]


def test_sitemap_lastmod_is_derived_from_history_not_the_clock():
    snapshots = [
        {"generated_at": "2026-08-19T23:50:00+00:00"},
        {"generated_at": "2026-08-21T02:17:00+00:00"},
        {"generated_at": "2026-08-20T12:00:00+00:00"},
    ]
    root = sitemap_tree(snapshots).getroot()
    lastmods = [node.text for node in root.findall("sm:url/sm:lastmod", NS)]
    # One date per URL, the newest snapshot's, so two rebuilds over the same
    # history are byte-identical.
    assert lastmods == ["2026-08-21"] * (len(INDEXABLE_VIEWS) + 1)


def test_sitemap_without_snapshots_omits_lastmod():
    root = sitemap_tree([]).getroot()
    assert [node.text for node in root.findall("sm:url/sm:lastmod", NS)] == []
    assert len(root.findall("sm:url", NS)) == len(INDEXABLE_VIEWS) + 1


def test_each_view_has_its_own_title_and_description():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    blocks = [
        script.split(f"const {name} = {{", 1)[1].split("\n};", 1)[0]
        for name in ("VIEW_SEO", "UTILITY_SEO")
    ]
    titles = [title for block in blocks for title in re.findall(r'title: "([^"]+)"', block)]
    descriptions = [
        description
        for block in blocks
        for description in re.findall(r'description:\s*"([^"]+)"', block, flags=re.DOTALL)
    ]
    assert len(titles) == len(INDEXABLE_VIEWS)
    assert len(set(titles)) == len(INDEXABLE_VIEWS)
    assert len(descriptions) == len(INDEXABLE_VIEWS)
    assert len(set(descriptions)) == len(INDEXABLE_VIEWS)

    # Wired inside setView, not beside it: boot, popstate, nav clicks, and
    # fallbacks all route through one place.
    set_view = script.split("function setView(", 1)[1].split("\nfunction ", 1)[0]
    assert "applyCurrentSeo()" in set_view


def test_write_sitemap_writes_valid_xml_beside_the_data(tmp_path):
    output = tmp_path / "site" / "sitemap.xml"
    written = write_sitemap([{"generated_at": "2026-08-21T02:17:00+00:00"}], output)
    assert written == output
    parsed = ET.parse(output)
    assert parsed.getroot().tag == f"{{{NS['sm']}}}urlset"


def test_published_head_and_robots_match_the_generated_sitemap():
    html = Path("site/index.html").read_text(encoding="utf-8")
    robots = Path("site/robots.txt").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Canonical default in the static head; app.js restates it per view.
    assert f'<link rel="canonical" href="{SITE_URL}/">' in html
    assert 'link[rel="canonical"]' in script
    assert 'new URL(seo.canonical, "https://benchmark-radar.org")' in script

    # Each view is published at the path its canonical names; a view added to
    # one side must land on the other.
    for _, path in INDEXABLE_VIEWS:
        assert f'canonical: "{path}"' in script

    # Global navigation and contextual utilities use root-relative links. The
    # generated Explore and Rubric routes remain indexable without global tabs.
    assert 'href="/leaderboard/"' in html
    assert 'href="/trends/"' in html
    assert 'href="/cli/"' in html
    assert 'href="/cite/"' in html
    nav = html.split('<nav class="view-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/explore/"' not in nav
    assert 'href="/rubric/"' not in nav

    # robots.txt points at the sitemap URL the build actually writes.
    sitemap_url = f"{SITE_URL}/sitemap.xml"
    assert sitemap_url in robots
    assert "https://ktwu01.github.io/benchmark-radar" not in html
    assert "https://ktwu01.github.io/benchmark-radar" not in robots
    assert "https://koutian.is-a.dev/benchmark-radar" not in html
    assert "https://koutian.is-a.dev/benchmark-radar" not in robots


def test_structured_data_describes_a_searchable_site_and_a_dataset():
    html = Path("site/index.html").read_text(encoding="utf-8")
    blocks = [
        json.loads(chunk.split(">", 1)[1].split("</script>", 1)[0])
        for chunk in html.split('type="application/ld+json"')[1:]
    ]
    types = {block["@type"] for block in blocks}
    assert {"WebSite", "Dataset"} <= types

    website = next(block for block in blocks if block["@type"] == "WebSite")
    target = website["potentialAction"]["target"]["urlTemplate"]
    # The search endpoint is the leaderboard's real lq filter, not a pretend one.
    assert "{search_term_string}" in target
    assert "/saturation/?bq={search_term_string}" in target
    assert website["potentialAction"]["query-input"] == "required name=search_term_string"

    dataset = next(block for block in blocks if block["@type"] == "Dataset")
    assert dataset["url"].endswith("/data/radar.json")
    distributions = [entry["contentUrl"] for entry in dataset["distribution"]]
    assert dataset["url"] in distributions
    assert dataset["license"].endswith("/MIT")


def test_sitemap_lists_the_blog_with_a_per_brief_lastmod():
    """A brief from three weeks ago did not change when today's snapshot landed."""
    root = sitemap_tree(
        [{"generated_at": "2026-09-01T02:17:00+00:00"}],
        view_paths=[],
        blog_entries=[
            ("/blog/", "2026-09-01"),
            ("/blog/archive/", "2026-09-01"),
            ("/blog/2026-09-01/", "2026-09-01"),
            ("/blog/2026-08-10/", "2026-08-10"),
        ],
    ).getroot()
    entries = {
        node.find("sm:loc", NS).text: getattr(node.find("sm:lastmod", NS), "text", None)
        for node in root.findall("sm:url", NS)
    }
    assert entries[f"{SITE_URL}/blog/"] == "2026-09-01"
    assert entries[f"{SITE_URL}/blog/archive/"] == "2026-09-01"
    assert entries[f"{SITE_URL}/blog/2026-08-10/"] == "2026-08-10"


def test_a_build_that_writes_no_blog_lists_no_blog_urls():
    root = sitemap_tree([{"generated_at": "2026-09-01T02:17:00+00:00"}]).getroot()
    assert not [node.text for node in root.findall("sm:url/sm:loc", NS) if "/blog/" in node.text]


def test_sitemap_dates_a_standalone_page_with_the_site_date():
    """/about/ is prose, so it has no view entry and no brief of its own.

    It travels as a page entry instead, and its date is the site's rather than
    a per-record one: the page is rewritten from the shared chrome on every
    build that writes pages at all.
    """
    root = sitemap_tree(
        [{"generated_at": "2026-09-01T02:17:00+00:00"}],
        view_paths=[],
        page_entries=[(ABOUT_PATH, "2026-09-01")],
    ).getroot()
    entries = {
        node.find("sm:loc", NS).text: getattr(node.find("sm:lastmod", NS), "text", None)
        for node in root.findall("sm:url", NS)
    }
    assert entries[f"{SITE_URL}{ABOUT_PATH}"] == "2026-09-01"


def test_a_data_only_build_lists_no_standalone_pages():
    # Same rule the views and the blog follow: a build that writes no pages
    # passes nothing and lists nothing, rather than promising a crawler a URL
    # this deploy did not publish.
    root = sitemap_tree([{"generated_at": "2026-09-01T02:17:00+00:00"}]).getroot()
    urls = [node.text for node in root.findall("sm:url/sm:loc", NS)]
    assert f"{SITE_URL}{ABOUT_PATH}" not in urls


def test_llms_txt_lists_every_page_the_sitemap_publishes():
    """llms.txt is the hand-written index; the sitemap is generated.

    Nothing tied the two together, so /saturation/ and /about/ reached the
    sitemap and were never added here. An agent reading llms.txt alone could
    not find them. The expected paths are derived from the same constants the
    sitemap builds from, so adding a page to the site fails this test until
    llms.txt describes it.
    """
    llms = Path("site/llms.txt").read_text(encoding="utf-8")
    published = [
        *(path for _, path in INDEXABLE_VIEWS),
        BENCHMARK_DIRECTORY_PATH,
        BLOG_PATH,
        BLOG_ARCHIVE_PATH,
        ABOUT_PATH,
    ]

    for path in published:
        assert f"{SITE_URL}{path})" in llms, f"llms.txt does not link {path}"


def test_llms_txt_sends_agents_to_canonicals_not_redirects():
    # The alias paths exist for a reader who types "publications"; each one is
    # a redirect into /cite/. Naming one here would spend an agent's request on
    # a hop and hand it a non-canonical URL to quote.
    llms = Path("site/llms.txt").read_text(encoding="utf-8")

    for alias, _ in ALIAS_PATHS:
        assert f"{SITE_URL}{alias}" not in llms


def test_llms_txt_names_the_paper_it_asks_agents_to_cite():
    """llms.txt is the first file an agent or answer engine reads.

    The preferred citation is the arXiv report, so the paper has to be named
    there rather than one request deeper behind /cite/. The identifiers come
    from citation.py, so this surface cannot drift from the citation contract.
    """
    llms = Path("site/llms.txt").read_text(encoding="utf-8")

    assert ARXIV_ID in llms
    assert ARXIV_URL in llms
    # Written in arXiv's title case, so compare against citation.py's APA
    # sentence case without pinning the exact casing in two places.
    assert TITLE.lower() in llms.lower()
