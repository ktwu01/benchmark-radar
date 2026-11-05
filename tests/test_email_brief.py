"""The daily email: what it renders, who it goes to, and when it refuses (issue #977)."""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from benchmark_radar import email_brief
from benchmark_radar.email_brief import (
    EmailError,
    broadcast_body,
    check_segments,
    create_broadcast,
    render_email,
    segment_ids_for,
)

WORKFLOW = Path(".github/workflows/send-email.yml")


def _snapshot(day: str = "2026-10-26", bullets: list[str] | None = None) -> dict:
    return {
        "date": day,
        "generated_at": f"{day}T05:30:00Z",
        "briefing": {
            "bullets": ["First <finding> & why it matters."] if bullets is None else bullets,
            "bullets_zh": ["第一条发现。"],
        },
        "evidence_items": [],
    }


def test_the_email_is_the_english_briefing_with_a_link_and_unsubscribe():
    brief = render_email(_snapshot())
    assert brief.subject == "Benchmark Radar daily brief: 2026-10-26"
    assert "First &lt;finding&gt; &amp; why it matters." in brief.html
    # One language only: the hidden Chinese body of the blog page must not leak.
    assert "第一条" not in brief.html
    assert 'href="https://benchmark-radar.org/blog/2026-10-26/"' in brief.html
    # Kit's template adds the unsubscribe link and address once; the body must
    # not add a second copy.
    assert "unsubscribe_url" not in brief.html
    assert "{{ address }}" not in brief.html


def test_a_day_without_briefing_bullets_is_not_sent():
    with pytest.raises(EmailError, match="no stored briefing"):
        render_email(_snapshot(bullets=[" ", ""]))


@pytest.mark.parametrize(
    ("day", "expected"),
    [("2026-10-26", [11, 22]), ("2026-10-27", [11]), ("2026-11-01", [11])],
)
def test_weekly_subscribers_get_only_mondays_brief(day, expected):
    # 2026-10-26 is a Monday; the Weekly segment rides along only then (#979).
    assert segment_ids_for(day, 11, 22) == expected


def test_one_segment_id_for_both_cadences_is_refused():
    with pytest.raises(EmailError, match="must differ"):
        segment_ids_for("2026-10-26", 5, 5)


def test_the_broadcast_targets_segments_and_is_never_public():
    brief = render_email(_snapshot())
    when = datetime(2026, 10, 26, 8, 10, tzinfo=UTC)
    body = broadcast_body(brief, [11, 22], send_at=when)
    assert body["public"] is False
    assert body["send_at"] == "2026-10-26T08:10:00+00:00"
    assert body["subscriber_filter"] == [{"any": [{"type": "segment", "ids": [11, 22]}]}]
    assert broadcast_body(brief, [11], send_at=None)["send_at"] is None


def _fake_kit(monkeypatch, responses: list):
    calls = []

    def fake(method, path, api_key, body=None):
        calls.append((method, path, body))
        return responses.pop(0)

    monkeypatch.setattr(email_brief, "_kit", fake)
    return calls


def test_segments_must_exist_under_their_names(monkeypatch):
    page = {
        "segments": [{"id": 11, "name": "Daily"}, {"id": 22, "name": "Weekly"}],
        "pagination": {"has_next_page": False},
    }
    _fake_kit(monkeypatch, [page])
    check_segments("key", 11, 22)
    _fake_kit(monkeypatch, [page])
    with pytest.raises(EmailError, match="should be named 'Weekly'"):
        check_segments("key", 11, 99)


def test_segment_lookup_follows_pagination(monkeypatch):
    calls = _fake_kit(
        monkeypatch,
        [
            {
                "segments": [{"id": 11, "name": "Daily"}],
                "pagination": {"has_next_page": True, "end_cursor": "abc"},
            },
            {"segments": [{"id": 22, "name": "Weekly"}], "pagination": {"has_next_page": False}},
        ],
    )
    check_segments("key", 11, 22)
    assert calls[1][1].endswith("&after=abc")


