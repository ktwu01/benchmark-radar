"""Send one day's brief to email subscribers through Kit (issue #977).

The subscriber list lives in Kit (form 10097391, custom field ``frequency``),
so this module only has two jobs: render the day's brief as a plain email from
the same committed snapshot the blog page is built from, and hand it to Kit's
broadcast API for the right segment. It never decides *whether* today was
already sent; the workflow's git tag does that, before this runs, because a
lost API response must lead to a skipped day rather than a second mailing.

Weekly subscribers have no roundup yet (#979). Until they do, Monday's daily
brief goes to both segments, which is what the signup's "Weekly · every Monday"
option promises.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from .blog_content import build_post
from .site_shell import esc
from .snapshots import load_snapshots

KIT_API = "https://api.kit.com"
DAILY_SEGMENT_NAME = "Daily"
WEEKLY_SEGMENT_NAME = "Weekly"
# Kit sends a broadcast at send_at. A few minutes ahead keeps the time valid
# when it arrives and leaves a window to cancel it in Kit by hand.
SEND_DELAY = timedelta(minutes=10)
_TIMEOUT_SECONDS = 30
_MIN_BULLETS = 1


class EmailError(RuntimeError):
    """A condition under which nothing may be sent."""


@dataclass(frozen=True)
class EmailBrief:
    day: str
    subject: str
    preview_text: str
    html: str


def render_email(
    snapshot: dict[str, Any], *, days: list[dict[str, Any]] | None = None
) -> EmailBrief:
    """The day's briefing bullets, in English only, with a link to the full page.

    The blog page carries both languages and the site's stylesheet; neither
    survives an email client, so the email keeps the bullets and sends the
    reader to the page for questions, sources and provenance.
    """
    # Match the blog's fallback lead selection on days without share cards.
    post = build_post(snapshot, days=days)
    briefing = snapshot.get("briefing") or {}
    bullets = [str(bullet).strip() for bullet in briefing.get("bullets") or []]
    bullets = [bullet for bullet in bullets if bullet]
    if len(bullets) < _MIN_BULLETS:
        raise EmailError(f"{post.slug} has no stored briefing bullets to send")
    items = "".join(f'<li style="margin:0 0 12px">{esc(bullet)}</li>' for bullet in bullets)
    link = esc(post.canonical)
    html = (
        '<div style="font-family:-apple-system,Segoe UI,sans-serif;font-size:16px;'
        'line-height:1.5;color:#15242a;max-width:640px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{esc(post.title)}</h1>'
        f'<ol style="padding-left:20px;margin:0 0 20px">{items}</ol>'
        f'<p style="margin:0 0 24px"><a href="{link}">Read the full brief, with the '
        "questions, sources and evidence</a></p>"
        # Kit's account template appends the unsubscribe link and the postal
        # address under this; repeating them here printed both twice.
        '<p style="font-size:13px;color:#5f7078;margin:0">You get this because you '
        "subscribed at benchmark-radar.org.</p>"
        "</div>"
    )
    return EmailBrief(
        day=post.slug,
        subject=f"Benchmark Radar daily brief: {post.slug}",
        preview_text=post.description,
        html=html,
    )


def segment_ids_for(day: str, daily_id: int, weekly_id: int) -> list[int]:
    """Daily always; weekly too when the brief is Monday's."""
    if daily_id == weekly_id:
        raise EmailError("the Daily and Weekly segment ids must differ")
    monday = date.fromisoformat(day).weekday() == 0
    return [daily_id, weekly_id] if monday else [daily_id]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect would replay the API key header to another host.
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise EmailError("Kit answered with a redirect; refusing to follow it")


_OPENER = urllib.request.build_opener(_NoRedirect)


