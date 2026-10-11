import re
from pathlib import Path

import pytest

from benchmark_radar.themes import build_theme_index, write_themes

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
        "source_tags": ["xbsleepy:planning"],
    }
    item.update(overrides)
    return item


def _write_themes(snapshots, tmp_path):
    return write_themes(snapshots, tmp_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)


def test_build_theme_index_groups_by_source_tag_and_accounts_for_unthemed():
    snapshots = [
        _snapshot(
            [
                _item(),
                _item(
                    source_id="xbsleepy:2609.2",
                    url="https://arxiv.org/abs/2609.2",
                    title="Second",
                    source_tags=["xbsleepy:planning", "xbsleepy:web"],
                ),
                _item(
                    source_id="xbsleepy:2609.3",
                    url="https://arxiv.org/abs/2609.3",
                    title="Untagged",
                    source_tags=[],
                ),
                _item(
                    source_id="xbsleepy:2609.4",
                    url="https://arxiv.org/abs/2609.4",
                    title="No source_tags key",
                    source_tags=None,
                ),
                # The pipeline's own keyword classification is not a source
                # theme. A record carrying only that must count as unthemed
                # here, or the page groups by the local taxonomy while
                # advertising the source's.
                _item(
                    source_id="xbsleepy:2609.5",
                    url="https://arxiv.org/abs/2609.5",
                    title="Keyword classified only",
                    source_tags=[],
                    categories=["benchmark", "dataset"],
                ),
            ]
        )
    ]

    index = build_theme_index(snapshots)

    assert [group["category"] for group in index["groups"]] == [
        "xbsleepy:planning",
        "xbsleepy:web",
    ]
    planning = index["groups"][0]
    assert planning["count"] == 2
    assert [record["title"] for record in planning["records"]] == [
        "Second",
        "A Drift-Aware Agent Benchmark",
    ]
    # Nothing leaves the page: the three untagged records are accounted for
    # rather than dropped, and the totals reconcile.
    assert {record["title"] for record in index["unthemed"]} == {
        "Untagged",
        "No source_tags key",
        "Keyword classified only",
    }
    assert index["records"] == 5
    assert index["tagged"] == 2
    assert index["tagged"] + len(index["unthemed"]) == index["records"]


def test_build_theme_index_keeps_the_same_id_from_two_sources_apart():
    # Source ids are unique only within the source that minted them. Keying on
    # the id alone silently merged two sources' different records into one.
    snapshots = [
        _snapshot(
            [
                _item(source="XBsleepy", source_id="2609.1", title="From the digest"),
                _item(
                    source="arXiv",
                    source_id="2609.1",
                    title="From arXiv",
                    url="https://arxiv.org/abs/2609.1v2",
                    source_tags=["arxiv:planning"],
                ),
            ]
        )
    ]

    index = build_theme_index(snapshots)

    assert index["records"] == 2
    assert index["tagged"] == 2
    assert [group["category"] for group in index["groups"]] == [
        "arxiv:planning",
        "xbsleepy:planning",
    ]
    assert all(group["count"] == 1 for group in index["groups"])


def test_build_theme_index_keeps_one_record_recurring_across_snapshots():
    snapshots = [
        _snapshot([_item()]),
        _snapshot(
            [
                _item(
                    published_at="2026-09-11T18:00:00Z",
                    updated_at="2026-09-11T18:00:00Z",
                    summary="Revised abstract.",
                )
            ]
        ),
    ]

    index = build_theme_index(snapshots)

    assert index["records"] == 1
    assert index["groups"][0]["count"] == 1
    # The newest copy supplies what the reader sees.
    assert index["groups"][0]["records"][0]["date"] == "2026-09-11"
    assert index["groups"][0]["records"][0]["summary"] == "Revised abstract."


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
                        source_tags=["xbsleepy:planning", "xbsleepy:web"],
                    ),
                ]
            )
        ],
        tmp_path,
    )

    assert report["path"] == "/themes/"
    assert report["categories"] == 2
    assert report["records"] == 2
    assert report["tagged"] == 2
    assert report["unthemed"] == 0
    page = (tmp_path / "themes" / "index.html").read_text(encoding="utf-8")
    assert "xbsleepy:planning" in page
    assert "xbsleepy:web" in page
    assert "Browse new arrivals by theme" in page
    # The population is stated on the page, so a reader cannot mistake this
    # view for a count of the benchmark catalog.
    assert "2 discovery records read from the daily snapshots" in page
    # The chrome contract runs both ways: the page carries the site nav, and
    # the nav marks /themes/ active on the page.
    assert 'href="/themes/"' in page
    assert not (tmp_path / "themes.staging").exists()


def test_write_themes_lists_unthemed_records_instead_of_dropping_them(tmp_path):
    report = _write_themes([_snapshot([_item(source_tags=[])])], tmp_path)

    assert report["categories"] == 0
    assert report["records"] == 1
    assert report["unthemed"] == 1
    page = (tmp_path / "themes" / "index.html").read_text(encoding="utf-8")
    assert "No source has tagged a record with a theme yet." in page
    assert "No theme tag yet" in page
    assert "A Drift-Aware Agent Benchmark" in page


def test_every_chip_targets_a_slug_the_page_actually_carries(tmp_path):
    # The chips pinned `theme-<slug>` while the sections carried `<slug>`, so no
    # lookup ever matched and one click hid every section on the page. The page
    # looked fine until someone used it.
    _write_themes(
        [
            _snapshot(
                [
                    _item(),
                    _item(source_id="xbsleepy:2609.2", source_tags=["xbsleepy:web"]),
                    _item(source_id="xbsleepy:2609.3", source_tags=[]),
                ]
            )
        ],
        tmp_path,
    )
    page = (tmp_path / "themes" / "index.html").read_text(encoding="utf-8")

    targets = set(re.findall(r'class="theme-chip" data-target="([^"]+)"', page))
    slugs = set(re.findall(r'class="theme-section" id="theme-[^"]+" data-slug="([^"]+)"', page))

    assert targets, "expected chips to render"
    assert targets <= slugs
    # And the anchor each section offers is the slug the chip pins.
    assert {f"theme-{slug}" for slug in slugs} == set(
        re.findall(r'class="theme-section" id="(theme-[^"]+)"', page)
    )


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