def test_a_cursor_with_base64_symbols_is_url_encoded(monkeypatch):
    calls = _fake_kit(
        monkeypatch,
        [
            {
                "segments": [{"id": 11, "name": "Daily"}],
                "pagination": {"has_next_page": True, "end_cursor": "Wzc+XQ=="},
            },
            {"segments": [{"id": 22, "name": "Weekly"}], "pagination": {"has_next_page": False}},
        ],
    )
    check_segments("key", 11, 22)
    assert calls[1][1].endswith("&after=Wzc%2BXQ%3D%3D")


def test_a_scheduled_send_must_come_back_with_an_id_and_a_send_time(monkeypatch):
    brief = render_email(_snapshot())
    body = broadcast_body(brief, [11], send_at=datetime(2026, 10, 26, 8, 10, tzinfo=UTC))
    _fake_kit(monkeypatch, [{"broadcast": {"id": 7, "send_at": "2026-10-26T08:10:00Z"}}])
    assert create_broadcast("key", body)["id"] == 7
    _fake_kit(monkeypatch, [{"broadcast": {}}])
    with pytest.raises(EmailError, match="no broadcast id"):
        create_broadcast("key", body)
    _fake_kit(monkeypatch, [{"broadcast": {"id": 8, "send_at": None}}])
    with pytest.raises(EmailError, match="without a send time"):
        create_broadcast("key", body)


def _write_snapshot(tmp_path: Path) -> Path:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    real = sorted(Path("data/snapshots").glob("*.json"))[-1]
    (snapshots / real.name).write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    return snapshots


def test_preview_renders_without_any_kit_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("KIT_API_KEY", raising=False)
    snapshots = _write_snapshot(tmp_path)
    day = json.loads(next(snapshots.glob("*.json")).read_text(encoding="utf-8"))["date"]
    out = tmp_path / "email.html"
    code = email_brief.main(["--date", day, "--snapshots", str(snapshots), "--out", str(out)])
    assert code == 0
    assert f"/blog/{day}/" in out.read_text(encoding="utf-8")


def test_a_live_mode_without_credentials_fails_before_calling_kit(tmp_path, monkeypatch):
    monkeypatch.delenv("KIT_API_KEY", raising=False)
    monkeypatch.setattr(email_brief, "_kit", lambda *a, **k: pytest.fail("Kit was called"))
    snapshots = _write_snapshot(tmp_path)
    day = json.loads(next(snapshots.glob("*.json")).read_text(encoding="utf-8"))["date"]
    args = ["--date", day, "--snapshots", str(snapshots), "--out", str(tmp_path / "e.html")]
    assert email_brief.main([*args, "--mode", "send"]) == 1


def test_a_missing_snapshot_day_is_an_error(tmp_path):
    snapshots = _write_snapshot(tmp_path)
    out = tmp_path / "e.html"
    args = ["--date", "1999-01-01", "--snapshots", str(snapshots), "--out", str(out)]
    assert email_brief.main(args) == 1
    assert not out.exists()


