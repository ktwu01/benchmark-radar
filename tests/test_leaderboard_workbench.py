from pathlib import Path


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_frontier_opens_on_a_new_signal_with_three_readable_scores():
    # The panel is the score track, so the benchmark it opens on is chosen by the
    # same reading: the newest instrument that already carries three or more
    # dated values. A one-point plot is technically recent but says nothing.
    script = source("site/assets/app.js")

    default_entry = script.split("function frontierDefaultEntry(board)", 1)[1].split(
        "\nconst BENCHMARK_TASK_SHAPES", 1
    )[0]
    assert "isNewBenchmark(entry, board)" in default_entry
    assert "datedCount(entry) >= 3" in default_entry
    assert "sharedSignals.length ? sharedSignals : scored" in default_entry
    # And every candidate has a score record, so the default can never be a
    # benchmark the panel cannot draw.
    assert "entry.card_count > 0 && scoreRecord(entry.benchmark_id)" in default_entry


def test_a_thin_history_no_longer_falls_back_to_an_adoption_stepper():
    # A benchmark with one dated reporting organization used to swap the chart
    # for a three-step "released / first report / awaiting a second" list. That
    # is an adoption reading, and the score track answers a different question:
    # a benchmark with one adopter can still carry several readable scores, and
    # one with none is not offered at all.
    html = source("site/index.html")
    script = source("site/assets/app.js")

    assert 'id="frontier-milestones"' not in html
    assert "function sparseFrontier(" not in script
    assert "frontier.length < 2" not in script
    assert "frontier-sparse" not in script
    assert "Awaiting an independent second organization" not in script


def test_the_panel_prints_no_reporting_stage_verdict():
    # The stage badge graded a benchmark "Saturated reporting" from the share of
    # registry organizations reporting it. Saturation stays an editorial
    # judgement (see the header of data/benchmark_scores.yml), and the panel now
    # shows reported values over time rather than scoring them.
    html = source("site/index.html")
    script = source("site/assets/app.js")

    assert "function reportingStage(" not in script
    assert "advances / total >= 0.8" not in script
    assert 't("Saturated reporting")' not in script
    assert '"Saturated reporting":' not in script, "no zh entry for a badge nothing renders"
    assert "convention, not quality" not in script
    # The element survives for the external path, which puts a source name in it,
    # and the curated path hides it rather than leaving a bare outline.
    assert 'id="frontier-stage"' in html
    assert "stage.hidden = true;" in script or "stageBadge.hidden = true;" in script


