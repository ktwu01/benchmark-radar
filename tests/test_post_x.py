"""Tests for scripts/post_x.py (the daily X poster)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "post_x.py"
_spec = importlib.util.spec_from_file_location("post_x", _SCRIPT)
post_x = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(post_x)


def _snapshot() -> dict:
    return {
        "date": "2026-11-01",
        "evidence_items": [
            {"source": "Hugging Face", "title": "A"},
            {"source": "Hugging Face", "title": "B"},
            {"source": "DataCite", "title": "C"},
        ],
        "briefing": {
            "bullets": [
                "The new Alpha Bench tests coding agents. Evidence: E001.",
                "Beta Bench measures child safety. Evidence: E002.",
                "Gamma Bench audits clinical plans. Evidence: E003.",
                "Delta Bench tracks tool use over long horizons. Evidence: E004.",
            ],
            "bullets_zh": [
                "Alpha Bench 测编程 agent 的新数据集。Evidence: E001.",
                "Beta Bench 测儿童安全。Evidence: E002.",
                "Gamma Bench 审计临床计划。Evidence: E003.",
                "Delta Bench 追踪长程工具使用。Evidence: E004.",
            ],
        },
        "share": {
            "cards": [
                {
                    "title": "alpha-bench",
                    "source": "Hugging Face",
                    "published_at": "2026-11-01T00:00:00+00:00",
                    "blurb": "The new Alpha Bench tests coding agents.",
                    "authors": ["Ida Example"],
                    "affiliations": [],
                },
                {
                    "title": "Beta Bench",
                    "source": "DataCite",
                    "published_at": "2026-10-31T00:00:00+00:00",
                    "blurb": "Beta Bench measures child safety.",
                    "authors": ["Ann A", "Bob B", "Cat C", "Dan D"],
                    "affiliations": ["KORA", "Microsoft"],
                },
                {
                    "title": "Gamma Bench",
                    "source": "DataCite",
                    "published_at": "2026-10-31T00:00:00+00:00",
                    "blurb": "Gamma Bench audits clinical plans.",
                    "authors": [],
                    "affiliations": [],
                },
            ]
        },
    }


def test_english_post_uses_cards_and_carries_no_link():
    text = post_x.build_post(_snapshot(), "en", 42331)
    assert "Benchmark Radar, Nov 1, 2026" in text
    assert "3 new benchmark items surfaced today" in text
    assert "1. alpha-bench (Hugging Face, Nov 1)" in text
    assert "By Ann A, Bob B, Cat C et al. · KORA, Microsoft" in text
    assert "Delta Bench tracks tool use" in text
    assert "42,331 records" in text
    assert "http" not in text


def test_chinese_post_uses_zh_bullets_and_carries_no_link():
    text = post_x.build_post(_snapshot(), "zh", 42331)
    assert "2026 年 11 月 1 日" in text
    assert "Alpha Bench 测编程 agent 的新数据集。" in text
    assert "Delta Bench 追踪长程工具使用。" in text
    assert "42,331 条记录" in text
    assert "http" not in text


def test_oauth1_signature_matches_reference_implementation():
    # The worked example inputs from X's "Creating a signature" page, with
    # fixed nonce and timestamp. The expected signature was cross-checked
    # against oauthlib (the reference OAuth 1.0a library), which produces
    # the identical value for these inputs.
    credentials = {
        "api_key": "xvz1evFS4wEEPTGEFPHBog",
        "api_secret": "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
        "access_token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
        "access_token_secret": "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
    }
    header = post_x.oauth1_authorization_header(
        "POST",
        "https://api.twitter.com/1.1/statuses/update.json?include_entities=true",
        credentials,
        {"status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgm",
        timestamp="1318622958",
    )
    assert 'oauth_signature="zYI1a1h%2BZl3NQweXz1HNi2NnkEk%3D"' in header


def test_upload_media_sends_multipart_form(monkeypatch):
    captured = {}

    def fake_request_json(request):
        captured["data"] = request.data
        headers = {key.lower(): value for key, value in request.header_items()}
        captured["content_type"] = headers.get("content-type", "")
        return {"data": {"id": "1880028106020515840"}}

    monkeypatch.setattr(post_x, "_request_json", fake_request_json)
    credentials = {
        "api_key": "key",
        "api_secret": "secret",
        "access_token": "token",
        "access_token_secret": "token-secret",
    }
    image = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    assert post_x.upload_media(image, credentials) == "1880028106020515840"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    body = captured["data"]
    assert b'name="media"; filename="card.png"' in body
    assert b'name="media_category"' in body and b"tweet_image" in body
    assert image in body
    assert b"media_data" not in body


def test_ledger_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(post_x, "LEDGER_PATH", tmp_path / "x-posts.json")
    ledger = post_x.load_ledger()
    assert not post_x.already_posted(ledger, "2026-11-01", "en")
    post_x.record_post(ledger, "2026-11-01", "en", "12345")
    assert post_x.already_posted(post_x.load_ledger(), "2026-11-01", "en")
    assert not post_x.already_posted(post_x.load_ledger(), "2026-11-01", "zh")
