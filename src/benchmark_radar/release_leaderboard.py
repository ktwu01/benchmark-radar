"""Derive transparent, evidence-first recent release rankings.

Issue #530:
Opening Leaderboard should immediately answer: which newly released benchmarks
are receiving the most public attention now?

Default view: Latest releases · 30 days.
Cohorts:
- Exactly window_start = generated_at_utc - days * 24h
  window_start <= release_timestamp <= generated_at_utc
- Canonical benchmark entities with at least one `event_kind == "released"`
  observation in the window. Routine `updated` records are excluded, and so are
  records typed as a model, a method, an agent, a harness, or a software version
  release (`release_kind.py`).
- Normalization: log1p(val) / log1p(window_max) with fixed weights:
  GitHub stars: 55%
  Hugging Face paper upvotes: 30%
  Hugging Face 30d downloads: 15%
- Missing is unknown: no imputation with zero or midpoint. Weights never redistributed.
- Formal rank requirements:
  - Durable signal from dedicated GitHub repository or exact HF dataset;
  - Observed fresh component weight >= 45%;
  - Stale signals cannot cross the ranking threshold.
  Otherwise surfaced as unranked `limited_signals`.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from .affiliation_rank import affiliation_normalized, best_institution, institution_weights
from .catalog_identity import DEFAULT_IDENTITY_PATH
from .catalog_overrides import DEFAULT_LLM_STATS_IDENTITY_OVERRIDES_PATH
from .corpus import artifact_alias_map, exact_artifact_key
from .model_cards import DEFAULT_REGISTRY_PATH
from .paper_institutions import SHOWN_INSTITUTIONS, arxiv_id
from .release_kind import is_benchmark_release
from .release_signals import ReleaseSignals

METHOD_VERSION = "attention-ranking-v1"
# Issue #1120: the default once release signals are loaded. Attention keeps its
# internal split, scaled to 80%; the affiliation signal (affiliation_rank.py)
# adds 20%. Unknown affiliation contributes nothing and is not redistributed.
COMBINED_METHOD_VERSION = "attention-affiliation-v2"
AFFILIATION_WEIGHT = 0.20
MIN_OBSERVED_WEIGHT_RANK = 0.45
DEFAULT_TOP_LIMIT = 10

# One-line release summary (issue #348). A release row answers one question —
# what does this benchmark measure, and for whom — in a single scannable
# line, or it says nothing. The line is extractive, never generated: it is
# the first sentence of the source record's own summary, so a line can only
# state what the source already stated. No API call, no cache, nothing to
# regenerate: the same record always yields the same line.
ONE_LINE_SUMMARY_MAX_CHARS = 140
# Box-drawing and block characters: one release's summary was a run of "═══"
# that pushed a 720px column to 1349px (issue #333). They carry no meaning
# here, so they are stripped rather than escaped around.
_ONE_LINE_STRIP_RANGES = ((0x2500, 0x259F),)
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s+[A-Z0-9\"'(\[]|\s*$)")


def one_line_summary(value: Any) -> str:
    """Derive a release row's one-line summary from the record's own text.

    Takes the first sentence of ``value`` (the source record's summary),
    capped at :data:`ONE_LINE_SUMMARY_MAX_CHARS` characters. Whitespace
    controls become spaces and other control and box-drawing characters
    are stripped, so nothing in the line can break the column. Returns
    ``""`` when the record carries nothing usable: a
    release with nothing to summarise keeps an honest empty state instead
    of a manufactured line.
    """
    if not isinstance(value, str):
        return ""
    # Whitespace controls (\n, \t, \r, ...) separate words: turn them into
    # spaces first, so "OBJECTIVE\nThis..." does not become
    # "OBJECTIVEThis...". Every other control character is dropped.
    spaced = "".join(
        " " if char.isspace() and unicodedata.category(char) in ("Cc", "Zl", "Zp") else char
        for char in value
    )
    cleaned = "".join(
        char
        for char in spaced
        if unicodedata.category(char) not in ("Cc", "Cf", "Zl", "Zp")
        and not any(start <= ord(char) <= end for start, end in _ONE_LINE_STRIP_RANGES)
    )
    text = " ".join(cleaned.split())
    if not text:
        return ""
    match = _SENTENCE_END_RE.search(text)
    if match:
        text = text[: match.end()]
    if len(text) <= ONE_LINE_SUMMARY_MAX_CHARS:
        return text
    cut = text.rfind(" ", 0, ONE_LINE_SUMMARY_MAX_CHARS - 1)
    if cut <= 0:
        return text[: ONE_LINE_SUMMARY_MAX_CHARS - 1] + "…"
    return text[:cut] + "…"


WINDOW_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}

WINDOW_WEIGHTS: dict[str, float] = {
    "github_stars": 0.55,
    "hf_paper_upvotes": 0.30,
    "hf_dataset_downloads": 0.15,
}

DURABLE_SIGNALS: frozenset[str] = frozenset({"github_stars", "hf_dataset_downloads"})

METRIC_ALIASES: dict[str, str] = {
    "stars": "github_stars",
    "github_stars": "github_stars",
    "paper_upvotes": "hf_paper_upvotes",
    "hf_paper_upvotes": "hf_paper_upvotes",
    "upvotes": "hf_paper_upvotes",
    "downloads": "hf_dataset_downloads",
    "downloads_30d": "hf_dataset_downloads",
    "hf_dataset_downloads": "hf_dataset_downloads",
}

SIGNAL_SOURCES: dict[str, str] = {
    "github_stars": "github",
    "hf_paper_upvotes": "huggingface",
    "hf_dataset_downloads": "huggingface",
}

SIGNAL_VALUE_KINDS: dict[str, str] = {
    "github_stars": "cumulative",
    "hf_paper_upvotes": "cumulative",
    "hf_dataset_downloads": "rolling_30d",
}


def _parse_utc_datetime(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    if not value:
        return fallback
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    try:
        cleaned = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return fallback


def is_dedicated_benchmark_repo(url: str | None) -> bool:
    """Check if URL points to a dedicated GitHub repository rather than a subdirectory/tree."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if re.search(r"github\.com/[^/]+/[^/]+/(?:tree|blob)/", url, re.I):
        return False
    match = re.search(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)", url, re.I)
    if not match:
        return False
    # Split the same way the match above was made: case-insensitively. A
    # capitalised "GitHub.com/..." matched the regex and then found nothing to
    # split on, raising IndexError. That was survivable while only the
    # leaderboard build called this, but the attention collector now calls it
    # inside run_pipeline, where one such link in historical evidence would
    # abort the whole daily run.
    path_suffix = re.split(r"github\.com/", url, maxsplit=1, flags=re.I)[1]
    path_suffix = path_suffix.split("?")[0].split("#")[0].strip("/")
    parts = [p for p in path_suffix.split("/") if p]
    return len(parts) == 2


def is_exact_attention_source_url(signal: str, url: str | None) -> bool:
    """Whether a metric URL names the exact resource required by Ranking v1."""
    if not isinstance(url, str) or not url.strip():
        return False
    if signal == "github_stars":
        return is_dedicated_benchmark_repo(url)

    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.casefold().removeprefix("www.")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host != "huggingface.co":
        return False
    if signal == "hf_paper_upvotes":
        return len(segments) == 2 and segments[0].casefold() == "papers"
    if signal == "hf_dataset_downloads":
        return len(segments) == 3 and segments[0].casefold() == "datasets"
    return False


def normalize_log1p(value: int | float | None, window_max: int | float | None) -> float | None:
    """Log-max normalized value: log1p(val) / log1p(window_max)."""
    if value is None:
        return None
    val_float = max(0.0, float(value))
    if window_max is None or window_max <= 0:
        return 0.0
    max_float = max(0.0, float(window_max))
    if max_float == 0.0:
        return 0.0
    return min(1.0, math.log1p(val_float) / math.log1p(max_float))


def load_reviewed_benchmark_identifiers(
    *,
    registry_path: Path | None = None,
    identity_path: Path | None = None,
    overrides_path: Path | None = None,
) -> set[str]:
    """Load canonical identifiers of hand-reviewed benchmarks from repo layers."""
    reviewed: set[str] = set()

    mc_path = registry_path or DEFAULT_REGISTRY_PATH
    if mc_path and mc_path.exists():
        try:
            data = yaml.safe_load(mc_path.read_text(encoding="utf-8")) or {}
            for b in data.get("benchmarks", []):
                if b.get("id"):
                    reviewed.add(str(b["id"]))
                if b.get("name"):
                    reviewed.add(str(b["name"]).lower())
                for a in b.get("aliases", []):
                    if a:
                        reviewed.add(str(a).lower())
                if b.get("url"):
                    key = exact_artifact_key({"url": b["url"]})
                    if key:
                        reviewed.add(key)
        except Exception:
            pass

    id_path = identity_path or DEFAULT_IDENTITY_PATH
    if id_path and id_path.exists():
        try:
            data = yaml.safe_load(id_path.read_text(encoding="utf-8")) or {}
            for group in data.get("equivalent", []):
                if group.get("group_id"):
                    reviewed.add(str(group["group_id"]))
                for m in group.get("members", []):
                    if m:
                        m_str = str(m)
                        reviewed.add(m_str)
                        if m_str.startswith("http"):
                            reviewed.add(exact_artifact_key({"url": m_str}))
                for a in group.get("anchors", []):
                    if a:
                        a_str = str(a)
                        reviewed.add(a_str)
                        reviewed.add(f"artifact:{a_str}")
                        if a_str.startswith("gh:"):
                            reviewed.add(f"artifact:github:{a_str[3:]}")
                        elif a_str.startswith("arxiv:"):
                            reviewed.add(f"artifact:arxiv:{a_str[6:]}")
                        elif a_str.startswith("hf:"):
                            reviewed.add(f"artifact:huggingface:{a_str[3:]}")
        except Exception:
            pass

    ov_path = overrides_path or DEFAULT_LLM_STATS_IDENTITY_OVERRIDES_PATH
    if ov_path and ov_path.exists():
        try:
            data = yaml.safe_load(ov_path.read_text(encoding="utf-8")) or {}
            b_dict = data.get("benchmarks", {})
            if isinstance(b_dict, dict):
                for k, v in b_dict.items():
                    if isinstance(v, dict) and v.get("resolution_status") == "resolved":
                        reviewed.add(str(k))
                        for url_key in ("repo_url", "paper_url", "dataset_url"):
                            u = v.get(url_key)
                            if u:
                                key = exact_artifact_key({"url": u})
                                if key:
                                    reviewed.add(key)
        except Exception:
            pass

    return reviewed


def canonical_metric_key(metric: str | None) -> str | None:
    return METRIC_ALIASES.get(metric or "")


def _obs_time(obs: dict[str, Any], snap: dict[str, Any]) -> datetime:
    t = (
        obs.get("observed_at")
        or (snap.get("benchmark_attention") or {}).get("observed_at")
        or snap.get("generated_at")
        or snap.get("date")
    )
    return _parse_utc_datetime(t) or datetime.min.replace(tzinfo=UTC)


def _is_reviewed_entity(
    canonical_id: str,
    name: str,
    occurrences: list[tuple[dict[str, Any], dict[str, Any]]],
    reviewed_ids: set[str] | None,
) -> bool:
    if not reviewed_ids:
        return False
    if canonical_id in reviewed_ids or name.lower() in reviewed_ids:
        return True
    for item, _ in occurrences:
        if exact_artifact_key(item) in reviewed_ids:
            return True
        u = item.get("url")
        if u and exact_artifact_key({"url": u}) in reviewed_ids:
            return True
        for au in item.get("artifact_urls") or []:
            if au and exact_artifact_key({"url": au}) in reviewed_ids:
                return True
    return False


FALLBACK_METRIC_CONFIG = {
    "github_stars": ("github.com", "stars", is_dedicated_benchmark_repo),
    "hf_paper_upvotes": ("huggingface.co", "upvotes", None),
    "hf_dataset_downloads": ("huggingface.co/datasets", "downloads", None),
}


def _extract_fallback_metric(
    key: str,
    occurrences: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    domain_substring, metric_field, validator = FALLBACK_METRIC_CONFIG[key]
    newest_first = sorted(
        occurrences,
        key=lambda pair: (
            _parse_utc_datetime(pair[1].get("generated_at")) or datetime.min.replace(tzinfo=UTC)
        ),
        reverse=True,
    )
    for item, snap in newest_first:
        metrics = item.get("metrics") or {}
        if metric_field not in metrics or metrics[metric_field] is None:
            continue
        urls = [item.get("url"), *(item.get("artifact_urls") or [])]
        matched_url = next(
            (u for u in urls if u and isinstance(u, str) and domain_substring in u.lower()),
            None,
        )
        if not matched_url:
            continue
        if validator and not validator(matched_url):
            continue
        return {
            "value": metrics[metric_field],
            # Connector counters predate the source-health-aware attention
            # contract. Keep them visible for audit, but never promote them to
            # fresh merely because the benchmark identity was reviewed.
            "status": "unknown",
            "last_successful_date": str(snap.get("date") or "") or None,
            "source_url": matched_url,
        }
    return {"value": None, "status": "unknown", "source_url": None}


def _resolve_attention_metric(
    key: str,
    observations: list[tuple[dict[str, Any], dict[str, Any]]],
    health_events: list[tuple[datetime, bool]],
) -> dict[str, Any]:
    """Resolve metric value from snapshot benchmark_attention using latest source status."""
    observations.sort(key=lambda pair: _obs_time(pair[0], pair[1]))

    last_val = None
    last_date = None
    last_url = None

    for obs, snap in observations:
        val = obs.get("value")
        st = obs.get("status", "fresh")
        if val is not None and st in {"fresh", "stale"}:
            last_val = val
            obs_dt = _obs_time(obs, snap)
            last_date = obs.get("last_successful_date") or (
                obs_dt.date().isoformat() if obs_dt > datetime.min.replace(tzinfo=UTC) else None
            )
            last_url = obs.get("source_url")

    latest_obs, _ = observations[-1]
    latest_st = latest_obs.get("status", "fresh")
    latest_val = latest_obs.get("value")
    url = latest_obs.get("source_url") or last_url

    if not is_exact_attention_source_url(key, url):
        return {"value": None, "status": "unknown", "source_url": None}

    latest_obs_time = _obs_time(latest_obs, observations[-1][1])
    later_failed_health = any(
        event_time >= latest_obs_time and not ok for event_time, ok in health_events
    )

    if latest_st == "fresh" and latest_val is not None and not later_failed_health:
        return {"value": latest_val, "status": "fresh", "source_url": url}

    if (
        latest_st in {"unavailable", "stale"} or latest_val is None or later_failed_health
    ) and last_val is not None:
        return {
            "value": last_val,
            "status": "stale",
            "last_successful_date": str(last_date),
            "source_url": url,
        }

    status = latest_st if latest_st in {"unavailable", "stale"} else "unknown"
    return {"value": None, "status": status, "source_url": url}


def _resolve_signals(
    ba_obs_pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    occurrences: list[tuple[dict[str, Any], dict[str, Any]]],
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    signals = {}
    for key in WINDOW_WEIGHTS:
        key_obs = [
            pair for pair in ba_obs_pairs if canonical_metric_key(pair[0].get("metric")) == key
        ]
        if key_obs:
            health_events = []
            expected_source = SIGNAL_SOURCES[key]
            for snap in snapshots:
                block = snap.get("benchmark_attention") or {}
                event_time = _parse_utc_datetime(block.get("observed_at")) or _parse_utc_datetime(
                    snap.get("generated_at")
                )
                if event_time is None:
                    continue
                for health in block.get("health", []):
                    health_metric = health.get("metric")
                    if health.get("source") != expected_source:
                        continue
                    if health_metric is not None and canonical_metric_key(health_metric) != key:
                        continue
                    health_events.append((event_time, health.get("ok") is True))
            signals[key] = _resolve_attention_metric(key, key_obs, health_events)
        else:
            signals[key] = _extract_fallback_metric(key, occurrences)
    return signals


def filter_release_cohort(
    snapshots: list[dict[str, Any]],
    *,
    window_days: int,
    as_of: datetime | str | None = None,
    registry_path: Path | None = None,
    reviewed_benchmark_ids: set[str] | None = None,
    aliases: dict[str, str] | None = None,
    include_unconfirmed: bool = False,
) -> list[dict[str, Any]]:
    """Filter canonical entities released within the UTC window [as_of - window_days, as_of]."""
    if not snapshots:
        return []

    latest_snapshot = snapshots[-1]
    as_of_dt = (
        _parse_utc_datetime(as_of)
        or _parse_utc_datetime(latest_snapshot.get("generated_at"))
        or datetime.now(UTC)
    )
    window_start_dt = as_of_dt - timedelta(days=window_days)

    if reviewed_benchmark_ids is None:
        reviewed_benchmark_ids = load_reviewed_benchmark_identifiers(registry_path=registry_path)

    if aliases is None:
        all_evidence = [item for snap in snapshots for item in snap.get("evidence_items", [])]
        aliases = artifact_alias_map(all_evidence)

    attention_by_canonical: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for snap in snapshots:
        for obs in (snap.get("benchmark_attention") or {}).get("observations", []):
            cid = obs.get("canonical_artifact_id")
            if cid:
                canonical_id = aliases.get(str(cid), str(cid))
                attention_by_canonical.setdefault(canonical_id, []).append((obs, snap))

    items_by_canonical: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for snap in snapshots:
        for item in snap.get("evidence_items", []):
            key = exact_artifact_key(item)
            cid = aliases.get(key, key)
            items_by_canonical.setdefault(cid, []).append((item, snap))

    cohort = []
    for canonical_id, occurrences in items_by_canonical.items():
        release_dates = []
        for item, snap in occurrences:
            # A model, a method, an agent, a harness, or a software version tag
            # is a release of something, but not of a benchmark. It stays in the
            # corpus; it just does not open a Latest releases entry
            # (issues #902 and #961).
            if item.get("event_kind") == "released" and is_benchmark_release(item):
                ts = (
                    item.get("published_at")
                    or item.get("discovered_at")
                    or snap.get("generated_at")
                )
                dt = _parse_utc_datetime(ts)
                if dt:
                    release_dates.append((dt, item))

        if not release_dates:
            continue

        release_dates.sort(key=lambda pair: pair[0])
        earliest_dt, primary_item = release_dates[0]
        if not (window_start_dt <= earliest_dt <= as_of_dt):
            continue

        # A later snapshot can enrich a record whose earliest occurrence
        # has no summary (blanca-pueche/benchmark-complex-prediction:
        # empty on 2026-10-08, substantive on 2026-10-09). Keep the
        # earliest occurrence for the release date, but take the summary
        # from the first occurrence that has one.
        purpose_item = next(
            (item for _, item in release_dates if one_line_summary(item.get("summary"))),
            primary_item,
        )

        name = primary_item.get("title") or primary_item.get("source_id") or canonical_id
        is_reviewed = _is_reviewed_entity(canonical_id, name, occurrences, reviewed_benchmark_ids)
        ba_obs = attention_by_canonical.get(canonical_id, [])
        has_attention = bool(ba_obs)

        # Unconfirmed keyword discoveries without dated attention or reviewed status are excluded
        if not include_unconfirmed and not (has_attention or is_reviewed):
            continue

        cohort.append(
            {
                "canonical_artifact_id": canonical_id,
                "name": name,
                # One line from the record's own summary (issue #348). No
                # fallback to the title — the row already shows it — and no
                # manufactured "Benchmark and evaluation suite": a record
                # with nothing to summarise keeps an honest empty purpose,
                # which the row renders as an explicit empty state.
                "purpose": one_line_summary(purpose_item.get("summary")),
                "release_date": earliest_dt.isoformat(),
                "has_dated_attention": has_attention,
                "is_reviewed_benchmark": is_reviewed,
                "signals": _resolve_signals(ba_obs, occurrences, snapshots),
            }
        )

    return cohort


def compute_window_ranking(
    candidates: list[dict[str, Any]],
    *,
    window_days: int,
    top_limit: int | None = DEFAULT_TOP_LIMIT,
    affiliation_weight: float | None = None,
) -> dict[str, Any]:
    """Rank candidates for a window.

    Without ``affiliation_weight`` this is Ranking v1. With it, every attention
    weight is scaled by ``1 - affiliation_weight`` and a candidate's
    ``affiliation`` (0 to 1, or None for unknown) adds the rest. The rank
    threshold still reads attention alone: affiliation never qualifies a
    release by itself. A placeholder, archived or gone repository keeps the release listed, but
    unranked.
    """
    scale = 1.0 - (affiliation_weight or 0.0)
    window_maxes = {
        signal: max(
            [
                float(c["signals"][signal]["value"])
                for c in candidates
                if c.get("signals", {}).get(signal, {}).get("value") is not None
                and c.get("signals", {}).get(signal, {}).get("status") == "fresh"
                # A held-back release is unranked; it must not set the scale
                # the ranked releases are normalized against either.
                and not _held_back(c)
            ]
            or [0.0]
        )
        for signal in WINDOW_WEIGHTS
    }

    scored_entries = []
    for c in candidates:
        coverage = 0.0
        fresh_weight = 0.0
        observed_count = 0
        fresh_count = 0
        composite_score = 0.0
        components = {}
        has_durable = False

        for signal, weight in WINDOW_WEIGHTS.items():
            sig = c.get("signals", {}).get(signal, {})
            val = sig.get("value")
            status = sig.get("status", "unknown")
            norm = normalize_log1p(val, window_maxes[signal])

            entry = {
                "value": val,
                "normalized": norm,
                "weight": round(weight * scale, 4),
                "status": status,
                "source_url": sig.get("source_url"),
            }
            if sig.get("last_successful_date"):
                entry["last_successful_date"] = sig["last_successful_date"]
            components[signal] = entry

            if norm is not None:
                coverage += weight * scale
                observed_count += 1
                if status == "fresh":
                    composite_score += weight * scale * norm
                    fresh_count += 1
                    fresh_weight += weight
                    if signal in DURABLE_SIGNALS:
                        has_durable = True

        if affiliation_weight is not None:
            affiliation = c.get("affiliation")
            components["affiliation"] = {
                "value": c.get("affiliation_paper_count"),
                "institution": c.get("affiliation_institution"),
                "normalized": affiliation,
                "weight": affiliation_weight,
                "status": "fresh" if affiliation is not None else "unknown",
                "source_url": c.get("institutions_source_url"),
            }
            if affiliation is not None:
                # An observed signal like any other for the confidence tag.
                observed_count += 1
                coverage += affiliation_weight
                composite_score += affiliation_weight * affiliation

        raw_score = 100.0 * composite_score if fresh_count > 0 else None
        score = round(raw_score + 1e-9) if raw_score is not None else None
        coverage_rnd = round(coverage, 2)
        confidence = (
            "High"
            if coverage_rnd >= 0.75 and observed_count >= 2
            else "Medium"
            if coverage_rnd >= 0.40 and observed_count >= 2
            else "Low"
        )

        is_eligible = bool(c.get("has_dated_attention") or c.get("is_reviewed_benchmark"))
        if "has_dated_attention" not in c and "is_reviewed_benchmark" not in c:
            is_eligible = c.get("is_eligible", True)

        sufficient_weight = round(fresh_weight, 4) >= MIN_OBSERVED_WEIGHT_RANK or fresh_weight >= (
            MIN_OBSERVED_WEIGHT_RANK - 1e-9
        )
        held_back = _held_back(c)
        qualifies = (
            is_eligible and has_durable and sufficient_weight and score is not None
        ) and not held_back

        extra: dict[str, Any] = {}
        if c.get("institutions"):
            extra["institutions"] = c["institutions"]
            extra["institutions_basis"] = c.get("institutions_basis")
            extra["institutions_source_url"] = c.get("institutions_source_url")
        if held_back:
            extra["limited_reason"] = held_back

        scored_entries.append(
            {
                "canonical_artifact_id": c["canonical_artifact_id"],
                "name": c["name"],
                "purpose": c.get("purpose", ""),
                "release_date": c["release_date"],
                "score": score,
                "coverage": coverage_rnd,
                "confidence": confidence,
                "status": "ranked" if qualifies else "limited_signals",
                "rank": None,
                "components": components,
                **extra,
                "_ranking_score": raw_score,
            }
        )

    def _ts(e: dict[str, Any]) -> float:
        dt = _parse_utc_datetime(e.get("release_date"))
        return (dt or datetime.min.replace(tzinfo=UTC)).timestamp()

    ranked = [e for e in scored_entries if e["status"] == "ranked"]
    unranked = [e for e in scored_entries if e["status"] != "ranked"]

    ranked.sort(key=lambda e: (-(e["_ranking_score"] or 0), -_ts(e), e.get("name", "")))
    for idx, e in enumerate(ranked, start=1):
        e["rank"] = idx

    unranked.sort(
        key=lambda e: (
            -(e["_ranking_score"] if e["_ranking_score"] is not None else -1),
            -_ts(e),
            e.get("name", ""),
        )
    )

    all_entries = ranked + unranked
    for entry in all_entries:
        entry.pop("_ranking_score", None)
    visible = all_entries[:top_limit] if top_limit is not None else all_entries
    avg_cov = (
        round(sum(e["coverage"] for e in all_entries) / len(all_entries), 2) if all_entries else 0.0
    )

    return {
        "window_days": window_days,
        "ranked_count": len(ranked),
        "total_cohort_count": len(all_entries),
        "signal_coverage": avg_cov,
        "entries": visible,
    }


def build_latest_releases_leaderboard(
    snapshots: list[dict[str, Any]],
    *,
    as_of: datetime | str | None = None,
    registry_path: Path | None = None,
    reviewed_benchmark_ids: set[str] | None = None,
    include_unconfirmed: bool = False,
    top_limit: int | None = DEFAULT_TOP_LIMIT,
    signals: ReleaseSignals | None = None,
    institution_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build the full multi-window latest releases leaderboard for radar.json.

    ``signals`` (release_signals.py) switches the ranking to
    ``attention-affiliation-v2``, attaches each paper's first three
    institutions, and holds back placeholder, archived and gone repositories. Without it the payload
    is Ranking v1 exactly.
    """
    if not snapshots:
        return {
            "schema_version": 1,
            "method_version": METHOD_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "default_window": "30d",
            "windows": {},
        }

    latest = snapshots[-1]
    fallback_dt = _parse_utc_datetime(latest.get("generated_at")) or datetime.now(UTC)
    as_of_dt = _parse_utc_datetime(as_of) or fallback_dt

    if reviewed_benchmark_ids is None:
        reviewed_benchmark_ids = load_reviewed_benchmark_identifiers(registry_path=registry_path)

    all_evidence = [item for snap in snapshots for item in snap.get("evidence_items", [])]
    shared_aliases = artifact_alias_map(all_evidence)
    papers_by_canonical = _papers_by_canonical(shared_aliases) if signals is not None else {}
    counts = dict(institution_counts or {})
    weights = institution_weights(counts)

    windows_data: dict[str, Any] = {}
    for window_key, days in WINDOW_DAYS.items():
        cohort = filter_release_cohort(
            snapshots,
            window_days=days,
            as_of=as_of_dt,
            registry_path=registry_path,
            reviewed_benchmark_ids=reviewed_benchmark_ids,
            aliases=shared_aliases,
            include_unconfirmed=include_unconfirmed,
        )
        if signals is not None:
            for candidate in cohort:
                _attach_release_signals(candidate, signals, counts, weights, papers_by_canonical)
        ranking = compute_window_ranking(
            cohort,
            window_days=days,
            top_limit=top_limit,
            affiliation_weight=AFFILIATION_WEIGHT if signals is not None else None,
        )
        window_start = (as_of_dt - timedelta(days=days)).isoformat()
        windows_data[window_key] = {
            "window_start": window_start,
            "window_end": as_of_dt.isoformat(),
            **ranking,
        }

    return {
        "schema_version": 1,
        "method_version": COMBINED_METHOD_VERSION if signals is not None else METHOD_VERSION,
        "generated_at": as_of_dt.isoformat(),
        "default_window": "30d",
        "windows": windows_data,
    }


def _held_back(candidate: dict[str, Any]) -> str | None:
    """Why a candidate is listed but not ranked: placeholder, archived or gone."""
    if candidate.get("held_back"):
        return str(candidate["held_back"])
    return "placeholder_repository" if candidate.get("placeholder_repository") else None


def _papers_by_canonical(aliases: dict[str, str]) -> dict[str, str]:
    """The arXiv paper each canonical release is linked to through its aliases."""
    papers: dict[str, str] = {}
    for key, canonical in [*aliases.items(), *((c, c) for c in aliases.values())]:
        paper = arxiv_id(key)
        if paper:
            papers.setdefault(canonical, paper)
    return papers


def release_signal_targets(
    snapshots: list[dict[str, Any]],
    *,
    as_of: datetime | str | None = None,
    registry_path: Path | None = None,
) -> tuple[set[str], set[str]]:
    """arXiv papers and GitHub star URLs of the widest window's cohort.

    ``scripts/fetch_release_signals.py`` looks these up, so the build that
    reads the files finds an entry for every release it ranks.
    """
    if not snapshots:
        return set(), set()
    all_evidence = [item for snap in snapshots for item in snap.get("evidence_items", [])]
    aliases = artifact_alias_map(all_evidence)
    papers_by_canonical = _papers_by_canonical(aliases)
    as_of_dt = (
        _parse_utc_datetime(as_of)
        or _parse_utc_datetime(snapshots[-1].get("generated_at"))
        or datetime.now(UTC)
    )
    cohort = filter_release_cohort(
        snapshots,
        window_days=max(WINDOW_DAYS.values()),
        as_of=as_of_dt,
        registry_path=registry_path,
        aliases=aliases,
    )
    papers, repos = set(), set()
    for candidate in cohort:
        canonical = candidate["canonical_artifact_id"]
        paper = papers_by_canonical.get(canonical) or arxiv_id(canonical)
        if paper:
            papers.add(paper)
        url = (candidate.get("signals", {}).get("github_stars") or {}).get("source_url")
        if url:
            repos.add(str(url))
    return papers, repos


def _attach_release_signals(
    candidate: dict[str, Any],
    signals: ReleaseSignals,
    counts: dict[str, int],
    weights: dict[str, float],
    papers_by_canonical: dict[str, str],
) -> None:
    """Add institutions, affiliation and the hold-back reason to one candidate."""
    canonical = candidate["canonical_artifact_id"]
    paper = papers_by_canonical.get(canonical) or arxiv_id(canonical)
    row = signals.paper(paper)
    if row and row.get("institutions"):
        names = [str(name) for name in row["institutions"]]
        candidate["institutions"] = names[:SHOWN_INSTITUTIONS]
        candidate["institutions_basis"] = row.get("basis")
        candidate["institutions_source_url"] = row.get("source_url")
        # A paper OpenAlex has not indexed yet is scored on the names it
        # prints that exactly match a counted OpenAlex name; never fuzzily.
        candidate["affiliation"] = affiliation_normalized(names, weights)
        best = best_institution(names, weights)
        if best:
            # The input a reader can check: which institution, on how many papers.
            candidate["affiliation_institution"] = best
            candidate["affiliation_paper_count"] = counts[best]
    stars_url = (candidate.get("signals", {}).get("github_stars") or {}).get("source_url")
    reason = signals.held_back(stars_url)
    if reason:
        candidate["held_back"] = reason
