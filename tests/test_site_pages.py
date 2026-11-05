"""Static per-benchmark pages (issue #424) and their sitemap entries.

The pages are generated from the shards, never committed, and tested hermetically
against fabricated shards in tmp_path fixtures. They must be byte-deterministic,
escape every value they render, never emit placeholder text for missing fields,
and fail loudly rather than silently writing an empty directory.
"""

import json
import re
from pathlib import Path

import pytest

from benchmark_radar.cards import benchmark_card_url
from benchmark_radar.feed import SITE_URL
from benchmark_radar.site_pages import (
    benchmark_page_urls,
    benchmark_sitemap_entries,
    write_benchmark_pages,
)
from benchmark_radar.site_seo import sitemap_tree


def _shard(
    slug: str,
    name: str,
    *,
    source: str = "test_source",
    description: str | None = None,
    categories: list[str] | None = None,
    publisher: str | None = None,
    released: str | None = None,
    modality: str | None = None,
    scores: list[dict] | None = None,
    provenance: dict | None = None,
) -> dict:
    record = {
        "slug": slug,
        "name": name,
        "key": f"{source}:{slug}",
        "source": source,
        "categories": categories or [],
        "modality": modality,
        "publisher": publisher,
        "released": released,
        "openness": {"status": "unknown", "code_license": None, "data_license": None},
        "description": {"en": description} if description else {},
        "provenance": provenance or {},
    }
    scores_by_source = {source: {"rows": scores or [], "series": {}}} if scores else {}
    return {
        "schema_version": 1,
        "record": record,
        "siblings": [],
        "scores_by_source": scores_by_source,
    }


def _write_shards(tmp_path: Path, *shards: dict) -> Path:
    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    for shard in shards:
        (shard_dir / f"{shard['record']['slug']}.json").write_text(
            json.dumps(shard, ensure_ascii=False), encoding="utf-8"
        )
    return shard_dir


def _generated_pages(tmp_path: Path, *shards: dict) -> Path:
    shard_dir = _write_shards(tmp_path, *shards)
    output = tmp_path / "site" / "benchmarks"
    write_benchmark_pages(shard_dir, output)
    return output


def _page_text(output: Path, slug: str) -> str:
    return (output / slug / "index.html").read_text(encoding="utf-8")


def _jsonld_blocks(html: str) -> list[dict]:
    return [
        json.loads(chunk.split(">", 1)[1].split("</script>", 1)[0])
        for chunk in html.split('type="application/ld+json"')[1:]
    ]


def test_writes_one_page_per_shard_plus_directory(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench"),
        _shard("beta-bench", "Beta Bench"),
    )
    assert (output / "alpha-bench" / "index.html").exists()
    assert (output / "beta-bench" / "index.html").exists()
    assert (output / "index.html").exists()


def test_benchmark_pages_share_the_dashboard_shell_without_duplicate_navigation(tmp_path):
    from benchmark_radar.blog_shell import extract_site_chrome

    dashboard = Path("site/index.html").read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard, active_path="/saturation/")
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    page = _page_text(output, "alpha-bench")
    directory = (output / "index.html").read_text(encoding="utf-8")
    for text in (page, directory):
        assert chrome.header in text
        assert chrome.footer in text
        assert text.count("<footer>") == 1
        assert '<nav class="site">' not in text
        assert 'id="main-content"' in text
        assert 'src="/assets/blog.js"' in text
        assert text.count('src="/assets/clarity.js"') == 1
    assert page.count('class="record-history-link"') == 1
    assert f'href="{SITE_URL}/saturation/?lfrontier=alpha-bench"' in page


