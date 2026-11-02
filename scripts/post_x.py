#!/usr/bin/env python3
"""Post the day's Benchmark Radar briefing to X.

Reads the committed daily snapshot and builds one long post from material the
radar already produced: the briefing bullets and the share block that also
drives the day's cards. Nothing here writes new copy beyond fixed framing
lines, and no count is hard-coded: the item count and source list come from
the snapshot, the corpus total from the live records badge.

Two scheduled workflows call this script, one fixed UTC time each:

- post-x-en.yml at 13:00 UTC, posting the English briefing;
- post-x-zh.yml at 03:00 UTC, posting the Chinese briefing from
  ``briefing.bullets_zh`` for the latest committed snapshot.

The post body never carries a link; the maintainer adds benchmark-radar.org
as the first reply himself. Posting uses the official X API with OAuth 2.0
user context: the workflow exchanges the stored refresh token (secrets
X_CLIENT_ID, X_CLIENT_SECRET, X_REFRESH_TOKEN) for a short-lived access
token, then posts as @ktwu01. X rotates the refresh token on every
exchange and kills the old one, so whenever X returns a new refresh token
the script writes it back into the X_REFRESH_TOKEN secret (using the
X_SECRETS_PAT secret, a fine-grained PAT allowed to write this repo's
secrets); without that write-back the chain would break on the second run.
A ledger at data/x-posts.json records each
{date, lang, post id} so a re-run never posts the same briefing twice.
There are no retries: one attempt, then the run fails loudly.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
LEDGER_PATH = ROOT / "data" / "x-posts.json"
CARDS_IMAGE_URL = "https://cards.benchmark-radar.org/daily/{date}/top3.png"
BADGE_URL = "https://benchmark-radar.org/data/records-badge.json"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
TWEETS_URL = "https://api.x.com/2/tweets"
MAX_POST_CHARS = 4_000

_MONTHS_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_EVIDENCE_RE = re.compile(r"\s*Evidence:\s*[^.]*\.?")
_CITATION_RE = re.compile(r"\bEvidence\b")


def _clean(text: str) -> str:
    """Collapse whitespace and drop the briefing's evidence annotations."""
    text = _EVIDENCE_RE.sub("", str(text or ""))
    return " ".join(text.split()).strip()


def first_sentence_en(text: str) -> str:
    cleaned = _clean(text)
    match = re.match(r"^(.+?[.!?])(?:\s|$)", cleaned)
    return match.group(1) if match else cleaned


def first_sentence_zh(text: str) -> str:
    cleaned = _clean(text)
    match = re.match(r"^(.+?[。！？])", cleaned)
    return match.group(1) if match else first_sentence_en(cleaned)


def list_snapshots() -> list[str]:
    if not SNAPSHOT_DIR.is_dir():
        return []
    return sorted(
        path.stem for path in SNAPSHOT_DIR.glob("????-??-??.json")
    )


def pick_snapshot_date(lang: str, requested: str | None) -> str | None:
    """Which snapshot a run posts.

    English runs after the day's 05:00 UTC radar run, so it prefers today's
    UTC date. Chinese runs at 03:00 UTC, before that day's run, so the
    latest committed snapshot is the previous UTC day's; both languages fall
    back to the newest snapshot on disk so a delayed run still posts.
    """
    dates = list_snapshots()
    if not dates:
        return None
    if requested:
        return requested if requested in dates else None
    today = dt.datetime.now(dt.UTC).date().isoformat()
    if lang == "en" and today in dates:
        return today
    return dates[-1]


def load_snapshot(date: str) -> dict[str, Any]:
    path = SNAPSHOT_DIR / f"{date}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _format_date_en(iso_date: str) -> str:
    parsed = dt.date.fromisoformat(iso_date)
    return f"{_MONTHS_EN[parsed.month - 1]} {parsed.day}, {parsed.year}"


def _format_date_zh(iso_date: str) -> str:
    parsed = dt.date.fromisoformat(iso_date)
    return f"{parsed.year} 年 {parsed.month} 月 {parsed.day} 日"


def _format_day_en(iso_datetime: str) -> str:
    parsed = dt.datetime.fromisoformat(str(iso_datetime).replace("Z", "+00:00"))
    return f"{_MONTHS_EN[parsed.month - 1]} {parsed.day}"


def _format_day_zh(iso_datetime: str) -> str:
    parsed = dt.datetime.fromisoformat(str(iso_datetime).replace("Z", "+00:00"))
    return f"{parsed.month} 月 {parsed.day} 日"


def _creators_line(card: dict[str, Any], lang: str) -> str | None:
    authors = [str(name) for name in card.get("authors") or [] if str(name).strip()]
    affiliations = [
        str(name) for name in card.get("affiliations") or [] if str(name).strip()
    ]
    if not authors and not affiliations:
        return None
    label = "By" if lang == "en" else "作者"
    parts = []
    if authors:
        shown = ", ".join(authors[:3])
        if len(authors) > 3:
            shown += " et al."
        parts.append(shown)
    if affiliations:
        parts.append(", ".join(affiliations[:2]))
    return f"{label} {' · '.join(parts)}"


