"""The blog publishes one page per committed snapshot, and only from snapshots."""

import copy
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from benchmark_radar.blog import LATEST_POST_LIMIT, blog_feed_tree, build_posts, write_blog
from benchmark_radar.blog_content import (
    _QUESTION_ZH,
    KIND_BRIEF,
    KIND_EVIDENCE,
    KIND_NO_CHANGE,
    build_post,
)
from benchmark_radar.blog_shell import (
    _TODAY_HREFS,
    BLOG_ARCHIVE_PATH,
    BLOG_FEED_PATH,
    BLOG_PATH,
    _ensure_outline_icon,
    extract_site_chrome,
)
from benchmark_radar.feed import SITE_URL

# The blog chrome is extracted from the committed dashboard source, so the
# tests exercise the real site/index.html rather than a hand-written fixture
# that could drift from what ships.
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DASHBOARD_HTML = (SITE_DIR / "index.html").read_text(encoding="utf-8")
APP_JS = (SITE_DIR / "assets" / "app.js").read_text(encoding="utf-8")


def write_blog_with_chrome(snapshots, tmp_path):
    return write_blog(snapshots, tmp_path, dashboard_html=DASHBOARD_HTML, app_js=APP_JS)


SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshots"


def _snapshot(day: str) -> dict:
    return json.loads((SNAPSHOT_DIR / f"{day}.json").read_text(encoding="utf-8"))


def _snapshot_days() -> list[str]:
    return sorted(path.stem for path in SNAPSHOT_DIR.glob("*.json"))


