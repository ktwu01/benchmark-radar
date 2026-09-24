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

import math
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .citation import apa_citation
from .site_shell import SOURCE_LABELS, esc


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
# below the ranking. It is the caveat that keeps a document count from being
# read as a quality score, so a page that ships the ranking ships it too.
LEADERBOARD_TOP_NOTE = "Open the source-document list below to trace each count to its citations."
# The window the leaderboard opens on (issue #530), keyed as the payload keys it.
LATEST_WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}


# The slider's default position in site/index.html. The seed must render the
# same cutoff the browser starts on, or the first paint would change on hydrate.
DEFAULT_SCORE_CUTOFF = 70


def _display_value(value: float) -> str:
    """One decimal, matching scoreSummaryLabel in app.js so seeds and renders agree.

    Half-up rather than Python's default banker's rounding, because
    toLocaleString rounds half-up; without this a 0.95 prints as "1" in the
    browser and "0.9" in the seed. Rounding is display only: a 69.95 shows as
    "70" and still belongs under the <70 cutoff, which filters on the raw value.
    """
    rounded = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:,f}".rstrip("0").rstrip(".")


def _info_disclosure(text: str) -> str:
    """The markup infoDisclosure emits."""
    return (
        '<details class="info-disclosure">'
        '<summary class="info-disclosure-toggle" aria-label="What does this source record?">'
        "i</summary>"
        f'<p class="info-disclosure-body">{esc(text)}</p>'
        "</details>"
    )


# The signals latestReleaseRow lists, in its order and with its labels.
_LATEST_SIGNALS = (
    ("github_stars", "GitHub stars"),
    ("hf_paper_upvotes", "Hugging Face paper upvotes"),
    ("hf_dataset_downloads", "Hugging Face dataset downloads, last 30 days"),
)
_LATEST_EMPTY_ANCHOR = (
    '<p class="empty-state latest-releases-empty" id="latest-releases-empty" '
    'aria-live="polite" hidden></p>'
)
_LATEST_NOTE_ANCHOR = '<p class="section-note" id="latest-releases-note" aria-live="polite"></p>'
_LATEST_RANKED_NOTE = (
    "{ranked} of {total} releases in this window are ranked; "
    "the rest are listed with limited signals."
)
_LATEST_METHOD_NOTE = (
    "Ranking {method}: {signals}, each normalized as log1p(value) / log1p(window maximum) "
    "and summed to a 0 to 100 score. A release is ranked only when enough of its weight "
    "comes from fresh, durable signals; the rest are listed with limited signals. Dataset "
    "downloads are a rolling 30-day figure, never a cumulative total. Stars come from the "
    "benchmark's own repository, never a parent framework. Window {start} to {end}, UTC."
)


