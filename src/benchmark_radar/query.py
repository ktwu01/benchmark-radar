"""Shared read-only query service for CLI and HTTP benchmark discovery."""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .snapshots import REQUIRED_SOURCES, load_snapshots

QUERY_SCHEMA_VERSION = 6
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
    "source_id",
)
_FIELD_WEIGHTS = {
    "name": 5.0,
    "description": 1.0,
    "categories": 2.5,
    "publisher": 0.6,
    "modality": 1.2,
    "languages": 0.3,
    "source": 0.2,
    "source_id": 1.0,
}
_BM25_K1 = 1.2
_BM25_B = 0.75
_NAME_MATCH_MULTIPLIERS = (3.0, 1.5, 0.75)
_PHRASE_MULTIPLIER = 0.5

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
            f"{label} is missing at {path}; run `benchmark-radar normalize-external` "
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
    return tuple(re.findall(r"[a-z0-9]+", normalized))


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
    return True


@dataclass(frozen=True, slots=True)
class _SearchDocument:
    record: dict[str, Any]
    field_tokens: dict[str, tuple[str, ...]]
    field_counts: dict[str, Counter[str]]
    all_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class _SearchCorpus:
    documents: tuple[_SearchDocument, ...]
    document_frequency: Counter[str]
    average_field_lengths: dict[str, float]


def _build_search_corpus(records: list[dict[str, Any]]) -> _SearchCorpus:
    documents: list[_SearchDocument] = []
    document_frequency: Counter[str] = Counter()
    total_field_lengths: Counter[str] = Counter()
    for record in records:
        field_tokens = {field: _tokens(_field_text(record.get(field))) for field in _FIELD_ORDER}
        field_counts = {field: Counter(tokens) for field, tokens in field_tokens.items()}
        all_tokens = frozenset().union(*(set(tokens) for tokens in field_tokens.values()))
        document_frequency.update(all_tokens)
        total_field_lengths.update({field: len(tokens) for field, tokens in field_tokens.items()})
        documents.append(
            _SearchDocument(
                record=record,
                field_tokens=field_tokens,
                field_counts=field_counts,
                all_tokens=all_tokens,
            )
        )
    count = len(documents)
    averages = {
        field: total_field_lengths[field] / count if count else 0.0 for field in _FIELD_ORDER
    }
    return _SearchCorpus(tuple(documents), document_frequency, averages)


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


def _name_match(
    name_tokens: tuple[str, ...], query_tokens: tuple[str, ...]
) -> tuple[int, str] | None:
    if name_tokens == query_tokens:
        return 0, "exact name match"
    if name_tokens[: len(query_tokens)] == query_tokens:
        return 1, "name prefix match"
    if _contains_tokens(name_tokens, query_tokens):
        return 2, "name token-sequence match"
    return None


def _bm25f_score(
    document: _SearchDocument,
    query_tokens: tuple[str, ...],
    corpus: _SearchCorpus,
) -> float:
    score = 0.0
    for term in query_tokens:
        weighted_frequency = 0.0
        for field in _FIELD_ORDER:
            frequency = document.field_counts[field][term]
            if not frequency:
                continue
            average_length = corpus.average_field_lengths[field] or 1.0
            length_normalization = (
                1.0 - _BM25_B + _BM25_B * (len(document.field_tokens[field]) / average_length)
            )
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
    if document.all_tokens.isdisjoint(query_token_set):
        return None

    matched_fields: list[str] = []
    matched_tokens: set[str] = set()
    for field in _FIELD_ORDER:
        hits = query_token_set.intersection(document.field_counts[field])
        if hits:
            matched_fields.append(field)
            matched_tokens.update(hits)
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

    bm25f_score = _bm25f_score(document, query_tokens, corpus)
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

    def _radar_candidates(self) -> list[dict[str, Any]]:
        latest_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
        for snapshot in self._load_snapshots():
            for item in snapshot["evidence_items"]:
                source = str(item.get("source") or "")
                source_id = str(item.get("source_id") or "")
                urls = [str(item.get("url") or ""), *(item.get("artifact_urls") or [])]
                latest_by_identity[(source, source_id)] = {
                    "kind": "radar",
                    "key": f"radar:{source.casefold()}:{source_id}",
                    "slug": None,
                    "name": str(item.get("title") or ""),
                    "description": str(item.get("summary") or ""),
                    "categories": list(item.get("categories") or []),
                    "publisher": " ".join(item.get("organizations") or []),
                    "modality": None,
                    "languages": [],
                    "source": source,
                    "source_id": source_id,
                    "url": item.get("url"),
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
        return {
            "source": "local",
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
    ) -> dict[str, Any]:
        query = " ".join(str(query).split())
        query_tokens = tuple(dict.fromkeys(_tokens(query)))
        if not query_tokens:
            raise QueryError(
                "query must contain at least one letter or number",
                code="invalid_query",
                status=400,
            )
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
        candidates: list[dict[str, Any]] = []
        if scope in {"catalog", "all"}:
            candidates.extend(self._catalog_candidates())
        if scope in {"radar", "all"}:
            candidates.extend(self._radar_candidates())

        corpus = _build_search_corpus(candidates)
        scored: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        candidate_count = 0
        for document in corpus.documents:
            record = document.record
            if not _matches_filter(record, filters):
                continue
            match = _match(document, query_tokens=query_tokens, corpus=corpus)
            if match is None:
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
        elif partial_match_count:
            status = "partial_candidates_only"
        else:
            status = "no_lexical_candidates"
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
            "matching_policy": {
                "name": "lexical_candidates_v1",
                "ranking": "bm25f_v3",
                "minimum_should_match": "one unique query term",
                "query_coverage": "tie-breaker and explanation",
                "idf_coverage": "tie-breaker and explanation using smoothed query IDF",
            },
            "filters": filters,
            "limit": limit,
            "candidate_count": candidate_count,
            "total_matches": len(scored),
            "full_match_count": full_match_count,
            "partial_match_count": partial_match_count,
            "count": len(results),
            "data": self._data_summary(scope=scope),
            "results": results,
        }

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
                f"detail shard is missing at {path}; run `benchmark-radar normalize-external`",
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
            "benchmark": shard,
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
            results.append(item)
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
