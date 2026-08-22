"""The rendered half of issue #91: the score track and the stated findings.

Asserts on the shipped site sources the way `test_site.py` and
`test_leaderboard_workbench.py` do. These are guarantees about what a reader
sees, and several of them are honesty guarantees rather than layout ones: the
join rule has to hold in the drawing code, and a flat score tail has to be
labelled as a reading gap rather than left to be read as a plateau.
"""

from pathlib import Path

from benchmark_radar.benchmark_scores import DEFAULT_SCORES_PATH, build_score_progression
from benchmark_radar.model_cards import DEFAULT_REGISTRY_PATH, load_registry


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_the_score_track_occupies_the_whole_plot():
    # The panel used to lead with an adoption staircase and give the scores a
    # short strip underneath. The staircase answered a different question, so the
    # score band now starts at the top margin and takes the height the staircase,
    # the card rug and the inter-band gaps vacated. The y-axis is zoomed to the
    # observed range, so that height is vertical resolution on the one reading a
    # reader must not misjudge.
    script = source("site/assets/app.js")
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]

    assert "const scoreTop = margin.top;" in chart
    assert "const scoreHeight = 480;" in chart
    assert "const height = margin.top + scoreHeight + margin.bottom;" in chart
    assert "scoreY(observation.value)" in chart
    assert "x(observation.reported_at)" in chart


def test_the_score_layer_draws_no_connecting_line_at_all():
    # A shared instrument and protocol makes two numbers comparable; it does not
    # make them a series, and a segment asserts the second. On shipped GPQA
    # Diamond the old join rule connected DeepSeek-V4-Pro (90.1) to
    # DeepSeek-V4-Flash (88.1) and drew a decline out of a smaller model, and
    # connected two vendors' unrelated models into an apparent trajectory.
    # Restricting which pairs may join does not fix that: the defect is in the
    # segment. Comparability is still computed, and still stated in prose by the
    # paired comparison readout.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]

    assert "polyline" not in chart
    # A <path> draws the same segment a <polyline> would, so the ban names the
    # shape rather than one element. The running-best line is stepped (H/V
    # only): "nothing had beaten this yet", not a trajectory between points.
    for command in (" L ", "`L ${"):
        assert command not in chart, "a diagonal path segment is a trajectory claim"
    assert "if (!series.connectable) continue;" not in chart
    assert "score-line" not in script
    assert "score-line" not in styles
    # The one horizontal rule that remains is the best-on-record reference,
    # which is a fact about the corpus to date rather than a join between points.
    assert "const bestY = scoreY(record.saturation.best_value);" in chart


def test_comparability_is_stated_in_prose_rather_than_drawn():
    # A single-vendor comparable run used to be drawn as a dashed line, weaker
    # evidence than a solid cross-vendor one. Both are gone. The distinction
    # survives where it can carry its own caveat: the readout under the chart.
    script = source("site/assets/app.js")

    assert (
        "single_organization"
        not in script.split("function scoreTrackChart(", 1)[1].split(
            "\nfunction clearAdoptionFrontier", 1
        )[0]
    )
    # The evidence box is untouched: it names what a pair supports and what it
    # does not, which is the honesty a line could never carry. Its label and
    # both sentences come from the score record, so the readout renders them
    # rather than restating them here.
    readout = script.split("function scoreReadout(entry, record)", 1)[1].split("\nfunction ", 1)[0]
    assert 'text: t("Supports: ")' in readout
    assert 'text: t("Does not support: ")' in readout
    assert "evidence.does_not_support" in readout
    # And the comparable-run count is still surfaced, so comparability is
    # reported as a number even though it is not drawn as a line.
    assert '"comparable run"' in readout


def test_a_third_party_citation_is_marked_on_the_chart():
    # A publisher repeating a competitor's figure must not read as a first-party
    # report; it is weaker evidence and the chart has to say so.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    assert "score-point-third-party" in script
    assert "observation.reported_by" in script
    assert "score-point-citation-ring" in script
    assert ".score-point-citation-ring" in styles


def test_score_points_carry_recognizable_model_family_marks():
    """Issue #195: saturation points identify models before interaction."""
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]

    # The family marks moved to glyphs.js so the logo audit page can import the
    # same table the chart draws from (issue #261).
    glyphs = source("site/assets/glyphs.js")
    for family in ("Claude", "Gemini", "Grok"):
        assert f"{family}: [" in glyphs
    assert "modelGlyph(" in chart
    assert "observation.model" in chart
    assert 'r: 9,\n          class: "score-point-face"' in chart
    assert ".score-point-glyph" in styles
    assert "stroke: #6ea8dc" in styles.split(".score-point-face", 1)[1][:120]


