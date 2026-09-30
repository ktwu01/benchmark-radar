from pathlib import Path

import pytest

from benchmark_radar.themes import build_theme_groups, write_themes

# The real dashboard and app.js, same contract test_blog.py relies on: a
# fixture copy could drift from what ships.
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DASHBOARD_HTML = (SITE_DIR / "index.html").read_text(encoding="utf-8")
APP_JS = (SITE_DIR / "assets" / "app.js").read_text(encoding="utf-8")


def _snapshot(items):
    return {
        "schema_version": 2,
        "date": "2026-09-10",
        "generated_at": "2026-09-10T00:00:00Z",
        "evidence_items": items,
    }


def _item(**overrides):
    item = {
        "source": "XBsleepy",
        "source_id": "xbsleepy:2609.1",
        "title": "A Drift-Aware Agent Benchmark",
        "url": "https://arxiv.org/abs/2609.1",
        "published_at": "2026-09-09T18:00:00Z",
        "summary": "We present a benchmark.",
        "categories": ["xbsleepy:planning"],
    }
    item.update(overrides)
    return item


def _write_themes(snapshots, tmp_path):
    return write_themes(snapshots, tmp_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)


def test_build_theme_groups_dedupes_and_skips_uncategorized():
    snapshots = [
        _snapshot(
            [
                _item(),
                _item(
                    source_id="xbsleepy:2609.2",
                    url="https://arxiv.org/abs/2609.2",
                    title="Second",
                    categories=["xbsleepy:planning", "xbsleepy:web"],
                ),
                _item(
                    source_id="xbsleepy:2609.3",
                    url="https://arxiv.org/abs/2609.3",
                    title="Untagged",
                    categories=[],
                ),
                _item(
                    source_id="xbsleepy:2609.4",
                    url="https://arxiv.org/abs/2609.4",
                    title="No categories key",
                    categories=None,
                ),
            ]
        )
    ]

    groups = build_theme_groups(snapshots)

    assert [group["category"] for group in groups] == ["xbsleepy:planning", "xbsleepy:web"]
    planning = groups[0]
    assert planning["count"] == 2
    assert [record["title"] for record in planning["records"]] == [
        "A Drift-Aware Agent Benchmark",
        "Second",
    ]
    assert all(record["title"] != "Untagged" for group in groups for record in group["records"])


def test_write_themes_writes_page_with_groups_and_counts(tmp_path):
    report = _write_themes(
        [
            _snapshot(
                [
                    _item(),
                    _item(
                        source_id="xbsleepy:2609.2",
                        url="https://arxiv.org/abs/2609.2",
                        title="Second",
                        categories=["xbsleepy:planning", "xbsleepy:web"],
                    ),
                ]
            )
        ],
        tmp_path,
    )

    assert report["path"] == "/themes/"
    assert report["categories"] == 2
    assert report["records"] == 2
    page = (tmp_path / "themes" / "index.html").read_text(encoding="utf-8")
    assert "xbsleepy:planning" in page
    assert "xbsleepy:web" in page
    assert "Browse benchmarks by theme" in page
    # The chrome contract runs both ways: the page carries the site nav, and
    # the nav marks /themes/ active on the page.
    assert 'href="/themes/"' in page
    assert not (tmp_path / "themes.staging").exists()


def test_write_themes_renders_empty_state_without_tagged_records(tmp_path):
    report = _write_themes([_snapshot([_item(categories=[])])], tmp_path)

    assert report["categories"] == 0
    page = (tmp_path / "themes" / "index.html").read_text(encoding="utf-8")
    assert "No tagged records yet." in page


def test_write_themes_refuses_a_dashboard_without_the_footer_link(tmp_path):
    # If the dashboard drops the /themes/ link, the chrome extractor must
    # refuse loudly rather than publish a page that claims a section the
    # site's nav no longer has.
    linkless = DASHBOARD_HTML.replace('<a href="/themes/" data-i18n="Themes">Themes</a>', "")

    with pytest.raises(ValueError):
        write_themes([_snapshot([_item()])], tmp_path, dashboard_html=linkless, app_js=APP_JS)


def test_dashboard_footer_keeps_the_themes_link():
    # Same contract, dashboard side: this assertion breaks when someone
    # removes the footer link, before any build run gets to fail obscurely.
    assert 'href="/themes/"' in DASHBOARD_HTML
