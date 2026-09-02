"""Build the HTML each dashboard view ships in its first response.

``app_pages`` writes copies of ``site/index.html`` at the dashboard and utility
paths. The seeds here are what those copies carry inside the containers
``assets/app.js`` renders into. Utility pages follow the same rule as the data
views: their open dialog contains the real CLI, citation, or rubric card in the
first response, and the browser renderer replaces that seed after hydration.

One rule governs all of them: a seed is what the renderer would produce from the
same data, in the same markup, no more and no less. A summary written for
crawlers would show them a page no reader sees. Leaving out a card the renderer
always draws does the same thing in the other direction: the crawler gets a
thinner page than the reader, under a canonical that claims otherwise. Every
seed below names the function in ``assets/app.js`` it mirrors, so a change on
one side has an obvious counterpart on the other.
"""

from __future__ import annotations

from typing import Any

from .citation import apa_citation
from .site_shell import esc


def _num(value: Any) -> str:
    """Match Number.toLocaleString() for the en locale these seeds are written in."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def _metric_label(value: Any, singular: str, plural: str | None = None) -> str:
    count = int(value or 0)
    noun = singular if count == 1 else (plural or f"{singular}s")
    return f"{count:,} {noun}"


def _decimal(value: Any, places: int = 2) -> str:
    """Match Number(value).toFixed(places), with a safe zero for bad source data."""
    try:
        return f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return f"{0:.{places}f}"


def _collate(name: str) -> tuple[str, str]:
    """Order names the way String.prototype.localeCompare does for en.

    The renderers break count ties on the name, and the browser compares
    case-insensitively first: "arXiv" lands before "OpenAI" there and after it
    under Python's codepoint sort. Without this the two lists would disagree for
    the same data, which is exactly what a seed must never do.
    """
    return (name.casefold(), name)


# --- Leaderboard --------------------------------------------------------------

LEADERBOARD_TOP_LIMIT = 5

# The sentence renderLeaderboardTop joins onto board.measures inside the (i)
# beside the ranking. It is the caveat that keeps an adoption count from being
# read as a quality score, so a page that ships the ranking ships it too.
LEADERBOARD_TOP_NOTE = (
    "A report counts once per test, even if it lists that test several times. "
    "Some reports publish their results as a picture rather than text, and we "
    "read those with software that can misread a digit, so the list at the "
    "bottom of this page links every count back to the report it came from."
)


def _info_disclosure(text: str) -> str:
    """The markup infoDisclosure emits."""
    return (
        '<details class="info-disclosure">'
        '<summary class="info-disclosure-toggle" aria-label="What does this source record?">'
        "i</summary>"
        f'<p class="info-disclosure-body">{esc(text)}</p>'
        "</details>"
    )


def _leaderboard_seed(dashboard: dict[str, Any]) -> dict[str, str]:
    """The top rows, the measures note and the caveat renderLeaderboardTop emits."""
    board = dashboard.get("model_card_leaderboard") or {}
    ranked = [entry for entry in (board.get("entries") or []) if (entry.get("card_count") or 0) > 0]
    entries = ranked[:LEADERBOARD_TOP_LIMIT]
    if not entries:
        return {}
    # Scaled against the top row on screen rather than the top row overall,
    # because that is what the renderer scales against.
    top = max(int(entry["card_count"]) for entry in entries)
    rows = "".join(
        '<li class="leaderboard-top-row">'
        f'<span class="leaderboard-top-rank">{esc(str(entry.get("rank", "")).zfill(2))}</span>'
        f'<span class="leaderboard-top-name">{esc(entry.get("name") or "")}</span>'
        '<span class="leaderboard-top-bar">'
        '<span class="leaderboard-top-bar-fill" '
        f'style="width:{int(entry["card_count"]) / top * 100:.1f}%"></span>'
        "</span>"
        '<span class="leaderboard-top-count">'
        f"{esc(_metric_label(entry.get('card_count'), 'model card'))}</span>"
        "</li>"
        for entry in entries
    )
    measures = board.get("measures")
    note = " ".join(part for part in (measures, LEADERBOARD_TOP_NOTE) if part)
    seed = {
        '<ol class="leaderboard-top-list" id="leaderboard-top-list"></ol>': (
            f'<ol class="leaderboard-top-list" id="leaderboard-top-list" data-seed>{rows}</ol>'
        ),
        '<span id="leaderboard-top-info"></span>': (
            f'<span id="leaderboard-top-info" data-seed>{_info_disclosure(note)}</span>'
        ),
    }
    if len(ranked) > LEADERBOARD_TOP_LIMIT:
        button = "\n".join(
            (
                "          <button",
                '            class="leaderboard-top-more"',
                '            id="leaderboard-top-more"',
                '            type="button"',
                '            aria-label="Show more ranked benchmarks"',
                "            hidden",
                "          >Show more ranked benchmarks</button>",
            )
        )
        label = f"Show all {len(ranked)} benchmarks ↓"
        seed[button] = (
            button.replace("\n            hidden", "\n            data-seed")
            .replace(
                'aria-label="Show more ranked benchmarks"',
                f'aria-label="{esc(label)}"',
            )
            .replace(">Show more ranked benchmarks</button>", f">{esc(label)}</button>")
        )
    if measures:
        seed['<p class="leaderboard-deck visually-hidden" id="leaderboard-measures"></p>'] = (
            '<p class="leaderboard-deck visually-hidden" id="leaderboard-measures" data-seed>'
            f"{esc(measures)}</p>"
        )
    return seed


# --- Trends -------------------------------------------------------------------

# Intl.DateTimeFormat("en", {dateStyle: "medium"}) abbreviations. Spelled out
# rather than taken from strftime, whose %b follows the machine's LC_TIME and
# would make the published page depend on the runner's locale.
_MEDIUM_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _medium_date(value: str) -> str:
    """Match formatDate(value, {dateStyle: "medium"}) for the en locale."""
    try:
        year, month, day = (int(part) for part in value.split("-")[:3])
        return f"{_MEDIUM_MONTHS[month - 1]} {day}, {year}"
    except (AttributeError, IndexError, ValueError):
        return "Unknown"


def _domain_rows(trend: dict[str, Any]) -> list[tuple[str, str]]:
    """The stat rows domainCard builds, in its order and with its wording."""
    delta = trend.get("delta")
    if delta is None:
        change = "not comparable"
    else:
        change = "no change" if not int(delta) else f"{int(delta):+d}"
    baseline = trend.get("baseline")
    rows: list[tuple[str, str]] = [
        ("vs previous scan", change),
        (
            "recent daily average",
            "not enough history" if baseline is None else f"{float(baseline):.2f}",
        ),
    ]
    momentum = trend.get("momentum")
    if momentum is not None:
        percent = round(float(momentum) * 100)
        rows.append(("vs its average", f"{'+' if percent > 0 else ''}{percent}%"))
    rows.append(("cumulative", _num(trend.get("cumulative"))))
    updated_only = max(0, int(trend.get("total_count") or 0) - int(trend.get("count") or 0))
    if updated_only:
        rows.append(("also updated (not counted above)", _num(updated_only)))
    return rows


def _trends_seed(
    dashboard: dict[str, Any], palette: tuple[dict[str, str], list[str]]
) -> dict[str, str]:
    """The latest day's domain cards and its date, as renderDomainMetrics writes them."""
    days = dashboard.get("days") or []
    if not days:
        return {}
    day = days[-1]
    trends = day.get("category_trends") or {}
    entries = sorted(trends.items(), key=lambda item: (-int(item[1].get("count") or 0), item[0]))
    if not entries:
        return {}
    colors, fallbacks = palette
    cards = []
    for index, (category, trend) in enumerate(entries):
        delta = trend.get("delta")
        direction = ""
        if delta is not None:
            direction = " is-up" if int(delta) > 0 else (" is-down" if int(delta) < 0 else "")
        swatch = colors.get(category, fallbacks[index % len(fallbacks)])
        stats = "".join(
            f"<dt>{esc(label)}</dt><dd>{esc(value)}</dd>" for label, value in _domain_rows(trend)
        )
        cards.append(
            f'<article class="domain-card{direction}">'
            '<div class="domain-head">'
            f'<span class="legend-swatch" style="--swatch: {esc(swatch)};"></span>'
            f"<h3>{esc(category.replace('_', ' '))}</h3>"
            "</div>"
            '<p class="domain-count" '
            'title="New releases only. Re-announced updates are tracked separately.">'
            f"{esc(int(trend.get('count') or 0))}</p>"
            f'<dl class="domain-stats">{stats}</dl>'
            "</article>"
        )
    return {
        '<div class="domain-grid" id="domain-grid" aria-labelledby="domain-heading"></div>': (
            '<div class="domain-grid" id="domain-grid" aria-labelledby="domain-heading" data-seed>'
            f"{''.join(cards)}</div>"
        ),
        # The cards count one scan, so the heading beside them has to say which.
        '<span id="domain-date"></span>': (
            f'<span id="domain-date" data-seed>{esc(_medium_date(day.get("date")))}</span>'
        ),
    }