def test_the_reading_gap_is_labelled_rather_than_drawn_through():
    # Scores in this corpus stop well before mentions do. An unmarked flat tail
    # invites "saturated" as the explanation when "nothing newer could be read"
    # is the actual one.
    script = source("site/assets/app.js")

    assert "no score read from a document in this window" in script
    assert "score-gap-line" in script


def test_the_reading_gap_encodes_no_score_value():
    # Codex P1. An earlier version drew this span at the best-on-record height,
    # asserting that value at a date where nothing was recorded. On shipped data
    # the best often predates the last observation (AIME, SWE-bench Verified,
    # MMLU-Redux, IFEval), so it manufactured a flat tail out of missing data --
    # the exact failure the marker exists to prevent. The span must be purely
    # horizontal on the plot floor, carrying no y-value.
    script = source("site/assets/app.js")
    gap = script.split("const lastScoreX = x(record.last_reported_at);", 1)[1].split(
        "no score read from a document in this window", 1
    )[0]

    assert "scoreY(" not in gap, "the gap span must not be positioned by any score value"
    assert "const floorY = scoreTop + scoreHeight;" in gap


def test_shipped_data_has_benchmarks_whose_best_predates_their_last_score():
    # Guards the premise of the test above. If curation ever made every best the
    # newest observation, the P1 geometry would stop being reachable and that test
    # would silently become vacuous rather than protective.
    progression = build_score_progression(DEFAULT_SCORES_PATH, load_registry(DEFAULT_REGISTRY_PATH))
    stale_best = [
        benchmark_id
        for benchmark_id, record in progression["benchmarks"].items()
        if record["saturation"]["best_reported_at"] < record["last_reported_at"]
    ]
    assert stale_best, "expected at least one benchmark whose best is not its newest reading"


def test_better_is_up_even_when_lower_is_the_better_score():
    # Codex P2. `direction` exists in the schema so an error-rate metric does not
    # render its improvements as a downward slope. The renderer has to consult it.
    script = source("site/assets/app.js")
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]

    assert 'record.direction === "lower_is_better"' in chart
    assert "scoreDescends ? 1 - fraction : fraction" in chart


def test_lower_is_better_headroom_is_described_against_zero():
    # Codex P2. The backend measures headroom to zero for an inverted metric, so
    # naming `bound` in both cases would print "10 points to the 100-point bound"
    # for a score of 10.
    script = source("site/assets/app.js")

    assert "points to zero, the floor of this metric" in script


def test_only_a_benchmark_with_a_readable_score_can_be_selected():
    # The panel is the score track now, so a benchmark with no readable value has
    # nothing to draw. It is filtered out of the picker rather than opening an
    # empty chart, which would read as "scores went to zero here". 20 of the 79
    # adopted registry benchmarks take this path.
    script = source("site/assets/app.js")
    render = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\nfunction ", 1)[0]

    assert "const scored = adopted.filter((entry) => scoreRecord(entry.benchmark_id));" in render
    # The <select>, the resolution of a ?lfrontier= permalink, and the empty
    # state all read from `scored`, so none of them can surface an unscored one.
    assert "renderFrontierPicker(scored, state.lfrontier);" in render
    # And the picker itself applies the same rule to the crawled layer.
    picker = script.split("function frontierPickerGroups(scored)", 1)[1].split("\n}", 1)[0]
    assert "record.score_count > 0" in picker
    assert "scored.find((candidate) => candidate.benchmark_id === state.lfrontier)" in render
    assert "if (!scored.length || !defaultEntry)" in render
    # The default selection is drawn from the same set.
    default_entry = script.split("function frontierDefaultEntry(board)", 1)[1].split("\n}", 1)[0]
    assert "scoreRecord(entry.benchmark_id)" in default_entry


def test_the_picker_and_the_search_both_cover_both_layers():
    # The two layers used to have opposite blind spots: the <select> held only
    # the 59 curated benchmarks, while the search box read only the crawled
    # index, so typing "GPQA" surfaced crawled rows but not the curated GPQA
    # Diamond record the panel actually charts. Both entry points now reach
    # both layers.
    script = source("site/assets/app.js")

    picker = script.split("function frontierPickerGroups(scored)", 1)[1].split("\n}", 1)[0]
    assert 't("Curated registry")' in picker
    assert "state.benchmarkIndex || []" in picker
    # Grouped, never interleaved: only the curated layer carries an instrument,
    # a protocol and a publication date, so a reader must be able to tell which
    # layer a row is from before selecting it.
    assert '"optgroup"' in script
    assert "externalSourceMeta(source).name" in picker

    render = script.split("function renderBenchmarkSearch()", 1)[1].split("\nfunction ", 1)[0]
    assert "searchCuratedEntries(board, state.benchmarkQuery)" in render
    assert "searchBenchmarkIndex(records, state.benchmarkQuery)" in render
    # Curated results come first, and the cap spans both lists so a common name
    # cannot push every curated hit off the end.
    assert render.index("shownCurated") < render.index("shownExternal")
    assert "BENCHMARK_SEARCH_LIMIT - shownCurated.length" in render


