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


def test_site_has_accessible_landmarks_and_views():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    assert parser.html_lang == "en"
    assert parser.viewport
    assert {"header", "nav", "main", "footer", "dialog"} <= set(parser.tags)
    assert {"today-view", "trends-view", "map-view", "main-content"} <= parser.ids
    assert "explorer-view" not in parser.ids


def test_priority_score_is_reachably_explained():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The score label itself is the affordance, so a reader looking at the
    # number does not have to hunt elsewhere for its definition.
    assert 'id="rubric-dialog"' in html
    assert 'id="rubric-content"' in html
    assert 'id="rubric-nav"' in html
    assert "score-explain" in script
    assert "openRubric" in script
    assert "How is this scored?" in script


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
    # The list is bounded and scroll-fed (issue #311): one page at a time, no
    # button, a status line saying how much is loaded.
    assert "observations.slice(0, todayPageLimit())" in script
    assert "state.todayResultsLimit += TODAY_PAGE_SIZE" in script
    assert "const TODAY_PAGE_SIZE = 20;" in script
    assert 'id="today-loaded"' in html
    assert 'id="today-sentinel"' in html
    assert "function watchTodaySentinel(" in script
    assert 'id="today-show-more"' not in html
    assert 'byId("daily-briefing").hidden = showingAllDates' in script
    assert 'byId("source-health-panel").hidden = showingAllDates' in script


def test_dashboard_bounds_work_before_and_during_filtering():
    """Issue #222: hidden views and unbounded card lists must not block input."""
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "state.observations = [...evidence, ...attention].sort" in script
    assert "if (state.observations) return state.observations" in script
    assert "const visibleObservations = observations.slice(0, todayPageLimit())" in script
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
    today = body.split('if (state.view === "today")', 1)[1].split('if (state.view === "map"', 1)[0]
    for key in ("date", "q", "kind", "category", "source", "organization", "event"):
        assert f'params.set("{key}"' in today

    leaderboard = body.split('if (state.view === "leaderboard")', 1)[1]
    for key in ("lq", "ldomain", "lorg", "lera", "lfrontier"):
        assert f'params.set("{key}"' in leaderboard

    assert 'if (state.view === "map" && state.entity) params.set("entity"' in body


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
    assert "grid-template-columns: repeat(6, 2.6rem)" in styles
    assert "width: 2.6rem" in styles
    assert "height: 2.6rem" in styles
    assert "grid-column: span 3" in styles
    assert 'class="repo-badge-glyph" id="lang-toggle-label">中<' in html
    assert 'class="brand-icon github-icon"' in html
    assert "grid-template-columns: repeat(6, 2.1rem)" in styles
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
    assert "中经人工核对为同一基准的记录" in script


def test_language_toggle_click_handler_is_wired():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # The 中文 button must actually respond to a click: bindEvents has to attach
    # toggleLang to #lang-toggle, otherwise clicking it silently does nothing.
    assert 'langToggle.addEventListener("click", toggleLang)' in script


def test_rubric_dialog_is_linkable_by_url_hash():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #41: opening the rubric must be shareable as a hashtag link, and
    # loading that link must reopen the same rubric version.
    assert "state.rubric" in script
    assert 'window.location.hash.slice(1)).get("rubric")' in script
    assert 'hashParams.set("rubric", state.rubric)' in script
    assert "openRubric(null, state.rubric)" in script


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
    assert "visibleObservations.map(observationCard)" in script
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
    assert 'fetch("data/radar.json", { cache: "reload" })' in script
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
    # The two dialogs on the page are non-record chrome: the scoring rubric and
    # the contact sheet (the export dialog went with the export button,
    # issue #311). Record detail must stay inline, so any third showModal()
    # is a regression to a record modal.
    assert script.count(".showModal()") == 2


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

    assert 'data-view="map"' in html
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

    assert 'data-view="map"' in html
    assert 'data-i18n="Explore">Explore</button>' in html
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
    generated_assets = {"feed.xml"}
    missing = []
    for reference in parser.local_refs:
        path = urlsplit(reference).path
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


def test_repo_badges_invite_an_action_rather_than_listing_a_roster():
    html = Path("site/index.html").read_text(encoding="utf-8")

    # Each badge sends the reader somewhere they can act. Linking to
    # /stargazers, /forks, or the issue list showed them a roster instead.
    assert 'href="https://github.com/ktwu01/benchmark-radar/fork"' in html
    assert 'href="https://github.com/ktwu01/benchmark-radar/issues/new"' in html
    assert 'href="https://github.com/ktwu01/benchmark-radar"' in html
    assert "/stargazers" not in html
    assert "benchmark-radar/forks" not in html

    for label in (">Star<", ">Fork<", ">Issues<"):
        assert label in html

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

    assert "BADGE_ACTIONS" in script
    for fragment in (
        "Star this repository on GitHub",
        "Fork this repository on GitHub",
        "Open a new issue on GitHub",
    ):
        assert fragment in script
    assert 'badge.setAttribute("aria-label"' in script