# --- Explore ------------------------------------------------------------------

# The five entity kinds renderMapInsights counts, with its labels.
MAP_COVERAGE_ROWS = (
    ("Items", "artifact"),
    ("Organizations", "organization"),
    ("Authors", "person"),
    ("Sources", "source"),
    ("Topics", "topic"),
)

# renderMapInsights spells out the topic keys a reader would not recognize and
# falls back to the key with its underscores opened up.
MAP_TOPIC_LABELS = {
    "agentic": "AI agents",
    "benchmark": "benchmarks",
    "dataset": "datasets",
    "evaluation": "evaluations",
    "data_quality": "data quality",
}


def _ranked_counts(values: Any, limit: int = 6) -> list[tuple[str, int]]:
    """The rankedCounts helper: highest count first, ties broken on the name."""
    items = (values or {}).items() if isinstance(values, dict) else ()
    ranked = sorted(items, key=lambda item: (-int(item[1] or 0), _collate(str(item[0]))))
    return [(str(name), int(count or 0)) for name, count in ranked[:limit]]


def _map_insight_card(title: str, entries: list[tuple[str, str]], empty_text: str) -> str:
    """The markup mapInsightCard emits for rows that carry no drill-in detail."""
    if entries:
        body = "".join(
            f"<li><span>{esc(label)}</span><strong>{esc(value)}</strong></li>"
            for label, value in entries
        )
        body = f"<ul>{body}</ul>"
    else:
        body = f"<p>{esc(empty_text)}</p>"
    return f'<article class="map-insight-card"><h2>{esc(title)}</h2>{body}</article>'


