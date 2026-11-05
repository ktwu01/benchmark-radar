"""Affiliation signal: unknown handling, log1p normalization, weight preservation.

Opt-in signal only, not a quality judgement. See
``benchmark_radar.affiliation_rank`` docstring.
"""

from __future__ import annotations

import math

from benchmark_radar.affiliation_rank import (
    AFFILIATION_WEIGHT,
    MIN_OBSERVED_WEIGHT_RANK,
    TOTAL_WEIGHT,
    affiliation_normalized,
    build_affiliation_signal,
    combine_with_attention,
    count_scored_benchmarks_per_institution,
    institution_weights,
    normalize_log1p,
)


def _fresh(norm):
    return {"value": 100, "normalized": norm, "status": "fresh"}


def _unknown():
    return {"value": None, "normalized": None, "status": "unknown"}


def test_unknown_institutions_stay_unknown_not_zero():
    # No institutions on file -> None, never 0.0, and the benchmark
    # stays limited_signals even with a fresh durable attention signal
    # if observed weight is below the threshold on its own.
    assert affiliation_normalized([], {}) is None
    assert affiliation_normalized(["No Such University"], {}) is None
    result = combine_with_attention(
        {"github_stars": _unknown(), "hf_paper_upvotes": _unknown()},
        None,
    )
    assert result["score"] is None
    assert result["status"] == "limited_signals"
    assert result["affiliation"]["status"] == "unknown"


def test_log1p_normalization_matches_formula_and_is_monotonic():
    assert normalize_log1p(None, 100) is None
    assert normalize_log1p(100, 100) == 1.0
    assert normalize_log1p(0, 100) == 0.0
    expected = math.log1p(10) / math.log1p(100)
    assert normalize_log1p(10, 100) == expected
    weights = institution_weights({"A": 1, "B": 10, "C": 100})
    assert weights["C"] == 1.0
    assert weights["A"] < weights["B"] < weights["C"]
    # Log compression: 10x the count is far less than 10x the weight.
    assert weights["B"] > 0.4 and weights["B"] < 0.8


def test_missing_signals_are_not_redistributed():
    # Stars-only, perfect, no affiliation: fixed denominator 1.20,
    # not renormalized to 100. 100 * 0.55 / 1.20 = 45.83 -> 46.
    result = combine_with_attention(
        {
            "github_stars": _fresh(1.0),
            "hf_paper_upvotes": _unknown(),
            "hf_dataset_downloads": _unknown(),
        },
        None,
    )
    assert result["score"] == 46
    assert result["observed_weight"] == 0.55
    assert result["status"] == "ranked"  # 0.55 >= 0.45 + durable stars

    # Same stars plus a perfect affiliation signal: 100 * (0.55 + 0.20) / 1.20 = 62.5 -> 63.
    # The affiliation adds, it does not rescale the stars weight.
    with_affil = combine_with_attention(
        {
            "github_stars": _fresh(1.0),
            "hf_paper_upvotes": _unknown(),
            "hf_dataset_downloads": _unknown(),
        },
        1.0,
    )
    assert with_affil["score"] == 63
    assert with_affil["observed_weight"] == 0.75


def test_observed_weight_below_threshold_stays_limited():
    # Upvotes only (0.30) + affiliation (0.20) = 0.50 would pass, so
    # use upvotes alone: 0.30 < 0.45, and no durable signal either.
    result = combine_with_attention(
        {
            "github_stars": _unknown(),
            "hf_paper_upvotes": _fresh(1.0),
            "hf_dataset_downloads": _unknown(),
        },
        None,
    )
    assert result["status"] == "limited_signals"
    assert result["observed_weight"] == 0.30
    assert MIN_OBSERVED_WEIGHT_RANK == 0.45
    assert TOTAL_WEIGHT == 1.20
    assert AFFILIATION_WEIGHT == 0.20


def test_frequency_counts_only_scored_benchmarks_and_means_institutions():
    records = [
        {"key": "a", "has_score": True, "institutions": ["Tsinghua University", "MIT"]},
        {"key": "b", "has_score": True, "institutions": ["Tsinghua University"]},
        {"key": "c", "has_score": False, "institutions": ["Tsinghua University"]},
        {"key": "d", "institutions": ["MIT"]},  # no score field -> not scored
    ]
    counts = count_scored_benchmarks_per_institution(records)
    assert counts == {"Tsinghua University": 2, "MIT": 1}
    weights = institution_weights(counts)
    signal = build_affiliation_signal(records)
    # Mean of [1.0, log1p(1)/log1p(2)] for record a.
    assert signal["a"]["affiliation_normalized"] == (1.0 + weights["MIT"]) / 2
    assert signal["b"]["affiliation_normalized"] == 1.0
    # Unscored record c still lists institutions but did not inflate counts.
    assert signal["c"]["institutions"] == ["Tsinghua University"]