def _utc_medium_date(value: Any) -> str:
    """Match formatDate(value, {dateStyle: "medium"}): the UTC calendar day."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return _medium_date(str(value or "")[:10])
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return _medium_date(parsed.date().isoformat())


def _percent(value: Any) -> str:
    """Match Math.round(Number(value) * 100): half rounds up, never to even."""
    scaled = Decimal(str(float(value) * 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(scaled)}%"


def _js_number(value: Any) -> str:
    """Match String(number) for the integral and plain decimal scores the engine emits."""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def _safe_http_url(value: Any) -> str:
    """Mirror safeHttpUrl in app.js: the normalized href, or "" if not http(s).

    The renderer builds its link from `new URL(value).href`, which lowercases
    the scheme and host and supplies a "/" path. Prefix-testing the raw string
    instead looked equivalent and was not: the engine accepts `HTTPS://Host/x`
    (release_leaderboard casefolds before comparing), and for that input the
    seed emitted no link at all while the renderer emitted one, so a crawler
    and a reader without scripts lost the provenance link a scripted reader
    got. That is the one thing a seed may never do.
    """
    parsed = urlsplit(str(value or ""))
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            parsed.query,
            parsed.fragment,
        )
    )


def _latest_signal_text(component: dict[str, Any]) -> str:
    """The reading latestSignalText prints for one component."""
    status = component.get("status") or "unknown"
    value = component.get("value")
    if status == "unavailable":
        return "unavailable"
    if value is None:
        return "not observed"
    number = _num(value)
    if status == "stale":
        since = component.get("last_successful_date")
        return f"{number} · stale since {since}" if since else f"{number} · stale"
    if status != "fresh":
        since = component.get("last_successful_date")
        return f"{number} · unverified since {since}" if since else f"{number} · unverified"
    return number


def _latest_method_note(payload: dict[str, Any], window: dict[str, Any]) -> str:
    """The (i) text latestReleasesMethodNote composes from the published weights."""
    entries = window.get("entries") or []
    parts = []
    for key, label in _LATEST_SIGNALS:
        weight = next(
            (
                entry["components"][key].get("weight")
                for entry in entries
                if "weight" in ((entry.get("components") or {}).get(key) or {})
            ),
            None,
        )
        parts.append(label if weight is None else f"{_percent(weight)} {label}")
    return _LATEST_METHOD_NOTE.format(
        method=payload.get("method_version") or "",
        signals=", ".join(parts),
        start=_utc_medium_date(window.get("window_start")),
        end=_utc_medium_date(window.get("window_end")),
    )


def _latest_release_row(entry: dict[str, Any], top: float) -> str:
    """One row, as latestReleaseRow draws it: the rank line and its disclosure."""
    ranked = entry.get("status") == "ranked" and bool(entry.get("rank"))
    score = entry.get("score")
    confidence = str(entry.get("confidence") or "").lower()
    width = f"{float(score) / top * 100:.1f}" if score is not None and top else "0"
    rank = (
        f'<span class="leaderboard-top-rank">{int(entry["rank"]):02}</span>'
        if ranked
        else '<span class="leaderboard-top-rank"><span aria-hidden="true">—</span>'
        '<span class="visually-hidden">unranked</span></span>'
    )
    release_date = entry.get("release_date")
    date = (
        f'<small class="latest-release-date">released {esc(_utc_medium_date(release_date))}</small>'
        if release_date
        else ""
    )
    bar_class = "leaderboard-top-bar-fill" + ("" if ranked else " latest-release-bar-limited")
    score_text = esc(_js_number(score)) if score is not None else "no score"
    pill = (
        f'<span class="pill pill-confidence pill-confidence-{esc(confidence)}">'
        f"{esc(confidence)}</span>"
        if confidence
        else ""
    )
    signals = []
    for key, label in _LATEST_SIGNALS:
        component = (entry.get("components") or {}).get(key) or {}
        url = _safe_http_url(component.get("source_url"))
        link = (
            f'<a class="latest-release-source" href="{esc(url)}" target="_blank" '
            'rel="noopener noreferrer">source ↗</a>'
            if url
            else ""
        )
        weight = component.get("weight")
        weight_text = (
            f'<small class="latest-release-weight">weight {_percent(weight)}</small>'
            if weight is not None
            else ""
        )
        signals.append(
            f'<div class="latest-release-signal"><dt>{esc(label)}</dt>'
            f"<dd><span>{esc(_latest_signal_text(component))}</span>{link}{weight_text}</dd></div>"
        )
    meta = " · ".join(
        part
        for part in (
            f"Coverage {_decimal(entry.get('coverage') or 0)}",
            f"confidence {confidence}" if confidence else "",
            "" if ranked else "limited signals: not enough fresh durable signal to rank",
        )
        if part
    )
    purpose = entry.get("purpose")
    purpose_html = f'<p class="latest-release-purpose">{esc(purpose)}</p>' if purpose else ""
    return (
        '<li class="latest-release"><details class="latest-release-details" '
        f'data-artifact="{esc(entry.get("canonical_artifact_id") or "")}">'
        '<summary class="leaderboard-top-row latest-release-summary">'
        f"{rank}"
        f'<span class="leaderboard-top-name"><span>{esc(entry.get("name") or "")}</span>'
        f"{date}</span>"
        f'<span class="leaderboard-top-bar"><span class="{bar_class}" style="width:{width}%">'
        "</span></span>"
        f'<span class="leaderboard-top-count"><span>{score_text}</span>{pill}</span>'
        "</summary>"
        f'<div class="latest-release-body">{purpose_html}'
        f'<dl class="latest-release-signals">{"".join(signals)}</dl>'
        f'<p class="latest-release-meta">{esc(meta)}</p></div>'
        "</details></li>"
    )


def _latest_releases_seed(dashboard: dict[str, Any]) -> dict[str, str]:
    """What renderLatestReleases draws for the payload's default window.

    The page opens on this ranking (issue #530), so a crawler or a reader
    without scripts must see the rows the script would draw, each with the
    inputs behind its rank, the method note, and, when the window holds
    nothing, the same empty state with its way out. A build without the
    ranking seeds nothing here and the script says so.
    """
    payload = dashboard.get("latest_releases_leaderboard") or {}
    windows = payload.get("windows") or {}
    window_key = payload.get("default_window") or "30d"
    window = windows.get(window_key) or {}
    if not payload or not window:
        return {}
    days = LATEST_WINDOW_DAYS.get(window_key, window_key)
    seeds = {
        '<span class="latest-releases-window" id="latest-releases-window">· 30 days</span>': (
            '<span class="latest-releases-window" id="latest-releases-window" data-seed>'
            f"· {days} days</span>"
        ),
    }
    if window.get("window_start"):
        seeds['<span id="latest-releases-info"></span>'] = (
            '<span id="latest-releases-info" data-seed>'
            f"{_info_disclosure(_latest_method_note(payload, window))}</span>"
        )
    entries = window.get("entries") or []
    if not entries:
        # latestReleasesEmptyState: wider windows are offered unless they are
        # known to be empty too; past the widest, the adoption view.
        keys = list(LATEST_WINDOW_DAYS)
        wider = [
            key
            for key in keys[keys.index(window_key) + 1 :]
            if key not in windows or (windows[key] or {}).get("entries")
        ]
        actions = [
            '<button class="latest-releases-empty-action" type="button" '
            f'data-lwindow="{key}">Try {LATEST_WINDOW_DAYS[key]} days</button>'
            for key in wider
        ]
        if not wider:
            actions.append(
                '<button class="latest-releases-empty-action" type="button" '
                'data-lmode="adoption">See model-card adoption instead</button>'
            )
        seeds[_LATEST_EMPTY_ANCHOR] = (
            '<p class="empty-state latest-releases-empty" id="latest-releases-empty" '
            'aria-live="polite" data-seed>'
            f"No benchmark released in the last {days} days has a measurable attention "
            f"signal yet. {''.join(actions)}</p>"
        )
        return seeds
    scores = [float(entry["score"]) for entry in entries if entry.get("score") is not None]
    top = max(scores) if scores else 0.0
    rows = "".join(_latest_release_row(entry, top) for entry in entries)
    seeds[
        '<ol class="leaderboard-top-list latest-releases-list" id="latest-releases-list"></ol>'
    ] = (
        '<ol class="leaderboard-top-list latest-releases-list" id="latest-releases-list" '
        f"data-seed>{rows}</ol>"
    )
    ranked = _num(window.get("ranked_count") or 0)
    total = _num(window.get("total_cohort_count") or 0)
    seeds[_LATEST_NOTE_ANCHOR] = (
        '<p class="section-note" id="latest-releases-note" aria-live="polite" data-seed>'
        f"{esc(_LATEST_RANKED_NOTE.format(ranked=ranked, total=total))}</p>"
    )
    return seeds


def _leaderboard_seed(
    dashboard: dict[str, Any], catalog_index: list[dict[str, Any]]
) -> dict[str, str]:
    """The top rows, the measures note and the caveat renderLeaderboardTop emits."""
    board = dashboard.get("model_card_leaderboard") or {}
    ranked = [entry for entry in (board.get("entries") or []) if (entry.get("card_count") or 0) > 0]
    entries = ranked[:LEADERBOARD_TOP_LIMIT]
    ranking_seed = {
        **_latest_releases_seed(dashboard),
        **_score_ranking_seed(dashboard, catalog_index),
    }
    if not entries:
        return ranking_seed
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
        f"{esc(_metric_label(entry.get('card_count'), 'source document'))}</span>"
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
    return {**seed, **ranking_seed}


def _browser_score_summary(record: dict[str, Any]) -> dict[str, Any] | None:
    """Match scoreBrowserSummary: preserve source values except declared error percentages."""
    summary = record.get("score_summary")
    if not summary:
        return None
    minimum = summary.get("raw_min")
    maximum = summary.get("raw_max")
    if (
        record.get("unit") == "percent"
        and (record.get("score_direction") or record.get("direction")) == "lower_is_better"
        and isinstance(minimum, (int, float))
        and isinstance(maximum, (int, float))
        and 0 <= minimum <= maximum <= 100
    ):
        return {**summary, "display_max": 100 - minimum, "normalized_from_lower": True}
    return summary


def _benchmark_date(
    record: dict[str, Any], entry: dict[str, Any] | None = None
) -> tuple[str | None, str | None]:
    """Mirror skyline.js: release, score publication, then a labelled score-date proxy."""

    def valid(value: Any) -> bool:
        try:
            return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False

    for released in [(entry or {}).get("released"), record.get("released")]:
        if valid(released):
            return released, "Released"
    reports = [record.get("first_reported_at"), record.get("first_score_reported_at")]
    reports += [
        row.get("reported_at") or row.get("reported_date")
        for row in record.get("observations") or []
        if isinstance(row.get("value"), (int, float))
        and not isinstance(row["value"], bool)
        and math.isfinite(row["value"])
        and row.get("date_precision") not in {"model_announcement", "crawl"}
    ]
    first = min((value for value in reports if valid(value)), default=None)
    if first:
        return first, "First LLM score reported"
    first_record = record.get("first_score_record") or {}
    if first_record.get("date_precision") in {
        "day",
        "document_publication",
        "score_publication",
        "model_announcement",
    } and valid(first_record.get("reported_at")):
        label = (
            "First dated LLM score (model-release proxy)"
            if first_record.get("date_precision") == "model_announcement"
            else "First LLM score reported"
        )
        return first_record["reported_at"], label
    return None, None


def _catalog_score_rows(catalog_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The complete population and ordering used by scoreBrowseRows."""
    rows = [
        {
            "id": record["slug"],
            "name": record["name"],
            "source": record["source"],
            "summary": _browser_score_summary(record),
            "date": _benchmark_date(record),
        }
        for record in catalog_index
    ]
    rows.sort(key=lambda row: (-(row["summary"] or {}).get("numeric_count", 0), row["id"]))
    return rows


def _has_reported_score(row: dict[str, Any]) -> bool:
    summary = row["summary"] or {}
    value = summary.get("display_max")
    return (
        summary.get("numeric_count", 0) > 0
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _score_browser_seed(
    dashboard: dict[str, Any], catalog_index: list[dict[str, Any]]
) -> dict[str, str]:
    """Saturation's empty-search browser, with the shared default cutoff."""
    if not catalog_index:
        return {}
    rows = [
        row
        for row in _catalog_score_rows(catalog_index)
        if not _has_reported_score(row) or row["summary"]["display_max"] < DEFAULT_SCORE_CUTOFF
    ]
    shown = rows[:50]
    content = ""
    for index, row in enumerate(shown):
        label = SOURCE_LABELS.get(row["source"], row["source"])
        dated, basis = row["date"]
        date_label = f"{basis} {_medium_date(dated)}" if dated else "Date unknown"
        facts = f"{label} · {date_label}"
        if not _has_reported_score(row):
            facts += " · No score reported"
        pressed = "true" if index == 0 else "false"
        content += (
            '<button class="benchmark-result score-browse-result" '
            f'type="button" aria-pressed="{pressed}">'
            f'<span class="benchmark-result-name">{esc(row["name"])}</span>'
            f'<span class="benchmark-result-facts">{esc(facts)}</span>'
            "</button>"
        )
    if not rows:
        content = (
            '<p class="empty-state">No benchmarks match these filters.</p>'
            '<button class="clear-button" type="button">All</button>'
        )
    seeds = {
        '<div id="benchmark-search-results"></div>': (
            f'<div id="benchmark-search-results" data-seed>{content}</div>'
        ),
        '<p id="benchmark-search-status" class="benchmark-search-status"></p>': (
            '<p id="benchmark-search-status" class="benchmark-search-status" data-seed>'
            f"{len(shown):,} of {len(rows):,} matches</p>"
        ),
    }
    if len(rows) > 50:
        button = (
            '<button id="benchmark-search-more" class="clear-button" type="button" '
            'data-i18n="Show more" hidden>Show more</button>'
        )
        seeds[button] = button.replace(" hidden>", " data-seed>")
    return seeds


def _score_ranking_seed(
    dashboard: dict[str, Any], catalog_index: list[dict[str, Any]]
) -> dict[str, str]:
    """The score ranking keeps its scored 2024+ cohort, independent of the slider."""
    rows = [
        row
        for row in _catalog_score_rows(catalog_index)
        if _has_reported_score(row) and (row["date"][0] is None or row["date"][0] >= "2024-01-01")
    ]
    if not rows:
        return {}
    maximum = rows[0]["summary"]["numeric_count"]
    ranking = ""
    for rank, row in enumerate(rows[:5], 1):
        summary = row["summary"]
        value = _display_value(summary["display_max"])
        unit = summary.get("unit")
        suffix = "%" if unit == "percent" else f" {unit}" if unit else ""
        label = SOURCE_LABELS.get(row["source"], row["source"])
        count = _metric_label(summary["numeric_count"], "data point")
        width = summary["numeric_count"] / maximum * 100
        ranking += (
            '<li class="leaderboard-top-row">'
            f'<span class="leaderboard-top-rank">{rank:02}</span>'
            '<span class="leaderboard-top-name">'
            '<button class="score-ranking-link" type="button" aria-pressed="false">'
            f"<span>{esc(row['name'])}</span>"
            f"<small>{esc(label + ' · ' + value + suffix)}</small></button></span>"
            '<span class="leaderboard-top-bar"><span class="leaderboard-top-bar-fill" '
            f'style="width:{width:.1f}%"></span></span>'
            f'<span class="leaderboard-top-count">{esc(count)}</span></li>'
        )
    seeds = {
        '<ol class="leaderboard-top-list" id="score-ranking-list"></ol>': (
            f'<ol class="leaderboard-top-list" id="score-ranking-list" data-seed>{ranking}</ol>'
        ),
    }
    if len(rows) > 5:
        button = (
            '<button id="score-ranking-more" class="leaderboard-top-more" type="button" '
            'data-i18n="Show more" hidden>Show more</button>'
        )
        seeds[button] = button.replace(" hidden>", " data-seed>")
    return seeds


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
    dashboard: dict[str, Any],
    palette: tuple[dict[str, str], list[str]],
    catalog_index: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, str]]:
    """Every view's seed, keyed by view. An empty dict means nothing to publish."""
    return {
        "leaderboard": _leaderboard_seed(dashboard, catalog_index or []),
        "saturation": _score_browser_seed(dashboard, catalog_index or []),
        "trends": _trends_seed(dashboard, palette),
        "map": _map_seed(dashboard),
    }