def test_frontier_svg_fits_the_viewport_without_horizontal_scrolling():
    styles = source("site/assets/styles.css")

    rule = styles.split(".frontier-chart svg {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in rule
    assert "height: auto" in rule
    assert "min-width" not in rule
    # The marker styling this used to check belonged to the adoption advance
    # diamond, which is gone with its band. The score point is the only marker
    # the chart draws now, and it keeps the brand-glyph treatment (issue #178).
    assert ".score-point-face" in styles
    assert ".score-point-glyph" in styles


def test_trajectory_points_expose_and_pin_record_details():
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    assert 'className: "frontier-tooltip"' in script
    assert 'role: "tooltip"' in script
    assert 'group.addEventListener("pointerenter", () =>' in script
    assert 'group.addEventListener("click"' in script
    assert 'event.key === "Escape"' in script
    assert 'classList.add("is-selected")' in script
    assert '"aria-pressed": "false"' in script
    assert 'label: t("Run conditions")' in script
    assert 'label: t("Source")' in script
    assert ".score-point.is-selected .score-point-face" in styles
    assert "pinned: selectedFrontierPoint === group" in script
    assert 'record.unit === "percent" ? "%" : ` ${record.unit}`' in script
    assert 'role: "group"' in script
    assert 'event.key === "Escape" && selectedFrontierPoint' in script
    assert 'view !== "leaderboard" && selectedFrontierPoint' in script
    assert 'pinned ? "dialog" : "tooltip"' in script
    assert 'text: t("Open source record ↗")' in script
    # Resolved from the point's own chart, not by a document-wide id: the
    # crawled panel mounts a second tooltip and getElementById returned that
    # one, which is what killed hover and click on the curated chart (#261).
    assert 'frontierTooltipFor(group)?.querySelector("a")?.focus()' in script
    assert 'byId("frontier-tooltip")' not in script
    assert "tooltip?.contains(document.activeElement)" in script
    assert "if (focused) show()" in script
    assert "else if (hovered)" in script
    assert "if (selectedFrontierPoint === group)" in script
    assert "clearFrontierPointSelection();" in script.split("function openRubric", 1)[1]
    assert "function enableFrontierTouchTargets(svg)" in script
    assert "nearestDistance <= 22" in script
    assert 'window.addEventListener("resize", repositionFrontierTooltip)' in script
    assert 'window.addEventListener("scroll", repositionFrontierTooltip' in script
    assert "pointer-events: none" in styles
    assert ".frontier-tooltip.is-pinned" in styles
    # Score points are now the only pinnable marks, so they carry the whole
    # tooltip contract that the advance diamond and the rug ticks used to share.
    assert 'kind: t("Score read from a document")' in script
    assert "title: `${observation.organization} · ${observation.model}`" in script
    assert "function scoreOnlyChart(" not in script
    assert "`${event.organization} · ${event.model} · first report · count" not in script
    assert "`${observation.model} · ${observation.value} · ${observation.protocol}`" not in script


def test_the_score_legend_keys_one_mark_and_promises_no_connection():
    # The legend used to explain a solid connection (same instrument and
    # protocol across organizations) and a dashed one (same, within a single
    # vendor). Neither is drawn any more: comparability is stated by the paired
    # comparison readout, in words that can carry the caveat a line cannot.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    assert '"legend-swatch-score",' in script
    assert '"one value read verbatim from a cited document"' in script
    for gone in (
        "legend-swatch-score-line",
        "Solid score connection",
        "Dashed score connection",
        "same instrument and protocol across organizations",
        "same instrument and protocol, one organization only",
    ):
        assert gone not in script, f"{gone!r} survives in the legend"
    assert ".legend-swatch-score-line" not in styles


def test_task_preview_distinguishes_source_paraphrase_from_domain_fallback():
    html = source("site/index.html")
    script = source("site/assets/app.js")

    assert 'id="frontier-task-preview"' in html
    assert "BENCHMARK_TASK_SHAPES[entry.benchmark_id]" in script
    assert "TASK_SHAPES[entry.domain]" in script
    assert '"Source-paraphrased task shape"' in script
    assert '"Representative task shape"' in script
    assert "Not a verbatim benchmark item" in script
    assert 'rel: "noopener noreferrer"' in script


def test_workbench_states_the_schema_needed_for_a_true_pareto_frontier():
    html = source("site/index.html")
    normalized = " ".join(html.split())

    assert "What would make this a true Pareto frontier?" in normalized
    for field in (
        "benchmark version and split",
        "metric direction",
        "harness or scaffold",
        "reasoning budget",
        "cost or latency",
    ):
        assert field in normalized
    assert "Only compatible configurations" in normalized
    assert "connect only nondominated observations" in normalized
    assert "publication-time slider" in normalized


def test_apex_agents_links_to_its_actual_paper():
    registry = source("data/model_cards.yml")
    apex = registry.split("  - id: apex_agents", 1)[1].split("\n  - id:", 1)[0]

    assert "https://arxiv.org/abs/2601.14242" in apex
    assert "released: 2026-01-20" in apex
    assert "2512.02141" not in apex


def test_issue_240_sections_default_collapsed_but_visible():
    # "Benchmarks by model card adoption", "Model cards in the registry", and
    # "What the two layers say - Stated findings" are <details> with no `open`:
    # present on first load, closed until the reader asks.
    html = source("site/index.html")

    assert '<details class="findings-panel" id="benchmark-findings"' in html
    assert '<details class="trend-panel adoption-table" id="adoption-table">' in html
    assert '<details class="ledger" aria-labelledby="leaderboard-cards-heading">' in html
    assert 'id="benchmark-findings" open' not in html
    assert 'adoption-table" open' not in html
    assert 'class="ledger" open' not in html

    # The empty-findings behaviour is unchanged: hidden entirely, since an
    # empty panel reads as "we looked and the field is uneventful". Collapsed
    # by default applies only when findings exist.
    script = source("site/assets/app.js")
    renderer = script.split("function renderBenchmarkFindings(board)", 1)[1].split(
        "\nfunction modelCardLabelCounts", 1
    )[0]
    assert "panel.hidden = true" in renderer
    assert "panel.hidden = false" in renderer


def test_lfrontier_resolves_slug_first_then_canonical_id_then_default():
    # Display plan step 6's permalink contract, in this order: an exact
    # external slug (which is what gives the crawled-only benchmarks a URL),
    # then a canonical registry id so pre-widening shared links keep working,
    # then the auto-picked default.
    script = source("site/assets/app.js")

    dispatch = script.split("function renderAdoptionFrontier(board)", 1)[1].split(
        "const events = frontierEvents(entry)", 1
    )[0]
    slug_check = dispatch.index("record.slug === state.lfrontier")
    canonical_check = dispatch.index("candidate.benchmark_id === state.lfrontier")
    default_pick = dispatch.index("state.lfrontier = defaultEntry.benchmark_id")
    assert slug_check < canonical_check < default_pick
    # Only the default pick clears the reader's explicitness flag: the flag is
    # cleared exactly once in the dispatch, and only after the default is taken.
    assert dispatch.count("state.lfrontierExplicit = false") == 1
    assert dispatch.index("state.lfrontierExplicit = false") > default_pick


def test_a_slug_permalink_survives_the_index_fetch():
    # While the index is on the wire the panel holds a loading state instead of
    # snapping to the default, which would rewrite the reader's URL before the
    # slug could be checked. When the fetch settles, the panel re-renders.
    script = source("site/assets/app.js")

    dispatch = script.split("function renderAdoptionFrontier(board)", 1)[1].split(
        "const events = frontierEvents(entry)", 1
    )[0]
    # The still-loading branch holds the selection in a loading shell and
    # returns before the default pick can rewrite the reader's URL.
    loading = dispatch.split("!state.benchmarkIndexLoaded", 1)[1].split("return;", 1)[0]
    assert "state.lfrontier = defaultEntry.benchmark_id" not in loading
    assert "Loading benchmark details" in loading
    # The fetch-failed branch ("!state.benchmarkIndex)" with the closing paren,
    # to tell it apart from the Loaded flag above) says so explicitly rather
    # than snapping to the default either.
    failed = dispatch.split("!state.benchmarkIndex)", 1)[1].split("return;", 1)[0]
    assert "state.lfrontier = defaultEntry.benchmark_id" not in failed
    assert "Could not load details for this benchmark." in failed

    init = script.split("function initBenchmarkSearch()", 1)[1].split(
        "function renderBenchmarkNavigator", 1
    )[0]
    assert "state.benchmarkIndexLoaded = true" in init
    assert "renderAdoptionFrontier(board)" in init


def test_detail_panel_renders_for_any_selected_record():
    script = source("site/assets/app.js")

    for fn in (
        "function renderExternalBenchmark(board, scored, record)",
        "function externalIdentityBlock(detail)",
        "function externalOpennessBlock(detail)",
        "function externalSizesBlock(detail)",
        "function externalScoresBlock(shard)",
        "function loadBenchmarkShard(slug)",
    ):
        assert fn in script
    # Empty fields say "not established" in the DOM rather than being hidden:
    # whether these facts are known is precisely the reader's question.
    for phrase in (
        "publisher not established",
        "release date not established",
        "modality not established",
        "description not established",
        "size not established",
    ):
        assert phrase in script
    # The publisher keeps its role: the hub card publisher is not the creator.
    assert "publisherRoleLabel" in script
    assert "published the hub card" in script


def test_search_selection_updates_the_detail_panel():
    script = source("site/assets/app.js")

    row = script.split("function benchmarkResultRow(record)", 1)[1].split(
        "function renderBenchmarkSearch", 1
    )[0]
    assert "selectFrontier(record.slug)" in row
    assert "renderAdoptionFrontier(board)" in row


def test_crawled_scores_are_partitioned_by_source_with_no_merge_path():
    # The honesty rule has teeth: the renderer reads the keyed scores_by_source
    # object and paints one table per source. No flat array of rows from two
    # sources exists anywhere in this code path to be sorted into a ranking.
    script = source("site/assets/app.js")

    section = script.split("function externalScoresBlock(shard)", 1)[1].split(
        "// Identity siblings", 1
    )[0]
    assert "shard.scores_by_source" in section
    assert "Object.keys(bySource)" in section
    assert "sources.map((source) => externalSourceTable(source, bySource[source]))" in section
    assert ".concat(" not in section
    assert "[...rows" not in section
    # element() appends children verbatim, so the per-source tables are spread
    # into the child list; passing the mapped array itself would stringify it
    # into "[object HTMLDivElement]" in the rendered panel.
    assert "...(sources.length" in section


def test_crawled_scores_never_render_a_percentage_or_scale():
    # display_scale is null on every crawled series, so no percentage bar and
    # no "% of max" can be drawn; raw_value prints verbatim (in the chart's point
    # labels, since the table that used to print it is gone). vending-bench-2
    # declares max 1.0 and carries 8017.59, so a contradicted declared maximum
    # is printed as a claim about the source, never used as a denominator.
    script = source("site/assets/app.js")

    section = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "// Identity siblings", 1
    )[0]
    assert "row.raw_value" in section
    assert "display_scale" not in section
    assert "%" not in section
    assert "max_score_contradicted" in section
    assert "declared_max" in section