def _map_seed(dashboard: dict[str, Any]) -> dict[str, str]:
    """The four cards renderMapInsights builds, in its order.

    All four, not just the coverage counts: the renderer always draws the topic,
    source and organization rankings, so a page that shipped one card would give
    a crawler a quarter of what a reader sees.
    """
    aggregates = (dashboard.get("corpus") or {}).get("aggregates") or {}
    entity_types = aggregates.get("entity_types") or {}
    topics = aggregates.get("topics") or []
    sources = aggregates.get("sources") or {}
    organizations = aggregates.get("organizations") or {}
    if not (entity_types or topics or sources or organizations):
        return {}

    coverage = [(label, _num(entity_types.get(key))) for label, key in MAP_COVERAGE_ROWS]
    ranked_topics = sorted(
        topics,
        key=lambda topic: (
            -int(topic.get("entity_count") or 0),
            _collate(str(topic.get("topic"))),
        ),
    )
    topic_rows = []
    for topic in ranked_topics:
        key = str(topic.get("topic"))
        topic_rows.append(
            (
                MAP_TOPIC_LABELS.get(key, key.replace("_", " ")),
                f"{_num(topic.get('entity_count'))} items"
                f" · {_metric_label(topic.get('source_breadth'), 'source')}",
            )
        )
    source_rows = [(name, f"{_num(count)} times found") for name, count in _ranked_counts(sources)]
    organization_rows = [
        (name, f"{_num(count)} times found") for name, count in _ranked_counts(organizations)
    ]

    cards = "".join(
        (
            _map_insight_card("At a glance", coverage, "Nothing found yet."),
            _map_insight_card("What it is about", topic_rows, "No topics yet."),
            _map_insight_card("Where we found it", source_rows, "No sources yet."),
            _map_insight_card("Who appears most", organization_rows, "No organizations yet."),
        )
    )
    return {
        '<div class="map-insights" id="map-insights" aria-label="Overview"></div>': (
            '<div class="map-insights" id="map-insights" aria-label="Overview" data-seed>'
            f"{cards}</div>"
        )
    }