# --- Utility dialogs ----------------------------------------------------------

# These are the verbatim public values used by openCite and openCli in app.js.
# Tests compare both renderers so a change to either copy fails instead of
# quietly giving a crawler a different setup prompt or citation than a reader.
CITE_DOI_URL = "https://arxiv.org/abs/2609.11115"
CITE_CFF_URL = "https://github.com/ktwu01/benchmark-radar/blob/main/CITATION.cff"
# The site dialog and the CLI reminder share citation.py's title and author
# list, so the APA a reader copies is the APA an agent is asked for.
CITE_APA = apa_citation()
CITE_BIBTEX = """@misc{wu2026benchmarkradarlivingdatabase,
      title={Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and Evaluation},
      author={Koutian Wu and Junjie Zhou and Ergan Shang and Jiayu Wang and
              Pengqian Han and Junkai Wang and Wanghan Xu},
      year={2026},
      eprint={2609.11115},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2609.11115},
}"""

# The catalogs the score layer reads. LLM Stats asks for credit visible to
# readers with a link back, and the citation card is where a reader goes to ask
# where this data came from, so the credit lives there rather than in a file
# only contributors open.
SCORE_SOURCE_LINKS: tuple[tuple[str, str], ...] = (
    ("LLM Stats", "https://llm-stats.com"),
    ("Artificial Analysis", "https://artificialanalysis.ai"),
    ("OpenCompass Hub", "https://hub.opencompass.org.cn"),
)
CITE_CREDIT_LEAD = "Benchmark score data comes from lab model reports and from"

