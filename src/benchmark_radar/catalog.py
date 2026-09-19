"""Normalize registered leaderboard snapshots into the shared benchmark catalog.

All adapters emit the same records, series, observations and cited documents.
Source names preserve provenance and never determine a record's eligibility.
Missing fields stay unknown until reviewed evidence supplies them. Identity
links do not merge source records, transfer scores or establish a test protocol.

LLM Stats and Artificial Analysis use the CSV adapter here. Their model-release
dates are labelled proxies, not evaluation dates. A declared maximum can be
contradicted by the observations; it never establishes a percentage scale on
its own. Each series carries its measured direction and display metadata.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

from .score_summary import score_summary

CATALOG_SCHEMA_VERSION = 1

DEFAULT_OUTPUT_DIR = Path("data/catalog")

LLM_STATS_SNAPSHOT_ID = "llm_stats_2026-08-17"
LLM_STATS_SOURCE = "llm_stats"
LLM_STATS_KEY_PREFIX = "llm-stats"

ARTIFICIAL_ANALYSIS_SNAPSHOT_ID = "artificial_analysis_2026-08-25"
ARTIFICIAL_ANALYSIS_SOURCE = "artificial_analysis"
ARTIFICIAL_ANALYSIS_KEY_PREFIX = "artificial-analysis"

# Every crawled snapshot in the registry is the same two CSVs with the same
# header vocabulary, so one normalizer reads all of them and a source is three
# strings rather than a module. A second shape would mean a second loader, a
# second normalizer, and two sets of invariants drifting apart.
SOURCES = {
    LLM_STATS_SNAPSHOT_ID: (LLM_STATS_SOURCE, LLM_STATS_KEY_PREFIX),
    ARTIFICIAL_ANALYSIS_SNAPSHOT_ID: (ARTIFICIAL_ANALYSIS_SOURCE, ARTIFICIAL_ANALYSIS_KEY_PREFIX),
}

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

# One organization, one name, across all sources.
#
# The aggregator names an organization however its own catalog spells it, and
# that spelling is not always the one the curated registry uses for the same
# company. Left unmapped, `Alibaba Cloud / Qwen Team` and `Qwen` are two
# organizations to every count, color and brand glyph on the site, and the two
# largest crawled publishers end up with no mark at all -- not because no mark
# exists, but because the key did not match.
#
# Each entry below was confirmed by reading the model lines on both sides, not
# by name similarity: the vendor's `Alibaba Cloud / Qwen Team` rows are Qwen
# models, its `Zhipu AI` rows are GLM models. Organizations that merely sound
# related are absent -- Microsoft publishes Phi and is not OpenAI, OpenBMB
# publishes MiniCPM and has no curated twin. A merge here asserts same
# publisher, so an unverified one would be a wrong attribution, which is the
# error this module exists to avoid.
#
# `Google` is canonical over the curated layer's `Google DeepMind` (issue
# #261): the releasing entity names the organization. That direction is the
# reverse of the other three, so the curated YAML was rewritten to match
# rather than aliased here -- this map only ever sees crawled vendor strings,
# and the vendor already says `Google`.
CANONICAL_ORGANIZATIONS = {
    "Alibaba Cloud / Qwen Team": "Qwen",
    "Mistral AI": "Mistral",
    "Zhipu AI": "Z.ai",
    # Artificial Analysis spells the same four vendors its own way. Each pair
    # below was confirmed the same way as the three above, by reading the model
    # lines on both sides rather than by name similarity: the `Alibaba` rows are
    # 14 Qwen models, `Kimi` publishes the Kimi K2 line Moonshot AI publishes,
    # `SpaceXAI` publishes Grok, and `Z AI` publishes GLM. Left unmapped these
    # were 20 duplicate models on the site, one under each spelling.
    "Alibaba": "Qwen",
    "Kimi": "Moonshot AI",
    "SpaceXAI": "xAI",
    "Z AI": "Z.ai",
}


def canonical_organization(name: str | None) -> str | None:
    """The one name this project uses for an organization, or None.

    Unknown names pass through unchanged: a name absent from the map is a
    distinct organization, not an error, and 29 of the 33 crawled publishers
    are exactly that.
    """
    if name is None:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    return CANONICAL_ORGANIZATIONS.get(cleaned, cleaned)


class CatalogError(ValueError):
    """Raised when a snapshot cannot be normalized into catalog records."""


def slugify(key: str) -> str:
    """A filesystem and URL safe form of a record key.

    Source ids are not safe to use as filenames. llm-stats issues ids such as
    `community:07c9946d-dcf0-4977-a640-a6b1356b4f0b`, and OpenCompass uses
    `1248__MMMU`; colons, slashes and non-ASCII all appear. The slug is emitted
    into the record so no consumer has to recompute it and risk disagreeing
    about the shard filename.
    """
    slug = _SLUG_STRIP.sub("-", key.lower()).strip("-")
    if not slug:
        raise CatalogError(f"key {key!r} has no slug-safe characters")
    return slug


def assign_slugs(keys: list[str]) -> dict[str, str]:
    """Slugs for every key, with deterministic suffixes when two collide.

    Collisions are resolved in sorted key order rather than input order so the
    same input always produces the same assignment, whatever order the rows
    happened to arrive in.
    """
    assigned: dict[str, str] = {}
    used: set[str] = set()
    for key in sorted(keys):
        base = slugify(key)
        slug = base
        count = 1
        # A "-N" suffix can land on another key's natural slug (two variants of
        # "vending bench" collide onto "vending-bench-2" while a real
        # "vending-bench-2" key already owns that slug), so keep bumping until
        # the slug is globally free rather than trusting the per-base counter.
        while slug in used:
            count += 1
            slug = f"{base}-{count}"
        used.add(slug)
        assigned[key] = slug
    return assigned


def finite_float(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def json_list(value: str) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def value_kind(raw: str, parsed: float | None) -> str:
    if not (raw or "").strip():
        return "missing"
    return "number" if parsed is not None else "text"


def _source_record(
    row: dict[str, str],
    slug: str,
    crawled_at: str,
    *,
    source: str,
    key_prefix: str,
    snapshot_id: str,
) -> dict[str, Any]:
    source_id = row["benchmark_id"].strip()
    description = (row.get("description") or "").strip()
    return {
        "key": f"{key_prefix}:{source_id}",
        "slug": slug,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source": source,
        "source_benchmark_id": source_id,
        "name": (row.get("name") or "").strip() or source_id,
        "description": {"en": description} if description else {},
        # Everything below is empty because the source carries no such field.
        # See the module docstring: these are answers, not gaps.
        "publisher": None,
        "artifacts": [],
        "openness": {
            "status": "unknown",
            "code_license": None,
            "data_license": None,
            "evidence": [],
        },
        "sizes": [],
        "released": None,
        "modality": (row.get("modality") or "").strip() or None,
        "categories": json_list(row.get("categories", "")),
        "provenance": {
            "source_url": (row.get("detail_source_url") or "").strip() or None,
            "crawled_at": crawled_at,
            "crawl_bundle": snapshot_id,
        },
    }


def _observation(
    row: dict[str, str],
    *,
    key: str,
    series_id: str,
    crawled_at: str,
    source: str,
) -> dict[str, Any]:
    raw_value = (row.get("benchmark_score") or "").strip()
    parsed = finite_float(raw_value)
    rank = (row.get("rank") or "").strip()
    # Identity is (benchmark, model_id): distinct dated checkpoints can share a
    # display name, so the name is vocabulary and the id is what a row is.
    model_id = (row.get("model_id") or "").strip() or None
    observation_identity = (
        model_id
        or "unidentified-"
        + hashlib.sha256(
            json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:20]
    )
    self_reported = (row.get("self_reported") or "").strip().lower()
    return {
        "obs_id": f"{source}:{row['benchmark_id'].strip()}:{observation_identity}",
        "key": key,
        "series_id": series_id,
        "model_name": (row.get("model_name") or "").strip(),
        "model_id": model_id,
        "organization": canonical_organization(row.get("organization_name")),
        "raw_value": raw_value,
        "value": parsed,
        "value_kind": value_kind(raw_value, parsed),
        # The source flags self-reporting but never records a protocol, so the
        # only honest comparability class is "none". Null never joins to null.
        "reported_by": (
            "self_reported"
            if self_reported == "true"
            else "third_party"
            if self_reported == "false"
            else "unknown"
        ),
        "measured_by": "Artificial Analysis" if source == ARTIFICIAL_ANALYSIS_SOURCE else None,
        "comparable_group": None,
        "rank_in_source_response": int(rank) if rank.isdigit() else None,
        "crawled_at": crawled_at,
        # This is the MODEL's own announcement date, not a measurement date: the
        # source records when a model shipped, never when this specific score
        # was run. It still orders and dates the field honestly (100% fill,
        # vs. release_date's 99.6%), which "no date at all" did not, so it is
        # kept and labelled for what it is rather than discarded because it
        # is not a full evaluation date. `date_precision` says which claim the
        # value supports.
        "reported_date": (row.get("announcement_date") or "").strip() or None,
        "date_precision": "model_announcement",
        "source_url": (row.get("source_url") or "").strip() or None,
    }


def first_score_record(
    observations: list[dict[str, Any]], *, allow_model_dates: bool = True
) -> dict[str, Any] | None:
    """Earliest dated numeric score, preserving the source's date precision."""
    precisions = {"day", "document_publication", "score_publication"}
    if allow_model_dates:
        precisions.add("model_announcement")
    reports = []
    for row in observations:
        value = row.get("value")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or row.get("date_precision") not in precisions
        ):
            continue
        reported = row.get("reported_at") or row.get("reported_date")
        try:
            if (
                not isinstance(reported, str)
                or date.fromisoformat(reported).isoformat() != reported
            ):
                continue
        except ValueError:
            continue
        reports.append(
            {
                "reported_at": reported,
                "obs_id": row.get("obs_id"),
                "source_url": row.get("source_url"),
                "date_precision": row.get("date_precision"),
            }
        )
    return min(reports, key=lambda row: (row["reported_at"], row["obs_id"] or ""), default=None)