def test_every_crawled_score_is_a_plotted_point():
    # The crawled layer used to render as a table and nothing else: 679
    # benchmarks carrying 5,544 real numbers got no figure while 59 curated ones
    # did, because a crawled row has no evaluation date. A withheld protocol is a
    # reason not to draw a chronology; it is not a reason to make the reader draw
    # the field in their own head. So every reported value is a point, and the
    # chart replaces the table outright rather than sitting beside it -- the
    # table added nothing the chart's point titles did not already say.
    script = source("site/assets/app.js")

    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
    )[0]
    table = script.split("function externalSourceTable(source, payload)", 1)[1].split(
        "// Identity siblings", 1
    )[0]

    assert "externalScoreChart(source, payload)" in table
    assert "<table" not in table.replace('"table"', "").replace("'table'", "")
    assert "(payload.rows || [])" in chart
    assert ".slice(" not in chart
    # A value that did not parse into a number has no position on an axis, so it
    # is dropped. That is the only row the chart may drop, and it drops it by
    # testing the value rather than by a cap.
    assert 'typeof row.value === "number" && Number.isFinite(row.value)' in chart


def test_the_crawled_chart_axis_is_score_not_time():
    # A crawled row's only date is announcement_date, the MODEL's own release
    # date, not a measurement date -- normalize_llm_stats fills reported_date
    # from it now (external_catalog.py:_observation), so the field is real,
    # but it is still not a time this chart's x-axis is entitled to use: the
    # x position comes from each row's own value (sorted ascending), and the
    # axis label says in words that the date recorded is model release, not
    # measurement time, so this is still not a time axis despite the date
    # existing.
    script = source("site/assets/app.js")

    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
    )[0]

    assert "a.value - b.value" in chart
    # The label was shortened (issue #269): it had grown into a defensive
    # sentence that read as an excuse for the dates rather than a description
    # of the axis. The claim it has to make is unchanged -- ordered by score,
    # and the dates are release dates rather than measurement times.
    assert "ordered by score, low to high." in chart
    assert "model release dates, not when each score was measured" in chart
    # reported_date is read (for the pinned card's Date row), but never as an
    # x-coordinate: the axis-building code above the point loop never touches it.
    assert "row.reported_date" in chart
    assert "x(row.reported_date)" not in chart
    # And no segment between points, for the same reason the curated chart draws
    # none: adjacency by score is not a trajectory.
    assert "polyline" not in chart