def test_curated_search_matches_aliases_and_ranks_the_exact_one_first():
    # The registry records aliases so a reader need not know the canonical
    # spelling. It also records `HLEAutomationBench`, which made AutomationBench
    # a prefix hit for "HLE" and, ranked on entry-name length, beat the record
    # literally named HLE. The matched alias is what gets ranked.
    script = source("site/assets/app.js")
    search = script.split("function searchCuratedEntries(board, query", 1)[1].split("\n}", 1)[0]

    assert "entry.aliases || []" in search
    assert "name === needle ? 0 : name.startsWith(needle) ? 1 : 2" in search
    # Only scored benchmarks are offered, same rule as the picker.
    # The picker drives a chart, so it still skips entries with no score
    # record. Issue #245 added an opt-in for callers asking only "is this
    # tracked?"; the default must stay off so this panel is unaffected.
    assert "if (!includeUnscored && !scoreRecord(entry.benchmark_id)) continue;" in search
    assert "includeUnscored = false" in search


def test_search_still_works_when_the_crawled_index_is_unavailable():
    # The curated layer lives in the dashboard payload, which is already loaded,
    # so a failed or pending index fetch must degrade only the crawled half
    # rather than blanking search entirely.
    script = source("site/assets/app.js")
    render = script.split("function renderBenchmarkSearch()", 1)[1].split("\nfunction ", 1)[0]

    assert "if (!records && !curatedCount)" in render
    assert "records\n    ? searchBenchmarkIndex(records, state.benchmarkQuery)\n    : []" in render


def test_the_navigator_is_a_tool_region_not_a_content_section():
    # The examples were a titled block with an eyebrow, a heading, a paragraph
    # and two computed subheadings. That outranked the search box it existed to
    # support, and the paragraph restated the heading. The panel is now a field,
    # its reach line, its results, and a quiet ranked list.
    html = source("site/index.html")
    navigator = html.split('class="benchmark-navigator"', 1)[1].split("</aside>", 1)[0]

    for gone in (
        'data-i18n="Famous benchmarks"',
        'data-i18n="Worked examples"',
        'data-i18n="leaderboard.navigator.note"',
        "benchmark-shortlist-section",
    ):
        assert gone not in navigator, f"{gone} still occupies the navigator"
    # The search label is the only heading, so it is the panel's one anchor.
    assert navigator.count("<h2") == 1
    assert 'data-i18n="Search every benchmark"' in navigator
    # And the examples label is not `.eyebrow`, whose accent blue would plant a
    # second anchor competing with the field.
    assert 'class="eyebrow"' not in navigator
    assert 'class="benchmark-example-lead"' in navigator

    order = [
        navigator.index('id="benchmark-search-input"'),
        navigator.index('id="benchmark-search-status"'),
        navigator.index('id="benchmark-search-results"'),
        navigator.index('id="benchmark-shortlist"'),
    ]
    assert order == sorted(order), "field, reach line, results, then examples"


