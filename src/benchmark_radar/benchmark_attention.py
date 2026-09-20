"""Dated, attributable public counters for recently released benchmarks.

The Latest Releases leaderboard (`release_leaderboard.py`) ranks a release by
GitHub stars, Hugging Face paper upvotes and Hugging Face dataset downloads.
It reads them from the `benchmark_attention` block of each daily snapshot,
whose shape `snapshots.py` validates. The ranking engine, its validator and
its tests landed for issue #530 before anything wrote that block, so every
window collapsed to hand-reviewed registry entries carrying `unknown`
signals, which issue #589 reports as "stars 0, forks 0". This module is the
collector that fills the block.

Each rule below prevents a specific failure:

- Only an exact resource is queried: a dedicated GitHub repository, a
  Hugging Face paper page, a Hugging Face dataset page. A repository that
  hosts a benchmark in a subdirectory would credit the host's stars to the
  benchmark; the validator refuses such URLs and so does the selection here.
- A resource the API says is gone is recorded as `unavailable` with a null
  value, never as zero. The ranking treats null as "no signal"; a zero would
  rank a deleted repository below a live one with a single star.
- A request that fails for a reason about the request (rate limit, outage,
  malformed payload) produces no reading. The resource's last reading from
  the previous snapshot is written again as `stale`, dated by the day it was
  read, because the ranking reports whatever the newest observation says:
  writing nothing would leave yesterday's reading reported as fresh.
- Health is reported per (source, metric), so a paper-page outage cannot mark
  dataset downloads stale. `ok` stays true while any request succeeded: the
  ranking reads a failed health event at the same instant as fresh
  observations as a reason to demote all of them to stale.
- Requests are bounded per source and spent newest release first, so the
  windows the leaderboard shows by default are refreshed before the 90-day
  tail, and a budget smaller than the eligible cohort degrades to stale
  readings on the oldest releases rather than to nothing.
- A source that fails several times in a row is not asked again this run.
  A rate limit or outage answers every request the same way, and a run that
  waits out the timeout for each of a thousand resources would outlive the
  daily workflow; the resources not asked keep their stale readings.
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from .corpus import artifact_alias_map, exact_artifact_key
from .http import RequestError, get_json
from .models import SourceHealth
from .release_leaderboard import canonical_metric_key, is_exact_attention_source_url
from .sources import ConnectorPayloadError, _github_headers, _request_options

BLOCK_SCHEMA_VERSION = 1
DEFAULT_WINDOW_DAYS = 90
DEFAULT_MAX_REQUESTS = {"github": 800, "huggingface": 1200}
DEFAULT_REQUEST_DELAY_SECONDS = {"github": 0.0, "huggingface": 0.1}
DEFAULT_MAX_CONSECUTIVE_FAILURES = 5

# One row per ranking signal: the snapshot source and metric names the
# validator accepts, the counter kind the ranking expects, and the label the
# dashboard's source-health list shows.
SIGNALS: dict[str, dict[str, str]] = {
    "github_stars": {
        "source": "github",
        "metric": "stars",
        "value_kind": "cumulative",
        "label": "GitHub stars",
    },
    "hf_paper_upvotes": {
        "source": "huggingface",
        "metric": "upvotes",
        "value_kind": "cumulative",
        "label": "Hugging Face paper upvotes",
    },
    "hf_dataset_downloads": {
        "source": "huggingface",
        "metric": "downloads_30d",
        "value_kind": "rolling_30d",
        "label": "Hugging Face dataset downloads",
    },
}

# Statuses that describe the artifact rather than the request: the resource is
# gone (or legally withheld), so the honest reading is "unavailable", not a
# retry later.
_MISSING_RESOURCE_STATUSES = {404, 410, 451}


@dataclass(slots=True)
class AttentionTarget:
    canonical_id: str
    released_at: datetime | None = None
    resources: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class _SignalStats:
    attempted: int = 0
    observed: int = 0
    unavailable: int = 0
    failed: int = 0
    skipped: int = 0
    stale: int = 0
    last_error: str | None = None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def select_targets(
    items: list[dict[str, Any]],
    *,
    as_of: datetime,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[AttentionTarget]:
    """Released artifacts inside the window that name at least one exact resource.

    Identity follows the ranking's own rule: occurrences are grouped by the
    alias-mapped exact artifact key, and the release date is the earliest
    `released` observation, so a re-announcement cannot move a benchmark back
    into a window it has left. Resources are gathered from every occurrence,
    since the repository URL of a paper released without one often arrives
    later on the repository's own `updated` record. Artifacts released outside
    the window, never released, or naming no exact resource produce no
    target: there is nothing to observe for them, and a null observation
    would admit them to the cohort with no signal to rank on.
    """
    as_of = as_of.astimezone(UTC)
    window_start = as_of - timedelta(days=window_days)
    aliases = artifact_alias_map(items)
    grouped: dict[str, AttentionTarget] = {}
    for item in items:
        key = exact_artifact_key(item)
        canonical_id = aliases.get(key, key)
        target = grouped.get(canonical_id)
        if target is None:
            target = AttentionTarget(canonical_id=canonical_id)
            grouped[canonical_id] = target
        if item.get("event_kind") == "released":
            released = _parse_time(item.get("published_at") or item.get("discovered_at"))
            if released is not None and (
                target.released_at is None or released < target.released_at
            ):
                target.released_at = released
        urls = [item.get("url"), *(item.get("artifact_urls") or [])]
        for url in urls:
            if not isinstance(url, str):
                continue
            for signal in SIGNALS:
                if signal not in target.resources and is_exact_attention_source_url(signal, url):
                    target.resources[signal] = url.strip()
    selected = [
        target
        for target in grouped.values()
        if target.resources
        and target.released_at is not None
        and window_start <= target.released_at <= as_of
    ]
    selected.sort(key=lambda target: (target.released_at, target.canonical_id), reverse=True)
    return selected


def _http_status(error: Exception) -> int | None:
    match = re.match(r"HTTP (\d{3}) ", str(error))
    return int(match.group(1)) if match else None


def _counter(payload: Any, field_name: str, *, label: str) -> int | float:
    if not isinstance(payload, dict):
        raise ConnectorPayloadError(f"{label} metadata was not an object")
    raw = payload.get(field_name)
    if raw is None or isinstance(raw, bool):
        raise ConnectorPayloadError(f"{label} metadata is missing {field_name}")
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ConnectorPayloadError(f"{label} {field_name} is not a number") from error
    if not math.isfinite(value) or value < 0:
        raise ConnectorPayloadError(f"{label} {field_name} is not a non-negative number")
    # Counters are whole numbers; keep them so in the snapshot and the
    # dashboard rather than serialising 150 as 150.0.
    return int(value) if value.is_integer() else value


def _fetch_counter(
    signal: str,
    url: str,
    *,
    options: dict[str, Any],
    get_json: Callable[..., Any],
) -> int | float:
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    if signal == "github_stars":
        # A clone URL is an exact reference to the same repository, and the
        # exactness rule accepts it, but api.github.com has no repository whose
        # name ends in `.git`: the request 404s and a live repository would be
        # recorded as `unavailable`, which is the misreading this module exists
        # to prevent. The untouched URL is still what `source_url` reports.
        owner, repo = segments[0], segments[1].removesuffix(".git")
        payload = get_json(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=_github_headers(),
            **options,
        )
        return _counter(payload, "stargazers_count", label="GitHub repository")
    if signal == "hf_paper_upvotes":
        payload = get_json(f"https://huggingface.co/api/papers/{segments[1]}", **options)
        return _counter(payload, "upvotes", label="Hugging Face paper")
    if signal == "hf_dataset_downloads":
        # The Hub's `downloads` counter is the rolling 30-day figure the
        # ranking weights; the all-time counter is a different measure and is
        # only served on request.
        payload = get_json(
            f"https://huggingface.co/api/datasets/{segments[1]}/{segments[2]}", **options
        )
        return _counter(payload, "downloads", label="Hugging Face dataset")
    raise ValueError(f"unknown attention signal {signal!r}")


def _read_resource(
    signal: str,
    url: str,
    *,
    options: dict[str, Any],
    get_json: Callable[..., Any],
    stats: _SignalStats,
) -> tuple[int | float | None, str] | None:
    """One reading, or None when the request (not the artifact) failed.

    A gone resource is a fact about the artifact and becomes an `unavailable`
    reading. Anything else that goes wrong (a rate limit, an outage, a payload
    that is not JSON or lacks the counter) is a fact about the request: it is
    counted against the signal's health and produces no reading, so the
    resource keeps its last one. No exception escapes, because one unreadable
    resource must not abort the readings of the hundreds after it.
    """
    stats.attempted += 1
    try:
        value = _fetch_counter(signal, url, options=options, get_json=get_json)
    except RequestError as error:
        if _http_status(error) in _MISSING_RESOURCE_STATUSES:
            stats.unavailable += 1
            return (None, "unavailable")
        stats.failed += 1
        stats.last_error = f"{type(error).__name__}: {error}"
        return None
    except Exception as error:
        stats.failed += 1
        stats.last_error = f"{type(error).__name__}: {error}"
        return None
    stats.observed += 1
    return (value, "fresh")


def _previous_readings(block: dict[str, Any] | None) -> dict[tuple[str, str], tuple[Any, str]]:
    """The last known value per (signal, resource URL) and the date it was read.

    Keyed by resource rather than artifact: alias links can rename an
    artifact's canonical id between runs, the URL cannot change.
    """
    readings: dict[tuple[str, str], tuple[Any, str]] = {}
    if not block:
        return readings
    block_time = _parse_time(block.get("observed_at"))
    for observation in block.get("observations") or []:
        if not isinstance(observation, dict):
            continue
        signal = canonical_metric_key(observation.get("metric"))
        value = observation.get("value")
        if (
            signal is None
            or observation.get("status") not in {"fresh", "stale"}
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            continue
        read_at = observation.get("last_successful_date")
        if not read_at:
            read_time = _parse_time(observation.get("observed_at")) or block_time
            if read_time is None:
                continue
            read_at = read_time.date().isoformat()
        readings[(signal, str(observation.get("source_url") or ""))] = (value, str(read_at))
    return readings


def collect_benchmark_attention(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    observed_at: datetime,
    previous_block: dict[str, Any] | None = None,
    get_json: Callable[..., Any] = get_json,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any] | None, list[SourceHealth]]:
    """Observe the ranking signals for released artifacts in the window.

    `previous_block` is the previous snapshot's `benchmark_attention`; its
    readings are carried forward as `stale` for every resource this run did
    not read. Returns the snapshot `benchmark_attention` block and one
    `SourceHealth` row per signal for the run's attention health list, or
    `(None, [])` when the collector is disabled.
    """
    if not config or not config.get("enabled", True):
        return None, []
    observed_at = observed_at.astimezone(UTC)
    window_days = max(1, int(config.get("window_days", DEFAULT_WINDOW_DAYS)))
    targets = select_targets(items, as_of=observed_at, window_days=window_days)
    options = _request_options(config)
    max_consecutive_failures = max(
        1, int(config.get("max_consecutive_failures", DEFAULT_MAX_CONSECUTIVE_FAILURES))
    )
    budgets: dict[str, int] = {}
    delays: dict[str, float] = {}
    for source, default_budget in DEFAULT_MAX_REQUESTS.items():
        source_config = config.get(source) or {}
        budgets[source] = max(0, int(source_config.get("max_requests", default_budget)))
        delays[source] = max(
            0.0,
            float(
                source_config.get("request_delay_seconds", DEFAULT_REQUEST_DELAY_SECONDS[source])
            ),
        )

    requests_made: dict[str, int] = dict.fromkeys(budgets, 0)
    failure_streaks: dict[str, int] = dict.fromkeys(budgets, 0)
    paused: dict[str, bool] = dict.fromkeys(budgets, False)
    stats: dict[str, _SignalStats] = {signal: _SignalStats() for signal in SIGNALS}
    previous = _previous_readings(previous_block)
    observations: list[dict[str, Any]] = []
    observed_iso = observed_at.isoformat()

    for target in targets:
        for signal, url in target.resources.items():
            spec = SIGNALS[signal]
            source = spec["source"]
            signal_stats = stats[signal]
            reading = None
            if paused[source] or requests_made[source] >= budgets[source]:
                signal_stats.skipped += 1
            else:
                if requests_made[source] and delays[source]:
                    sleep(delays[source])
                requests_made[source] += 1
                reading = _read_resource(
                    signal, url, options=options, get_json=get_json, stats=signal_stats
                )
                if reading is None:
                    failure_streaks[source] += 1
                    paused[source] = failure_streaks[source] >= max_consecutive_failures
                else:
                    failure_streaks[source] = 0
            observation = {
                "canonical_artifact_id": target.canonical_id,
                "source": source,
                "metric": spec["metric"],
                "value_kind": spec["value_kind"],
                "source_url": url,
                "observed_at": observed_iso,
            }
            if reading is not None:
                value, status = reading
                observations.append({**observation, "value": value, "status": status})
                continue
            carried = previous.get((signal, url))
            if carried is None:
                continue
            value, last_successful_date = carried
            signal_stats.stale += 1
            observations.append(
                {
                    **observation,
                    "value": value,
                    "status": "stale",
                    "last_successful_date": last_successful_date,
                }
            )

    health: list[dict[str, Any]] = []
    source_health: list[SourceHealth] = []
    for signal, spec in SIGNALS.items():
        signal_stats = stats[signal]
        source = spec["source"]
        succeeded = signal_stats.observed + signal_stats.unavailable
        ok = not (signal_stats.attempted and succeeded == 0)
        notes = []
        if signal_stats.failed:
            notes.append(
                f"{signal_stats.failed} of {signal_stats.attempted} requests failed; "
                f"last: {signal_stats.last_error}"
            )
        if paused[source] and signal_stats.skipped:
            notes.append(f"{source} paused after {max_consecutive_failures} consecutive failures")
        if signal_stats.skipped:
            notes.append(
                f"{signal_stats.skipped} resources not read, "
                f"{signal_stats.stale} carried forward as stale"
            )
        error = "; ".join(notes) or None
        health.append(
            {
                "source": source,
                "metric": spec["metric"],
                "ok": ok,
                "item_count": succeeded,
                "error": error,
            }
        )
        source_health.append(
            SourceHealth(
                source=spec["label"],
                ok=ok,
                item_count=succeeded,
                error=error,
                kind="attention",
                method="API",
            )
        )
    block = {
        "schema_version": BLOCK_SCHEMA_VERSION,
        "observed_at": observed_iso,
        "observations": observations,
        "health": health,
    }
    return block, source_health


def merge_benchmark_attention(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Union two same-day blocks; the newer reading wins on a shared resource.

    Same rule as evidence and social attention in `merge_snapshots`: a second
    pass on the day must add to the day's readings, not replace them, and a
    pass that ran out of budget must not erase counters the earlier pass
    observed. A reading the newer pass only carried forward as `stale` does
    not replace one the earlier pass actually made that day. Health describes
    the newest pass, since it is the one whose failures the ranking should
    treat as current.
    """
    if not existing and not incoming:
        return None
    if not incoming:
        return existing
    if not existing:
        return incoming
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for observation in existing.get("observations") or []:
        merged[_observation_key(observation)] = observation
    for observation in incoming.get("observations") or []:
        key = _observation_key(observation)
        if observation.get("status") == "stale" and key in merged:
            if merged[key].get("status") != "stale":
                continue
        merged[key] = observation
    return {
        "schema_version": BLOCK_SCHEMA_VERSION,
        "observed_at": incoming.get("observed_at") or existing.get("observed_at"),
        "observations": list(merged.values()),
        "health": list(incoming.get("health") or []),
    }


def _observation_key(observation: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(observation.get("canonical_artifact_id")),
        str(observation.get("metric")),
        str(observation.get("source_url")),
    )
