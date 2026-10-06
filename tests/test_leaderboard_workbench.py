import json
from pathlib import Path


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_catalog_aime_2025_has_a_source_ranked_record_sequence():
    """Issue #312: 115 drawable dots cannot silently produce no record path."""
    shard = json.loads(
        Path("site/data/benchmarks/llm-stats-aime-2025.json").read_text(encoding="utf-8")
    )
    rows = shard["scores_by_source"]["llm_stats"]["rows"]
    series = shard["scores_by_source"]["llm_stats"]["series"]

    assert len(rows) == 115
    assert series["direction"] == "higher_is_better"
    assert series["direction_basis"] == "source_rank_descending"
    ranked = sorted(rows, key=lambda row: row["rank_in_source_response"])
    assert [row["value"] for row in ranked] == sorted(
        (row["value"] for row in ranked), reverse=True
    )

    best_by_date = {}
    for row in rows:
        current = best_by_date.get(row["reported_date"])
        if current is None or (row["value"], -row["rank_in_source_response"]) > (
            current["value"],
            -current["rank_in_source_response"],
        ):
            best_by_date[row["reported_date"]] = row

    setters = []
    best = None
    for row in (best_by_date[date] for date in sorted(best_by_date)):
        if best is None or row["value"] > best:
            best = row["value"]
            setters.append(row)

    assert [(row["reported_date"], row["value"]) for row in setters] == [
        ("2025-01-10", 0.498),
        ("2025-02-17", 0.933),
        ("2025-07-09", 1.0),
    ]


def test_the_frontier_opens_on_the_benchmark_the_page_ranks_first():
    """The highest observation-count candidate is both rank 1 and the default chart."""
    script = source("site/assets/app.js")
    default = script.split("function frontierDefaultEntry(board)", 1)[1].split("\n}", 1)[0]
    assert "saturationRows()[0]" in default
    assert "if (!state.lfrontierExplicit) state.lfrontier = defaultEntry?.id" in script


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
    assert "if (selectedFrontierPoint || describedFrontierPoint)" in script
    assert 'pinned ? "dialog" : "tooltip"' in script
    assert 'details.urlLabel || t("Open source record ↗")' in script
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
    # Issue #276: this panel used to say "Pareto frontier", "harness or
    # scaffold" and "nondominated observations". The substance it has to keep
    # is the list of things you must know before two scores can be compared,
    # so these assert the meaning rather than the vocabulary that carried it.
    html = source("site/index.html")
    normalized = " ".join(html.split())

    assert "What would it take to chart best score against lowest cost?" in normalized
    for field in (
        "which version of the test",
        "which slice of it",
        "whether a high number is good or bad",
        "which model",
        "what software ran it",
        "how much thinking time",
        "what it cost",
        "how long it took",
        "when it was published",
    ):
        assert field in normalized
    # Codex review: the fields must be *recorded*, not identical. Model, cost,
    # time and date are exactly what the chart varies, so asserting this line
    # keeps a future rewrite from turning them back into equality constraints.
    assert "are free to differ, because those are what the chart compares" in normalized
    assert "It does not yet record those measurements." in normalized
    assert "nothing else beats on both at once" in normalized
    assert "date slider" in normalized


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


def test_all_permalink_ids_resolve_through_the_same_catalog():
    script = source("site/assets/app.js")
    dispatch = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\n// ---", 1)[0]
    assert "state.benchmarkIndex.find((row) => row.slug === state.lfrontier)" in dispatch
    assert "renderCatalogBenchmark(board, scored, record)" in dispatch
    assert "scoreRecord(" not in dispatch
    assert "board.entries" not in dispatch
    assert "if (!state.lfrontierExplicit)" in dispatch


def test_a_slug_permalink_survives_loading_and_failed_catalog_fetches():
    script = source("site/assets/app.js")
    dispatch = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\n// ---", 1)[0]
    loading = dispatch.split("if (!state.benchmarkIndex)", 1)[1].split("return;", 1)[0]
    assert "Loading benchmark details" in loading
    assert "Full benchmark catalog could not be loaded." in loading
    assert "state.lfrontier =" not in loading
    init = script.split("function initBenchmarkSearch()", 1)[1].split("\n// ---", 1)[0]
    assert "reloadBenchmarkIndex();" in init
    settlement = script.split("function reloadBenchmarkIndex()", 1)[1].split(
        "function benchmarkIndexRetryButton", 1
    )[0]
    assert "state.benchmarkIndexLoaded = true" in settlement
    assert "renderLeaderboard();" in settlement