CLI_SKILL_URL = (
    "https://github.com/ktwu01/benchmark-radar/blob/main/skills/benchmark-radar/SKILL.md"
)
CLI_SKILL_INSTALL = "npx skills add ktwu01/benchmark-radar"
CLI_INSTALL_LABEL = "Install"


def _copy_block(label: str, value: str, hint: str, hide_label: bool = False) -> str:
    """The non-interactive form of copyBlock in app.js.

    The button already contains its label, value and fallback instruction. The
    runtime only has to add clipboard behavior; a failed or disabled script
    never leaves behind an empty button.
    """
    label_class = "copy-label visually-hidden" if hide_label else "copy-label"
    return (
        '<section class="copy-block">'
        f'<h3 class="{label_class}">{esc(label)}</h3>'
        f'<button class="copy-target" type="button" aria-label="{esc(hint)}: {esc(label)}">'
        f'<code class="copy-text">{esc(value)}</code>'
        f'<span class="copy-status">{esc(hint)}</span>'
        "</button>"
        "</section>"
    )


def _cite_credit() -> str:
    """The sentence both renderers draw, so the seed and app.js cannot drift."""
    links = [
        f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(name)}</a>'
        for name, url in SCORE_SOURCE_LINKS
    ]
    joined = f"{', '.join(links[:-1])} and {links[-1]}"
    return f"{esc(CITE_CREDIT_LEAD)} {joined}."


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
        f'<p class="cite-credit">{_cite_credit()}</p>'
    )
    return {'<div id="cite-content"></div>': (f'<div id="cite-content" data-seed>{content}</div>')}


def _cli_seed() -> dict[str, str]:
    content = (
        '<p class="detail-source">Benchmark Radar</p>'
        '<h2 class="detail-title cli-title" id="cli-title">'
        "Query it locally (CLI version)</h2>"
        '<div class="copy-blocks">'
        f"{_copy_block(CLI_INSTALL_LABEL, CLI_SKILL_INSTALL, 'Click to copy', True)}"
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
