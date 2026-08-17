"""Simplified Chinese rendering of the dashboard's validated English prose.

Issue #231: the dashboard's interface chrome (labels, buttons, help text) is
translated in the browser through the I18N table in site/assets/app.js, but the
daily briefing and the Q&A answers are model prose generated at runtime, so a
Chinese reader toggling the interface still saw English paragraphs. This module
translates that prose on the same run that generates it, one extra OpenAI call
each for the briefing and for the Q&A answers.

The English text is the source of truth: it was validated against the evidence
packet and the stat registry before this module runs. Translation therefore
re-validates the output instead of trusting it. Any translation that drops,
renames, or reorders an E###/S### id or a quantity is rejected, and the day
keeps only the English rendering.

A rounding hazard deserves its own rule: Chinese numerals (三, 二十) are never
allowed, because the dashboard and the report print figures from the registry
and the Q&A validator rejects prose that states a number the registry does not
hold. The translator must carry every Arabic digit run over verbatim.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .briefing import (
    DEFAULT_BRIEFING_MODEL,
    RESPONSES_URL,
    BriefingError,
    _extract_response_text,
    _output_text,
    _request_token_estimate,
    _usage,
)
from .http import post_json

# Sizing note (issue #231): the briefing's own generation is budgeted at
# 60,000 request tokens and 4,000 output tokens. A translation call repeats
# the day's prose, not its evidence packet, so it needs far less headroom.
MAX_ZH_REQUEST_TOKENS = 30_000
MAX_ZH_OUTPUT_TOKENS = 4_000
# Generation assembles a bullet from an 800-char finding and an 800-char
# rationale plus markers (briefing.py), so an assembled bullet can reach
# roughly 1,700 chars. The zh rendering is capped at the same ceiling rather
# than a shorter one, or long valid briefings would silently lose their
# Chinese rendering every day.
MAX_BULLET_CHARS = 1_800
MAX_ZH_CAVEAT_CHARS = 1_400
MAX_ZH_ANSWER_CHARS = 900

_ZH_INSTRUCTIONS = (
    "Role: You are the translator for the AI Benchmark Radar dashboard.\n\n"
    "You translate validated English prose into natural, fluent Simplified Chinese "
    "(zh-CN). The English text you receive is the source of truth: every fact, "
    "quantity, citation, and caveat in it was verified before it reached you, so you "
    "translate meaning and never add, drop, soften, or reorder anything.\n\n"
    "Hard rules, in priority order:\n"
    "1. Preserve every token of the form E### (evidence id) or S### (statistic id) "
    "exactly, including the leading letter.\n"
    "2. Preserve every run of Arabic digits exactly, including its sign, "
    "decimals, percentages, and thousands separators (-5%, 3, 20, 40, 12.5, 40%, "
    "4,000). Never write a quantity "
    "with a Chinese numeral such as 三 or 二十. The translated prose must contain "
    "exactly the same Arabic digit runs as the English.\n"
    "3. For briefing bullets, keep the English structural markers exactly as written: "
    "the phrases \"Why it matters:\" and \"Evidence:\", and the trailing confidence "
    "phrase such as \"High confidence.\" or \"Medium confidence.\". Translate only the "
    "prose around them. The dashboard splits bullets on these markers.\n"
    "4. Keep proper nouns that are identifiers or names (benchmark names, repository "
    "names, model names, paper titles) as-is or in their common English form.\n"
    "5. Write idiomatic Simplified Chinese that a reader familiar with AI evaluation "
    "would understand.\n\n"
    "Output: the fields defined by the schema. bullets_zh must have exactly as many "
    "entries as the input bullets, in the same order. answers_zh must have exactly as "
    "many entries as the input answers, each carrying the same index."
)

_BULLET_MARKERS = ("Why it matters:", "Evidence:")
_CONFIDENCE_LEVEL = re.compile(r"\b(High|Medium|Low|Moderate|Mixed)\s+confidence\.?\s*$")
_ID_TOKEN = re.compile(r"\b[ES]\d{3}\b")
# Mirrors the English Q&A validator's number shape so the same "every digit
# survives" check works in either language. Sign and percent sign are part of
# the quantity (-5% and 5 are different measurements); thousands separators
# are normalized away so 4,000 and 4000 compare equal.
_DIGIT_RUN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")

# One prose field per answer, in the shape the dashboard reads. The zh name of
# the plain-English field stays `plain_chinese` because the answer already
# carries plain_english; the rest mirror the English field with a _zh suffix.
_ANSWER_FIELD_PAIRS = (
    ("signal", "signal_zh"),
    ("plain_english", "plain_chinese"),
    ("takeaway", "takeaway_zh"),
    ("counter_view", "counter_view_zh"),
)
# The zh field names the snapshot carries per answer; the dashboard reads these
# exact keys. Exported so questions.py can attach them without re-declaring.
ZH_ANSWER_FIELDS = tuple(zh_field for _, zh_field in _ANSWER_FIELD_PAIRS)

_BRIEFING_ZH_SCHEMA = {
    "type": "object",
    "properties": {
        "bullets_zh": {"type": "array", "items": {"type": "string"}},
        "caveat_zh": {"type": "string"},
    },
    "required": ["bullets_zh", "caveat_zh"],
    "additionalProperties": False,
}

_ANSWERS_ZH_SCHEMA = {
    "type": "object",
    "properties": {
        "answers_zh": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "signal_zh": {"type": "string"},
                    "plain_chinese": {"type": "string"},
                    "takeaway_zh": {"type": "string"},
                    "counter_view_zh": {"type": "string"},
                },
                "required": [
                    "index",
                    "signal_zh",
                    "plain_chinese",
                    "takeaway_zh",
                    "counter_view_zh",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["answers_zh"],
    "additionalProperties": False,
}


def _payload(
    model: str, serialized: str, schema: dict[str, Any], schema_name: str
) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": _ZH_INSTRUCTIONS,
        "input": serialized,
        "reasoning": {"effort": "medium"},
        "text": {
            "verbosity": "medium",
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        "max_output_tokens": MAX_ZH_OUTPUT_TOKENS,
        "store": False,
    }


def _digit_runs(text: str) -> list[str]:
    """Every quantity in a piece of prose, thousands separators normalized."""
    return sorted(token.replace(",", "") for token in _DIGIT_RUN.findall(text))


def _require_zh_text(value: Any, *, field: str, max_chars: int) -> str:
    """A translation that comes back empty is a failure, not prose to store.

    An empty zh field would pass grounding on a digit-free English original
    and then fail snapshot validation at save time, so it is rejected here,
    where the caller can still fall back to the English rendering.
    """
    text = _output_text(value, field=field, max_chars=max_chars)
    if not text:
        raise BriefingError(f"zh translation returned an empty {field}")
    return text


def _check_grounding(en_text: str, zh_text: str, field: str) -> None:
    """Reject a translation that dropped, renamed, or changed an id or a number."""
    if set(_ID_TOKEN.findall(en_text)) != set(_ID_TOKEN.findall(zh_text)):
        raise BriefingError(
            f"zh translation of {field} dropped or changed an E###/S### id"
        )
    if _digit_runs(en_text) != _digit_runs(zh_text):
        raise BriefingError(
            f"zh translation of {field} changed a quantity; every Arabic digit "
            "must survive verbatim"
        )


def _check_bullet(en_bullet: str, zh_bullet: str) -> None:
    """Reject a translated bullet the dashboard's splitter could not parse."""
    for marker in _BULLET_MARKERS:
        if marker in en_bullet and marker not in zh_bullet:
            raise BriefingError(f"zh briefing bullet dropped the marker {marker!r}")
    en_confidence = _CONFIDENCE_LEVEL.search(en_bullet)
    if en_confidence:
        zh_confidence = _CONFIDENCE_LEVEL.search(zh_bullet)
        if not zh_confidence:
            raise BriefingError("zh briefing bullet dropped the confidence marker")
        # Presence alone is not enough: the dashboard publishes this level, so
        # translating "Medium confidence." as "High confidence." would put a
        # fabricated reading on the page.
        if zh_confidence.group(1).lower() != en_confidence.group(1).lower():
            raise BriefingError("zh briefing bullet changed the confidence level")
    _check_grounding(en_bullet, zh_bullet, "briefing bullet")