def test_the_crawled_chart_reuses_the_curated_chart_classes():
    # The visual language is not allowed to fork: the crawled figure draws with
    # the exact classes scoreTrackChart draws with (frontier-grid, frontier-tick,
    # frontier-axis-label, score-point/-face/-glyph, score-best-line/-label), so
    # one CSS ruleset governs both and a reader never has to learn a second
    # chart style for a second kind of evidence.
    script = source("site/assets/app.js")

    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
    )[0]

    for shared_class in [
        "frontier-grid",
        "frontier-tick",
        "frontier-axis-label",
        "score-point-face",
        "score-point-glyph",
        "score-point-citation-ring",
        "score-best-line",
        "score-best-label",
    ]:
        assert shared_class in chart, shared_class
    assert "external-field" not in chart


def test_the_crawled_chart_is_drawn_per_source_block():
    # One chart per source block, built from that block's own rows. The chart is
    # called from inside externalSourceTable, which the keyed scores_by_source
    # object already partitions, so there is no path by which two sources' values
    # land on one axis.
    script = source("site/assets/app.js")

    block = script.split("function externalScoresBlock(shard)", 1)[1].split(
        "\n// --- The reported field", 1
    )[0]

    assert "externalScoreChart" not in block


def test_every_crawled_score_has_the_curated_charts_pinned_tooltip():
    # A crawled point with only a native <title> was a hover with no keyboard
    # affordance and no click -- a reader landing on a single-point field
    # (e.g. llm-stats-researchclawbench) saw a dot and nothing else. Every
    # crawled point now goes through makeFrontierPointInteractive, the exact
    # system the curated chart's points use: role="button", data-frontier-point,
    # and a pinned card on click. externalSourceTable mounts its own
    # frontierTooltip() instance beside the chart so that card has somewhere to
    # render (external records hide the curated #frontier-chart entirely).
    script = source("site/assets/app.js")

    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
    )[0]
    assert "makeFrontierPointInteractive(group" in chart
    assert 'role: "button"' in chart
    assert '"data-frontier-point": ""' in chart
    assert "enableFrontierTouchTargets(svg)" in chart
    # Only fields a crawled row actually carries -- no Instrument, Protocol,
    # Date or Read-from row, which do not exist in this source and would print
    # as "not recorded" filler beside the curated card's real ones.
    assert 't("Instrument")' not in chart
    assert 't("Protocol")' not in chart
    assert 't("Date")' not in chart

    table_fn = script.split("function externalSourceTable(source, payload)", 1)[1].split(
        "\n// Identity siblings", 1
    )[0]
    assert 'element("div", { className: "frontier-chart" }, [chart, frontierTooltip()])' in table_fn


