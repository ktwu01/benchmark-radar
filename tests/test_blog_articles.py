import json
from pathlib import Path

import pytest
from test_blog import APP_JS, DASHBOARD_HTML, _briefed

from benchmark_radar.blog import write_blog
from benchmark_radar.blog_articles import KIND_ARTICLE, load_articles
from benchmark_radar.blog_shell import BLOG_PATH

COMMITTED = Path(__file__).resolve().parents[1] / "data" / "blog_posts"


def _post(root: Path, slug: str, **meta) -> Path:
    folder = root / slug
    folder.mkdir(parents=True)
    fields = {"title": "A written post", "description": "What it says.", "published": "2026-11-23"}
    fields.update(meta)
    (folder / "post.json").write_text(json.dumps(fields), encoding="utf-8")
    (folder / "body.html").write_text(
        '<p>Body.</p><img src="chart.png" alt="chart">', encoding="utf-8"
    )
    (folder / "chart.png").write_bytes(b"png")
    return folder


def _write(site: Path, articles: Path, snapshots=()):
    return write_blog(
        list(snapshots), site, dashboard_html=DASHBOARD_HTML, app_js=APP_JS, articles_dir=articles
    )


def test_a_written_post_is_published_beside_the_briefs_with_its_assets(tmp_path):
    _post(tmp_path / "posts", "levels")
    report = _write(tmp_path / "site", tmp_path / "posts", [_briefed()])
    blog = tmp_path / "site" / "blog"
    page = (blog / "levels" / "index.html").read_text(encoding="utf-8")
    assert "<p>Body.</p>" in page
    assert (blog / "levels" / "chart.png").read_bytes() == b"png"
    assert not (blog / "levels" / "post.json").exists()
    index = (blog / "index.html").read_text(encoding="utf-8")
    assert f'href="{BLOG_PATH}levels/"' in index
    assert f"{BLOG_PATH}levels/" in (blog / "feed.xml").read_text(encoding="utf-8")
    assert (f"{BLOG_PATH}levels/", "2026-11-23") in report["sitemap_entries"]


def test_posts_are_ordered_by_publish_day_not_slug(tmp_path):
    _post(tmp_path / "posts", "zebra", published="2020-01-01")
    _write(tmp_path / "site", tmp_path / "posts", [_briefed()])
    index = (tmp_path / "site" / "blog" / "index.html").read_text(encoding="utf-8")
    assert index.index(f"{BLOG_PATH}{_briefed()['date']}/") < index.index(f"{BLOG_PATH}zebra/")


def test_a_missing_posts_folder_publishes_only_the_briefs(tmp_path):
    report = _write(tmp_path / "site", tmp_path / "absent", [_briefed()])
    assert report["post_count"] == 1


@pytest.mark.parametrize(
    "slug, meta",
    [
        ("2026-08-30", {}),
        ("levels", {"published": "November"}),
        ("levels", {"title": ""}),
        ("levels", {"sources": [{"title": "x", "url": "javascript:alert(1)"}]}),
    ],
)
def test_a_malformed_post_fails_the_build(tmp_path, slug, meta):
    _post(tmp_path / "posts", slug, **meta)
    with pytest.raises(ValueError):
        _write(tmp_path / "site", tmp_path / "posts", [_briefed()])


def test_the_committed_posts_load():
    articles = load_articles(COMMITTED)
    assert articles
    for article in articles:
        assert article.post.kind == KIND_ARTICLE
        assert article.assets
