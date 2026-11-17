"""Shared read-only query service for CLI and HTTP benchmark discovery."""

from __future__ import annotations

import csv
import json
import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .citation import citation_block, required_citations
from .corpus import exact_artifact_key
from .science_domains import science_domains_for_record
from .snapshots import REQUIRED_SOURCES, load_snapshots

if TYPE_CHECKING:
    from .related_work import ManuscriptContext

QUERY_SCHEMA_VERSION = 8
DEFAULT_INDEX_PATH = Path("site/data/benchmark-index.json")
DEFAULT_SHARD_DIR = Path("site/data/benchmarks")
DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")
SEARCH_SCOPES = ("catalog", "radar", "all")

_FIELD_ORDER = (
    "name",
    "description",
    "categories",
    "publisher",
    "modality",
    "languages",
    "source",
)
_FIELD_WEIGHTS = {
    "name": 5.0,
    "description": 1.0,
    "categories": 2.5,
    "publisher": 0.6,
    "modality": 1.2,
    "languages": 0.3,
    "source": 0.2,
}
_BM25_K1 = 1.2
_BM25_B = 0.75
_NAME_MATCH_MULTIPLIERS = (3.0, 1.5, 0.75)
_PHRASE_MULTIPLIER = 0.5
_MIN_PREFIX_LENGTH = 2
# Han ideographs plus hiragana and katakana, which share unspaced text with Han.
_CJK_CHARS = (
    r"\u3005\u3041-\u309f\u30a1-\u30fa\u30fc-\u30ff\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
)
# Latin letters outside ASCII are left out of the word alternative so Latin text
# keeps its original ASCII tokens, and English scores stay unchanged.
_LATIN_EXTENDED = r"\u00c0-\u02af\u1e00-\u1eff\u2c60-\u2c7f\ua720-\ua7ff\uab30-\uab6f"
_TOKEN_PARTS = re.compile(
    rf"[a-z0-9]+|(?P<cjk>[{_CJK_CHARS}]+)"
    rf"|(?:(?![{_CJK_CHARS}{_LATIN_EXTENDED}])[^\W\d_])+"
)

LOGGER = logging.getLogger(__name__)


class QueryError(RuntimeError):
    """A public, actionable query failure with a stable machine code."""

    def __init__(self, message: str, *, code: str = "query_error", status: int = 500):
        super().__init__(message)
        self.code = code
        self.status = status


def error_payload(error: QueryError) -> dict[str, Any]:
    """Stable machine-readable error envelope shared by every interface."""
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "error": {"code": error.code, "message": str(error)},
    }


