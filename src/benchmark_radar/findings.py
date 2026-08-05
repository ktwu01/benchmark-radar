"""Deterministic day-over-day findings for the daily briefing.

Issue #127. The briefing previously asked a model to find "the strongest
grounded insight" in a payload of aggregate counts and twelve unranked titles.
It produced counter recitation, because counts were nearly all it received:

    Today: 259 evidence items and 21 attention items, including 158 new items.
    Compared with Aug 4, evidence rose by 47 ... while arXiv fell by 5.

Every number there is already rendered beside the panel, and "arXiv fell by 5"
is not a claim about the world at all: two connectors were failing, so the
system reported its own plumbing as if it were the field.

This module computes findings instead of asking for them. Candidates are
discovered and verified in code, each carrying the evidence a reader needs to
check it, and the model is left with at most a copy-editing role. Three
properties make that worth doing:

Shares, not counts. Raw volume in this project is dominated by connector
onboarding: the corpus went from 20 items a day to 259 while healthy sources
went from 3 to 6. A count-based detector would report a twelvefold rise in
"the field" that is entirely crawler growth. Composition survives that.

Persistence over significance. A robust z-score against the trailing window
scores the real agentic shift at 1.54, below any usable threshold, because the
trailing window contains the shift. Requiring a fully separated recent window
catches what a point test misses, and rejects one-day spikes a point test would
happily report.

Breadth. A composition change carried by one connector is that connector's
artifact. Requiring several independent sources is what makes the claim about
the feed rather than about a fetcher.

Scope discipline: every claim describes the captured feed, never the field. The
crawler is not a population sample, and a briefing that says "AI evaluation is
shifting" is overclaiming on a keyword-filtered scrape of five sources.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

# A finding needs enough of the day to be about the day rather than about noise.
MINIMUM_DAY_ITEMS = 25
# Windows are deliberately short: this project holds two weeks of history, so
# the 28-to-56-day weekday-conditioned baselines that a mature feed would use
# are not available. Five and four are the smallest windows where a fully
# separated split is not routine chance, and both are checked below.
RECENT_DAYS = 5
MINIMUM_BASELINE_DAYS = 4
# Percentage points. Below this a composition change is not worth a reader's
# attention even when it is real and separated.
MINIMUM_SHIFT_POINTS = 5.0
# A change carried by fewer independent sources than this is a connector
# artifact, not a property of the feed.
MINIMUM_SOURCE_BREADTH = 3
# Categories are multi-label, so several move together and testing all of them
# invites reporting whichever crossed the line. Only the largest separated
# shift is published, which is the same discipline as reporting the gated cell
# rather than the average.
MAX_FINDINGS = 1


class Coverage:
    """Connector health for one day, used to gate and caption every claim.

    Gating is on required sources only. Optional connectors fail for reasons
    that have nothing to do with the day's composition and stay failed for
    long stretches: `brave` has no configured API key and `openreview` has
    returned 403 for nine consecutive runs. Gating on every connector would
    mean never publishing a finding, so the gate asks whether the sources the
    corpus is actually built from reported, while the caption still discloses
    the optional ones so a reader knows the feed was partial.
    """

    def __init__(
        self,
        healthy: int,
        total: int,
        failed_required: list[str],
        failed_optional: list[str],
    ) -> None:
        self.healthy = healthy
        self.total = total
        self.failed_required = failed_required
        self.failed_optional = failed_optional

    @property
    def complete(self) -> bool:
        """Whether a composition claim can be separated from missing sources."""
        return not self.failed_required

    def caption(self) -> str:
        parts = [f"Coverage: {self.healthy}/{self.total} connectors healthy"]
        if self.failed_required:
            parts.append(f"required source(s) {', '.join(self.failed_required)} unavailable")
        if self.failed_optional:
            parts.append(f"{', '.join(self.failed_optional)} unavailable")
        return "; ".join(parts) + "."


def coverage_for(snapshot: dict[str, Any], config: dict[str, Any] | None = None) -> Coverage:
    sources = (config or {}).get("sources") or {}
    health = [
        entry for entry in snapshot.get("ingest_health") or [] if entry.get("kind") != "attention"
    ]
    failed_required, failed_optional = [], []
    for entry in health:
        if entry.get("ok"):
            continue
        source = str(entry.get("source"))
        target = failed_required if (sources.get(source) or {}).get("required") else failed_optional
        target.append(source)
    return Coverage(
        healthy=sum(1 for entry in health if entry.get("ok")),
        total=len(health),
        failed_required=sorted(failed_required),
        failed_optional=sorted(failed_optional),
    )


def _category_shares(snapshot: dict[str, Any]) -> dict[str, float]:
    """Return each category's share of the day, as a percentage of items.

    Shares rather than counts because item volume tracks connector onboarding.
    A category can hold a steady share of a tripling corpus, which is not a
    change in what the feed is finding.
    """
    items = snapshot.get("evidence_items") or []
    if not items:
        return {}
    counts: Counter[str] = Counter()
    for item in items:
        # Multi-label: one artifact can be a benchmark and a dataset and
        # agentic, so shares across categories do not sum to 100.
        for category in item.get("categories") or []:
            counts[str(category)] += 1
    return {category: 100.0 * count / len(items) for category, count in counts.items()}


def _source_breadth(snapshot: dict[str, Any], category: str) -> tuple[int, int]:
    """Return how many sources carry this category, and how many are present."""
    carrying = {
        str(item.get("source"))
        for item in snapshot.get("evidence_items") or []
        if category in (item.get("categories") or [])
    }
    present = {str(item.get("source")) for item in snapshot.get("evidence_items") or []}
    return len(carrying), len(present)


def _category_counts(snapshot: dict[str, Any], category: str) -> tuple[int, int]:
    """Return the category's item count and the day's total, for citation."""
    items = snapshot.get("evidence_items") or []
    matching = sum(1 for item in items if category in (item.get("categories") or []))
    return matching, len(items)


def composition_shift(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the largest verified composition shift, or None.

    `history` is chronological and ends with the day being reported. A shift is
    published only when the recent window is fully separated from the earlier
    one: every recent day above every baseline day, or every recent day below.
    Full separation is a deliberately blunt instrument, and it is doing the work
    a significance test cannot here. The trailing window contains the shift
    being detected, so a robust z-score against it scores the real 12.3% to
    25.9% agentic move at 1.54 and rejects it. Separation instead asks whether
    the two windows describe the same regime, which is the actual question.
    """
    if len(history) < RECENT_DAYS + MINIMUM_BASELINE_DAYS:
        return None
    today = history[-1]
    if len(today.get("evidence_items") or []) < MINIMUM_DAY_ITEMS:
        return None

    recent = history[-RECENT_DAYS:]
    baseline = history[:-RECENT_DAYS]
    recent_shares = [_category_shares(day) for day in recent]
    baseline_shares = [_category_shares(day) for day in baseline]
    # A day with no items has no composition and would otherwise read as 0% in
    # every category, manufacturing separation out of an outage.
    if any(not shares for shares in recent_shares + baseline_shares):
        return None

    candidates = []
    for category in sorted(_category_shares(today)):
        recent_values = [shares.get(category, 0.0) for shares in recent_shares]
        baseline_values = [shares.get(category, 0.0) for shares in baseline_shares]
        recent_mean = statistics.mean(recent_values)
        baseline_mean = statistics.mean(baseline_values)
        shift = recent_mean - baseline_mean
        if abs(shift) < MINIMUM_SHIFT_POINTS:
            continue
        rising = shift > 0
        separated = (
            min(recent_values) > max(baseline_values)
            if rising
            else max(recent_values) < min(baseline_values)
        )
        if not separated:
            continue
        breadth, present = _source_breadth(today, category)
        if breadth < MINIMUM_SOURCE_BREADTH:
            continue
        count, total = _category_counts(today, category)
        candidates.append(
            {
                "category": category,
                "rising": rising,
                "recent_share": round(recent_mean, 1),
                "baseline_share": round(baseline_mean, 1),
                "shift_points": round(shift, 1),
                "recent_days": len(recent_values),
                "baseline_days": len(baseline_values),
                "count": count,
                "total": total,
                "source_breadth": breadth,
                "sources_present": present,
            }
        )
    if not candidates:
        return None
    # Largest absolute move wins. Publishing every category that cleared the
    # bar would let a reader pick the most flattering one.
    candidates.sort(key=lambda finding: abs(finding["shift_points"]), reverse=True)
    return candidates[0]