def test_the_pinned_tooltip_positions_against_its_own_parent_not_a_fixed_id():
    # positionFrontierTooltip and the two keyboard-cycle handlers used to read
    # byId("frontier-chart") directly, which only exists for the curated path.
    # Deriving the host from the tooltip's own parentElement is what lets one
    # tooltip implementation serve both the curated chart (mounted inside
    # #frontier-chart) and the crawled chart (mounted inside a lookalike
    # .frontier-chart div under #frontier-external).
    script = source("site/assets/app.js")

    position_fn = script.split("function positionFrontierTooltip(tooltip, group)", 1)[1].split(
        "\nfunction repositionFrontierTooltip", 1
    )[0]
    assert "tooltip.parentElement" in position_fn
    assert 'byId("frontier-chart")' not in position_fn


def test_crawled_third_party_text_never_enters_the_dom_as_markup():
    # Descriptions and README excerpts are crawled third-party HTML. The whole
    # external detail path builds nodes through element({text}), which sets
    # textContent.
    script = source("site/assets/app.js")

    section = script.split("// --- External catalog detail", 1)[1].split(
        "function renderBenchmarkNavigator", 1
    )[0]
    assert "innerHTML" not in section
    assert "insertAdjacentHTML" not in section


def test_related_records_are_cross_links_never_merges():
    # A variant sibling selects its own shard rather than folding into the
    # current record: two labelled records are a smaller lie than one wrong
    # merge.
    script = source("site/assets/app.js")

    section = script.split("function externalSiblingsBlock(shard)", 1)[1].split(
        "function externalBenchmarkDetail", 1
    )[0]
    assert "selectFrontier(sibling.slug)" in section