def build_post(snapshot: dict[str, Any], lang: str, total_records: int | None) -> str:
    """Assemble the long post for one snapshot in one language."""
    date = str(snapshot["date"])
    items = snapshot.get("evidence_items") or []
    sources = ", ".join(
        source for source, _ in Counter(
            str(item.get("source") or "unknown") for item in items
        ).most_common()
    )
    briefing = snapshot.get("briefing") or {}
    bullets = briefing.get("bullets") or []
    bullets_zh = briefing.get("bullets_zh") or []
    cards = (snapshot.get("share") or {}).get("cards") or []
    top_cards = cards[:3]

    if lang == "zh":
        lines = [
            f"📡 Benchmark Radar，{_format_date_zh(date)}",
            "",
            f"今天从 {sources} 共扫到 {len(items)} 条新条目。最值得先点开的三条：",
            "",
        ]
        for index, card in enumerate(top_cards):
            day = _format_day_zh(str(card.get("published_at") or ""))
            lines.append(
                f"{index + 1}. {card.get('title')}（{card.get('source')}，{day}）"
            )
            blurb = (
                first_sentence_zh(bullets_zh[index])
                if index < len(bullets_zh)
                else first_sentence_en(str(card.get("blurb") or ""))
            )
            if blurb:
                lines.append(blurb)
            creators = _creators_line(card, lang)
            if creators:
                lines.append(creators)
            lines.append("")
        extra = [first_sentence_zh(b) for b in bullets_zh[3:5] if b.strip()]
        if extra:
            lines.append("今日简报其他要点：")
            lines.extend(f"· {line}" for line in extra)
            lines.append("")
        if total_records:
            lines.append(f"Radar 现在共 {total_records:,} 条记录，每天更新，免费开源。")
        lines.append("完整数据和搜索在第一条回复里 👇")
        return "\n".join(lines)

    lines = [
        f"📡 Benchmark Radar, {_format_date_en(date)}",
        "",
        f"{len(items)} new benchmark items surfaced today across {sources}. "
        "Three to open first:",
        "",
    ]
    for index, card in enumerate(top_cards):
        day = _format_day_en(str(card.get("published_at") or ""))
        lines.append(f"{index + 1}. {card.get('title')} ({card.get('source')}, {day})")
        blurb = first_sentence_en(str(card.get("blurb") or ""))
        if blurb:
            lines.append(blurb)
        creators = _creators_line(card, lang)
        if creators:
            lines.append(creators)
        lines.append("")
    extra = [first_sentence_en(b) for b in bullets[3:5] if b.strip()]
    if extra:
        lines.append("Also in today's briefing:")
        lines.extend(f"· {line}" for line in extra)
        lines.append("")
    if total_records:
        lines.append(
            f"Radar totals: {total_records:,} records, updated daily, "
            "free and open source."
        )
    lines.append("Full data and search in the first reply 👇")
    return "\n".join(lines)


def fetch_total_records() -> int | None:
    """Corpus size from the live records badge; None when unreachable."""
    try:
        with urllib.request.urlopen(BADGE_URL, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        match = re.match(r"([\d,]+)", str(payload.get("message") or ""))
        return int(match.group(1).replace(",", "")) if match else None
    except (OSError, ValueError) as error:
        print(f"warning: records badge unavailable: {error}", file=sys.stderr)
        return None


def fetch_image(date: str) -> bytes | None:
    """The day's top3 card image; None when the cards site has not served it."""
    url = CARDS_IMAGE_URL.format(date=date)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except OSError as error:
        print(f"warning: share image unavailable ({url}): {error}", file=sys.stderr)
        return None


def load_ledger() -> dict[str, Any]:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {"posts": []}


def already_posted(ledger: dict[str, Any], date: str, lang: str) -> bool:
    return any(
        entry.get("date") == date and entry.get("lang") == lang
        for entry in ledger.get("posts") or []
    )


def record_post(ledger: dict[str, Any], date: str, lang: str, post_id: str) -> None:
    ledger.setdefault("posts", []).append(
        {
            "date": date,
            "lang": lang,
            "id": post_id,
            "posted_at": dt.datetime.now(dt.UTC).isoformat(),
        }
    )
    LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _request_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X API {error.code}: {body}") from error


def _request_no_content(request: urllib.request.Request) -> None:
    """Run a request whose success response may have an empty body.

    GitHub answers 204 No Content when an existing secret is updated, so
    this path must not go through the JSON-only helper.
    """
    try:
        with urllib.request.urlopen(request) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{request.full_url} failed: HTTP {exc.code}: {detail}"
        ) from exc


def fetch_access_token(credentials: dict[str, str]) -> tuple[str, str | None]:
    """Trade the stored OAuth 2.0 refresh token for a short-lived access token.

    Returns (access_token, new_refresh_token). X rotates the refresh token
    on every exchange: the response carries a fresh one and the presented
    token stops working, so the caller must persist the new one.
    """
    basic = base64.b64encode(
        f"{credentials['client_id']}:{credentials['client_secret']}".encode()
    ).decode()
    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": credentials["refresh_token"],
            }
        ).encode(),
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    payload = _request_json(request)
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"X token exchange returned no access token: {payload}")
    new_refresh = payload.get("refresh_token")
    return str(access_token), (str(new_refresh) if new_refresh else None)


