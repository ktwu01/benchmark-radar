#!/usr/bin/env python3
"""One-off diagnostic probes for the X API upload 503. Posts nothing public.

Run inside GitHub Actions on a scratch branch, with the same four repo
secrets the poster uses. Each probe prints one line: name, HTTP status,
and the first part of the response body.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "post_x", Path(__file__).resolve().parent / "post_x.py"
)
post_x = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(post_x)

CREDENTIALS = {
    "api_key": os.environ.get("X_API_KEY") or "",
    "api_secret": os.environ.get("X_API_SECRET") or "",
    "access_token": os.environ.get("X_ACCESS_TOKEN") or "",
    "access_token_secret": os.environ.get("X_ACCESS_TOKEN_SECRET") or "",
}

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def probe(name: str, request: urllib.request.Request) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, body = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read().decode("utf-8", "replace")
    except Exception as error:  # noqa: BLE001 - diagnostic, report anything
        print(f"PROBE {name}: EXCEPTION {type(error).__name__}: {error}")
        return 0, ""
    print(f"PROBE {name}: HTTP {status} {body[:300]!r}")
    return status, body


def signed(method: str, url: str) -> str:
    return post_x.oauth1_authorization_header(method, url, CREDENTIALS)


def main() -> int:
    print("PROBE secrets_present:", all(CREDENTIALS.values()))

    # A. Auth check: who am I?
    probe(
        "A users/me",
        urllib.request.Request(
            "https://api.x.com/2/users/me",
            headers={"Authorization": signed("GET", "https://api.x.com/2/users/me")},
        ),
    )

    # B. Tweets endpoint gate: an empty body must fail validation (400) on a
    # healthy account; it can never create a post.
    probe(
        "B tweets empty body",
        urllib.request.Request(
            post_x.TWEETS_URL,
            data=b"{}",
            method="POST",
            headers={
                "Authorization": signed("POST", post_x.TWEETS_URL),
                "Content-Type": "application/json",
            },
        ),
    )

    card = post_x.fetch_image("2026-11-02") or b""
    print("PROBE card image bytes:", len(card))

    # C. One-shot upload, tiny 1x1 PNG.
    body, content_type = post_x._multipart_form_body(
        {"media_category": "tweet_image", "media_type": "image/png"},
        "media",
        "tiny.png",
        "image/png",
        TINY_PNG,
    )
    probe(
        "C one-shot tiny png",
        urllib.request.Request(
            post_x.MEDIA_UPLOAD_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": signed("POST", post_x.MEDIA_UPLOAD_URL),
                "Content-Type": content_type,
            },
        ),
    )

    # D. One-shot upload with NO auth header: gateway sanity (expect 401).
    probe(
        "D one-shot no auth",
        urllib.request.Request(
            post_x.MEDIA_UPLOAD_URL,
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        ),
    )

    # E. Chunked flow with the real card image: initialize, append, finalize.
    init_url = "https://api.x.com/2/media/upload/initialize"
    status, init_body = probe(
        "E1 chunked initialize",
        urllib.request.Request(
            init_url,
            data=json.dumps(
                {
                    "media_type": "image/png",
                    "total_bytes": len(card),
                    "media_category": "tweet_image",
                }
            ).encode(),
            method="POST",
            headers={
                "Authorization": signed("POST", init_url),
                "Content-Type": "application/json",
            },
        ),
    )
    media_id = None
    if status in (200, 201):
        try:
            media_id = (json.loads(init_body).get("data") or {}).get("id")
        except json.JSONDecodeError:
            media_id = None
    print("PROBE E chunked media_id:", media_id)
    if media_id:
        append_url = f"https://api.x.com/2/media/upload/{media_id}/append"
        body, content_type = post_x._multipart_form_body(
            {"segment_index": "0"},
            "media",
            "card.png",
            "image/png",
            card,
        )
        probe(
            "E2 chunked append",
            urllib.request.Request(
                append_url,
                data=body,
                method="POST",
                headers={
                    "Authorization": signed("POST", append_url),
                    "Content-Type": content_type,
                },
            ),
        )
        finalize_url = f"https://api.x.com/2/media/upload/{media_id}/finalize"
        probe(
            "E3 chunked finalize",
            urllib.request.Request(
                finalize_url,
                data=b"",
                method="POST",
                headers={"Authorization": signed("POST", finalize_url)},
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
