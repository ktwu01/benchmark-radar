"""Same-day snapshot merging for the daily report, and bullet escaping.

The OpenAI-generated briefing this module used to own is gone (issue #127). It
asked a model for "the strongest grounded insight" over aggregate counts and
twelve unranked titles, and got counter recitation back, because counts were
nearly all it received. Findings are now computed and verified in
`findings.py`, where the evidence for each claim is explicit and checkable.

What remains here is the snapshot plumbing the daily report needs: merging the
day's passes into one view, and escaping bullets at the Markdown boundary.
"""

from __future__ import annotations

import html
import re
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from .models import AttentionObservation, RadarItem, RadarRun
from .snapshots import merge_snapshots, snapshot_for_run


def previous_calendar_day(snapshots: list[dict[str, Any]], run: RadarRun) -> dict[str, Any] | None:
    """Return yesterday's snapshot, never an earlier or same-day run."""
    expected = (run.generated_at.astimezone(UTC).date() - timedelta(days=1)).isoformat()
    return next(
        (snapshot for snapshot in reversed(snapshots) if snapshot["date"] == expected),
        None,
    )


def current_day_snapshot(snapshots: list[dict[str, Any]], run: RadarRun) -> dict[str, Any]:
    """Return this run merged with an earlier pass from the same UTC day."""
    incoming = snapshot_for_run(run)
    existing = next(
        (snapshot for snapshot in reversed(snapshots) if snapshot["date"] == incoming["date"]),
        None,
    )
    if not existing:
        return incoming
    merged = merge_snapshots(existing, incoming)
    merged["evidence_items"].sort(
        key=lambda item: (
            bool(item.get("watchlist")),
            float(item.get("total_score") or 0),
            str(item.get("published_at") or ""),
        ),
        reverse=True,
    )
    return merged


def _record_from_dict(record_type, value: dict[str, Any]):
    values = {field.name: value[field.name] for field in fields(record_type) if field.name in value}
    for name in ("published_at", "updated_at", "discovered_at", "retrieved_at", "observed_at"):
        if values.get(name):
            values[name] = datetime.fromisoformat(str(values[name]).replace("Z", "+00:00"))
    return record_type(**values)


def daily_report_run(snapshot: dict[str, Any], latest_run: RadarRun) -> RadarRun:
    """Project a merged daily snapshot back into the report's typed view."""
    return replace(
        latest_run,
        generated_at=datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00")),
        since=datetime.fromisoformat(str(snapshot["since"]).replace("Z", "+00:00")),
        items=[_record_from_dict(RadarItem, item) for item in snapshot["evidence_items"]],
        attention=[
            _record_from_dict(AttentionObservation, item)
            for item in (snapshot.get("attention") or {}).get("observations") or []
        ],
        selection=dict(snapshot.get("selection") or {}),
    )


def markdown_bullet(bullet: str) -> str:
    """Escape one canonical bullet for the Markdown report.

    Bullets are stored as canonical plain text, because the dashboard assigns
    them through DOM `textContent` where stored escapes would render as visible
    backslashes and HTML entities. The Markdown report needs them escaped, so
    that happens here at the render boundary.

    Findings are now computed from the corpus rather than written by a model
    (issue #127), so no untrusted prose reaches this function. The escaping
    stays because the bullets still interpolate upstream-derived values, and a
    category name or source name is data that must not become Markdown.
    """
    escaped = html.escape(bullet, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!>])", r"\\\1", escaped)
