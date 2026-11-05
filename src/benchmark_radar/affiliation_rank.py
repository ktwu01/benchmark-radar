"""Opt-in affiliation signal for benchmark ranking.

This is a SIGNAL, not a quality judgement.

Benchmark Radar provides data and makes no quality judgements (AGENTS.md):
readers decide how to rank or compare. This module therefore never replaces
``attention-ranking-v1`` in ``release_leaderboard.py``. It adds one optional,
fully disclosed column a reader can turn on:

* Institutions come from OpenAlex linked institutions for the benchmark's
  own introducing arXiv paper (``data/catalog/benchmark_institutions.yml``,
  see ``catalog_institutions.py``). A paper that only evaluates or
  aggregates benchmarks contributes no institutions here.
* The institution weight is the catalog's own frequency: how many scored
  benchmarks in the current catalog list that institution, log1p-normalized
  against the most frequent institution. Frequency is a description of
  the catalog, not a claim that an institution is better.
* Missing is unknown, exactly as in ``release_leaderboard.py``: no
  zero-imputation, no midpoint, and weights are never redistributed to
  the signals that happen to be present. A benchmark with no institutions
  on file gets ``affiliation_normalized = None``.
* A benchmark is ``limited_signals`` unless its observed fresh weight is
  at least ``MIN_OBSERVED_WEIGHT_RANK`` (0.45, mirroring
  ``release_leaderboard.py``) and it has a durable attention signal
  (GitHub stars or HF dataset downloads). Affiliation alone never
  qualifies a benchmark as ranked.

Related to #904 (joined benchmarks need a shared view before any
cross-source average is meaningful), #550 (an index to compare with
Artificial Analysis, built here as a disclosed signal rather than a
quality index), and #660 (a recommendation signal, opt-in only).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from .catalog_institutions import DEFAULT_INSTITUTIONS_PATH
from .release_leaderboard import MIN_OBSERVED_WEIGHT_RANK, WINDOW_WEIGHTS

METHOD_VERSION = "affiliation-signal-v1"
AFFILIATION_WEIGHT = 0.20
AFFILIATION_SIGNAL = "affiliation_frequency"

# Fixed denominator: attention weights sum to 1.0, plus the affiliation
# weight. Dividing by this constant (never by the observed weight) is what
# keeps missing signals from being redistributed.
TOTAL_WEIGHT = sum(WINDOW_WEIGHTS.values()) + AFFILIATION_WEIGHT


def normalize_log1p(value: int | float | None, window_max: int | float | None) -> float | None:
    """Log-max normalization, mirroring ``release_leaderboard.normalize_log1p``."""
    if value is None:
        return None
    val_float = max(0.0, float(value))
    if window_max is None or window_max <= 0:
        return 0.0
    max_float = max(0.0, float(window_max))
    if max_float == 0.0:
        return 0.0
    return min(1.0, math.log1p(val_float) / math.log1p(max_float))


def load_institutions_map(
    path: Path | None = None,
) -> dict[str, list[str]]:
    """Return ``{benchmark key: [institution, ...]}`` from the yml file.

    Tolerant on purpose: unlike the strict validator in
    ``catalog_institutions.load_benchmark_institutions``, a missing or
    unreadable file means "no affiliation signal", not a build failure.
    Malformed entries are skipped rather than aborting the ranking.
    """
    resolved = path or DEFAULT_INSTITUTIONS_PATH
    try:
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, fact in benchmarks.items():
        if isinstance(fact, dict):
            institutions = fact.get("institutions")
        elif isinstance(fact, list):
            institutions = fact
        else:
            continue
        if isinstance(institutions, list) and institutions:
            names = [str(name) for name in institutions if str(name).strip()]
            if names:
                result[str(key)] = names
    return result


def _record_institutions(
    record: dict[str, Any], institutions_map: dict[str, list[str]] | None
) -> list[str]:
    """Institutions for one record, preferring the record itself."""
    direct = record.get("institutions")
    if isinstance(direct, list) and direct:
        return [str(name) for name in direct if str(name).strip()]
    if institutions_map:
        mapped = institutions_map.get(str(record.get("key", "")))
        if mapped:
            return list(mapped)
    return []


def _record_is_scored(record: dict[str, Any]) -> bool:
    """Whether a record counts as scored for the frequency denominator.

    Accepts the shapes callers actually pass: an explicit ``has_score``
    flag, a numeric ``score`` / ``reported_score``, or a non-empty
    ``scores`` list. Records with no score field at all are not counted,
    so an unscored record never inflates an institution's frequency.
    """
    if "has_score" in record:
        return bool(record["has_score"])
    for field in ("score", "reported_score", "display_max"):
        value = record.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    scores = record.get("scores")
    if isinstance(scores, list):
        return len(scores) > 0
    if isinstance(scores, dict):
        return len(scores) > 0
    return False


def count_scored_benchmarks_per_institution(
    records: list[dict[str, Any]],
    institutions_map: dict[str, list[str]] | None = None,
) -> dict[str, int]:
    """Count scored benchmarks per institution across the catalog."""
    counts: dict[str, int] = {}
    for record in records:
        if not _record_is_scored(record):
            continue
        for name in _record_institutions(record, institutions_map):
            counts[name] = counts.get(name, 0) + 1
    return counts


def institution_weights(counts: dict[str, int]) -> dict[str, float]:
    """Log1p-normalize raw frequency counts against the max count."""
    if not counts:
        return {}
    window_max = max(counts.values())
    return {name: normalize_log1p(count, window_max) or 0.0 for name, count in counts.items()}


def affiliation_normalized(institutions: list[str], weights: dict[str, float]) -> float | None:
    """Mean institution weight for a benchmark, or None if unknown.

    The mean (not the sum) keeps a benchmark with many listed
    institutions from outscoring a single-institution benchmark purely
    by listing more names. Institutions absent from ``weights`` are
    unknown and skipped; if every institution is unknown, the result
    is None, not zero.
    """
    if not institutions:
        return None
    known = [weights[name] for name in institutions if name in weights]
    if not known:
        return None
    return min(1.0, sum(known) / len(known))


def combine_with_attention(
    attention_components: dict[str, dict[str, Any]] | None,
    affiliation_norm: float | None,
    *,
    has_durable_attention: bool | None = None,
) -> dict[str, Any]:
    """Combine attention-ranking-v1 components with the affiliation signal.

    ``attention_components`` uses the ``release_leaderboard`` shape:
    ``{signal: {"normalized": float | None, "status": str, ...}}``.
    Only ``status == "fresh"`` attention contributes to the score;
    stale or unknown attention contributes nothing and is not
    redistributed. Affiliation contributes only when it is known
    (not None).

    Returns a dict with the combined score (0-100, or None when
    nothing fresh was observed), the fixed-denominator observed weight,
    and ``ranked`` / ``limited_signals`` status mirroring
    ``release_leaderboard.compute_window_ranking``.
    """
    components = attention_components or {}
    attention_raw = 0.0
    observed_weight = 0.0
    durable = False
    for signal, weight in WINDOW_WEIGHTS.items():
        entry = components.get(signal) or {}
        norm = entry.get("normalized")
        status = entry.get("status", "unknown")
        if norm is not None and status == "fresh":
            attention_raw += weight * norm
            observed_weight += weight
            if signal in {"github_stars", "hf_dataset_downloads"}:
                durable = True
    if has_durable_attention is not None:
        durable = has_durable_attention

    affiliation_entry: dict[str, Any] = {
        "value": affiliation_norm,
        "normalized": affiliation_norm,
        "weight": AFFILIATION_WEIGHT,
        "status": "fresh" if affiliation_norm is not None else "unknown",
    }
    combined_raw = attention_raw
    if affiliation_norm is not None:
        combined_raw += AFFILIATION_WEIGHT * affiliation_norm
        observed_weight += AFFILIATION_WEIGHT

    raw_score = 100.0 * combined_raw / TOTAL_WEIGHT if combined_raw > 0 else None
    score = round(raw_score + 1e-9) if raw_score is not None else None
    sufficient = observed_weight >= MIN_OBSERVED_WEIGHT_RANK - 1e-9
    status = "ranked" if (sufficient and durable and score is not None) else "limited_signals"
    return {
        "method_version": METHOD_VERSION,
        "score": score,
        "observed_weight": round(observed_weight, 4),
        "status": status,
        "affiliation": affiliation_entry,
        "disclosure": (
            "Opt-in signal only: institution frequency in this catalog, "
            "not a quality judgement. See affiliation_rank.py docstring."
        ),
    }


def build_affiliation_signal(
    records: list[dict[str, Any]],
    institutions_map: dict[str, list[str]] | None = None,
    *,
    institutions_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the per-benchmark affiliation signal for a catalog.

    Returns ``{benchmark key: {"institutions": [...], "affiliation_normalized": ...}}``.
    Unscored records are included with their institutions listed but do
    not contribute to the frequency counts.
    """
    mapping = institutions_map
    if mapping is None:
        mapping = load_institutions_map(institutions_path)
    counts = count_scored_benchmarks_per_institution(records, mapping)
    weights = institution_weights(counts)
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("key", ""))
        if not key:
            continue
        institutions = _record_institutions(record, mapping)
        result[key] = {
            "institutions": institutions,
            "affiliation_normalized": affiliation_normalized(institutions, weights),
            "institution_weights": {
                name: weights[name] for name in institutions if name in weights
            },
        }
    return result
