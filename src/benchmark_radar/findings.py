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

import re
import statistics
from collections import Counter
from datetime import date, timedelta
from typing import Any

from .corpus import artifact_alias_map, exact_artifact_key

# A finding needs enough of the day to be about the day rather than about noise.
MINIMUM_DAY_ITEMS = 25
# Windows are deliberately short: this project holds two weeks of history, so
# the 28-to-56-day weekday-conditioned baselines that a mature feed would use
# are not available. Five and four are the smallest windows where a fully
# separated split is not routine chance, and both are checked below.
RECENT_DAYS = 5
MINIMUM_RECENT_DAYS = 4
MINIMUM_BASELINE_DAYS = 4
# The baseline is a bounded trailing window, not all recorded history. Left
# unbounded, one old extreme share would block separation permanently as the
# archive grows, silently suppressing every later real shift.
BASELINE_DAYS = 9
# Percentage points. Below this a composition change is not worth a reader's
# attention even when it is real and separated.
MINIMUM_SHIFT_POINTS = 5.0
# A change has to appear in at least this many sources, and in a majority of
# the sources comparable across both windows. The absolute floor rejects a
# two-source feed where one connector is half the evidence; the majority rule
# scales with the feed instead of demanding unanimity, which a fixed count
# effectively does when only three sources span both windows.
MINIMUM_SOURCE_BREADTH = 2
# Percentage points a single source must move on its own before it counts as
# having contributed. Without a floor, noise in three sources can certify a
# change that came almost entirely from a fourth.
MINIMUM_SOURCE_SHIFT_POINTS = 2.0
# The largest share of total movement one source may supply. Counting sources
# equally lets a connector contributing nearly all of a change hide behind two
# others that merely cleared the floor.
MAX_SOURCE_CONTRIBUTION = 0.7
# Categories are multi-label, so several move together and testing all of them
# invites reporting whichever crossed the line. Only the largest separated
# shift is published, which is the same discipline as reporting the gated cell
# rather than the average.
MAX_FINDINGS = 1
MAX_EVIDENCE_EXAMPLES = 3


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
            required = ", ".join(source.replace("_", " ") for source in self.failed_required)
            parts.append(f"required source(s) {required} unavailable")
        if self.failed_optional:
            optional = ", ".join(source.replace("_", " ") for source in self.failed_optional)
            parts.append(f"{optional} unavailable")
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
    # A required source with no health row at all never reported, which is not
    # the same as reporting successfully. Historical days recorded before a
    # connector became required would otherwise be admitted as fully covered,
    # and the caption would call the feed complete while a required source was
    # simply absent from it.
    reported = {str(entry.get("source")) for entry in health}
    for source, settings in sources.items():
        settings = settings or {}
        # A disabled source is intentionally not fetched and emits no health row,
        # which the pipeline also excludes from its own required-source gate.
        # Synthesizing a failure for it would mark every day incomplete and
        # suppress all findings until someone noticed the stale `required` flag.
        if not settings.get("enabled", True):
            continue
        if settings.get("required") and source not in reported:
            failed_required.append(source)
    return Coverage(
        healthy=sum(1 for entry in health if entry.get("ok")),
        total=len(health) + len(set(failed_required) - reported),
        failed_required=sorted(set(failed_required)),
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


def _per_source_shares(snapshot: dict[str, Any], category: str) -> dict[str, float]:
    """Return the category's share of each source's own items for one day."""
    totals: Counter[str] = Counter()
    matching: Counter[str] = Counter()
    for item in snapshot.get("evidence_items") or []:
        source = str(item.get("source"))
        totals[source] += 1
        if category in (item.get("categories") or []):
            matching[source] += 1
    return {source: 100.0 * matching[source] / total for source, total in totals.items() if total}


def _contributing_sources(
    recent: list[dict[str, Any]], baseline: list[dict[str, Any]], category: str, *, rising: bool
) -> tuple[int, int]:
    """Return how many sources independently moved, and how many are comparable.

    Presence is not contribution. A category can appear on many sources while
    its entire increase comes from one connector, which is the single-source
    artifact this gate exists to reject. So each source is measured against its
    own baseline share and counted only if it moved in the same direction as the
    aggregate claim. Only sources present in both windows are comparable: a
    connector that switched on mid-window has no baseline to move away from, and
    counting it would credit onboarding as a feed-wide shift.
    """

    def mean_share(days: list[dict[str, Any]], source: str) -> float | None:
        values = [
            shares[source]
            for shares in (_per_source_shares(day, category) for day in days)
            if source in shares
        ]
        return statistics.mean(values) if values else None

    recent_sources = {str(item.get("source")) for day in recent for item in day["evidence_items"]}
    baseline_sources = {
        str(item.get("source")) for day in baseline for item in day["evidence_items"]
    }
    comparable = recent_sources & baseline_sources
    moves: list[float] = []
    for source in comparable:
        recent_share = mean_share(recent, source)
        baseline_share = mean_share(baseline, source)
        if recent_share is None or baseline_share is None:
            continue
        # Material movement, not any directional drift. Counting a source that
        # went from 10% to 11% as a contributor would let three sources of noise
        # certify a change that came almost entirely from a fourth, which is the
        # single-source artifact this gate exists to reject.
        change = recent_share - baseline_share
        if abs(change) < MINIMUM_SOURCE_SHIFT_POINTS:
            continue
        if (change > 0) if rising else (change < 0):
            moves.append(abs(change))
    return moves, len(comparable)


def discriminating_power(baseline_share: float) -> float:
    """How much a category's presence distinguishes one artifact from another.

    A tag carried by almost everything says almost nothing about the artifact
    carrying it. In this corpus `benchmark` sits near 83% of items and `dataset`
    near 69%, because virtually everything a benchmark tracker collects is both;
    `agentic` sits near 12%, so knowing an artifact is agentic is genuinely
    informative. A ten-point move in a near-universal tag and a ten-point move
    in a discriminating one are not equally worth a reader's attention, even
    when both are equally verified.

    Scored as the absent fraction, `(100 - share) / 100`: the probability that
    an arbitrary artifact does *not* carry the tag, which is exactly how much
    the tag narrows the field when it does appear. This is the self-information
    of the label expressed linearly, and it is a stated property of the data
    rather than a threshold chosen to produce a preferred answer.

    Deliberately one-sided. Bernoulli variance, `share * (100 - share)`, was the
    first thing tried and is wrong here: it peaks at 50% and so scores `dataset`
    at 69% above `agentic` at 14%, penalising a rare category as heavily as a
    near-universal one. A rare category is informative, not less so; only
    universality dilutes a claim.
    """
    share = max(0.0, min(100.0, baseline_share))
    return (100.0 - share) / 100.0


def _ranking_key(finding: dict[str, Any]) -> tuple[float, float, str]:
    """Rank verified candidates by how much a reader learns from them.

    Size alone ranked the `dataset` decline above the `agentic` rise on real
    data, which is defensible arithmetic and a poor briefing: `dataset` tags
    most of the corpus, so its share moving is closer to a restatement of volume
    than to news about composition.

    Direction is deliberately not part of this. Preferring rises because they
    read as better news would choose the story over the evidence, and on a day
    whose only real signal is a decline it would surface a weaker rise instead.
    The category name breaks ties so the ordering is total and stable rather
    than dependent on dictionary iteration.
    """
    weight = discriminating_power(finding["baseline_share"])
    # Rounded before the tie-breakers run. Binary floats make products that are
    # mathematically equal compare unequal: a 20% baseline moving 6 pp and a 40%
    # baseline moving 8 pp both score 4.8, but the first evaluates to
    # 4.800000000000001 and would win on noise, silently skipping the larger-move
    # tie-break that is supposed to decide it.
    score = round(weight * abs(finding["shift_points"]), 6)
    return score, abs(finding["shift_points"]), finding["category"]


def _dominated_by_one_source(moves: list[float]) -> bool:
    """Whether one source supplies most of the movement being claimed.

    Counting sources equally is not enough. Three sources moving 0 to 100, 0 to
    2, and 0 to 0 satisfies both a count floor and a majority rule while 100 of
    102 matching items came from one connector, which is precisely the artifact
    the breadth gate exists to reject. So the largest single contribution is
    bounded as a fraction of the total movement.
    """
    if not moves:
        return True
    return max(moves) > MAX_SOURCE_CONTRIBUTION * sum(moves)


def _category_counts(snapshot: dict[str, Any], category: str) -> tuple[int, int]:
    """Return the category's item count and the day's total, for citation."""
    items = snapshot.get("evidence_items") or []
    matching = sum(1 for item in items if category in (item.get("categories") or []))
    return matching, len(items)


def _trailing_run(days: list[dict[str, Any]], usable) -> list[dict[str, Any]]:
    """Return the longest run of usable days on consecutive dates, ending last.

    Usability alone is not adjacency. A day with no snapshot at all leaves no
    entry to reject, so walking the list would silently step over the gap and
    describe five observations spanning a week as "the last 5 days". Requiring
    consecutive calendar dates makes a missing day end the run, which is what a
    persistence claim needs: the run has to be what it says it is.
    """
    run: list[dict[str, Any]] = []
    expected: date | None = None
    for day in reversed(days):
        if not usable(day):
            break
        current = date.fromisoformat(str(day["date"]))
        if expected is not None and current != expected:
            break
        run.append(day)
        expected = current - timedelta(days=1)
    return list(reversed(run))


# Every setting that changes which items a day contains or how they are
# classified. Historical snapshots record a positive `report_limit`; current
# uncapped snapshots record zero, so the transition is explicit rather than a
# missing value the conflict check would ignore.
MEASUREMENT_KEYS = ("taxonomy_version", "max_items_per_source", "report_limit")


def measurement_conflict(window: list[dict[str, Any]]) -> bool:
    """Whether the window spans a change in how the corpus was measured.

    Category shares are only comparable across days classified by the same
    taxonomy and collected under the same historical caps. Any of those changing
    reclassifies or re-selects artifacts wholesale, which can
    produce a fully separated share change that reflects the instrument rather
    than the feed.

    A day recording none of these keys is incomparable, not compatible: it was
    produced under settings nobody wrote down, and silently admitting it would
    let a differently-measured day sit inside a window described as verified.
    Individual absent keys are treated as unknown rather than different, which
    is what keeps the real history usable: its early days stamp the taxonomy but
    not the caps, and every one of them was in fact classified identically.
    """
    for key in MEASUREMENT_KEYS:
        recorded = {
            (day.get("selection") or {}).get(key)
            for day in window
            if (day.get("selection") or {}).get(key) is not None
        }
        if len(recorded) > 1:
            return True
    return False


def comparable_window(
    history: list[dict[str, Any]], config: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Return (recent, baseline) days fit to compare, or None.

    Every day in both windows has to clear the same bars, not just the day being
    reported. A one-item day yields 0% or 100% in every category and manufactures
    separation from a handful of records; a day missing a required connector can
    fake a composition change on its own; and days measured under different
    taxonomies are not measuring the same thing.
    """
    if len(history) < RECENT_DAYS + MINIMUM_BASELINE_DAYS:
        return None

    def usable(day: dict[str, Any]) -> bool:
        """Whether a day can stand in a comparison at all.

        A thin day yields 0% or 100% in every category and manufactures
        separation out of a handful of records. A day missing a required
        connector is measuring a different feed. A day recording none of the
        measurement settings was produced under settings nobody wrote down, so
        it cannot be certified as measured the same way as its neighbours. Each
        has to be kept out of both windows, not merely out of the reported day.
        """
        selection = day.get("selection") or {}
        return (
            len(day.get("evidence_items") or []) >= MINIMUM_DAY_ITEMS
            and coverage_for(day, config).complete
            and any(selection.get(key) is not None for key in MEASUREMENT_KEYS)
        )

    # The reported day itself is never dropped: if it cannot be compared, there
    # is nothing to report and the caller renders the reason instead.
    if not usable(history[-1]):
        return None
    # Windows must be contiguous. Dropping an unusable day from the middle and
    # comparing what is left would let a contradictory day be skipped while the
    # remaining days are still described as consecutive, which is the
    # cherry-picking the persistence rule exists to prevent. So the recent
    # window is the longest unbroken run of usable days ending today, and the
    # baseline is the longest unbroken run ending immediately before it.
    #
    # Truncating rather than rejecting outright matters: the real history opens
    # with four days of arXiv outage, and discarding every window that reaches
    # back to them would suppress findings for as long as those days stayed in
    # range.
    recent = _trailing_run(history[-RECENT_DAYS:], usable)
    if len(recent) < MINIMUM_RECENT_DAYS:
        return None
    earlier = history[: len(history) - len(recent)]
    baseline = _trailing_run(earlier[-BASELINE_DAYS:], usable)
    if len(baseline) < MINIMUM_BASELINE_DAYS:
        return None
    if measurement_conflict([*baseline, *recent]):
        return None
    return recent, baseline


def composition_shift(
    history: list[dict[str, Any]], config: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Return the largest verified composition shift, or None.

    `history` is chronological and ends with the day being reported. A shift is
    published only when the recent window is fully separated from the baseline:
    every recent day above every baseline day, or every recent day below.

    Full separation is a deliberately blunt instrument, and it is doing work a
    significance test cannot here. The trailing window contains the shift being
    detected, so a robust z-score against it scores the real 12.3% to 25.9%
    agentic move at 1.54 and rejects it. Separation asks instead whether the two
    windows describe the same regime, which is the actual question, and it
    rejects the one-day spikes a point test would happily report.
    """
    window = comparable_window(history, config)
    if window is None:
        return None
    recent, baseline = window
    recent_shares = [_category_shares(day) for day in recent]
    baseline_shares = [_category_shares(day) for day in baseline]
    today = history[-1]

    candidates = []
    # Every category seen anywhere in the window, not only those present today.
    # A category that collapsed to zero is absent from today's shares, so
    # iterating today would silently skip the most complete falling shift there
    # is: 30% throughout the baseline to 0% throughout the recent window.
    observed = {category for shares in [*baseline_shares, *recent_shares] for category in shares}
    for category in sorted(observed):
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
        # Contribution, not presence: the change has to show up independently in
        # several sources measured against their own baselines, in most of the
        # sources that can be compared at all, and without one of them supplying
        # nearly all of the movement.
        moves, comparable = _contributing_sources(recent, baseline, category, rising=rising)
        moved = len(moves)
        if moved < MINIMUM_SOURCE_BREADTH or moved * 2 <= comparable:
            continue
        if _dominated_by_one_source(moves):
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
                "sources_moved": moved,
                "sources_comparable": comparable,
            }
        )
    if not candidates:
        return None
    # Exactly one finding is published. Categories are multi-label and move
    # together, so several candidates are usually the same underlying shift
    # described three ways, and publishing all of them would let a reader pick
    # the most flattering framing.
    candidates.sort(key=_ranking_key, reverse=True)
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
    if finding["sources_moved"] < finding["sources_comparable"]:
        return "Moderate confidence"
    return "High confidence" if not coverage.failed_optional else "Moderate confidence"


