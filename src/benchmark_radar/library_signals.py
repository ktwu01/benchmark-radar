"""Attach benchmark-radar.com attention signals to catalog records.

GitHub stars, Hugging Face paper upvotes and dataset downloads are observations
of a repository or paper on a date, exported from Claire Radar with that date
(scripts/export_claire_library_signals.py). They reach a record through the
same exact identity stages as the Library's directions (candidate_stages), and
only when every candidate reports the same values: two .com records that share a
paper but track different repositories would otherwise lend one record the
other's stars.

`github_stars_30d` is the stars gained in the 30 days ending on the observation
date, read from the sparse history (a value is stored only when it changes). The
history starts 2026-08-19, so a longer window would really measure "since
collection began"; when the history does not reach back 30 days the gain is
None rather than a guess.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .library_directions import candidate_stages

DEFAULT_LIBRARY_SIGNALS_PATH = Path("data/catalog/claire_library_signals.json")
SIGNAL_NAMES = ("github_stars", "hf_paper_upvotes", "hf_dataset_downloads")
GAIN_WINDOW_DAYS = 30


def load_library_signals(path: Path = DEFAULT_LIBRARY_SIGNALS_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    return document


def stars_gained(history: list[list[Any]], as_of: str, days: int = GAIN_WINDOW_DAYS) -> int | None:
    """Stars gained in the `days` ending on `as_of`, or None if uncovered."""
    if not history:
        return None
    start = (date.fromisoformat(as_of) - timedelta(days=days)).isoformat()
    points = sorted((str(day), int(value)) for day, value in history)
    if points[0][0] > start:
        return None
    before = [value for day, value in points if day <= start][-1]
    latest = [value for day, value in points if day <= as_of][-1]
    return latest - before


def _signals(entry: dict[str, Any], record_id: str, join: str, observed_on: str) -> dict[str, Any]:
    as_of = entry.get("as_of") or observed_on
    return {
        **{name: entry.get(name) for name in SIGNAL_NAMES},
        "github_stars_30d": stars_gained(entry.get("github_stars_history") or [], as_of)
        if as_of
        else None,
        "as_of": as_of,
        "join": join,
        "source_record": record_id,
    }


def assign_library_signals(
    records: list[dict[str, Any]], document: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """Map catalog record keys to their observed signals, by exact identity only."""
    if not document:
        return {}
    entries: dict[str, Any] = document["records"]
    observed_on = str((document.get("source") or {}).get("observed_on") or "")
    signals: dict[str, dict[str, Any]] = {}
    for record, stages in candidate_stages(records, entries):
        for join, candidates in stages:
            values = {
                json.dumps(
                    {name: entries[candidate].get(name) for name in SIGNAL_NAMES},
                    sort_keys=True,
                )
                for candidate in candidates
            }
            if len(values) == 1:
                chosen = min(candidates)
                signals[record["key"]] = _signals(entries[chosen], chosen, join, observed_on)
                break
    return signals