@dataclass(frozen=True, slots=True)
class QueryPaths:
    index: Path = DEFAULT_INDEX_PATH
    shards: Path = DEFAULT_SHARD_DIR
    snapshots: Path = DEFAULT_SNAPSHOT_DIR
    data_version: str | None = None
    generated_at: str | None = None
    synced_at: str | None = None


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise QueryError(
            f"{label} is missing at {path}; run `benchmark-radar normalize-catalog` "
            "for catalog data or provide an explicit path",
            code="data_unavailable",
            status=503,
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise QueryError(
            f"cannot read {label} at {path}: {type(error).__name__}: {error}",
            code="invalid_data",
            status=500,
        ) from error
    if not isinstance(value, dict):
        raise QueryError(
            f"{label} at {path} must be a JSON object",
            code="invalid_data",
            status=500,
        )
    return value


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _trace_normalization_diff(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Diff only the vocabulary both representations share.

    Raw inputs and normalized rows use different schemas, so keys present on
    only one side are mapping, not drift.  Fields whose type changed
    (scalar to object, object to list) are representation changes and are
    reported separately from value changes.
    """
    changes: list[dict[str, Any]] = []
    restructured: list[str] = []

    def walk(raw: Any, norm: Any, prefix: str) -> None:
        if isinstance(raw, dict) and isinstance(norm, dict):
            for key in sorted(set(raw) & set(norm)):
                walk(raw[key], norm[key], f"{prefix}.{key}" if prefix else str(key))
            return
        if isinstance(raw, dict) or isinstance(norm, dict):
            if isinstance(raw, dict) != isinstance(norm, dict):
                restructured.append(prefix)
            return
        if _canon(raw) != _canon(norm):
            changes.append({"field": prefix, "before": raw, "after": norm})

    walk(before, after, "")
    return changes, restructured


def _trace_repo_root(index_path: Path) -> Path | None:
    """Return the checkout root when the index sits at ``<root>/site/data``.

    Installed clients keep the index under ``~/.benchmark-radar/versions/``;
    the pipeline inputs (``data/catalog``, ``data/leaderboard_snapshots``,
    ``data/model_cards.yml``) exist only in a repository checkout, so those
    stages must report absent there instead of probing the wrong directory.
    """
    if index_path.parent.name == "data" and index_path.parent.parent.name == "site":
        return index_path.parent.parent.parent
    return None


def _trace_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError) as error:
        raise QueryError(f"cannot read snapshot at {path}: {error}", code="invalid_data") from error


def _trace_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise QueryError(
            f"cannot read normalized evidence at {path}: {error}", code="invalid_data"
        ) from error
    if any(not isinstance(row, dict) for row in rows):
        raise QueryError(f"{path}: expected JSON objects", code="invalid_data")
    return rows


def _load_leaderboard_snapshots(path: Path) -> Any:
    from .leaderboard_snapshots import load_snapshots as load_leaderboard_snapshots

    return load_leaderboard_snapshots(path)


def _load_model_card_registry(path: Path) -> Any:
    from .model_cards import load_registry

    return load_registry(path)


def _load_benchmark_scores(path: Path) -> Any:
    from .benchmark_scores import load_scores

    return load_scores(path)


def _trace_validate(path: Path, label: str, loader: Any) -> None:
    """Run a pipeline loader and report its rejection as ``invalid_data``.

    The loaders raise ``ValueError`` subclasses for invalid content; a
    malformed entry can also surface as ``KeyError``/``TypeError``/
    ``AttributeError`` before their checks run. All of them mean the pipeline
    cannot read this input, which trace must report in its error envelope
    rather than as a traceback.
    """
    try:
        loader(path)
    except (
        OSError,
        UnicodeDecodeError,
        yaml.YAMLError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as error:
        raise QueryError(
            f"invalid {label} at {path}: {type(error).__name__}: {error}", code="invalid_data"
        ) from error


def _trace_snapshot_row(
    root: Path, source: str, source_benchmark_id: str
) -> tuple[dict[str, Any] | None, Path | None, str]:
    """Return ``(row, path, state)`` for the newest committed crawl row.

    ``state`` is ``found``, ``missing`` (the snapshot artifact exists but has
    no row for this record), or ``unavailable`` (no snapshot applies or the
    registry cannot be read).
    """
    registry_path = root / "data" / "leaderboard_snapshots.yml"
    if not registry_path.exists() or not source_benchmark_id:
        return None, None, "unavailable"
    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise QueryError(
            f"cannot read snapshot registry at {registry_path}: {type(error).__name__}: {error}",
            code="invalid_data",
        ) from error
    # The registry must pass the same validation normalize-catalog applies:
    # schema_version, required fields, declared row counts and checksums. A
    # shape-only check would let trace mark source and normalization present
    # for a registry the pipeline itself refuses to read.
    _trace_validate(registry_path, "snapshot registry", _load_leaderboard_snapshots)
    snapshots = [
        entry
        for entry in registry["snapshots"]
        if str(entry.get("id") or "").startswith(f"{source}_")
    ]
    if not snapshots:
        return None, None, "unavailable"
    entry = max(snapshots, key=lambda row: str(row.get("crawled_at") or ""))
    columns = entry.get("benchmark_columns") or {}
    id_column = columns.get("benchmark_id")
    benchmark_file = entry.get("benchmark_file")
    if not id_column or not benchmark_file:
        return None, None, "unavailable"
    path = root / "data" / str(benchmark_file)
    if not path.exists():
        return None, path, "missing"
    row = next(
        (row for row in _trace_csv_rows(path) if row.get(id_column) == source_benchmark_id), None
    )
    if row is None:
        return None, path, "missing"
    value: dict[str, Any] = dict(row)
    value["snapshot"] = entry
    value["input_paths"] = {"benchmark_file": str(path), "registry": str(registry_path)}
    if entry.get("scores_file"):
        scores_path = root / "data" / entry["scores_file"]
        score_id = (entry.get("columns") or {}).get("benchmark_id", id_column)
        value["score_rows"] = [
            row for row in _trace_csv_rows(scores_path) if row.get(score_id) == source_benchmark_id
        ]
        value["input_paths"]["scores_file"] = str(scores_path)
    if source == "opencompass_hub":
        from .catalog_opencompass import DEFAULT_ROUND2_PATH

        round2_path = root / DEFAULT_ROUND2_PATH
        value["round2_evidence"] = next(
            (
                row
                for row in _trace_jsonl_rows(round2_path)
                if row.get("benchmark_id") == source_benchmark_id
            ),
            None,
        )
        value["input_paths"]["round2_evidence"] = str(round2_path)
        if value["round2_evidence"] is None:
            raise QueryError(
                f"no round-2 evidence for {source_benchmark_id} at {round2_path}",
                code="invalid_data",
            )
    return json.loads(_canon(value)), path, "found"


def _trace_reviewed_record(record: dict[str, Any], normalized_path: Path) -> dict[str, Any]:
    """Replay reviewed enrichment before comparing with the stored source record."""
    from .catalog import CatalogError
    from .catalog_authors import apply_benchmark_authors, load_benchmark_authors
    from .catalog_dates import apply_benchmark_dates, load_benchmark_dates
    from .catalog_institutions import apply_benchmark_institutions, load_benchmark_institutions
    from .catalog_overrides import (
        apply_llm_stats_identity_overrides,
        load_llm_stats_identity_overrides,
    )

    directory = normalized_path.parent
    root = directory.parent.parent
    population = [
        row
        for path in sorted(directory.glob("*_source_records.jsonl"))
        for row in _trace_jsonl_rows(path)
        if row.get("key") != record["key"]
    ] + [record]
    records = [record]
    try:
        overrides_path = directory / "llm_stats_identity_overrides.yml"
        if record.get("source") == "llm_stats" and overrides_path.exists():
            overrides = load_llm_stats_identity_overrides(population, overrides_path)
            # Apply all registered rows, as the production adapter requires.
            enriched = apply_llm_stats_identity_overrides(population, overrides)
            records = [row for row in enriched if row["key"] == record["key"]]
        steps = [("benchmark_dates.yml", load_benchmark_dates, apply_benchmark_dates)]
        if record.get("source") != "opencompass_hub":
            steps += [
                ("benchmark_authors.yml", load_benchmark_authors, apply_benchmark_authors),
                (
                    "benchmark_institutions.yml",
                    load_benchmark_institutions,
                    apply_benchmark_institutions,
                ),
            ]
        for filename, load, apply in steps:
            path = directory / filename
            if path.exists():
                records = apply(records, load(population, path))
    except (CatalogError, OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as error:
        raise QueryError(f"cannot replay reviewed inputs: {error}", code="invalid_data") from error
    # Production stores checkout-relative lineage paths. Relativize the
    # decoded values rather than the JSON text: serialization escapes Windows
    # backslashes, so a text replace of ``str(root) + "/"`` never matches there.
    return _trace_relativize(json.loads(_canon(records[0])), str(root))


def _trace_relativize(value: Any, root: str) -> Any:
    """Strip the checkout root from every path inside ``value``.

    Paths may carry a ``#locator`` suffix and may sit inside longer text, so
    each occurrence of the root (with either separator) is removed, and the
    path that follows it is rewritten with ``/`` to match the stored rows.
    """
    if isinstance(value, dict):
        return {key: _trace_relativize(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_trace_relativize(item, root) for item in value]
    if not isinstance(value, str):
        return value
    base = root.rstrip("/\\")
    for prefix in (base + "/", base + "\\"):
        while prefix in value:
            head, tail = value.split(prefix, 1)
            path, separator, rest = tail.partition("#")
            path, space, after = path.partition(" ")
            value = head + path.replace("\\", "/") + space + after + separator + rest
    return value


def _trace_record_changes(
    record: dict[str, Any], normalized: dict[str, Any], normalized_path: Path
) -> list[dict[str, Any]]:
    record = _trace_reviewed_record(record, normalized_path)
    fields = (record.keys() & normalized.keys()) | {
        "released_reference",
        "first_score_source_reference",
        "first_score_reported_at",
        "authors",
        "authors_reference",
        "institutions",
        "institutions_reference",
        "identity_override",
    }
    if record.get("identity_override") or normalized.get("identity_override"):
        fields |= {
            "repository",
            "artifacts",
            "publisher",
            "released",
            "released_basis",
            "sizes",
            "openness",
        }
    # Include removed facts and newly supplied fields, which an intersection-only
    # raw-schema comparison cannot detect.
    return [
        {"field": key, "before": record.get(key), "after": normalized.get(key)}
        for key in sorted(fields)
        if key not in {"provenance", "slug", "evidence"}
        and _canon(record.get(key)) != _canon(normalized.get(key))
    ]


def _trace_snapshot_changes(
    raw: dict[str, Any],
    normalized: dict[str, Any],
    normalized_path: Path,
) -> list[dict[str, Any]]:
    """Use the production adapters to compare supplementary inputs with their outputs."""
    snapshot = raw.get("snapshot")
    if not isinstance(snapshot, dict):
        if (raw.get("sources") or {}).get("registry"):
            return _trace_model_reports_changes(raw, normalized, normalized_path)
        return []
    from .catalog import CatalogError, normalize_snapshot
    from .catalog_evidence import attach_evidence
    from .catalog_opencompass import normalize_opencompass

    paths = raw["input_paths"]
    snapshot = {
        **snapshot,
        "benchmark_rows": _trace_csv_rows(Path(paths["benchmark_file"])),
        "score_rows": raw.get("score_rows", []),
    }
    try:
        if "round2_evidence" in raw:
            expected = normalize_opencompass(
                Path(paths["round2_evidence"]), catalog_snapshot=snapshot
            )
            record = next(
                row
                for row in attach_evidence(expected["source_records"], [], [])
                if row["source_benchmark_id"] == raw["benchmark_id"]
            )
            return _trace_record_changes(record, normalized, normalized_path)
        expected = normalize_snapshot(snapshot)
    except (CatalogError, KeyError, TypeError, ValueError) as error:
        raise QueryError(f"cannot normalize source inputs: {error}", code="invalid_data") from error
    record = next(
        row
        for row in attach_evidence(
            expected["source_records"], expected["score_series"], expected["score_observations"]
        )
        if row["key"] == normalized["key"]
    )
    changes = _trace_record_changes(record, normalized, normalized_path)
    if "score_rows" not in raw:
        return changes
    source = expected["validation"]["source"]
    return changes + _trace_row_set_changes(
        "score_observations",
        [row for row in expected["score_observations"] if row["key"] == normalized["key"]],
        normalized_path.parent / f"{source}_score_observations.jsonl",
        normalized["key"],
        "obs_id",
    )


def _trace_row_set_changes(
    field: str,
    expected_rows: list[dict[str, Any]],
    stored_path: Path,
    key: str,
    id_field: str,
) -> list[dict[str, Any]]:
    """Compare replayed rows for one record with the rows stored on disk."""
    if not stored_path.exists():
        return [
            {
                "field": field,
                "before": "source inputs available",
                "after": f"missing artifact at {stored_path}",
            }
        ]
    stored_rows = [row for row in _trace_jsonl_rows(stored_path) if row.get("key") == key]
    if any(not isinstance(row.get(id_field), str) or not row[id_field] for row in stored_rows):
        raise QueryError(f"{stored_path}: missing {id_field} row identity", code="invalid_data")
    stored = {row[id_field]: row for row in stored_rows}
    current = {row[id_field]: row for row in expected_rows}
    changes: list[dict[str, Any]] = []
    for row_id in sorted(current.keys() | stored.keys()):
        if row_id not in current or row_id not in stored:
            changes.append(
                {
                    "field": f"{field}.{row_id}",
                    "before": current.get(row_id),
                    "after": stored.get(row_id),
                }
            )
        else:
            delta, _ = _trace_normalization_diff(current[row_id], stored[row_id])
            changes.extend({**item, "field": f"{field}.{row_id}.{item['field']}"} for item in delta)
    return changes


def _trace_model_reports_changes(
    raw: dict[str, Any], normalized: dict[str, Any], normalized_path: Path
) -> list[dict[str, Any]]:
    """Replay normalize_reports and compare its record, series and observations.

    A model_reports raw value has no ``snapshot``, and its ``score_rows``,
    ``metric_identity`` and ``adopting_documents`` never appear on the
    normalized record, so a field diff alone cannot see a changed or deleted
    score or card mention. Rebuild the source exactly as normalize-catalog does.
    """
    from .benchmark_scores import load_scores
    from .catalog import CatalogError
    from .catalog_evidence import attach_evidence
    from .catalog_reports import normalize_reports
    from .model_cards import load_registry

    sources = raw.get("sources") or {}
    score_archive = sources.get("score_archive")
    try:
        expected = normalize_reports(
            load_registry(Path(sources["registry"])),
            load_scores(Path(score_archive))
            if score_archive
            else {"schema_version": 1, "benchmarks": [], "results": []},
        )
    except (CatalogError, OSError, KeyError, TypeError, ValueError) as error:
        raise QueryError(
            f"cannot normalize model report inputs: {type(error).__name__}: {error}",
            code="invalid_data",
        ) from error
    key = normalized["key"]
    series = [row for row in expected["score_series"] if row["key"] == key]
    observations = [row for row in expected["score_observations"] if row["key"] == key]
    record = next(
        (
            row
            for row in attach_evidence(expected["source_records"], series, observations)
            if row["key"] == key
        ),
        None,
    )
    if record is None:
        return [
            {
                "field": "record",
                "before": "not produced by current model report inputs",
                "after": "stored normalized record",
            }
        ]
    return (
        _trace_record_changes(record, normalized, normalized_path)
        + _trace_row_set_changes(
            "score_series",
            series,
            normalized_path.parent / "model_reports_score_series.jsonl",
            key,
            "key",
        )
        + _trace_row_set_changes(
            "score_observations",
            observations,
            normalized_path.parent / "model_reports_score_observations.jsonl",
            key,
            "obs_id",
        )
    )


def _trace_model_reports_row(
    root: Path, source_benchmark_id: str
) -> tuple[dict[str, Any] | None, Path | None, str]:
    """Assemble every model_cards/benchmark_scores input for one benchmark.

    ``normalize_reports`` consumes the ``benchmarks:`` entry, the metric
    identity and score rows in ``benchmark_scores.yml``, and every model card
    or source document that cites the benchmark, so the source stage shows
    all of them rather than only the registry row.
    """
    path = root / "data" / "model_cards.yml"
    scores_path = root / "data" / "benchmark_scores.yml"
    if not source_benchmark_id:
        return None, None, "unavailable"
    if not path.exists():
        return None, path, "missing"
    # normalize_reports only ever sees these files through their production
    # loaders, so trace validates them the same way before indexing into them.
    _trace_validate(path, "model card registry", _load_model_card_registry)
    if scores_path.exists():
        _trace_validate(scores_path, "score archive", _load_benchmark_scores)
    try:
        registry = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise QueryError(
            f"cannot read model card registry at {path}: {type(error).__name__}: {error}",
            code="invalid_data",
        ) from error
    entry = next(
        (
            benchmark
            for benchmark in registry.get("benchmarks") or []
            if isinstance(benchmark, dict) and benchmark.get("id") == source_benchmark_id
        ),
        None,
    )
    if entry is None:
        return None, path, "missing"
    value = dict(entry)
    value["sources"] = {
        "registry": str(path),
        "score_archive": str(scores_path) if scores_path.exists() else None,
    }
    if scores_path.exists():
        try:
            scores = yaml.safe_load(scores_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            raise QueryError(
                f"cannot read score archive at {scores_path}: {type(error).__name__}: {error}",
                code="invalid_data",
            ) from error
        value["metric_identity"] = next(
            (
                metric
                for metric in scores.get("benchmarks") or []
                if isinstance(metric, dict) and metric.get("benchmark_id") == source_benchmark_id
            ),
            None,
        )
        value["score_rows"] = [
            row
            for row in scores.get("results") or []
            if isinstance(row, dict) and row.get("benchmark_id") == source_benchmark_id
        ]
    documents = []
    for card in registry.get("model_cards") or []:
        if not isinstance(card, dict):
            continue
        cited = {str(ref) for ref in card.get("benchmarks") or []}
        if source_benchmark_id in cited:
            documents.append(
                {
                    "id": card.get("id"),
                    "model": card.get("model"),
                    "document_type": card.get("document_type"),
                    "url": card.get("url"),
                }
            )
    for source_doc in registry.get("source_documents") or []:
        if not isinstance(source_doc, dict):
            continue
        cited = {str(ref) for ref in source_doc.get("benchmarks") or []}
        if source_benchmark_id in cited:
            documents.append(
                {
                    "id": source_doc.get("id"),
                    "name": source_doc.get("name"),
                    "document_type": source_doc.get("document_type"),
                    "url": source_doc.get("url"),
                }
            )
    if documents:
        value["adopting_documents"] = documents
    # yaml parses dates into date objects; the trace payload must stay JSON-safe.
    return json.loads(_canon(value)), path, "found"


def _trace_raw_row(
    root: Path | None,
    catalog: dict[str, Any] | None,
    normalized: dict[str, Any] | None,
    shard_record: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, Path | None, str]:
    """Inspect the per-record input the catalog pipeline normalized.

    Works from the normalized row alone so a record dropped before the
    catalog still resolves its raw artifact.  ``state`` is ``found``,
    ``missing`` (the artifact exists but has no row for this record), or
    ``unavailable`` (checkout inputs cannot be inspected).
    """
    if root is None:
        return None, None, "unavailable"
    source_benchmark_id = str(
        (normalized or {}).get("source_benchmark_id")
        or (shard_record or {}).get("source_benchmark_id")
        or str((catalog or {}).get("key") or "").partition(":")[2]
        or (catalog or {}).get("slug")
        or ""
    )
    source = str((catalog or {}).get("source") or (normalized or {}).get("source") or "")
    if not source_benchmark_id or not source:
        return None, None, "unavailable"
    if source == "model_reports":
        return _trace_model_reports_row(root, source_benchmark_id)
    return _trace_snapshot_row(root, source, source_benchmark_id)


def _trace_identity_population(
    root: Path, index_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the records normalize-catalog validates identity.yml against.

    The pipeline calls ``load_identity`` on the current normalized source
    records, not on the published index. When the sources have advanced past
    a stale index, validating against the index would accept a rule whose
    member no longer exists, and trace would report identity present for a
    record the pipeline refuses to build. The index is used only when the
    checkout has no normalized source records at all.
    """
    paths = sorted((root / "data" / "catalog").glob("*_source_records.jsonl"))
    if not paths:
        return index_records
    return [row for path in paths for row in _trace_jsonl_rows(path)]


def _trace_rebuild(root: Path, population: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Rebuild one record's index row and detail shard from normalized artifacts.

    normalize-catalog writes the source records, series and observations
    before it builds the index and the shards, and both carry fields that
    exist nowhere else: index score projections (``score_count``,
    ``scored_models``, ``score_summary``...), Library enrichment, sibling
    descriptors and ``scores_by_source``. Replay identity inheritance,
    evidence, ``build_benchmark_index`` and ``build_shard`` with the
    production inputs so trace compares whole artifacts, not shared keys.
    Returns None when the current source records no longer contain ``key``.
    """
    from .catalog import build_benchmark_index
    from .catalog_evidence import attach_evidence
    from .catalog_identity import apply_inherited_identity, load_identity
    from .catalog_shards import build_shard
    from .library_directions import (
        assign_library_directions,
        load_direction_reviews,
        load_library_directions,
    )
    from .library_signals import assign_library_signals, load_library_signals

    catalog_dir = root / "data" / "catalog"
    try:
        identity = load_identity(population, catalog_dir / "identity.yml")
        record = next(
            (
                row
                for row in apply_inherited_identity(population, identity)
                if row.get("key") == key
            ),
            None,
        )
        if record is None:
            return None
        series = [
            row
            for path in sorted(catalog_dir.glob("*_score_series.jsonl"))
            for row in _trace_jsonl_rows(path)
            if row.get("key") == key
        ]
        observations = [
            row
            for path in sorted(catalog_dir.glob("*_score_observations.jsonl"))
            for row in _trace_jsonl_rows(path)
            if row.get("key") == key
        ]
        [record] = attach_evidence([record], series, observations)
        series_by_key = {row["key"]: row for row in series}
        directions = assign_library_directions(
            population,
            load_library_directions(catalog_dir / "claire_library_categories.json"),
            identity.equivalent_groups,
            load_direction_reviews(catalog_dir / "library_direction_reviews.yml"),
        )
        signals = assign_library_signals(
            population, load_library_signals(catalog_dir / "claire_library_signals.json")
        )
        [index_row] = build_benchmark_index(
            [record],
            series_by_key,
            observations,
            directions_by_key=directions,
            signals_by_key=signals,
        )
        shard = build_shard(
            record,
            identity=identity,
            series_by_key=series_by_key,
            observations_by_key={key: observations} if observations else {},
        )
    except QueryError:
        raise
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        yaml.YAMLError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as error:
        raise QueryError(
            f"cannot rebuild catalog artifacts from {catalog_dir}: {type(error).__name__}: {error}",
            code="invalid_data",
        ) from error
    return {
        "index_row": index_row,
        "shard": json.loads(_canon(shard)),
        "inheritance": identity.inheritance_for(key),
    }


def _trace_field_changes(
    before: dict[str, Any], after: dict[str, Any], prefix: str = ""
) -> list[dict[str, Any]]:
    """Every top-level field whose value differs between two objects."""
    return [
        {"field": prefix + field, "before": before.get(field), "after": after.get(field)}
        for field in sorted(before.keys() | after.keys())
        if _canon(before.get(field)) != _canon(after.get(field))
    ]


def _trace_sibling_descriptor_changes(
    siblings: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compare each shard sibling with the descriptor siblings_for would write.

    Key and relation only say the join is declared; ``slug``, ``name`` and
    ``source`` drive the detail link, so a stale one is a change too.
    """
    expected_by_pair = {(str(row.get("key")), str(row.get("relation"))): row for row in expected}
    changes: list[dict[str, Any]] = []
    for sibling in siblings:
        pair = (str(sibling.get("key")), str(sibling.get("relation")))
        current = expected_by_pair.get(pair)
        if current is not None:
            changes.extend(_trace_field_changes(sibling, current, f"siblings.{pair[0]}."))
    return changes


def _trace_source_record(root: Path, key: str) -> tuple[dict[str, Any] | None, Path | None]:
    for path in sorted((root / "data" / "catalog").glob("*_source_records.jsonl")):
        for row in _trace_jsonl_rows(path):
            if row.get("key") == key:
                return row, path
    return None, None


def _trace_donor_changes(
    root: Path, inheritance: dict[str, Any] | None, index_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replay the identity donor's own source inputs.

    A recipient in an ``inherit_from`` group shows its donor's publisher,
    artifacts, release, sizes and openness. Rebuilding the recipient from
    the donor's stored normalized row would reapply stale values, so run the
    donor through the same source replay trace uses for its own target and
    report drift in the fields the recipient can inherit.
    """
    from .catalog_identity import INHERITED_IDENTITY_FIELDS

    if not inheritance:
        return []
    donor_key = str(inheritance.get("donor_key") or "")
    donor, donor_path = _trace_source_record(root, donor_key)
    if donor is None or donor_path is None:
        return [
            {
                "field": f"donor.{donor_key}",
                "before": "identity donor",
                "after": "absent from current normalized source records",
            }
        ]
    donor_catalog = next((row for row in index_records if row.get("key") == donor_key), None)
    raw, _, state = _trace_raw_row(root, donor_catalog, donor, None)
    if state != "found" or raw is None:
        return []
    inheritable = {*INHERITED_IDENTITY_FIELDS, "released_reference"}
    return [
        {**change, "field": f"donor.{donor_key}.{change['field']}"}
        for change in _trace_snapshot_changes(raw, donor, donor_path)
        if change["field"].split(".")[0] in inheritable
    ]


def _trace_declared_pairs(
    root: Path,
    records: list[dict[str, Any]],
) -> tuple[set[frozenset[str]], set[tuple[str, str, str]], dict[str, set[str]]] | None:
    """Return identity rules as ``(equivalent pairs, directed variants, peers)``.

    ``peers`` maps each declared key to the keys the current rules join it
    with, in either direction, so trace can find joins a stale shard is
    missing as well as siblings the rules no longer declare.
    """
    path = root / "data" / "catalog" / "identity.yml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise QueryError(
            f"cannot read identity rules at {path}: {type(error).__name__}: {error}",
            code="invalid_data",
        ) from error
    if not isinstance(data, dict):
        raise QueryError(f"identity rules at {path} must be a mapping", code="invalid_data")
    for section in ("equivalent", "variants"):
        entries = data.get(section, [])
        if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
            raise QueryError(f"{path}: {section} must be a list of objects", code="invalid_data")
        for row in entries:
            values = (
                row.get("members", [])
                if section == "equivalent"
                else [row.get("of"), row.get("key")]
            )
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise QueryError(f"{path}: invalid {section} record keys", code="invalid_data")
            if section == "variants" and not isinstance(row.get("relation", "related"), str):
                raise QueryError(f"{path}: invalid variant relation", code="invalid_data")
    from .catalog_identity import IdentityError, load_identity

    try:
        load_identity(records, path)
    except (
        IdentityError,
        OSError,
        yaml.YAMLError,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise QueryError(
            f"cannot validate identity rules at {path}: {error}", code="invalid_data"
        ) from error
    record_keys = {row["key"] for row in records}
    equivalent: set[frozenset[str]] = set()
    peers: dict[str, set[str]] = {}
    for group in data.get("equivalent") or []:
        members = [str(member) for member in group.get("members") or []]
        for position, first in enumerate(members):
            for second in members[position + 1 :]:
                equivalent.add(frozenset((first, second)))
        for member in members:
            peers.setdefault(member, set()).update(other for other in members if other != member)
    variants: set[tuple[str, str, str]] = set()
    for entry in data.get("variants") or []:
        pair = {str(entry.get("of") or ""), str(entry.get("key") or "")}
        pair.discard("")
        if len(pair) == 2 and pair <= record_keys:
            parent = str(entry["of"])
            child = str(entry["key"])
            variants.add((parent, child, f"variant:{entry.get('relation', 'related')}"))
            variants.add((child, parent, "variant:of"))
            first, second = tuple(pair)
            peers.setdefault(first, set()).add(second)
            peers.setdefault(second, set()).add(first)
    return equivalent, variants, peers


def _trace_export_contains(root: Path, benchmark_id: str) -> dict[str, dict[str, Any]]:
    """Leaderboard exports and whether they verifiably contain one record.

    Unreadable artifacts are reported with ``error`` rather than omitted, so
    a corrupt output cannot hide behind a healthy index or shard.
    """
    found: dict[str, dict[str, Any]] = {}
    data_dir = root / "site" / "data"
    csv_path = data_dir / "leaderboard.csv"
    if csv_path.exists():
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                contains = any(
                    row.get("benchmark_id") == benchmark_id for row in csv.DictReader(handle)
                )
            found["leaderboard.csv"] = {"path": str(csv_path), "contains": contains}
        except (OSError, csv.Error, UnicodeDecodeError) as error:
            found["leaderboard.csv"] = {
                "path": str(csv_path),
                "contains": None,
                "error": f"{type(error).__name__}: {error}",
            }
    json_path = data_dir / "leaderboard.json"
    if json_path.exists():
        try:
            payload = _read_object(json_path, label="leaderboard export")
            entries = payload.get("entries") or []
            contains = any(
                isinstance(entry, dict) and entry.get("benchmark_id") == benchmark_id
                for entry in entries
            )
            found["leaderboard.json"] = {"path": str(json_path), "contains": contains}
        except QueryError as error:
            found["leaderboard.json"] = {
                "path": str(json_path),
                "contains": None,
                "error": str(error),
            }
    md_path = data_dir / "leaderboard.md"
    if md_path.exists():
        try:
            contains = benchmark_id in md_path.read_text(encoding="utf-8")
            found["leaderboard.md"] = {"path": str(md_path), "contains": contains}
        except (OSError, UnicodeDecodeError) as error:
            found["leaderboard.md"] = {
                "path": str(md_path),
                "contains": None,
                "error": f"{type(error).__name__}: {error}",
            }
    return found


def _validate_index_record(record: dict[str, Any], *, position: int) -> None:
    label = f"benchmark index record {position}"
    for field in ("key", "slug", "name", "source"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise QueryError(
                f"{label} {field} must be a non-empty string",
                code="invalid_data",
            )
    if not isinstance(record.get("description"), str):
        raise QueryError(f"{label} description must be a string", code="invalid_data")
    for field in ("categories", "languages"):
        value = record.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise QueryError(
                f"{label} {field} must be an array of strings",
                code="invalid_data",
            )
    for field in ("has_paper", "has_repo", "has_dataset", "has_size"):
        if not isinstance(record.get(field), bool):
            raise QueryError(f"{label} {field} must be a boolean", code="invalid_data")


def _tokens(value: Any) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    tokens: list[str] = []
    for match in _TOKEN_PARTS.finditer(normalized):
        part = match.group()
        if match.lastgroup == "cjk":
            # Han and kana text has no spaces between words. Adjacent character
            # pairs let a short query find a longer source description without
            # treating every shared single character as a strong match. NFKD
            # split voiced kana such as が from their marks, so recompose first.
            part = unicodedata.normalize("NFC", part)
            tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
            if len(part) == 1:
                tokens.append(part)
        else:
            tokens.append(part)
    return tuple(tokens)


def _field_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _filter_value(value: Any) -> str:
    return str(value or "").strip().casefold()


def _matches_filter(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    for flag in ("has_paper", "has_repo", "has_dataset"):
        expected = filters.get(flag)
        if expected is not None and record.get(flag) is not expected:
            return False
    for field in ("openness", "modality", "source"):
        expected = filters.get(field)
        if expected is not None and _filter_value(record.get(field)) != _filter_value(expected):
            return False
    sources = filters.get("sources")
    if sources is not None and _filter_value(record.get("source")) not in sources:
        return False
    return True


@dataclass(frozen=True, slots=True)
class _SearchDocument:
    record: dict[str, Any]
    field_tokens: dict[str, tuple[str, ...]]
    field_counts: dict[str, Counter[str]]
    field_ascii_lengths: dict[str, int]
    field_unicode_lengths: dict[str, int]
    all_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class _SearchCorpus:
    documents: tuple[_SearchDocument, ...]
    document_frequency: Counter[str]
    average_field_lengths: dict[str, float]
    average_unicode_field_lengths: dict[str, float]


def _build_search_corpus(records: list[dict[str, Any]]) -> _SearchCorpus:
    documents: list[_SearchDocument] = []
    document_frequency: Counter[str] = Counter()
    total_field_lengths: Counter[str] = Counter()
    total_unicode_field_lengths: Counter[str] = Counter()
    for record in records:
        field_tokens = {field: _tokens(_field_text(record.get(field))) for field in _FIELD_ORDER}
        # Registered aliases are name evidence for every source. Keep the
        # published display name and the shared ranking algorithm unchanged.
        if record.get("aliases"):
            field_tokens["name"] = _tokens(
                _field_text(record.get("name")) + " " + _field_text(record["aliases"])
            )
        field_counts = {field: Counter(tokens) for field, tokens in field_tokens.items()}
        ascii_lengths = {
            field: sum(token.isascii() for token in tokens)
            for field, tokens in field_tokens.items()
        }
        unicode_lengths = {
            field: len(tokens) - ascii_lengths[field] for field, tokens in field_tokens.items()
        }
        all_tokens = frozenset().union(*(set(tokens) for tokens in field_tokens.values()))
        document_frequency.update(all_tokens)
        total_field_lengths.update(ascii_lengths)
        total_unicode_field_lengths.update(unicode_lengths)
        documents.append(
            _SearchDocument(
                record=record,
                field_tokens=field_tokens,
                field_counts=field_counts,
                field_ascii_lengths=ascii_lengths,
                field_unicode_lengths=unicode_lengths,
                all_tokens=all_tokens,
            )
        )
    count = len(documents)
    averages = {
        field: total_field_lengths[field] / count if count else 0.0 for field in _FIELD_ORDER
    }
    unicode_averages = {
        field: total_unicode_field_lengths[field] / count if count else 0.0
        for field in _FIELD_ORDER
    }
    return _SearchCorpus(tuple(documents), document_frequency, averages, unicode_averages)


def _idf(term: str, corpus: _SearchCorpus) -> float:
    count = len(corpus.documents)
    frequency = corpus.document_frequency[term]
    return math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))


def _contains_tokens(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    size = len(needle)
    return any(
        haystack[index : index + size] == needle for index in range(len(haystack) - size + 1)
    )


def _unique_query_tokens(query: str) -> tuple[str, ...]:
    """Unique query words in first-seen order, except that the word the user typed
    last stays last, since it is the one treated as still being typed."""
    tokens = _tokens(query)
    unique = dict.fromkeys(tokens)
    if tokens:
        unique.pop(tokens[-1])
        unique[tokens[-1]] = None
    return tuple(unique)


def validate_search_query(query: str) -> str:
    """Normalize and validate a search query without loading catalog data."""
    normalized = " ".join(str(query).split())
    if not _unique_query_tokens(normalized):
        raise QueryError(
            "query must contain at least one letter or number",
            code="invalid_query",
            status=400,
        )
    return normalized


def _prefix_term(query_tokens: tuple[str, ...]) -> str | None:
    """The word still being typed. The search box searches as you type, so the
    last query word also matches the words that start with it. Only ASCII words
    qualify: CJK tokens are character pairs, and a one-character prefix of a pair
    would match every pair that starts with that character."""
    last = query_tokens[-1]
    return last if len(last) >= _MIN_PREFIX_LENGTH and last.isascii() else None


def _prefix_counts(document: _SearchDocument, term: str) -> dict[str, int]:
    """Per field, how many tokens start with `term` without being `term`."""
    counts: dict[str, int] = {}
    for field, field_counts in document.field_counts.items():
        total = sum(
            count
            for token, count in field_counts.items()
            if token != term and token.startswith(term)
        )
        if total:
            counts[field] = total
    return counts


def _name_match(
    name_tokens: tuple[str, ...], query_tokens: tuple[str, ...]
) -> tuple[int, str] | None:
    if name_tokens == query_tokens:
        return 0, "exact name match"
    head = name_tokens[: len(query_tokens)]
    if head == query_tokens or (
        len(head) == len(query_tokens)
        and head[:-1] == query_tokens[:-1]
        and _prefix_term(query_tokens) is not None
        and head[-1].startswith(query_tokens[-1])
    ):
        return 1, "name prefix match"
    if _contains_tokens(name_tokens, query_tokens):
        return 2, "name token-sequence match"
    return None


def _bm25f_score(
    document: _SearchDocument,
    query_tokens: tuple[str, ...],
    corpus: _SearchCorpus,
    prefix_counts: dict[str, int],
) -> float:
    score = 0.0
    for term in query_tokens:
        weighted_frequency = 0.0
        for field in _FIELD_ORDER:
            frequency = document.field_counts[field][term]
            # A word that exists in the corpus keeps its whole-word scores, so
            # finishing "agent" does not reorder results; an unknown fragment such
            # as "saf" has no whole-word score, so its prefix hits supply it.
            if prefix_counts and term == query_tokens[-1] and not corpus.document_frequency[term]:
                frequency += prefix_counts.get(field, 0)
            if not frequency:
                continue
            # CJK bigrams expand descriptions that were invisible to English
            # search. Keep ASCII length normalization on its original token
            # population so adding Unicode support does not reorder English hits.
            if term.isascii():
                field_length = document.field_ascii_lengths[field]
                average_length = corpus.average_field_lengths[field] or 1.0
            else:
                field_length = document.field_unicode_lengths[field]
                average_length = corpus.average_unicode_field_lengths[field] or 1.0
            length_normalization = 1.0 - _BM25_B + _BM25_B * (field_length / average_length)
            weighted_frequency += _FIELD_WEIGHTS[field] * frequency / length_normalization
        if weighted_frequency:
            score += _idf(term, corpus) * (
                weighted_frequency * (_BM25_K1 + 1.0) / (_BM25_K1 + weighted_frequency)
            )
    return score


def _match(
    document: _SearchDocument,
    *,
    query_tokens: tuple[str, ...],
    corpus: _SearchCorpus,
) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
    query_token_set = set(query_tokens)
    prefix_term = _prefix_term(query_tokens)
    prefix_counts = _prefix_counts(document, prefix_term) if prefix_term else {}
    if document.all_tokens.isdisjoint(query_token_set) and not prefix_counts:
        return None

    matched_fields: list[str] = []
    matched_tokens: set[str] = set()
    for field in _FIELD_ORDER:
        hits = query_token_set.intersection(document.field_counts[field])
        if field in prefix_counts:
            hits.add(prefix_term)
        if hits:
            matched_fields.append(field)
            matched_tokens.update(hits)
    # Issue #432: for a multi-word query, a record matching one query token
    # in description only is noise, not evidence. Generic prose words (e.g.
    # "prediction") fill every slot while the rarer query words match
    # nothing. A single token in a name, category or other field still
    # counts, as does a one-word query.
    if len(query_tokens) > 1 and len(matched_tokens) == 1 and matched_fields == ["description"]:
        return None
    name_match = _name_match(document.field_tokens["name"], query_tokens)

    coverage = len(matched_tokens) / len(query_tokens)
    query_weight = sum(_idf(term, corpus) for term in query_tokens)
    matched_weight = sum(_idf(term, corpus) for term in matched_tokens)
    idf_coverage = matched_weight / query_weight if query_weight else 0.0

    if name_match is not None:
        name_tier, reason = name_match
    elif len(matched_tokens) == len(query_tokens):
        name_tier = 3
        reason = "all query tokens matched across fields"
    else:
        name_tier = 4
        reason = (
            f"{len(matched_tokens)} of {len(query_tokens)} unique query tokens matched "
            f"across fields; IDF coverage {idf_coverage:.2f}"
        )

    bm25f_score = _bm25f_score(document, query_tokens, corpus, prefix_counts)
    phrase_fields = [
        field
        for field in _FIELD_ORDER
        if _contains_tokens(document.field_tokens[field], query_tokens)
    ]
    # BM25F already rewards matching more query terms, so IDF coverage is
    # only a tie-breaker and explanation. Exactness and phrase proximity are the
    # two conventional secondary signals. Scale both by query IDF instead of
    # mixing giant fixed constants into a corpus-dependent lexical score.
    non_name_phrase = any(field != "name" for field in phrase_fields)
    phrase_bonus = query_weight * _PHRASE_MULTIPLIER if non_name_phrase else 0.0
    name_bonus = (
        query_weight * _NAME_MATCH_MULTIPLIERS[name_match[0]] if name_match is not None else 0.0
    )
    retrieval_score = bm25f_score + phrase_bonus + name_bonus

    record = document.record
    completeness = sum(
        1 for field in ("publisher", "released", "modality") if record.get(field) not in (None, "")
    ) + sum(1 for field in ("has_paper", "has_repo", "has_dataset") if record.get(field))
    sort_key = (
        -retrieval_score,
        -idf_coverage,
        name_tier,
        -completeness,
        len(str(record.get("name") or "")),
        str(record.get("name") or "").casefold(),
        str(record.get("key") or ""),
    )
    return (
        sort_key,
        {
            "ranking_algorithm": "bm25f_v3",
            "retrieval_score": round(retrieval_score, 6),
            "score_components": {
                "bm25f": round(bm25f_score, 6),
                "phrase_bonus": round(phrase_bonus, 6),
                "name_bonus": round(name_bonus, 6),
            },
            "matched_fields": matched_fields,
            "matched_tokens": sorted(matched_tokens),
            "missing_tokens": sorted(set(query_tokens) - matched_tokens),
            "query_coverage": round(coverage, 4),
            "idf_coverage": round(idf_coverage, 4),
            "phrase_fields": phrase_fields,
            "reason": reason,
        },
    )


class QueryService:
    """Load local Radar artifacts and expose one query contract to every interface."""

    def __init__(self, paths: QueryPaths | None = None):
        self.paths = paths or QueryPaths()
        self._index: dict[str, Any] | None = None
        self._snapshots: list[dict[str, Any]] | None = None
        self._validated_shards: int | None = None

    def _load_index(self) -> dict[str, Any]:
        if self._index is None:
            index = _read_object(self.paths.index, label="benchmark index")
            if index.get("schema_version") != 1:
                raise QueryError(
                    f"benchmark index schema {index.get('schema_version')!r} is unsupported",
                    code="unsupported_schema",
                )
            records = index.get("benchmarks")
            if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
                raise QueryError(
                    "benchmark index benchmarks must be an array of objects",
                    code="invalid_data",
                )
            if index.get("count") != len(records):
                raise QueryError(
                    "benchmark index count does not match its records",
                    code="invalid_data",
                )
            for position, record in enumerate(records):
                _validate_index_record(record, position=position)
            keys = [record["key"] for record in records]
            slugs = [record["slug"] for record in records]
            if len(keys) != len(set(keys)) or len(slugs) != len(set(slugs)):
                raise QueryError(
                    "benchmark index keys and slugs must be unique",
                    code="invalid_data",
                )
            self._index = index
        return self._index

    def _load_snapshots(self) -> list[dict[str, Any]]:
        if self._snapshots is None:
            if not self.paths.snapshots.exists():
                raise QueryError(
                    f"snapshot directory is missing at {self.paths.snapshots}",
                    code="data_unavailable",
                    status=503,
                )
            try:
                snapshots = load_snapshots(self.paths.snapshots)
            except Exception as error:
                raise QueryError(
                    f"cannot load snapshots from {self.paths.snapshots}: "
                    f"{type(error).__name__}: {error}",
                    code="invalid_data",
                ) from error
            if not snapshots:
                raise QueryError(
                    f"snapshot directory has no JSON snapshots at {self.paths.snapshots}",
                    code="data_unavailable",
                    status=503,
                )
            self._snapshots = snapshots
        return self._snapshots

    def _catalog_candidates(self) -> list[dict[str, Any]]:
        return [{"kind": "catalog", **record} for record in self._load_index()["benchmarks"]]

    def _validate_detail_shards(self) -> int:
        if self._validated_shards is not None:
            return self._validated_shards
        index = self._load_index()
        for record in index["benchmarks"]:
            path = self.paths.shards / f"{record['slug']}.json"
            shard = _read_object(path, label="benchmark detail shard")
            shard_record = shard.get("record")
            if not isinstance(shard_record, dict) or shard_record.get("key") != record["key"]:
                raise QueryError(
                    f"detail shard {path} does not match catalog key {record['key']}",
                    code="invalid_data",
                )
        self._validated_shards = index["count"]
        return self._validated_shards

    def validated_catalog_index(self) -> dict[str, Any]:
        """Return the catalog index after validating its records and detail shards."""
        index = self._load_index()
        self._validate_detail_shards()
        return index

    def _radar_candidates(self) -> list[dict[str, Any]]:
        latest_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
        for snapshot in self._load_snapshots():
            for item in snapshot["evidence_items"]:
                source = str(item.get("source") or "")
                source_id = str(item.get("source_id") or "")
                identity = source_id
                if source == "Hugging Face":
                    # Hub kinds have independent owner/name namespaces. Use
                    # the primary repository URL, excluding related artifacts,
                    # to keep each kind's latest observation and public key.
                    identity = exact_artifact_key(
                        {"source": source, "source_id": source_id, "url": item.get("url")}
                    )
                urls = [str(item.get("url") or ""), *(item.get("artifact_urls") or [])]
                latest_by_identity[(source, identity)] = {
                    "kind": "radar",
                    "key": f"radar:{source.casefold()}:{identity}",
                    "slug": None,
                    "name": str(item.get("title") or ""),
                    "description": str(item.get("summary") or ""),
                    "categories": list(item.get("categories") or []),
                    # Derived here rather than copied from the snapshot:
                    # stored snapshots predate the field, so a plain copy
                    # would hand every historical record an empty list on
                    # this surface while radar.json showed tags (issue #511
                    # review BLOCKER). Same function, same output.
                    "science_domains": science_domains_for_record(item),
                    "publisher": " ".join(item.get("organizations") or []),
                    "authors": [str(name) for name in item.get("authors") or []],
                    "modality": None,
                    "languages": [],
                    "source": source,
                    "source_id": source_id,
                    "url": item.get("url"),
                    "artifact_urls": list(item.get("artifact_urls") or []),
                    "published_at": item.get("published_at"),
                    "updated_at": item.get("updated_at"),
                    "score": item.get("total_score"),
                    "recommended": item.get("recommended", False),
                    "openness": None,
                    "has_paper": any("arxiv.org" in value for value in urls),
                    "has_repo": any("github.com" in value for value in urls),
                    "has_dataset": any(
                        "huggingface.co/datasets/" in value or "kaggle.com/datasets/" in value
                        for value in urls
                    ),
                    "has_size": False,
                    "snapshot_date": snapshot["date"],
                }
        return list(latest_by_identity.values())

    def _provenance(self) -> dict[str, Any]:
        # Provenance retains the full citation formats for existing consumers.
        # Research payloads also expose required_citations as the dependency contract.
        return {
            "source": "local",
            "citation": citation_block(),
            **({"data_version": self.paths.data_version} if self.paths.data_version else {}),
            **({"generated_at": self.paths.generated_at} if self.paths.generated_at else {}),
            **({"synced_at": self.paths.synced_at} if self.paths.synced_at else {}),
        }

    def _data_summary(self, *, scope: str) -> dict[str, Any]:
        value = self._provenance()
        if scope in {"catalog", "all"}:
            index = self._load_index()
            value.update(
                {
                    "catalog_path": str(self.paths.index),
                    "catalog_schema_version": index["schema_version"],
                    "catalog_count": index["count"],
                }
            )
        if scope in {"radar", "all"}:
            snapshots = self._load_snapshots()
            value.update(
                {
                    "snapshot_path": str(self.paths.snapshots),
                    "snapshot_count": len(snapshots),
                    "latest_date": snapshots[-1]["date"],
                    "latest_generated_at": snapshots[-1]["generated_at"],
                }
            )
        return value

    def search(
        self,
        query: str,
        *,
        scope: str = "catalog",
        limit: int = 20,
        has_paper: bool | None = None,
        has_repo: bool | None = None,
        has_dataset: bool | None = None,
        openness: str | None = None,
        modality: str | None = None,
        source: str | None = None,
        sources: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        query = validate_search_query(query)
        query_tokens = _unique_query_tokens(query)
        if scope not in SEARCH_SCOPES:
            raise QueryError(
                f"scope must be one of {', '.join(SEARCH_SCOPES)}",
                code="invalid_scope",
                status=400,
            )
        if limit < 1 or limit > 200:
            raise QueryError(
                "limit must be between 1 and 200",
                code="invalid_limit",
                status=400,
            )
        filters = {
            key: value
            for key, value in {
                "has_paper": has_paper,
                "has_repo": has_repo,
                "has_dataset": has_dataset,
                "openness": openness,
                "modality": modality,
                "source": source,
            }.items()
            if value is not None
        }
        if sources is not None:
            filters["sources"] = sorted(_filter_value(value) for value in sources)
        candidates: list[dict[str, Any]] = []
        if scope in {"catalog", "all"}:
            candidates.extend(self._catalog_candidates())
        if scope in {"radar", "all"}:
            candidates.extend(self._radar_candidates())

        corpus = _build_search_corpus(candidates)
        scored: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        candidate_count = 0
        weak_filtered_count = 0
        filter_excluded_match_count = 0
        query_token_set = set(query_tokens)
        for document in corpus.documents:
            record = document.record
            if not _matches_filter(record, filters):
                # The filter hid this record before overlap was tracked, so
                # a name hit outside the filter looked like no record
                # matched at all. Count a whole-token sharer here (same
                # whole-token test as the weak-hit count; a prefix-only
                # sharer is not counted) so the reason can say so.
                if not document.all_tokens.isdisjoint(query_token_set):
                    filter_excluded_match_count += 1
                continue
            match = _match(document, query_tokens=query_tokens, corpus=corpus)
            if match is None:
                # _match drops a record for zero overlap or for the #432
                # description-only floor. One it drops despite sharing a
                # query token is a weak hit the policy hid, not proof that
                # nothing shares a word; count it so the reason can say so.
                # (A prefix-only sharer is not counted: a prefix is not a
                # whole-token match.)
                if not document.all_tokens.isdisjoint(query_token_set):
                    weak_filtered_count += 1
                continue
            candidate_count += 1
            sort_key, explanation = match
            scored.append((sort_key, {**record, "match": explanation}))
        scored.sort(key=lambda value: value[0])
        full_match_count = sum(not record["match"]["missing_tokens"] for _, record in scored)
        partial_match_count = len(scored) - full_match_count
        results = [
            {**record, "rank": rank} for rank, (_, record) in enumerate(scored[:limit], start=1)
        ]
        if full_match_count:
            status = "full_matches_found"
            decision = "matches"
            decision_reason = "at least one record matched every query token"
        elif partial_match_count:
            status = "partial_candidates_only"
            decision = "no_confident_match"
            decision_reason = (
                "no record matched every query token; partial candidates "
                "share only some query tokens"
            )
        else:
            status = "no_lexical_candidates"
            decision = "no_confident_match"
            reasons: list[str] = []
            if weak_filtered_count:
                noun = "record" if weak_filtered_count == 1 else "records"
                reasons.append(
                    f"{weak_filtered_count} {noun} shared a query token but "
                    "only a single token in description"
                )
            if filter_excluded_match_count:
                noun = "record" if filter_excluded_match_count == 1 else "records"
                verb = "was" if filter_excluded_match_count == 1 else "were"
                reasons.append(
                    f"{filter_excluded_match_count} {noun} shared a query token "
                    f"but {verb} excluded by the active filters"
                )
            if reasons:
                decision_reason = "no candidate passed the matching policy; " + "; ".join(reasons)
            else:
                decision_reason = "no record matched any query token"
        LOGGER.info(
            "lexical search query=%r scope=%s documents=%d candidates=%d full=%d partial=%d "
            "returned=%d status=%s",
            query,
            scope,
            len(corpus.documents),
            candidate_count,
            full_match_count,
            partial_match_count,
            len(results),
            status,
        )
        return {
            "schema_version": QUERY_SCHEMA_VERSION,
            "query": query,
            "scope": scope,
            "retrieval_mode": "lexical",
            "search_status": status,
            "decision": decision,
            "decision_reason": decision_reason,
            "matching_policy": {
                "name": "lexical_candidates_v2",
                "ranking": "bm25f_v3",
                "minimum_should_match": (
                    "one unique query term, except a lone description-only "
                    "token for a multi-word query"
                ),
                "query_coverage": "tie-breaker and explanation",
                "idf_coverage": "tie-breaker and explanation using smoothed query IDF",
            },
            "filters": filters,
            "limit": limit,
            "candidate_count": candidate_count,
            "total_matches": len(scored),
            "weak_filtered_count": weak_filtered_count,
            "filter_excluded_match_count": filter_excluded_match_count,
            "full_match_count": full_match_count,
            "partial_match_count": partial_match_count,
            "count": len(results),
            "data": self._data_summary(scope=scope),
            "required_citations": required_citations(),
            "results": results,
        }

    def related_work(
        self,
        topics: list[str],
        *,
        per_topic: int = 6,
        include_partial: bool = False,
        include_radar: bool = True,
        manuscript: ManuscriptContext | None = None,
    ) -> dict[str, Any]:
        """Draft a cited related-work section from topic queries (issues #549, #650)."""
        from .related_work import build_related_work

        return build_related_work(
            self,
            topics,
            per_topic=per_topic,
            include_partial=include_partial,
            include_radar=include_radar,
            manuscript=manuscript,
        )

    def show(self, identifier: str) -> dict[str, Any]:
        identifier = str(identifier).strip()
        if not identifier:
            raise QueryError(
                "benchmark identifier is required",
                code="invalid_identifier",
                status=400,
            )
        matches = [
            record
            for record in self._load_index()["benchmarks"]
            if identifier in {str(record.get("key")), str(record.get("slug"))}
        ]
        if not matches:
            raise QueryError(
                f"benchmark {identifier!r} was not found in the catalog index",
                code="not_found",
                status=404,
            )
        if len(matches) != 1:
            raise QueryError(
                f"benchmark identifier {identifier!r} resolves to multiple catalog records",
                code="invalid_data",
            )
        record = matches[0]
        path = self.paths.shards / f"{record['slug']}.json"
        if not path.exists():
            raise QueryError(
                f"detail shard is missing at {path}; run `benchmark-radar normalize-catalog`",
                code="data_unavailable",
                status=503,
            )
        shard = _read_object(path, label="benchmark detail shard")
        shard_record = shard.get("record")
        if not isinstance(shard_record, dict):
            raise QueryError(
                f"detail shard {path} record must be a JSON object",
                code="invalid_data",
            )
        if shard_record.get("key") != record["key"]:
            raise QueryError(
                f"detail shard {path} does not match catalog key {record['key']}",
                code="invalid_data",
            )
        return {
            "schema_version": QUERY_SCHEMA_VERSION,
            "identifier": record["key"],
            "retrieval_mode": "direct",
            "data": {
                **self._data_summary(scope="catalog"),
                "catalog_path": str(self.paths.index),
                "shard_path": str(path),
            },
            "required_citations": required_citations(),
            "benchmark": shard,
        }

    def trace(self, identifier: str) -> dict[str, Any]:
        """Trace one record through the locally available pipeline artifacts.

        This intentionally reports absent stages instead of manufacturing a
        record from a later artifact.  That makes an incomplete local checkout
        useful for diagnosis while keeping the command read-only and offline.
        """
        identifier = str(identifier).strip()
        if not identifier:
            raise QueryError(
                "benchmark identifier is required",
                code="invalid_identifier",
                status=400,
            )

        index = self._load_index()
        catalog = next(
            (
                row
                for row in index["benchmarks"]
                if identifier in {str(row.get("key")), str(row.get("slug"))}
            ),
            None,
        )
        root = _trace_repo_root(self.paths.index)
        normalized_row: dict[str, Any] | None = None
        normalized_path: Path | None = None
        if root is not None:
            catalog_dir = root / "data" / "catalog"
            targets = {identifier}
            if catalog is not None:
                targets.update({str(catalog.get("key")), str(catalog.get("slug"))})
            matches: list[tuple[dict[str, Any], Path]] = []
            if catalog_dir.is_dir():
                for path in sorted(catalog_dir.glob("*_source_records.jsonl")):
                    try:
                        rows = [
                            json.loads(line)
                            for line in path.read_text(encoding="utf-8").splitlines()
                        ]
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise QueryError(
                            f"cannot read source records at {path}: "
                            f"{type(error).__name__}: {error}",
                            code="invalid_data",
                        ) from error
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        if catalog is not None:
                            if row.get("key") == catalog["key"]:
                                matches.append((row, path))
                        elif targets & {
                            str(row.get("key")),
                            str(row.get("slug")),
                            str(row.get("source_benchmark_id")),
                        }:
                            matches.append((row, path))
            # An exact key is unambiguous. Otherwise every source that shares
            # an unqualified ID (llm-stats and Artificial Analysis both carry
            # aime-2025) is a candidate, and choosing by filename order would
            # trace a different benchmark than the caller meant.
            exact = [match for match in matches if match[0].get("key") == identifier]
            if exact:
                matches = exact
            keys = sorted({str(row.get("key")) for row, _ in matches})
            if len(keys) > 1:
                raise QueryError(
                    "ambiguous normalized source identifier; use a full key: " + ", ".join(keys),
                    code="ambiguous_identifier",
                    status=400,
                )
            if matches:
                normalized_row, normalized_path = matches[0]

        # Consult Radar only when nothing in the catalog resolves the
        # identifier. A record that exists only in the normalized source rows
        # must still trace in a checkout without data/snapshots, where loading
        # Radar would raise data_unavailable before any stage is reported.
        radar_matches = (
            []
            if catalog is not None or normalized_row is not None
            else [
                row
                for row in self._radar_candidates()
                if identifier in {str(row.get("key")), str(row.get("source_id"))}
            ]
        )
        if len(radar_matches) > 1:
            raise QueryError(
                "ambiguous Radar source identifier; use a full Radar key: "
                + ", ".join(str(row["key"]) for row in radar_matches),
                code="ambiguous_identifier",
                status=400,
            )
        radar = radar_matches[0] if len(radar_matches) == 1 else None

        shard: dict[str, Any] | None = None
        shard_path: Path | None = None
        if catalog is not None:
            shard_path = self.paths.shards / f"{catalog['slug']}.json"
            if shard_path.exists():
                shard = _read_object(shard_path, label="benchmark detail shard")

        siblings = shard.get("siblings", []) if shard is not None else []
        if not isinstance(siblings, list) or any(not isinstance(row, dict) for row in siblings):
            raise QueryError(
                f"benchmark detail shard at {shard_path} must have a list of sibling objects",
                code="invalid_data",
            )

        raw_shard_record = shard.get("record") if isinstance(shard, dict) else None
        shard_record_valid = isinstance(raw_shard_record, dict)
        shard_record = raw_shard_record if shard_record_valid else {}
        raw_row, raw_path, raw_state = _trace_raw_row(root, catalog, normalized_row, shard_record)
        shard_key = shard_record.get("key")
        shard_key_mismatch = (
            catalog is not None and shard is not None and shard_key != catalog.get("key")
        )

        stages: list[dict[str, Any]] = []

        def add_stage(
            name: str,
            value: Any,
            *,
            path: Path | None = None,
            input_value: Any = None,
            changes: list[dict[str, Any]] | None = None,
        ) -> None:
            present = value is not None
            stage: dict[str, Any] = {
                "stage": name,
                "status": "absent" if not present else ("changed" if changes else "present"),
                "path": str(path) if path else None,
                "input": input_value,
                "output": value,
                "changes": changes or [],
            }
            if not present:
                stage["error"] = "artifact is missing locally"
            stages.append(stage)

        if raw_state == "found":
            source_value = raw_row
            source_stage_path = raw_path
        elif raw_state == "missing":
            source_value = None
            source_stage_path = raw_path
        else:
            source_value = normalized_row or radar
            source_stage_path = normalized_path if normalized_row is not None else None
        add_stage("source", source_value, path=source_stage_path)
        if raw_state == "missing":
            if raw_path is not None and raw_path.exists():
                stages[-1]["error"] = f"no raw input row for this record in {raw_path}"
            else:
                stages[-1]["error"] = f"raw input artifact missing at {raw_path}"
        if normalized_row is not None:
            norm_changes: list[dict[str, Any]] = []
            restructured: list[str] = []
            if raw_row is not None:
                norm_changes, restructured = _trace_normalization_diff(raw_row, normalized_row)
                norm_changes.extend(
                    _trace_snapshot_changes(raw_row, normalized_row, normalized_path)
                )
            add_stage(
                "normalization",
                normalized_row,
                path=normalized_path,
                input_value=raw_row,
                changes=norm_changes,
            )
            notes = []
            if raw_state == "missing":
                notes.append("raw input row absent; normalized row is the earliest artifact")
            elif raw_row is None:
                notes.append("no raw input artifact found for this source")
            if restructured:
                notes.append(
                    "fields restructured by normalization: " + ", ".join(restructured[:10])
                )
            if notes:
                stages[-1]["note"] = "; ".join(notes)
        else:
            add_stage(
                "normalization",
                None,
                input_value=raw_row,
            )

        identity_path = (
            root / "data" / "catalog" / "identity.yml"
            if root is not None and (root / "data" / "catalog" / "identity.yml").exists()
            else None
        )
        population = (
            _trace_identity_population(root, index["benchmarks"]) if root is not None else None
        )
        declared = (
            _trace_declared_pairs(root, population)
            if root is not None and population is not None
            else None
        )
        identity_value = None
        identity_changes: list[dict[str, Any]] = []
        rebuilt: dict[str, Any] | None = None
        if catalog is not None and declared is not None:
            equivalent, variants, peers = declared
            if normalized_row is not None and root is not None and population is not None:
                rebuilt = _trace_rebuild(root, population, str(catalog.get("key")))
                if rebuilt is None:
                    identity_changes.append(
                        {
                            "field": "record",
                            "before": "in benchmark-index.json",
                            "after": "absent from current normalized source records",
                        }
                    )
                else:
                    identity_changes.extend(_trace_field_changes(catalog, rebuilt["index_row"]))
                    identity_changes.extend(
                        _trace_sibling_descriptor_changes(siblings, rebuilt["shard"]["siblings"])
                    )
                    identity_changes.extend(
                        _trace_donor_changes(root, rebuilt["inheritance"], index["benchmarks"])
                    )
            if shard is not None:
                for sibling in siblings:
                    sibling_key = str(sibling.get("key") or "")
                    pair = frozenset({str(catalog.get("key")), sibling_key})
                    relation = str(sibling.get("relation") or "")
                    declared_relation = (
                        pair in equivalent
                        if relation == "equivalent"
                        else (str(catalog["key"]), sibling_key, relation) in variants
                    )
                    if not declared_relation:
                        identity_changes.append(
                            {
                                "field": f"siblings.{sibling_key}",
                                "before": relation or "sibling",
                                "after": "not declared by current identity.yml",
                            }
                        )
                sibling_keys = {str(sibling.get("key")) for sibling in siblings}
                for peer in sorted(peers.get(str(catalog.get("key")), set()) - sibling_keys):
                    identity_changes.append(
                        {
                            "field": f"identity.{peer}",
                            "before": "declared in identity.yml",
                            "after": "absent from shard siblings",
                        }
                    )
            identity_value = {"record": catalog, "siblings": siblings}
        add_stage(
            "identity",
            identity_value,
            path=identity_path,
            input_value=normalized_row if normalized_row is not None else raw_row,
            changes=identity_changes,
        )
        if identity_value is not None and shard is None:
            stages[-1]["note"] = (
                "detail shard missing; sibling joins cannot be verified against the rules"
            )

        enrichment = None
        enrichment_changes: list[dict[str, Any]] = []
        enrichment_restructured: list[str] = []
        if shard is not None:
            enrichment = {
                "record": shard_record.copy(),
                "scores_by_source": shard.get("scores_by_source", {}),
            }
            if not shard_record_valid:
                enrichment_changes.append(
                    {
                        "field": "record",
                        "before": "object",
                        "after": type(raw_shard_record).__name__,
                    }
                )
            elif shard_key_mismatch:
                enrichment_changes.append(
                    {
                        "field": "record.key",
                        "before": catalog.get("key") if catalog else None,
                        "after": shard_key,
                    }
                )
            elif catalog is not None:
                content_changes, enrichment_restructured = _trace_normalization_diff(
                    catalog, shard_record
                )
                enrichment_changes.extend(content_changes)
            # The record can agree while an interrupted shard swap leaves old
            # scores behind, so compare the score payload build_shard writes.
            if rebuilt is not None and not shard_key_mismatch:
                enrichment_changes.extend(
                    _trace_field_changes(
                        shard.get("scores_by_source") or {},
                        rebuilt["shard"]["scores_by_source"],
                        "scores_by_source.",
                    )
                )
        add_stage(
            "enrichment",
            enrichment,
            path=shard_path,
            input_value=identity_value,
            changes=enrichment_changes,
        )
        if enrichment_restructured:
            stages[-1]["note"] = "fields restructured between index and shard record: " + ", ".join(
                enrichment_restructured[:10]
            )

        outputs: dict[str, Any] = {}
        if catalog is not None:
            outputs["benchmark-index.json"] = {
                "path": str(self.paths.index),
                "contains": True,
            }
        if shard is not None:
            outputs["shard"] = {
                "path": str(shard_path),
                "record_key": shard_key,
                "matches_target": not shard_key_mismatch,
            }
        output_changes: list[dict[str, Any]] = []
        if catalog is not None and root is not None:
            page = root / "site" / "benchmarks" / str(catalog["slug"]) / "index.html"
            if page.exists():
                outputs["benchmark-page"] = {"path": str(page), "contains": True}
            # write_exports refuses a CSV/JSON export unless every index slug
            # is an entry, so membership is checked for every source by the
            # catalog slug. Markdown is intentionally top-N and only reported.
            for name, entry in _trace_export_contains(root, str(catalog["slug"])).items():
                outputs[f"export:{name}"] = entry
                if entry.get("error"):
                    output_changes.append(
                        {"field": f"export:{name}", "before": "readable", "after": entry["error"]}
                    )
                elif name != "leaderboard.md" and entry.get("contains") is False:
                    output_changes.append(
                        {
                            "field": f"export:{name}",
                            "before": "contains this record",
                            "after": "record missing from full export",
                        }
                    )
        add_stage("outputs", outputs or None, input_value=enrichment, changes=output_changes)
        first_change = next(
            (stage["stage"] for stage in stages if stage["status"] in {"changed", "absent"}), None
        )
        return {
            "schema_version": QUERY_SCHEMA_VERSION,
            "identifier": identifier,
            "retrieval_mode": "direct_trace",
            "data": {
                **self._data_summary(scope="catalog"),
                "catalog_path": str(self.paths.index),
            },
            "required_citations": required_citations(),
            "status": "present" if catalog or radar else "missing",
            "first_change": first_change,
            "stages": stages,
        }

    def recent(
        self,
        *,
        limit: int = 20,
        category: str | None = None,
        source: str | None = None,
        recommended: bool = False,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise QueryError(
                "limit must be between 1 and 200",
                code="invalid_limit",
                status=400,
            )
        latest = self._load_snapshots()[-1]
        results = []
        for item in latest["evidence_items"]:
            if category and _filter_value(category) not in {
                _filter_value(value) for value in item.get("categories") or []
            }:
                continue
            if source and _filter_value(item.get("source")) != _filter_value(source):
                continue
            if recommended and item.get("recommended") is not True:
                continue
            # Same derivation the dashboard publishes, so `recent` and
            # `search` cannot disagree about a record's domains.
            results.append({**item, "science_domains": science_domains_for_record(item)})
        results = results[:limit]
        return {
            "schema_version": QUERY_SCHEMA_VERSION,
            "retrieval_mode": "latest_snapshot",
            "date": latest["date"],
            "generated_at": latest["generated_at"],
            "filters": {
                key: value
                for key, value in {
                    "category": category,
                    "source": source,
                    "recommended": True if recommended else None,
                }.items()
                if value is not None
            },
            "limit": limit,
            "count": len(results),
            "data": self._data_summary(scope="radar"),
            "required_citations": required_citations(),
            "results": results,
        }

    def status(self) -> dict[str, Any]:
        index = self._load_index()
        snapshots = self._load_snapshots()
        latest = snapshots[-1]
        expected_shards = {f"{record['slug']}.json" for record in index["benchmarks"]}
        existing_shards = (
            {path.name for path in self.paths.shards.glob("*.json")}
            if self.paths.shards.is_dir()
            else set()
        )
        missing_shards = sorted(expected_shards - existing_shards)
        validated_shard_count = 0 if missing_shards else self._validate_detail_shards()
        health = {str(item.get("source")): item for item in latest.get("ingest_health") or []}
        gaps = sorted(
            source
            for source in REQUIRED_SOURCES
            if source not in health or health[source].get("ok") is not True
        )
        return {
            "schema_version": QUERY_SCHEMA_VERSION,
            "retrieval_mode": "health_check",
            "data": self._provenance(),
            "status": "ok" if not gaps and not missing_shards else "degraded",
            "catalog": {
                "path": str(self.paths.index),
                "schema_version": index["schema_version"],
                "count": index["count"],
                "shard_path": str(self.paths.shards),
                "shard_count": len(existing_shards),
                "validated_shard_count": validated_shard_count,
                "complete": not missing_shards,
                "missing_shard_count": len(missing_shards),
                "missing_shards": missing_shards[:20],
            },
            "radar": {
                "path": str(self.paths.snapshots),
                "snapshot_count": len(snapshots),
                "latest_date": latest["date"],
                "latest_generated_at": latest["generated_at"],
                "required_coverage_complete": not gaps,
                "required_coverage_gaps": gaps,
                "ingest_health": latest.get("ingest_health") or [],
            },
        }
