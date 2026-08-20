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

    row = script.split("function benchmarkResultRow(record", 1)[1].split(
        "function renderBenchmarkSearch", 1
    )[0]
    assert "selectFrontier(record.slug)" in row
    assert "renderAdoptionFrontier(board)" in row
    # Issue #245 added a `navigate` path for rows rendered outside the
    # leaderboard, where updating the panel in place would look like the click
    # did nothing. It must not replace the in-place update the panel relies on.
    assert 'setView("leaderboard")' in row


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
    # A value that did not parse into a number has no position on an axis, so it
    # is dropped, and it is dropped by testing the value rather than by a cap.
    assert 'typeof row.value === "number" && Number.isFinite(row.value)' in chart
    # No cap. The bare .slice() copies before sorting so the source array is
    # not mutated; every .slice(0, N) is ISO-date truncation, not a row limit.
    # A truncating slice over the rows would silently hide scores.
    #
    # Counting instances is not the guarantee -- issue #298 added a second
    # date truncation for the quarterly axis ticks, which drops nothing. The
    # guarantee is that each one slices a date string to 10 chars, so any
    # slice with a different length, or one applied to the rows, fails here.
    assert ".slice()" in chart
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
    table = script.split("function externalSourceTable(source, payload)", 1)[1].split(
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

    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
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
    # the best score. Reading the best off the end of the array is the specific
    # bug this reordering would introduce if the two were conflated.
    assert "const bestRow = plotted.reduce(" in chart
    assert "plotted[plotted.length - 1].model_name" not in chart
    assert "const values = plotted.map((row) => row.value).sort((a, b) => a - b);" in chart

    # And still no segment between points: a line would assert a trajectory
    # through models that were never a series, which is the claim the curated
    # chart earns with a protocol and this one does not.
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


def test_a_benchmark_with_no_adopters_answers_for_itself():
    # Issue #287: ?lfrontier=rsi_bench drew AutomationBench's chart. `adopted`
    # is gated on card_count > 0, so a benchmark recorded before any model card
    # reports it was filtered out before the unscored guard could see it. It
    # matched no branch, fell through to the default entry, and the page
    # printed another benchmark's track, its 31.8% best-on-record figure and
    # its model points under a URL still reading rsi_bench, saying nothing.
    script = source("site/assets/app.js")
    body = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\nfunction ", 1)[0]

    # Resolved against every registry entry, not just the adopted subset.
    guard = body.split("const unscoredEntry", 1)[1].split("if (unscoredEntry)", 1)[0]
    assert "(board.entries || []).find(" in guard
    assert "adopted.find(" not in guard

    # Zero adopters and "adopters but no readable score" are different answers,
    # and a reader chasing a brand-new benchmark wants to know which one it is.
    assert "No model card in this registry reports this benchmark yet" in body
    assert "unscoredEntry.card_count" in body

    # The picker lists only scored benchmarks, so an unscored selection matches
    # no option and the browser shows the first one instead: a <select> reading
    # AA-LCR beside a panel headed RSI-Bench is lying about the state.
    assert "prependOption" in body


def test_issue_256_the_ranking_leads_the_page_it_names():
    """The tab is called Leaderboard and the ranking was the sixth block on it.

    A reader opening it passed a method note, an evidence strip, a findings
    panel, a search box and a 480px chart before reaching the thing the tab is
    named after, which shipped collapsed. The ranking now leads, in five lines
    carrying one measure, and everything about how the number was computed
    stays below it.
    """
    html = source("site/index.html")
    script = source("site/assets/app.js")

    # Above the workbench, which is where the search box and the chart live.
    assert html.index('class="leaderboard-top"') < html.index('class="benchmark-workbench"')
    # And above the full table, which is now nested inside it as the expandable.
    assert html.index('class="leaderboard-top"') < html.index('id="adoption-table"')
    assert html.index('id="adoption-table"') < html.index('class="benchmark-workbench"')

    renderer = script.split("function renderLeaderboardTop(board)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # Five lines, and the cap is a named constant rather than a literal buried
    # in the slice.
    assert "LEADERBOARD_TOP_LIMIT" in renderer
    assert "const LEADERBOARD_TOP_LIMIT = 5;" in script
    # One measure. No domain, no organization count, no release year, no bar:
    # those are what made the full table a wall rather than a few lines.
    assert 'metricLabel(entry.card_count, "model card")' in renderer
    for absent in ("entry.domain", "organization_count", "entry.released", "adoptionBar("):
        assert absent not in renderer, f"{absent} belongs to the full table, not the summary"

    # The order is read, never recomputed. adoption_rank breaks card-count ties
    # on organization count and then name, so re-sorting here on card_count
    # alone would print a row numbered 05 in position 04.
    assert "entry.rank" in renderer
    assert ".sort(" not in renderer

    # A registry with nothing reported yet says so rather than drawing blanks.
    assert "No model card in this registry reports a benchmark yet." in renderer

    # The full ranking is still one click away and still collapsed by default,
    # so #240's contract holds for the bulk material it was written about.
    assert '<details class="trend-panel adoption-table" id="adoption-table">' in html
    assert 'adoption-table" open' not in html
    # Its filters travelled with it.
    assert html.index('id="adoption-table"') < html.index('id="leaderboard-filters"')


def test_issue_256_the_figure_region_carries_no_pipeline_coverage_count():
    """"26 model cards · 3 scores read from a document" beside a chart.

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
    assert 'metricLabel(entry.card_count, "model card")' in navigator
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
    html = source("site/index.html")
    script = source("site/assets/app.js")

    external = script.split("function renderExternalBenchmark(board, scored, record)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # No eyebrow and no badge on this path; both are passed empty and hidden.
    assert 'eyebrow: ""' in external
    assert 'badge: ""' in external
    assert 'eyebrow: t("External catalog record")' not in script
    assert "subline: externalSubline(record, meta)" in external

    shell = script.split("function renderExternalShell(", 1)[1].split("\nfunction ", 1)[0]
    # Empty means hidden, not rendered blank.
    assert "eyebrowNode.hidden = !eyebrow;" in shell
    assert "stage.hidden = !badge;" in shell

    # Neither the block nor its per-source renderer carries a heading now.
    scores = script.split("function externalScoresBlock(shard)", 1)[1].split("\n}\n", 1)[0]
    assert 'element("h3", { text: t("Scores") })' not in scores
    table = script.split("function externalSourceTable(source, payload)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "external-source-heading" not in table
    assert 'element("h4"' not in table
    # But the provenance note survives, moved to the (i) beside the title.
    assert 'byId("frontier-heading-info")' in table
    assert "infoDisclosure(notes.join" in table
    assert 'id="frontier-heading-info"' in html
    # The (i) sits with the title rather than in a separate block.
    assert html.index('id="frontier-heading"') < html.index('id="frontier-heading-info"')
    assert html.index('id="frontier-heading-info"') < html.index('id="frontier-benchmark"')


def test_issue_298_the_crawled_axes_can_be_read_rather_than_inferred():
    """Two y ticks and two x ticks made the reader interpolate every position."""
    script = source("site/assets/app.js")
    chart = script.split("function externalScoreChart(source, payload)", 1)[1].split(
        "\nfunction externalSourceTable", 1
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
    assert "bestValue.toFixed(2)" in chart
    assert '"text-anchor": "start", class: "score-best-label"' in chart


def test_issue_298_the_sidebar_row_leads_with_the_benchmark_name():
    """Every row printed domain, year, a source chip and a score count.

    Four grey fields per row, repeated down the list, so finding a name meant
    reading past them. The count stays because it is the measure this registry
    is built on. What the search MATCHES is unchanged -- domain, publisher and
    modality are still queried, they are simply not printed.
    """
    script = source("site/assets/app.js")
    row = script.split("function curatedResultRow(entry, { navigate = false, inert = false } = {})", 1)[1].split(
        "\nfunction ", 1
    )[0]

    assert 'metricLabel(entry.card_count, "model", "models")' in row
    for absent in ("benchmark-result-meta", "Curated registry", "benchmark-result-scores"):
        assert absent not in row, f"{absent} is the grey wall this removed"
    assert "entry.domain" not in row
    assert "entry.released" not in row

    # Matching is untouched: the fields left the display, not the query.
    matcher = script.split("function searchCuratedEntries(", 1)[1].split("\nfunction ", 1)[0]
    assert "domain" in matcher


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

    steps = script.split("function runningBestSteps(points", 1)[1].split("\n}\n", 1)[0]
    # Better is not always larger, so the frontier follows the metric rather
    # than the number, or it would trace the worst result on a lower-is-better
    # benchmark.
    assert "descends ? point.value < best : point.value > best" in steps
    # A line through one date asserts nothing, so it is not drawn.
    assert "if (dated.length < 2) return [];" in steps
    assert "if (new Set(dated.map((point) => point.time)).size < 2) return [];" in steps

    # Stepped, never diagonal: a slope would imply the score moved continuously
    # between two reports, which is interpolation this corpus cannot support.
    path = script.split("function runningBestPath(steps, x, y, endX)", 1)[1].split("\n}\n", 1)[0]
    assert '`H ${x(step.time)}`' in path
    assert '`V ${y(step.value)}`' in path
    assert "L " not in path

    # Both charts draw it, and the curated one passes the direction flag.
    assert script.count("class: \"score-frontier-line\"") == 2
    assert "{ descends: scoreDescends }" in script
    assert ".score-frontier-line {" in styles

    # And it did not reintroduce the join the evidence rules forbid: the
    # running best says "nothing had beaten this yet", never "these points are
    # a series".
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "polyline" not in chart