def test_detail_panel_renders_for_any_selected_record():
    script = source("site/assets/app.js")

    for fn in (
        "function renderCatalogBenchmark(board, scored, record)",
        "function catalogIdentityBlock(detail)",
        "function catalogOpennessBlock(detail)",
        "function catalogSizesBlock(detail)",
        "function catalogScoresBlock(shard)",
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
    identity = script.split("function catalogIdentityBlock(detail)", 1)[1].split(
        "function catalogOpennessBlock", 1
    )[0]
    assert 't("Importer")' in identity
    assert 't("Original evidence")' in identity
    assert 't("Review status")' in identity
    assert "provenance.review_state" in identity
    assert 't("not reviewed")' not in identity
    assert "detail.provenance" in identity


def test_search_selection_updates_the_detail_panel():
    script = source("site/assets/app.js")

    row = script.split("function benchmarkResultRow(record", 1)[1].split(
        "function renderBenchmarkSearch", 1
    )[0]
    assert "selectFrontier(record.slug)" in row
    assert "renderAdoptionFrontier(catalogDocumentBoard())" in row
    # Issue #245 added a `navigate` path for rows rendered outside the
    # leaderboard, where updating the panel in place would look like the click
    # did nothing. It must not replace the in-place update the panel relies on.
    assert 'setView("saturation")' in row


def test_crawled_scores_are_partitioned_by_source_with_no_merge_path():
    # The honesty rule has teeth: the renderer reads the keyed scores_by_source
    # object and paints one table per source. No flat array of rows from two
    # sources exists anywhere in this code path to be sorted into a ranking.
    script = source("site/assets/app.js")

    section = script.split("function catalogScoresBlock(shard)", 1)[1].split(
        "// Identity siblings", 1
    )[0]
    assert "shard.scores_by_source" in section
    assert "Object.keys(bySource)" in section
    assert "sources.map((source) => catalogSourceTable(source, bySource[source]))" in section
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

    section = script.split("function catalogPlottedRows(payload)", 1)[1].split(
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

    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]
    table = script.split("function catalogSourceTable(source, payload)", 1)[1].split(
        "// Identity siblings", 1
    )[0]

    assert "catalogScoreChart(source, payload)" in table
    assert "<table" not in table.replace('"table"', "").replace("'table'", "")
    assert "(payload.rows || [])" in chart
    # A value that did not parse into a number has no position on an axis, so it
    # is dropped, and it is dropped by testing the value rather than by a cap.
    assert 'typeof row.value === "number" && Number.isFinite(row.value)' in chart
    # No cap. The rows reach .sort() through .filter(), which already returns a
    # fresh array, so the sort cannot mutate the caller's rows and no copying
    # slice is needed to protect them. Every .slice(0, N) here is ISO-date
    # truncation, not a row limit; a truncating slice over the rows would
    # silently hide scores.
    #
    # Counting instances is not the guarantee -- issue #298 added a second
    # date truncation for the quarterly axis ticks, which drops nothing. The
    # guarantee is that each one slices a date string to 10 chars, so any
    # slice with a different length, or one applied to the rows, fails here.
    assert ".filter((row) =>" in chart
    assert chart.count(".slice(0,") == chart.count(".slice(0, 10)")
    assert ".slice(0, 10)" in chart
    for cap in ("plotted.slice(0,", "numeric.slice(0,", "dated.slice(0,", "rows.slice(0,"):
        assert cap not in chart, f"{cap} would silently hide scores"
    # The x-axis is a date now (issue #279), so a row with no parseable release
    # date has no honest position either. That drops nothing today -- all 5,544
    # numeric crawled rows carry a reported_date -- but if it ever does, the
    # count is declared rather than left to be inferred from a total that does
    # not add up.
    #
    # Issue #298 moved that declaration off the axis label, which now names the
    # date and stops, and into the source's (i) provenance note. The rows are
    # still counted and still stated; only where they are said changed.
    assert "undatedCount" not in chart, "the axis label no longer carries the count"
    table = script.split("function catalogSourceTable(source, payload)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "const undated = (payload.rows || []).filter(" in table
    assert "!Number.isFinite(dateValue(row.reported_date))" in table
    assert "carry no position on this axis and are not drawn" in table
    assert "notes.push(" in table


def test_the_crawled_chart_axis_is_release_date_and_says_so():
    # Supersedes test_the_crawled_chart_axis_is_score_not_time (issue #279).
    #
    # That test pinned a deliberate decision from c8e001d: the date exists on
    # every row, but it is the MODEL's announcement date, so the axis stayed
    # score-ordered rather than claim a measurement time it does not have.
    # The concern was right; the remedy threw the date away and drew a sorted
    # list that ramps upward and reads like progress.
    #
    # The axis is now that release date, and the honesty burden moves onto the
    # label: every place the reader can look must say which date this is. A
    # model released in March can be evaluated in August, so nothing here is a
    # measurement timeline, and the assertions below are what stop it drifting
    # into being presented as one.
    script = source("site/assets/app.js")

    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]

    # Positioned by date, so a burst of releases in one month reads as a burst
    # rather than being spread evenly by rank.
    assert "x(dateValue(row.reported_date))" in chart
    assert "const times = plotted.map((row) => dateValue(row.reported_date));" in chart
    # Ordered by date, ties broken by score so same-day releases are stable.
    assert "dateValue(a.reported_date) - dateValue(b.reported_date) || a.value - b.value" in chart

    # The visible axis label, the aria-label and the pinned card all name the
    # date as a release date. Losing any one of them is how a chart starts
    # implying it plots measurements.
    #
    # Issue #298 shortened the VISIBLE label to "model release date": the
    # qualifying clause was reported as noise on the axis itself. The claim it
    # carried is not weakened, it is relocated -- the aria-label and the source
    # provenance note both still spell out that this is not a measurement time,
    # and those assertions are below. What must never happen is the axis
    # calling this a plain "date".
    assert "model release date" in chart
    assert '"Date (model release)"' in script
    # The full statement survives where a reader who asks for it will find it:
    # the chart's own aria-label, and the (i) provenance note for the source.
    assert "is not when the score was measured" in chart
    assert "not when the score was measured" in script

    # `plotted` is in date order, so the last element is the newest model, not
    # the best score. Best follows the normalized higher-is-better contract;
    # source rank is only the deterministic tie break.
    assert "payload.series?.direction || null" in chart
    assert 'const descends = recordDirection === "lower_is_better";' in chart
    assert "row.value > best.value" in chart
    assert "row.rank_in_source_response ?? Number.MAX_SAFE_INTEGER" in chart
    assert "plotted[plotted.length - 1].model_name" not in chart
    assert "const values = plotted.map((row) => row.value).sort((a, b) => a - b);" in chart

    # The record path is explicitly a sequence by model release date, not an
    # evaluation-time trend. Its direction comes from the normalized series
    # contract rather than being reverse-engineered in the renderer.
    assert "payload.series?.direction ||" in chart
    assert "const recordSetters = catalogRecordSetters(plotted, recordDirection);" in chart
    assert "if (hasRecordPath)" in chart
    assert 'class: "score-frontier-line"' in chart


def test_the_crawled_chart_reuses_the_curated_chart_classes():
    # The visual language is not allowed to fork: the crawled figure draws with
    # the exact classes scoreTrackChart draws with (frontier-grid, frontier-tick,
    # frontier-axis-label, score-point/-face/-glyph, score-best-line/-label), so
    # one CSS ruleset governs both and a reader never has to learn a second
    # chart style for a second kind of evidence.
    script = source("site/assets/app.js")

    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]

    for shared_class in [
        "frontier-grid",
        "frontier-tick",
        "frontier-axis-label",
        "score-point-face",
        "score-point-glyph",
        "score-best-line",
        "score-best-label",
    ]:
        assert shared_class in chart, shared_class
    assert "catalog-field" not in chart


def test_the_crawled_chart_is_drawn_per_source_block():
    # One chart per source block, built from that block's own rows. The chart is
    # called from inside catalogSourceTable, which the keyed scores_by_source
    # object already partitions, so there is no path by which two sources' values
    # land on one axis.
    script = source("site/assets/app.js")

    block = script.split("function catalogScoresBlock(shard)", 1)[1].split("\n}\n", 1)[0]

    assert "catalogScoreChart" not in block


def test_every_crawled_score_has_the_curated_charts_pinned_tooltip():
    # A crawled point with only a native <title> was a hover with no keyboard
    # affordance and no click -- a reader landing on a single-point field
    # (e.g. llm-stats-researchclawbench) saw a dot and nothing else. Every
    # crawled point now goes through makeFrontierPointInteractive, the exact
    # system the curated chart's points use: role="button", data-frontier-point,
    # and a pinned card on click. catalogSourceTable mounts its own
    # frontierTooltip() instance beside the chart so that card has somewhere to
    # render (external records hide the curated #frontier-chart entirely).
    script = source("site/assets/app.js")

    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]
    assert "makeFrontierPointInteractive(group" in chart
    assert 'role: "button"' in chart
    assert '"data-frontier-point": ""' in chart
    assert "enableFrontierTouchTargets(svg)" in chart
    # Only fields a crawled row actually carries -- no Instrument, Protocol,
    # Date or Read-from row, which do not exist in this source and would print
    # as "not recorded" filler beside the curated card's real ones.
    assert '...(row.instrument ? [{ label: t("Instrument")' in chart
    assert '...(row.protocol ? [{ label: t("Protocol")' in chart
    assert 't("Date")' not in chart

    table_fn = script.split("function catalogSourceTable(source, payload)", 1)[1].split(
        "\n// Identity siblings", 1
    )[0]
    assert 'element("div", { className: "frontier-chart" }, [chart, frontierTooltip()])' in table_fn