def test_the_search_field_carries_the_panel_weight_through_affordance():
    # The importance of this panel is expressed by the control, not by a large
    # heading or a paragraph of prose. The label stays small; the field gets the
    # emphasis, and the reach line drops a size and a step of contrast so it
    # reads as a footnote to the field rather than as a headline.
    styles = source("site/assets/styles.css")

    field = styles.split(".benchmark-search-input {", 1)[1].split("}", 1)[0]
    assert "border: 2px solid var(--ink)" in field
    assert "background: white" in field

    label = styles.split(".benchmark-search-label {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.78rem" in label, "the label must not grow"

    status = styles.split(".benchmark-search-status {", 1)[1].split("}", 1)[0]
    assert "font-size: 0.7rem" in status
    assert "opacity: 0.75" in status


def test_the_examples_are_ranked_by_how_many_cards_report_them():
    # No editorial list and no computed subheadings: "most reported" is both the
    # rank and the reason a name is worth trying, which is the one reading this
    # registry exists to make. Curated only, because `card_count` is a curated
    # fact; the crawled layer is reached from the field and the picker instead.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    navigator = script.split("function renderBenchmarkNavigator(board)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "b.card_count - a.card_count || a.name.localeCompare(b.name)" in navigator
    assert "entry.card_count > 0 && scoreRecord(entry.benchmark_id)" in navigator
    assert "BENCHMARK_EXAMPLE_LIMIT" in navigator
    assert 'metricLabel(entry.card_count, "model card")' in navigator
    # Every example is on the page: an inner scroller hid ranks 8-20 behind a
    # scrollbar that read as the end of the list. The sticky aside is what gets
    # bounded to the viewport instead.
    shortlist = styles.split(".benchmark-shortlist {", 1)[1].split("}", 1)[0]
    assert "max-height" not in shortlist
    aside = styles.split(".benchmark-navigator {", 1)[1].split("}", 1)[0]
    assert "max-height: calc(100vh - 2rem)" in aside
    assert "overflow-y: auto" in aside


def test_the_navigator_still_starts_the_crawled_index_fetch():
    # Regression guard. `initBenchmarkSearch` binds the input and kicks off the
    # index fetch, and it lived at the end of the shortlist renderer. Rewriting
    # that renderer dropped it, so the index was never requested: search fell
    # back to the curated layer alone and the reach line read "59 benchmarks,
    # 1 source" instead of "1,207 benchmarks, 3 sources".
    script = source("site/assets/app.js")
    navigator = script.split("function renderBenchmarkNavigator(board)", 1)[1].split(
        "\nfunction ", 1
    )[0]

    assert "initBenchmarkSearch();" in navigator
    assert navigator.index("initBenchmarkSearch();") < navigator.index("renderBenchmarkSearch();")


def test_the_search_reach_line_counts_only_what_it_can_return():
    # A count that advertised records the box cannot return would be a boast
    # rather than a statement of reach, so it is derived from the loaded layers
    # and drops when the crawled index fails. "Sources" counts those layers, not
    # the radar's discovery connectors, which contribute no benchmark here.
    script = source("site/assets/app.js")
    render = script.split("function renderBenchmarkSearch()", 1)[1].split("\nfunction ", 1)[0]

    assert 't("{n} benchmarks")' in render
    assert 'metricLabel(sources.size, "source")' in render
    assert "const sources = new Set((records || []).map((record) => record.source));" in render
    assert 'if (curatedCount) sources.add("curated");' in render
    # No literal totals anywhere: the numbers are computed, never written down.
    assert "4,861" not in script and "4861" not in script


def test_search_matches_the_fields_the_placeholder_promises():
    # The box says "benchmarks, tasks, domains". Name and alias cover the first,
    # and `domain` covers the rest: the task shape rendered in the panel is
    # selected by domain, so matching it is what makes "agent" or "science"
    # return a set instead of nothing. The crawled catalog carries no domain, so
    # publisher and modality are the equivalent there.
    script = source("site/assets/app.js")

    curated = script.split("function searchCuratedEntries(board, query", 1)[1].split("\n}", 1)[0]
    assert "foldName(entry.domain).includes(needle)" in curated
    # A field hit is a weaker answer than a name hit and ranks below every one.
    assert "const best = hits.length ? Math.min(...hits.map(tier)) : 3;" in curated

    external = script.split("function searchBenchmarkIndex(records, query)", 1)[1].split("\n}", 1)[
        0
    ]
    assert "foldName(record.publisher).includes(needle)" in external
    assert "foldName(record.modality).includes(needle)" in external


def test_a_link_to_an_unscored_benchmark_says_so_instead_of_swapping():
    # These 20 benchmarks resolved and drew an adoption staircase before this
    # change, so links to them are already out there. Falling through to the
    # default entry would show a different benchmark under the reader's own URL
    # with nothing to say so, which is a worse failure than an explicit refusal.
    script = source("site/assets/app.js")
    render = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\nfunction ", 1)[0]

    assert "const unscoredEntry = state.lfrontier" in render
    assert "&& !scoreRecord(candidate.benchmark_id)" in render
    assert "so there is no track to draw" in render
    # It resolves before the default-entry fallback, or the fallback wins.
    fallback = "state.lfrontier = defaultEntry.benchmark_id"
    assert render.index("const unscoredEntry") < render.index(fallback)
    # And the reader's URL is left alone: the panel names the benchmark they
    # asked for rather than rewriting the address to one they did not.
    assert "heading: unscoredEntry.name" in render


def test_no_route_into_the_panel_can_land_on_an_unscored_benchmark():
    # The picker is not the only way in: a leaderboard row and a finding card
    # both jump here. Either would snap to the default entry for an unscored
    # benchmark and lie about what it opened, so neither offers the jump.
    script = source("site/assets/app.js")

    row = script.split("function leaderboardRow(entry)", 1)[1]
    assert "const frontierButton = scoreRecord(entry.benchmark_id)" in row

    finding = script.split("function findingCard(finding, board)", 1)[1]
    guard = "entry.benchmark_id === finding.benchmark_id && scoreRecord(entry.benchmark_id)"
    assert guard in finding


def test_the_time_range_covers_the_score_track_at_both_ends():
    # Codex P2, second pass. `startText` already considered the first score date
    # while `endText` derived only from adoption dates, so a score newer than
    # every card -- reachable when a card carries a later `revised` date -- landed
    # outside the viewBox and was silently clipped.
    script = source("site/assets/app.js")
    chart = script.split("function scoreTrackChart(", 1)[1]
    range_block = chart.split("const start = new Date(", 1)[0]

    assert "const startText = record.first_reported_at;" in range_block
    assert "record.last_reported_at" in range_block


def test_scores_render_whether_or_not_any_mention_carries_a_date():
    # The registry permits a card without `published`. When the adoption band led
    # the panel, a benchmark with no dated mention was routed through a separate
    # early return and a second entry point into the chart. The score track needs
    # no dated mention at all: its own axis is bounded by the score record, and
    # `lastMention` is consulted only to bound the reading-gap marker.
    script = source("site/assets/app.js")

    assert "if (!events.length) {" not in script
    render = script.split("function renderAdoptionFrontier(board)", 1)[1].split("\nfunction ", 1)[0]
    paint = (
        'replaceChildren(byId("frontier-chart"), '
        "[scoreTrackChart(entry, board), frontierTooltip()])"
    )
    assert paint in render

    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "const startText = record.first_reported_at;" in chart
    # The only adoption field the renderer touches is the mention date, and only
    # to bound the reading gap. It reads no advance flag and no running count.
    assert "const lastMention = frontierEvents(entry).at(-1)?.published;" in chart
    assert ".advances" not in chart
    assert "organizationCount" not in chart


def test_there_is_exactly_one_renderer_per_score_layer():
    # Two implementations of one axis would be free to disagree about the join
    # rule, which is the single thing this chart must not do. The second entry
    # point (`scoreOnlyChart`, for a benchmark with no dated mention) existed only
    # to suppress the adoption bands and went with them.
    #
    # The crawled layer has its own single renderer rather than a variant of this
    # one, and that separation is the point: `scoreTrackChart` owns the time axis
    # and the join rule, `externalScoreChart` owns a rank axis and joins nothing.
    # One function serving both would have to carry a mode flag deciding whether
    # a date exists, which is exactly how a crawled row ends up on a chronology.
    script = source("site/assets/app.js")

    assert script.count("function scoreTrackChart(") == 1
    assert script.count("function externalScoreChart(") == 1
    assert "function scoreOnlyChart(" not in script
    assert "function adoptionFrontierChart(" not in script
    # And no permanently-false flag left behind in its place: a switch nobody can
    # turn on is worse than no switch.
    assert "sparse" not in script


def test_the_reading_gap_ends_at_this_benchmarks_own_latest_mention():
    # Codex P2, third pass. `endText` comes from the newest card anywhere in the
    # registry, so shipped Arena-Hard and Aider Polyglot -- which have no adopter
    # newer than their last score -- drew a long gap nothing supported.
    script = source("site/assets/app.js")
    gap = script.split("const lastMention = frontierEvents(entry)", 1)[1].split(
        "no score read from a document in this window", 1
    )[0]

    assert "lastMention > record.last_reported_at" in gap
    assert "x(endText)" not in gap, "the gap must not extend to the registry-wide end date"


def test_the_adoption_marks_are_gone_from_the_chart():
    # The staircase, its orange advance diamonds, the release marker and the card
    # rug all answered "who reported this, and when" rather than "what did it
    # score". They are removed rather than hidden behind a flag: the geometry
    # that kept them legible (the count axis, the rug's collision sweep, the
    # release line spanning both plots) is dead weight the moment nothing draws
    # them, and it would drift out of agreement with the score band it no longer
    # shares a viewBox with.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    for mark in (
        "frontier-point-advance",
        "frontier-point-face",
        "frontier-point-number",
        "card-rug-tick",
        "card-rug-baseline",
        "frontier-release-line",
        "MIN_TICK_GAP",
        "organizationCount",
        "maxOrganizations",
        "frontier-sparse",
    ):
        assert mark not in script, f"{mark} still drawn"
        assert mark not in styles, f"{mark} still styled"

    # `frontier-line` was the adoption staircase's join. It is checked apart
    # from the list above because issue #288 added `score-frontier-line` -- the
    # running best -- and a bare substring test cannot tell the two apart. The
    # retired class is gone; the new one is a different mark making a different
    # claim (nothing had beaten this yet, rather than these points are a line).
    for text in (script, styles):
        assert "score-frontier-line" in text
        assert '"frontier-line"' not in text
        assert ".frontier-line" not in text

    # The score marks are untouched. They carry their own classes, so a check
    # that the adoption ones are absent cannot pass by emptying the chart.
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "score-point-face" in chart
    assert ".score-point-face" in styles