def test_pages_build_when_invoked_outside_repository(tmp_path, monkeypatch):
    # Callers selecting a custom shard/output directory cannot rely on the shell's cwd.
    shard_dir = _write_shards(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    output = tmp_path / "pages"
    monkeypatch.chdir(tmp_path)
    write_benchmark_pages(shard_dir, output)
    assert "Alpha Bench" in _page_text(output, "alpha-bench")


def test_output_is_byte_deterministic(tmp_path):
    shard_dir = _write_shards(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_benchmark_pages(shard_dir, first)
    write_benchmark_pages(shard_dir, second)
    for path in sorted(p.relative_to(first) for p in first.rglob("index.html")):
        assert (second / path).read_bytes() == (first / path).read_bytes()


def test_unscored_page_does_not_advertise_results_from_an_empty_bucket(tmp_path):
    shard = _shard("alpha-bench", "Alpha Bench")
    shard["scores_by_source"] = {"test_source": {"rows": [], "series": {}}}

    output = _generated_pages(tmp_path, shard)
    page = _page_text(output, "alpha-bench")

    assert "Results" not in page.split("</title>", 1)[0]
    assert "No reported scores are on record" in page


def test_page_shows_importer_original_evidence_and_review_status(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            source="claire_radar",
            provenance={
                "source_url": "https://example.org/original-record",
                "review_state": "source-reviewed",
            },
        ),
    )
    page = _page_text(output, "alpha-bench")

    assert "Importer" in page
    assert "Claire Radar" in page
    assert "Original evidence" in page
    assert 'href="https://example.org/original-record"' in page
    assert "Review status" in page
    assert "source-reviewed" in page


@pytest.mark.parametrize("source_url", ["javascript:alert(1)", "data:text/html,x", "http://["])
def test_page_omits_unsafe_original_evidence_links(tmp_path, source_url):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            source="claire_radar",
            provenance={"source_url": source_url},
        ),
    )
    page = _page_text(output, "alpha-bench")

    assert "Original evidence" not in page
    assert source_url not in page


def test_page_has_unique_title_and_canonical(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench"),
        _shard("beta-bench", "Beta Bench"),
    )
    alpha = _page_text(output, "alpha-bench")
    beta = _page_text(output, "beta-bench")
    assert "<title>Alpha Bench: What It Tests | Benchmark Radar</title>" in alpha
    assert "<title>Beta Bench: What It Tests | Benchmark Radar</title>" in beta
    assert alpha.split("<title>")[1] != beta.split("<title>")[1]
    assert (
        '<link rel="canonical" href="https://benchmark-radar.org/benchmarks/alpha-bench/">' in alpha
    )


def test_benchmark_and_directory_pages_declare_the_same_share_card_as_the_homepage(tmp_path):
    # Issue #891: a deep link shared on X should get the same large card as the
    # homepage, so every head carries the image, its size and twitter:image.
    # A benchmark page carries its own card (issue #671) in the same block.
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    homepage = Path("site/index.html").read_text(encoding="utf-8")

    def expected(card):
        return [
            f'<meta property="og:image" content="{card}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:image" content="{card}">',
        ]

    site_card = f"{SITE_URL}/assets/og-card.png"
    for tag in expected(site_card):
        assert tag in homepage
        assert tag in (output / "index.html").read_text("utf-8")
    for tag in expected(benchmark_card_url("alpha-bench")):
        assert tag in _page_text(output, "alpha-bench")


def test_interactive_view_link_lands_on_saturation_with_the_slug(tmp_path):
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    page = _page_text(output, "alpha-bench")
    # The permalink needs the leaderboard page, not a bare lfrontier query on
    # the root, which opens the default Today view and cannot resolve the slug.
    assert 'href="https://benchmark-radar.org/saturation/?lfrontier=alpha-bench"' in page
    assert "?lfrontier=alpha-bench" not in page.replace("/saturation/?lfrontier=alpha-bench", "")


def test_page_previews_and_shares_its_own_benchmark_card(tmp_path):
    output = _generated_pages(tmp_path, _shard("gpqa", "GPQA <Diamond>"))
    html = _page_text(output, "gpqa")
    # On the page's own host: X showed no preview for a card on another host (#891).
    card = "https://benchmark-radar.org/cards/gpqa.png"
    assert f'<meta property="og:image" content="{card}">' in html
    # Hidden until share-card.js wakes it, so no reader meets a dead control.
    button = re.search(r"<button[^>]*data-share-benchmark=[^>]*>", html).group(0)
    assert 'data-share-benchmark="gpqa"' in button
    assert 'data-name="GPQA &lt;Diamond&gt;"' in button
    assert " hidden" in button
    assert '<script src="/assets/share-card.js" type="module"></script>' in html


def test_card_urls_agree_between_the_build_and_the_browser():
    script = Path("site/assets/share-card.js").read_text(encoding="utf-8")
    base = re.search(r'CARDS_URL =\s*"([^"]+)"', script).group(1)
    # The browser asks its own origin for the card the page names.
    assert benchmark_card_url("gpqa") == f"{SITE_URL}{base}/gpqa.png"