def test_the_pinned_tooltip_positions_against_its_own_parent_not_a_fixed_id():
    # positionFrontierTooltip and the two keyboard-cycle handlers used to read
    # byId("frontier-chart") directly, which only exists for the curated path.
    # Deriving the host from the tooltip's own parentElement is what lets one
    # tooltip implementation serve both the curated chart (mounted inside
    # #frontier-chart) and the crawled chart (mounted inside a lookalike
    # .frontier-chart div under #frontier-catalog).
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

    section = script.split("// --- Catalog detail", 1)[1].split(
        "function renderBenchmarkNavigator", 1
    )[0]
    assert "innerHTML" not in section
    assert "insertAdjacentHTML" not in section


def test_related_records_are_cross_links_never_merges():
    # A variant sibling selects its own shard rather than folding into the
    # current record: two labelled records are a smaller lie than one wrong
    # merge.
    script = source("site/assets/app.js")

    section = script.split("function catalogSiblingsBlock(shard)", 1)[1].split(
        "function catalogBenchmarkDetail", 1
    )[0]
    assert "selectFrontier(sibling.slug)" in section


def test_shard_fetch_failure_keeps_the_selection_and_the_row():
    # Display plan step 7: a failed shard renders an explicit message in the
    # panel and does not clear the selection or throw into the router.
    script = source("site/assets/app.js")

    assert 'fetch(`/data/benchmarks/${slug}.json`, { cache: "no-cache" })' in script
    handler = script.split("loadBenchmarkShard(record.slug).then((shard) =>", 1)[1]
    assert "state.lfrontier !== record.slug" in handler
    assert "Could not load details for this benchmark." in handler