def test_the_legend_keys_only_marks_that_are_on_the_chart():
    # A key describing marks that are not on screen is worse than no key. The
    # four adoption entries (the advance diamond, the two rug ticks and their
    # effect on the count) named marks the chart no longer draws, so they went
    # with the bands; what remains is keyed to the score marks.
    html = source("site/index.html")
    script = source("site/assets/app.js")
    legend = script.split("function renderFrontierLegend(", 1)[1].split("\n}", 1)[0]

    assert 'id="frontier-legend"' in html
    assert "const items = [];" in legend
    for gone in (
        "New organization",
        "First card from that organization",
        "Later card, organization already counted",
        "cumulative count increases",
        "count unchanged",
        "the tick under the jump",
    ):
        assert gone not in script, f"{gone!r} still in the legend copy"
    # One entry remains, keyed to the only mark the chart draws.
    assert "legend-swatch-score" in legend
    assert "one value read verbatim from a cited document" in legend
    for gone in ("Solid score connection", "Dashed score connection"):
        assert gone not in script, f"{gone!r} keys a mark that is no longer drawn"


def test_the_axis_and_header_name_the_score_reading():
    # The header said "ADOPTION TRAJECTORY" over a chart that no longer plots
    # adoption, and the counts line under it ("26 model cards, 10 distinct
    # organizations, last new organization ...") was an adoption reading in
    # prose. Both are replaced by what the panel actually shows.
    html = source("site/index.html")
    script = source("site/assets/app.js")

    # The heading is the benchmark's name and the eyebrow says what kind of
    # picture it is. They used to say the same thing twice: an eyebrow reading
    # "Scores over time" above a heading reading "<name> reported scores over
    # time". What must not drift is that a single reading is never presented as
    # a track over time.
    assert 'byId("frontier-heading").textContent = entry.name;' in script
    assert "spansTime(record)" in script
    assert 't("Scores over time")' in script
    assert '"charted score"' in script
    assert "adoption trajectory" not in script
    # The counts line and the reporting-stage sentence are gone from the markup,
    # so nothing can repopulate them.
    assert 'id="frontier-summary"' not in html
    assert "frontier-summary" not in script
    assert "function reportingStage(" not in script

    # The x axis names the date each point actually carries. 5,522 of the 5,544
    # crawled rows carry a model release date and none carries an evaluation
    # date, so an unqualified "time" invites the wrong reading; the curated
    # points here sit at the date their citing document was published, and the
    # label says which.
    assert 't("document publication date")' in script
    assert '"document publication date": ' in script