def test_description_is_present_and_derived_from_the_shard(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            description="A tough reasoning test with a long tail.",
        ),
        _shard("beta-bench", "Beta Bench"),
    )
    alpha = _page_text(output, "alpha-bench")
    beta = _page_text(output, "beta-bench")
    assert "A tough reasoning test with a long tail." in alpha
    assert '<meta name="description" content="' in alpha
    assert beta.count('<meta name="description" content="') == 1
    assert len(beta.split('content="', 1)[1].split('"', 1)[0]) <= 160


def test_visible_overview_is_complete_and_has_no_observation_count(tmp_path):
    description = (
        "A benchmark of scientific reasoning across biology, chemistry and physics. "
        "Each question requires specialist knowledge and has been checked by independent experts. "
        "The final sentence explains the evaluation task in full."
    )
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench", description=description, scores=[{"value": 0}]),
        _shard("beta-bench", "Beta Bench", scores=[{"value": 0}]),
    )
    page = _page_text(output, "alpha-bench")
    assert f'<p class="lede">{description}</p>' in page
    assert "<h2>About Alpha Bench</h2>" not in page
    assert len(page.split('name="description" content="')[1].split('"')[0]) <= 160
    overview = page.split('<p class="lede">')[1].split("</section>")[0]
    assert "Reported scores" not in overview
    fallback = _page_text(output, "beta-bench").split('<p class="lede">')[1].split("</p>")[0]
    assert fallback == "Beta Bench is an AI benchmark in the Benchmark Radar catalog."


def test_score_evidence_is_complete_inside_closed_source_disclosures(tmp_path):
    shard = _shard("alpha-bench", "Alpha Bench", scores=[{"model_name": "Zero", "value": 0}])
    shard["scores_by_source"]["llm_stats"] = {
        "rows": [{"model_name": "Other model", "value": 42}],
        "series": {},
    }
    page = _page_text(_generated_pages(tmp_path, shard), "alpha-bench")
    disclosures = re.findall(r'<details class="record-scores">(.*?)</details>', page, re.S)
    assert len(disclosures) == 2
    for disclosure in disclosures:
        summary = disclosure.split("</summary>")[0]
        assert "Reported benchmark scores · " in summary
        assert "Reported scores: 1" not in summary
        assert "Reported scores: 1" in disclosure
        assert "<table>" in disclosure
        assert disclosure.count("<tbody><tr>") == 1
    assert any("Zero</td>" in part and "<td>0</td>" in part for part in disclosures)
    assert any("Other model</td>" in part for part in disclosures)
    assert 'record-scores" open' not in page


def test_jsonld_blocks_are_single_objects_with_expected_types(tmp_path):
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    blocks = _jsonld_blocks(_page_text(output, "alpha-bench"))
    types = [block["@type"] for block in blocks]
    assert types == ["WebPage", "BreadcrumbList"]
    webpage = blocks[0]
    assert webpage["@id"] == "https://benchmark-radar.org/benchmarks/alpha-bench/"
    assert webpage["about"]["name"] == "Alpha Bench"
    crumbs = [item["name"] for item in blocks[1]["itemListElement"]]
    assert crumbs == ["Benchmark Radar", "Benchmark directory", "Alpha Bench"]