def test_each_chart_owns_its_tooltip_rather_than_sharing_one_id():
    """Issue #261: hover and click looked dead on the curated chart.

    Both charts mounted a tooltip with the same hardcoded id, and
    #frontier-catalog sits above #frontier-chart in index.html. Every
    getElementById therefore resolved to the crawled panel's node, so the
    curated chart's card was written into a hidden element -- the handlers
    fired correctly and painted somewhere invisible.
    """
    script = source("site/assets/app.js")
    html = source("site/index.html")

    # The container order that made a shared id unresolvable is still the
    # order the page ships; the fix must not depend on changing it.
    assert html.index('id="frontier-catalog"') < html.index('id="frontier-chart"')

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
    # External title provenance must leave with the external chart. Without
    # this reset, curated AIME inherited "115 reported scores · LLM Stats" and
    # its own "Scores over time" eyebrow remained hidden.
    assert 'const eyebrow = byId("frontier-eyebrow");' in chrome
    assert "eyebrow.hidden = false;" in chrome
    assert 'const subline = byId("frontier-subline");' in chrome
    assert 'subline.textContent = "";' in chrome
    assert "subline.hidden = true;" in chrome


def test_the_crawled_chart_ticks_label_real_values_not_padded_bounds():
    """Issue #269: AIME 2025 announced an axis from "-0.1" to "1.17".

    The band pads by 18% so points are not drawn on the frame, and the ticks
    printed that padded bound. On a 0.067-to-1.0 field that advertised a
    negative score and a ceiling above every observed value -- two numbers that
    are not in the data and cannot be.
    """
    script = source("site/assets/app.js")
    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]

    # The tick set starts from the real extremes, and issue #298 added
    # intermediate ticks between them so a point's height can be read rather
    # than inferred. Those are generated from `low`/`high` and filtered to
    # `> low && < high`, so the padded bound still cannot reach a label.
    assert "const yTicks = [high, low];" in chart
    assert "for (const value of yTicks)" in chart
    assert "rounded > low && rounded < high" in chart
    assert "for (const value of [band.high, band.low])" not in chart
    assert "band.low" not in chart.split("const yTicks", 1)[1].split("const bestY", 1)[0]
    # The band itself still pads; only the labels changed.
    assert "band = { low: low - pad, high: high + pad }" in chart


def test_benchmark_skyline_leads_the_ranked_list_and_states_its_coverage():
    html = source("site/index.html")
    # The tooltip resolves through .closest(".frontier-chart"), so that class on
    # the mount is a contract, not styling.
    assert 'class="frontier-chart skyline-chart" id="benchmark-skyline-chart"' in html
    assert html.index('id="benchmark-skyline"') < html.index('id="score-ranking-list"')
    assert 'data-i18n="Benchmark Frontier"' in html
    script = source("site/assets/app.js")
    # principle.md: a count in a footnote cannot replace the missing records.
    # Every source participates; incomplete records have inspectable marks.
    assert "scorePopulation(" in script
    assert "skyline-pending-point" in script
    assert "{n} benchmarks · {s} sources" in script
    assert 'id="benchmark-skyline-note"' in html
    assert "lower-is-better percentages become 100 minus the original value" in html


