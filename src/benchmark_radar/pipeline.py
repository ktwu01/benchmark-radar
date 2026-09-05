from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import rubric
from .attention import fetch_attention_feeds
from .corpus import exact_artifact_keys
from .models import RadarItem, RadarRun, SourceHealth
from .sources import FUTURE_TIMESTAMP_TOLERANCE, SOURCE_FETCHERS, collection_method

TRACKING_PARAMETERS = {"ref", "source", "utm_campaign", "utm_content", "utm_medium", "utm_source"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMETERS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalized_title(title: str | None) -> str:
    # A connector that lets an upstream null through used to abort the entire
    # daily run here, losing every other source's evidence to one malformed
    # row. Connectors are still responsible for rejecting untitled records;
    # this only keeps that mistake from being fatal to the whole collection.
    return " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))


def dedupe_keys(item: RadarItem) -> list[str]:
    """Every identity this record can be recognized by.

    Keying on the normalized title alone ignored the DOI, arXiv id, and
    owner/repo already sitting in ``artifact_urls``, so two connectors that
    titled the same artifact differently never merged, and short-titled
    repositories such as ``torchgeo/torchgeo`` fell back to a URL key that can
    never match across sources.

    The keys are additive rather than ranked: a record merges with anything it
    shares *any* identity with. Returning only the strongest key would make
    dedup stricter instead of smarter, because a paper and its own repository
    have different exact identifiers and would stop merging on their title.
    """
    keys: list[str] = [
        # Every identifier, not just the strongest: a paper linking its own
        # repository must emit that repository's key too, or the two never meet.
        exact
        for exact in exact_artifact_keys(
            {
                "url": item.url,
                "artifact_urls": item.artifact_urls,
                "source": item.source,
                "source_id": item.source_id,
            }
        )
        # A URL digest is not a public identifier, so it carries no more
        # authority than the canonical URL already used below.
        if not exact.startswith("artifact:url:")
    ]
    title_key = normalized_title(item.title)
    if len(title_key) >= 24:
        keys.append(f"title:{hashlib.sha256(title_key.encode()).hexdigest()}")
    keys.append(f"url:{hashlib.sha256(canonical_url(item.url).encode()).hexdigest()}")
    return keys


def deduplicate(items: list[RadarItem]) -> list[RadarItem]:
    def merge_into(target: RadarItem, duplicate: RadarItem) -> None:
        if duplicate.url != target.url and duplicate.url not in target.artifact_urls:
            target.artifact_urls.append(duplicate.url)
        target.metrics.update(
            {
                metric: max(value, target.metrics.get(metric, 0))
                for metric, value in duplicate.metrics.items()
            }
        )
        # The merged copy is dropped, so keep the corroboration it carried:
        # a cross-source link is exactly what the evidence component reads.
        for url in duplicate.artifact_urls:
            if url != target.url and url not in target.artifact_urls:
                target.artifact_urls.append(url)
        for author in duplicate.authors:
            if author not in target.authors:
                target.authors.append(author)
        for organization in duplicate.organizations:
            if organization not in target.organizations:
                target.organizations.append(organization)
        # A record with no description loses nothing by adopting one that has
        # it; a record that already has one keeps its own.
        if not target.summary.strip() and duplicate.summary.strip():
            target.summary = duplicate.summary
        for rationale in duplicate.rationale:
            if rationale not in target.rationale:
                target.rationale.append(rationale)
        note = f"Also found via {duplicate.source}"
        if note not in target.rationale:
            target.rationale.append(note)

    kept: dict[str, RadarItem] = {}
    order: list[RadarItem] = []
    for item in sorted(
        items,
        key=lambda value: value.updated_at or value.published_at,
        reverse=True,
    ):
        keys = dedupe_keys(item)
        matches: list[RadarItem] = []
        for key in keys:
            match = kept.get(key)
            if match is not None and not any(match is candidate for candidate in matches):
                matches.append(match)
        if matches:
            # A bridge can connect two clusters that already exist: for example,
            # a DOI-plus-repository record arriving after DOI-only and repo-only
            # observations. Keep the first (newest) cluster and absorb every
            # other match so identity remains genuinely transitive.
            positions = {id(candidate): index for index, candidate in enumerate(order)}
            matches.sort(key=lambda candidate: positions[id(candidate)])
            target = matches[0]
            merge_into(target, item)
            for absorbed in matches[1:]:
                merge_into(target, absorbed)
                order = [candidate for candidate in order if candidate is not absorbed]
                for known_key, known_target in list(kept.items()):
                    if known_target is absorbed:
                        kept[known_key] = target
        else:
            target = item
            order.append(item)
        for key in keys:
            kept[key] = target
    # One record is registered under several keys, so dict values repeat.
    # Insertion order is preserved to keep the output deterministic.
    return order


def match_phrase(text: str, term: str) -> bool:
    """Substring match anchored at a word start, optionally at a word end too.

    A bare substring test let `corpora` match inside "incorporates" and
    "corporate", tagging unrelated artifacts as datasets: the same failure mode
    issue #51 raised for bare taxonomy words. Anchoring the left edge fixes
    most of it while preserving the deliberate stem behaviour the taxonomy
    relies on, since `evaluat` must still match "evaluating" and "evaluated".

    A trailing ``$`` on a term closes the right edge as well, which is what
    separates the whole word `corpora$` from the stem `evaluat`.
    """
    term = term.lower()
    if term.endswith("$"):
        return re.search(rf"\b{re.escape(term[:-1])}\b", text) is not None
    return re.search(rf"\b{re.escape(term)}", text) is not None


def _proximity_tokens(text: str) -> list[str]:
    """Word tokens with hyphens treated as separators.

    Repository names carry their whole description in one hyphenated slug
    (`agent-failure-atlas-benchmark`), so splitting only on whitespace hides
    the two words a proximity rule needs to see. Six of the agentic misses
    measured for issue #52 were exactly this shape.
    """
    return re.findall(r"[a-z0-9]+", text.replace("-", " "))


def match_proximity_rule(text: str, rule: dict[str, Any]) -> str | None:
    """Match when a term from each of two token groups appears close together.

    A plain substring test demands the words be literally adjacent in one
    fixed order, so `agent benchmark` cannot see "Benchmark **for** Database
    Operations **Agents**" -- the dominant real phrasing. Measured against a
    hand-labeled sample of the corpus (109 candidates, two independent
    annotators, Cohen's kappa 0.888), the adjacency list scored 21.7% recall
    where this rule reaches 95.0% at 75.0% precision.

    `exclude` removes the residual false positives, which are systematically
    artifacts that *build* an agent or survey the field rather than evaluate
    one.
    """
    if rule.get("exclude") and re.search(str(rule["exclude"]), text):
        return None
    tokens = _proximity_tokens(text)
    window = int(rule.get("within", 15))
    left = {str(term).lower() for term in rule.get("any_of") or []}
    right = {str(term).lower() for term in rule.get("near") or []}
    left_at = [n for n, token in enumerate(tokens) if token in left]
    right_at = [n for n, token in enumerate(tokens) if token in right]
    for a in left_at:
        for b in right_at:
            if abs(a - b) <= window:
                return f"{tokens[a]}~{tokens[b]}"
    return None


def is_self_reference(item: RadarItem) -> bool:
    """Whether a record is this project reporting on itself.

    Matched on the exact repository identity rather than on a substring, so an
    unrelated repository whose name merely contains "benchmark-radar" (the
    corpus already holds `H20Zhang/Agent-Benchmark-Radar`) keeps its place.
    The canonical GitHub `source_id` is the reliable signal; the URL is checked
    as well because a record can arrive from a release or first-party feed
    whose id is not the `owner/name` pair.
    """
    if item.source_id and item.source_id.strip().lower() == rubric.SELF_REPOSITORY:
        return True
    parsed = urlsplit(item.url or "")
    if parsed.netloc.lower().removeprefix("www.") != "github.com":
        return False
    parts = [part for part in parsed.path.lower().split("/") if part]
    return len(parts) >= 2 and "/".join(parts[:2]) == rubric.SELF_REPOSITORY


def _has_structural_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _matches_structural_signal(item: RadarItem, signal: dict[str, Any]) -> bool:
    fields = tuple(str(field) for field in signal["fields"])
    values = [_has_structural_value(getattr(item, field, None)) for field in fields]
    if signal["condition"] == "all_missing":
        return not any(values)
    raise ValueError(f"unknown structural signal condition: {signal['condition']}")


def score_item(
    item: RadarItem,
    taxonomy: dict[str, Any],
    now: datetime | None = None,
    *,
    lookback_hours: float = rubric.DEFAULT_LOOKBACK_HOURS,
) -> RadarItem:
    now = now or datetime.now(UTC)
    # Only match against text a human actually wrote about the artifact. If a
    # fetcher ever reintroduces a generated summary, the words in it must not
    # earn relevance -- otherwise the pipeline scores itself on its own prose.
    haystack = f"{item.title} {item.summary}".lower()
    categories = []
    matched_terms: list[str] = []
    for category, terms in taxonomy.items():
        # A category is either a plain phrase list or a proximity rule. Both
        # shapes stay supported so the three categories measured as working
        # (benchmark, dataset, evaluation at 96-98% recall) keep their exact
        # current semantics and counts.
        if isinstance(terms, dict):
            hit = match_proximity_rule(haystack, terms)
            matches = [hit] if hit else []
        else:
            matches = [term for term in terms if match_phrase(haystack, term)]
        if matches:
            categories.append(category)
            matched_terms.extend(matches[:2])
    item.categories = categories
    relevance = min(
        rubric.SCORE_MAX,
        rubric.RELEVANCE_PER_CATEGORY * len(categories)
        + rubric.RELEVANCE_PER_TERM * len(matched_terms),
    )
    text_deductions = [
        signal
        for signal in rubric.LOW_VALUE_SIGNALS
        if re.search(str(signal["pattern"]), haystack, flags=re.IGNORECASE)
    ]
    structural_deductions = [
        signal for signal in rubric.STRUCTURAL_SIGNALS if _matches_structural_signal(item, signal)
    ]
    deductions = [*text_deductions, *structural_deductions]
    deduction = min(
        rubric.MAX_LOW_VALUE_DEDUCTION,
        sum(float(signal["deduction"]) for signal in deductions),
    )
    item.relevance_score = max(0.0, relevance - deduction)
    item.suppression_reasons = [
        str(signal["label"]) for signal in deductions if signal["action"] == "suppress"
    ]
    if is_self_reference(item):
        item.suppression_reasons.append(rubric.SELF_REFERENCE_LABEL)

    evidence = rubric.EVIDENCE_BASE
    if item.source in rubric.EVIDENCE_PRIMARY_SOURCES:
        evidence += rubric.EVIDENCE_PRIMARY_CREDIT
    if item.source in rubric.EVIDENCE_ARTIFACT_SOURCES:
        evidence += rubric.EVIDENCE_ARTIFACT_CREDIT
    if item.authors:
        evidence += rubric.EVIDENCE_AUTHORSHIP_CREDIT
    if item.artifact_urls:
        evidence += rubric.EVIDENCE_CROSS_LINK_CREDIT
    item.evidence_score = min(evidence, rubric.SCORE_MAX)

    activity_at = item.updated_at or item.published_at
    age_hours = max(0.0, (now - activity_at).total_seconds() / 3600)
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")
    item.recency_score = max(
        0.0,
        rubric.SCORE_MAX * (1.0 - age_hours / lookback_hours),
    )
    recency_factor = rubric.RECENCY_EVENT_FACTORS.get(item.event_kind, 1.0)
    item.recency_score *= recency_factor

    # Each counter is scored on its own log curve against its own saturation
    # point, then the strongest one wins. Counters that accumulate without a
    # human decision are capped first, so a large automated download total can
    # place a record mid-pack but cannot outscore a widely-starred repository
    # (issue #278). The cap applies per metric before the max, not to the
    # result, so a record carrying both stars and downloads is still free to
    # score above the cap on its stars.
    adoption = max(
        (
            min(
                rubric.SCORE_MAX
                * math.log10(1 + max(0.0, float(item.metrics.get(metric, 0))))
                / math.log10(1 + saturation),
                rubric.ADOPTION_CAPPED_METRICS.get(metric, rubric.SCORE_MAX),
            )
            for metric, saturation in rubric.ADOPTION_METRIC_SATURATION.items()
            if item.metrics.get(metric, 0)
        ),
        default=0.0,
    )
    item.adoption_score = min(adoption, rubric.SCORE_MAX)
    item.total_score = round(
        sum(
            weight * getattr(item, f"{component}_score")
            for component, weight in rubric.WEIGHTS.items()
        ),
        2,
    )
    item.score_version = rubric.SCORING_VERSION
    item.score_max = rubric.SCORE_MAX
    item.rationale = [
        reason
        for reason in item.rationale
        if not reason.startswith(
            (
                "Matched:",
                "Demoted:",
                "Structural demotion:",
                "Structural gate:",
                "Recency discount:",
                "Primary record:",
            )
        )
    ]
    if matched_terms:
        item.rationale.append(f"Matched: {', '.join(sorted(set(matched_terms)))}")
    for signal in text_deductions:
        item.rationale.append(
            f"Demoted: {signal['label']} (-{float(signal['deduction']):g} relevance)"
        )
    for signal in structural_deductions:
        prefix = "Structural gate" if signal["action"] == "suppress" else "Structural demotion"
        item.rationale.append(
            f"{prefix}: {signal['label']} (-{float(signal['deduction']):g} relevance)"
        )
    if recency_factor < 1.0:
        item.rationale.append(f"Recency discount: {item.event_kind} event ×{recency_factor:g}")
    item.rationale.append(f"Primary record: {item.source}")
    return item


def apply_watchlist(
    items: list[RadarItem],
    watchlist: list[dict[str, Any]],
) -> list[RadarItem]:
    """Tag records naming an artifact the reader always wants to see.

    Only the title and source id are matched. A watchlisted name mentioned in
    passing inside an abstract describes related work, not a release of that
    artifact, so including the summary pinned unrelated papers to the top.
    Matching is on word boundaries for the same reason: a bare substring made
    "long horizon" swallow every agent paper that used the phrase.

    This marks and routes the record only; it never edits a score, so the
    published ranking stays explainable.
    """
    if not watchlist:
        return items
    for item in items:
        haystack = f"{item.title} {item.source_id}".casefold()
        for entry in watchlist:
            name = str(entry.get("name") or "").strip()
            aliases = [str(alias).casefold() for alias in entry.get("aliases") or []]
            terms = [alias for alias in [*aliases, name.casefold()] if alias]
            # Hyphens, spaces and underscores are interchangeable separators
            # so "mle-bench", "mle bench" and "mle_bench" all match one alias.
            patterns = [
                r"(?<![0-9a-z])"
                + r"[\s_-]*".join(re.escape(part) for part in re.split(r"[\s_-]+", term) if part)
                + r"(?![0-9a-z])"
                for term in terms
            ]
            if any(re.search(pattern, haystack) for pattern in patterns):
                item.watchlist = name or terms[0]
                item.watchlist_note = str(entry.get("note") or "").strip()
                item.rationale.append(f"Watchlist: {item.watchlist}")
                break
    return items


BOILERPLATE_THRESHOLD = 3


def assert_no_boilerplate_summaries(items: list[RadarItem]) -> None:
    """Fail the run when a fetcher emits one summary for many different records.

    A summary repeated across unrelated artifacts is templated text, not a
    description. It misleads the reader and, because `score_item` reads
    `summary`, it also inflates relevance for every record from that source.
    This is a hard error rather than a warning: a silently boilerplated report
    looks successful, which is how the defect survived unnoticed before.
    """
    counts = Counter(item.summary.strip().lower() for item in items if item.summary.strip())
    repeated = {text: n for text, n in counts.items() if n >= BOILERPLATE_THRESHOLD}
    if repeated:
        worst = max(repeated.items(), key=lambda pair: pair[1])
        raise RuntimeError(
            f"Refusing to publish templated descriptions: {worst[1]} records share the "
            f"summary {worst[0]!r}. Derive summaries from source metadata (see describe.py) "
            "and leave them empty when the source publishes none."
        )


def _drop_future_dated_items(
    items: list[RadarItem],
    *,
    now: datetime,
) -> tuple[list[RadarItem], int]:
    """Quarantine records whose source timestamps are materially in the future."""
    latest_allowed = now + FUTURE_TIMESTAMP_TOLERANCE
    accepted = [
        item
        for item in items
        if item.published_at <= latest_allowed
        and (item.updated_at is None or item.updated_at <= latest_allowed)
    ]
    return accepted, len(items) - len(accepted)


def _failure_streak_key(layer: str, health: Any) -> str:
    if layer == "producer":
        identity = [layer, health.producer, health.source]
    else:
        identity = [layer, health.source]
    return json.dumps(identity, ensure_ascii=False, separators=(",", ":"))


def _date(value: str | None, *, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _apply_arxiv_discovery_state(
    fetched: list[RadarItem],
    *,
    now: datetime,
    state: dict[str, Any],
) -> list[RadarItem]:
    arxiv_state = state.setdefault("arxiv", {})
    changed: list[RadarItem] = []
    for item in fetched:
        previous = arxiv_state.get(item.source_id) or {}
        activity_at = item.updated_at or item.published_at
        item.discovered_at = _date(previous.get("discovered_at"), fallback=now)
        previous_activity = _date(
            previous.get("last_activity_at"),
            fallback=datetime.min.replace(tzinfo=UTC),
        )
        if not previous or activity_at > previous_activity:
            changed.append(item)
        arxiv_state[item.source_id] = {
            "discovered_at": item.discovered_at.astimezone(UTC).isoformat(),
            "last_activity_at": activity_at.astimezone(UTC).isoformat(),
        }
    return changed


def _score_and_select(
    items: list[RadarItem],
    config: dict[str, Any],
    *,
    now: datetime,
    fetched_count: int,
    suppressed_count: int,
    future_dated_count: int = 0,
) -> tuple[list[RadarItem], dict[str, Any]]:
    """Score, dedupe and select a fetched item pool as of a given moment.

    Split out of `run_pipeline` so a backfill replay can reuse the exact same
    scoring and selection a live run applies, evaluated at a simulated `now`
    instead of the real one, without duplicating the eligibility/watchlist/sort
    logic a second time.
    """
    settings = config["radar"]
    # `minimum_score` is the legacy config name. It now controls only the
    # Recommended presentation badge; it never decides whether a record is
    # retained. `float()` accepts `.nan` from YAML, so validate it explicitly.
    recommendation_score = float(settings["minimum_score"])
    if not math.isfinite(recommendation_score):
        raise ValueError(
            f"minimum_score must be a finite recommendation threshold, got {recommendation_score!r}"
        )
    # A record with no title cannot be rendered: report._escape() raises on
    # None, so letting one through here only moves the crash from dedup to
    # publication. Connectors already reject untitled records, and this drops
    # any that a future connector lets slip rather than failing the whole run.
    # Counted separately so the funnel does not silently bill the drop to
    # dedupe, which would hide the connector bug this is compensating for.
    titled = [item for item in items if (item.title or "").strip()]
    untitled_count = len(items) - len(titled)
    unique = deduplicate(titled)
    scored = apply_watchlist(
        [
            score_item(
                item,
                config["taxonomy"],
                now,
                lookback_hours=float(settings["lookback_hours"]),
            )
            for item in unique
        ],
        config.get("watchlist") or [],
    )
    for item in scored:
        item.recommended = item.total_score >= recommendation_score
    selected = [
        item
        for item in scored
        # Suppression is checked before the watchlist, not beside it. Written as
        # `item.watchlist or (not item.suppression_reasons and ...)` the `or`
        # short-circuits, so a watchlisted record published even when it matched
        # a suppress rule, which made every "hard" filter advisory.
        if not item.suppression_reasons
        # A watchlist hit is retained even without a taxonomy category: the
        # reader asked for it by name. Scores do not participate in eligibility.
        and (item.watchlist or item.categories)
    ]
    selected.sort(
        key=lambda item: (bool(item.watchlist), item.total_score, item.published_at),
        reverse=True,
    )
    # The snapshot is the corpus, not the digest. Retain every eligible record;
    # `issue_item_limit` bounds the Markdown issue separately.
    published = selected
    assert_no_boilerplate_summaries(published)
    # The dashboard previously showed "228 found" beside 8 published records
    # with nothing to explain the gap. Persist each stage so the drop-off is
    # auditable rather than looking like lost data.
    #
    # These counters mirror the eligibility predicate above in its own
    # precedence order, so each excluded record has one reason and they sum to
    # `scored - eligible`. Recommendation is reported alongside the funnel,
    # never as a drop reason.
    # Self-exclusion is counted apart from the low-value deductions. Both stop
    # a record at the same gate, but billing "this project's own repository" to
    # `suppressed_low_value` would report a credibility rule as a taxonomy
    # judgement and make the low-value count untrue.
    suppressed_self_reference = sum(
        1 for item in scored if rubric.SELF_REFERENCE_LABEL in item.suppression_reasons
    )
    suppressed_low_value = sum(
        1
        for item in scored
        if rubric.SELF_REFERENCE_LABEL not in item.suppression_reasons and item.suppression_reasons
    )
    uncategorized = sum(
        1
        for item in scored
        if not item.suppression_reasons and not item.watchlist and not item.categories
    )
    recommended = sum(1 for item in selected if item.recommended)
    merged_as_duplicate = len(titled) - len(unique)
    selection = {
        "fetched": fetched_count,
        # arXiv records already seen in a previous run, dropped before dedupe.
        "suppressed_as_seen": suppressed_count,
        # Invalid upstream dates are removed before scoring so they cannot get
        # maximum recency or displace legitimate current records.
        "suppressed_future_dated": future_dated_count,
        # Records a connector emitted with no usable title. Always 0 unless a
        # connector regresses, so a non-zero value here is the signal that one
        # has, rather than an unexplained gap between fetched and deduplicated.
        "suppressed_untitled": untitled_count,
        # Multiple source observations absorbed into one surviving artifact.
        "merged_as_duplicate": merged_as_duplicate,
        "deduplicated": len(unique),
        "scored": len(scored),
        "eligible": len(selected),
        # Deprecated compatibility alias for consumers of snapshots written
        # before score stopped participating in eligibility.
        "qualified": len(selected),
        # Retained purely by a watchlist match rather than taxonomy.
        "watchlisted": sum(1 for item in selected if item.watchlist and not item.categories),
        # Suppression now applies to watchlisted records too, so the count is
        # every suppressed record rather than only the un-watchlisted ones.
        "suppressed_low_value": suppressed_low_value,
        # This project's own repository, removed from its own ranking (#278).
        "suppressed_self_reference": suppressed_self_reference,
        # Deprecated compatibility field. Scores no longer suppress records.
        "suppressed_below_minimum": 0,
        # Matched no taxonomy category and was not explicitly watchlisted.
        "suppressed_uncategorized": uncategorized,
        # Presentation split across eligible records. Both groups are retained.
        "recommended": recommended,
        "not_recommended": len(selected) - recommended,
        # This pass only. The whole day can hold more because two or more passes
        # merge into one snapshot and their unions are counted by
        # `published_total` in `merge_snapshots`.
        "published": len(published),
        # The old key remains readable by historical tooling; the new key names
        # its actual role for current consumers.
        "minimum_score": recommendation_score,
        "recommendation_score": recommendation_score,
        # Zero is the explicit uncapped marker. Historical snapshots carry the
        # numeric truncation limit (usually 300), so trend code can reject a
        # comparison across this measurement-policy transition.
        "report_limit": 0,
        # A per-source fetch that returned exactly this many rows was truncated,
        # so "300 found" is a ceiling rather than a total. Publishing the cap
        # lets the dashboard say which counts are limits.
        "max_items_per_source": int(settings["max_items_per_source"]),
        "lookback_hours": float(settings["lookback_hours"]),
        "score_version": rubric.SCORING_VERSION,
        "score_max": rubric.SCORE_MAX,
        # Which rules produced this day's categories (issue #72). Recorded
        # beside the scoring version for the same reason: a category count is
        # only comparable across days that were classified the same way.
        "taxonomy_version": rubric.taxonomy_version(config.get("taxonomy") or {}),
    }
    return published, selection


# Connectors this project can honestly re-derive for a past date from data
# fetched today. arXiv is excluded: its reliable path (RSS, config.yml's
# `atom_enabled: false`) only ever serves the current feed with no date-range
# query, and its date-range-capable path (Atom) is the one already disabled
# for rate-limit fragility (see config.yml comments at the arxiv source). Its
# adoption metrics (stars/downloads/citations) also reflect today's values,
# not what they were on the simulated date, which is a known limitation of
# every connector below too -- recorded on the resulting run rather than
# presented as if it were measured at the time.
BACKFILL_SOURCES = {
    "huggingface",
    "github",
    "github_releases",
    "openreview",
    "semantic_scholar",
    "crossref",
}


def simulate_backfill(
    config: dict[str, Any],
    dates: list[datetime],
    *,
    previous_snapshot: dict[str, Any] | None = None,
) -> list[RadarRun]:
    """Derive one simulated `RadarRun` per date in `dates` from a single fetch.

    Issue #35: reaching 30 daily snapshots by waiting on the calendar is slow
    when the same historical window is already fetchable today. Rather than
    issue one live historical query per simulated date (rate-limit and
    flakiness risk for `github` in particular, and arXiv cannot do this at
    all -- see `BACKFILL_SOURCES`), every connector below is queried exactly
    once with `since` covering the entire requested span, and each simulated
    date re-runs the same scoring and selection `run_pipeline` uses, evaluated
    at that date instead of the live one.

    `dates` must be sorted oldest first: discovery_state (the arXiv
    already-seen ledger folds into this too, though arxiv itself never
    contributes items here) chains from one simulated day to the next exactly
    as the daily pipeline chains from one real day to the next, and running
    dates out of order would let a later, older `discovered_at` overwrite a
    real ledger entry.
    """
    if dates != sorted(dates):
        raise ValueError("simulate_backfill dates must be sorted oldest first")
    settings = config["radar"]
    lookback_hours = int(settings["lookback_hours"])
    limit = int(settings["max_items_per_source"])
    earliest_since = min(dates) - timedelta(hours=lookback_hours)

    pool: list[RadarItem] = []
    fetch_health: list[SourceHealth] = []
    for source_name, source_config in config["sources"].items():
        if source_name not in BACKFILL_SOURCES or not source_config.get("enabled", True):
            continue
        fetcher = SOURCE_FETCHERS[source_name]
        try:
            fetched = fetcher(source_config, earliest_since, limit)
            fetch_health.append(
                SourceHealth(
                    source=source_name,
                    ok=True,
                    item_count=len(fetched),
                    method=collection_method(source_name, fetched),
                )
            )
            pool.extend(fetched)
        except Exception as error:  # a partial backfill is preferable; health exposes the gap
            fetch_health.append(
                SourceHealth(
                    source=source_name,
                    ok=False,
                    error=f"{type(error).__name__}: {error}",
                )
            )

    runs: list[RadarRun] = []
    discovery_state = deepcopy((previous_snapshot or {}).get("discovery_state") or {})
    for simulated_now in dates:
        since = simulated_now - timedelta(hours=lookback_hours)
        visible = [
            deepcopy(item)
            for item in pool
            if since <= (item.updated_at or item.published_at) <= simulated_now
        ]
        for item in visible:
            item.discovered_at = simulated_now
            item.retrieved_at = item.retrieved_at or simulated_now
        health = [
            *fetch_health,
            SourceHealth(
                source="arxiv",
                ok=False,
                error="arXiv has no date-range query on the RSS path this project relies on; "
                "excluded from simulated backfill (issue #35 known limitation)",
            ),
        ]
        published, selection = _score_and_select(
            visible,
            config,
            now=simulated_now,
            fetched_count=len(visible),
            suppressed_count=0,
        )
        selection["simulated"] = True
        runs.append(
            RadarRun(
                generated_at=simulated_now,
                since=since,
                items=published,
                health=health,
                selection=selection,
                discovery_state=discovery_state,
            )
        )
    return runs


def run_pipeline(
    config: dict[str, Any],
    now: datetime | None = None,
    *,
    previous_snapshot: dict[str, Any] | None = None,
) -> RadarRun:
    now = now or datetime.now(UTC)
    settings = config["radar"]
    since = now - timedelta(hours=int(settings["lookback_hours"]))
    limit = int(settings["max_items_per_source"])
    items: list[RadarItem] = []
    health: list[SourceHealth] = []
    # Counted before arXiv overlap and future-date suppression. The selection
    # funnel records both exclusions so every fetched row remains accounted for.
    fetched_count = 0
    suppressed_count = 0
    future_dated_count = 0
    discovery_state = deepcopy((previous_snapshot or {}).get("discovery_state") or {})
    for source_name, source_config in config["sources"].items():
        if not source_config.get("enabled", True):
            continue
        fetcher = SOURCE_FETCHERS[source_name]
        try:
            fetch_config = {**source_config, "_collection_now": now}
            if source_name == "openalex":
                fetched = fetcher(fetch_config, since, limit, now=now)
            else:
                fetched = fetcher(fetch_config, since, limit)
            connector_rejected = int(fetch_config.get("_future_rejections", 0) or 0)
            fetched_count += len(fetched) + connector_rejected
            fetched, rejected_future = _drop_future_dated_items(fetched, now=now)
            rejected_future += connector_rejected
            future_dated_count += rejected_future
            source_notes = [str(value) for value in fetch_config.get("_source_warnings", [])]
            if rejected_future:
                source_notes.insert(0, f"Discarded {rejected_future} future-dated record(s)")
            health.append(
                SourceHealth(
                    source=source_name,
                    ok=True,
                    item_count=len(fetched),
                    error="; ".join(source_notes) if source_notes else None,
                    method=collection_method(source_name, fetched),
                )
            )
            for item in fetched:
                item.retrieved_at = item.retrieved_at or now
            if source_name == "arxiv":
                changed = _apply_arxiv_discovery_state(
                    fetched,
                    now=now,
                    state=discovery_state,
                )
                suppressed_count += len(fetched) - len(changed)
                items.extend(changed)
            else:
                for item in fetched:
                    item.discovered_at = now
                items.extend(fetched)
        except Exception as error:  # a partial report is preferable; health exposes the gap
            health.append(
                SourceHealth(
                    source=source_name,
                    ok=False,
                    error=f"{type(error).__name__}: {error}",
                )
            )
    required = {
        name
        for name, source_config in config["sources"].items()
        if source_config.get("enabled", True) and source_config.get("required", False)
    }
    required_health = {source.source: source for source in health if source.source in required}
    unavailable_required = []
    for source in sorted(required):
        source_health = required_health.get(source)
        if source_health is None:
            unavailable_required.append(f"{source} was not checked")
        elif not source_health.ok:
            unavailable_required.append(
                f"{source} failed" + (f" ({source_health.error})" if source_health.error else "")
            )
        elif source_health.item_count == 0 and not config["sources"][source].get(
            "allow_empty", False
        ):
            unavailable_required.append(f"{source} returned no records")
    if unavailable_required:
        raise RuntimeError(
            "Required discovery sources failed or returned no records: "
            + ", ".join(unavailable_required)
        )
    published, selection = _score_and_select(
        items,
        config,
        now=now,
        fetched_count=fetched_count,
        suppressed_count=suppressed_count,
        future_dated_count=future_dated_count,
    )
    attention, attention_health, producer_health, attention_state = fetch_attention_feeds(
        config.get("attention") or {},
        observed_at=now,
        previous_state=((previous_snapshot or {}).get("discovery_state") or {}).get("attention")
        or {},
        previous_observations=((previous_snapshot or {}).get("attention") or {}).get("observations")
        or [],
    )
    previous_streaks = ((previous_snapshot or {}).get("discovery_state") or {}).get(
        "source_failure_streaks"
    ) or {}
    failure_streaks: dict[str, int] = {}
    monitored_health = [
        *(("evidence", source_health) for source_health in health),
        *(("attention", source_health) for source_health in attention_health),
        *(("producer", source_health) for source_health in producer_health),
    ]
    for layer, source_health in monitored_health:
        if source_health.ok:
            continue
        streak_key = _failure_streak_key(layer, source_health)
        previous = previous_streaks.get(streak_key, 0)
        try:
            previous_count = max(0, int(previous))
        except (TypeError, ValueError):
            previous_count = 0
        failure_streaks[streak_key] = previous_count + 1

    return RadarRun(
        generated_at=now,
        since=since,
        items=published,
        health=health,
        attention=attention,
        attention_ingest_health=attention_health,
        producer_health=producer_health,
        selection=selection,
        discovery_state={
            **discovery_state,
            "attention": attention_state,
            "source_failure_streaks": failure_streaks,
        },
    )