def _translate(
    packet: dict[str, Any],
    schema: dict[str, Any],
    schema_name: str,
    api_key: str,
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One translation call; returns (parsed object, provenance metadata)."""
    serialized = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    payload = _payload(model, serialized, schema, schema_name)
    request_tokens = _request_token_estimate(payload, model)
    if request_tokens > MAX_ZH_REQUEST_TOKENS:
        raise BriefingError("zh translation input exceeds the request token budget")
    response = post_json(
        RESPONSES_URL,
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
        attempts=4,
        timeout=90.0,
    )
    try:
        parsed = json.loads(_extract_response_text(response))
    except json.JSONDecodeError as error:
        raise BriefingError("OpenAI zh translation output is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise BriefingError("OpenAI zh translation output is not an object")
    return parsed, {
        "model": str(response.get("model") or model),
        "response_id": str(response.get("id") or ""),
        "usage": _usage(response),
    }


def translate_briefing_to_zh(
    bullets: list[str],
    caveat: str,
    api_key: str,
    *,
    model: str = DEFAULT_BRIEFING_MODEL,
) -> dict[str, Any]:
    """Translate one day's validated briefing bullets and caveat into Chinese.

    Returns the zh prose plus the translation call's provenance. Raises
    BriefingError on any structural or grounding violation so the caller can
    fall back to the English-only briefing.
    """
    en_bullets = [
        _output_text(bullet, field="briefing bullet", max_chars=MAX_BULLET_CHARS)
        for bullet in bullets
    ]
    en_caveat = _output_text(caveat, field="caveat", max_chars=1_000)
    parsed, meta = _translate(
        {"bullets": en_bullets, "caveat": en_caveat},
        _BRIEFING_ZH_SCHEMA,
        "daily_radar_briefing_zh",
        api_key,
        model,
    )
    raw_bullets = parsed.get("bullets_zh") or []
    if len(raw_bullets) != len(en_bullets):
        raise BriefingError("zh briefing returned the wrong number of bullets")
    bullets_zh = [
        _require_zh_text(item, field="bullet_zh", max_chars=MAX_BULLET_CHARS)
        for item in raw_bullets
    ]
    for en, zh in zip(en_bullets, bullets_zh, strict=True):
        _check_bullet(en, zh)
    result = {**meta, "bullets_zh": bullets_zh}
    # An empty caveat is a legitimate briefing shape (the day had insights but
    # no caveat), so it is skipped rather than translated; a non-empty caveat
    # whose zh rendering comes back empty is a translation failure.
    if en_caveat:
        caveat_zh = _require_zh_text(
            parsed.get("caveat_zh"), field="caveat_zh", max_chars=MAX_ZH_CAVEAT_CHARS
        )
        _check_grounding(en_caveat, caveat_zh, "caveat")
        result["caveat_zh"] = caveat_zh
    return result


def translate_answers_to_zh(
    answers: list[dict[str, Any]],
    api_key: str,
    *,
    model: str = DEFAULT_BRIEFING_MODEL,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Translate every prose field of one day's answers in a single call.

    Returns (zh answers aligned to the input by position, provenance). Raises
    BriefingError on a count, shape, or grounding violation.
    """
    en_answers = []
    for index, answer in enumerate(answers):
        en_answers.append(
            {
                "index": index,
                **{
                    en_field: _output_text(
                        answer.get(en_field), field=en_field, max_chars=MAX_ZH_ANSWER_CHARS
                    )
                    for en_field, _ in _ANSWER_FIELD_PAIRS
                },
            }
        )
    parsed, meta = _translate(
        {"answers": en_answers},
        _ANSWERS_ZH_SCHEMA,
        "daily_radar_answers_zh",
        api_key,
        model,
    )
    raw = parsed.get("answers_zh") or []
    if len(raw) != len(en_answers):
        raise BriefingError("zh translation returned the wrong number of answers")
    try:
        by_index = {int(item.get("index")): item for item in raw}
    except (TypeError, ValueError) as error:
        raise BriefingError("zh translation returned a malformed answer index") from error
    translated: list[dict[str, Any]] = []
    for index, en_answer in enumerate(en_answers):
        item = by_index.get(index)
        if not isinstance(item, dict):
            raise BriefingError("zh translation returned a malformed answer")
        zh_answer: dict[str, Any] = {"index": index}
        for en_field, zh_field in _ANSWER_FIELD_PAIRS:
            en_value = en_answer[en_field]
            if not en_value:
                # Nothing to translate; leave the zh field absent so the
                # dashboard falls back to the (empty) English field.
                continue
            value = _require_zh_text(
                item.get(zh_field), field=zh_field, max_chars=MAX_ZH_ANSWER_CHARS
            )
            _check_grounding(en_value, value, zh_field)
            zh_answer[zh_field] = value
        translated.append(zh_answer)
    return translated, meta