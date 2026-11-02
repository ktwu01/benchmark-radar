"""Tests for scripts/post_x.py (the daily X poster)."""

from __future__ import annotations

import datetime as dt
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


def test_eastern_window_follows_daylight_saving():
    # 12:00 UTC is 8:00 EDT in summer and 7:00 EST in winter.
    assert post_x.in_eastern_window(dt.datetime(2026, 7, 1, 12, tzinfo=dt.UTC))
    assert not post_x.in_eastern_window(dt.datetime(2026, 1, 15, 12, tzinfo=dt.UTC))
    # 13:00 UTC is 8:00 EST in winter.
    assert post_x.in_eastern_window(dt.datetime(2026, 1, 15, 13, tzinfo=dt.UTC))
    # A delayed summer trigger at 13:30 UTC (9:30 EDT) still posts.
    assert post_x.in_eastern_window(dt.datetime(2026, 7, 1, 13, 30, tzinfo=dt.UTC))
    # 15:00 UTC (11:00 EDT) is outside the window.
    assert not post_x.in_eastern_window(dt.datetime(2026, 7, 1, 15, tzinfo=dt.UTC))


def test_ledger_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(post_x, "LEDGER_PATH", tmp_path / "x-posts.json")
    ledger = post_x.load_ledger()
    assert not post_x.already_posted(ledger, "2026-11-01", "en")
    post_x.record_post(ledger, "2026-11-01", "en", "12345")
    assert post_x.already_posted(post_x.load_ledger(), "2026-11-01", "en")
    assert not post_x.already_posted(post_x.load_ledger(), "2026-11-01", "zh")
