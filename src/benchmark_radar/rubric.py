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

SCORING_VERSION = 3
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

# Evidence is explicit and additive on a 0-100 scale.
EVIDENCE_BASE = 10.0
EVIDENCE_PRIMARY_SOURCES = (
    "arXiv",
    "First-party feed",
    "OpenAlex",
    "OpenReview",
    "Semantic Scholar",
)
EVIDENCE_PRIMARY_CREDIT = 40.0
EVIDENCE_ARTIFACT_SOURCES = ("GitHub", "GitHub Release", "Hugging Face")
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
)
MAX_LOW_VALUE_DEDUCTION = 60.0

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
                f"{SCORE_MAX:.0f} at publication or update time",
                f"Decays linearly across the configured {lookback_hours:g}-hour lookback",
                f"Reaches 0 at {lookback_hours:g} hours",
            ],
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
            + ["Uses the strongest available normalized counter", "Clamped to 0-100"],
        },
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
            "Adoption measures attention, not correctness.",
            "Attention observations are shown separately and are never quality-scored.",
            "Watchlisted artifacts are retained whatever they score and sort first. Their "
            "rank reflects that request, not a higher score.",
        ],
        "lookback_hours": float(lookback_hours),
    }
    return value


def v2_rubric_reference(
    *, lookback_hours: float = DEFAULT_LOOKBACK_HOURS
) -> dict[str, Any]:
    """Describe v2 without retroactively granting its records the v3 feed tier."""
    value = rubric_reference(lookback_hours=lookback_hours)
    value["scoring_version"] = 2
    for component in value["components"]:
        if component["key"] != "evidence":
            continue
        component["bands"] = [
            band.replace(", First-party feed", "") for band in component["bands"]
        ]
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