def test_the_chart_does_not_collapse_on_a_narrow_viewport():
    # `width: 100%` scales height with width, so a 920-unit viewBox at 390px
    # rendered the chart about 90px tall. A narrower viewBox scales the same
    # content up; distorting the aspect ratio would stretch the axis text.
    #
    # The width selection itself is asserted, not just the breakpoint expression:
    # an earlier version of this test passed even with `width` reverted to a
    # constant 920, because `narrow` stayed in use for the axis labels.
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")

    assert 'const narrow = typeof window !== "undefined" && window.innerWidth <= 760' in script
    assert "const width = narrow ? 520 : 920;" in script
    assert 'preserveAspectRatio: "none"' not in script
    narrow_rule = styles.split("@media (max-width: 760px) {", 1)[1]
    assert "min-height" in narrow_rule.split(".frontier-chart svg {", 1)[1].split("}", 1)[0]
    # Crossing the breakpoint has to redraw, or a resized page keeps a stale box.
    assert "if (isNarrow === wasNarrow) return;" in script


def test_the_rug_collision_sweep_went_with_the_rug():
    # The rug's one-pass tick allocation existed because several cards sharing a
    # date overpainted each other. With the rug removed there is nothing left to
    # allocate, and a nudging sweep that still ran would move score points off
    # the dates they were reported on -- the opposite of what it was for.
    script = source("site/assets/app.js")

    assert "MIN_TICK_GAP" not in script
    # Score points sit at x(reported_at) and nowhere else. Several scores may
    # share a date; they are separated by their y value, which is the reading,
    # rather than nudged along the axis, which would falsify it.
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "x(observation.reported_at)" in chart
    assert "previous + " not in chart


def test_the_zoom_marker_survives_a_narrow_viewport():
    # Codex P2. Dropping it on small screens left no indication that the score axis
    # is magnified, and the justification (that the readout states the band bounds)
    # was false -- the bounds appear only as the two axis ticks.
    script = source("site/assets/app.js")

    assert "(zoom)" in script
    assert "(zoomed)" in script


def test_the_score_axis_says_it_is_zoomed():
    # Every value in this corpus sits in the upper part of its scale, so the
    # band is padded around the observed range instead of running 0-100. A
    # zoomed axis that does not say so overstates the movement it shows.
    script = source("site/assets/app.js")

    assert "function scoreBand(record)" in script
    assert "(zoomed)" in script


def test_a_benchmark_with_no_readable_score_draws_no_chart_at_all():
    # Previously the panel opened on the adoption staircase and said in the
    # readout that no score could be read. With the staircase retired there is
    # nothing left to draw, so the renderer refuses rather than emitting an empty
    # band, which a reader would take for a drop to zero.
    script = source("site/assets/app.js")

    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]
    assert "if (!record) return null;" in chart
    # No conditional band height survives: the band is unconditionally full.
    assert "record ? 132 : 0" not in chart

    # The readout keeps the honest sentence for the defensive case, minus the
    # clause promising an adoption chart that no longer exists.
    readout = script.split("function renderScoreReadout(entry)", 1)[1].split("\nfunction ", 1)[0]
    assert "not a zero and not a plateau" in readout
    assert "the chart shows adoption only" not in script