def _text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _briefed(status: str | None = None) -> dict:
    """A snapshot carrying a complete stored briefing and one question answer."""
    return {
        "date": "2026-08-30",
        "generated_at": "2026-08-30T02:00:00+00:00",
        "evidence_items": [
            {
                "title": "A new evaluation suite",
                "source": "arXiv",
                "url": "https://arxiv.org/abs/2608.00001",
            },
            {"title": "No link here", "source": "GitHub Release"},
        ],
        "attention": {"observations": [{"id": "A1"}]},
        "briefing": {
            "status": status,
            "bullets": ["Agentic artifacts rose to 26% of the captured feed."],
            "bullets_zh": ["智能体成果占捕获信息流的 26%。"],
            "caveat": "The feed is keyword-filtered.",
            "caveat_zh": "该信息流经过关键词筛选。",
            "model": "gpt-5.6-sol",
            "input": {"coverage": {"evidence_injected": 1, "corpus_evidence_records": 2}},
            "citations": [
                {
                    "title": "A new evaluation suite",
                    "source": "arXiv",
                    "url": "https://arxiv.org/abs/2608.00001",
                }
            ],
        },
        "questions": {
            "groups": [
                {
                    "title": "What arrived today",
                    "answers": [
                        {
                            "question": "What is new?",
                            "question_zh": "有什么新内容？",
                            "signal": "One suite landed.",
                            "signal_zh": "出现了一个新套件。",
                            "plain_english": "A single benchmark appeared.",
                            "plain_chinese": "出现了一个 benchmark。",
                            "takeaway": "Watch the next few days.",
                            "counter_view": "One day is not a trend.",
                            "confidence": "medium",
                            "sufficient_evidence": False,
                            "cited_stats": [
                                {"label": "artifacts today", "value": 1, "unit": "count"}
                            ],
                            "cited_evidence": [
                                {
                                    "title": "A new evaluation suite",
                                    "source": "arXiv",
                                    "url": "https://arxiv.org/abs/2608.00001",
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }


def _legacy() -> dict:
    """An early snapshot from before briefings were stored."""
    return {
        "date": "2026-07-23",
        "generated_at": "2026-07-23T02:00:00+00:00",
        "attention": {"observations": []},
        "evidence_items": [
            {"title": f"Record {index}", "source": "arXiv", "url": f"https://example.org/{index}"}
            for index in range(25)
        ],
    }


# --- one page per snapshot, whatever kind of day it was -------------------


def test_every_committed_snapshot_gets_exactly_one_post():
    days = _snapshot_days()
    posts = build_posts([_snapshot(day) for day in days])
    assert [post.slug for post in posts] == sorted(days, reverse=True)


def test_committed_history_covers_all_three_kinds_of_day():
    kinds = {post.kind for post in build_posts([_snapshot(day) for day in _snapshot_days()])}
    assert kinds == {KIND_BRIEF, KIND_NO_CHANGE, KIND_EVIDENCE}


def test_no_material_insight_day_is_published_as_its_own_report():
    post = build_post(_briefed(status="no_material_insight"))
    assert post.kind == KIND_NO_CHANGE
    assert "Agentic artifacts rose" in _text(post.body_en)


def test_missing_calendar_days_get_no_page():
    """A gap in collection stays a gap; an empty post would be an invented day."""
    posts = build_posts([_snapshot("2026-08-08"), _snapshot("2026-08-10")])
    assert [post.slug for post in posts] == ["2026-08-10", "2026-08-08"]


def test_duplicate_snapshot_dates_are_rejected():
    with pytest.raises(ValueError, match="duplicate snapshot dates"):
        build_posts([_briefed(), _briefed()])


# --- what each kind of day is allowed to claim ----------------------------


def test_briefed_day_renders_every_stored_field():
    body = _text(build_post(_briefed(status="insight")).body_en)
    assert "Agentic artifacts rose" in body
    assert "What is new?" in body
    assert "medium confidence" in body
    assert "Not enough evidence" in body
    assert "artifacts today: 1" in body
    assert "Takeaway: Watch the next few days." in body
    assert "Another reading: One day is not a trend." in body
    assert "Briefing model: gpt-5.6-sol" in body
    assert "It read 1 of 2 records." in body
    assert "The feed is keyword-filtered." in body


def test_legacy_day_is_labelled_a_deterministic_summary_not_a_briefing():
    post = build_post(_legacy())
    body = _text(post.body_en)
    assert post.kind == KIND_EVIDENCE
    assert "No briefing was stored for this day" in body
    assert "deterministic summary of the 25 evidence records" in body
    assert "not a synthesized briefing" in body
    assert "Daily briefing" not in body


def test_legacy_day_shows_the_first_ten_stored_records():
    body = build_post(_legacy()).body_en
    listed = re.findall(r"Record \d+", body)
    assert listed == [f"Record {index}" for index in range(10)]


def test_partial_briefing_never_invents_a_model_or_coverage():
    """2026-08-05 stored bullets with no generator metadata; say so, do not guess."""
    body = _text(build_post(_snapshot("2026-08-05")).body_en)
    assert "without recording the model that produced it" in body
    assert "Briefing model:" not in body
    assert "0 of 0" not in body


def test_a_source_url_that_is_not_http_is_dropped():
    snapshot = _briefed()
    snapshot["briefing"]["citations"] = [{"title": "Bad", "url": "javascript:alert(1)"}]
    snapshot["questions"]["groups"][0]["answers"][0]["cited_evidence"] = []
    assert all(url.startswith("https://") for _, _, url in build_post(snapshot).sources)


# --- bilingual behavior ---------------------------------------------------


def test_stored_chinese_is_published_with_a_toggle():
    post = build_post(_briefed(status="insight"))
    assert post.body_zh is not None
    assert "智能体成果占捕获信息流的 26%" in post.body_zh
    assert "该信息流经过关键词筛选" in post.body_zh


def test_a_day_without_stored_chinese_publishes_english_body_with_the_toggle(tmp_path):
    post = build_post(_legacy())
    assert post.body_zh is None and post.title_zh is None
    write_blog_with_chrome([_legacy()], tmp_path)
    page = (tmp_path / "blog" / "2026-07-23" / "index.html").read_text(encoding="utf-8")
    # No invented translation: the body ships English-only. The toggle stays,
    # because the chrome itself is translatable on every page.
    assert 'data-lang-content="zh"' not in page
    assert 'data-lang-content="en"' in page
    assert 'id="lang-toggle"' in page


def test_the_toggle_is_on_every_blog_page_like_the_dashboard(tmp_path):
    write_blog_with_chrome([_briefed(status="insight"), _legacy()], tmp_path)
    for slug in ("", "archive/", "2026-08-30/", "2026-07-23/"):
        page = (tmp_path / "blog" / slug / "index.html").read_text(encoding="utf-8")
        assert page.count('id="lang-toggle"') == 1, f"missing toggle on /blog/{slug}"
    translated = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    assert 'data-lang-content="zh"' in translated and 'data-lang-content="en"' in translated


# --- the published tree ---------------------------------------------------


def test_write_blog_publishes_index_archive_feed_and_one_page_per_day(tmp_path):
    snapshots = [_snapshot(day) for day in _snapshot_days()]
    report = write_blog_with_chrome(snapshots, tmp_path)
    blog = tmp_path / "blog"
    assert report["post_count"] == len(snapshots)
    assert (blog / "index.html").exists()
    assert (blog / "archive" / "index.html").exists()
    assert (blog / "feed.xml").exists()
    for snapshot in snapshots:
        assert (blog / str(snapshot["date"]) / "index.html").exists()


def test_the_landing_page_shows_the_latest_days_and_the_archive_shows_all(tmp_path):
    snapshots = [_snapshot(day) for day in _snapshot_days()]
    write_blog_with_chrome(snapshots, tmp_path)
    latest = (tmp_path / "blog" / "index.html").read_text(encoding="utf-8")
    archive = (tmp_path / "blog" / "archive" / "index.html").read_text(encoding="utf-8")
    assert latest.count('class="blog-card"') == LATEST_POST_LIMIT
    assert archive.count('class="blog-card"') == len(snapshots)
    for snapshot in snapshots:
        assert f"{BLOG_PATH}{snapshot['date']}/" in archive


def test_blog_document_links_stay_on_the_serving_host(tmp_path):
    write_blog_with_chrome([_briefed(), _legacy()], tmp_path)
    latest = (tmp_path / "blog" / "index.html").read_text(encoding="utf-8")
    archive = (tmp_path / "blog" / "archive" / "index.html").read_text(encoding="utf-8")
    assert f'href="{BLOG_ARCHIVE_PATH}"' in latest
    assert f'href="{BLOG_PATH}"' in archive
    for post in build_posts([_briefed(), _legacy()]):
        assert f'href="{post.path}"' in latest
        assert f'href="{post.path}"' in archive
        assert f'href="{post.canonical}"' not in latest
        assert f'href="{post.canonical}"' not in archive


def test_a_rebuild_removes_pages_for_days_that_left_the_history(tmp_path):
    write_blog_with_chrome([_briefed(), _legacy()], tmp_path)
    assert (tmp_path / "blog" / "2026-08-30" / "index.html").exists()
    write_blog_with_chrome([_legacy()], tmp_path)
    assert not (tmp_path / "blog" / "2026-08-30").exists()
    assert (tmp_path / "blog" / "2026-07-23" / "index.html").exists()


def test_rebuilding_is_deterministic_and_never_mutates_the_snapshot(tmp_path):
    snapshots = [_snapshot(day) for day in _snapshot_days()]
    original = copy.deepcopy(snapshots)
    write_blog_with_chrome(snapshots, tmp_path / "first")
    write_blog_with_chrome(snapshots, tmp_path / "second")
    assert snapshots == original
    for page in sorted((tmp_path / "first" / "blog").rglob("*")):
        if page.is_file():
            twin = tmp_path / "second" / "blog" / page.relative_to(tmp_path / "first" / "blog")
            assert page.read_bytes() == twin.read_bytes()


# --- metadata a search engine and a reader both depend on -----------------


def test_each_page_carries_its_own_canonical_and_blogposting_schema(tmp_path):
    write_blog_with_chrome([_briefed(status="insight")], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    canonical = f"{SITE_URL}{BLOG_PATH}2026-08-30/"
    assert f'<link rel="canonical" href="{canonical}">' in page
    posting = next(payload for payload in _schemas(page) if payload.get("@type") == "BlogPosting")
    assert posting["url"] == canonical
    assert posting["datePublished"] == "2026-08-30"
    assert posting["citation"] == ["https://arxiv.org/abs/2608.00001"]
    assert posting["inLanguage"] == ["en", "zh-Hans"]


def _schemas(page: str) -> list[dict]:
    return [
        json.loads(block.replace("<\\/", "</"))
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    ]


def test_each_page_carries_a_breadcrumb_back_to_the_blog(tmp_path):
    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    crumb = next(p for p in _schemas(page) if p.get("@type") == "BreadcrumbList")
    assert [item["item"] for item in crumb["itemListElement"]] == [
        f"{SITE_URL}/",
        f"{SITE_URL}{BLOG_PATH}",
        f"{SITE_URL}{BLOG_PATH}2026-08-30/",
    ]


def test_sitemap_entries_cover_the_blog_and_date_each_brief_individually(tmp_path):
    snapshots = [_snapshot(day) for day in _snapshot_days()]
    entries = write_blog_with_chrome(snapshots, tmp_path)["sitemap_entries"]
    paths = [path for path, _ in entries]
    assert paths[:2] == [BLOG_PATH, BLOG_ARCHIVE_PATH]
    assert len(paths) == len(snapshots) + 2
    by_path = dict(entries)
    assert by_path["/blog/2026-07-23/"] == "2026-07-23"
    assert by_path["/blog/2026-09-01/"] == "2026-09-01"


def test_the_blog_feed_lists_every_post_and_is_self_describing():
    posts = build_posts([_snapshot(day) for day in _snapshot_days()])
    channel = blog_feed_tree(posts).getroot().find("channel")
    links = [item.find("link").text for item in channel.findall("item")]
    assert links == [post.canonical for post in posts]
    self_link = channel.find("{http://www.w3.org/2005/Atom}link")
    assert self_link.get("href") == SITE_URL + BLOG_FEED_PATH


def test_the_blog_feed_is_written_into_the_published_tree(tmp_path):
    snapshots = [_snapshot(day) for day in _snapshot_days()]
    write_blog_with_chrome(snapshots, tmp_path)
    channel = ET.parse(tmp_path / "blog" / "feed.xml").getroot().find("channel")
    assert len(channel.findall("item")) == len(snapshots)


def _cited_day() -> dict:
    """The newest snapshot whose briefing cites evidence by ID."""
    for day in reversed(_snapshot_days()):
        snapshot = _snapshot(day)
        citations = (snapshot.get("briefing") or {}).get("citations") or []
        if any(citation.get("id") for citation in citations):
            return snapshot
    raise AssertionError("no committed snapshot cites evidence by ID")


def test_cited_evidence_keeps_the_id_the_prose_refers_to():
    snapshot = _cited_day()
    citations = snapshot["briefing"]["citations"]
    body = build_post(snapshot).body_en
    for citation in citations:
        identifier = citation.get("id")
        if not identifier:
            continue
        assert f'<span class="blog-cite-id">{identifier}</span>' in body


def test_cited_ids_are_not_replaced_by_list_position():
    """A briefing can cite E011 without listing ten earlier records."""
    snapshot = _cited_day()
    identifiers = [
        citation["id"] for citation in snapshot["briefing"]["citations"] if citation.get("id")
    ]
    positions = [f"E{index:03d}" for index in range(1, len(identifiers) + 1)]
    if identifiers == positions:
        pytest.skip("this day's citation IDs happen to match their list positions")
    body = build_post(snapshot).body_en
    assert identifiers[-1] in body


def test_cited_statistics_show_the_registry_id():
    for day in reversed(_snapshot_days()):
        snapshot = _snapshot(day)
        stats = [
            stat
            for _, answer in _stored_answers(snapshot)
            for stat in answer.get("cited_stats") or []
            if stat.get("id")
        ]
        if not stats:
            continue
        body = build_post(snapshot).body_en
        for stat in stats:
            assert f'<span class="blog-cite-id">{stat["id"]}</span>' in body
        return
    pytest.skip("no committed snapshot cites a statistic by ID")


def _stored_answers(snapshot: dict) -> list[tuple[str, dict]]:
    return [
        (str(group.get("title") or ""), answer)
        for group in (snapshot.get("questions") or {}).get("groups") or []
        for answer in group.get("answers") or []
    ]


def test_a_chinese_brief_translates_the_fixed_question_prompts():
    for day in reversed(_snapshot_days()):
        snapshot = _snapshot(day)
        answers = _stored_answers(snapshot)
        post = build_post(snapshot)
        if not answers or post.body_zh is None:
            continue
        translated = [
            (title, answer)
            for title, answer in answers
            if title in _QUESTION_ZH or str(answer.get("question")) in _QUESTION_ZH
        ]
        assert translated, f"{day} stores no prompt the dashboard translates"
        for title, answer in translated:
            for english in (title, str(answer.get("question"))):
                if english in _QUESTION_ZH:
                    assert _QUESTION_ZH[english] in post.body_zh
                    assert f"<h3>{english}</h3>" not in post.body_zh
        return
    pytest.skip("no committed snapshot pairs stored answers with a translation")


def test_question_translations_match_the_dashboard_table():
    """One prompt cannot read one way on the dashboard and another on the blog."""
    app_js = (Path(__file__).resolve().parents[1] / "site" / "assets" / "app.js").read_text(
        encoding="utf-8"
    )
    for english, chinese in _QUESTION_ZH.items():
        match = re.search(rf'"{re.escape(english)}":\s*\n?\s*"([^"]+)"', app_js)
        assert match, f"the dashboard does not translate {english!r}"
        assert match.group(1) == chinese


def _nav_targets(fragment: str) -> list[str]:
    """Href sequence of a section nav; the SPA's Today button maps to ``/``."""
    nav = re.search(r'<nav class="view-nav".*?</nav>', fragment, re.S).group(0)
    targets = []
    for match in re.finditer(r"<(a|button)\b([^>]*)>", nav):
        tag, attrs = match.group(1), match.group(2)
        href = re.search(r'href="([^"]*)"', attrs)
        if tag == "a":
            assert href, f"nav anchor without href: {match.group(0)!r}"
            targets.append(href.group(1))
        else:
            view = re.search(r'data-view="([^"]*)"', attrs)
            assert view and view.group(1) in _TODAY_HREFS, attrs
            targets.append(_TODAY_HREFS[view.group(1)])
    return targets


def test_blog_nav_lists_the_same_sections_in_the_same_order_as_the_dashboard(tmp_path):
    # The nav is extracted from site/index.html, not restated; this fails
    # loudly if the extractor breaks or the dashboard grows a section the
    # blog silently stops carrying.
    dashboard_targets = _nav_targets(DASHBOARD_HTML)
    assert dashboard_targets, "the extractor found no nav in site/index.html"
    write_blog_with_chrome([_briefed(), _legacy()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    assert _nav_targets(page) == dashboard_targets
    assert 'class="nav-active" aria-current="page" href="/blog/"' in page


def test_dashboard_and_blog_share_the_reduced_chrome_contract(tmp_path):
    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    expected = [
        "/",
        "/cli/",
        "/leaderboard/",
        "/trends/",
        "/blog/",
    ]
    for document in (DASHBOARD_HTML, page):
        assert _nav_targets(document) == expected
        header = re.search(r'<header class="masthead".*?</header>', document, re.S).group(0)
        numbered = []
        for anchor in re.finditer(r"<a\b([^>]*)>(.*?)</a>", header, re.S):
            if "data-count" not in anchor.group(2):
                continue
            badge_id = re.search(r'id="([^"]+)"', anchor.group(1))
            assert badge_id
            numbered.append(badge_id.group(1))
        assert numbered == ["badge-stars"]


def test_blog_fetches_only_the_star_count_like_the_dashboard():
    script = (SITE_DIR / "assets" / "blog.js").read_text(encoding="utf-8")
    assert "repo.stargazers_count" in script
    assert "repo.forks_count" not in script
    assert "api.github.com/search/issues" not in script


def test_the_contact_button_becomes_the_dashboard_deep_link(tmp_path):
    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    # The contact sheet itself lives inside the SPA; the blog links to the
    # deep link that opens it on load instead of shipping a dead button.
    assert '<a class="repo-badge" href="/#contact"' in page
    assert 'id="badge-contact"' not in page


def test_the_footer_build_date_is_baked_from_the_day_the_page_describes(tmp_path):
    write_blog_with_chrome([_briefed(), _legacy()], tmp_path)
    brief = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    legacy = (tmp_path / "blog" / "2026-07-23" / "index.html").read_text(encoding="utf-8")
    assert '<span data-i18n="Updated">Updated</span> 2026-08-30' in brief
    assert '<span data-i18n="Updated">Updated</span> 2026-07-23' in legacy
    assert "Updated \u2014" not in brief


def test_a_missing_dashboard_source_fails_visibly(tmp_path):
    with pytest.raises(FileNotFoundError, match="dashboard source"):
        write_blog([_briefed()], tmp_path)


def test_the_extractor_fails_loudly_when_the_dashboard_changes_shape():
    with pytest.raises(ValueError, match="masthead"):
        extract_site_chrome("<html><body><p>no header here</p></body></html>")


def test_the_chrome_i18n_table_is_baked_from_app_js_for_chinese_readers(tmp_path):
    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="chrome-i18n">(.*?)</script>', page, re.S
    )
    assert match, "the baked chrome-i18n table is missing"
    table = json.loads(match.group(1))
    # Same reviewed strings the dashboard applies: the contact label, the
    # toggle states, and the badge aria templates.
    assert table["Contact"] == "联系作者"
    assert table["Switch to English"] == "切换到英文"
    assert "{count}" in table["Star this repository on GitHub. {count} stars"]
    assert table["Updated"] == "更新于"


def test_nav_labels_without_a_reviewed_string_stay_english_like_the_dashboard(tmp_path):
    # The dashboard's t() falls back to the key when the table lacks it, so
    # short section labels stay English there; the blog must mirror that
    # instead of inventing translations.
    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="chrome-i18n">(.*?)</script>', page, re.S
    )
    table = json.loads(match.group(1))
    # Section labels carry reviewed translations (Blog → 博客), same as the
    # dashboard's menubar in Chinese mode.
    assert table["Blog"] == "博客"
    assert table["CLI"] == "命令行"


def test_ensure_outline_icon_tolerates_existing_classes_and_attribute_order():
    already = '<svg class="outline-icon" viewBox="0 0 24 24"></svg>'
    assert _ensure_outline_icon(already) == already
    extra = '<svg class="foo outline-icon" viewBox="0 0 24 24"></svg>'
    assert _ensure_outline_icon(extra) == extra
    appended = _ensure_outline_icon('<svg class="foo" viewBox="0 0 24 24"></svg>')
    assert 'class="foo outline-icon"' in appended
    added = _ensure_outline_icon('<svg viewBox="0 0 24 24"></svg>')
    assert re.search(r'<svg\b[^>]*\bclass="[^"]*\boutline-icon\b', added)
    reordered = _ensure_outline_icon('<svg viewBox="0 0 24 24" class="foo"></svg>')
    assert re.search(r'<svg\b[^>]*\bclass="[^"]*\boutline-icon\b', reordered)


def test_contact_button_has_outline_icon_in_dashboard_source_and_blog_pages(tmp_path):
    # The contact button svg must carry class="outline-icon" directly in index.html,
    # and the extracted anchor in generated blog pages must preserve it so the icon
    # renders with stroke instead of a filled black blob.
    assert re.search(
        r'<button\b[^>]*\bid="badge-contact"[^>]*>[\s\S]*?<svg\b[^>]*\bclass="[^"]*\boutline-icon\b',
        DASHBOARD_HTML,
    ), "site/index.html contact button svg lacks outline-icon class"

    write_blog_with_chrome([_briefed()], tmp_path)
    page = (tmp_path / "blog" / "2026-08-30" / "index.html").read_text(encoding="utf-8")
    contact_match = re.search(r'<a\b[^>]*\bhref="/#contact"[^>]*>([\s\S]*?)</a>', page)
    assert contact_match, "transformed contact link missing in blog page"
    assert re.search(
        r'<svg\b[^>]*\bclass="[^"]*\boutline-icon\b',
        contact_match.group(1),
    )


def _run_blog_language_harness(mode: str, target_lang: str, remember: bool = True) -> dict:
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    args = [
        node,
        "tests/render_blog_language_harness.mjs",
        mode,
        target_lang,
    ]
    if remember:
        args.append("remember")
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_client_language_switch_keeps_untranslated_body_visible_while_translating_chrome():
    # When a post has no Chinese body translation, switching to Chinese must translate
    # the chrome (navbar, badges, footer) and update toggle state without hiding the English body.
    res = _run_blog_language_harness("untranslated", "zh")
    assert res["htmlLang"] == "zh-CN"
    assert res["enHidden"] is False
    assert res["zhHidden"] is None
    assert res["toggleAriaPressed"] == "true"
    assert res["toggleLabel"] == "EN"
    assert res["storedLang"] == "zh"
    assert res["contactText"] == "联系作者"


def test_client_language_switch_toggles_translated_body_between_en_and_zh():
    # When a post has both en and zh translations, switching to Chinese shows zh and hides en;
    # switching to English shows en and hides zh.
    zh_res = _run_blog_language_harness("translated", "zh")
    assert zh_res["htmlLang"] == "zh-CN"
    assert zh_res["enHidden"] is True
    assert zh_res["zhHidden"] is False
    assert zh_res["toggleAriaPressed"] == "true"
    assert zh_res["toggleLabel"] == "EN"
    assert zh_res["storedLang"] == "zh"
    assert zh_res["contactText"] == "联系作者"

    en_res = _run_blog_language_harness("translated", "en")
    assert en_res["htmlLang"] == "en"
    assert en_res["enHidden"] is False
    assert en_res["zhHidden"] is True
    assert en_res["toggleAriaPressed"] == "false"
    assert en_res["toggleLabel"] == "中"
    assert en_res["storedLang"] == "en"
    assert en_res["contactText"] == "Contact"


def test_client_malformed_chrome_i18n_logs_error_without_throwing():
    # If the baked chrome-i18n payload fails to parse, it logs with console.error,
    # keeps the page functional in English, and does not throw.
    res = _run_blog_language_harness("malformed-json", "zh")
    assert any("Failed to parse #chrome-i18n payload" in err for err in res["consoleErrors"])
    assert res["contactText"] == "Contact"
