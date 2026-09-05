import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()
        self.html_lang = ""
        self.viewport = False
        self.local_refs: list[str] = []
        self.icon_hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append(tag)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "html":
            self.html_lang = str(values.get("lang", ""))
        if tag == "meta" and values.get("name") == "viewport":
            self.viewport = True
        if tag == "link" and "icon" in str(values.get("rel", "")).split():
            self.icon_hrefs.append(str(values.get("href", "")))
        reference = values.get("href") or values.get("src")
        if reference and not urlsplit(reference).scheme and not reference.startswith(("#", "//")):
            self.local_refs.append(reference)


def test_readmes_offer_free_data_and_an_earned_star_request():
    english = Path("README.md").read_text(encoding="utf-8")
    chinese = Path("README.zh-CN.md").read_text(encoding="utf-8")

    # Language switch sits top-left above the title with a plain label.
    assert '<div align="left">' in english.split("# Benchmark Radar")[0]
    assert "[中文](README.zh-CN.md)" in english
    assert "[README.zh-CN.md](README.zh-CN.md)" not in english
    assert '<div align="left">' in chinese.split("# Benchmark Radar")[0]
    assert "[English](README.md)" in chinese
    assert "Click" in english and "the GIF below" in english
    assert "点击下面的动图" in chinese
    assert "assets/swe-bench-verified.gif" in english
    assert "assets/swe-bench-verified.gif" in chinese
    assert "data/radar.json" in english and "no crawler or contact required" in english
    assert "data/radar.json" in chinese and "无需爬虫或联系作者" in chinese
    assert "star the repository" in english
    assert "给仓库点个 Star" in chinese
    assert Path("CITATION.cff").exists()


def test_site_has_accessible_landmarks_and_views():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    assert parser.html_lang == "en"
    assert parser.viewport
    assert {"header", "nav", "main", "footer", "dialog"} <= set(parser.tags)
    assert {"today-view", "trends-view", "map-view", "main-content"} <= parser.ids
    assert "explorer-view" not in parser.ids


def test_every_html_entry_point_loads_clarity_once_and_discloses_analytics():
    html_paths = sorted(Path("site").glob("*.html"))
    assert html_paths

    for path in html_paths:
        html = path.read_text(encoding="utf-8")
        head = html.split("<head>", 1)[1].split("</head>", 1)[0]
        assert head.count("assets/clarity.js") == 1, path

    # The dashboard is also served at /leaderboard/, /trends/ and /explore/,
    # where a relative src resolves one directory down and 404s. logos.html is
    # only ever served from the root, so it may stay relative.
    dashboard = Path("site/index.html").read_text(encoding="utf-8")
    dashboard_head = dashboard.split("<head>", 1)[1].split("</head>")[0]
    assert 'src="/assets/clarity.js"' in dashboard_head

    loader = Path("site/assets/clarity.js").read_text(encoding="utf-8")
    assert loader.count("ya4h95jvfj") == 1
    assert "https://www.clarity.ms/tag/" in loader
    assert "t.async = 1" in loader

    homepage = Path("site/index.html").read_text(encoding="utf-8")
    assert "session replays and heatmaps" in homepage
    assert "Sensitive content is masked by default" in homepage
    assert "https://privacy.microsoft.com/privacystatement" in homepage


def test_privacy_notice_is_collapsible_and_collapsed_by_default():
    homepage = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")
    renderer = Path("site/assets/app.js").read_text(encoding="utf-8")

    disclosure = homepage.split('<details class="privacy-note">', 1)[1].split("</details>", 1)[0]
    assert "<summary" in disclosure
    assert "Privacy notice" in disclosure.split("<summary", 1)[1].split("</summary>", 1)[0]
    assert "session replays and heatmaps" in disclosure
    assert "Sensitive content is masked by default" in disclosure
    assert "https://privacy.microsoft.com/privacystatement" in disclosure
    assert 'class="privacy-note" open' not in homepage

    assert ".privacy-note summary {" in styles
    assert ".privacy-note[open] summary::after" in styles
    assert '"Privacy notice": "隐私声明"' in renderer


def test_priority_score_is_reachably_explained():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The score label itself is the affordance, so a reader looking at the
    # number does not have to hunt elsewhere for its definition.
    assert 'id="rubric-dialog"' in html
    assert 'id="rubric-content"' in html
    assert 'id="rubric-nav"' not in html
    assert "score-explain" in script
    assert "openRubric" in script
    assert "How is this scored?" in script


def test_citation_formats_are_one_click_away_behind_a_short_link():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")
    cff = Path("CITATION.cff").read_text(encoding="utf-8")

    # Same pop-out treatment as the rubric, with a first-class path short enough
    # to paste into a paper or a message.
    assert 'id="cite-dialog"' in html
    assert 'id="cite-content"' in html
    assert 'href="/cite/"' in html
    assert 'aria-controls="cite-dialog"' in html
    assert 'state.cite = pathUtility === "cite"' in script
    assert 'canonical: "/cite/"' in script
    assert "function openCite(" in script

    # Three formats, each copied by clicking the citation itself.
    assert 'copyBlock("APA", CITE_APA, "Click to copy")' in script
    assert 'copyBlock("BibTeX", CITE_BIBTEX, "Click to copy")' in script
    assert 'copyBlock("Citation file (.cff)", CITE_CFF_URL, "Click to copy link")' in script
    assert "navigator.clipboard.writeText(value)" in script
    assert ".copy-target {" in styles

    # The card draws no data, so a build whose payload never arrives must still
    # open it and must still close it on Back: both sides of that sit above the
    # early return in onPopState.
    pop_state = script.split("async function onPopState() {", 1)[1]
    cite_sync = pop_state.index('const citeDialog = byId("cite-dialog");')
    assert cite_sync < pop_state.index("if (!state.data) return;")

    # Opening from the footer pushes an entry carrying its background view.
    # Closing consumes it, while a directly-opened /cite/ replaces to `/` and
    # never sends the reader back to an external referrer.
    assert "citeOwnsHistoryEntry = updateUrl;" in script
    assert 'finishUtilityClose("cite", owned);' in script
    assert "benchmarkRadarUtility" in script

    # The rendered citations must agree with the file they claim to mirror, or
    # the site would hand out a citation the repository does not make.
    for fragment in ("10.5281/zenodo.22167102", "Benchmark Radar v0.9.0: Technical Report"):
        assert fragment in cff
        assert fragment in script
    assert "given-names: Junjie" in cff
    assert '"Wu, K., & Zhou, J. (2026)' in script
    assert '"author = {Wu, Koutian and Zhou, Junjie},"' in script
    assert html.count('name="citation_author"') == 2
    assert '<meta name="citation_author" content="Zhou, Junjie">' in html


