"""Score progression and saturation reading (issue #91).

`model_cards.py` answers "which benchmarks do vendors report" by counting
mentions. That is the 上榜 question: a benchmark enters the field's shared
vocabulary when a new organization first puts it in front of readers. It says
nothing about whether the benchmark is still hard.

This module answers the other half, from `data/benchmark_scores.yml`: where a
real number was read out of a real document, how have reported scores moved?
The two readings are published against one time axis so a reader can see the
case the issue asks about -- a benchmark that everyone adopts *and* whose
headroom is closing -- without having to hold two charts in their head.

WHY A HISTORICAL BEST IS NOT A SATURATION VERDICT

The data file states the trap plainly and this module is built to respect it: a
running maximum rises or stays flat by construction, so a flat run is not
evidence of saturation. It is equally consistent with vendors having stopped
reporting the benchmark, with a protocol change, or with nobody having published
since. The benchmark-wide historical-best frontier is therefore a presentation
of record-setting observations, not evidence of a trend or a ceiling. Three
analytical readings are computed and published separately, and none of
them is allowed to be read as the others:

`best`
    The highest comparable value on record, with the date and document that
    produced it. A fact about the corpus, not about the benchmark's ceiling.
`headroom`
    Distance from `best` to the metric's own bound, when the metric has one.
    This is what "saturated" can mean without a trend claim: an instrument
    scored at 92 of a possible 100 has 8 points left whether or not anyone
    reports it again.
`comparable_series`
    Only the runs the join rule actually permits: identical instrument AND
    identical protocol. Everything else stays an unconnected point.

THE SAMPLE IS SMALL AND THE READING SAYS SO

Under the strict join rule this corpus yields very few multi-date runs, and most
of those are one vendor reporting its own successive models. That is a real
property of vendor reporting, not a bug to be engineered around by relaxing the
join, so `evidence_grade` labels each benchmark with what its rows can and
cannot support. A two-point single-vendor run is reported as such and never
described as a field-wide trend.

Scores also stop earlier than mentions do. Every 2026-dated card in the registry
is listed as unread in the data file, so a benchmark can be actively adopted in
2026 with no score after mid-2025. `score_gap_days` measures that lag explicitly,
because a chart drawn without it would show a flat score line beside a climbing
adoption line and invite "saturated" as the explanation when "unread" is the
actual one.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

SCORES_SCHEMA_VERSION = 1

DEFAULT_SCORES_PATH = Path("data/benchmark_scores.yml")

# `direction` exists because not every metric improves upward. Only the two
# meanings the file documents are accepted: an unrecognized direction would
# otherwise be treated as higher-is-better and silently invert a chart.
_DIRECTIONS = ("higher_is_better", "lower_is_better")

# Percent is the only unit in the corpus with a defensible fixed bound, and
# `headroom` is only computed for it. A raw F1 or an Elo has no ceiling this
# module is entitled to invent, so those benchmarks publish `headroom: None`
# rather than a number derived from an assumption.
_BOUNDED_UNITS = {"percent": 100.0}

_REQUIRED_BENCHMARK_FIELDS = ("benchmark_id", "metric", "direction", "unit")
_REQUIRED_SOURCE_FIELDS = (
    "id",
    "title",
    "publisher",
    "document_type",
    "url",
    "benchmarks",
    "retrieved_at",
)
_REQUIRED_RESULT_FIELDS = (
    "benchmark_id",
    "instrument",
    "protocol",
    "model",
    "organization",
    "source_id",
    "reported_at",
    "value",
    "read_from",
)

# How a value was obtained. Mirrors the vocabulary the data file documents;
# a row claiming some other provenance is a data error, not a new category to
# be accepted silently, because the UI grades evidence on this field.
_READ_FROM = ("pdf_text", "html_text", "table_image")
_MEASUREMENT_KINDS = ("reported_self_score", "benchmark_publisher_run")

# Below this many distinct dates a run cannot express a direction over time at
# all: two points define one segment, which is a comparison, not a trend.
_MIN_DATES_FOR_TREND = 3


class BenchmarkScoreError(ValueError):
    """Raised when the curated score file is internally inconsistent."""


def _require(value: Any, fields: tuple[str, ...], *, label: str) -> None:
    if not isinstance(value, dict):
        raise BenchmarkScoreError(f"{label} must be a mapping")
    missing = [
        field
        for field in fields
        if value.get(field) is None or (isinstance(value[field], str) and not value[field].strip())
    ]
    if missing:
        raise BenchmarkScoreError(f"{label} is missing fields: {', '.join(missing)}")


def _require_date(value: Any, *, label: str) -> str:
    """Reject a date the browser cannot format.

    Identical in intent to `model_cards._require_date`, and deliberately not
    imported from it: these values reach `Intl.DateTimeFormat` on the same page,
    where an unparseable one throws and takes every view down with it. The
    duplication is two callers agreeing on one browser constraint, not two
    definitions of a date.
    """
    if type(value) is date:
        return value.isoformat()
    text = str(value)
    if not _ISO_DATE.fullmatch(text):
        raise BenchmarkScoreError(f"{label} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise BenchmarkScoreError(f"{label} is not a real calendar date") from error
    return text


def load_scores(path: Path = DEFAULT_SCORES_PATH) -> dict[str, Any]:
    """Read and validate the curated score file.

    Strict for the same reason the registry loader is: the failure mode of a
    lenient read is not a crash but a plausible-looking chart. A row naming a
    benchmark absent from the `benchmarks` block has no metric, direction or
    unit, so it would plot on an axis whose meaning nobody declared.
    """
    if not path.exists():
        raise BenchmarkScoreError(f"{path}: score file not found")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise BenchmarkScoreError(f"{path}: score file must be a mapping")
    version = document.get("schema_version")
    if version != SCORES_SCHEMA_VERSION:
        raise BenchmarkScoreError(f"{path}: unsupported schema_version {version!r}")

    benchmarks = document.get("benchmarks")
    results = document.get("results")
    if not isinstance(benchmarks, list) or not benchmarks:
        raise BenchmarkScoreError(f"{path}: benchmarks must be a non-empty array")
    if not isinstance(results, list) or not results:
        raise BenchmarkScoreError(f"{path}: results must be a non-empty array")

    metrics: dict[str, dict[str, Any]] = {}
    for index, benchmark in enumerate(benchmarks):
        _require(benchmark, _REQUIRED_BENCHMARK_FIELDS, label=f"{path}: benchmark {index}")
        benchmark_id = str(benchmark["benchmark_id"])
        if benchmark_id in metrics:
            raise BenchmarkScoreError(f"{path}: duplicate benchmark_id {benchmark_id!r}")
        direction = str(benchmark["direction"])
        if direction not in _DIRECTIONS:
            raise BenchmarkScoreError(
                f"{path}: benchmark {benchmark_id!r} direction must be one of "
                f"{', '.join(_DIRECTIONS)}"
            )
        metrics[benchmark_id] = {
            "benchmark_id": benchmark_id,
            "metric": str(benchmark["metric"]),
            "direction": direction,
            "unit": str(benchmark["unit"]),
        }

    source_rows = document.get("sources", [])
    if not isinstance(source_rows, list):
        raise BenchmarkScoreError(f"{path}: sources must be an array")
    sources: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(source_rows):
        label = f"{path}: source {index}"
        _require(source, _REQUIRED_SOURCE_FIELDS, label=label)
        source_id = str(source["id"])
        if source_id in sources:
            raise BenchmarkScoreError(f"{path}: duplicate source id {source_id!r}")
        url = str(source["url"])
        if not url.startswith(("https://", "http://")):
            raise BenchmarkScoreError(f"{label} url must be HTTP(S)")
        source_benchmarks = source["benchmarks"]
        if not isinstance(source_benchmarks, list) or not source_benchmarks:
            raise BenchmarkScoreError(f"{label} benchmarks must be a non-empty array")
        sources[source_id] = {
            "id": source_id,
            "title": str(source["title"]),
            "publisher": str(source["publisher"]),
            "document_type": str(source["document_type"]),
            "url": url,
            "benchmarks": [str(item) for item in source_benchmarks],
            "retrieved_at": _require_date(source["retrieved_at"], label=f"{label} retrieved_at"),
        }

    seen: set[tuple[str, ...]] = set()
    rows: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        label = f"{path}: result {index}"
        _require(result, _REQUIRED_RESULT_FIELDS, label=label)
        benchmark_id = str(result["benchmark_id"])
        if benchmark_id not in metrics:
            raise BenchmarkScoreError(f"{label} references unknown benchmark_id {benchmark_id!r}")
        try:
            value = float(result["value"])
        except (TypeError, ValueError) as error:
            raise BenchmarkScoreError(f"{label} value must be a number") from error
        # YAML's `.nan` and `.inf` parse as floats, and NaN fails every range
        # comparison silently rather than tripping the percent check below. Either
        # would reach `json.dumps` as the bare tokens `NaN` / `Infinity`, which are
        # not valid JSON: the browser's `response.json()` rejects the file and the
        # dashboard's init catch then hides *every* view. One unusable value would
        # take the whole site down, so it is refused here.
        if not math.isfinite(value):
            raise BenchmarkScoreError(f"{label} value must be a finite number")
        unit = metrics[benchmark_id]["unit"]
        # A percent outside 0-100 is a transcription error, and it is worth
        # catching here rather than on the axis: a 964 would rescale the whole
        # chart and make every real value look flat.
        if unit == "percent" and not 0.0 <= value <= 100.0:
            raise BenchmarkScoreError(f"{label} value {value} is outside 0-100 for a percent")
        read_from = str(result["read_from"])
        if read_from not in _READ_FROM:
            raise BenchmarkScoreError(f"{label} read_from must be one of {', '.join(_READ_FROM)}")
        reported_at = _require_date(result["reported_at"], label=f"{label} reported_at")
        score_source = sources.get(str(result["source_id"]))
        row = {
            # Stable within the curated trust domain. The tuple is already the
            # loader's uniqueness contract below, so publishing it gives every
            # downstream consumer one identity for selection, frontier
            # membership and tests instead of rebuilding an ad-hoc key from a
            # subset of fields.
            "observation_id": "\u0000".join(
                (
                    "curated",
                    benchmark_id,
                    str(result["source_id"]),
                    str(result["instrument"]),
                    str(result["protocol"]),
                    str(result["model"]),
                )
            ),
            "benchmark_id": benchmark_id,
            "instrument": str(result["instrument"]),
            "protocol": str(result["protocol"]),
            "model": str(result["model"]),
            "organization": str(result["organization"]),
            "source_id": str(result["source_id"]),
            "reported_at": reported_at,
            "value": value,
            "read_from": read_from,
            "measurement_kind": str(result.get("measurement_kind") or "reported_self_score"),
            "source_title": score_source["title"] if score_source else None,
            "source_url": score_source["url"] if score_source else None,
            "source_document_type": score_source["document_type"] if score_source else None,
            # Present only on a third-party citation: the publisher repeated
            # someone else's self-reported figure. Weaker evidence, and the UI
            # marks it rather than mixing it in.
            "reported_by": str(result["reported_by"]) if result.get("reported_by") else None,
        }
        if row["measurement_kind"] not in _MEASUREMENT_KINDS:
            raise BenchmarkScoreError(
                f"{label} measurement_kind must be one of {', '.join(_MEASUREMENT_KINDS)}"
            )
        # The same model measured twice on one instrument under one protocol in
        # one document is a contradiction: the chart would draw two points at
        # one x with no way to say which is the reading.
        key = (
            benchmark_id,
            row["instrument"],
            row["protocol"],
            row["model"],
            row["source_id"],
        )
        if key in seen:
            raise BenchmarkScoreError(
                f"{label} repeats {row['model']!r} on {row['instrument']!r} "
                f"({row['protocol']!r}) from {row['source_id']!r}"
            )
        seen.add(key)
        rows.append(row)

    return {"benchmarks": metrics, "sources": sources, "results": rows}


def _cross_check_sources(scores: dict[str, Any], registry: dict[str, Any]) -> None:
    """Every score must cite a model card or declared benchmark source.

    Provenance is the whole basis of this layer's claim to be readable-out-of-a
    -document rather than assembled from memory. A `source_id` with no matching
    card or score-source declaration is a citation to nothing: it would render
    as a linkless number that a reader cannot check, which is the one thing this
    dataset promises not to do.
    """
    reported: dict[str, set[str]] = {
        str(card["id"]): {str(ref) for ref in card["benchmarks"]}
        for card in registry["model_cards"]
    }
    reported.update(
        {
            str(source["id"]): {str(ref) for ref in source["benchmarks"]}
            for source in registry.get("source_documents", [])
        }
    )
    source_metadata = {
        str(card["id"]): {
            "title": str(card.get("title") or ""),
            "url": str(card.get("url") or ""),
            "document_type": str(card.get("document_type") or ""),
        }
        for card in registry["model_cards"]
    }
    source_metadata.update(
        {
            str(source["id"]): {
                "title": str(source.get("title") or ""),
                "url": str(source.get("url") or ""),
                "document_type": str(source.get("document_type") or ""),
            }
            for source in registry.get("source_documents", [])
        }
    )
    unknown = sorted({row["source_id"] for row in scores["results"]} - reported.keys())
    if unknown:
        raise BenchmarkScoreError(
            "score rows cite source_ids absent from the model card registry and score source "
            f"registry: {', '.join(unknown)}"
        )
    for row in scores["results"]:
        metadata = source_metadata[row["source_id"]]
        if all(metadata.values()):
            row["source_title"] = metadata["title"]
            row["source_url"] = metadata["url"]
            row["source_document_type"] = metadata["document_type"]
    registry_ids = {str(benchmark["id"]) for benchmark in registry["benchmarks"]}
    stray = sorted(set(scores["benchmarks"]) - registry_ids)
    if stray:
        raise BenchmarkScoreError(
            "score file declares benchmarks absent from the model card registry: "
            f"{', '.join(stray)}"
        )

    # Existence of the cited card is not enough. A `source_id` mistyped to a
    # different real card passes the check above while attributing the score to a
    # document that never reported that benchmark -- a published number with false
    # provenance, which is worse than a missing one because it looks checkable.
    # The registry already records which benchmarks each card reports, so the pair
    # is verifiable rather than taken on trust.
    mismatched = sorted(
        f"{row['source_id']} does not report {row['benchmark_id']}"
        for row in scores["results"]
        if row["benchmark_id"] not in reported[row["source_id"]]
    )
    if mismatched:
        raise BenchmarkScoreError(
            "score rows cite documents that do not report the benchmark they score: "
            f"{', '.join(dict.fromkeys(mismatched))}"
        )


def _rows_on(rows: list[dict[str, Any]], reported_at: str) -> list[dict[str, Any]]:
    """The rows sharing one date, for picking a series endpoint by value."""
    return [row for row in rows if row["reported_at"] == reported_at]


def _best_row(rows: list[dict[str, Any]], direction: str) -> dict[str, Any]:
    """The strongest value on record, respecting the metric's direction."""
    reverse = direction == "higher_is_better"
    return sorted(
        rows,
        key=lambda row: (row["value"], row["reported_at"]),
        reverse=reverse,
    )[0]


