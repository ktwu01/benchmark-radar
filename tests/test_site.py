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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append(tag)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "html":
            self.html_lang = str(values.get("lang", ""))
        if tag == "meta" and values.get("name") == "viewport":
            self.viewport = True
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
        assert f'["{component}", Number(item.' in script


def test_today_view_has_one_filterable_observation_list_and_one_source_status():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert html.count("Matching observations") == 1
    assert 'id="today-list"' in html
    assert 'id="filters"' in html
    assert 'id="kind-filter"' in html
    assert "observations.map(observationCard)" in script
    assert "Daily field note" not in html
    assert "What entered the field?" not in html
    assert "today-overview" not in html
    assert "today-attention-list" not in html
    assert "Sources in results" not in script
    assert "health-summary" not in html


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

    assert 'text: "Not quality-scored"' in script
    assert '["Submissions", Number(item.metrics?.submissions ?? 1).toLocaleString()]' in script
    assert '["Published", formatDate(item.published_at' in script
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
    assert script.count(".showModal()") == 1


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


def test_trend_map_shows_the_complete_corpus_and_summarizes_its_shape():
    html = Path("site/index.html").read_text(encoding="utf-8")
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'id="map-insights"' in html
    assert "renderMapInsights(corpus)" in script
    assert "Most represented organizations" in script
    assert "Showing all ${artifacts.length.toLocaleString()} artifacts" in script
    assert ".slice(0, 16)" not in script
    assert "author nodes summarized above and omitted from the canvas" in script


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


def test_static_html_references_existing_local_assets():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    missing = []
    for reference in parser.local_refs:
        path = urlsplit(reference).path
        target = Path("site") if path in {"", ".", "./"} else Path("site") / path
        if not target.exists():
            missing.append(reference)

    assert not missing


def test_one_snapshot_trend_explains_history_requirement():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")
    styles = Path("site/assets/styles.css").read_text(encoding="utf-8")

    assert "At least two daily snapshots are required to calculate a trend." in script
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
    # A collapsed <details> next to a long, often multi-screen record list was
    # reported unreadable ("I cannot see it") -- default it open so the totals
    # are visible without a click, on both wide and stacked-mobile layouts.
    assert '<details id="corpus-totals-details" open>' in html


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
    assert '"not yet reported in these cards"' in script
    assert '"Domains reported at least once"' in script


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
