"""Versioned, published definitions for Benchmark Radar priority scores.

The pipeline and dashboard both consume this module.  A score is useful only
when the arithmetic shown to a reader is the arithmetic that produced it, so
historical scoring versions remain available instead of being relabelled when
the current rubric changes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCORING_VERSION = 5
SCORE_MAX = 100.0
DEFAULT_LOOKBACK_HOURS = 48.0

# The v1 rubric placed 60% of the total on evidence and recency, which barely
# varied inside the 48-hour collection window.  Adoption now has enough weight
# to distinguish established artifacts while relevance remains the largest
# input.
WEIGHTS: dict[str, float] = {
    "relevance": 0.35,
    "evidence": 0.20,
    "recency": 0.20,
    "adoption": 0.25,
}

# A repository touch or paper replacement is current activity, but it is not
# the same event as a first announcement. Prereleases retain more credit than
# ordinary updates because they still introduce a new, if provisional, release.
# Unknown event kinds keep full credit so a new connector is not silently
# penalized before its semantics have been reviewed.
RECENCY_EVENT_FACTORS: dict[str, float] = {
    "released": 1.0,
    "discovered": 1.0,
    "prereleased": 0.75,
    "updated": 0.50,
}

# Evidence is explicit and additive on a 0-100 scale.
EVIDENCE_BASE = 10.0
EVIDENCE_PRIMARY_SOURCES = (
    "arXiv",
    "First-party feed",
    "OpenAlex",
    "OpenReview",
    "Semantic Scholar",
    "Crossref",
)
EVIDENCE_PRIMARY_CREDIT = 40.0
EVIDENCE_ARTIFACT_SOURCES = (
    "GitHub",
    "GitHub Release",
    "GitHub Organization",
    "Hugging Face",
    "Kaggle Dataset",
    "Zenodo",
)
EVIDENCE_ARTIFACT_CREDIT = 30.0
EVIDENCE_AUTHORSHIP_CREDIT = 20.0
EVIDENCE_CROSS_LINK_CREDIT = 20.0

# Relevance credit for taxonomy matches.  A single incidental term cannot
# produce a high score; multiple independent category matches can.
RELEVANCE_PER_CATEGORY = 20.0
RELEVANCE_PER_TERM = 5.0
RELEVANCE_TERMS_COUNTED_PER_CATEGORY = 2

# Deterministic negative signals address artifacts that are technically
# on-topic but do not represent a benchmark/data release worth occupying the
# daily radar.  Patterns require specific phrases rather than generic words so
# a legitimate leaderboard or anonymous conference paper is not penalized.
LOW_VALUE_SIGNALS: tuple[dict[str, Any], ...] = (
    {
        "label": "follower-count leaderboard",
        "pattern": (
            r"\bfollowers?[\s_-]*(?:count[\s_-]*)?leaderboard\b"
            r"|\bfollower leaderboard(?:'s)? history\b"
        ),
        "deduction": 50.0,
        "action": "demote",
    },
    {
        "label": "results dump or per-run index",
        "pattern": (
            r"\bresults?[\s_-]*(?:dump|index)\b"
            r"|\bper[\s_-]*run[\s_-]*results?\b"
        ),
        "deduction": 30.0,
        "action": "suppress",
    },
    {
        "label": "submission placeholder",
        "pattern": (
            r"\b(?:anonymous|anonymized)[\s_-]*(?:review[\s_-]*)?submission\b"
            r"|\breview[\s_-]*process[\s_-]*(?:stub|placeholder)\b"
            r"|\bsubmission[\s_-]*(?:stub|placeholder)\b"
        ),
        "deduction": 30.0,
        "action": "suppress",
    },
    {
        "label": "visualization-only companion",
        "pattern": (
            r"\bvisuali[sz]ation companion\b"
            r"|\bcompact browser assets\b"
            r"|\bleaderboard case assets\b"
        ),
        "deduction": 25.0,
        "action": "suppress",
    },
    {
        "label": "sponsor-bait resource listing",
        "pattern": (
            r"\bsponsor\b.{0,40}\bobtain\b.{0,20}\b(?:full|complete)\b.{0,20}\b(?:data|dataset)\b"
        ),
        "deduction": 30.0,
        "action": "suppress",
    },
)
MAX_LOW_VALUE_DEDUCTION = 60.0

# Field-only provenance checks stay separate from LOW_VALUE_SIGNALS, which are
# regular expressions over title + summary. These rules deliberately make no
# semantic claim about whether an artifact is a good or novel benchmark. They
# only detect records that cannot lead a reader to their source or that arrived
# with no supporting metadata beyond a title and URL.
STRUCTURAL_SIGNALS: tuple[dict[str, Any], ...] = (
    {
        "label": "missing primary source URL",
        "fields": ("url",),
        "condition": "all_missing",
        "description": "no primary source URL",
        "deduction": 30.0,
        "action": "suppress",
    },
    {
        "label": "title-only provenance",
        "fields": ("summary", "authors", "organizations", "artifact_urls", "metrics"),
        "condition": "all_missing",
        "description": ("no source description, attribution, artifact link, or public counter"),
        "deduction": 15.0,
        "action": "demote",
    },
)

V5_LIMITS = (
    "Update-driven recency is discounted from first announcements using the source's "
    "event kind. This cannot distinguish a material GitHub release from a packaging bump.",
    "Structural checks use only missing or populated record fields as a provenance signal. "
    "They do not judge benchmark quality, novelty, or validity.",
)

# Adoption reaches the top of its scale at a documented, source-appropriate
# public counter.  The strongest available counter is used because adding
# incomparable counters (stars + downloads + citations) rewards sources merely
# for exposing more metric types.
ADOPTION_METRIC_SATURATION: dict[str, float] = {
    "stars": 10_000.0,
    "citations": 1_000.0,
    "downloads": 100_000.0,
    "likes": 1_000.0,
}

# Downloads and likes are not comparable achievements to a star or a citation.
# A dataset accrues downloads from any script that pulls it once, and a like
# costs less than a star does; both counters accumulate without anyone deciding
# the artifact was worth keeping. Under the max-wins rule of v3 that asymmetry
# was structural rather than incidental: GitHub records never carry downloads
# and Hugging Face records never carry stars, so whichever counter saturates
# most easily decided the ranking for the source that exposes it. On
# 2026-08-19 a dataset with 25,238 downloads and 1 like scored adoption 88.0
# and took the #2 slot from a 3,265-star repository at 87.8 (issue #278).
#
# Capping rather than removing: dropping downloads entirely would collapse
# every Hugging Face dataset to adoption 0 and simply flip the bias toward
# GitHub. A cap lets automated traffic place an artifact mid-pack while
# reserving the top of the scale for counters that record a human decision.
# 60 is the score of roughly 250 stars, so a capped download total still
# outranks a barely-noticed repository and never outranks a widely-held one.
# Stars and citations remain unbounded within the 0-100 scale.
ADOPTION_CAPPED_METRICS: dict[str, float] = {
    "downloads": 60.0,
    "likes": 60.0,
}

# `ktwu01/benchmark-radar` is this project. Its description is wall-to-wall
# benchmark vocabulary and it is committed to daily, so it scored relevance 100
# and recency ~96 and reached the top 5 on 9 of the first 27 collected days
# (issue #278). Whatever the arithmetic says, a radar that recommends itself is
# not reporting on the field, and #32 already established that self-referential
# artifacts do not belong in the daily list.
#
# Matched on the exact repository identity, never as a substring: an unrelated
# `H20Zhang/Agent-Benchmark-Radar` appears in the corpus and is a legitimate
# record. Both the canonical GitHub id and the URL host/path are checked
# because a record can reach the pipeline from either shape.
SELF_REPOSITORY = "ktwu01/benchmark-radar"
SELF_REFERENCE_LABEL = "this project's own repository"


def taxonomy_version(taxonomy: dict[str, Any]) -> str:
    """A stable fingerprint of the taxonomy that classified a record.

    Issue #72 asked for trend values to be bound to the taxonomy that produced
    them, after PR #67 moved the cumulative `agentic` count from 3 to 78. That
    was a rules change, not 75 new agent benchmarks, and nothing in a snapshot
    recorded which rules had run: two days classified under different taxonomies
    were indistinguishable, so a measurement fix read as a domain explosion.

    Derived from the taxonomy's own content rather than hand-bumped. A version
    a maintainer has to remember to increment is a version that silently stops
    being true the first time someone edits a keyword list and forgets, which
    is exactly the failure this is meant to detect. Editing any term changes
    the digest; nothing else can.

    The digest covers the category names, their terms, and the structure of a
    proximity rule, canonicalized so that reordering *categories* in
    `config.yml` without changing what matches does not invent a new version
    and force a false "not comparable" on every trend.

    Term order inside a category is deliberately significant, unlike category
    order. `rescore` records only the first two matching terms in a record's
    "Matched:" rationale, so listing the same terms in a different order
    produces different stored evidence for the same artifact. That is a real
    change in output, and a version that called those two runs identical would
    be claiming something false.
    """
    canonical = json.dumps(taxonomy, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    # Truncated: this is an equality check between snapshots, not a security
    # boundary, and a full 64-character digest in every record and on the
    # dashboard is noise a reader has to scroll past.
    return f"sha256:{digest[:12]}"


def _components(*, lookback_hours: float) -> list[dict[str, Any]]:
    return [
        {
            "key": "relevance",
            "label": "Relevance",
            "weight": WEIGHTS["relevance"],
            "summary": (
                "How squarely the title and the source's own description land inside the "
                "benchmark, evaluation, dataset, and data-quality taxonomy, after explicit "
                "low-value deductions."
            ),
            "bands": [
                f"{RELEVANCE_PER_CATEGORY:.0f} per taxonomy category matched",
                f"+{RELEVANCE_PER_TERM:.0f} per matched term, counting up to "
                f"{RELEVANCE_TERMS_COUNTED_PER_CATEGORY} terms per category",
                *[
                    f"-{signal['deduction']:.0f} for {signal['label']}"
                    + ("; suppressed" if signal["action"] == "suppress" else "")
                    for signal in LOW_VALUE_SIGNALS
                ],
                *_structural_bands(),
                f"Total deductions capped at {MAX_LOW_VALUE_DEDUCTION:.0f}",
                f"Clamped to 0-{SCORE_MAX:.0f}",
            ],
        },
        {
            "key": "evidence",
            "label": "Evidence",
            "weight": WEIGHTS["evidence"],
            "summary": (
                "How directly the record is attested: a primary or structured record "
                "outranks a secondary mention, and named authors and linked artifacts "
                "add corroboration."
            ),
            "bands": [
                f"{EVIDENCE_BASE:.0f} baseline for any record that passed ingest",
                f"+{EVIDENCE_PRIMARY_CREDIT:.0f} from a primary or structured record "
                f"({', '.join(EVIDENCE_PRIMARY_SOURCES)})",
                f"+{EVIDENCE_ARTIFACT_CREDIT:.0f} from a structured artifact registry "
                f"({', '.join(EVIDENCE_ARTIFACT_SOURCES)})",
                f"+{EVIDENCE_AUTHORSHIP_CREDIT:.0f} when the source names authors",
                f"+{EVIDENCE_CROSS_LINK_CREDIT:.0f} when another artifact URL corroborates it",
                f"Capped at {SCORE_MAX:.0f}",
            ],
        },
        {
            "key": "recency",
            "label": "Recency",
            "weight": WEIGHTS["recency"],
            "summary": (
                "How recently the artifact was published or materially updated within "
                "this scan's configured collection window."
            ),
            "bands": [
                f"{SCORE_MAX:.0f} at release or first-discovery time",
                f"Age-based credit decays linearly across the configured "
                f"{lookback_hours:g}-hour lookback",
                f"Age-based credit reaches 0 at {lookback_hours:g} hours",
            ]
            + _recency_event_bands(),
        },
        {
            "key": "adoption",
            "label": "Adoption",
            "weight": WEIGHTS["adoption"],
            "summary": (
                "The strongest available public uptake counter on a log scale. "
                "This measures attention, not scientific quality."
            ),
            "bands": [
                f"{metric} reaches 100 at {saturation:g}"
                for metric, saturation in ADOPTION_METRIC_SATURATION.items()
            ]
            + [
                f"{metric} is capped at {cap:.0f}, the score of roughly 250 stars, "
                "because the counter accumulates without a human decision"
                for metric, cap in ADOPTION_CAPPED_METRICS.items()
            ]
            + ["Uses the strongest available normalized counter", "Clamped to 0-100"],
        },
    ]


def _structural_bands() -> list[str]:
    return [
        f"-{signal['deduction']:.0f} for {signal['label']}: {signal['description']}"
        + ("; suppressed" if signal["action"] == "suppress" else "")
        for signal in STRUCTURAL_SIGNALS
    ]


def _recency_event_bands() -> list[str]:
    return [
        f"{event} events retain {factor * 100:g}% of their age-based recency"
        for event, factor in RECENCY_EVENT_FACTORS.items()
    ]


def _v4_recency_bands(*, lookback_hours: float) -> list[str]:
    return [
        f"{SCORE_MAX:.0f} at publication or update time",
        f"Decays linearly across the configured {lookback_hours:g}-hour lookback",
        f"Reaches 0 at {lookback_hours:g} hours",
    ]


def priority_formula() -> str:
    """Render the weighted sum the way the README and dashboard state it."""
    return " + ".join(f"{weight:.2f} {component}" for component, weight in WEIGHTS.items())


def rubric_reference(
    *,
    lookback_hours: float = DEFAULT_LOOKBACK_HOURS,
) -> dict[str, Any]:
    """Return the current rubric as a browser-safe published reference."""
    value: dict[str, Any] = {
        "scoring_version": SCORING_VERSION,
        "score_max": SCORE_MAX,
        "formula": priority_formula(),
        "components": _components(lookback_hours=lookback_hours),
        "limits": [
            "This is triage for a reader deciding what to open next. It is not peer "
            "review, a quality verdict, or an endorsement.",
            "Relevance reads only the title and source-published description. Nothing "
            "this project writes about a record can earn it points.",
            "Negative signals demote only named artifact patterns. Result indexes, "
            "submission placeholders, and visualization-only companions are suppressed; "
            "the selection funnel reports how many were removed.",
            "Adoption measures attention, not correctness. Counters that accumulate "
            "without a human decision (downloads, likes) are capped below the top of "
            "the adoption scale; stars and citations are not.",
            f"This project's own repository ({SELF_REPOSITORY}) is excluded from its own ranking.",
            "Attention observations are shown separately and are never quality-scored.",
            "Watchlisted artifacts are retained whatever they score and sort first. Their "
            "rank reflects that request, not a higher score.",
            *V5_LIMITS,
        ],
        "lookback_hours": float(lookback_hours),
    }
    return value


def v4_rubric_reference(*, lookback_hours: float = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any]:
    """Describe v4 without retroactively applying v5's event and structure rules."""
    value = rubric_reference(lookback_hours=lookback_hours)
    value["scoring_version"] = 4
    for component in value["components"]:
        if component["key"] == "relevance":
            component["bands"] = [
                band for band in component["bands"] if band not in _structural_bands()
            ]
        elif component["key"] == "recency":
            component["bands"] = _v4_recency_bands(lookback_hours=lookback_hours)
    value["limits"] = [limit for limit in value["limits"] if limit not in V5_LIMITS]
    return value