def test_no_surface_calls_a_benchmark_external():
    # design.md, "Show all the data, unify the vocabulary": "external" describes
    # where a record was collected, not what it is, and it invites a reader to
    # discount most of the corpus. The source name carries the provenance.
    script = source("site/assets/app.js")
    html = source("site/index.html")
    assert 't("External benchmark")' not in script
    assert '"External benchmark":' not in script, "no zh entry for a label nothing renders"
    assert "External benchmark" not in html


def test_score_ranking_and_adoption_state_their_distinct_measures():
    html = source("site/index.html")
    # The score ranking is labelled by its own column headers rather than a
    # paragraph of prose, so the two rankings stay distinguishable by structure.
    assert 'data-i18n="Data points"' in html
    assert 'data-i18n="Most documented benchmarks"' in html
    assert html.index('id="score-ranking-list"') < html.index('id="leaderboard-top-list"')
    script = source("site/assets/app.js")
    adoption = script.split("function renderLeaderboardTop(board)", 1)[1].split("\nfunction ", 1)[0]
    assert "board.measures" in adoption
    assert "infoDisclosure(" in adoption


def test_a_benchmark_without_documents_or_scores_uses_its_own_catalog_detail():
    script = source("site/assets/app.js")
    body = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\n// ---", 1)[0]
    assert "state.benchmarkIndex.find(" in body
    assert "renderCatalogBenchmark(board, scored, record);" in body
    assert "card_count" not in body and "scoreRecord(" not in body
    detail = script.split("function renderCatalogBenchmark(", 1)[1].split("\nfunction ", 1)[0]
    assert "picker.prepend(option(record.slug" in detail


def test_leaderboard_keeps_its_rankings_and_saturation_owns_the_workbench():
    """The tab is called Leaderboard and the ranking was the sixth block on it.

    A reader opening it passed a method note, an evidence strip, a findings
    panel, a search box and a 480px chart before reaching the thing the tab is
    named after, which shipped collapsed. The ranking now leads, in five lines
    carrying one measure, and everything about how the number was computed
    stays below it.
    """
    html = source("site/index.html")
    script = source("site/assets/app.js")

    # The order the page reads in. The figure is the primary evidence, so only
    # the title and the five-line ranking may precede it; everything that
    # summarises or interprets follows it.
    #
    # Measured before this order: the chart began at y=1356 on a 1440x900
    # laptop, entirely below the fold, behind ~1180px of KPI cards, a findings
    # accordion and the full 80-row table. It now begins at y=824.
    order = [
        'id="score-ranking-list"',
        'class="leaderboard-top"',
        'id="leaderboard-insights"',
        'id="benchmark-findings"',
        'id="adoption-table"',
        'aria-labelledby="leaderboard-cards-heading"',
    ]
    leaderboard = html.split('id="leaderboard-view"', 1)[1].split('id="saturation-view"', 1)[0]
    saturation = html.split('id="saturation-view"', 1)[1].split('id="trends-view"', 1)[0]
    assert 'class="benchmark-workbench"' not in leaderboard
    assert 'class="benchmark-workbench"' in saturation
    assert 'id="score-ranking-list"' not in saturation
    positions = [html.index(marker) for marker in order]
    assert positions == sorted(positions), (
        "leaderboard blocks are out of order: "
        f"{[m for _, m in sorted(zip(positions, order, strict=True))]}"
    )

    renderer = script.split("function renderLeaderboardTop(board)", 1)[1].split("\nfunction ", 1)[0]
    # Five lines, and the cap is a named constant rather than a literal buried
    # in the slice.
    assert "LEADERBOARD_TOP_LIMIT" in renderer
    assert "const LEADERBOARD_TOP_LIMIT = 5;" in script
    # One measure. No domain, no organization count, no release year, no bar:
    # those are what made the full table a wall rather than a few lines.
    assert 'metricLabel(entry.card_count, "source document")' in renderer
    for absent in ("entry.domain", "organization_count", "entry.released", "adoptionBar("):
        assert absent not in renderer, f"{absent} belongs to the full table, not the summary"

    # The order is read, never recomputed. adoption_rank breaks card-count ties
    # on organization count and then name, so re-sorting here on card_count
    # alone would print a row numbered 05 in position 04.
    assert "entry.rank" in renderer
    assert ".sort(" not in renderer

    # A registry with nothing reported yet says so rather than drawing blanks.
    assert "No source documents record a benchmark yet." in renderer

    # The full ranking is still one click away and still collapsed by default,
    # so #240's contract holds for the bulk material it was written about.
    assert '<details class="trend-panel adoption-table" id="adoption-table">' in html
    assert 'adoption-table" open' not in html
    # Its filters travelled with it.
    assert html.index('id="adoption-table"') < html.index('id="leaderboard-filters"')