def test_leaderboard_view_is_a_first_class_dashboard_view():
    parser = SiteParser()
    html = Path("site/index.html").read_text(encoding="utf-8")
    parser.feed(html)
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # Issue #83 step 3: the Model Card Adoption Rank is reachable as
    # ?view=leaderboard from the homepage nav, not a separate page.
    assert "leaderboard-view" in parser.ids
    assert 'data-view="leaderboard"' in html
    assert '"map", "leaderboard"' in script
    assert 'if (button.dataset.view === "leaderboard") renderLeaderboard();' in script
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
    assert "navButton.hidden = true" in script
    assert 'state.view === "leaderboard" && !state.data.model_card_leaderboard' in script


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
    assert "https://ktwu01.github.io/benchmark-radar/assets/og-card.png" in html
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
    assert (
        '{t("Evidence & briefing details")} · ${citations.length.toLocaleString()} '
        '${t("sources")}' in script
    )
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

    # An older bullet without the "Why it matters" structure degrades to a head
    # with no body, yet its evidence and confidence still move to the metadata.
    fallback = insights[1]
    fbhead = next(n for n in fallback["children"] if n["className"] == "briefing-insight-head")
    fbmeta = next(n for n in fallback["children"] if n["className"] == "briefing-insight-meta")
    assert subtext(fbhead).startswith("An older-format bullet")
    assert "Evidence:" not in subtext(fbhead)
    assert "Medium confidence" in subtext(fbmeta)
    assert "2 sources" in subtext(fbmeta)


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
    assert "border: 1px solid var(--ink)" in questions
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
    assert "雷达今天首次看到了哪些基准、数据集或评估方法？" in text
    # The model prose is the snapshot's zh rendering, not the English original.
    assert "今天首次观察到的记录大多是智能体评估框架。" in text
    assert "Most of today's first-observed records" not in text
    assert "未找到可信的反方观点。" in text


def test_rendered_questions_keep_english_prose_when_zh_fields_are_absent():
    """Without zh prose fields, only the fixed question strings translate."""
    nodes = list(_flatten(_rendered_questions("tests/fixtures/daily_questions.json", "zh")))
    text = next(iter(nodes))["text"]

    assert "雷达今天首次看到了哪些基准、数据集或评估方法？" in text
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
    assert button["text"] == "联系"
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
    assert "text: emptyTodayMessage(day, benchmarkMatches)," in script
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

    # Every sentence it can print is translated, including the general one,
    # which shipped untranslated before this change.
    for phrase in (
        "No observations match these filters. Clear one or more filters to widen the view.",
        "Try another date, or clear the filter.",
    ):
        assert script.count(f'"{phrase}"') >= 2, phrase


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
    assert 'window.history.pushState(null, "", url);' in script
    assert 'window.history.replaceState(null, "", url);' in script

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
    of three, and more load only when the reader scrolls to the sentinel under
    the list. The status line at the bottom states how much is on screen, so
    progressive loading never reads as a truncated list.
    """
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    # One named page size, applied at first paint and on every filter change.
    assert "const TODAY_PAGE_SIZE = 20;" in script
    assert "todayResultsLimit: TODAY_PAGE_SIZE," in script
    renderer = script.split("function renderToday({ resultsOnly = false } = {})", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "state.todayResultsLimit = TODAY_PAGE_SIZE;" in renderer
    assert "const visibleObservations = observations.slice(0, todayPageLimit());" in renderer

    # Scroll loads; no button competes with it.
    assert "function watchTodaySentinel(" in script
    watcher = script.split("function watchTodaySentinel(", 1)[1].split("\nfunction ", 1)[0]
    assert "new IntersectionObserver(" in watcher
    assert "state.todayResultsLimit += TODAY_PAGE_SIZE;" in watcher
    assert "renderToday({ resultsOnly: true });" in watcher
    assert 'id="today-sentinel"' in html
    assert "watchTodaySentinel(remainingResults);" in renderer
    assert 'id="today-show-more"' not in html

    # A load-more pass appends the new page instead of rebuilding the list,
    # so a card the reader expanded stays open under them.
    assert "const growsInPlace =" in renderer
    assert "listHost.append(" in renderer
    assert "observationCard(item, renderedCount + offset))" in renderer
    assert "state.todayRenderedCount = visibleObservations.length;" in renderer

    # No IntersectionObserver, no scroll trigger, no button: the cap would
    # strand every row past the first page, so the bound is removed instead.
    fallback = script.split("function todayPageLimit()", 1)[1].split("\nfunction ", 1)[0]
    assert "return Infinity;" in fallback
    assert "observations.slice(0, todayPageLimit())" in renderer

    # The bottom line reports what loaded.
    assert "{loaded} of {total} results loaded · scroll for more" in renderer
    assert "All {total} results loaded" in renderer

    # The legend keeps the class breakdown and the order; the raw total and
    # its duplicated noun are gone, and "need attention" lost its verb.
    assert 'id="today-count"' not in html
    assert 'byId("today-breakdown").textContent =' in renderer
    assert '${attentionCount} ${t("attention")}' in renderer
    assert '"need attention"' not in script

    # Dataset access moved out of the header: contact-first, star-first.
    assert 'id="badge-export"' not in html
    assert 'id="export-dialog"' not in html
    assert "function openExport(" not in script
    assert "function observationsToCsv(" not in script
    assert "function downloadText(" not in script
    footer = html.split('<p class="footer-dataset">', 1)[1].split("</p>", 1)[0]
    assert "No crawler needed: star the repository" in footer
    assert 'id="footer-contact"' in footer
    contact = script.split("function openContact()", 1)[1].split("dialog.showModal();", 1)[0]
    assert "No crawler needed: star the repository" in contact
    assert 'className: "contact-dataset"' in contact