def test_the_evidence_grade_is_printed_not_hidden():
    # The honest scope of a two-point chart is the first thing a reader needs,
    # not an optional disclosure.
    script = source("site/assets/app.js")

    assert "evidence.supports" in script
    assert "evidence.does_not_support" in script
    assert '"Does not support: "' in script


def test_findings_are_rendered_with_their_evidence():
    # Issue #91's third point. A finding a reader cannot audit is an assertion.
    html = source("site/index.html")
    script = source("site/assets/app.js")

    assert 'id="benchmark-findings"' in html
    assert 'id="findings-list"' in html
    assert "function renderBenchmarkFindings(board)" in script
    assert "finding.evidence" in script
    assert "finding.detail" in script


def test_findings_state_what_they_do_not_measure():
    script = source("site/assets/app.js")

    assert "insights.does_not_measure" in script
    assert 'id="findings-limits"' in source("site/index.html")


def test_an_empty_findings_list_hides_the_panel_rather_than_showing_nothing():
    # An empty panel reads as "we looked and the field is uneventful".
    script = source("site/assets/app.js")
    renderer = script.split("function renderBenchmarkFindings(board)", 1)[1].split(
        "\nfunction modelCardLabelCounts", 1
    )[0]

    assert "panel.hidden = true" in renderer
    assert "!insights.findings?.length" in renderer


def test_a_finding_can_move_the_chart_to_the_benchmark_it_is_about():
    # A claim should never be more than one interaction away from its data.
    script = source("site/assets/app.js")
    card = script.split("function findingCard(finding, board)", 1)[1].split(
        "\nfunction renderBenchmarkFindings", 1
    )[0]

    assert "selectFrontier(target.benchmark_id)" in card
    assert "renderAdoptionFrontier(board)" in card
    # Corpus-scope findings name no benchmark, so there is nothing to focus.
    assert "finding.benchmark_id" in card


def test_the_explainer_leaves_saturation_as_the_readers_judgement():
    # The predecessor of this guarantee said a flat adoption run was reporting
    # saturation and not a claim about scores. The adoption run is gone, so the
    # confusion it guarded against is now the inverse one: a flat score tail read
    # as a saturated benchmark. The preamble has to name the gap for what it is
    # and must not print a saturation verdict of its own.
    html = " ".join(source("site/index.html").split())

    assert "no newer number could be read" in html
    assert "the gap is marked rather than drawn through" in html
    assert "stays a reading you make, not a score this panel prints" in html
    assert "connected only where the test variant and run conditions" in html
    # And it names the date the x axis carries, rather than leaving "time" to be
    # read as an evaluation date.
    dateline = "placed at the date that document was published rather than at any evaluation date"
    assert dateline in html


def test_the_score_layer_is_keyed_by_the_same_benchmark_id_as_adoption():
    # Two rankings that could disagree about what a benchmark is would be worse
    # than one. The score layer is a lookup, not a second ordering.
    script = source("site/assets/app.js")

    assert "benchmark_score_progression?.benchmarks?.[benchmarkId]" in script