def _series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group rows into the runs the join rule permits a line through.

    The key is (instrument, protocol) exactly as the data file specifies. A
    series is published with `dated_points` alongside its length because those
    two numbers differ in the way that matters: five rows sharing one date are a
    comparison table from one document, and drawing them as a progression would
    invent a trend out of a single publication.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["instrument"], row["protocol"])].append(row)

    series = []
    for (instrument, protocol), members in grouped.items():
        ordered = sorted(
            members,
            key=lambda row: (row["reported_at"], row["organization"], row["model"]),
        )
        dates = {row["reported_at"] for row in ordered}
        organizations = {row["organization"] for row in ordered}
        series.append(
            {
                "instrument": instrument,
                "protocol": protocol,
                "points": ordered,
                "point_count": len(ordered),
                "dated_points": len(dates),
                "organization_count": len(organizations),
                # A run whose every row comes from one publisher is that
                # publisher's own model line. It is legitimate evidence about
                # that vendor and not evidence about the field, so the
                # distinction travels with the series rather than being
                # recovered in the browser.
                "single_organization": len(organizations) == 1,
                "first_reported_at": ordered[0]["reported_at"],
                "last_reported_at": ordered[-1]["reported_at"],
                # Only a run crossing at least two dates can express movement.
                "connectable": len(dates) >= 2,
            }
        )

    series.sort(
        key=lambda item: (
            -item["dated_points"],
            -item["point_count"],
            item["instrument"],
            item["protocol"],
        )
    )
    return series