def view_seeds(
    dashboard: dict[str, Any], palette: tuple[dict[str, str], list[str]]
) -> dict[str, dict[str, str]]:
    """Every view's seed, keyed by view. An empty dict means nothing to publish."""
    return {
        "leaderboard": _leaderboard_seed(dashboard),
        "trends": _trends_seed(dashboard, palette),
        "map": _map_seed(dashboard),
    }


# --- Utility dialogs ----------------------------------------------------------

# These are the verbatim public values used by openCite and openCli in app.js.
# Tests compare both renderers so a change to either copy fails instead of
# quietly giving a crawler a different setup prompt or citation than a reader.
CITE_DOI_URL = "https://doi.org/10.5281/zenodo.22167102"
CITE_CFF_URL = "https://github.com/ktwu01/benchmark-radar/blob/main/CITATION.cff"
# The site dialog and the CLI reminder share citation.py's author list and
# version, so the APA a reader copies is the APA an agent is asked for.
CITE_APA = apa_citation()
CITE_BIBTEX = """@techreport{Wu_Benchmark_Radar_v0_9_0_2026,
author = {Wu, Koutian and Zhou, Junjie},
doi = {10.5281/zenodo.22167102},
month = aug,
title = {{Benchmark Radar v0.9.0: Technical Report}},
url = {https://zenodo.org/records/22167102},
year = {2026}
}"""

CLI_SKILL_URL = (
    "https://github.com/ktwu01/benchmark-radar/blob/main/skills/benchmark-radar/SKILL.md"
)
CLI_SKILL_INSTALL = "npx skills add ktwu01/benchmark-radar"
CLI_AGENT_PROMPT = "\n".join(
    (
        "Use the installed Benchmark Radar Skill to finish local benchmark search setup. Follow",
        CLI_SKILL_URL,
        "to install or repair the CLI if needed, initialize the local data, and verify the setup.",
        "You have permission to install the CLI from the official repository. Use only consumer"
        " commands.",
    )
)


def _copy_block(label: str, value: str, hint: str) -> str:
    """The non-interactive form of copyBlock in app.js.

    The button already contains its label, value and fallback instruction. The
    runtime only has to add clipboard behavior; a failed or disabled script
    never leaves behind an empty button.
    """
    return (
        '<section class="copy-block">'
        f'<h3 class="copy-label">{esc(label)}</h3>'
        f'<button class="copy-target" type="button" aria-label="{esc(hint)}: {esc(label)}">'
        f'<code class="copy-text">{esc(value)}</code>'
        f'<span class="copy-status">{esc(hint)}</span>'
        "</button>"
        "</section>"
    )


def _cite_seed() -> dict[str, str]:
    blocks = "".join(
        (
            _copy_block("APA", CITE_APA, "Click to copy"),
            _copy_block("BibTeX", CITE_BIBTEX, "Click to copy"),
            _copy_block("Citation file (.cff)", CITE_CFF_URL, "Click to copy link"),
        )
    )
    content = (
        '<p class="detail-source">Benchmark Radar</p>'
        '<h2 class="detail-title cite-title" id="cite-title">Cite this work</h2>'
        '<p class="detail-summary">'
        "Pick the format your paper or repository needs, then click it to copy."
        "</p>"
        f'<div class="copy-blocks">{blocks}</div>'
        '<a class="secondary-link dialog-link" '
        f'href="{esc(CITE_CFF_URL)}" target="_blank" rel="noopener noreferrer">'
        "View the citation file</a>"
    )
    return {'<div id="cite-content"></div>': (f'<div id="cite-content" data-seed>{content}</div>')}