def _representative_key(item: dict[str, Any]) -> tuple[bool, float, bool]:
    """Rank evidence for a reader, not merely for ingestion."""
    return (
        item.get("event_kind") == "released",
        float(item.get("total_score") or 0),
        bool(str(item.get("summary") or "").strip()),
    )


def first_seen_items(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the best record for each artifact on the day it first appeared.

    Daily snapshots overlap, and one artifact can arrive from several connectors.
    Examples must therefore be new to the radar, not merely present in today's
    rolling scan. Alias resolution also prevents a paper and its repository from
    being presented as independent pieces of evidence.
    """
    all_items = [item for day in history for item in day.get("evidence_items") or []]
    if not all_items:
        return []
    aliases = artifact_alias_map(all_items)
    seen: set[str] = set()
    today: list[dict[str, Any]] = []
    for day in history:
        first_on_day: dict[str, dict[str, Any]] = {}
        for item in day.get("evidence_items") or []:
            identity = aliases[exact_artifact_key(item)]
            if identity in seen:
                continue
            existing = first_on_day.get(identity)
            if existing is None or _representative_key(item) > _representative_key(existing):
                first_on_day[identity] = item
        seen.update(first_on_day)
        today = list(first_on_day.values())
    return sorted(today, key=_representative_key, reverse=True)


_FOCUS_PREFIX = re.compile(
    r"^(?:an?\s+)?(?:[\w-]+\s+){0,3}benchmark(?:ing)?\s*(?:for|of|on)?\s*",
    flags=re.IGNORECASE,
)
_EVIDENCE_THEMES = (
    ("personalization and memory", re.compile(r"\b(?:persona\w*|personali[sz]\w*|memor\w*)\b")),
    (
        "safety and evaluation integrity",
        re.compile(
            r"\b(?:privacy|secur\w*|safety|reliab\w*|validit\w*|adversarial|attack\w*|gaming)\b"
        ),
    ),
    ("coding agents", re.compile(r"\b(?:coding|software|web agents?|web generation|frontend)\b")),
    ("embodied systems", re.compile(r"\b(?:embodied|robot\w*|home safety|vision-language)\b")),
    (
        "evaluation infrastructure",
        re.compile(r"\b(?:harness\w*|infrastructure|observability|protocol\w*|framework\w*)\b"),
    ),
)


def _compact_evidence_label(item: dict[str, Any], *, focus_limit: int = 88) -> str:
    """Turn a source title into a compact statement of what it measures."""
    title = " ".join(str(item.get("title") or "").split())
    if not title:
        return "Untitled artifact"
    if ":" not in title:
        return title[:120].rstrip()
    name, focus = (part.strip() for part in title.split(":", 1))
    focus = re.sub(r"^(?:the|an?)\s+", "", focus, flags=re.IGNORECASE)
    focus = _FOCUS_PREFIX.sub("", focus).strip()
    if not focus:
        return name[:120].rstrip()
    if len(focus) > focus_limit:
        focus = focus[: focus_limit + 1].rsplit(" ", 1)[0].rstrip() + "…"
    # Source titles are usually title-cased. Preserve real acronyms such as LLM
    # and AI, while rendering the explanatory phrase as prose rather than a
    # headline pasted into parentheses.
    focus = re.sub(
        r"\b[A-Z][A-Za-z-]*\b",
        lambda match: match.group(0) if match.group(0).isupper() else match.group(0).lower(),
        focus,
    )
    return f"{name} ({focus})"


def _representative_evidence(
    items: list[dict[str, Any]], category: str, *, limit: int = MAX_EVIDENCE_EXAMPLES
) -> list[dict[str, Any]]:
    matching = [
        item
        for item in items
        if category in (item.get("categories") or []) and str(item.get("title") or "").strip()
    ]
    released = [item for item in matching if item.get("event_kind") == "released"]
    pool = released or matching
    return pool[:limit]


def evidence_examples(
    items: list[dict[str, Any]], category: str, *, limit: int = MAX_EVIDENCE_EXAMPLES
) -> list[str]:
    """Name the strongest first-seen releases that make a finding concrete."""
    return [
        _compact_evidence_label(item)
        for item in _representative_evidence(items, category, limit=limit)
    ]


def _evidence_theme(items: list[dict[str, Any]], category: str) -> tuple[str, int, int] | None:
    """Name a shared topic only when most representative titles support it."""
    representatives = _representative_evidence(items, category)
    if len(representatives) < 2:
        return None
    scored = []
    for position, (label, pattern) in enumerate(_EVIDENCE_THEMES):
        matches = sum(
            bool(pattern.search(str(item.get("title") or "").lower())) for item in representatives
        )
        scored.append((matches, -position, label))
    matches, _, label = max(scored)
    return (label, matches, len(representatives)) if matches >= 2 else None


def _join_examples(examples: list[str]) -> str:
    if len(examples) == 1:
        return examples[0]
    if len(examples) == 2:
        return f"{examples[0]} and {examples[1]}"
    return f"{'; '.join(examples[:-1])}; and {examples[-1]}"


def describe(
    finding: dict[str, Any], coverage: Coverage, *, first_seen: list[dict[str, Any]] | None = None
) -> list[str]:
    """Render a verified finding as a BLUF-ordered card.

    Judgment first, then the evidence that supports it, then the confidence and
    the collection gap. The wording says "our captured feed" because that is
    what was measured: a keyword-filtered scrape of a handful of sources, not
    the field.
    """
    direction = "rose to" if finding["rising"] else "fell to"
    category = finding["category"].replace("_", " ")
    bullets = [
        (
            f"{category.capitalize()} artifacts {direction} "
            f"{finding['recent_share']}% of our captured feed over the last "
            f"{finding['recent_days']} days, against a {finding['baseline_share']}% baseline "
            f"across the prior {finding['baseline_days']} days "
            f"({finding['shift_points']:+.1f} percentage points)."
        ),
    ]
    examples = evidence_examples(first_seen or [], finding["category"])
    if examples:
        theme = _evidence_theme(first_seen or [], finding["category"])
        lead = (
            f"{theme[0].capitalize()} recurred in {theme[1]} of the "
            f"{theme[2]} leading releases first observed today:"
            if theme
            else "The leading releases in that category first observed today were"
        )
        bullets.append(f"{lead} {_join_examples(examples)}.")
    bullets.append(
        f"The change appeared independently in {finding['sources_moved']} of "
        f"the {finding['sources_comparable']} sources present in both windows. "
        f"{_confidence(finding, coverage)}. {coverage.caption()}"
    )
    return bullets


def no_finding(
    history: list[dict[str, Any]], coverage: Coverage, config: dict[str, Any] | None = None
) -> list[str]:
    """Render the absent case, which is a result rather than a failure.

    Most days in a niche feed genuinely have no pattern. Saying so is the
    correct output, and the states are kept distinct so a quiet day is never
    confused with an outage or with a feed too small to read.

    The wording is deliberately conservative about *why* nothing was published.
    A candidate can clear separation and still be rejected for materiality or
    for coming from too few sources, so claiming every share stayed within its
    baseline would be false in exactly the cases a reader would most want to
    know about.
    """
    today = history[-1] if history else {}
    items = len(today.get("evidence_items") or [])
    if not coverage.complete:
        return [
            f"No pattern assessed for {items} items: a required connector was unavailable, "
            "so a composition change cannot be separated from missing sources.",
            coverage.caption(),
        ]
    if items < MINIMUM_DAY_ITEMS:
        return [
            f"Insufficient volume to assess a pattern: {items} items is below the "
            f"{MINIMUM_DAY_ITEMS} needed for a composition claim.",
            coverage.caption(),
        ]
    if comparable_window(history, config) is None:
        return [
            f"Insufficient comparable history to assess a pattern: "
            f"{MINIMUM_RECENT_DAYS} recent and {MINIMUM_BASELINE_DAYS} earlier days are needed "
            "with full required coverage, the same taxonomy, and enough volume each.",
            coverage.caption(),
        ]
    return [
        f"No material pattern detected among {items} items. No category shifted far enough, "
        "persistently enough, and across enough sources to report.",
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
    finding = composition_shift(history, config) if coverage.complete else None
    if finding is None:
        return no_finding(history, coverage, config)
    return describe(finding, coverage, first_seen=first_seen_items(history))