def _span_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _evidence_grade(series: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """State what this benchmark's rows can and cannot support.

    Written as a grade rather than a boolean because the useful distinctions are
    not binary: a run can be long enough to show movement but come from a single
    vendor, which supports "this vendor's models improved" and not "the field
    improved". The UI prints `supports` and `does_not_support` verbatim, so the
    honest scope of every chart is authored here and tested, not phrased ad hoc
    in JavaScript.
    """
    trend_series = [item for item in series if item["dated_points"] >= _MIN_DATES_FOR_TREND]
    multi_org_trend = [item for item in trend_series if not item["single_organization"]]
    connectable = [item for item in series if item["connectable"]]

    if multi_org_trend:
        return {
            "id": "multi_organization_trend",
            "label": "Comparable run across organizations",
            "supports": (
                "At least one run holds instrument and protocol fixed across three or more "
                "dates and more than one organization, so its movement is not one vendor's "
                "own model line."
            ),
            "does_not_support": (
                "Vendors publish the benchmarks they do well on, so even a comparable run "
                "measures reporting choice as well as capability."
            ),
        }
    if trend_series:
        return {
            "id": "single_organization_trend",
            "label": "Comparable run, one organization",
            "supports": (
                "One publisher reported this instrument and protocol on three or more dates, "
                "which shows how that publisher's own models moved."
            ),
            "does_not_support": (
                "Nothing about the field. A single vendor's model line cannot separate "
                "capability gains from changes in how that vendor evaluates."
            ),
        }
    if connectable:
        return {
            "id": "paired_comparison",
            "label": "Paired comparison only",
            "supports": (
                "Two dates share an instrument and protocol, so the pair is a like-for-like "
                "before-and-after."
            ),
            "does_not_support": (
                "A direction over time. Two points define one segment; a third would be "
                "needed before the word trend applies."
            ),
        }
    dates = {row["reported_at"] for row in rows}
    if len(dates) == 1 and len(rows) >= 2:
        return {
            "id": "same_day_comparison",
            "label": "Same-day comparison",
            "supports": (
                "Multiple values are readable from documents on one date, so the table "
                "supports a cross-system snapshot comparison."
            ),
            "does_not_support": (
                "Any movement over time. All observations share one date, so this is a "
                "leaderboard snapshot rather than a longitudinal series."
            ),
        }
    if len(dates) >= 2:
        return {
            "id": "unjoinable",
            "label": "No comparable run",
            "supports": ("Each value is readable in its own document at its own protocol."),
            "does_not_support": (
                "Any comparison between these numbers. No two rows share both an instrument "
                "and a protocol, so every point stands alone."
            ),
        }
    return {
        "id": "single_reading",
        "label": "Single reading",
        "supports": "One recorded value, readable in the document that printed it.",
        "does_not_support": (
            "Any movement at all. There is one date on record for this benchmark."
        ),
    }


def _saturation(
    rows: list[dict[str, Any]],
    metric: dict[str, Any],
    series: list[dict[str, Any]],
) -> dict[str, Any]:
    """The headroom reading, and the gain behind it when a run supports one.

    `headroom` is the part that carries no trend claim: it is the distance from
    the best recorded value to the metric's own bound. `best_gain` is reported
    only from a connectable run, and it is labelled with the run it came from so
    a reader can see whether the gain is one vendor's or the field's.
    """
    direction = metric["direction"]
    best = _best_row(rows, direction)
    bound = _BOUNDED_UNITS.get(metric["unit"])
    headroom = None
    if bound is not None:
        headroom = round(
            bound - best["value"] if direction == "higher_is_better" else best["value"],
            0 if float(bound).is_integer() and float(best["value"]).is_integer() else 2,
        )

    gain = None
    for item in series:
        if not item["connectable"]:
            continue
        # Endpoints are chosen by a stated policy, not by list position. `points`
        # is ordered by (date, organization, model), so when a date carries more
        # than one model -- a document comparing several at once -- the endpoint
        # fell out lexically: renaming a model could change `improvement` and
        # trigger or suppress a `fast_gain` finding while every value and date
        # stayed identical. The policy is the best value on each endpoint date,
        # which is reproducible from the data alone and is the reading a
        # progression is asking for.
        first = _best_row(_rows_on(item["points"], item["first_reported_at"]), direction)
        last = _best_row(_rows_on(item["points"], item["last_reported_at"]), direction)
        delta = last["value"] - first["value"]
        if direction == "lower_is_better":
            delta = -delta
        elapsed = _span_days(first["reported_at"], last["reported_at"])
        candidate = {
            "instrument": item["instrument"],
            "protocol": item["protocol"],
            # Named only when the run has exactly one publisher, so a consumer
            # attributing the gain to a vendor cannot do so for a run that
            # crossed vendors.
            "organization": first["organization"] if item["single_organization"] else None,
            "from_value": first["value"],
            "to_value": last["value"],
            "from_reported_at": first["reported_at"],
            "to_reported_at": last["reported_at"],
            "from_model": first["model"],
            "to_model": last["model"],
            "improvement": round(delta, 2),
            "elapsed_days": elapsed,
            "single_organization": item["single_organization"],
            "dated_points": item["dated_points"],
        }
        # The longest-running comparable series wins, then the largest move.
        # Picking the largest move first would surface a two-point jump over a
        # four-date run that actually shows a shape.
        if gain is None or (item["dated_points"], abs(delta)) > (
            gain["dated_points"],
            abs(gain["improvement"]),
        ):
            gain = candidate

    return {
        "best_value": best["value"],
        "best_model": best["model"],
        "best_organization": best["organization"],
        "best_reported_at": best["reported_at"],
        "best_source_id": best["source_id"],
        "best_is_third_party": best["reported_by"] is not None,
        "bound": bound,
        "headroom": headroom,
        "best_gain": gain,
    }


def _historical_best_frontier(
    rows: list[dict[str, Any]],
    direction: str,
) -> dict[str, Any]:
    """Normalize one benchmark's visible scores into its running best.

    The scope is deliberately every valid observation rendered for this
    benchmark, regardless of protocol. Protocol remains attached to each
    observation and still governs like-for-like comparisons in ``series``;
    it does not secretly redefine a chart labelled as the benchmark-wide
    historical best.

    Readings on one publication date collapse to the directional best before
    records are selected. Equal later values are not new records. A stable
    observation id breaks an exact same-date/value tie without depending on
    YAML row order.
    """
    best_by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = best_by_date.get(row["reported_at"])
        if current is None:
            best_by_date[row["reported_at"]] = row
            continue
        improves = (
            row["value"] > current["value"]
            if direction == "higher_is_better"
            else row["value"] < current["value"]
        )
        if improves or (
            row["value"] == current["value"] and row["observation_id"] < current["observation_id"]
        ):
            best_by_date[row["reported_at"]] = row

    points: list[dict[str, Any]] = []
    running_best: float | None = None
    for reported_at in sorted(best_by_date):
        row = best_by_date[reported_at]
        improves = running_best is None or (
            row["value"] > running_best
            if direction == "higher_is_better"
            else row["value"] < running_best
        )
        if not improves:
            continue
        running_best = row["value"]
        points.append(
            {
                "observation_id": row["observation_id"],
                "reported_at": row["reported_at"],
                "value": row["value"],
                "model": row["model"],
                "organization": row["organization"],
                "source_id": row["source_id"],
            }
        )

    return {
        "definition": "running_best_of_all_rendered_observations",
        "date_kind": "document_publication",
        "direction": direction,
        "tie_policy": "strict_improvement",
        "points": points,
    }


def score_progression(
    scores: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the per-benchmark score layer the dashboard draws.

    Keyed by benchmark_id so the browser can join it against the adoption
    ranking it already has, rather than being handed a second ranking that could
    disagree with the first about what a benchmark is.
    """
    if registry is not None:
        _cross_check_sources(scores, registry)

    by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scores["results"]:
        by_benchmark[row["benchmark_id"]].append(row)

    latest_overall = max(row["reported_at"] for row in scores["results"])

    benchmarks = {}
    for benchmark_id, rows in by_benchmark.items():
        metric = scores["benchmarks"][benchmark_id]
        series = _series(rows)
        dates = sorted({row["reported_at"] for row in rows})
        historical_best_frontier = _historical_best_frontier(rows, metric["direction"])
        benchmarks[benchmark_id] = {
            "benchmark_id": benchmark_id,
            "metric": metric["metric"],
            "direction": metric["direction"],
            "unit": metric["unit"],
            "observation_count": len(rows),
            "dated_observation_count": len(dates),
            "organization_count": len({row["organization"] for row in rows}),
            "first_reported_at": dates[0],
            "last_reported_at": dates[-1],
            "third_party_count": sum(1 for row in rows if row["reported_by"]),
            "series": series,
            "comparable_series_count": sum(1 for item in series if item["connectable"]),
            "saturation": _saturation(rows, metric, series),
            "historical_best_frontier": historical_best_frontier,
            "evidence": _evidence_grade(series, rows),
            "observations": sorted(
                rows,
                key=lambda row: (row["reported_at"], row["organization"], row["model"]),
            ),
        }

    return {
        "schema_version": SCORES_SCHEMA_VERSION,
        "benchmark_count": len(benchmarks),
        "observation_count": len(scores["results"]),
        "organizations": sorted({row["organization"] for row in scores["results"]}),
        "first_reported_at": min(row["reported_at"] for row in scores["results"]),
        "last_reported_at": latest_overall,
        "benchmarks": benchmarks,
        "measures": (
            "Scores read verbatim from cited documents, connected only where instrument "
            "and protocol are identical. The historical-best frontier spans every displayed "
            "score; it records new benchmark-wide highs or lows but is not a comparable "
            "series or a saturation verdict. A value's absence is not a zero and a flat run "
            "is equally consistent with vendors having stopped reporting the benchmark."
        ),
        "join_rule": (
            "Two values may be connected only when both the instrument and the protocol "
            "match exactly. An unstated condition is never treated as equal to another "
            "unstated condition."
        ),
    }


def build_score_progression(
    path: Path = DEFAULT_SCORES_PATH,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return score_progression(load_scores(path), registry)