def _confidence(finding: dict[str, Any], coverage: Coverage) -> str:
    """Kent-style calibrated confidence, tied to stated evidence.

    Optional connectors being down caps confidence at moderate rather than
    suppressing the finding. Composition shares are less sensitive to a missing
    source than volume counts are, so the claim survives, but "high" would
    overstate a feed that was missing three connectors: what those sources
    would have contributed is unmeasured, and calling that high confidence is
    the unstated-error-bar failure the rubric warns about.
    """
    if not coverage.complete:
        return "Low confidence"
    if finding["source_breadth"] < finding["sources_present"]:
        return "Moderate confidence"
    return "High confidence" if not coverage.failed_optional else "Moderate confidence"


def describe(finding: dict[str, Any], coverage: Coverage) -> list[str]:
    """Render a verified finding as a BLUF-ordered card.

    Judgment first, then the evidence that supports it, then the confidence and
    the collection gap. The wording says "our captured feed" because that is
    what was measured: a keyword-filtered scrape of a handful of sources, not
    the field.
    """
    direction = "rose to" if finding["rising"] else "fell to"
    category = finding["category"].replace("_", " ")
    return [
        (
            f"{category.capitalize()} artifacts {direction} "
            f"{finding['recent_share']}% of our captured feed over the last "
            f"{finding['recent_days']} days, against a {finding['baseline_share']}% baseline "
            f"across the prior {finding['baseline_days']} days "
            f"({finding['shift_points']:+.1f} pp)."
        ),
        (
            f"Today {finding['count']} of {finding['total']} items carry it, "
            f"across {finding['source_breadth']} of {finding['sources_present']} reporting sources."
        ),
        f"{_confidence(finding, coverage)}. {coverage.caption()}",
    ]


