"""One reported score per model and benchmark record, for the Models matrix.

benchmark-radar.com's Model Evals compared models in a "model x benchmark"
matrix with a shared-benchmark average. This module builds the data that view
reads, from the same catalog shards every other surface reads (one evidence
path, as ``models_registry.build_registry``), and holds the rules the page
applies, so the Python seed and ``assets/app.js`` cannot drift:

1. A comparison uses only the benchmarks every compared model has a score on.
   A model that reported only easy benchmarks does not get a higher average.
2. A score enters an average on its series' direction and scale. Raw values mix
   Elo (1577), fractions (0.6) and percentages (74.7); a series'
   ``display_multiplier`` puts it on its display scale, and only a series whose
   source states a 0-100 scale (a percent unit, or a declared maximum the
   multiplier puts at 100) is averaged, flipped when lower is better. The
   multiplier alone is display convention, not evidence of a percentage
   (score_summary), so such a series, like Elo, dollar and point scales, is
   shown in its cells and left out of averages.
3. Every average states how many shared benchmarks it uses.

Every source is read the same way: none is preferred or discounted.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .models_registry import build_registry

SCHEMA_VERSION = 1
DEFAULT_SCORES_OUTPUT = Path("site/data/model-scores.json")
DIRECTIONS = ("higher_is_better", "lower_is_better")


def score_scale(series: dict[str, Any]) -> tuple[float, bool]:
    """A series' display multiplier, and whether its source states a 0-100 scale.

    The multiplier is the series' own ``display_multiplier``. It is display
    convention only (score_summary: it "never establishes a percentage or
    ceiling"), so the scale is 0-100 only when the source says so: a percent
    unit, or a declared maximum that the multiplier puts at 100. A reported
    value outside 0-100 contradicts that and wins. Mirrors modelSeriesScale in
    app.js.
    """
    summary = series.get("score_summary") or {}
    multiplier = summary.get("display_multiplier") or 1
    unit = summary.get("unit") or series.get("unit")
    declared = series.get("declared_max")
    percent = unit == "percent" or (declared is not None and declared * multiplier == 100)
    raw_min, raw_max = summary.get("raw_min"), summary.get("raw_max")
    if raw_min is not None and raw_min * multiplier < 0:
        percent = False
    if raw_max is not None and raw_max * multiplier > 100:
        percent = False
    return multiplier, percent


def _better(direction: str | None, candidate: float, current: float) -> bool:
    if direction == "lower_is_better":
        return candidate < current
    return candidate > current


def _unit_label(series: dict[str, Any], percent: bool) -> str | None:
    if percent:
        return "%"
    unit = (series.get("score_summary") or {}).get("unit") or series.get("unit")
    return {"elo": "Elo", "usd": "USD"}.get(unit, unit)


def joined_map_from_groups(groups: list[dict[str, Any]] | None) -> dict[str, str]:
    """Record key -> equivalent-group id, from reviewed `equivalent` groups only.

    Only groups from `data/catalog/identity.yml` belong here: a shared name is
    not an anchor, and `variants` never join (they are related records, not the
    same instrument). A group with fewer than two members joins nothing, and a
    record claimed by two groups keeps the first, matching the identity
    loader, which forbids a key in two equivalent groups.
    """
    joined: dict[str, str] = {}
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        group_id = group.get("group_id")
        members = group.get("members") or []
        if not group_id or len(members) < 2:
            continue
        for member in members:
            joined.setdefault(str(member), str(group_id))
    return joined


def build_model_scores(
    shard_dir: Path, equivalences: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Each registry model's best reported score on each benchmark record.

    Models are the registry's (organization, model) identities, so the matrix
    and models.json agree. Several rows for one model on one record (different
    protocols or settings) keep the best by the series' direction; the count of
    rows is kept so the page can say that more settings were reported, and the
    side panel reads every row from the record's shard.

    When `equivalences` is given (reviewed `equivalent` groups from
    `data/catalog/identity.yml`), each benchmark entry also carries the
    `"joined"` group id of its record, so the Models average can intersect
    on joined keys. The cells stay per record: the join is an average
    computation, not a catalog merge, and no source row disappears.
    """
    shard_dir = Path(shard_dir)
    joined = joined_map_from_groups(equivalences)
    registry = build_registry({}, shard_dir)
    keys = {
        (record.organization.lower(), record.model.lower()): key for key, record in registry.items()
    }
    # A source that reuses one display label for distinct checkpoints (LLM
    # Stats: gpt-4o-2024-05-13 and gpt-4o-2024-08-06 are both "GPT-4o") keeps
    # them as separate columns, keyed by the source's model ID, the row identity
    # in catalog._observation. Other sources' rows stay on the registry model.
    source_ids: dict[tuple[str, str], set[str]] = {}
    for path in sorted(shard_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        for source, payload in (shard.get("scores_by_source") or {}).items():
            for row in payload.get("rows") or []:
                identity = (
                    (row.get("organization") or "").lower(),
                    (row.get("model_name") or "").lower(),
                )
                if identity in keys and row.get("model_id"):
                    source_ids.setdefault((keys[identity], source), set()).add(row["model_id"])
    split = {pair for pair, ids in source_ids.items() if len(ids) > 1}
    columns: dict[str, tuple[str, str | None]] = {}
    benchmarks: list[dict[str, Any]] = []
    cells: dict[str, dict[int, list[Any]]] = {}
    # Per model and source: the latest date on its rows and what that date is
    # (a score report's publication, or a model announcement for aggregators).
    dates: dict[str, dict[str, list[str]]] = {}
    for path in sorted(shard_dir.glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        record_key = (shard.get("record") or {}).get("key")
        for source, payload in sorted((shard.get("scores_by_source") or {}).items()):
            rows = [
                row
                for row in payload.get("rows") or []
                if isinstance(row.get("value"), (int, float))
            ]
            if not rows or not record_key:
                continue
            series = payload.get("series") or {}
            multiplier, percent = score_scale(series)
            direction = series.get("direction")
            index = len(benchmarks)
            # A record whose rows fall in several comparable groups (protocols,
            # scaffolds) lists them, and each cell keeps its value's group, so
            # an average compares models only within one group.
            groups = sorted({str(row.get("comparable_group")) for row in rows})
            benchmark = {
                "key": record_key,
                "direction": direction if direction in DIRECTIONS else None,
                "multiplier": multiplier,
                "percent": percent,
                "unit": _unit_label(series, percent),
            }
            if record_key in joined:
                benchmark["joined"] = joined[record_key]
            if len(groups) > 1:
                benchmark["groups"] = groups
            benchmarks.append(benchmark)
            for row in rows:
                identity = (
                    (row.get("organization") or "").lower(),
                    (row.get("model_name") or "").lower(),
                )
                model = keys.get(identity)
                if model is None:
                    continue
                base = model
                if (base, source) in split:
                    model = f"{base}@{row.get('model_id')}"
                    columns[model] = (base, row.get("model_id"))
                else:
                    columns.setdefault(model, (base, None))
                value = round(row["value"] * multiplier, 4)
                group = groups.index(str(row.get("comparable_group"))) if len(groups) > 1 else None
                cell = cells.setdefault(model, {}).get(index)
                if cell is None:
                    cells[model][index] = [value, 1, group]
                else:
                    cell[1] += 1
                    if _better(direction, value, cell[0]):
                        cell[0], cell[2] = value, group
                reported = row.get("reported_date") or row.get("reported_at") or ""
                current = dates.setdefault(model, {}).get(source)
                if reported and (current is None or reported > current[0]):
                    dates[model][source] = [reported, row.get("date_precision") or ""]
    models = [
        {
            "key": key,
            "model": registry[columns[key][0]].model,
            "organization": registry[columns[key][0]].organization,
            **({"source_model_id": columns[key][1]} if columns[key][1] else {}),
            # {source: [latest date, what the date is]}
            "dates": dict(sorted(dates.get(key, {}).items())),
            # [benchmark index, display value], then the row count when several
            # settings were reported or the record has comparable groups, then
            # the index of the value's group in that record's "groups".
            "scores": [
                [index, value]
                if count == 1 and group is None
                else [index, value, count]
                if group is None
                else [index, value, count, group]
                for index, (value, count, group) in sorted(cells[key].items())
            ],
        }
        for key in sorted(cells)
    ]
    return {"schema_version": SCHEMA_VERSION, "benchmarks": benchmarks, "models": models}


# What a column's date is: aggregators date a score by the model's
# announcement, model reports by the document's publication.
DATE_LABELS = {"model_announcement": "announced {date}", "document_publication": "reported {date}"}


def latest_date(dates: dict[str, list[str]], source: str | None = None) -> tuple[str, str]:
    """The latest (date, precision) over a model's sources, or one source's.

    Ties keep the first source in name order. Mirrors modelLatestDate in app.js.
    """
    entries = (
        [dates[source]] if source and source in dates else [] if source else list(dates.values())
    )
    best = max(entries, key=lambda entry: entry[0], default=["", ""])
    return best[0], best[1]


def write_model_scores(shard_dir: Path, output: Path = DEFAULT_SCORES_OUTPUT) -> dict[str, Any]:
    payload = build_model_scores(shard_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return {"models": len(payload["models"]), "benchmarks": len(payload["benchmarks"])}


def average_value(value: float, benchmark: dict[str, Any]) -> float | None:
    """A display value on the 0-100 higher-is-better scale averages use, or None."""
    if not benchmark.get("percent") or benchmark.get("direction") not in DIRECTIONS:
        return None
    return 100 - value if benchmark["direction"] == "lower_is_better" else value


def round_tenth(value: float) -> float:
    """Math.round(10 * value) / 10, as the page rounds, not banker's rounding."""
    return math.floor(10 * value + 0.5) / 10


def _joined_columns(
    columns: list[dict[str, float]],
    benchmarks: dict[str, dict[str, Any]],
    joined: dict[str, str],
) -> list[dict[str, tuple[str, float]]]:
    """Collapse each column onto joined keys, one record's score per group.

    A column scores a joined benchmark through its first averageable record
    in sorted record-key order. The join counts shared benchmarks; it does
    not merge scores across records, so no value is averaged across sources
    to make a cell.
    """
    collapsed: list[dict[str, tuple[str, float]]] = []
    for column in columns:
        by_joined: dict[str, tuple[str, float]] = {}
        for key in sorted(column):
            group_key = joined.get(key, key)
            if group_key in by_joined:
                continue
            if average_value(column[key], benchmarks.get(key) or {}) is None:
                continue
            by_joined[group_key] = (key, column[key])
        collapsed.append(by_joined)
    return collapsed


def _joined_group_label(
    record_key: str,
    index: int | None,
    benchmarks: dict[str, dict[str, Any]],
) -> str | int | None:
    """Comparable-group label for one joined record's cell.

    ``index`` is local to the record's own ``benchmark["groups"]`` list, so
    index 0 can mean ``cot`` on one record and ``plain`` on another; resolve
    it to the label before comparing across records. A record without a
    groups list keeps its index, which preserves the single-group behaviour.
    """
    groups = (benchmarks.get(record_key) or {}).get("groups")
    if isinstance(groups, list) and index is not None and 0 <= index < len(groups):
        return groups[index]
    return index


def shared_average(
    columns: list[dict[str, float]],
    benchmarks: dict[str, dict[str, Any]],
    groups: list[dict[str, int | None]] | None = None,
    joined: dict[str, str] | None = None,
) -> tuple[list[float | None], list[str]]:
    """Mean over the averageable benchmarks every column has a score on.

    ``columns`` maps record keys to display values, one mapping per model;
    ``groups`` maps them to the comparable group each value came from. A record
    counts only when every column's value is in the same group: different
    protocols on one record are not one benchmark.
    Returns each column's mean (None when nothing is shared) and the shared
    record keys, whose count the page shows. Mirrors modelSharedAverage in
    app.js, summing in the same key order so both round the same float.

    When ``joined`` maps record keys to reviewed equivalent-group ids (see
    :func:`joined_map_from_groups`), the intersection is on joined keys
    instead of raw record keys: two columns scoring different records of
    one group share that benchmark. The returned keys are the joined keys,
    and the comparable-group rule still applies, now to the records each
    column scored the group through, comparing each record's group label
    (not its local index into its own groups list). Without ``joined`` the
    behaviour is unchanged.
    """
    if not columns:
        return [], []
    if joined:
        collapsed = _joined_columns(columns, benchmarks, joined)
        shared = sorted(
            key
            for key in collapsed[0]
            if all(key in column for column in collapsed)
            and len(
                {
                    _joined_group_label(
                        collapsed[i][key][0],
                        (groups or [{}] * len(columns))[i].get(collapsed[i][key][0]),
                        benchmarks,
                    )
                    for i in range(len(columns))
                }
            )
            == 1
        )
        if not shared:
            return [None] * len(columns), []
        means: list[float | None] = []
        for column in collapsed:
            total = 0.0
            for key in shared:
                record_key, value = column[key]
                total += average_value(value, benchmarks[record_key])
            means.append(round_tenth(total / len(shared)))
        return means, shared
    shared = sorted(
        key
        for key in columns[0]
        if all(key in column for column in columns)
        and len({(groups or [{}] * len(columns))[i].get(key) for i in range(len(columns))}) == 1
        and average_value(columns[0][key], benchmarks.get(key) or {}) is not None
    )
    if not shared:
        return [None] * len(columns), []
    means: list[float | None] = []
    for column in columns:
        total = 0.0
        for key in shared:
            total += average_value(column[key], benchmarks[key])
        means.append(round_tenth(total / len(shared)))
    return means, shared


# .com Model Evals' capability groups, in its order, read from a record's
# categories and Library direction, as whole words. A benchmark measuring several
# abilities sits in the first group it matches. Mirrors modelCapabilityGroup in
# app.js.
CAPABILITY_GROUPS = (
    ("Mathematics", {"math", "mathematics"}),
    ("Coding", {"code", "coding", "software", "frontend"}),
    ("Agents & Tools", {"agent", "agents", "agentic", "tool", "tools", "computer"}),
    ("Science", {"science", "scientific", "biology", "chemistry", "physics"}),
    ("Multimodal", {"multimodal", "vision", "image", "video", "audio", "speech"}),
    ("Reasoning & Knowledge", {"reasoning", "knowledge", "language", "multilingual"}),
)
CAPABILITY_ORDER = (
    "Reasoning & Knowledge",
    "Mathematics",
    "Coding",
    "Agents & Tools",
    "Science",
    "Multimodal",
    "Other",
)


def capability_group(record: dict[str, Any]) -> str:
    """The first group sharing a whole word with the record's category ids.

    Category ids are words joined by "-" or "_" ("agentic-coding"); matching
    words, not substrings, keeps "multilingual" out of Multimodal.
    """
    direction = record.get("library_direction") or {}
    ids = [*(record.get("categories") or []), *(direction.get("categories") or [])]
    words = set(re.split(r"[^a-z0-9]+", " ".join(ids).lower()))
    for group, vocabulary in CAPABILITY_GROUPS:
        if words & vocabulary:
            return group
    return "Other"


_CONFIGURATION = re.compile(r"^(.*?)[\s-]*\(([^()]*)\)$")


def model_family(name: str) -> tuple[str, str]:
    """A model name split into its family and configuration.

    "Claude Opus 5 (Adaptive Reasoning, High Effort)" is the family "Claude Opus
    5" in the configuration "Adaptive Reasoning, High Effort", so configurations
    of one model sit together in the matrix. A name without a trailing
    parenthesis is its own family. Mirrors modelFamily in app.js.
    """
    match = _CONFIGURATION.match(name.strip())
    if match and match.group(1):
        return match.group(1), match.group(2)
    return name.strip(), ""


def order_models(models: list[dict[str, Any]], sort: str = "coverage") -> list[dict[str, Any]]:
    """Columns in the page's order, a family's configurations together.

    ``models`` carry ``organization``, ``model``, ``date`` and ``cells``.
    "coverage" puts the most benchmarks first, then the newest; "newest" orders
    by the latest reported score. Families sort by their best member, then by
    name; within one, the base model comes before its configurations, then the
    same order, then the name. Mirrors modelOrder in app.js (plain code-point
    comparison on both sides).
    """

    def family_key(model: dict[str, Any]) -> str:
        return f"{model['organization']}\u0000{model_family(model['model'])[0]}"

    def descending(value: str) -> tuple[int, ...]:
        return tuple(-ord(char) for char in value) + (1,)

    def metric(model: dict[str, Any]) -> tuple[Any, ...]:
        newest = descending(model.get("date") or "")
        return (newest,) if sort == "newest" else (-len(model.get("cells") or ()), newest)

    best: dict[str, tuple[Any, ...]] = {}
    for model in models:
        key = family_key(model)
        best[key] = min(best.get(key, metric(model)), metric(model))
    return sorted(
        models,
        key=lambda model: (
            best[family_key(model)],
            family_key(model),
            bool(model.get("source_model_id") or model_family(model["model"])[1]),
            metric(model),
            model["model"],
        ),
    )
