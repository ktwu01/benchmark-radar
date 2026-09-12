"""Static per-benchmark pages (issue #424) and their sitemap entries.

The pages are generated from the shards, never committed, and tested hermetically
against fabricated shards in tmp_path fixtures. They must be byte-deterministic,
escape every value they render, never emit placeholder text for missing fields,
and fail loudly rather than silently writing an empty directory.
"""

import json
from pathlib import Path

import pytest

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


def test_output_is_byte_deterministic(tmp_path):
    shard_dir = _write_shards(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_benchmark_pages(shard_dir, first)
    write_benchmark_pages(shard_dir, second)
    for path in sorted(p.relative_to(first) for p in first.rglob("index.html")):
        assert (second / path).read_bytes() == (first / path).read_bytes()


def test_page_has_unique_title_and_canonical(tmp_path):
    output = _generated_pages(
        tmp_path,
        _shard("alpha-bench", "Alpha Bench"),
        _shard("beta-bench", "Beta Bench"),
    )
    alpha = _page_text(output, "alpha-bench")
    beta = _page_text(output, "beta-bench")
    assert "<title>Alpha Bench · Benchmark Radar</title>" in alpha
    assert "<title>Beta Bench · Benchmark Radar</title>" in beta
    assert alpha.split("<title>")[1] != beta.split("<title>")[1]
    assert (
        '<link rel="canonical" href="https://benchmark-radar.org/benchmarks/alpha-bench/">' in alpha
    )


def test_interactive_view_link_lands_on_saturation_with_the_slug(tmp_path):
    output = _generated_pages(tmp_path, _shard("alpha-bench", "Alpha Bench"))
    page = _page_text(output, "alpha-bench")
    # The permalink needs the leaderboard page, not a bare lfrontier query on
    # the root, which opens the default Today view and cannot resolve the slug.
    assert 'href="https://benchmark-radar.org/saturation/?lfrontier=alpha-bench"' in page
    assert "?lfrontier=alpha-bench" not in page.replace("/saturation/?lfrontier=alpha-bench", "")


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
    assert page.count("</script>") == 2  # one per JSON-LD block, no injected markup


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
    assert "llm_stats" in page
    assert "never merged into a single cross-source ranking" in page
    assert "<dt>Reported scores</dt><dd>2</dd>" in page


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
        f"{SITE_URL}/leaderboard/",
        f"{SITE_URL}/saturation/",
        f"{SITE_URL}/trends/",
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
    # Nine site-wide dates, then the benchmark's own; the undated page gets none.
    assert lastmods == ["2026-08-21"] * 9 + ["2025-05-22"]


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