def _cli_seed() -> dict[str, str]:
    content = (
        '<p class="detail-source">Benchmark Radar</p>'
        '<h2 class="detail-title cli-title" id="cli-title">'
        "Query it locally (CLI version)</h2>"
        '<p class="detail-summary">'
        "This website is the hosted view. For local queries, install the Agent Skill, "
        "then let your coding agent configure the command-line tool and searchable data."
        "</p>"
        '<div class="copy-blocks">'
        f"{_copy_block('Install the Agent Skill', CLI_SKILL_INSTALL, 'Click to copy')}"
        f"{_copy_block('Give this prompt to your coding agent', CLI_AGENT_PROMPT, 'Click to copy')}"
        "</div>"
        '<a class="secondary-link dialog-link" '
        f'href="{esc(CLI_SKILL_URL)}" target="_blank" rel="noopener noreferrer">'
        "Read the setup guide</a>"
    )
    return {'<div id="cli-content"></div>': (f'<div id="cli-content" data-seed>{content}</div>')}


def _rubric_seed(dashboard: dict[str, Any]) -> dict[str, str]:
    data = dashboard.get("rubric") or {}
    components = data.get("components") or []
    if not data or not components:
        return {}

    version = int(data.get("scoring_version") or 1)
    maximum = float(data.get("score_max") or 4)
    header = (
        f'<p class="detail-source">Scoring rubric v{version} · current</p>'
        '<h2 class="detail-title rubric-title" id="rubric-title">How priority is scored</h2>'
        '<p class="detail-summary">'
        "Priority is the weighted mean of four components, each measured on a 0 to "
        f"{maximum:.2f} scale. Every number below is read from the same definition the "
        "pipeline applies.</p>"
        f'<p class="rubric-formula">{esc(data.get("formula") or "")}</p>'
    )
    component_sections = []
    for component in components:
        bands = "".join(f"<li>{esc(band)}</li>" for band in (component.get("bands") or []))
        component_sections.append(
            '<section class="rubric-component">'
            '<div class="rubric-component-head">'
            f"<h3>{esc(component.get('label') or '')}</h3>"
            f'<span class="rubric-weight">weight {_decimal(component.get("weight"))}</span>'
            "</div>"
            f"<p>{esc(component.get('summary') or '')}</p>"
            f'<ul class="rubric-bands">{bands}</ul>'
            "</section>"
        )

    limits = ""
    if data.get("limits"):
        items = "".join(f"<li>{esc(limit)}</li>" for limit in data["limits"])
        limits = (
            '<section class="rubric-limits">'
            "<h3>What this score does not claim</h3>"
            f"<ul>{items}</ul>"
            "</section>"
        )

    selection = (dashboard.get("days") or [{}])[-1].get("selection") or {}
    recommendation = selection.get("recommendation_score")
    historical_minimum = (
        selection.get("minimum_score") if "recommendation_score" not in selection else None
    )
    cutoff = ""
    if recommendation is not None:
        cutoff = (
            '<p class="discovery-note">'
            "Every record matching at least one taxonomy category is retained. A score of "
            f"{_decimal(recommendation)} or above marks the item as recommended; it does not "
            "control inclusion. Watchlisted artifacts are also retained.</p>"
        )
    elif historical_minimum is not None:
        cutoff = (
            '<p class="discovery-note">This historical scan used '
            f"{_decimal(historical_minimum)} as an inclusion cutoff. Records below it were "
            "not retained.</p>"
        )

    content = (
        header + "".join(component_sections) + limits + cutoff + '<div class="detail-links">'
        '<a class="secondary-link" '
        'href="https://github.com/ktwu01/benchmark-radar/blob/main/src/benchmark_radar/rubric.py" '
        'target="_blank" rel="noopener noreferrer">Read the scoring code ↗</a>'
        "</div>"
    )
    return {
        '<div id="rubric-content"></div>': (f'<div id="rubric-content" data-seed>{content}</div>')
    }


def utility_seeds(dashboard: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Initial content for every utility route's existing dashboard dialog."""
    return {
        "cli": _cli_seed(),
        "cite": _cite_seed(),
        "rubric": _rubric_seed(dashboard),
    }