def test_the_workflow_records_the_day_before_it_calls_kit():
    """A lost Kit response must block a resend, so the tag push comes first."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    preflight = workflow.index("--preflight")
    tag_push = workflow.index('git push --porcelain "$remote"')
    send = workflow.index("- name: Send or save to Kit")
    # Checks that can fail run before the day is recorded; the POST runs after.
    assert preflight < tag_push < send
    # Only a git "absent" answer (exit 2) may lead to a send.
    assert 'elif [ "$ls_code" -ne 2 ]; then' in workflow
    assert "persist-credentials: false" in workflow
    assert re.search(r'^\s+- cron: "0 8 \* \* \*"$', workflow, re.M)
    assert "cancel-in-progress: false" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    # The key reaches only the two steps that call Kit, and a preview gets none.
    assert workflow.count("secrets.KIT_API_KEY") == 2
    assert "steps.plan.outputs.mode != 'preview' && secrets.KIT_API_KEY || ''" in workflow
    # Manual runs default to a preview that touches nothing.
    assert re.search(r"options: \[preview, draft, send\]\n\s+default: preview", workflow)


def test_preflight_checks_segments_but_never_creates_a_broadcast(tmp_path, monkeypatch):
    snapshots = _write_snapshot(tmp_path)
    day = json.loads(next(snapshots.glob("*.json")).read_text(encoding="utf-8"))["date"]
    monkeypatch.setenv("KIT_API_KEY", "key")
    monkeypatch.setenv("KIT_DAILY_SEGMENT_ID", "11")
    monkeypatch.setenv("KIT_WEEKLY_SEGMENT_ID", "22")
    calls = _fake_kit(
        monkeypatch,
        [
            {
                "segments": [{"id": 11, "name": "Daily"}, {"id": 22, "name": "Weekly"}],
                "pagination": {"has_next_page": False},
            }
        ],
    )
    args = ["--date", day, "--snapshots", str(snapshots), "--out", str(tmp_path / "e.html")]
    assert email_brief.main([*args, "--mode", "send", "--preflight"]) == 0
    assert [method for method, _, _ in calls] == ["GET"]


def test_the_live_check_does_not_pipe_curl_into_grep_q():
    """Under pipefail, `curl | grep -q` fails on a match, so a live brief never sent."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"curl[^\n|]*\|\s*grep -q", workflow)
    assert 'page="$(curl -fsS --max-time 30 "$url" || true)"' in workflow


@pytest.mark.parametrize("case", ["no_share", "share", "no_candidates"])
def test_email_and_blog_headings_share_the_committed_history(tmp_path, monkeypatch, case):
    from benchmark_radar.blog import build_posts
    from benchmark_radar.snapshots import load_snapshots

    def item(name, score):
        return {
            "source": "arXiv",
            "source_id": name,
            "title": f"{name}: a benchmark release",
            "url": f"https://example.org/{score}",
            "published_at": "2026-10-25T00:00:00Z",
            "event_kind": "released",
            "categories": [],
            "metrics": {},
            "evidence_score": 0,
            "relevance_score": 0,
            "recency_score": 0,
            "adoption_score": 0,
            "total_score": score,
            "rationale": [],
        }

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    old = item("OldBench", 99)
    new = item("New & Safe Bench", 80)
    for day, items in [("2026-10-25", [old]), ("2026-10-26", [old, new])]:
        snapshot = _snapshot(day)
        snapshot.update(
            schema_version=2,
            since=f"{day}T00:00:00Z",
            evidence_items=[] if case == "no_candidates" else items,
            attention={"observations": []},
            ingest_health=[],
            producer_health=[],
            discovery_state={},
        )
        snapshot["briefing"]["date"] = day
        if case == "share":
            snapshot["share"] = {"cards": [{"title": "CardBench: a stored share pick"}]}
        (snapshots / f"{day}.json").write_text(json.dumps(snapshot), encoding="utf-8")

    days = load_snapshots(snapshots)
    post = next(post for post in build_posts(days) if post.slug == "2026-10-26")
    if case == "no_share":
        assert post.title == "AI benchmark news: New & Safe Bench · Oct 26, 2026"
    elif case == "share":
        assert post.title == "AI benchmark news: CardBench · Oct 26, 2026"
    else:
        assert post.title == "Daily AI benchmark brief: 2026-10-26"

    monkeypatch.setattr(email_brief, "_kit", lambda *a, **k: pytest.fail("Kit was called"))
    out = tmp_path / "email.html"
    assert (
        email_brief.main(["--date", "2026-10-26", "--snapshots", str(snapshots), "--out", str(out)])
        == 0
    )
    rendered = out.read_text(encoding="utf-8")
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", rendered).group(1)
    assert html.unescape(heading) == post.title
    assert heading == html.escape(post.title, quote=True)
    assert 'href="https://benchmark-radar.org/blog/2026-10-26/"' in rendered