def _kit(method: str, path: str, api_key: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        KIT_API + path,
        data=data,
        method=method,
        headers={
            "X-Kit-Api-Key": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with _OPENER.open(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The body is Kit's error message; the request headers, which hold the
        # key, are never printed.
        detail = error.read().decode("utf-8", "replace")[:500]
        raise EmailError(f"Kit {method} {path} failed with HTTP {error.code}: {detail}") from None
    except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
        raise EmailError(f"Kit {method} {path} did not answer: {error}") from None
    except ValueError as error:
        raise EmailError(f"Kit {method} {path} answered with invalid JSON: {error}") from None


def check_segments(api_key: str, daily_id: int, weekly_id: int) -> None:
    """Stop unless both ids exist in this account under the expected names."""
    names: dict[int, str] = {}
    after = ""
    while True:
        page = _kit("GET", f"/v4/segments?per_page=1000{after}", api_key)
        for segment in page.get("segments") or []:
            names[int(segment["id"])] = str(segment.get("name") or "")
        pagination = page.get("pagination") or {}
        if not pagination.get("has_next_page"):
            break
        after = "&after=" + urllib.parse.quote(str(pagination["end_cursor"]), safe="")
    for segment_id, expected in ((daily_id, DAILY_SEGMENT_NAME), (weekly_id, WEEKLY_SEGMENT_NAME)):
        if names.get(segment_id) != expected:
            raise EmailError(
                f"segment {segment_id} should be named {expected!r} in Kit, "
                f"found {names.get(segment_id)!r}"
            )


def broadcast_body(
    brief: EmailBrief, segment_ids: list[int], *, send_at: datetime | None
) -> dict[str, Any]:
    return {
        "subject": brief.subject,
        "preview_text": brief.preview_text,
        "description": f"Daily brief {brief.day} (sent by .github/workflows/send-email.yml)",
        "content": brief.html,
        "public": False,
        # Required by the API; only shown when public, which this never is.
        "published_at": (send_at or datetime.now(UTC)).isoformat(),
        "send_at": send_at.isoformat() if send_at else None,
        "subscriber_filter": [{"any": [{"type": "segment", "ids": segment_ids}]}],
    }


def create_broadcast(api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    response = _kit("POST", "/v4/broadcasts", api_key, body)
    broadcast = (response or {}).get("broadcast") or {}
    if not broadcast.get("id"):
        raise EmailError(f"Kit accepted the request but returned no broadcast id: {response}")
    if body["send_at"] and not broadcast.get("send_at"):
        raise EmailError(f"Kit saved broadcast {broadcast['id']} without a send time")
    return broadcast


def _snapshot_for(snapshot_dir: Path, day: str, *, days: list[dict[str, Any]]) -> dict[str, Any]:
    for snapshot in days:
        if str(snapshot["date"]) == day:
            return snapshot
    raise EmailError(f"no committed snapshot for {day} in {snapshot_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--snapshots", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--mode", choices=("preview", "draft", "send"), default="preview")
    parser.add_argument("--out", type=Path, default=Path("email.html"))
    # Every check a send makes, without the POST. The workflow runs this before
    # it records the day, so a fault found here never blocks the day.
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    day = args.date.isoformat()
    try:
        days = load_snapshots(args.snapshots)
        brief = render_email(_snapshot_for(args.snapshots, day, days=days), days=days)
        args.out.write_text(brief.html, encoding="utf-8")
        print(f"rendered {brief.subject!r} to {args.out}")
        if args.mode == "preview":
            return 0
        api_key = os.environ.get("KIT_API_KEY", "")
        daily, weekly = (
            os.environ.get("KIT_DAILY_SEGMENT_ID"),
            os.environ.get("KIT_WEEKLY_SEGMENT_ID"),
        )
        if not api_key or not daily or not weekly:
            raise EmailError(
                "KIT_API_KEY, KIT_DAILY_SEGMENT_ID and KIT_WEEKLY_SEGMENT_ID must all be set"
            )
        daily_id, weekly_id = int(daily), int(weekly)
        check_segments(api_key, daily_id, weekly_id)
        segments = segment_ids_for(day, daily_id, weekly_id)
        if args.preflight:
            print(f"preflight passed: {args.mode} to segments {segments}")
            return 0
        send_at = datetime.now(UTC) + SEND_DELAY if args.mode == "send" else None
        broadcast = create_broadcast(api_key, broadcast_body(brief, segments, send_at=send_at))
        state = f"scheduled for {broadcast['send_at']}" if send_at else "saved as a draft"
        print(f"Kit broadcast {broadcast['id']} {state} to segments {segments}")
        return 0
    except EmailError as error:
        print(f"::error title=Email not sent::{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