def test_issue_312_the_saturation_view_reveals_left_to_right():
    """The chart popped in fully drawn, so the reader never saw the shape form.

    The running-best line now draws itself across the axis and each point
    brightens while the drawing front crosses its date: the reveal reads in
    the same direction the data does. The entrance is presentation only -- a
    reduced-motion reader gets the finished chart immediately.
    """
    script = source("site/assets/app.js")
    styles = source("site/assets/styles.css")
    chart = script.split("function scoreTrackChart(", 1)[1].split(
        "\nfunction clearAdoptionFrontier", 1
    )[0]

    # The line declares its length, so CSS can draw it with a dash offset
    # instead of script measuring geometry on a detached tree.
    assert 'pathLength: "1",' in chart

    # Each point carries its own delay on the timeline, derived from where it
    # sits on the x axis rather than from its row order.
    assert "function frontierPointRevealDelay(pointX, margin, plotWidth)" in script
    assert "(pointX - margin.left) / plotWidth" in script
    assert "frontierPointRevealDelay(pointX, margin, plotWidth)" in chart
    assert 'style: `--reveal-delay:${revealDelay}ms`,' in chart

    # The crawled layer's points share the same reveal: one kind of mark gets
    # one entrance, so selecting a crawled benchmark does not fade everything
    # in at once while the curated one staggers.
    external = script.split("function externalScoreChart(", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "frontierPointRevealDelay" in external

    # The issue's definition is enforced in the same pass: points that hold
    # the best value as of their date are the line; every other reading fades
    # back behind it, and recovers on hover or focus. Dimming is gated on the
    # line actually existing -- no line, nothing recedes behind it.
    assert "const frontierMarks = new Set();" in chart
    assert "if (frontier && frontier.steps.length) {" in chart
    assert "if (point.value === best) {" in chart
    # Membership carries the comparable run's own key, so an unrelated run
    # reporting the same number on the same date is not drawn onto the line.
    assert "`${frontier.key}\\u0000${point.time}\\u0000${point.value}`" in chart
    assert (
        "`${observation.instrument || \"\"}\\u0000${observation.protocol || \"\"}\\u0000" in chart
    )
    # Same-date readings collapse to their directional best before the steps
    # are built, so what is drawn and what is emphasized cannot disagree: the
    # line never steps through an inferior number that shares a better
    # reading's date.
    assert "const bestByDate = new Map();" in chart
    assert ".sort((a, b) => a[0] - b[0])" in chart
    assert "runningBestSteps(points, { descends: scoreDescends })" in chart

    # A shell or empty state replaces the chart on screen, so a running
    # completion timer may not spend the reveal it can no longer show.
    shell = script.split("function renderExternalShell(", 1)[1].split("\nfunction ", 1)[0]
    assert "drawnFrontierEntranceKey = null;" in shell
    clear_fn = script.split("function clearAdoptionFrontier(message)", 1)[1].split("\n}", 1)[0]
    assert "drawnFrontierEntranceKey = null;" in clear_fn
    # Dimming itself is gated on a line being drawn: with no comparable pair
    # there is no reference, and every point keeps full emphasis rather than
    # all of them receding together.
    assert (
        "const offTheLine = Boolean(frontierSteps?.length) && !onFrontier;" in chart
    )
    assert "offTheLine ? \" score-point-dim\" : \"\"" in chart
    dim = styles.split(".score-point-dim .score-point-face {", 1)[1][:200]
    assert "fill-opacity: 0.6;" in dim
    assert ".score-point-dim:hover .score-point-face" in styles
    assert ".score-point-dim.is-selected .score-point-glyph" in styles

    # The entrance is gated to arrivals and runs to completion before it is
    # spent: a redraw into a hidden panel never spends an entrance, and the
    # crawled catalog settling mid-reveal replays rather than cancels it.
    assert "function frontierShouldAnimate(key)" in script
    gate = script.split("function frontierShouldAnimate(key)", 1)[1].split("\n}", 1)[0]
    assert 'if (state.view !== "leaderboard") return false;' in gate
    assert "completedFrontierEntranceKey === key" in gate
    # And the completion callback rechecks visibility and the drawn selection:
    # leaving mid-reveal, to another view or another benchmark, must still
    # play the entrance on return.
    assert 'if (state.view === "leaderboard") completedFrontierEntranceKey = key;' not in gate
    assert "drawnFrontierEntranceKey === key" in gate
    assert "state.view === \"leaderboard\" &&\n        drawnFrontierEntranceKey === key" in gate
    assert "const FRONTIER_ENTRANCE_MS = 1400;" in script
    assert 'frontierShouldAnimate(`curated:${entry.benchmark_id}`)' in script
    assert 'frontierShouldAnimate(`external:${record.slug}`)' in script
    assert script.count('"score-chart-enter"') == 2

    # A superseded shard callback may not paint: two renders of one record
    # before its cached shard settles would otherwise let the second paint
    # clear the entrance class before the browser drew a frame.
    assert "let externalRenderSeq = 0;" in script
    external_render = script.split("function renderExternalBenchmark(board, scored, record)", 1)[
        1
    ].split("\nfunction ", 1)[0]
    assert "const renderToken = ++externalRenderSeq;" in external_render
    assert "if (renderToken !== externalRenderSeq) return;" in external_render

    line_rule = styles.split(".score-chart-enter .score-frontier-line {", 1)[1][:400]
    assert "stroke-dasharray: 1;" in line_rule
    assert "stroke-dashoffset: 1;" in line_rule
    assert "animation: score-frontier-draw" in line_rule
    assert "@keyframes score-frontier-draw" in styles

    point_rule = styles.split(".score-chart-enter .score-point {", 1)[1][:300]
    assert "opacity: 0;" in point_rule
    assert "animation: score-point-reveal" in point_rule
    assert "animation-delay: var(--reveal-delay, 0ms);" in point_rule

    # And the whole entrance collapses for prefers-reduced-motion. The guard
    # must match the gated selectors or it would lose the cascade.
    guard = styles.split("@media (prefers-reduced-motion: reduce)", 1)[1][:600]
    assert ".score-chart-enter .score-point" in guard
    assert ".score-chart-enter .score-frontier-line" in guard
    assert "stroke-dashoffset: 0;" in guard