def update_refresh_secret(new_refresh_token: str) -> None:
    """Write the rotated refresh token back into the X_REFRESH_TOKEN secret.

    Uses the GitHub actions-secrets API with X_SECRETS_PAT. The value is
    sealed with the repo's public key (PyNaCl) and never printed.
    """
    pat = os.environ.get("X_SECRETS_PAT") or ""
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    if not pat or not repo:
        print(
            "::warning::X rotated the refresh token but X_SECRETS_PAT is not "
            "set, so the new token could not be saved. The next run will "
            "fail until X_REFRESH_TOKEN is updated by hand."
        )
        return
    try:
        from nacl.encoding import Base64Encoder
        from nacl.public import PublicKey, SealedBox
    except ImportError:
        print("::warning::PyNaCl is missing; cannot update X_REFRESH_TOKEN.")
        return
    api = f"https://api.github.com/repos/{repo}/actions/secrets"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }
    key_request = urllib.request.Request(
        f"{api}/public-key", headers=headers, method="GET"
    )
    key_payload = _request_json(key_request)
    box = SealedBox(PublicKey(key_payload["key"], encoder=Base64Encoder))
    sealed = base64.b64encode(
        box.encrypt(new_refresh_token.encode("utf-8"))
    ).decode()
    put_request = urllib.request.Request(
        f"{api}/X_REFRESH_TOKEN",
        data=json.dumps(
            {"encrypted_value": sealed, "key_id": key_payload["key_id"]}
        ).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT",
    )
    _request_no_content(put_request)
    print("Saved the rotated refresh token to X_REFRESH_TOKEN.")


def upload_media(image: bytes, access_token: str) -> str:
    request = urllib.request.Request(
        MEDIA_UPLOAD_URL,
        data=json.dumps(
            {
                "media_data": base64.b64encode(image).decode(),
                "media_category": "tweet_image",
                "media_type": "image/png",
            }
        ).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    payload = _request_json(request)
    media_id = (payload.get("data") or {}).get("id")
    if not media_id:
        raise RuntimeError(f"X media upload returned no media id: {payload}")
    return str(media_id)


def create_post(text: str, media_id: str | None, access_token: str) -> str:
    payload: dict[str, Any] = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    request = urllib.request.Request(
        TWEETS_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    result = _request_json(request)
    post_id = (result.get("data") or {}).get("id")
    if not post_id:
        raise RuntimeError(f"X post creation returned no id: {result}")
    return str(post_id)


def _emit_output(**values: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")
    for key, value in values.items():
        print(f"{key}={value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=("en", "zh"), required=True)
    parser.add_argument("--date", help="Snapshot date (YYYY-MM-DD); default per language")
    parser.add_argument("--dry-run", action="store_true", help="Print, do not post")
    args = parser.parse_args(argv)

    date = pick_snapshot_date(args.lang, args.date)
    if date is None:
        print("::error::No snapshot found to post.", file=sys.stderr)
        return 1
    snapshot = load_snapshot(date)
    text = build_post(snapshot, args.lang, fetch_total_records())
    if len(text) > MAX_POST_CHARS:
        print(
            f"::error::Post is {len(text)} characters, over the {MAX_POST_CHARS} cap.",
            file=sys.stderr,
        )
        return 1
    if "http://" in text or "https://" in text:
        print("::error::Post text contains a URL; links belong in the reply.", file=sys.stderr)
        return 1

    if args.dry_run:
        print(text)
        _emit_output(posted="false", snapshot_date=date)
        return 0

    ledger = load_ledger()
    if already_posted(ledger, date, args.lang):
        print(f"Skipping: {date} ({args.lang}) is already in the ledger.")
        _emit_output(posted="false", snapshot_date=date)
        return 0

    credentials = {
        "client_id": os.environ.get("X_CLIENT_ID") or "",
        "client_secret": os.environ.get("X_CLIENT_SECRET") or "",
        "refresh_token": os.environ.get("X_REFRESH_TOKEN") or "",
    }
    if not all(credentials.values()):
        print(
            "::warning::X API secrets are not set yet; skipping the post. "
            "Add X_CLIENT_ID, X_CLIENT_SECRET and X_REFRESH_TOKEN as "
            "repository secrets to enable posting."
        )
        _emit_output(posted="false", snapshot_date=date)
        return 0

    access_token, new_refresh_token = fetch_access_token(credentials)
    if new_refresh_token and new_refresh_token != credentials["refresh_token"]:
        update_refresh_secret(new_refresh_token)
    image = fetch_image(date)
    media_id = upload_media(image, access_token) if image else None
    post_id = create_post(text, media_id, access_token)
    record_post(ledger, date, args.lang, post_id)
    print(f"Posted {date} ({args.lang}): https://x.com/ktwu01/status/{post_id}")
    _emit_output(posted="true", snapshot_date=date, post_id=post_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