def test_benchmark_is_described_as_a_dataset_from_its_own_fields(tmp_path):
    """Answer engines cite the paper and the publisher, so both reach the markup."""
    shard = _shard(
        "alpha-bench",
        "Alpha Bench",
        description="A tough reasoning test.",
        categories=["math", "Official"],
        released="2025-03-04",
    )
    shard["record"]["publisher"] = {"name": "Alpha Lab", "role": "hub_publisher"}
    shard["record"]["artifacts"] = [
        {"kind": "repo", "url": "https://github.com/alpha/bench"},
        {"kind": "paper", "url": "https://arxiv.org/abs/2501.00001"},
    ]
    output = _generated_pages(tmp_path, shard, _shard("beta-bench", "Beta Bench"))
    alpha_text = _page_text(output, "alpha-bench")
    webpage = _jsonld_blocks(alpha_text)[0]
    entity = webpage["about"]
    assert entity["@type"] == "Dataset"
    assert entity["@id"] == "https://benchmark-radar.org/benchmarks/alpha-bench/#benchmark"
    assert webpage["mainEntity"] == {"@type": "Dataset", "@id": entity["@id"]}
    assert entity["citation"] == ["https://arxiv.org/abs/2501.00001"]
    assert entity["sameAs"] == ["https://github.com/alpha/bench"]
    assert entity["publisher"] == {"@type": "Organization", "name": "Alpha Lab"}
    assert entity["datePublished"] == "2025-03-04"
    assert entity["keywords"] == ["math"]
    # Score dates are evidence dates, not when the page changed, so no
    # modification time is claimed.
    assert "dateModified" not in webpage
    assert (
        '<link rel="alternate" type="application/json" '
        'href="https://benchmark-radar.org/data/benchmarks/alpha-bench.json">'
    ) in alpha_text

    beta = _jsonld_blocks(_page_text(output, "beta-bench"))[0]
    for missing in ("citation", "sameAs", "publisher", "datePublished", "keywords"):
        assert missing not in beta["about"]


def test_object_publisher_reaches_the_visible_facts(tmp_path):
    """The Publisher fact reads publisher["name"]; an object is not a missing value (#982)."""
    shard = _shard("alpha-bench", "Alpha Bench", categories=["math"])
    shard["record"]["publisher"] = {
        "name": "mbzuai",
        "role": "hub_publisher",
        "locator": "detail.basicInfo.publishOrg",
    }
    string_shard = _shard("beta-bench", "Beta Bench", publisher="Beta Lab")
    output = _generated_pages(tmp_path, shard, string_shard)
    alpha = _page_text(output, "alpha-bench")
    assert "<dt>Publisher</dt><dd>mbzuai</dd>" in alpha
    assert "published by mbzuai" in alpha
    assert "<dt>Publisher</dt><dd>Beta Lab</dd>" in _page_text(output, "beta-bench")


def test_node_references_carry_their_own_type_so_they_resolve_off_the_homepage(tmp_path):
    """A bare `@id` resolves nowhere but the homepage, which Search Console rejects."""
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    directory = (output / "index.html").read_text(encoding="utf-8")
    for text in (_page_text(output, "alpha-bench"), directory):
        part_of = _jsonld_blocks(text)[0]["isPartOf"]
        assert part_of["@type"] == "WebSite"
        assert part_of["@id"] == "https://benchmark-radar.org/#website"
        assert part_of["url"] == "https://benchmark-radar.org/"


def test_values_are_escaped_and_cannot_inject_markup(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha <script>alert(1)</script>",
            description="Cross-site <script>description</script> payload",
            publisher='"><img src=x onerror=alert(2)>',
        ),
    )
    page = _page_text(output, "alpha-bench")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x onerror" not in page
    assert "payload</script>" not in page
    # two JSON-LD blocks, chrome data, two chrome scripts and share-card.js
    assert page.count("</script>") == 6


def test_no_placeholder_text_for_missing_fields(tmp_path):
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    page = _page_text(output, "alpha-bench")
    for token in ("undefined", "None", "NaN", "null"):
        assert token not in page.lower()
    assert "Description unavailable" not in page


def test_zero_score_is_rendered_not_replaced(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            scores=[{"model_name": "Model-X", "organization": "Org", "raw_value": "0", "value": 0}],
        ),
    )
    page = _page_text(output, "alpha-bench")
    assert "<td>0</td>" in page
    assert "<td>—</td>" not in page.split("Reported value", 1)[1].split("</tr>", 1)[0]


def test_scores_are_partitioned_by_source(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            source="llm_stats",
            scores=[
                {"model_name": "A", "organization": "OrgA", "raw_value": "0.6", "value": 0.6},
                {"model_name": "B", "organization": "OrgB", "raw_value": "0.4", "value": 0.4},
            ],
        ),
    )
    page = _page_text(output, "alpha-bench")
    assert "LLM Stats" in page
    assert "llm_stats" not in page
    assert "never merged into a single cross-source ranking" in page
    evidence = page.split('<details class="record-scores">', 1)[1].split("</details>")[0]
    assert '<p class="caveat">Reported scores: 2</p>' in evidence
    assert "<dt>Reported scores</dt>" not in page