def _series(
    row: dict[str, str],
    *,
    key: str,
    observations: list[dict[str, Any]],
    source: str,
) -> dict[str, Any]:
    declared_max = finite_float(row.get("max_score", ""))
    values = [obs["value"] for obs in observations if obs["value"] is not None]
    observed_max = max(values) if values else None
    contradicted = (
        declared_max is not None and observed_max is not None and observed_max > declared_max
    )
    return {
        "series_id": f"{source}:{row['benchmark_id'].strip()}:default",
        "key": key,
        # The API does not name the metric, so it stays null. Direction is not
        # guessed from the scale: every scored series is source-ranked in
        # descending numeric order, pinned by the snapshot invariant tests.
        "metric": None,
        "direction": "higher_is_better",
        "direction_basis": "source_rank_descending",
        "bounds": {"min": None, "max": declared_max, "basis": "aggregator_declared"},
        "declared_max": declared_max,
        "observed_max": observed_max,
        "max_score_contradicted": contradicted,
        # No scale means no percentage bar. See the module docstring.
        "display_scale": None,
        "observation_count": len(observations),
        "first_score_report": first_score_record(observations, allow_model_dates=False),
        "first_score_record": first_score_record(observations),
        "score_summary": score_summary(
            observations,
            fractional_display=True,
            declared_max=declared_max,
            max_score_contradicted=contradicted,
        ),
    }


def normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Turn one validated crawl snapshot into catalog records.

    Source-agnostic: every snapshot in the registry is the same two CSVs with
    the same header vocabulary, so the only thing that varies between them is
    the three strings in `SOURCES`. Returns source records, score series and
    observations, plus the validation counts that let a reviewer check the
    result without rereading the CSVs.
    """
    snapshot_id = snapshot["id"]
    if snapshot_id not in SOURCES:
        raise CatalogError(f"snapshot {snapshot_id!r} has no source descriptor")
    source, key_prefix = SOURCES[snapshot_id]

    benchmark_rows = snapshot["benchmark_rows"]
    score_rows = snapshot["score_rows"] or []
    crawled_at = snapshot["crawled_at"]

    keys = [f"{key_prefix}:{row['benchmark_id'].strip()}" for row in benchmark_rows]
    slugs = assign_slugs(keys)

    by_benchmark: dict[str, list[dict[str, str]]] = {}
    for row in score_rows:
        by_benchmark.setdefault(row["benchmark_id"].strip(), []).append(row)

    records: list[dict[str, Any]] = []
    series: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []

    for row in benchmark_rows:
        source_id = row["benchmark_id"].strip()
        key = f"{key_prefix}:{source_id}"
        records.append(
            _source_record(
                row,
                slugs[key],
                crawled_at,
                source=source,
                key_prefix=key_prefix,
                snapshot_id=snapshot_id,
            )
        )
        series_id = f"{source}:{source_id}:default"
        rows = by_benchmark.get(source_id, [])
        observed = [
            _observation(
                score_row, key=key, series_id=series_id, crawled_at=crawled_at, source=source
            )
            for score_row in rows
        ]
        observations.extend(observed)
        series.append(_series(row, key=key, observations=observed, source=source))

    records.sort(key=lambda item: item["key"])
    series.sort(key=lambda item: item["series_id"])

    def _order(item: dict[str, Any]) -> tuple[str, int, str]:
        rank = item["rank_in_source_response"]
        return (item["key"], rank if rank is not None else 1 << 30, item["model_id"] or "")

    observations.sort(key=_order)

    return {
        "source_records": records,
        "score_series": series,
        "score_observations": observations,
        "validation": _validation(
            records, series, observations, source=source, snapshot_id=snapshot_id
        ),
    }


def _validation(
    records: list[dict[str, Any]],
    series: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    *,
    source: str,
    snapshot_id: str,
) -> dict[str, Any]:
    seen: dict[str, int] = {}
    for obs in observations:
        seen[obs["obs_id"]] = seen.get(obs["obs_id"], 0) + 1
    collisions = sorted(obs_id for obs_id, count in seen.items() if count > 1)

    kinds: dict[str, int] = {}
    reported: dict[str, int] = {}
    for obs in observations:
        kinds[obs["value_kind"]] = kinds.get(obs["value_kind"], 0) + 1
        reported[obs["reported_by"]] = reported.get(obs["reported_by"], 0) + 1

    contradicted = [item["key"] for item in series if item["max_score_contradicted"]]
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source": source,
        "snapshot": snapshot_id,
        "source_record_count": len(records),
        "score_series_count": len(series),
        "score_observation_count": len(observations),
        "obs_id_unique": not collisions,
        "obs_id_collisions": collisions,
        "benchmarks_with_zero_observations": sorted(
            item["key"] for item in series if item["observation_count"] == 0
        ),
        "max_score_contradicted_benchmarks": sorted(contradicted),
        "max_score_contradicted_row_count": sum(
            1
            for obs in observations
            for item in series
            if item["key"] == obs["key"]
            and item["max_score_contradicted"]
            and obs["value"] is not None
            and item["declared_max"] is not None
            and obs["value"] > item["declared_max"]
        ),
        "value_kind_distribution": dict(sorted(kinds.items())),
        "reported_by_distribution": dict(sorted(reported.items())),
        # The three invariants the rest of the system is allowed to rely on.
        "comparable_group_null_fraction": (
            sum(1 for obs in observations if obs["comparable_group"] is None) / len(observations)
            if observations
            else 1.0
        ),
        "display_scale_null_fraction": (
            sum(1 for item in series if item["display_scale"] is None) / len(series)
            if series
            else 1.0
        ),
        "empty_provenance_fraction": (
            sum(
                1
                for item in records
                if item["publisher"] is None and not item["artifacts"] and not item["sizes"]
            )
            / len(records)
            if records
            else 1.0
        ),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_catalog(
    normalized: dict[str, Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    """Write the normalized catalog to disk, deterministically.

    Keys are sorted and no build timestamp is embedded, so rerunning against
    unchanged inputs produces byte-identical files and a rebuild shows an empty
    diff rather than a whole-file churn.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    # Filenames carry the source, so a second snapshot writes beside the first
    # rather than over it.
    source = normalized["validation"]["source"]
    paths = {
        "source_records": output_dir / f"{source}_source_records.jsonl",
        "score_series": output_dir / f"{source}_score_series.jsonl",
        "score_observations": output_dir / f"{source}_score_observations.jsonl",
        "validation": output_dir / f"{source}_normalization_validation.json",
    }
    _write_jsonl(paths["source_records"], normalized["source_records"])
    _write_jsonl(paths["score_series"], normalized["score_series"])
    _write_jsonl(paths["score_observations"], normalized["score_observations"])
    paths["validation"].write_text(
        json.dumps(normalized["validation"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return paths


def build_benchmark_index(
    records: list[dict[str, Any]],
    series_by_key: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The small search payload: one entry per source record, never per merge.

    Merging two sources into one row is a claim that they describe the same
    benchmark, and that claim lives in `identity.yml` under human review. Doing
    it here would bake a wrong join into the artifact the reader searches, where
    it is invisible. One row per record keeps a bad grouping a display bug.
    """
    series_by_key = series_by_key or {}
    index: list[dict[str, Any]] = []
    for record in records:
        openness = record.get("openness") or {}
        artifacts = record.get("artifacts") or []
        series = series_by_key.get(record["key"]) or {}
        dated_reports = [
            report
            for report in (
                series.get("first_score_report"),
                record.get("first_score_source_reference"),
            )
            if report and report.get("reported_at")
        ]
        first_report = min(dated_reports, key=lambda report: report["reported_at"], default=None)
        publisher = record.get("publisher")
        repository = record.get("repository") or {}
        index.append(
            {
                "slug": record["slug"],
                "key": record["key"],
                "name": record["name"],
                "aliases": list(record.get("aliases") or []),
                # Search text stays source-derived. The normalizers carry
                # descriptions by language; no generated prose or inferred
                # category is introduced in this compact index.
                "description": " ".join(
                    str(value).strip()
                    for value in (
                        record.get("description", {}).values()
                        if isinstance(record.get("description"), dict)
                        else [record.get("description")]
                    )
                    if str(value or "").strip()
                ),
                "categories": list(record.get("categories") or []),
                "languages": list(record.get("languages") or []),
                "source": record["source"],
                "publisher": publisher["name"] if publisher else None,
                "released": record.get("released"),
                "released_reference": record.get("released_reference"),
                # Collection is provenance, never benchmark introduction.
                # Keep actual publication evidence separate from model-date
                # proxies so every consumer can explain its fallback.
                "collected_at": (record.get("provenance") or {}).get("crawled_at"),
                "first_score_reported_at": (first_report or {}).get("reported_at"),
                "first_score_source_reference": first_report,
                "first_score_record": series.get("first_score_record"),
                "source_url": (record.get("provenance") or {}).get("source_url"),
                "openness": openness.get("status", "unknown"),
                "modality": record.get("modality"),
                "score_count": series.get("observation_count", 0),
                "score_summary": series.get("score_summary"),
                "score_direction": series.get("direction"),
                "unit": series.get("unit"),
                "evidence_summary": record.get("evidence_summary"),
                "has_paper": any(item["kind"] == "paper" for item in artifacts),
                "has_repo": any(item["kind"] == "repo" for item in artifacts),
                "repo_kind": repository.get("kind"),
                "repo_resolution_status": repository.get("resolution_status"),
                "has_dataset": any(item["kind"] == "dataset" for item in artifacts),
                "has_size": bool(record.get("sizes")),
            }
        )
    index.sort(key=lambda item: (item["name"].lower(), item["key"]))
    return index


def write_benchmark_index(
    index: list[dict[str, Any]], output: Path, *, documents: dict[str, Any] | None = None
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": CATALOG_SCHEMA_VERSION,
                "count": len(index),
                "benchmarks": index,
                **({"document_registry": documents} if documents is not None else {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
