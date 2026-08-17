"""The zh translation pass re-validates grounding it claims to preserve."""

import json

import pytest

from benchmark_radar.briefing import BriefingError
from benchmark_radar.translate_zh import translate_answers_to_zh, translate_briefing_to_zh


def _fake_response(text: str) -> dict:
    return {
        "id": "resp_zh",
        "model": "gpt-5.6-2026-08-01",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 5},
        },
    }


def _run(monkeypatch, payload: dict) -> None:
    def fake_post(url, body, **kwargs):
        assert url == "https://api.openai.com/v1/responses"
        return _fake_response(json.dumps(payload))

    monkeypatch.setattr("benchmark_radar.translate_zh.post_json", fake_post)


_EN_BULLET = (
    "Memory evaluation is moving toward persistence. Why it matters: Teams need "
    "longitudinal tests. Evidence: E001. High confidence."
)
_ZH_BULLET = (
    "记忆评估正在向持久化方向发展。Why it matters: 团队需要纵向测试。"
    "Evidence: E001. High confidence."
)


def test_briefing_translation_preserves_markers_ids_and_digits(monkeypatch):
    _run(monkeypatch, {"bullets_zh": [_ZH_BULLET], "caveat_zh": "仅一个发布。"})

    result = translate_briefing_to_zh(
        [_EN_BULLET], "One captured release does not establish a trend.", "k", model="gpt-5.6"
    )

    assert result["bullets_zh"] == [_ZH_BULLET]
    assert result["caveat_zh"] == "仅一个发布。"
    assert result["response_id"] == "resp_zh"
    assert result["usage"]["total_tokens"] == 150