def test_issue_256_the_figure_region_carries_no_pipeline_coverage_count():
    """ "26 model cards · 3 scores read from a document" beside a chart.

    The card count is a fact about the world: how many vendors chose to report
    the benchmark. The second number was a fact about this pipeline -- how many
    of those mentions we could read a value out of -- which is noise next to a
    figure, and it is gone along with the helper that produced it.
    """
    script = source("site/assets/app.js")

    assert "chartedScoreLabel" not in script
    navigator = script.split("function renderBenchmarkNavigator(board)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "saturationRows()" in navigator
    assert "score read from a document" not in navigator
    # The keys the helper used are still live for the search rows and the score
    # readout, so removing the helper must not have taken them with it.
    assert '"score read from a document": ' in script


def test_issue_298_a_crawled_record_names_itself_once():
    """The panel said "AIME 2025" twice and "LLM Stats" twice, and looked broken.

    An eyebrow reading "External catalog record", the benchmark name as the
    title, a non-interactive "LLM Stats" chip, and a second heading inside the
    scores block repeating the source and the count. Four elements, two facts.
    There is now one title and one subline, and the picker still mirrors the
    selection because a <select> disagreeing with the panel is a lie about
    state rather than a duplicate.
    """
    script = source("site/assets/app.js")

    external = script.split("function renderCatalogBenchmark(board, scored, record)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # No eyebrow and no badge on this path; both are passed empty and hidden.
    assert 'eyebrow: ""' in external
    assert 'badge: ""' in external
    assert 'eyebrow: t("External catalog record")' not in script
    assert "subline: catalogSubline(record, meta)" in external

    shell = script.split("function renderCatalogShell(", 1)[1].split("\nfunction ", 1)[0]
    # Empty means hidden, not rendered blank.
    assert "eyebrowNode.hidden = !eyebrow;" in shell
    assert "stage.hidden = !badge;" in shell

    # Neither the block nor its per-source renderer carries a heading now.
    scores = script.split("function catalogScoresBlock(shard)", 1)[1].split("\n}\n", 1)[0]
    assert 'element("h3", { text: t("Scores") })' not in scores
    table = script.split("function catalogSourceTable(source, payload)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "catalog-source-heading" not in table
    assert 'element("h4"' not in table
    # One collapsed provenance note follows the figure it explains.
    assert 'byId("frontier-heading-info")' not in table
    assert "infoDisclosure(notes.join" in table
    assert table.index('className: "frontier-chart"') < table.index("infoDisclosure(notes.join")


def test_issue_298_the_crawled_axes_can_be_read_rather_than_inferred():
    """Two y ticks and two x ticks made the reader interpolate every position."""
    script = source("site/assets/app.js")
    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]

    # Intermediate score ticks, bounded by the real observed extremes.
    assert "for (const fraction of [0.25, 0.5, 0.75])" in chart
    assert "rounded > low && rounded < high" in chart
    # Quarterly date ticks, strictly inside the observed span and never
    # colliding with the endpoint labels that carry the real first and last.
    assert "cursor.setUTCMonth(cursor.getUTCMonth() + 3);" in chart
    assert "cursor.getTime() < lastTime" in chart
    assert "quarterGap" in chart

    # The best-on-record annotation reads as a sentence and sits on its line.
    assert 't("Best reported score:")' in chart
    # Rounded to two decimals via `shown`, which also applies the axis's display
    # factor so the annotation cannot disagree with the ticks beside it.
    assert "shown(bestValue)" in chart
    assert "const shown = (value) => Number((value * factor).toFixed(2));" in chart
    assert '"text-anchor": "start", class: "score-best-label"' in chart


def test_issue_298_the_sidebar_row_leads_with_the_benchmark_name():
    script = source("site/assets/app.js")
    row = script.split("function benchmarkResultRow(record", 1)[1].split("\nfunction ", 1)[0]
    assert 'className: "benchmark-result-name"' in row
    assert "record.domain" not in row
    assert "record.released" not in row
    matcher = script.split("function searchBenchmarkIndex(", 1)[1].split("\nfunction ", 1)[0]
    assert "record.categories" in matcher


def test_issue_288_the_charts_draw_a_running_best_not_an_invented_cost_axis():
    """Asked for a Pareto frontier "just like harbor-index.org".

    Harbor plots cost against pass rate. This corpus records no cost and no
    latency for any score: a curated observation carries value, model,
    organization, reported_at, instrument and protocol; a crawled row carries
    value, model_name and reported_date. Drawing Harbor's chart here would mean
    inventing the x-axis.

    What is drawable is the same idea on the axes these charts already have --
    the set of points nothing else beats, which on one score axis over time is
    the running maximum.
    """
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    # The browser is geometry-only. Direction, same-date collapse, strict
    # improvement and all-observation scope are normalized in Python, so the
    # final value and the readout cannot be calculated from different subsets.
    curated = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "record.historical_best_frontier?.points || []" in curated
    assert "runningBestSteps" not in curated

    # The visual links one actual record setter directly to the next. It does
    # not invent horizontal holds, vertical jumps, or an extension beyond the
    # final report, and one point alone cannot produce a line.
    path = script.split("function recordSetterPath(points, xValue, yValue)", 1)[1].split(
        "\n}\n", 1
    )[0]
    assert 'if (points.length < 2) return "";' in path
    assert '${index ? "L" : "M"}' in path
    assert "parts.push(`H " not in path
    assert "parts.push(`V " not in path
    assert "endX" not in path

    # The historical best is benchmark-wide as the label promises. Protocol
    # remains in the tooltip and in the separate comparable-series readout; it
    # cannot choose a lower subgroup frontier behind the reader's back.
    assert script.count('class: "score-frontier-line"') == 2
    assert ".score-frontier-line {" in styles
    assert "frontierMarks.has(observation.observation_id)" in curated
    assert "observation.protocol" in curated

    # The crawled layer now draws successive reported highs. Direction is a
    # normalized LLM Stats property, not a browser inference.
    crawled = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]
    assert "payload.series?.direction" in crawled
    assert "payload.series?.direction || null" in crawled
    assert "sourceRankDirection" not in script
    assert "catalogRecordSetters(plotted, recordDirection)" in crawled
    assert "score-frontier-line" in crawled
    assert "runningBestSteps" not in crawled

    # Neither renderer connects every model into a trend. Both pass only strict
    # record setters to the direct-path geometry.
    assert "polyline" not in curated
    assert "recordSetterPath(" in curated
    assert "recordSetterPath(" in crawled


def test_the_ranking_expands_and_the_intro_condensed_into_one_toggle():
    """Four elements said something about one ranking, above the figure.

    An eyebrow ("Model Card Adoption Rank"), the h1, the deck, and a "How to
    read this evidence" note filled the space where the figure should have
    been. They are one (i) beside the ranking heading now. The h1 stays: it is
    the view's accessible name via aria-labelledby.
    """
    html = source("site/index.html")
    script = source("site/assets/app.js")

    for gone in (
        'data-i18n="Model Card Adoption Rank"',
        'class="method-note"',
        'data-i18n="How to read this evidence"',
    ):
        assert gone not in html, f"{gone} still sits above the figure"
    assert 'id="leaderboard-heading"' in html
    assert 'aria-labelledby="leaderboard-heading"' in html

    # The deck is still written and still published data -- read rather than
    # displayed, so a screen reader gets it with the heading.
    assert 'id="leaderboard-measures"' in html
    assert "visually-hidden" in html.split('id="leaderboard-measures"', 1)[0][-200:]
    renderer = script.split("function renderLeaderboardTop(board)", 1)[1].split("\nfunction ", 1)[0]
    assert "board.measures" in renderer
    # The caveat travels with the payload that produced the order rather than
    # being restated in the browser, where it could drift from it.
    assert "vendor attention, not benchmark quality" not in script

    # Five lines by default, all 79 on request, and back again.
    assert 'id="leaderboard-top-more"' in html
    sliced = "state.leaderboardTopExpanded ? ranked : ranked.slice(0, LEADERBOARD_TOP_LIMIT)"
    assert sliced in renderer
    assert "more.hidden = ranked.length <= LEADERBOARD_TOP_LIMIT;" in renderer
    toggle = script.split('byId("leaderboard-top-more").addEventListener("click"', 1)[1].split(
        "});", 1
    )[0]
    assert "state.leaderboardTopExpanded = !state.leaderboardTopExpanded;" in toggle


def test_an_unresolved_permalink_reports_the_missing_record_without_substitution():
    script = source("site/assets/app.js")
    dispatch = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\n// ---", 1)[0]
    unresolved = dispatch.split("if (record)", 1)[1].split("return;", 1)[1]
    assert "This benchmark is not in the loaded catalog." in unresolved
    assert "heading: state.lfrontier" in unresolved
    assert "state.lfrontier =" not in unresolved
    assert "writeUrl(" not in unresolved


def test_document_ranking_keeps_a_compact_heading_and_its_note_below():
    """Show the ranked evidence first, with its explanation below the figure."""
    styles = source("site/assets/styles.css")
    html = source("site/index.html")

    rule = styles.split(".leaderboard-top-heading h2 {", 1)[1].split("}", 1)[0]
    assert "font-size: clamp(1.25rem, 2vw, 1.5rem);" in rule
    assert "margin: 0;" in rule
    # The global h1 caps its width at 800px; the heading is a flex item, so that
    # cap is what let the title's box stretch and strand the (i). Reset it here
    # so the title is content-sized and the toggle anchors to its last glyph.
    assert "max-width: none;" in rule
    # The heading is an <h2>: the page keeps a single <h1> ("Today's radar"),
    # so crawlers see one document outline instead of four competing titles.

    heading = styles.split(".leaderboard-top-heading {", 1)[1].split("}", 1)[0]
    assert "flex-wrap: wrap;" in heading
    assert "align-items: center;" in heading

    assert html.index('id="leaderboard-top-list"') < html.index('id="leaderboard-top-info"')


def test_chart_legends_and_secondary_notes_follow_their_figures():
    html = source("site/index.html")
    styles = source("site/assets/styles.css")
    for figure, legend in (
        ("benchmark-skyline-chart", "benchmark-skyline-legend"),
        ("frontier-chart", "frontier-legend"),
        ("trend-chart", "trend-legend"),
    ):
        assert html.index(f'id="{figure}"') < html.index(f'id="{legend}"')
    note = html.split('id="benchmark-skyline-method"', 1)[1].split("</details>", 1)[0]
    assert "open" not in note.split(">", 1)[0]
    for fact in ("count", "note", "sources", "coverage", "pareto"):
        assert f'id="benchmark-skyline-{fact}"' in note
    assert ".skyline-method:not([open]) > .skyline-method-body { display: none; }" in styles
    closed = styles.split(".info-disclosure:not([open]) > .info-disclosure-body {", 1)[1].split(
        "}", 1
    )[0]
    assert "display: none;" in closed
    assert ".info-disclosure:focus-within > .info-disclosure-body" not in styles


def test_document_ranking_expansion_keeps_the_common_corpus():
    script = source("site/assets/app.js")
    action = script.split('byId("leaderboard-top-more").addEventListener', 1)[1].split(
        "\n  });", 1
    )[0]
    assert "catalogDocumentBoard()" in action
    assert "model_card_leaderboard" not in action


def test_issue_341_a_fractional_series_is_drawn_on_a_zero_to_hundred_axis():
    """Terminal-Bench 2.0 announced its best model as "0.83".

    Every write-up a reader arrives from quotes that same result as a
    percentage, so reading the axis meant multiplying by 100 on every tick.

    The remedy is a change of units and nothing more. Multiplying a whole
    series by a constant preserves every ordering and every ratio in it and
    asserts nothing about a ceiling, which is the distinction `catalog`
    cares about: it refuses to emit a `display_scale` because a declared maximum
    is not a bound, and that refusal still stands. So there is no bar, no `%`
    and no "out of 100" here -- an Elo series stays in Elo.
    """
    script = source("site/assets/app.js")
    helper = script.split("function catalogDisplayFactor(series)", 1)[1].split("\nfunction ", 1)[0]

    # Scale is now generated once from all numeric rows, including undated ones.
    # Threshold and contradicted-bound cases are exercised in test_score_filters.
    assert "series?.score_summary?.display_multiplier" in helper
    chart = script.split("function catalogPlottedRows(payload)", 1)[1].split(
        "\nfunction catalogSourceTable", 1
    )[0]
    # Display only. Geometry still takes raw values, so applying the factor
    # cannot move a single point.
    assert "const factor = catalogDisplayFactor(payload.series);" in chart
    assert "const scoreY = (value) => {" in chart
    assert "scoreY(shown(" not in chart
    assert "shown(bestValue)" in chart
    # No claim of a maximum anywhere on the figure.
    for claim in ('"%"', "out of 100", "percent"):
        assert claim not in chart

    table = script.split("function catalogSourceTable(source, payload)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # Stated where the reader can see it, beside the other provenance notes.
    assert "catalogDisplayFactor(series) !== 1" in table
    assert "multiplies them by 100" in table
    # And the number the source actually published stays one click away.
    assert 't("Score as reported"), value: String(row.raw_value ?? row.value)' in chart


def test_issue_341_terminal_bench_2_qualifies_and_an_elo_board_does_not():
    """The rule has to hold against the real crawled shards, not just in the abstract."""

    def factor(slug: str) -> int:
        shard = json.loads(Path(f"site/data/benchmarks/{slug}.json").read_text(encoding="utf-8"))
        payload = shard["scores_by_source"]["llm_stats"]
        series = payload["series"]
        values = [
            row["value"]
            for row in payload["rows"]
            if isinstance(row["value"], (int, float)) and row["reported_date"]
        ]
        if not values or series["max_score_contradicted"]:
            return 1
        declared = series["declared_max"]
        if declared is not None and declared > 1:
            return 1
        return 100 if all(0 <= value <= 1 for value in values) else 1

    # The benchmark from the report: every score between 0 and 1.
    assert factor("llm-stats-terminal-bench-2") == 100
    # An Elo board declares 3000 and carries four-figure values. Untouched.
    assert factor("llm-stats-aa-briefcase") == 1