def test_offline_cli_route_is_in_the_view_bar_behind_a_short_link():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    # Same pop-out treatment as the rubric, reached from the view bar rather
    # than from a section of the README a reader has to scroll to.
    nav = html.split('<nav class="view-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'id="cli-nav"' in nav
    assert 'href="/cli/"' in nav
    assert 'aria-controls="cli-dialog"' in nav
    assert 'id="cli-dialog"' in html
    assert 'id="cli-content"' in html
    assert 'state.cli = pathUtility === "cli"' in script
    assert 'canonical: "/cli/"' in script
    assert "function openCli(" in script

    # The single command shares the citation card's copy control rather than
    # adding another clipboard handler, and its label is for screen readers only.
    assert 'copyBlock("Install", CLI_SKILL_INSTALL, "Click to copy", true)' in script
    assert 'hideLabel ? "copy-label visually-hidden" : "copy-label"' in script

    # The card holds no data either, so it opens before the fetch and closes on
    # Back above the early return, and it owns its pushed history entry.
    assert "if (state.cli) openCli(false);" in script
    pop_state = script.split("async function onPopState() {", 1)[1]
    assert pop_state.index('const cliDialog = byId("cli-dialog");') < pop_state.index(
        "if (!state.data) return;"
    )
    assert "cliOwnsHistoryEntry = updateUrl;" in script
    assert 'finishUtilityClose("cli", owned);' in script

    # A view entry and the CLI entry must not both read as current, and the CLI
    # entry carries the rubric's dialog-trigger treatment: both open a sheet
    # over the page rather than changing the view under it.
    assert 'cliNav.classList.toggle("nav-active", utility === "cli");' in script
    assert "!utility && item.dataset.view === state.view" in script
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")
    assert "#cli-nav:not(.nav-active) {" in styles
    assert "#cli-nav::after {" in styles

    # The card is the README's setup route, not a second one written for the
    # site: the prompt it hands out has to be the prompt the README publishes.
    readme_cli = readme.split("## Query it locally (CLI version)", 1)[1].split("## More", 1)[0]
    skill_url = (
        "https://github.com/ktwu01/benchmark-radar/blob/main/skills/benchmark-radar/SKILL.md"
    )
    assert skill_url in readme_cli
    assert skill_url in script
    assert "npx skills add ktwu01/benchmark-radar" in readme_cli
    assert "npx skills add ktwu01/benchmark-radar" in script
    # One published command, and nothing the reader has to relay to an agent:
    # the Skill installs the CLI and the data the first time it is asked.
    assert "```text" not in readme_cli
    assert "CLI_AGENT_PROMPT" not in script


def test_only_one_sheet_is_open_at_a_time():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # showModal() stacks a dialog on top of an open one instead of replacing it,
    # so every opener has to close the others first or the previous sheet waits
    # underneath and reappears when the new one is dismissed.
    assert "function closeOtherSheets(" in script
    for keep in ("rubric-dialog", "contact-dialog", "cite-dialog", "cli-dialog"):
        assert f'closeOtherSheets("{keep}");' in script
    guard = script.split("function closeOtherSheets(", 1)[1].split("\n}", 1)[0]
    for dialog in ("rubric-dialog", "contact-dialog", "cite-dialog", "cli-dialog"):
        assert dialog in guard
    # Dropped before closing, so the sheet being replaced does not step history
    # back through the entry the reader arrived on.
    assert guard.index("rubricOwnsHistoryEntry = false;") < guard.index("other.close();")
    assert guard.index("citeOwnsHistoryEntry = false;") < guard.index("other.close();")
    assert guard.index("cliOwnsHistoryEntry = false;") < guard.index("other.close();")


def test_visible_navigation_items_use_the_same_active_state():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # Explore and Rubric keep direct routes without claiming a global tab.
    nav = html.split('<nav class="view-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/explore/"' not in nav
    assert 'href="/rubric/"' not in nav
    assert 'aria-expanded="false"' in nav
    today = re.search(r'<button\b(?=[^>]*data-view="today")[^>]*>', html)
    assert today and "nav-active" in today.group(0)
    assert 'aria-current="page"' in today.group(0)
    assert "function syncNavState()" in script
    assert 'item.classList.toggle("nav-active", active);' in script
    assert 'rubricNav.classList.toggle("nav-active", rubricActive);' not in script
    assert script.count("syncNavState();") >= 3
    assert ".view-nav .nav-active {" in styles
    assert '.view-nav button[aria-current="page"]' not in styles


def test_recommendation_threshold_does_not_gate_inclusion_and_rows_carry_no_badge():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #248: the badge was removed because it flagged most top-ranked
    # rows and so communicated nothing. The rubric still explains that the
    # threshold does not control inclusion.
    assert "recommendation-badge" not in script
    assert 'text: t("Recommended")' not in script
    assert "Recommended to review" not in script
    assert "not an endorsement" in script
    assert "it does not control inclusion" in script
    assert "Every record matching at least one taxonomy category is retained" in script
    assert "This historical scan used" in script
    assert "Records below it were not retained" in script
    assert "selectedDay?.selection?.minimum_score" in script


def test_scan_date_select_is_not_reset_by_the_shared_filters_input_handler():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #43: a <select> fires "input" before "change". The shared
    # #filters input handler must not re-render on the Scan date select's
    # bubbled "input" event, or it clobbers the pick with the stale date
    # before the select's own dedicated "change" handler runs.
    filters_handler = script.split('byId("filters").addEventListener("input"', 1)[1]
    handler_body = filters_handler.split("});", 1)[0]
    assert 'event.target === byId("today-date")' in handler_body
    assert "return" in handler_body


def test_scan_date_can_be_reset_to_all_dates():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'option("all", t("All dates"), state.todayDate === "all")' in script
    assert 'state.todayDate === "all" || item.snapshot_date === state.todayDate' in script
    assert 'state.todayDate = "all";' in script
    assert 'params.set("date", "all")' in script
    # The list is bounded by explicit pages (issue #322), so reaching the
    # footer never silently appends the rest of the archive.
    assert "observations.slice(pageStart, pageEnd)" in script
    assert "state.todayPage += 1" in script
    assert "const TODAY_PAGE_SIZE = 20;" in script
    assert 'id="today-page-status"' in html
    assert 'id="today-page-prev"' in html
    assert 'id="today-page-next"' in html
    assert "IntersectionObserver" not in script
    assert 'byId("daily-briefing").hidden = showingAllDates' in script
    assert 'byId("source-health-panel").hidden = showingAllDates' in script


def test_search_defaults_to_all_dates_and_explains_the_scope():
    """Issue #481: searching must not silently inherit the newest scan."""
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # The scope explanation is the first row of the results area, before both
    # registry matches and daily-discovery matches.
    assert 'id="search-scope-banner"' in html
    assert html.index('id="search-scope-banner"') < html.index('id="today-benchmarks"')
    assert html.index('id="search-scope-banner"') < html.index('id="today-list"')
    assert ".search-scope-banner" in styles

    # A typed query and a bare ?q= permalink both start archive-wide. Once the
    # reader explicitly narrows an existing query, continued typing preserves it.
    assert 'params.get("date") || (state.q ? "all" : "")' in script
    handler = script.split('byId("filters").addEventListener("input"', 1)[1].split("});", 1)[0]
    assert "const hadQuery = Boolean(state.q.trim());" in handler
    assert 'state.todayDate = "all";' in handler
    assert "!hadQuery && state.q.trim()" in handler
    assert "ensureFullData()" in handler

    # The banner offers a real today link, and large result sets point to the
    # public CLI setup route for a complete export.
    banner = script.split("function renderSearchScopeBanner", 1)[1].split(
        "function renderToday", 1
    )[0]
    assert 'state.todayDate !== "all"' in banner
    assert "totalResults > 10" in banner
    assert 'attrs: { href: "/cli/" }' in banner
    assert "openCli();" in banner
    assert 'text: t("Search today")' in banner
    assert "state.todayDate = state.data.latest_date;" in banner
    assert "(state.q || state.todayDate !== state.data?.latest_date)" in script
    assert '"This search covers all dates.": "此处搜索全部日期的结果。"' in script


def test_dashboard_bounds_work_before_and_during_filtering():
    """Issue #222: hidden views and unbounded card lists must not block input."""
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "state.observations = [...evidence, ...attention].sort" in script
    assert "if (state.observations) return state.observations" in script
    assert "const visibleObservations = observations.slice(pageStart, pageEnd)" in script
    assert "renderToday({ resultsOnly: true })" in script
    assert 'if (state.view === "today") renderToday()' in script
    assert 'if (state.view === "leaderboard") renderLeaderboard()' in script
    assert "function rerenderCurrentView()" in script


def test_automatic_frontier_default_does_not_leak_into_unrelated_urls():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "lfrontierExplicit: false" in script
    assert "state.lfrontierExplicit = Boolean(state.lfrontier)" in script
    assert "if (state.lfrontierExplicit && state.lfrontier)" in script
    assert "state.lfrontierExplicit = false" in script
    assert "function selectFrontier(benchmarkId)" in script


def test_each_view_serializes_only_the_filters_it_reads():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    body = script.split('function writeUrl(mode = "replace")', 1)[1].split("\nfunction ", 1)[0]

    # Issue #123: a reader clicking a trend date got
    # ?date=...&lfrontier=apex_agents, and switching to the leaderboard carried
    # ?date=... along, because writeUrl() wrote every filter on every view.
    # Each param is read back by exactly one view, so only that view may write
    # it. Guard the gate rather than the individual set() calls, which the
    # previous fix already had and which still leaked.
    today = body.split('if (!utility && state.view === "today")', 1)[1].split(
        'if (!utility && state.view === "map"', 1
    )[0]
    for key in ("date", "q", "kind", "category", "source", "organization", "event"):
        assert f'params.set("{key}"' in today

    leaderboard = body.split('if (!utility && state.view === "leaderboard")', 1)[1]
    for key in ("lq", "ldomain", "lorg", "lera", "lfrontier"):
        assert f'params.set("{key}"' in leaderboard

    assert 'if (!utility && state.view === "map" && state.entity) params.set("entity"' in body


def test_site_has_an_icon():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    # Issue #152: without this the browser requests /favicon.ico and 404s, so
    # tabs and bookmarks fall back to a blank page glyph. The referenced file
    # is checked for existence by test_static_html_references_existing_local_assets.
    assert parser.icon_hrefs, "index.html declares no icon"


def test_top_right_utilities_use_shared_icon_geometry_and_contact_control():
    html = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert 'id="badge-contact"' in html
    # The export badge is gone (issue #311): dataset requests go through the
    # contact sheet and the footer note, not a header button.
    assert 'id="badge-export"' not in html
    assert 'id="export-dialog"' not in html
    assert 'id="badge-wechat"' not in html
    assert 'id="badge-discord"' not in html
    assert 'id="lang-toggle"' in html
    assert 'class="repo-badge"' in html
    assert "grid-template-columns: repeat(4, 2.6rem)" in styles
    assert "width: 2.6rem" in styles
    assert "height: 2.6rem" in styles
    assert ".repo-badges" not in styles
    assert 'class="repo-badge-glyph" id="lang-toggle-label">中<' in html
    assert 'class="brand-icon github-icon"' in html
    assert "grid-template-columns: repeat(4, 2.1rem)" in styles
    assert "flex: 0 0 1.5rem" in styles
    assert ".repo-badge svg," in styles


def test_top_right_utilities_have_immediate_visible_feedback():
    """Issue #228: feedback includes a fast high-contrast state and label."""
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert 'node.setAttribute("data-tooltip", resolved)' in script
    assert 'node.removeAttribute("title")' in script
    badge = styles.split(".repo-badge {", 1)[1].split("}", 1)[0]
    feedback = styles.split(".repo-badge:hover,", 1)[1].split("}", 1)[0]
    assert "60ms" in badge
    assert "background: var(--ink)" in feedback
    assert "color: var(--panel)" in feedback
    assert "content: attr(data-tooltip)" in styles


def test_language_toggle_and_contact_labels_are_translated():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'data-i18n-title="Switch to Chinese (中文)"' in html
    for key in (
        '"Site utilities": "网站工具"',
        '"Switch to Chinese (中文)": "切换到中文"',
        'Contact: "联系"',
    ):
        assert key in script


def test_issue_316_benchmark_detail_labels_are_translated():
    # The crawled benchmark detail panel (identity / openness / size) rendered
    # its headings, field labels and "not established" placeholders through t(),
    # but only "Released" had a zh entry -- so under Chinese the whole panel
    # except that one line fell back to English. Every label the panel draws
    # must have a zh translation.
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    for key in (
        'Identity: "基本信息"',
        'Publisher: "发布方"',
        'Modality: "模态"',
        'Openness: "开放性"',
        'Size: "规模"',
        '"Code licence": "代码许可证"',
        '"Data licence": "数据许可证"',
        '"not established": "尚未确定"',
        '"description not established": "简介尚未确定"',
        '"publisher not established": "发布方尚未确定"',
        '"release date not established": "发布日期尚未确定"',
        '"modality not established": "模态尚未确定"',
        '"openness not established": "开放性尚未确定"',
        '"size not established": "规模尚未确定"',
        '"No openness evidence recorded.": "未记录开放性证据。"',
        'open: "开放"',
        'restricted: "受限"',
        'Paper: "论文"',
        '"Code repository": "代码仓库"',
        'Dataset: "数据集"',
        '"Project site": "项目站点"',
        'maintainer: "维护者"',
        '"published the hub card": "发布了 Hub 卡片"',
        '"organization behind the paper": "论文背后的机构"',
        '"counts the": "统计的是"',
        '"what it counts is unclear": "统计对象不明"',
        '"evidence ↗": "证据 ↗"',
    ):
        assert key in script, f"missing zh translation for {key!r}"

    # The longest placeholder wraps onto its own line in the source, so assert
    # the value rather than a single-line "key": "value" pair.
    assert "尚未确定论文、代码仓库、数据集或站点链接。" in script
    # The #262 inheritance note also wraps onto its own line.
    assert "人工核对确认它指向同一个benchmark" in script


def test_language_toggle_click_handler_is_wired():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The 中文 button must actually respond to a click: bindEvents has to attach
    # toggleLang to #lang-toggle, otherwise clicking it silently does nothing.
    assert 'langToggle.addEventListener("click", toggleLang)' in script


def test_rubric_dialog_is_linkable_by_clean_path_and_version_query():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #41: current and historical rubrics remain shareable, but the
    # content now has one indexable path rather than fragment-only states.
    assert "state.rubric" in script
    assert 'pathUtility === "rubric"' in script
    assert 'currentParams.get("version") || "current"' in script
    assert 'params.set("version", state.rubric)' in script
    assert 'canonical: "/rubric/"' in script
    # Old fragments are still understood long enough to replace-migrate them.
    assert 'rawHash === "rubric"' in script
    assert 'state.rubric === "current" ? null : state.rubric' in script


def test_contact_stays_in_page_while_rubric_uses_its_clean_path():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'rawHash === "contact"' in script
    assert 'hash = "contact"' in script
    assert "state.contact = true;" in script
    assert "openContact(false)" in script
    assert "UTILITY_SEO[utility].canonical" in script
    # The current rubric has no query; historical records keep their version.
    assert 'state.rubric !== "current"' in script


def test_clean_route_model_migrates_legacy_urls_and_preserves_utility_backgrounds():
    """Execute the real URL functions against a small browser-history stub."""
    import json
    import shutil
    import subprocess

    import pytest

    source = Path("site/assets/app.js").read_text(encoding="utf-8")
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")

    def section(start: str, end: str) -> str:
        return source[source.index(start) : source.index(end, source.index(start))]

    route_source = "\n".join(
        (
            section("const VIEW_SEO = {", "// These sheets are also indexable pages."),
            section("const UTILITY_SEO = {", "// One list, not two:"),
            section("const VIEW_PATHS =", "function applySeo("),
            section("function readUrl()", "// `push` adds a history entry"),
            section("function writeUrl(", "// A pushed entry changes the URL"),
        )
    )
    program = f"""
const state = {{}};
{route_source}
function install(url, historyState = null) {{
  const parsed = new URL(url, "https://benchmark-radar.org");
  window.location.pathname = parsed.pathname;
  window.location.search = parsed.search;
  window.location.hash = parsed.hash;
  window.history.state = historyState;
}}
function applyHistory(stateValue, url) {{
  install(url, stateValue);
}}
globalThis.window = {{
  location: {{ origin: "https://benchmark-radar.org", pathname: "/", search: "", hash: "" }},
  history: {{
    state: null,
    pushState(stateValue, _title, url) {{ applyHistory(stateValue, url); }},
    replaceState(stateValue, _title, url) {{ applyHistory(stateValue, url); }},
  }},
}};
const results = {{}};
install("/?view=leaderboard&lq=agent");
readUrl();
writeUrl("replace");
results.legacyView = window.location.pathname + window.location.search;

install("/#rubric=2");
readUrl();
writeUrl("replace");
results.legacyRubric = window.location.pathname + window.location.search;
results.legacyReturns = window.history.state.benchmarkRadarUtility.returnOnClose;

install("/leaderboard/?lq=agent");
readUrl();
state.cli = true;
writeUrl("push");
results.openCli = window.location.pathname + window.location.search;
results.background = window.history.state.benchmarkRadarUtility;
readUrl();
results.forwardView = state.view;
results.forwardQuery = state.lq;

install("/cite/");
readUrl();
results.directCite = {{ view: state.view, cite: state.cite }};
console.log(JSON.stringify(results));
"""
    result = subprocess.run(
        [node, "-e", program], capture_output=True, text=True, timeout=60, check=True
    )
    routes = json.loads(result.stdout)

    assert routes["legacyView"] == "/leaderboard/?lq=agent"
    assert routes["legacyRubric"] == "/rubric/?version=2"
    assert routes["legacyReturns"] is False
    assert routes["openCli"] == "/cli/"
    assert routes["background"] == {
        "utility": "cli",
        "backgroundView": "leaderboard",
        "backgroundUrl": "/leaderboard/?lq=agent",
        "returnOnClose": True,
    }
    assert routes["forwardView"] == "leaderboard"
    assert routes["forwardQuery"] == "agent"
    assert routes["directCite"] == {"view": "today", "cite": True}


def test_utility_routes_have_distinct_metadata_and_accessible_active_state():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    utility_seo = script.split("const UTILITY_SEO = {", 1)[1].split("\n};", 1)[0]

    for utility, path in (("cli", "/cli/"), ("cite", "/cite/"), ("rubric", "/rubric/")):
        entry = utility_seo.split(f"  {utility}: {{", 1)[1].split("  },", 1)[0]
        assert "title:" in entry
        assert "description:" in entry
        assert f'canonical: "{path}"' in entry
    assert "applySeo(utility ? UTILITY_SEO[utility]" in script
    assert 'rubricNav.setAttribute("aria-current", "page")' not in script
    assert 'cliNav.setAttribute("aria-current", "page")' in script
    assert 'citeOpen?.setAttribute("aria-expanded", String(utility === "cite"))' in script
    assert 'citeOpen?.setAttribute("aria-current", "page")' in script


def test_routes_degrade_to_static_pages_and_refresh_the_payload_the_route_needs():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    nav = script.split('document.querySelectorAll("[data-view]")', 1)[1].split(
        "// Reads every control rather than the event target", 1
    )[0]
    refresh = script.split("async function refreshData()", 1)[1].split(
        "async function initialize()", 1
    )[0]
    initialize = script.split("async function initialize()", 1)[1]

    # A copied trend-day link must leave /trends/ even without JavaScript.
    assert "attrs: { href: `/?date=${day.date}` }" in script
    # Missing bootstrap data falls through to a real anchor; a failed lazy full
    # fetch hard-navigates to that generated route instead of swallowing click.
    assert "if (!compatibleDashboard(state.data))" in nav
    assert "if (anchor) return;" in nav
    assert 'window.location.assign(anchor?.href || VIEW_PATHS[view] || "/")' in nav
    assert "const navigationSequence = ++viewNavigationSequence;" in nav
    assert nav.count("navigationSequence !== viewNavigationSequence") == 2

    # A route that needs history selects radar.json before fetching, verifies
    # again after assignment, and only then retires the visible error.
    assert "state.fullDataLoaded || stateNeedsFullData()" in refresh
    assert 'needsFullPayload ? "/data/radar.json" : "/data/radar-bootstrap.json"' in refresh
    assert 'if (stateNeedsFullData()) await ensureFullData("reload");' in refresh
    assert refresh.index(
        'if (stateNeedsFullData()) await ensureFullData("reload");'
    ) < refresh.index('byId("error-state").hidden = true;')
    # A stale full-data failure from the route that initialized the document
    # cannot erase a newer view (or a successful Refresh) that the payload in
    # state already satisfies.
    assert "initializationWasSuperseded" in initialize
    assert "initializationNavigationSequence !== viewNavigationSequence" in initialize
    assert "initializationRefreshSequence !== successfulDataRefreshSequence" in initialize
    recovery = initialize.split("initializationWasSuperseded", 2)[2].split("// /leaderboard/", 1)[0]
    assert "rerenderCurrentView();" in recovery
    assert "return;" in recovery


def test_newer_successful_data_requests_cannot_be_overwritten_by_late_responses():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    apply_data = script.split("function applyDashboardData", 1)[1].split("function element", 1)[0]
    refresh = script.split("async function refreshData()", 1)[1].split(
        "async function initialize()", 1
    )[0]
    initialize = script.split("async function initialize()", 1)[1]

    assert "requestSequence < latestAppliedDashboardRequestSequence" in apply_data
    assert "latestAppliedDashboardRequestSequence = requestSequence" in apply_data
    assert "const requestSequence = ++nextDashboardRequestSequence;" in refresh
    assert "if (!applyDashboardData(data, requestSequence" in refresh
    assert "const requestSequence = ++nextDashboardRequestSequence;" in initialize
    assert "if (!applyDashboardData(data, requestSequence, false)) return;" in initialize
    ensure_full = script.split("async function ensureFullData", 1)[1].split(
        "async function ensureDataForState", 1
    )[0]
    assert "if (!applied && !state.fullDataLoaded)" in ensure_full
    assert "Full data request was superseded by a bootstrap response" in ensure_full


def test_rubric_remains_a_direct_route_without_a_navigation_control():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="rubric-nav"' not in html
    assert 'canonical: "/rubric/"' in script
    assert 'state.rubric = pathUtility === "rubric"' in script
    assert 'openRubric(null, state.rubric === "current" ? null : state.rubric, false)' in script


def test_hydrated_expansion_controls_announce_the_action_they_will_take():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    top = script.split("function renderLeaderboardTop", 1)[1].split(
        "function syncLeaderboardNav", 1
    )[0]
    table = script.split("const showAllButton =", 1)[1].split("const cards =", 1)[0]

    assert 'more.setAttribute("aria-label", label);' in top
    assert 'showAllButton.setAttribute("aria-label", showAllLabel);' in table


def test_seeded_utility_dialog_is_promoted_without_an_invalid_second_open():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    promote = script.split("function promoteSeededDialog", 1)[1].split(
        "function showModalDialog", 1
    )[0]
    show = script.split("function showModalDialog", 1)[1].split("let rubricOwnsHistoryEntry", 1)[0]
    initialize = script.split("async function initialize()", 1)[1]

    assert 'dialog.hasAttribute("data-seed")' in promote
    assert promote.index('dialog.removeAttribute("open")') < promote.index("dialog.showModal()")
    assert "replaceChildren" not in promote
    assert "if (!dialog.open) dialog.showModal();" in show
    assert "promoteSeededDialog(byId(`${seededUtility}-dialog`))" in initialize
    assert initialize.index("promoteSeededDialog") < initialize.index(
        'fetch("/data/radar-bootstrap.json")'
    )


def test_initial_page_uses_small_bootstrap_and_lazy_loads_history():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    initialize = script.split("async function initialize()", 1)[1]
    assert 'fetch("/data/radar-bootstrap.json")' in initialize
    assert "await ensureDataForState();" in initialize
    loader = script.split("async function ensureFullData(", 1)[1].split("\nasync function ", 1)[0]
    assert 'fetch("/data/radar.json", { cache })' in loader
    assert '["trends", "map"].includes(state.view)' in script
    assert 'state.todayDate === "all"' in script


def test_rubric_is_read_from_published_data_not_restated_in_the_browser():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # A second hardcoded copy of the weights in the browser is exactly the
    # drift this rubric exists to prevent.
    assert "state.data?.rubrics" in script
    assert "0.40 relevance" not in script
    assert "0.25 evidence" not in script
    for weight in ("0.4 *", "0.25 *", "0.2 *", "0.15 *"):
        assert weight not in script
    assert 'text: "/ 4.00"' not in script


def test_attention_signals_are_not_offered_the_evidence_rubric():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "isAttention ? attentionActivity(item) : scoreBlock(item)" in script
    assert "openRubric(item)" not in script[script.index("function attentionActivity") :]


def test_detail_grid_shows_every_component_that_moves_the_total():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    for component in ("Priority", "Relevance", "Evidence", "Recency", "Adoption"):
        assert f'[t("{component}"), Number(item.' in script


def test_today_view_has_one_filterable_observation_list_and_one_source_status():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The heading appears in the data-i18n key and the visible text.
    assert html.count("Today's radar") == 2
    assert 'id="today-list"' in html
    assert 'id="filters"' in html
    assert 'id="kind-filter"' in html
    assert (
        "visibleObservations.map((item, offset) => observationCard(item, pageStart + offset))"
        in script
    )
    assert "Daily field note" not in html
    assert "What entered the field?" not in html
    assert "today-overview" not in html
    assert "today-attention-list" not in html
    assert "Sources in results" not in script
    assert "health-summary" not in html


def test_today_toolbar_keeps_secondary_filters_in_a_popover():
    """Issue #248: the first viewport must stay on results, so the five
    secondary filters live in a drawer behind a trigger whose badge counts
    the active ones, and the toolbar adds a refresh control."""
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="filters-drawer"' in html
    assert 'id="filters-toggle"' in html
    assert 'id="filters-count"' in html
    assert 'id="refresh-button"' in html
    assert 'id="search-filter"' in html
    assert 'id="kind-filter"' in html
    assert 'id="category-filter"' in html
    assert 'id="source-filter"' in html
    assert 'id="organization-filter"' in html
    assert 'id="event-filter"' in html
    assert 'id="clear-filters"' in html
    assert "function updateFiltersCount()" in script
    assert "function closeFiltersDrawer()" in script
    assert "function refreshData()" in script
    assert "state.fullDataLoaded || stateNeedsFullData()" in script
    assert 'needsFullPayload ? "/data/radar.json" : "/data/radar-bootstrap.json"' in script
    assert 'const response = await fetch(path, { cache: "reload" });' in script
    assert "drawer.hidden = true" in script


def test_summaries_truncate_at_a_word_boundary():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'const lastSpace = candidate.lastIndexOf(" ");' in script
    assert "candidate.slice(0, lastSpace)" in script
    assert "shorten(item.summary)" in script


def test_site_does_not_render_source_content_as_html():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert ".innerHTML" not in script
    assert ".outerHTML" not in script
    assert "document.write" not in script
    assert " eval(" not in script


def test_attention_signals_use_activity_metrics_not_quality_scores():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'text: t("Not quality-scored")' in script
    assert '[t("Submissions"), Number(item.metrics?.submissions ?? 1).toLocaleString()]' in script
    assert '[t("Published"), formatDate(item.published_at' in script
    assert "supporting_observations" in script
    assert "total_score: 0" not in script
    assert "evidence_score: 0" not in script


def test_evidence_cards_show_fetched_source_metadata_without_inventing_zeroes():
    """Issue #361: raw facts must be visible beside the derived score."""
    import json
    import shutil
    import subprocess

    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    node = shutil.which("node")
    assert node is not None, "Node.js is required for the site behavior tests"
    result = subprocess.run(
        [node, "tests/record_facts_harness.mjs"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    facts = json.loads(result.stdout)

    assert facts["reported"] == [
        ["Organizations", "OpenAI"],
        ["Authors", "Alice, Bob +1"],
        ["Stars", "0"],
    ]
    assert facts["unreported"] == [
        ["Authors", "Deyao Hong"],
        ["Activity counters", "Not reported by this source"],
    ]
    assert facts["dates"] == [
        ["Published", "date:2026-08-24T17:59:04Z"],
        ["Updated", "date:2026-08-25T17:59:04Z"],
    ]
    assert facts["rendered"] == {
        "tag": "div",
        "className": "record-facts",
        "role": "group",
        "ariaLabel": "Source metadata",
    }
    assert ".record-facts" in styles


def test_main_filters_use_persisted_attention_and_snapshot_dates():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert "loadExternalFeeds" not in script
    assert "state.external" not in script
    assert "day.attention.observations.map" in script
    assert "snapshot_date: day.date" in script
    assert 'id="kind-filter"' in html
    assert "renderExplorer" not in script
    assert "explorer-view" not in html


def test_all_dates_keeps_only_the_latest_matching_sighting_per_source_record():
    import json
    import shutil
    import subprocess

    import pytest

    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    assert 'state.todayDate === "all" ? latestObservationsByRecord(matches) : matches' in script

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, "tests/deduplicate_observations_harness.mjs"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    rows = json.loads(result.stdout)

    assert [(row["source"], row["source_id"], row["snapshot_date"]) for row in rows] == [
        ("GitHub Release", "modelscope/evalscope@v1.11.0", "2026-08-26"),
        ("GitHub", "modelscope/evalscope@v1.11.0", "2026-08-25"),
        ("Hacker News", "123", "2026-08-26"),
        ("arXiv", "2608.00001", "2026-08-24"),
    ]


def test_records_expand_inline_without_an_exclusive_accordion_or_record_modal():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert '"details"' in script
    assert '"summary"' in script
    assert "record-detail" in script
    assert ".record-summary::before" in styles
    assert ".record-card[open] > .record-summary::before" in styles
    assert "detail-dialog" not in html
    assert "detail-dialog" not in script
    # A shared details[name] would force one row closed when another opens.
    assert "attrs: { name:" not in script
    # The dialogs on the page are non-record chrome: the scoring rubric, the
    # contact sheet (the export dialog went with the export button, issue
    # #311), the citation card, and the CLI setup card. Record detail must stay
    # inline, so a showModal() the list below does not name is a regression to a
    # record modal.
    assert script.count(".showModal()") == 3
    assert 'byId("rubric-dialog")' in script
    assert 'byId("contact-dialog")' in script
    assert 'byId("cite-dialog")' in script
    assert 'byId("cli-dialog")' in script
    for opener in ("openRubric", "openCite", "openCli"):
        body = script.split(f"function {opener}(", 1)[1].split("\n}", 1)[0]
        assert "showModalDialog(dialog);" in body


def test_hugging_face_expansion_links_to_the_full_card():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'item.source === "Hugging Face"' in script
    assert '"Read full card ↗"' in script


def test_expanded_detail_continues_past_the_teaser_instead_of_repeating_it():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "function summaryRemainder(fullText, teaser)" in script
    assert "summaryRemainder(item.summary, teaser)" in script
    # expandedRecord must receive the same teaser text the summary row shows,
    # or the remainder cannot know what the reader already read.
    assert 'expandedRecord(item, (item.summary || "").trim() ? summary : "")' in script


def test_trend_map_is_keyboard_accessible_and_coordinates_today_filters():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="map-view"' in html
    assert 'canonical: "/explore/"' in script
    assert 'id="map-canvas"' in html
    assert "state.data.corpus" in script
    assert "HAS_TOPIC" in script
    assert '"aria-label": `${entity.type}: ${entity.label}`' in script
    assert 'event.key === "Enter" || event.key === " "' in script
    assert "mapFilterFor(entity)" in script
    assert "View matching observations →" in script
    assert 'setView("today")' in script
    assert 'id="organization-filter"' in html
    assert "state.organization" in script


def test_dashboard_links_are_validated_escaped_and_non_swallowing():
    # Regression guards for the browser-side hardening: every external href is
    # produced by safeHttpUrl; the interactive map is role="group" (ARIA makes
    # descendants of role="img" presentational, hiding its focusable markers);
    # Escape yields to an open dialog instead of swallowing the first press;
    # and clearing the adoption frontier also clears its org color key.
    #
    # The CSV formula-quoting guard retired with the client-side export
    # (issue #311 removed the export dialog and its CSV builder).
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "function safeHttpUrl(" in script
    # The curated chart's SVG root and the crawled chart's SVG root are both
    # role="group" (image descendants are presentational in ARIA, which would
    # hide their focusable marker buttons). role="img" is reserved for the
    # adoption bar, a non-interactive widget; every chart point -- curated or
    # crawled -- is role="button" via makeFrontierPointInteractive's pinned
    # tooltip, not role="img", because it is a focusable, clickable marker.
    assert 'role: "group"' in script
    assert script.count('role: "img"') == 1
    assert 'document.querySelector("dialog[open]")' in script
    assert "Do not swallow Escape" in script
    assert 'replaceChildren(byId("frontier-org-key"), [])' in script


def test_corpus_view_progressively_discloses_the_complete_relationship_map():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    nav = html.split('<nav class="view-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/explore/"' not in nav
    assert 'id="map-insights"' in html
    assert '<details class="relationship-explorer" id="relationship-explorer">' in html
    assert "renderMapInsights(corpus)" in script
    assert "Who appears most" in script
    assert "if (!explorer.open)" in script
    assert 'replaceChildren(byId("map-canvas"), [])' in script
    assert "if (selectedFromUrl) explorer.open = true" in script
    assert ".slice(0, 16)" not in script


def test_trends_gate_comparisons_on_connector_coverage():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "sameCollectionContext" in script
    assert "coverage_signature" in script
    assert "Coverage is incomplete:" in script


def test_trend_chart_can_filter_to_releases_only():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="trend-released-only"' in html
    assert 'byId("trend-released-only")' in script
    assert "state.trendReleasedOnly" in script
    assert "day.category_counts_released" in script
    # The domain card shows the release count as the headline, and reports
    # anything set aside as an update rather than dropping it silently.
    assert "trend.total_count" in script
    assert "also updated (not counted above)" in script


def test_trend_chart_does_not_stack_overlapping_categories():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert "Category tags overlap. Each bar is an independent count" in html
    assert 'className: "series-bars" }, [...segments, attentionBar]' in script
    assert 'className: "bar-stack"' not in script
    assert "overlapping evidence category matches" in script
    assert "Math.max(...Object.values(countsFor(day)), day.attention.active_count)" in script
    assert ".bar-stack" not in styles
    assert ".attention-volume {\n  background: var(--ink);" in styles


def test_static_html_references_existing_local_assets():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    # Pages generates these from validated source data before upload. Their
    # generators and rendered structure have dedicated tests, while this check
    # remains about static assets that must exist in a clean checkout.
    # radar.json is the dashboard bundle the "Download the dataset" link points
    # at. Pages writes it during the build, before the artifact upload, so the
    # published link resolves; it is absent from a clean checkout by design.
    # The view paths are this same document republished by app_pages.py, also
    # during the build.
    generated_assets = {
        "feed.xml",
        "data/radar.json",
        "blog/",
        "leaderboard/",
        "trends/",
        "explore/",
        "rubric/",
        "cli/",
        "cite/",
    }
    missing = []
    for reference in parser.local_refs:
        # References are root-absolute because this document is also served at
        # /leaderboard/, /trends/ and /explore/. Strip the leading slash so the
        # target resolves inside site/ rather than at the filesystem root.
        path = urlsplit(reference).path.lstrip("/")
        target = Path("site") if path in {"", ".", "./"} else Path("site") / path
        if not target.exists() and path not in generated_assets:
            missing.append(reference)

    assert not missing


def test_one_snapshot_trend_explains_history_requirement():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert 't("At least two daily snapshots are required to calculate a trend")' in script
    assert "dayCount === 1" in script
    assert "[hidden]" in styles
    assert "display: none !important" in styles


def test_supporting_attention_provider_is_not_hard_coded():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "`${record.source || item.source} #${record.source_id}`" in script
    assert "Hacker News #${record.source_id}" not in script


def test_header_keeps_one_github_action_and_issues_remain_reachable():
    html = Path("site/index.html").read_text(encoding="utf-8")

    # The header keeps one GitHub destination. Issue links remain in context.
    assert 'href="https://github.com/ktwu01/benchmark-radar"' in html
    assert "https://github.com/ktwu01/benchmark-radar/issues" in html
    assert 'id="badge-forks"' not in html
    assert 'id="badge-issues"' not in html
    assert "/stargazers" not in html
    assert "benchmark-radar/forks" not in html

    assert ">Star<" in html

    # Starring has no GET endpoint, so the star badge opens the repository and
    # the reader clicks Star there. Asserting the absence of a fabricated
    # /star URL keeps a future edit from inventing one that 404s.
    assert "benchmark-radar/star" not in html


def test_today_view_shows_total_corpus_counts_by_category():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #52: how many distinct artifacts the whole corpus has ever
    # surfaced, by category, alongside the existing per-source health panel.
    assert 'id="corpus-totals-list"' in html
    assert 'id="corpus-totals-status"' in html
    assert "state.data.corpus?.aggregates?.topics" in script
    assert "state.data.corpus?.aggregates?.entity_types?.artifact" in script
    # Issue #183: the totals start collapsed so the long topic list never takes
    # over the page, and the summary still tells the reader the total so no one
    # has to expand it to learn how big the corpus is. No `open` attribute.
    assert '<details id="corpus-totals-details">' in html
    assert 'corpus-totals-details" open>' not in html
    summary_status = 'corpus-totals-status").textContent = '
    assert f'{summary_status}`${{totalArtifacts.toLocaleString()}} ${{t("artifacts")}}`' in script


def test_badge_accessible_names_state_the_action():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "function setStarCount" in script
    assert "Star this repository on GitHub" in script
    assert "Fork this repository on GitHub" not in script
    assert "Open a new issue on GitHub" not in script
    assert 'badge.setAttribute("aria-label"' in script


def test_repo_badge_counts_are_visible():
    css = Path("site/assets/styles.css").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")

    # Issue #402: the GitHub API count should be useful to sighted visitors,
    # not only present as clipped text for screen readers.
    assert 'id="badge-stars"' in html
    assert ".repo-badge-count" in css
    assert (
        "clip-path: inset(50%)"
        not in css[css.index(".repo-badge-count") : css.index(".feed-badge svg")]
    )
    assert (
        "background: var(--panel)"
        in css[css.index(".repo-badge-count") : css.index(".feed-badge svg")]
    )


def test_leaderboard_view_is_a_first_class_dashboard_view():
    parser = SiteParser()
    html = Path("site/index.html").read_text(encoding="utf-8")
    parser.feed(html)
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The interactive state remains first class even though the crawlable href
    # now points at a static landing page and JavaScript intercepts the click.
    assert "leaderboard-view" in parser.ids
    assert 'data-view="leaderboard"' in html
    assert '"map", "leaderboard"' in script
    assert 'if (view === "leaderboard") renderLeaderboard();' in script
    assert "state.data?.model_card_leaderboard" in script


def test_leaderboard_states_what_it_measures_before_the_ranking():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # A reader who takes the order as a quality ranking draws the opposite of
    # the intended conclusion, so the correction is published data shown in the
    # heading rather than a restated string in the browser or a footnote.
    assert 'id="leaderboard-measures"' in html
    assert 'byId("leaderboard-measures").textContent = board.measures' in script
    assert "vendor attention, not benchmark quality" not in script
    # Per-benchmark caveats travel with each row.
    assert "entry.caveat" in script


def test_leaderboard_rows_link_back_to_the_model_cards_they_counted():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="leaderboard-cards"' in html
    assert "adopter-list" in script
    assert '"Reported by"' in script
    # Every adopter link opens the source document itself, so any count in the
    # ranking can be checked against the card it was read from.
    assert "adopter.url" in script
    assert 'rel: "noopener noreferrer"' in script


def test_summary_counts_expand_to_the_records_behind_them():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    css = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # A summary count is a claim about specific records. "OpenAI: 5 cards" names
    # five documents, and a reader who cannot see which five takes it on faith,
    # so every row in the four registry cards opens to its own contents.
    assert "insight-row-expandable" in script
    assert "insightDetailList" in script
    assert ".map-insight-card li.insight-row-expandable" in css
    # The plain rows are flex containers; an expandable row has to become a block
    # so the expanded list can sit beneath its summary rather than beside it.
    expandable = css.split(".map-insight-card li.insight-row-expandable {", 1)[1]
    assert "display: block" in expandable.split("}", 1)[0]


def test_two_documents_about_one_model_are_labelled_apart():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Z.ai published both a GLM-5 model card and a GLM-5 technical report. Both
    # are counted, correctly, as separate adoptions, but labelling both
    # "Z.ai · GLM-5" makes a correct count look like a double-counting bug.
    assert "labelCounts" in script
    assert "cardLabel" in script


def test_leaderboard_filters_use_prefixed_url_keys():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Prefixed keys let one permalink hold a Today filter and a Leaderboard
    # filter at once without either view reinterpreting the other's
    # `organization`.
    assert 'id="leaderboard-filters"' in html
    for key in ("lq", "ldomain", "lorg", "lera"):
        assert f'params.set("{key}"' in script
        assert f'params.get("{key}")' in script


def test_leaderboard_filter_handler_reads_controls_not_the_event_target():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Same <select> "input"-before-"change" hazard as issue #43: reading all
    # four controls from the DOM makes the event ordering irrelevant.
    handler = script.split('byId("leaderboard-filters").addEventListener("input"', 1)[1]
    body = handler.split("});", 1)[0]
    for control in (
        "leaderboard-search",
        "leaderboard-domain",
        "leaderboard-organization",
        "leaderboard-era",
    ):
        assert f'byId("{control}")' in body


def test_release_date_filter_uses_fixed_eras_not_a_rolling_window():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="leaderboard-era"' in html
    # Fixed boundaries, so a shared "?lera=2026" link keeps meaning "released in
    # 2026" indefinitely rather than drifting into "the last N months".
    assert "LEADERBOARD_ERAS" in script
    assert '"2026-01-01"' in script
    # "Released in 2026" is bounded at both ends. With only a lower bound it
    # would silently absorb 2027 benchmarks the moment one is added.
    assert '"2027-01-01"' in script
    # ISO strings compare directly; no Date parsing means no timezone can move a
    # benchmark across a year boundary.
    assert "entry.released < era.from" in script
    assert "!entry.released) return false" in script


def test_unranked_rows_select_their_grid_by_class_not_has():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    css = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # This grid template is layout-critical: without it a card heading lands in
    # the 38px rank column and wraps one character per line. A :has() selector
    # is dropped whole by browsers that do not support it, restoring exactly
    # that bug, so the rule is keyed on an explicit class instead.
    assert "record-summary-unranked" in script
    assert ".record-summary.record-summary-unranked" in css
    # Scoped to selectors that set a grid template on a record summary. The
    # file's other `:has()` use is a hover de-emphasis on the trend chart, which
    # is cosmetic: a browser that drops it loses an effect, not a layout. This
    # rule decides column widths, so it must not be droppable.
    selectors = [
        line for line in css.splitlines() if line.rstrip().endswith("{") and "*" not in line
    ]
    assert not [line for line in selectors if ":has(" in line and "record-summary" in line]
    # Two classes outrank the single-class mobile rule, so the breakpoint needs
    # its own override or phones keep the desktop template.
    mobile = css.split("@media (max-width: 760px)", 1)[1]
    assert ".record-summary.record-summary-unranked" in mobile


def test_model_card_rows_expand_to_the_benchmarks_they_report():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The reverse direction of the registry link. A reader auditing our data
    # against a vendor PDF needs the card's full benchmark list in one place,
    # grouped the way the source groups it, plus a link to the source itself.
    assert "function modelCardRow(card)" in script
    assert "card.reported_benchmarks" in script
    assert '"Benchmarks this document reports"' in script
    assert "card-benchmark-group" in script
    assert '"Open source document ↗"' in script
    # Says a mention is not a score at the point where an expanded list would
    # otherwise read as an extract of the card's results table.
    assert "These are mentions, not scores" in script


def test_leaderboard_degrades_when_the_curated_registry_is_absent():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # No registry means no ranking. Hiding the nav entry and redirecting a
    # ?view=leaderboard permalink beats offering a tab that opens blank.
    assert "document.querySelector('[data-view=\"leaderboard\"]')" in script
    assert "navButton.hidden = !state.data?.model_card_leaderboard;" in script
    assert 'state.view === "leaderboard" && !state.data.model_card_leaderboard' in script
    # The entry has to reflect the data from every view, not only from the one
    # being rendered. Boot settles it before it picks a view to draw, so Today
    # cannot leave a dead tab on screen for a click to push /leaderboard/ over.
    boot = script.split("renderTodayDateOptions();\n    syncLeaderboardNav();", 1)
    assert len(boot) == 2, "boot does not sync the leaderboard nav"
    assert 'if (state.view === "leaderboard") renderLeaderboard();' in boot[1]


def test_leaderboard_names_an_unadopted_benchmark_rather_than_showing_a_bare_zero():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # A tracked benchmark no curated card reports is an observation about the
    # registry, not an empty row, and the domain summary counts only adopted
    # benchmarks so it must not claim to be the same figure as the filter.
    # Issue #183: the registry-overview coverage counts open to their itemized
    # evidence, so the tracked-vs-reported split is legible in the tiles too.
    assert '"not yet reported in these cards"' in script
    assert '"Benchmarks tracked"' in script
    assert '"Benchmarks reported at least once"' in script
    assert '"not yet reported"' in script


def test_leaderboard_domain_filter_offers_every_tracked_domain():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # board.domains counts only adopted benchmarks, so a domain whose
    # benchmarks are all unadopted would appear in the table with no way to
    # filter to it. The options come from the entries themselves.
    assert "new Set((board.entries || []).map((entry) => entry.domain))" in script


def test_filter_forms_do_not_submit_and_reload_the_page():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Both panels are <form>s whose state lives in the URL query the app builds
    # itself. Enter in a search field would fire an implicit GET carrying only
    # the named controls, dropping `view` and dumping the reader into Today.
    assert 'querySelectorAll("#filters, #leaderboard-filters")' in script
    assert 'form.addEventListener("submit", (event) => event.preventDefault())' in script


def test_a_zero_adoption_bar_has_no_visible_width():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The 2% floor keeps a one-card benchmark visible, but a bar beside a count
    # of 0 would contradict the number it encodes.
    assert "maxCount && entry.card_count" in script


def test_leaderboard_has_an_honest_time_based_score_track():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    # Whitespace-normalized: these are prose guarantees, and HTML collapses the
    # line wrapping, so a reflowed paragraph must not read as a lost disclaimer.
    prose = " ".join(html.split())

    assert 'id="adoption-frontier"' in html
    assert 'id="frontier-benchmark"' in html
    assert 'id="frontier-chart"' in html
    # `frontierEvents` outlives the staircase it was written for: the leaderboard
    # still counts first reports, and the score chart still reads the newest
    # mention date to bound its reading gap.
    assert "function frontierEvents(entry)" in script
    assert "const advances = !seenOrganizations.has(adopter.organization)" in script
    # The disclaimer this replaces separated reporting saturation from score
    # saturation, which mattered while a staircase led the panel. The panel now
    # shows only scores, so the guarantee is that it still declines to grade
    # them: saturation stays an editorial judgement, never a printed number.
    assert "no newer number could be read" in prose
    assert "stays a reading you make, not a score this panel prints" in prose


def test_new_benchmarks_are_visually_prioritized_without_changing_the_rank():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert "function isNewBenchmark(entry, board)" in script
    assert "cutoff.setUTCDate(cutoff.getUTCDate() - 548)" in script
    assert 'text: t("new benchmark")' in script
    assert '"New benchmarks"' in script
    assert ".benchmark-new" in styles
    assert "board.entries?.[0]?.card_count" in script


def test_share_card_is_declared_with_an_absolute_url():
    html = Path("site/index.html").read_text(encoding="utf-8")

    # Open Graph consumers do not resolve relative URLs, so a relative
    # og:image silently yields the same blank grey card as no tag at all
    # (issue #88). The failure is invisible from inside the site.
    assert 'property="og:image"' in html
    assert "https://benchmark-radar.org/assets/og-card.png" in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    # Declared dimensions let a consumer reserve the large-image layout before
    # the file is fetched; without them some fall back to a small thumbnail.
    assert 'property="og:image:width" content="1200"' in html
    assert 'property="og:image:height" content="630"' in html


def test_share_card_exists_at_the_declared_size():
    from PIL import Image

    card = Path("site/assets/og-card.png")
    assert card.exists(), "run scripts/generate_og_image.py"

    with Image.open(card) as image:
        # 1200x630 is the ratio Open Graph consumers crop to. A card generated
        # at another size loses its bottom line, which is where the "not
        # benchmark quality" caveat sits.
        assert image.size == (1200, 630)


def test_share_card_attributes_its_source_without_overlapping_the_caveat():
    from PIL import Image, ImageDraw

    sys.path.insert(0, "scripts")
    from generate_og_image import MARGIN, WIDTH, font

    # The card is built to be reposted, and a screenshot of a ranking with no
    # source is a claim nobody can check. Pillow does not wrap or shrink text:
    # if the caveat and the attribution stop fitting on one line they silently
    # draw over each other, and the rendered PNG is the only place that shows.
    draw = ImageDraw.Draw(Image.new("RGB", (WIDTH, 630)))
    caveat = draw.textlength("Vendor reporting convention, not benchmark quality", font=font(23))
    attribution = draw.textlength("github.com/ktwu01/benchmark-radar", font=font(21))

    assert caveat + attribution < WIDTH - 2 * MARGIN


def test_today_view_places_the_daily_briefing_in_the_sidebar():
    """Issue #248: matching results lead the view; the briefing rides along."""
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="daily-briefing"' in html
    assert 'id="daily-briefing-body"' in html
    # The matching results form the main column; the briefing describes the
    # whole scan date, so it sits in the sidebar above the Sources card.
    assert html.index('id="today-list"') < html.index('id="daily-briefing"')
    assert html.index('id="daily-briefing"') < html.index('id="source-health-panel"')
    assert "renderDailyBriefing(day)" in script


def test_daily_briefing_withholds_another_days_text_and_names_an_absent_one():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Reuse requires the stored briefing to match the day being rendered, so a
    # briefing carried over from another date is never shown beside these
    # listings.
    assert "briefing.date === day.date" in script
    assert "No briefing was recorded for this day." in script


def test_daily_briefing_links_only_cited_http_evidence_ids():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "validBriefingCitations(briefing.citations)" in script
    assert "briefingContent(line, citations)" in script
    assert "String(line).matchAll(/\\bE\\d{3}\\b/g)" in script
    assert '["http:", "https:"].includes(url.protocol)' in script
    assert 'className: "briefing-evidence-link"' in script
    assert 'target: "_blank"' in script
    assert 'rel: "noopener noreferrer"' in script
    assert "document.createTextNode(line.slice(cursor))" in script


def test_daily_briefing_renders_its_provenance_caveat_and_evidence_ledger():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'briefing.generator !== "openai-responses"' in script
    assert "via OpenAI Responses API" in script
    assert "input.evidence_items" in script
    assert "input.history_days" in script
    assert 'text: t("Caveat: ")' in script
    assert 'text: t("Evidence cited by GPT")' in script
    assert "briefingEvidenceList(citations)" in script
    assert "`${citation.id} — ${citation.title}`" in script


def test_daily_briefing_collapses_verbose_evidence_details_by_default():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'element("details", { className: "daily-briefing-details" }' in script
    assert 'citations.length === 1 ? t("source") : t("sources")' in script
    assert "briefingDetails(briefing, citations)" in script
    assert 'attrs: { open: "" }' not in script


def test_daily_briefing_renders_scannable_insight_blocks():
    """Issue #203: a briefing bullet is one scannable block, not a dense paragraph.

    The model prose "claim. Why it matters: point." is split into a takeaway
    head, the support underneath, and a quiet metadata row carrying confidence
    and source count. Evidence IDs move out of the running prose and into that
    row, so a scan meets the findings before any citation.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "function briefingParts(line)" in script
    assert "function briefingInsight(line, citations)" in script
    assert '"briefing-insight-head"' in script
    assert '"briefing-insight-body"' in script
    assert '"briefing-insight-meta"' in script
    assert "briefing-chip-sources" in script
    # The takeaway is pulled out of the wider prose by the "Why it matters"
    # split, never by guessing at sentence boundaries.
    assert "text.search(/\\bWhy it matters:\\s*/i)" in script
    # The evidence clause is lifted out of the body into the metadata, so the
    # IDs read as a source count rather than competing with the conclusion.
    assert "replace(/\\s*\\.?\\s*Evidence:" in script
    assert "parts.body" in script


def _rendered_briefing(fixture: str | None = None, lang: str | None = None):
    """Run the real briefing renderer over a fixture and return the DOM tree."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node is not installed")
    result = subprocess.run(
        [
            node,
            "tests/render_briefing_harness.mjs",
            *([fixture] if fixture else []),
            *([lang] if lang else []),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def test_rendered_briefing_splits_each_bullet_into_head_body_and_meta():
    nodes = list(_flatten(_rendered_briefing()))
    insights = [n for n in nodes if n["className"] == "briefing-insight"]
    classnames = " ".join(n["className"] for n in nodes)

    assert len(insights) == 2
    assert "briefing-insight-head" in classnames
    assert "briefing-insight-body" in classnames
    assert "briefing-insight-meta" in classnames
    assert "briefing-chip-sources" in classnames

    def subtext(node):
        return node["text"]

    # The structured bullet splits cleanly: the takeaway is only the head prose
    # (nothing past the "Why it matters" split), the body carries the support,
    # and the metadata names the confidence and source count.
    structured = insights[0]
    head = next(n for n in structured["children"] if n["className"] == "briefing-insight-head")
    body = next(n for n in structured["children"] if n["className"] == "briefing-insight-body")
    meta = next(n for n in structured["children"] if n["className"] == "briefing-insight-meta")
    assert subtext(head).startswith("Several new releases in this captured feed")
    assert "Why it matters" not in subtext(head)
    assert subtext(body).startswith("Evaluators should choose suites")
    assert "Evidence:" not in subtext(body)
    assert "High confidence" in subtext(meta)
    assert "3 sources" in subtext(meta)
    multi_source_chip = next(
        node for node in meta["children"] if "briefing-chip-sources" in node["className"].split()
    )
    assert multi_source_chip["tag"] == "span"
    assert multi_source_chip["href"] == ""

    # An older bullet without the "Why it matters" structure degrades to a head
    # with no body, yet its evidence and confidence still move to the metadata.
    fallback = insights[1]
    fbhead = next(n for n in fallback["children"] if n["className"] == "briefing-insight-head")
    fbmeta = next(n for n in fallback["children"] if n["className"] == "briefing-insight-meta")
    assert subtext(fbhead).startswith("An older-format bullet")
    assert "Evidence:" not in subtext(fbhead)
    assert "Medium confidence" in subtext(fbmeta)
    assert "2 sources" in subtext(fbmeta)


def test_rendered_single_source_chip_links_to_its_evidence():
    """Issue #467: the singular source count is the evidence affordance."""
    nodes = list(_flatten(_rendered_briefing("tests/fixtures/daily_briefing_one_source.json")))
    source_chip = next(
        node for node in nodes if "briefing-chip-sources" in node["className"].split()
    )
    confidence_chip = next(node for node in nodes if "briefing-chip-medium" in node["className"])
    details_summary = next(node for node in nodes if node["tag"] == "summary")

    assert source_chip["tag"] == "a"
    assert source_chip["text"] == "1 source"
    assert source_chip["href"] == "https://github.com/example/benchmark-release"
    assert confidence_chip["tag"] == "span"
    assert confidence_chip["href"] == ""
    assert details_summary["text"] == "Evidence & briefing details · 1 source"


def test_rendered_briefing_shows_chinese_when_the_snapshot_has_it():
    """Under the zh interface, the snapshot's zh rendering replaces the English.

    The zh bullets are validated at generation to carry the same E### ids, the
    same markers, and the same digits, so the renderer treats them as drop-in
    replacements: markers still split, evidence still lifts to the meta line.
    """
    nodes = list(_flatten(_rendered_briefing("tests/fixtures/daily_briefing_zh.json", "zh")))
    insights = [n for n in nodes if n["className"] == "briefing-insight"]

    assert len(insights) == 2
    head = next(n for n in insights[0]["children"] if n["className"] == "briefing-insight-head")
    body = next(n for n in insights[0]["children"] if n["className"] == "briefing-insight-body")
    meta = next(n for n in insights[0]["children"] if n["className"] == "briefing-insight-meta")
    assert "本次捕获的流中" in head["text"]
    assert "评估者应选择能复现目标技术栈" in body["text"]
    # The zh bullet keeps the English markers, so the splitter still removes them
    # from the running text just as it does for English bullets.
    assert "Why it matters" not in head["text"]
    assert "Evidence:" not in body["text"]
    assert "High" in meta["text"]
    # The translated caveat is shown instead of the English one.
    caveat = next(n for n in nodes if n["className"] == "daily-briefing-caveat")
    assert "仅注入了" in caveat["text"]
    assert "Only 25 of 164" not in caveat["text"]


def test_rendered_briefing_falls_back_to_english_without_zh_fields():
    """A day whose snapshot carries no zh fields stays English under zh."""
    nodes = list(_flatten(_rendered_briefing("tests/fixtures/daily_briefing.json", "zh")))
    heads = [
        n["text"]
        for n in nodes
        if n["className"] == "briefing-insight-head" and n["text"].startswith("Several")
    ]
    assert heads and "Several new releases in this captured feed" in heads[0]
    caves = [n["text"] for n in nodes if n["className"] == "daily-briefing-caveat"]
    assert caves and "Only 25 of 164" in caves[0]


def test_today_view_renders_the_daily_questions_under_the_briefing():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="daily-questions"' in html
    assert 'id="daily-questions-body"' in html
    # The briefing says what changed and the Q&A answers what a reader would ask
    # about it, so the Q&A follows the briefing in the sidebar, above the
    # Sources card and below the matching results (issue #248).
    assert html.index('id="daily-briefing"') < html.index('id="daily-questions"')
    assert html.index('id="daily-questions"') < html.index('id="source-health-panel"')
    assert html.index('id="today-list"') < html.index('id="daily-questions"')
    assert "renderDailyQuestions(day)" in script
    # Both describe one scan date, so neither is shown over the whole archive.
    assert 'byId("daily-questions").hidden = showingAllDates' in script


def test_daily_questions_render_in_the_sidebar_column():
    """Issue #248: the sidebar column constrains the section, not an explicit cap."""
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    questions = styles.split(".daily-questions {", 1)[1].split("}", 1)[0]
    body = styles.split("#daily-questions-body {", 1)[1].split("}", 1)[0]
    assert "max-width: calc(100% - 22rem)" not in questions
    assert "max-width: 72ch" in body
    # The section carries the same box treatment as the cards beside it.
    assert "border: 1px solid var(--edge)" in questions
    assert "background: var(--panel)" in questions


def test_daily_questions_withhold_another_days_answers_and_name_an_absent_set():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "questions.date === day.date" in script
    assert "No questions were answered for this day." in script


def test_daily_questions_print_stat_values_from_the_registry_not_the_prose():
    """The renderer must never take a number from the model's own sentences.

    `questions.py` computes every figure before the call and has the model cite
    S### ids; the page prints the cited statistic's own value. Rendering prose
    numbers instead would reintroduce exactly the fabrication the registry
    exists to prevent.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "formatStatValue(stat)" in script
    assert "answer.cited_stats" in script
    assert 'unit !== "count"' in script
    assert 'window !== "today"' in script
    # Spans already carry parentheses; the Markdown renderer avoids nesting a
    # second pair and the dashboard has to agree with it.
    assert 'window.endsWith(")")' in script


def test_daily_questions_show_the_counter_view_and_admitted_insufficiency():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # A daily feed that only ever confirms itself teaches a reader nothing about
    # how much to trust it, so the counter-view is rendered, never collapsed.
    assert 'text: t("Counter-view: ")' in script
    assert 'text: t("Takeaway: ")' in script
    assert 't("Evidence is insufficient to answer this today.")' in script
    assert "answer?.sufficient_evidence === false" in script


def test_daily_questions_flag_an_uncertified_comparison_window():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Without a certified window, day-over-day differences may be collection
    # changes rather than field changes, so the answers must not read as trends.
    assert "questions.comparable === false" in script
    assert "questions.comparability_note" in script
    assert 'questions.generator !== "openai-responses"' in script
    assert 't("every figure computed before the call and cited by ID")}.`' in script


def test_daily_questions_link_only_validated_http_evidence():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Same gate as the briefing: an id-shaped string with an unsafe or missing
    # URL is not turned into a link a reader can click.
    assert "validBriefingCitations(answer?.cited_evidence)" in script


def _rendered_questions(fixture: str | None = None, lang: str | None = None):
    """Run the real renderer over a fixture and return the resulting DOM tree.

    Source assertions cannot distinguish "renders the answer" from "mentions the
    word answer". The whole claim of this section is that every figure on it is
    traceable to a statistic computed before the model ran, so it is executed.
    """
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node is not installed")
    result = subprocess.run(
        [
            node,
            "tests/render_questions_harness.mjs",
            *([fixture] if fixture else []),
            *([lang] if lang else []),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def _flatten(node):
    yield node
    for child in node.get("children") or []:
        yield from _flatten(child)


def test_rendered_questions_carry_every_answer_field_and_registry_value():
    nodes = list(_flatten(_rendered_questions()))
    classes = {node["className"] for node in nodes}
    text = next(iter(nodes))["text"]

    assert {"question-group", "answer", "answer-signal", "answer-takeaway"} <= classes
    assert "answer-counter-view" in classes
    # Both fixture groups and all three answers render, not just the first.
    assert len([n for n in nodes if n["className"] == "question-group"]) == 2
    assert len([n for n in nodes if n["className"] == "answer"]) == 3

    # The statistic's value and span come from the registry entry, and the span
    # is not wrapped in a second pair of parentheses.
    assert "First-observed records today: 40" in text
    assert "12 since 2026-07-23 (17 days)" in text
    assert "12 (since 2026-07-23 (17 days))" not in text

    # A registry value is printed at full precision. `toLocaleString()` would
    # round this to 1,234.568, quietly altering a figure on the one page whose
    # whole claim is that every number is the one that was computed.
    assert "1,234.56789 days" in text
    assert "1,234.568 days" not in text

    # The model's own prose is reproduced verbatim, and the counter-view with it.
    assert "No credible counter-view found." in text
    assert "Evidence is insufficient to answer this today." in text
    assert "No certified comparison window" in text
    assert "Answered by gpt-5 in 3 calls" in text


def test_rendered_questions_show_chinese_prose_and_questions_under_zh():
    """Under zh, fixed question strings come from the I18N table and the day's
    answer prose from the snapshot's zh fields when the run produced them."""
    nodes = list(_flatten(_rendered_questions("tests/fixtures/daily_questions_zh.json", "zh")))
    classes = {n["className"] for n in nodes}
    text = next(iter(nodes))["text"]

    assert {"question-group", "answer", "answer-signal", "answer-takeaway"} <= classes
    # Group titles and the fixed question strings translate through the table.
    assert "今日新增" in text
    assert "雷达今天首次看到了哪些benchmark、数据集或评估方法？" in text
    # The model prose is the snapshot's zh rendering, not the English original.
    assert "今天首次观察到的记录大多是智能体评估框架。" in text
    assert "Most of today's first-observed records" not in text
    assert "未找到可信的反方观点。" in text


def test_rendered_questions_keep_english_prose_when_zh_fields_are_absent():
    """Without zh prose fields, only the fixed question strings translate."""
    nodes = list(_flatten(_rendered_questions("tests/fixtures/daily_questions.json", "zh")))
    text = next(iter(nodes))["text"]

    assert "雷达今天首次看到了哪些benchmark、数据集或评估方法？" in text
    assert "Most of today's first-observed records are agentic evaluation harnesses." in text
    assert "今天首次观察到的记录大多是智能体评估框架。" not in text


def _rendered_stale_banner(
    fixture: str | None = None, lang: str | None = None, resolve_failure: bool = False
):
    """Run the real stale-banner renderer over a fixture and return its DOM tree.

    Source assertions cannot tell "renders two actions" from "mentions Contact",
    and the failed-run deep link only exists after an async lookup resolves, so
    the renderer runs for real and the settled tree is asserted on.
    """
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node is not installed")
    result = subprocess.run(
        [
            node,
            "tests/render_stale_banner_harness.mjs",
            *([fixture] if fixture else []),
            *(["--resolve-failure"] if resolve_failure else []),
            *([lang] if lang else []),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout)


def test_rendered_stale_banner_names_the_gap_and_offers_two_actions():
    import re

    banner = _rendered_stale_banner("tests/fixtures/stale_radar.json")
    nodes = list(_flatten(banner))

    assert {n["className"] for n in nodes} >= {"stale-banner-actions", "stale-banner-action"}
    # The hour count moves with the clock, so only the sentence shape is pinned.
    assert re.search(
        r"Last updated Jan 1, 2020.*hours ago\. The automatic update has not succeeded since\.",
        banner["children"][0]["text"],
    )
    # The fallback href must already be live before any deep-link lookup returns.
    link = next(n for n in nodes if n["tag"] == "a")
    assert link["text"] == "What broke?"
    assert link["href"].startswith("https://github.com/ktwu01/benchmark-radar/actions/")
    button = next(n for n in nodes if n["tag"] == "button")
    assert button["text"] == "Contact"


def test_rendered_stale_banner_translates_copy_under_zh():
    banner = _rendered_stale_banner("tests/fixtures/stale_radar.json", "zh")
    nodes = list(_flatten(banner))

    link = next(n for n in nodes if n["tag"] == "a")
    button = next(n for n in nodes if n["tag"] == "button")
    assert link["text"] == "哪里出了问题？"
    assert button["text"] == "联系作者"
    assert "那之后的自动更新一直没有成功。" in banner["children"][0]["text"]
    assert "The automatic update has not succeeded" not in banner["children"][0]["text"]


def test_rendered_stale_banner_marks_degraded_coverage_with_the_gaps():
    banner = _rendered_stale_banner("tests/fixtures/degraded_radar.json")

    assert "stale-banner-degraded" in {n["className"] for n in _flatten(banner)}
    assert "Some sources failed to answer on 2999-12-31: arxiv listings, hugging face." in [
        n["text"] for n in _flatten(banner)
    ]


def test_rendered_fresh_snapshot_keeps_the_banner_hidden():
    banner = _rendered_stale_banner("tests/fixtures/fresh_radar.json")

    assert banner["hidden"] is True
    assert banner["text"] == ""


def test_rendered_stale_banner_deep_links_the_latest_failed_run():
    """When the Actions API answers, "What broke?" pins the exact failed run."""
    banner = _rendered_stale_banner(resolve_failure=True)
    link = next(n for n in _flatten(banner) if n["tag"] == "a")

    assert link["href"] == "https://github.com/ktwu01/benchmark-radar/actions/runs/32439770574"


def test_dashboard_and_markdown_format_statistics_identically():
    """The two renderers must print the same figure for the same statistic.

    The Markdown report and the dashboard are both published from one registry,
    so a reader comparing them must not see two different numbers. This runs the
    JS formatter against `report._format_stat_value` over the same inputs.
    """
    import json
    import re
    import shutil
    import subprocess
    from pathlib import Path as _Path

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")

    from benchmark_radar.report import _format_stat_value

    cases = [1234.56789, 12.5, 40.0, 0.125, 1234567.0, -1234.5, -1234567, 0, 100, 999, 1000]
    source = _Path("site/assets/app.js").read_text(encoding="utf-8")
    match = re.search(r"function formatStatValue[\s\S]*?\n}\n", source)
    assert match, "formatStatValue not found in app.js"
    program = (
        f"{match.group(0)}\n"
        f"const cases = {json.dumps(cases)};\n"
        "console.log(JSON.stringify(cases.map((value) => "
        'formatStatValue({ value, unit: "count", window: "today" }))));'
    )
    result = subprocess.run(
        [node, "-e", program], capture_output=True, text=True, timeout=60, check=True
    )

    expected = [
        _format_stat_value({"value": value, "unit": "count", "window": "today"}) for value in cases
    ]
    assert json.loads(result.stdout) == expected


def test_rendered_questions_link_cited_evidence_to_its_source():
    nodes = list(_flatten(_rendered_questions()))
    links = [node for node in nodes if node["href"]]

    assert [node["href"] for node in links] == ["https://arxiv.org/abs/2608.00001"]
    assert links[0]["text"] == "A harness for long-horizon agent tasks"


def _render_with(mutate, tmp_path):
    """Render the fixture after applying `mutate` to it."""
    import json
    from pathlib import Path as _Path

    fixture = json.loads(_Path("tests/fixtures/daily_questions.json").read_text(encoding="utf-8"))
    mutate(fixture)
    path = tmp_path / "daily_questions.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return _rendered_questions(str(path))


def test_rendered_questions_withhold_a_stale_day_rather_than_mislabel_it(tmp_path):
    """A Q&A stamped with another date answers questions about the wrong day."""

    def restamp(fixture):
        fixture["questions"]["date"] = "2026-08-07"

    rendered = _render_with(restamp, tmp_path)
    assert "No questions were answered for this day." in rendered["text"]
    assert not any(node["className"] == "answer" for node in _flatten(rendered))


def test_rendered_questions_report_an_absent_set_rather_than_blank_space(tmp_path):
    """The Q&A is opt-in, so a day with none must say so under its heading."""

    def clear(fixture):
        fixture["questions"] = {}

    rendered = _render_with(clear, tmp_path)
    assert "No questions were answered for this day." in rendered["text"]
    assert not any(node["className"] == "question-group" for node in _flatten(rendered))


def test_rendered_questions_name_a_disabled_run_rather_than_the_generic_message(tmp_path):
    """Issue #159: a disabled run must say so, not collapse into the generic empty state."""

    def disable(fixture):
        fixture["questions"] = {
            "status": "disabled",
            "reason": "OPENAI_QUESTIONS is not enabled",
        }

    rendered = _render_with(disable, tmp_path)
    assert "OPENAI_QUESTIONS is not enabled" in rendered["text"]
    assert "No questions were answered for this day." not in rendered["text"]
    assert not any(node["className"] == "question-group" for node in _flatten(rendered))


def test_rendered_questions_name_a_failed_run_rather_than_the_generic_message(tmp_path):
    """Issue #159: a failed generation must say so, not collapse into the generic empty state."""

    def fail(fixture):
        fixture["questions"] = {
            "status": "error",
            "reason": "BriefingError: OpenAI structured output is not valid JSON",
        }

    rendered = _render_with(fail, tmp_path)
    assert "Daily questions failed to generate" in rendered["text"]
    assert "OpenAI structured output is not valid JSON" in rendered["text"]
    assert "No questions were answered for this day." not in rendered["text"]
    assert not any(node["className"] == "question-group" for node in _flatten(rendered))


def test_rendered_questions_drop_an_evidence_citation_with_an_unsafe_url(tmp_path):
    """An id-shaped citation without a safe URL must not become a link."""

    def poison(fixture):
        citation = fixture["questions"]["groups"][0]["answers"][0]["cited_evidence"][0]
        citation["url"] = "javascript:alert(1)"

    rendered = _render_with(poison, tmp_path)
    assert not [node for node in _flatten(rendered) if node["href"]]
    # The answer itself still renders; only the unfollowable citation is dropped.
    assert any(node["className"] == "answer" for node in _flatten(rendered))


def test_rendered_answers_hide_supporting_detail_behind_a_collapsed_disclosure():
    """Issue #183: each Q&A keeps its headline visible but collapses its support.

    The question, confidence and one-line signal stay up front; the explanation,
    citations, takeaway and counter-view live inside a native <details> that
    starts collapsed (no `open` attribute, so it is reversible by the same
    control) and carries the supporting content somewhere beneath the summary.
    """
    nodes = list(_flatten(_rendered_questions()))
    answers = [n for n in nodes if n["className"] == "answer"]
    disclosures = [n for n in nodes if n["className"] == "answer-disclosure"]

    assert len(answers) == 3
    assert len(disclosures) == 3

    for answer, disclosure in zip(answers, disclosures, strict=True):
        # Every rendered answer pairs its disclosure without collapsing the
        # headline: question + signal stay direct children of the <article>.
        assert any(n["className"] == "answer-question" for n in answer["children"])
        signal = next(n for n in answer["children"] if n["className"] == "answer-signal")["text"]
        # The disclosure is collapsed on load (no `open`) and carries a visible
        # summary affordance naming what the reader will reveal.
        assert disclosure["tag"] == "details"
        assert "open" not in disclosure["attributes"]
        assert any(n["className"] == "answer-disclosure-summary" for n in disclosure["children"])
        # The supporting detail sits below the summary and does not repeat the
        # one-line signal that is already visible above it.
        detail = next(n for n in disclosure["children"] if n["className"] == "answer-detail")
        detail_text = "".join(_subtexts(detail))
        assert detail_text
        assert signal not in detail_text

    # Across all three answers, the full explanation, takeaway and counter-view
    # all warm up inside the disclosures rather than crowding the headlines.
    all_detail = "".join(
        "".join(_subtexts(detail))
        for d in disclosures
        for detail in d.get("children") or []
        if detail["className"] == "answer-detail"
    )
    assert "carry out a task" in all_detail  # a plain-English explanation
    assert "Treat unscored arrivals as unverified" in all_detail  # a takeaway
    assert "keyword-filtered" in all_detail  # a counter-view


def test_rendered_answers_hold_confidence_as_metadata_not_question_text():
    """Issue #203: confidence is a small badge beneath the question, not text
    pinned to the question's own line, and sources are counted alongside it."""
    nodes = list(_flatten(_rendered_questions()))
    answers = [n for n in nodes if n["className"] == "answer"]
    assert len(answers) == 3

    for answer in answers:
        question = next(n for n in answer["children"] if n["className"] == "answer-question")
        # The question line carries the question and nothing else; the
        # confidence badge lives in its own metadata row below the signal.
        assert question["children"] and all(n["tag"] == "#text" for n in question["children"])
        metas = [n for n in answer["children"] if n["className"] == "answer-meta"]
        assert metas
        meta_text = metas[0]["text"]
        assert " confidence" in meta_text
        assert any("pill-confidence" in n["className"] for n in nodes)

    # The disclosure's label is the short prompt, not the repeated long sentence.
    summary = next(n for n in nodes if n["className"] == "answer-disclosure-summary")
    assert "View analysis" in summary["text"]
    assert "READ the full answer" not in summary["text"].upper()


def test_leaderboard_coverage_counts_are_native_disclosures():
    """Issue #183: the registry-overview counts open to their itemized evidence.

    Each coverage tile is a native <details> whose summary keeps the stat and
    whose body lists the exact records behind it. No `open` attribute is added,
    so every tile loads collapsed and can be expanded and re-collapsed with the
    single, native (and keyboard-operable) control.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'className: "evidence-stat evidence-disclosure"' in script
    assert 'element("details", { className: "evidence-stat evidence-disclosure" }' in script
    assert 'className: "evidence-stat-summary"' in script
    assert 'className: "evidence-detail-list"' in script
    # Collapsed by default: the disclosures are built without an `open` attribute.
    assert ".attrs: { open" not in script
    # The itemized evidence is wired to the counts a reader would drill into.
    assert "Benchmarks tracked" in script
    assert "modelCardLine" in script
    assert "benchmarkLine" in script


def _subtexts(node):
    if node["tag"] == "#text":
        return [node["text"]]
    out = []
    for child in node.get("children") or []:
        out.extend(_subtexts(child))
    return out


def test_connector_failure_marks_the_summary_without_force_opening_the_panel():
    """Issue #183: a connector failure must change the collapsed Sources
    summary/status but never force the panel's body open."""
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The status and a failure class are set on the summary line regardless of
    # whether the panel is expanded.
    assert 'byId("health-status").textContent = failedCount' in script
    assert 'classList.toggle("has-failure", failedCount > 0)' in script
    # No code path opens the panel's body.
    assert 'health-panel-details").open' not in script
    assert 'health-panel-details" ].open' not in script


def test_source_mix_names_the_sources_that_found_nothing():
    """Issue #260: a source that found nothing must be printed as a gap.

    The ledger used to list only sources that returned something, so a day on
    which First-party feed found nothing looked exactly like a day on which
    First-party feed did not exist (issue #254). The zeros carry the signal: a
    source stuck at zero for days is usually broken rather than idle.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # Fetch health names a run by its internal key, the source mix by the label
    # a reader sees. Without the bridge the zeros cannot be matched at all.
    assert 'first_party_feeds: "First-party feed"' in script
    assert 'github_releases: "GitHub Release"' in script
    # Every fetcher in the pipeline needs a reader-facing name, or its zero day
    # would print a bare internal key.
    fetchers = Path("src/benchmark_radar/sources.py").read_text(encoding="utf-8")
    registry = fetchers.split("SOURCE_FETCHERS = {", 1)[1].split("}", 1)[0]
    for line in registry.splitlines():
        key = line.strip().split(":", 1)[0].strip('", ')
        if key:
            assert f"{key}:" in script.split("SOURCE_DISPLAY_NAMES = {", 1)[1], key

    # The mix cell is built from nodes now, so a zero can carry its own styling.
    assert 'element("td", {}, sourceMixCell(day))' in script
    assert '"source-gap"' in script
    assert ".source-gap {" in styles

    # And the newest day's gaps are stated in words above the table.
    assert 'id="source-gap-note"' in html


def test_daily_ledger_is_a_tiny_collapsed_dev_checker_below_the_trends():
    """The maintenance ledger stays available without competing for attention."""
    html = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert '<details class="dev-checker" aria-labelledby="dev-checker-heading">' in html
    assert '<summary class="dev-checker-summary">' in html
    assert 'data-i18n="Dev checker">Dev checker</span>' in html
    assert '<details class="dev-checker" open' not in html
    assert html.index('class="trend-panel"') < html.index('class="dev-checker"')
    assert ".dev-checker-summary {" in styles
    assert "font-size: 0.65rem;" in styles.split(".dev-checker-summary {", 1)[1].split("}", 1)[0]


def test_source_mix_separates_the_three_reasons_a_source_shows_zero():
    """Issue #260: the source mix counts ranked evidence, fetch health counts
    raw records, so a zero has three different meanings and only two of them
    are a reason to go and check something.

    Calling all three "found nothing" would be wrong: GitHub returning 300
    records that all scored too low is the ranking working as intended, and
    dressing that as a fault teaches the reader to ignore the real gaps.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # The state is derived from both signals, not from `ok` alone.
    assert 'state: !entry.ok ? "unreachable" : entry.fetched > 0 ? "unranked" : "empty"' in script
    # A source reported by two health rows must not take an arbitrary one of
    # them: a failure anywhere is the answer worth showing.
    assert "ok: previous ? previous.ok && entry.ok : entry.ok" in script

    # An unranked source is not dressed in the alarm colour, and the summary
    # warning is withheld when nothing worrying happened.
    assert '"source-gap is-unranked"' in script
    assert ".source-gap.is-unranked {" in styles
    assert 'note.classList.toggle("is-warning", worrying > 0)' in script

    # A row that names its zeros must not also claim "none".
    assert "if (found.length || !gaps.length) {" in script


def test_every_new_source_gap_string_has_a_chinese_rendering():
    """Issue #260 strings are user-facing, so the zh table must carry them."""
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    zh = script.split("  zh: {", 1)[1]
    for phrase in (
        "On {date} these sources found nothing at all: {sources}.",
        "On {date} these sources could not be reached: {sources}.",
        "On {date} these sources returned something, but none of it scored "
        "high enough to be listed: {sources}.",
        "A source that stays at zero for several days is usually broken, not quiet.",
        "This source was checked and found nothing at all on this day.",
        "This source could not be reached on this day.",
        "This source returned something, but none of it scored high enough to be listed.",
    ):
        assert f'"{phrase}":' in zh, phrase


def test_jargon_audit_reads_only_user_facing_text():
    """The weekly jargon audit (issue #241) must not flag code identifiers.

    Its value depends on every hit being text a reader actually sees. A run
    that reports `data-frontier-point` teaches the reader to skim past it,
    and then the real hits go unread too.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/audit_jargon.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        _term, _where, text = line.split("\t", 2)
        assert not text.startswith(("data-", "aria-")), text
        assert " " in text, f"lookup key, not prose: {text}"


def test_an_empty_source_filter_says_why_instead_of_blaming_the_filter():
    """Issue #254: filtering to a source that had a quiet day is not a filter bug.

    "Clear one or more filters to widen the view" is right when the filters are
    too narrow and wrong when the source simply collected nothing: clearing
    filters cannot conjure evidence that was never there, so the advice sends
    the reader hunting for a mistake they did not make. First-party feed on
    Aug 18 2026 is exactly that case, and it read as a broken filter.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The empty list asks the helper rather than hardcoding one sentence.
    assert "emptyTodayNodes(day, benchmarkMatches)" in script
    assert "function emptyTodayMessage(day" in script

    # It reuses issue #260's three states rather than inventing a fourth
    # answer that could disagree with the ledger on the same day.
    # Sliced to the next top-level function rather than a fixed character
    # count, so adding a branch to this helper cannot silently push the
    # assertions below out of the window being checked.
    helper = script.split("function emptyTodayMessage(day", 1)[1].split("\nfunction ", 1)[0]
    assert "zeroItemSources(day)" in helper
    for state in ("unreachable", "empty", "unranked"):
        assert state in helper, state

    # And it only speaks when the source filter alone emptied the list: with a
    # second filter on, which one did it is a guess.
    assert "others.length" in helper

    # Every source-specific sentence it can print is translated: the English
    # key the call site passes and the zh value it looks up.
    for phrase in (
        "{source} could not be reached on this day, so nothing was collected from it.",
        "Try another date, or clear the filter.",
    ):
        assert script.count(f'"{phrase}"') >= 2, phrase

    # The generic "too narrow" case (issue #386) no longer prints one sentence.
    # It returns null so emptyTodayNodes() can render a recovery checklist: two
    # ways to widen the view and a link to open an issue for a missing benchmark.
    assert "function emptyTodayNodes(day" in script
    assert "function noFilterMatchNodes()" in script
    for phrase in (
        "No observations match these filters.",
        "Clear one or more filters to widen the view.",
        'Reset the date to "all dates".',
        "Add your wanted benchmark as an ",
    ):
        assert script.count(f'"{phrase}"') >= 2 or script.count(f"'{phrase}'") >= 2, phrase
    assert "github.com/ktwu01/benchmark-radar/issues/" in script


def test_a_benchmark_name_search_reaches_the_registry_not_only_the_daily_feed():
    """Issue #245: the search box read the daily feed and nothing else.

    Two wrong answers came out of that. "researchclawbench" returned "No
    observations match these filters. Clear one or more filters", advice that
    cannot work, because no filter setting adds a dataset the box never read.
    "terminal-bench" was worse: it returned an arXiv paper on uncertainty
    propagation, ranked because the string "Terminal-Bench-2" happens to appear
    in its abstract, while the six Terminal-Bench records in the registry, one
    of them carrying 51 reported scores, were unreachable.

    Both benchmarks are in the registry. The query has to reach it.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The query runs against both registry layers, reusing the matchers the
    # leaderboard already uses rather than a second, drifting implementation.
    section = script.split("function renderTodayBenchmarks()", 1)[1].split(
        "function renderToday(", 1
    )[0]
    assert "searchCuratedEntries(board, query, { includeUnscored: true })" in section
    assert "searchBenchmarkIndex(state.benchmarkIndex || [], query)" in section

    # Curated rows rank above crawled ones: same order the leaderboard picker
    # uses, and the layer with a protocol and a time axis.
    assert section.index("curatedResultRow") < section.index("benchmarkResultRow")

    # Registry matches are named as such. Folding them into a list sorted by
    # daily priority is what surfaced the arXiv paper over the benchmark.
    assert "today-benchmarks" in section

    # The catalog is only fetched once someone searches, so a normal visit
    # still does not pay for it.
    # Attached once. The promise is cached, so one handler per keystroke would
    # all fire together on a slow fetch, each re-filtering and rebuilding.
    assert "!state.benchmarkIndexLoaded && !benchmarkIndexRerenderQueued" in section
    assert "benchmarkIndexRerenderQueued = true;" in section

    # Capped before the rows are built. "bench" matches 355 of the 1,148
    # crawled records, and building all of them into DOM subtrees with
    # listeners to then drop all but 50 is work repeated on every keystroke.
    assert "curated.slice(0, BENCHMARK_SEARCH_LIMIT)" in section
    assert section.index("externalShown") < section.index("benchmarkResultRow(record")

    # A failed catalog fetch is reported whether or not the curated layer
    # matched. Only saying so on an empty result would present half a registry
    # search as a whole one.
    assert "const indexFailed =" in section
    assert "if (!rows.length && !indexFailed && !indexPending)" in section

    # And an unsettled catalog is a third state. Zero matches is not a fact
    # while the request is in flight, so a cold search for a crawled-only
    # benchmark must not print "clear one or more filters" in the meantime.
    assert "const indexPending = !state.benchmarkIndexLoaded;" in section
    assert 'return !total && indexPending ? "pending" : total;' in section
    assert 'benchmarkMatches === "pending"' in script

    # With no leaderboard to land on, rows render inert rather than as buttons
    # whose click does nothing the reader can see. "Has entries" is not the
    # test: renderAdoptionFrontier() gives up unless an adopted entry has a
    # readable score record and a default entry resolves.
    assert "inert: !navigate" in section
    assert "scoreRecord(item.benchmark_id)" in section
    assert "frontierDefaultEntry(board)" in section

    # A truncated list says so. Presenting 50 of 383 as "the matches" invites
    # the reader to conclude a benchmark past row 50 is absent, which is the
    # same wrong conclusion this issue is about.
    assert "const truncated = total > rows.length;" in section
    assert "Showing {shown} of {total} registry records" in section

    # Clicking a row must draw the view it lands on. setView() toggles
    # visibility and the URL but does not render, so without this a first-time
    # visitor arrives at an empty leaderboard: 0 chart children, 0 table rows.
    for row in ("function curatedResultRow(entry", "function benchmarkResultRow(record"):
        body = script.split(row, 1)[1].split("\nfunction ", 1)[0]
        assert 'setView("leaderboard");\n      renderLeaderboard();' in body, row

    # And the empty list stops advising a filter change that cannot help when
    # the thing being searched for was found in the registry instead.
    helper = script.split("function emptyTodayMessage(day", 1)[1].split("\nfunction ", 1)[0]
    assert "benchmarkMatches" in helper

    # The claim is only made when the query is the sole filter. With a second
    # one active a matching observation may exist and have been filtered out,
    # so "nothing was collected" would assert more than this function knows.
    assert "queryOnly" in helper
    for other in ("state.kind", "state.category", "state.source", "state.event"):
        assert other in helper, other

    # "on this date" is false in All dates mode, where the search already
    # covered the whole archive, so that mode gets its own sentence.
    assert 'state.todayDate === "all"' in helper
    assert "No collected observation mentions" in helper

    # A t() string needs both halves in app.js: the English key the call site
    # passes and the zh value it looks up. Missing the second is the silent
    # failure mode, since the lookup just falls through to English.
    assert script.count("Nothing was collected about") >= 2

    # A data-i18n string is keyed from the HTML instead, so app.js carries the
    # translation only and the English lives in the markup.
    markup = Path("site/index.html").read_text(encoding="utf-8")
    assert 'data-i18n="Benchmarks with this name"' in markup
    assert '"Benchmarks with this name":' in script


def test_issue_286_navigation_is_backable_but_typing_is_not():
    """Back used to leave the site.

    Every URL write called replaceState, so the entry a reader arrived on was
    overwritten rather than kept: searching, opening a benchmark and pressing
    Back landed on about:blank. Measured on main, history.length stayed at 2
    across a search and a view change.

    Pushing everywhere is the opposite bug. The filter boxes write on a
    debounce as the reader types, so q=m, q=mm, q=mml, q=mmlu would each become
    an entry and Back would walk backwards through their own typing.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'function writeUrl(mode = "replace")' in script
    assert 'window.history.pushState(historyState, "", url);' in script
    assert 'window.history.replaceState(historyState, "", url);' in script

    # A discrete navigation the reader chose pushes. Changing view is the one
    # the issue measured; selecting a benchmark is the one that made it easy to
    # hit, because it carries a reader from a search into another view.
    assert 'function setView(view, update = true, mode = "push")' in script
    assert "if (update) writeUrl(mode);" in script
    picker = script.split('byId("frontier-benchmark").addEventListener("change"', 1)[1].split(
        "});", 1
    )[0]
    assert 'writeUrl("push")' in picker

    # Continuous refinement of the current view replaces. Both debounced
    # renderers are the keystroke path, and neither may push.
    leaderboard_debounce = script.split("const scheduleLeaderboardRender = debounce(", 1)[1].split(
        "});", 1
    )[0]
    assert "writeUrl();" in leaderboard_debounce
    assert "push" not in leaderboard_debounce

    # A pushed entry that nothing re-renders leaves the page disagreeing with
    # its own address bar, so the listener is part of the fix rather than an
    # optional extra.
    assert 'window.addEventListener("popstate", onPopState);' in script
    handler = script.split("function onPopState()", 1)[1].split("\n}\n", 1)[0]
    assert "readUrl();" in handler
    assert "setView(state.view, false);" in handler
    assert "rerenderCurrentView();" in handler

    # Pushing the URL already shown would make Back a no-op that looks broken.
    assert 'if (mode === "push" && url !== current)' in script


def test_issue_311_the_today_list_loads_one_page_at_a_time():
    """A busy day carded 100+ results before the reader could scroll.

    The first paint now carries 20 cards, the legend is two readings instead
    of three, and explicit previous/next controls move through stable pages.
    """
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # One named page size, with a URL-backed current page.
    assert "const TODAY_PAGE_SIZE = 20;" in script
    assert "todayPage: 1," in script
    assert 'params.get("page")' in script
    assert 'params.set("page", state.todayPage)' in script
    renderer = script.split("function renderToday({ resultsOnly = false } = {})", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "Math.ceil(observations.length / TODAY_PAGE_SIZE)" in renderer
    assert "const visibleObservations = observations.slice(pageStart, pageEnd);" in renderer
    assert 'byId("today-page-prev").disabled' in renderer
    assert 'byId("today-page-next").disabled' in renderer
    assert 'id="today-page-prev"' in html
    assert 'id="today-page-next"' in html
    assert 'id="today-page-status"' in html
    assert "IntersectionObserver" not in script

    # The legend keeps the class breakdown and the order; the raw total and
    # its duplicated noun are gone, and "need attention" lost its verb.
    assert 'id="today-count"' not in html
    assert 'byId("today-breakdown").textContent =' in renderer
    assert '${attentionCount} ${t("attention")}' in renderer
    assert '"need attention"' not in script

    # Dataset access remains free under the homepage pager; starring is an
    # earned request, not a gate. The stronger cite/star/share card closes the
    # page in the footer instead of competing with the result list.
    assert 'id="badge-export"' not in html
    assert 'id="export-dialog"' not in html
    assert "function openExport(" not in script
    assert "function observationsToCsv(" not in script
    assert "function downloadText(" not in script
    pager_end = html.index("</nav>", html.index('class="today-pagination"'))
    dataset_card = html.index('<div class="footer-dataset">')
    page_footer = html.index("<footer>")
    assert pager_end < dataset_card < page_footer
    dataset = html.split('<div class="footer-dataset">', 1)[1].split("</div>", 1)[0]
    assert "Free dataset. No crawler needed." in dataset
    assert 'href="/data/radar.json"' in dataset
    assert "Star the repository" not in dataset
    assert "Contact" not in dataset
    footer = html.split("<footer>", 1)[1].split("</footer>", 1)[0]
    assert 'class="adoption-cta"' in footer
    assert "If this saved you research time" in footer
    assert 'id="share-radar"' in footer
    contact = script.split("function openContact(", 1)[1].split("dialog.showModal();", 1)[0]
    assert "The complete dataset is free to download" in contact
    assert 'href: "/data/radar.json"' in contact
    assert 'className: "contact-dataset"' in contact


def _css_rule(styles: str, selector: str) -> str:
    """Return the body of the first rule whose selector matches exactly."""
    assert selector in styles, f"missing selector: {selector}"
    return styles.split(selector, 1)[1].split("}", 1)[0]


def test_heading_outline_and_scale_stay_quiet():
    """Regression guard for the per-view h1 outline and its typography.

    Each view is served at its own URL, so each one owns an h1 naming what that
    page is. Only one view is on screen at a time, so only one h1 ever renders.
    They keep the quiet leaderboard scale rather than the display scale, so
    promoting them changed the document outline and not the design: before this
    rule existed the headings carried the 3rem uppercase h1 treatment, which
    drowned the content they named.
    """
    html = Path("site/index.html").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # One h1 per view, and exactly one of them sits in a section the reader can
    # see. The other three stay behind `hidden` until routing opens them.
    sections = re.findall(
        r'<section class="view" id="([a-z]+)-view"([^>]*)>(.*?)\n      </section>',
        html,
        re.S,
    )
    assert {name for name, _, _ in sections} == {"today", "leaderboard", "map", "trends"}
    for name, _, body in sections:
        assert body.count("<h1") == 1, name
    visible = [name for name, attrs, _ in sections if " hidden" not in attrs]
    assert visible == ["today"], visible

    assert '<h1 class="today-heading" data-i18n="Today\'s radar">' in html
    for heading_id in ("leaderboard-heading", "map-heading", "trends-heading"):
        assert f'<h1 id="{heading_id}"' in html

    # The today h1 renders exactly like the counts caption beside it: the shared
    # small-caps utility group supplies face/size/case, and this rule only
    # mutes color and weight. No font-size override may reappear here.
    marker = "#today-view .section-title h1,"
    today_rule = styles.split(marker)[-1].split("}", 1)[0]
    assert "color: var(--muted);" in today_rule
    assert "font-weight: 400;" in today_rule
    assert "font-size" not in today_rule

    # The counts line reads as plain data, not a small-caps label. It used to
    # need an explicit `text-transform: none` to cancel an inherited uppercase;
    # issue #333 removed uppercase from the stylesheet outright, so the guard is
    # now that no rule anywhere can put it back.
    assert "text-transform: uppercase" not in styles
    assert "text-transform: none;" not in styles

    # Footer is one left-aligned column: updated stamp, view links, dataset
    # card last (bottom).
    footer_block = styles.split("\nfooter {")[-1].split("}", 1)[0]
    assert "flex-direction: column;" in footer_block
    assert "align-items: flex-start;" in footer_block

    # View and detail headings share the compact leaderboard scale; none of
    # them may reintroduce the uppercase display treatment. h1 and h2 are styled
    # by the same rule, so retagging a heading cannot change how it looks.
    compact = "clamp(1.25rem, 2vw, 1.5rem);"
    view_rule = _css_rule(styles, ".view-heading h1,\n.view-heading h2 {")
    assert f"font-size: {compact}" in view_rule
    assert "line-height: 1.2;" in view_rule
    assert "text-transform" not in view_rule
    detail_rule = _css_rule(styles, ".detail-title {")
    assert f"font-size: {compact}" in detail_rule
    assert "line-height: 1.2;" in detail_rule

    # The mobile h1 clamp must not reach the quiet view headings, in either tag.
    mobile_block = styles.split("@media (max-width: 760px)", 1)[1]
    first_rule = mobile_block.split("}", 1)[0]
    assert ".view-heading h1," not in first_rule
    assert ".view-heading h2," not in first_rule


def test_issue_332_a_release_outranks_a_same_day_update():
    """Every benchmark published today was buried under repositories that only took a commit.

    Priority measures how well a benchmark is documented -- artifacts,
    openness, size -- and a benchmark released this morning has had no time to
    accumulate any of it, while a repository that has existed for months has.
    Ranking a day purely by that score therefore sorts against the one question
    the page exists to answer. On 2026-08-24 the top eight rows were all
    `updated` and the best-scoring actual release sat at rank nine.
    """
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    rank = script.split("function releaseRank(item)", 1)[1].split("\n}", 1)[0]
    assert 'if (item.event_kind !== "released") return 3;' in rank
    # Releases are graded by how old they were when the scan ran, so a fresher
    # one leads an older one and priority only breaks ties inside a tier.
    assert "if (hours < RELEASE_FRESH_HOURS) return 0;" in rank
    assert "if (hours < RELEASE_RECENT_HOURS) return 1;" in rank
    assert "const RELEASE_FRESH_HOURS = 24;" in script
    assert "const RELEASE_RECENT_HOURS = 72;" in script

    age = script.split("function releaseAgeHours(item)", 1)[1].split("\n}", 1)[0]
    # `published_at` is the release moment. `discovered_at` is the crawl
    # timestamp, so using it would report every release as zero hours old and
    # hand the freshest tier to rows whose real date is unknown.
    assert "item.published_at || item.updated_at" in age
    assert "discovered_at" not in age
    # An undatable release is not treated as fresh.
    assert "return Number.POSITIVE_INFINITY;" in age
    # Measured against the snapshot's own scan time, not the reader's clock: an
    # older date has to rank as it stood, and a wall clock would collapse every
    # past day into one tier. It also keeps the cached sort deterministic.
    assert "item.snapshot_generated_at" in age
    assert "Date.now()" not in age
    assert script.count("snapshot_generated_at: day.generated_at,") == 2

    sort_body = script.split("state.observations = [...evidence, ...attention].sort(", 1)[1].split(
        "\n  });", 1
    )[0]
    # Date still leads: the archive is a chronology before it is a ranking.
    assert sort_body.index("const dateOrder") < sort_body.index("const releaseOrder")
    # Then releases, scored recency, and only then priority. The v5 event-kind
    # discount has to participate in the visible order instead of changing only
    # the number printed on the card.
    assert sort_body.index("const releaseOrder") < sort_body.index("const scoreOrder")
    assert sort_body.index("const releaseOrder") < sort_body.index("const recencyOrder")
    assert sort_body.index("const recencyOrder") < sort_body.index("const scoreOrder")
    assert "releaseRank(a) - releaseRank(b)" in sort_body
    assert "Number(b.recency_score || 0) - Number(a.recency_score || 0)" in sort_body

    # The caption names the order the reader is looking at, and only claims the
    # release tie-break when the result set actually contains both kinds.
    assert 't("Sort: New releases first, then Recency ↓, then Priority ↓")' in script
    assert 't("Sort: Date, then new releases, then Recency ↓, then Priority ↓")' in script
    # "Is a release" is its own predicate now that releaseRank grades by age:
    # reading it as `=== 0` would have counted only the freshest tier.
    assert "const releases = observations.filter(isRelease).length;" in script
    assert 'return item.event_kind === "released";' in script
    assert "releases > 0 && releases < observations.length" in script
    # The caption stops at "new releases first" rather than claiming a strict
    # timestamp sort across release tiers; it then names the scored-recency
    # order that v5 applies inside a tier.
    assert "Sort: Newest releases first" not in script

    # Both captions are translated; an untranslated string would render as
    # English inside an otherwise Chinese page.
    assert "排序:新发布优先,再按新鲜度 ↓,再按优先度 ↓" in script
    assert "排序:日期,再新发布优先,再按新鲜度 ↓,再按优先度 ↓" in script


def test_issue_333_the_page_never_scrolls_sideways():
    """The page slid left and right by ~19px at every width above 760.

    Nothing here is meant to be reached by scrolling sideways: every wide table
    and chart carries its own scroll container. Two separate causes had to go.
    """
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    # 1. A hover label centred under the last masthead badge. `visibility:
    #    hidden` does not take a box out of layout, so it widened the document
    #    even while it was invisible.
    anchored = _css_rule(styles, ".masthead-end > .repo-badge:last-child::after {")
    assert "right: 0;" in anchored
    assert "left: auto;" in anchored

    # The responsive one-column grid must be allowed to shrink below a long
    # record's intrinsic width. A bare 1fr track let real benchmark names widen
    # a 390px page to 455px.
    responsive = styles.split("@media (max-width: 1050px)", 1)[1].split(
        "@media (max-width: 760px)", 1
    )[0]
    assert "grid-template-columns: minmax(0, 1fr);" in responsive
    mobile = styles.split("@media (max-width: 760px)", 1)[1]
    assert "#today-sort" in mobile and "white-space: normal;" in mobile

    # 2. Crawled README banners made of box-drawing characters are a single
    #    unbreakable run, and one of them pushed a 720px column to 1349px.
    wrap = _css_rule(styles, ".record-card,\n.map-detail,\n.external-block {")
    assert "overflow-wrap: anywhere;" in wrap

    # And a structural backstop so the next decorative overhang cannot bring it
    # back. `clip`, never `hidden`: `hidden` would make the body a scroll
    # container and break every sticky header inside it.
    body_rule = _css_rule(styles, "\nbody {\n  overflow-x:")
    assert "clip" in body_rule
    assert "overflow-x: hidden" not in styles


def test_issue_333_the_page_is_two_typefaces_not_three():
    """Headings, body copy and labels were set in three unrelated faces at once."""
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    root = _css_rule(styles, ":root {")
    assert "--display: var(--body);" in root
    # The mono stays: it is the one face doing a job the sans cannot, holding
    # figures in columns that line up down the page.
    assert '--utility: "SFMono-Regular"' in root
    # The condensed face is gone, and so is the axis that selected it.
    assert "Condensed" not in styles
    assert "font-stretch" not in styles


def test_issue_333_dividers_are_grey_and_surfaces_are_rounded():
    """Every card edge and row rule was drawn in the text colour, on square corners."""
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    root = _css_rule(styles, ":root {")
    assert "--edge: " in root
    assert "--radius: " in root

    # No border anywhere is drawn in the ink again.
    assert "solid var(--ink)" not in styles.split(".repo-badge::after {", 1)[0]

    # The two deliberate exceptions, each of which is not a divider: the dark
    # tooltip chip, whose border IS its background, and the search field, whose
    # heavy border is the affordance telling a reader to type in it.
    tooltip = _css_rule(styles, ".repo-badge::after {")
    assert "border: 1px solid var(--ink);" in tooltip
    assert "background: var(--ink);" in tooltip
    field = _css_rule(styles, ".benchmark-search-input {")
    assert "border: 2px solid var(--ink);" in field

    # Elements that draw a single rule rather than a box stay square: rounding
    # one border of a four-sided box curls the ends of the line away from the
    # content it separates.
    radius_rule = styles.split("\n.daily-briefing,\n.daily-questions,", 1)[1].split("}", 1)[0]
    for rule_only in (".masthead", ".section-title", "footer", ".stale-banner"):
        assert f"{rule_only},\n" not in radius_rule


def test_issue_333_nothing_on_the_page_shouts():
    """58 rules set their text in capitals; the source strings are already cased."""
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert "text-transform: uppercase" not in styles
    # The labels the rules used to capitalise are written properly in the
    # markup, so removing the transform leaves readable sentence case rather
    # than lowercase fragments.
    assert '<span class="leaderboard-top-columns-rank" data-i18n="Rank">Rank</span>' in html


def test_issue_332_the_freshest_releases_reach_page_one():
    """Priority knows nothing about time, so a flat release group scrambles age.

    Crawl lag already spreads one snapshot's releases across roughly 72 hours of
    real release time -- "today's releases" was never one moment. Ordering that
    group by priority alone put a 39.8-hour-old row on page one above releases
    a few hours old. The age tiers fix that; priority still orders inside each.
    """
    import datetime as dt
    import json

    radar = Path("site/data/radar.json")
    if not radar.exists():
        import pytest

        pytest.skip("radar.json is generated; run the pipeline first")

    data = json.loads(radar.read_text(encoding="utf-8"))
    day = next(d for d in data["days"] if d["date"] == "2026-08-24")
    scanned_at = dt.datetime.fromisoformat(day["generated_at"])

    def age_hours(item: dict) -> float:
        stamp = item.get("published_at") or item.get("updated_at")
        if not stamp:
            return float("inf")
        return max(0.0, (scanned_at - dt.datetime.fromisoformat(stamp)).total_seconds() / 3600)

    def rank(item: dict) -> int:
        if item.get("event_kind") != "released":
            return 3
        hours = age_hours(item)
        return 0 if hours < 24 else 1 if hours < 72 else 2

    items = sorted(
        day["evidence_items"], key=lambda i: (rank(i), -float(i.get("total_score") or 0))
    )
    page_one = items[:20]

    # Every row a reader sees first is a release from the last 24 hours.
    assert all(rank(item) == 0 for item in page_one)
    # And the tiers are not vacuous: this day genuinely holds older releases
    # that the old flat ordering would have mixed in.
    assert any(rank(item) == 1 for item in items), "no 24-72h release to separate"
    assert any(rank(item) == 3 for item in items), "no non-release to outrank"

    # The specific regression: under priority-only ordering the 39.8-hour-old
    # rows made page one. They must not now.
    flat = sorted(
        (i for i in day["evidence_items"] if i.get("event_kind") == "released"),
        key=lambda i: -float(i.get("total_score") or 0),
    )
    assert max(age_hours(i) for i in flat[:20]) > 24, "fixture no longer shows the old bug"
    assert max(age_hours(i) for i in page_one) <= 24


# --- the blog's one and only footprint in the dashboard -------------------
#
# The blog is a separate set of documents. The dashboard gains exactly one
# menubar link to it and nothing else: no view, no route, no seed, no dialog.
# These pin that boundary, because the cheapest way to break the dashboard
# while adding pages beside it is to let the new thing leak into its router.


def test_the_dashboard_menubar_gains_exactly_one_blog_link():
    nav = re.search(
        r'<nav class="view-nav".*?</nav>', Path("site/index.html").read_text(encoding="utf-8"), re.S
    ).group(0)
    blog_links = re.findall(r"<a\b[^>]*href=\"/blog/\"[^>]*>", nav)
    assert len(blog_links) == 1
    assert "data-view" not in blog_links[0]


def test_the_blog_link_is_not_a_client_route():
    """app.js intercepts clicks on [data-view] only, so this must stay a real load."""
    from benchmark_radar.app_pages import APP_VIEWS

    assert "blog" not in APP_VIEWS
    app_js = Path("site/assets/app.js").read_text(encoding="utf-8")
    assert 'data-view="blog"' not in app_js
    assert "VIEW_SEO" in app_js and '"/blog/"' not in app_js


def test_the_blog_menubar_label_is_translated():
    app_js = Path("site/assets/app.js").read_text(encoding="utf-8")
    assert re.search(r'^\s*Blog: "[^"]+",$', app_js, re.M)


def test_blog_styles_cannot_reach_the_dashboard():
    """Every rule in blog.css is scoped to a class only generated blog pages carry."""
    css = Path("site/assets/blog.css").read_text(encoding="utf-8")
    selectors = [
        part.strip()
        for block in re.findall(r"([^{}]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
        for part in block.split(",")
        if part.strip() and not part.strip().startswith("@")
    ]
    assert selectors
    assert all(selector.startswith(".blog-page") for selector in selectors)
    assert "blog-page" not in Path("site/index.html").read_text(encoding="utf-8")