def test_briefing_translation_rejects_a_dropped_marker(monkeypatch):
    dropped = "记忆评估正在向持久化方向发展。团队需要纵向测试。Evidence: E001. High confidence."
    _run(monkeypatch, {"bullets_zh": [dropped], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="dropped the marker"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_rejects_a_changed_evidence_id(monkeypatch):
    changed = _ZH_BULLET.replace("E001", "E002")
    _run(monkeypatch, {"bullets_zh": [changed], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="dropped or changed an E###/S### id"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_rejects_a_chinese_numeral(monkeypatch):
    # The quantity 3 must survive as the Arabic digit; a Chinese numeral is a
    # rounding hazard because the dashboard prints figures from the registry.
    en = "3 suites arrived. Why it matters: Choice widens. Evidence: E001. Low confidence."
    zh = "三个套件到达。Why it matters: 选择变多。Evidence: E001. Low confidence."
    _run(monkeypatch, {"bullets_zh": [zh], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="changed a quantity"):
        translate_briefing_to_zh([en], "caveat", "k")


def test_briefing_translation_rejects_a_missing_confidence_marker(monkeypatch):
    no_confidence = _ZH_BULLET.replace(" High confidence.", "")
    _run(monkeypatch, {"bullets_zh": [no_confidence], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="confidence marker"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_rejects_a_changed_confidence_level(monkeypatch):
    # Presence alone is not enough: swapping Medium for High would publish a
    # fabricated confidence reading on the dashboard.
    swapped = _ZH_BULLET.replace("High confidence.", "Medium confidence.")
    _run(monkeypatch, {"bullets_zh": [swapped], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="confidence level"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_rejects_an_empty_bullet(monkeypatch):
    _run(monkeypatch, {"bullets_zh": [""], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="empty bullet_zh"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_rejects_an_empty_caveat(monkeypatch):
    _run(monkeypatch, {"bullets_zh": [_ZH_BULLET], "caveat_zh": ""})

    with pytest.raises(BriefingError, match="empty caveat_zh"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_briefing_translation_omits_caveat_zh_when_the_english_caveat_is_empty(monkeypatch):
    # A day with insights but no caveat is legitimate; the zh field is left
    # absent rather than stored empty (snapshot validation rejects empties).
    _run(monkeypatch, {"bullets_zh": [_ZH_BULLET], "caveat_zh": ""})

    result = translate_briefing_to_zh([_EN_BULLET], "", "k")

    assert result["bullets_zh"] == [_ZH_BULLET]
    assert "caveat_zh" not in result


def test_briefing_translation_rejects_a_dropped_sign(monkeypatch):
    en = "Downloads fell -5% today. Why it matters: Usage cooled. Evidence: E001. Low confidence."
    zh = "下载量今日上升 5%。Why it matters: 使用降温。Evidence: E001. Low confidence."
    _run(monkeypatch, {"bullets_zh": [zh], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="changed a quantity"):
        translate_briefing_to_zh([en], "caveat", "k")


def test_briefing_translation_rejects_a_dropped_percent_sign(monkeypatch):
    en = "Coverage reached 40% today. Why it matters: Gaps narrow. Evidence: E001. Low confidence."
    zh = "覆盖率今日达到 40。Why it matters: 差距缩小。Evidence: E001. Low confidence."
    _run(monkeypatch, {"bullets_zh": [zh], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="changed a quantity"):
        translate_briefing_to_zh([en], "caveat", "k")


def test_briefing_translation_accepts_a_fully_assembled_long_bullet(monkeypatch):
    # Generation assembles a bullet from an 800-char finding plus an 800-char
    # rationale, so the translator must accept bullets well past 800 chars or
    # every long briefing would silently lose its Chinese rendering.
    finding = "Long finding. " * 57
    why = "Long rationale. " * 50
    en = f"{finding} Why it matters: {why} Evidence: E001. High confidence."
    zh_finding = "这是一个很长的中文发现。" * 57
    zh_why = "这是一条很长的中文理由。" * 50
    zh = f"{zh_finding} Why it matters: {zh_why} Evidence: E001. High confidence."
    assert len(en) > 800
    _run(monkeypatch, {"bullets_zh": [zh], "caveat_zh": "x"})

    result = translate_briefing_to_zh([en], "caveat", "k")

    assert result["bullets_zh"] == [zh]


def test_briefing_translation_rejects_a_wrong_bullet_count(monkeypatch):
    _run(monkeypatch, {"bullets_zh": [_ZH_BULLET, _ZH_BULLET], "caveat_zh": "x"})

    with pytest.raises(BriefingError, match="wrong number of bullets"):
        translate_briefing_to_zh([_EN_BULLET], "caveat", "k")


def test_answers_translation_aligns_every_prose_field_by_index(monkeypatch):
    answers = [
        {
            "signal": "Most of today's records are agentic harnesses.",
            "plain_english": "Most new items test task execution, not recall.",
            "takeaway": "Expect setup cost, not just a scorer.",
            "counter_view": "The feed is keyword-filtered.",
        },
        {
            "signal": "Scoring documentation is mostly absent.",
            "plain_english": "We cannot tell how correctness is judged.",
            "takeaway": "Treat unscored arrivals as unverified.",
            "counter_view": "No credible counter-view found.",
        },
    ]
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": 0,
                    "signal_zh": "今天的记录大多是智能体框架。",
                    "plain_chinese": "大多数新条目测试的是任务执行而非记忆。",
                    "takeaway_zh": "预期成本在于搭建。",
                    "counter_view_zh": "该流按关键词过滤。",
                },
                {
                    "index": 1,
                    "signal_zh": "评分文档大多缺失。",
                    "plain_chinese": "我们无法判断正确性如何判定。",
                    "takeaway_zh": "将未评分条目视为未经核实。",
                    "counter_view_zh": "未找到可信的反方观点。",
                },
            ]
        },
    )

    zh, meta = translate_answers_to_zh(answers, "k", model="gpt-5.6")

    assert [item["index"] for item in zh] == [0, 1]
    assert zh[0]["signal_zh"] == "今天的记录大多是智能体框架。"
    assert zh[1]["counter_view_zh"] == "未找到可信的反方观点。"
    assert meta["response_id"] == "resp_zh"


def test_answers_translation_rejects_a_dropped_digit(monkeypatch):
    answers = [
        {
            "signal": "40 records arrived today.",
            "plain_english": "Forty items.",
            "takeaway": "Expect setup.",
            "counter_view": "Filtered feed.",
        }
    ]
    # The model rendered the 40 as a Chinese numeral in the translated signal.
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": 0,
                    "signal_zh": "今天到达了四十条记录。",
                    "plain_chinese": "四十个条目。",
                    "takeaway_zh": "预期搭建。",
                    "counter_view_zh": "过滤后的流。",
                }
            ]
        },
    )

    with pytest.raises(BriefingError, match="changed a quantity"):
        translate_answers_to_zh(answers, "k")


def test_answers_translation_rejects_a_wrong_answer_count(monkeypatch):
    answers = [
        {
            "signal": "One signal.",
            "plain_english": "One.",
            "takeaway": "One.",
            "counter_view": "None.",
        }
    ]
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": 0,
                    "signal_zh": "一个信号。",
                    "plain_chinese": "一个。",
                    "takeaway_zh": "一个。",
                    "counter_view_zh": "无。",
                },
                {
                    "index": 1,
                    "signal_zh": "另一个。",
                    "plain_chinese": "另一个。",
                    "takeaway_zh": "另一个。",
                    "counter_view_zh": "无。",
                },
            ]
        },
    )

    with pytest.raises(BriefingError, match="wrong number of answers"):
        translate_answers_to_zh(answers, "k")


def test_answers_translation_rejects_a_malformed_index(monkeypatch):
    """A missing or non-numeric index must fail as a BriefingError, not leak a
    TypeError up to the generator that called the translator."""
    answers = [
        {
            "signal": "One signal.",
            "plain_english": "One.",
            "takeaway": "One.",
            "counter_view": "None.",
        }
    ]
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": "zero",
                    "signal_zh": "一个信号。",
                    "plain_chinese": "一个。",
                    "takeaway_zh": "一个。",
                    "counter_view_zh": "无。",
                }
            ]
        },
    )

    with pytest.raises(BriefingError, match="malformed answer index"):
        translate_answers_to_zh(answers, "k")


def test_answers_translation_rejects_an_empty_zh_field(monkeypatch):
    answers = [
        {
            "signal": "One signal.",
            "plain_english": "One.",
            "takeaway": "One.",
            "counter_view": "None.",
        }
    ]
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": 0,
                    "signal_zh": "",
                    "plain_chinese": "一个。",
                    "takeaway_zh": "一个。",
                    "counter_view_zh": "无。",
                }
            ]
        },
    )

    with pytest.raises(BriefingError, match="empty signal_zh"):
        translate_answers_to_zh(answers, "k")


def test_answers_translation_omits_zh_fields_for_empty_english_fields(monkeypatch):
    # An answer field that is empty in English has nothing to translate; the zh
    # field is left absent so the dashboard falls back per field, and the empty
    # string never reaches snapshot validation.
    answers = [
        {
            "signal": "",
            "plain_english": "One.",
            "takeaway": "One.",
            "counter_view": "None.",
        }
    ]
    _run(
        monkeypatch,
        {
            "answers_zh": [
                {
                    "index": 0,
                    "signal_zh": "",
                    "plain_chinese": "一个。",
                    "takeaway_zh": "一个。",
                    "counter_view_zh": "无。",
                }
            ]
        },
    )

    zh, _ = translate_answers_to_zh(answers, "k")

    assert "signal_zh" not in zh[0]
    assert zh[0]["plain_chinese"] == "一个。"