def test_directory_page_lists_every_benchmark(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("zeta-bench", "Zeta Bench"),
        _shard("alpha-bench", "Alpha Bench"),
    )
    directory = (output / "index.html").read_text(encoding="utf-8")
    assert "<title>Benchmark directory · Benchmark Radar</title>" in directory
    assert "Alpha Bench" in directory and "Zeta Bench" in directory
    assert directory.index("Alpha Bench") < directory.index("Zeta Bench")
    assert "2 benchmarks" in directory
    assert '<a href="https://benchmark-radar.org/benchmarks/alpha-bench/">' in directory


def test_benchmark_page_urls_are_sorted_canonicals(tmp_path):
    shard_dir = _write_shards(
        tmp_path,
        _shard("zeta-bench", "Zeta Bench"),
        _shard("alpha-bench", "Alpha Bench"),
    )
    urls = benchmark_page_urls(shard_dir)
    assert urls == [
        f"{SITE_URL}/benchmarks/alpha-bench/",
        f"{SITE_URL}/benchmarks/zeta-bench/",
    ]
    assert benchmark_page_urls(tmp_path / "missing") == []


def test_sitemap_includes_benchmark_pages_when_entries_are_passed(tmp_path):
    tree = sitemap_tree(
        [{"generated_at": "2026-08-21T02:17:00+00:00"}],
        [("/benchmarks/alpha-bench/", "2025-05-22"), ("/benchmarks/zeta-bench/", None)],
    )
    urls = [
        node.text
        for node in tree.getroot().findall(
            "sm:url/sm:loc", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        )
    ]
    assert urls == [
        f"{SITE_URL}/",
        f"{SITE_URL}/library/",
        f"{SITE_URL}/models/",
        f"{SITE_URL}/trends/",
        f"{SITE_URL}/saturation/",
        f"{SITE_URL}/leaderboard/",
        f"{SITE_URL}/explore/",
        f"{SITE_URL}/cli/",
        f"{SITE_URL}/cite/",
        f"{SITE_URL}/rubric/",
        f"{SITE_URL}/benchmarks/",
        f"{SITE_URL}/benchmarks/alpha-bench/",
        f"{SITE_URL}/benchmarks/zeta-bench/",
    ]
    lastmods = [
        node.text
        for node in tree.getroot().findall(
            "sm:url/sm:lastmod", {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        )
    ]
    # Eleven site-wide dates, then the benchmark's own; the undated page gets none.
    assert lastmods == ["2026-08-21"] * 11 + ["2025-05-22"]


def test_benchmark_lastmod_comes_from_the_pages_own_evidence(tmp_path):
    """A page is not modified by another benchmark's snapshot landing."""
    shard_dir = _write_shards(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench", released="2024-02-01"),
        _shard("zeta-bench", "Zeta Bench", released=None),
    )
    alpha = json.loads((shard_dir / "alpha-bench.json").read_text(encoding="utf-8"))
    alpha["scores_by_source"] = {
        "model_reports": {
            "rows": [
                {"reported_date": "2025-05-22"},
                {"reported_date": "2026-01-09"},
                {"reported_date": "not a date"},
                # Right shape, no such day. It must not reach the sitemap.
                {"reported_date": "2026-02-30"},
            ]
        }
    }
    (shard_dir / "alpha-bench.json").write_text(json.dumps(alpha), encoding="utf-8")

    assert benchmark_sitemap_entries(shard_dir) == [
        ("/benchmarks/alpha-bench/", "2026-01-09"),
        ("/benchmarks/zeta-bench/", None),
    ]
    assert benchmark_sitemap_entries(tmp_path / "missing") == []


def test_write_benchmark_pages_fails_loudly_without_shards(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_benchmark_pages(tmp_path / "missing", tmp_path / "out")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        write_benchmark_pages(empty, tmp_path / "out")


def test_path_traversal_slug_is_rejected(tmp_path):
    shard_dir = _write_shards(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    (shard_dir / "..%2fescape.json").write_text(
        json.dumps(_shard("../escape", "Escape")), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        write_benchmark_pages(shard_dir, tmp_path / "out")


def test_slug_outside_the_slug_alphabet_is_rejected(tmp_path):
    """A slug reaches URLs and attributes unescaped, so the guard is the alphabet."""
    shard_dir = _write_shards(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    (shard_dir / "quoted.json").write_text(
        json.dumps(_shard('alpha" onload="x', "Quoted")), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        write_benchmark_pages(shard_dir, tmp_path / "out")


def _artifact_shard(slug: str, name: str, kinds: list[str], **kwargs) -> dict:
    shard = _shard(slug, name, **kwargs)
    shard["record"]["artifacts"] = [
        {"kind": kind, "url": f"https://example.org/{slug}/{kind}"} for kind in kinds
    ]
    return shard


def test_title_lists_only_the_search_intents_the_page_can_answer(tmp_path):
    """A title promising a dataset link on a page without one is a rewritten title."""
    output = _generated_pages(
        tmp_path,
        _artifact_shard("alpha-bench", "Alpha Bench", ["paper", "repo"]),
        _artifact_shard(
            "gpqa",
            "GPQA",
            ["dataset"],
            scores=[{"model_name": "A", "raw_value": "0.6", "value": 0.6}],
        ),
    )
    alpha = _page_text(output, "alpha-bench")
    gpqa = _page_text(output, "gpqa")
    assert "<title>Alpha Bench: Paper &amp; Code | Benchmark Radar</title>" in alpha
    # "GPQA" carries no "bench", so the word a reader types is added to it.
    assert "<title>GPQA Benchmark: Dataset &amp; Results | Benchmark Radar</title>" in gpqa


def test_a_name_used_by_two_sources_gets_two_distinct_titles(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("mvbench-llm-stats", "MVBench", source="llm_stats"),
        _shard("mvbench-opencompass", "MVBench", source="opencompass_hub"),
    )
    first = _page_text(output, "mvbench-llm-stats")
    second = _page_text(output, "mvbench-opencompass")
    assert "MVBench (LLM Stats)" in first
    assert "MVBench (OpenCompass Hub)" in second
    assert first.split("<title>")[1] != second.split("<title>")[1]


def test_artifact_links_are_published_instead_of_staying_in_the_shard(tmp_path):
    output = _generated_pages(
        tmp_path, _artifact_shard("alpha-bench", "Alpha Bench", ["paper", "repo", "dataset"])
    )
    page = _page_text(output, "alpha-bench")
    assert "<h2>Alpha Bench paper, code and dataset</h2>" in page
    for kind in ("paper", "repo", "dataset"):
        assert f'href="https://example.org/alpha-bench/{kind}"' in page


def test_resource_chips_share_marks_and_only_remove_repeated_destinations(tmp_path):
    shard = _shard("alpha-bench", "Alpha Bench")
    shard["record"]["artifacts"] = [
        {"kind": "repo", "url": "https://github.com/example/bench"},
        {"kind": "repo", "url": " https://github.com/example/bench "},
        {"kind": "repo", "url": "https://www.github.com/example/other"},
        {"kind": "paper", "url": "https://arxiv.org/abs/example"},
        {"kind": "dataset", "url": "https://huggingface.co/datasets/example/bench"},
        {"kind": "paper", "url": "ftp://example.org/paper"},
        {"kind": "website", "url": "https://github.com.example.org/bench"},
    ]
    shard["record"]["provenance"] = {"source_url": "https://github.com/example/bench"}
    page = _page_text(_generated_pages(tmp_path, shard), "alpha-bench")
    assert page.count('href="https://github.com/example/bench"') == 1
    assert 'href="https://www.github.com/example/other"' in page
    for brand in ("github", "arxiv", "huggingface"):
        assert f'href="/assets/source-icons.svg#{brand}"' in page
    assert 'aria-label="Code · https://github.com/example/bench · GitHub"' in page
    assert 'aria-label="Code · https://www.github.com/example/other · GitHub"' in page
    assert 'aria-label="Website · github.com.example.org"' in page
    assert "Original evidence" not in page
    assert 'href="ftp://example.org/paper"' not in page


def test_related_benchmarks_link_siblings_in_the_same_category(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench", categories=["coding_agent"]),
        _shard("beta-bench", "Beta Bench", categories=["coding_agent"]),
        _shard("gamma-bench", "Gamma Bench", categories=["safety"]),
    )
    alpha = _page_text(output, "alpha-bench")
    assert "<h2>Related coding agent benchmarks</h2>" in alpha
    assert f'href="{SITE_URL}/benchmarks/beta-bench/"' in alpha
    assert "gamma-bench" not in alpha
    # A page never lists itself as its own neighbour: the only self-reference
    # left is the canonical URL in the head.
    assert alpha.count(f'href="{SITE_URL}/benchmarks/alpha-bench/"') == 1


def _related_targets(page: str) -> list[str]:
    section = page.split("<h2>Related", 1)[1].split("</ul>", 1)[0]
    return [chunk.split("/", 1)[0] for chunk in section.split(f"{SITE_URL}/benchmarks/")[1:]]


def test_related_links_spread_across_a_category_instead_of_its_alphabetical_head(tmp_path):
    """Issue #673: name order sent every page's links to the same eight pages."""
    shards = [
        _shard(f"bench-{index:02d}", f"Bench {index:02d}", categories=["coding_agent"])
        for index in range(20)
    ]
    output = _generated_pages(tmp_path, *shards)
    linked = {
        target
        for shard in shards
        for target in _related_targets(_page_text(output, shard["record"]["slug"]))
    }
    # Name order reached 9 of 20 pages; equal candidates must now spread.
    assert len(linked) >= 15


def test_a_shared_artifact_outranks_alphabetically_earlier_category_siblings(tmp_path):
    siblings = [
        _shard(f"a-bench-{index}", f"A Bench {index}", categories=["coding_agent"])
        for index in range(10)
    ]
    alpha = _shard("alpha-tasks", "Alpha Tasks", categories=["coding_agent"])
    zeta = _shard("zeta-bench", "Zeta Bench", categories=["coding_agent"])
    shared = [{"kind": "paper", "url": "https://arxiv.org/abs/2601.00001"}]
    alpha["record"]["artifacts"] = shared
    zeta["record"]["artifacts"] = shared
    output = _generated_pages(tmp_path, *siblings, alpha, zeta)
    assert _related_targets(_page_text(output, "alpha-tasks"))[0] == "zeta-bench"


def test_status_tags_do_not_relate_benchmarks(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench", categories=["Unsupported", "不支持"]),
        _shard("beta-bench", "Beta Bench", categories=["Unsupported", "不支持"]),
    )
    assert "beta-bench" not in _page_text(output, "alpha-bench")


def test_citing_documents_are_listed_with_their_sources(tmp_path):
    shard = _shard("alpha-bench", "Alpha Bench")
    shard["record"]["documents"] = [
        {
            "title": "Claude Opus 5",
            "organization": "Anthropic",
            "published": "2026-07-24",
            "source_url": "https://example.org/opus-5",
        }
    ]
    output = _generated_pages(tmp_path, shard)
    page = _page_text(output, "alpha-bench")
    assert "<h2>Which sources cite Alpha Bench?</h2>" in page
    assert 'href="https://example.org/opus-5"' in page


def test_a_two_word_category_description_is_padded_with_real_evidence(tmp_path):
    """`Coding` describes nothing and reads identically on forty other pages."""
    output = _generated_pages(
        tmp_path,
        _shard(
            "alpha-bench",
            "Alpha Bench",
            description="Coding",
            scores=[{"model_name": "A", "raw_value": "0.6", "value": 0.6}],
        ),
    )
    description = _page_text(output, "alpha-bench").split('name="description" content="')[1]
    description = description.split('"')[0]
    assert description.startswith("Coding.")
    assert "1 reported scores" in description


def test_page_publishes_recorded_audits_with_receipts(tmp_path):
    shard = _shard("alpha-bench", "Alpha Bench")
    shard["record"]["audits"] = [
        {
            "auditor": "June Kim",
            "audit_date": "2026-05-24",
            "audit_url": "https://example.com/alpha-audit",
            "finding": "Some Alpha instances cannot run.",
            "receipts": ["https://example.com/alpha-receipt"],
        }
    ]
    output = _generated_pages(tmp_path, shard)
    page = _page_text(output, "alpha-bench")
    assert "Independent audits of Alpha Bench" in page
    assert "Some Alpha instances cannot run." in page
    assert 'href="https://example.com/alpha-audit"' in page
    assert 'href="https://example.com/alpha-receipt"' in page


def test_page_without_audits_has_no_audits_section(tmp_path):
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    assert "Independent audits" not in _page_text(output, "alpha-bench")