def v3_rubric_reference(*, lookback_hours: float = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any]:
    """Describe v3 without retroactively applying v4's download cap.

    A v3 score was produced by the uncapped max-wins adoption rule, and the
    records that ranked under it included this repository. Explaining those
    numbers with v4's bands would claim the run did something it did not, which
    is the relabelling #32 forbids.
    """
    value = v4_rubric_reference(lookback_hours=lookback_hours)
    value["scoring_version"] = 3
    for component in value["components"]:
        if component["key"] != "adoption":
            continue
        component["bands"] = [band for band in component["bands"] if "capped at" not in band]
    value["limits"] = [
        # v3 capped nothing, so its adoption limit is the bare sentence.
        "Adoption measures attention, not correctness."
        if limit.startswith("Adoption measures")
        else limit
        for limit in value["limits"]
        if not limit.startswith("This project's own repository")
    ]
    return value


def v2_rubric_reference(*, lookback_hours: float = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any]:
    """Describe v2 without retroactively granting its records the v3 feed tier."""
    value = v3_rubric_reference(lookback_hours=lookback_hours)
    value["scoring_version"] = 2
    for component in value["components"]:
        if component["key"] != "evidence":
            continue
        component["bands"] = [band.replace(", First-party feed", "") for band in component["bands"]]
    return value


def legacy_rubric_reference() -> dict[str, Any]:
    """Describe v1 records without pretending the current formula produced them."""
    return {
        "scoring_version": 1,
        "score_max": 4.0,
        "formula": "0.40 relevance + 0.25 evidence + 0.20 recency + 0.15 adoption",
        "components": [
            {
                "key": key,
                "label": key.title(),
                "weight": weight,
                "summary": "Legacy 0-4 component retained for historical audit.",
                "bands": ["Historical scoring version; superseded by rubric v2."],
            }
            for key, weight in {
                "relevance": 0.40,
                "evidence": 0.25,
                "recency": 0.20,
                "adoption": 0.15,
            }.items()
        ],
        "limits": [
            "This historical score used the original 0-4 rubric and is not directly "
            "comparable with current 0-100 scores."
        ],
    }