def test_shard_fetch_failure_keeps_the_selection_and_the_row():
    # Display plan step 7: a failed shard renders an explicit message in the
    # panel and does not clear the selection or throw into the router.
    script = source("site/assets/app.js")

    assert "fetch(`data/benchmarks/${slug}.json`)" in script
    handler = script.split("loadBenchmarkShard(record.slug).then((shard) =>", 1)[1]
    assert "state.lfrontier !== record.slug" in handler
    assert "Could not load details for this benchmark." in handler


def test_each_chart_owns_its_tooltip_rather_than_sharing_one_id():
    """Issue #261: hover and click looked dead on the curated chart.

    Both charts mounted a tooltip with the same hardcoded id, and
    #frontier-external sits above #frontier-chart in index.html. Every
    getElementById therefore resolved to the crawled panel's node, so the
    curated chart's card was written into a hidden element -- the handlers
    fired correctly and painted somewhere invisible.
    """
    script = source("site/assets/app.js")
    html = source("site/index.html")

    # The container order that made a shared id unresolvable is still the
    # order the page ships; the fix must not depend on changing it.
    assert html.index('id="frontier-external"') < html.index('id="frontier-chart"')

    # No document-wide lookup survives anywhere in the tooltip machinery.
    assert 'byId("frontier-tooltip")' not in script
    assert "id: `frontier-tooltip-${++frontierTooltipSeq}`" in script
    assert 'node?.closest(".frontier-chart")?.querySelector(".frontier-tooltip")' in script


def test_leaving_a_crawled_record_empties_its_panel_rather_than_hiding_it():
    """The other half of #261: hidden is not gone.

    A crawled record's DOM carries its own tooltip and its own focusable
    points. `hidden` only stops painting, so left in place they stayed in the
    tab order and in every document-wide query for the rest of the session.
    """
    script = source("site/assets/app.js")
    chrome = script.split("function setCanonicalFrontierChrome", 1)[1].split("\n}", 1)[0]

    assert "external.hidden = visible;" in chrome
    assert "if (visible) replaceChildren(external, []);" in chrome


def test_the_crawled_chart_ticks_label_real_values_not_padded_bounds():
    """Issue #269: AIME 2025 announced an axis from "-0.1" to "1.17".

    The band pads by 18% so points are not drawn on the frame, and the ticks
    printed that padded bound. On a 0.067-to-1.0 field that advertised a
    negative score and a ceiling above every observed value -- two numbers that
    are not in the data and cannot be.
    """
    script = source("site/assets/app.js")
    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
    )[0]

    assert "for (const value of [high, low])" in chart
    assert "for (const value of [band.high, band.low])" not in chart
    # The band itself still pads; only the labels changed.
    assert "band = { low: low - pad, high: high + pad }" in chart


def test_the_shortlist_says_what_it_ranks_by_behind_an_info_toggle():
    """Issue #269: "Most reported" invited a comparison it does not make.

    The list ranks by how many curated model cards report a benchmark. A
    crawled score count answers a different question, so AIME 2025's 115
    crawled scores losing to GPQA Diamond's 26 model cards is two measures
    being confused, not a ranking bug. The heading now says so, and the
    explanation sits behind the same (i) toggle the crawled source blocks use.
    """
    html = source("site/index.html")
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    assert 'data-i18n="Most reported in model cards"' in html
    assert 'id="benchmark-example-info"' in html
    # Reuses infoDisclosure rather than inventing a second (i) pattern.
    assert "infoDisclosure(" in script.split("function renderBenchmarkNavigator", 1)[1][:1200]
    assert "measures vendor reporting convention" in script

    # Hover opens it as well as click. A closed <details> hides its body by not
    # generating a box, so any `display` on that body pins the panel open --
    # the reveal runs on visibility/opacity instead.
    assert ".info-disclosure:hover > .info-disclosure-body" in styles
    body = styles.split(".info-disclosure > .info-disclosure-body", 1)[1][:200]
    assert "visibility: hidden" in body

    # And it escapes the navigator's scroll container rather than being clipped.
    pinned = styles.split(".benchmark-example-heading .info-disclosure-body", 1)[1][:200]
    assert "position: fixed" in pinned