def no_finding(history: list[dict[str, Any]], coverage: Coverage) -> list[str]:
    """Render the absent case, which is a result rather than a failure.

    Most days in a niche feed genuinely have no pattern. Saying so is the
    correct output, and the three states are kept distinct so a quiet day is
    never confused with an outage or with a feed too small to read.
    """
    today = history[-1] if history else {}
    items = len(today.get("evidence_items") or [])
    if not coverage.complete:
        return [
            f"No pattern assessed for {items} items: connector coverage was incomplete, "
            "so a composition change cannot be separated from missing sources.",
            coverage.caption(),
        ]
    if items < MINIMUM_DAY_ITEMS:
        return [
            f"Insufficient volume to assess a pattern: {items} items is below the "
            f"{MINIMUM_DAY_ITEMS} needed for a composition claim.",
            coverage.caption(),
        ]
    if len(history) < RECENT_DAYS + MINIMUM_BASELINE_DAYS:
        return [
            f"Insufficient history to assess a pattern: {len(history)} days recorded, "
            f"{RECENT_DAYS + MINIMUM_BASELINE_DAYS} needed for a baseline.",
            coverage.caption(),
        ]
    return [
        f"No material pattern detected among {items} items. Every category share "
        "stayed within its trailing baseline.",
        coverage.caption(),
    ]


def daily_findings(
    history: list[dict[str, Any]], config: dict[str, Any] | None = None
) -> list[str]:
    """Return the day's briefing bullets, computed rather than generated.

    `history` is chronological and ends with the day being reported. Returns
    the no-finding card when nothing clears the bar, never an empty list: a
    briefing that says "nothing moved" is informative, and an absent one reads
    as a broken pipeline.
    """
    if not history:
        return []
    coverage = coverage_for(history[-1], config)
    finding = composition_shift(history) if coverage.complete else None
    if finding is None:
        return no_finding(history, coverage)
    return describe(finding, coverage)
