import json
import re
from datetime import UTC, datetime

import pytest
import tiktoken

from benchmark_radar.briefing import (
    _INSTRUCTIONS,
    MAX_ATTENTION_ITEMS,
    MAX_BULLETS,
    MAX_FINDING_CHARS,
    MAX_INPUT_CHARS,
    MAX_METRIC_KEY_CHARS,
    MAX_METRIC_KEYS,
    MAX_METRIC_VALUE_CHARS,
    MAX_REQUEST_TOKENS,
    MAX_WHY_CHARS,
    BriefingError,
    _capped_metrics,
    _output_text,
    _payload,
    _request_token_estimate,
    briefing_input,
    current_day_snapshot,
    daily_report_run,
    generate_daily_briefing,
    markdown_bullet,
    previous_calendar_day,
)
from benchmark_radar.models import AttentionObservation, RadarItem, RadarRun
from benchmark_radar.snapshots import merge_snapshots, snapshot_for_run


def _item(index: int, *, title: str | None = None) -> RadarItem:
    return RadarItem(
        source="GitHub",
        source_id=f"org/repo-{index}",
        title=title or f"Benchmark {index}",
        url=f"https://github.com/org/repo-{index}",
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
    )


def _attention(index: int) -> AttentionObservation:
    observed = datetime(2026, 8, 4, tzinfo=UTC)
    return AttentionObservation(
        observation_id=f"producer:{index}",
        producer="producer",
        source="Hacker News",
        source_id=str(index),
        title=f"Discussion {index}",
        url=f"https://news.ycombinator.com/item?id={index}",
        published_at=observed,
        discovered_at=observed,
        observed_at=observed,
    )


def _run(items=None) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 8, 4, 12, tzinfo=UTC),
        since=datetime(2026, 8, 2, 12, tzinfo=UTC),
        items=items or [],
        health=[],
        selection={"taxonomy_version": "taxonomy-v2", "lookback_hours": 48},
    )


def test_previous_calendar_day_ignores_same_day_and_older_gap():
    snapshots = [
        {"date": "2026-08-01"},
        {"date": "2026-08-03"},
        {"date": "2026-08-04"},
    ]

    assert previous_calendar_day(snapshots, _run()) == {"date": "2026-08-03"}
    assert previous_calendar_day([snapshots[0], snapshots[2]], _run()) is None


def test_current_day_snapshot_merges_both_scheduled_passes():
    morning = snapshot_for_run(_run([_item(1)]))
    afternoon = _run([_item(2)])

    merged = current_day_snapshot([morning], afternoon)

    assert {item["source_id"] for item in merged["evidence_items"]} == {
        "org/repo-1",
        "org/repo-2",
    }


def test_current_day_snapshot_reranks_the_merged_items():
    morning_item = _item(1)
    morning_item.total_score = 50
    afternoon_item = _item(2)
    afternoon_item.total_score = 90

    merged = current_day_snapshot(
        [snapshot_for_run(_run([morning_item]))],
        _run([afternoon_item]),
    )

    assert [item["source_id"] for item in merged["evidence_items"]] == [
        "org/repo-2",
        "org/repo-1",
    ]


def test_current_day_snapshot_recomputes_badges_when_the_threshold_changes():
    morning_item = _item(1)
    morning_item.total_score = 45
    morning_item.recommended = True
    morning_run = _run([morning_item])
    morning_run.selection["recommendation_score"] = 40

    afternoon_item = _item(2)
    afternoon_item.total_score = 55
    afternoon_run = _run([afternoon_item])
    afternoon_run.selection["recommendation_score"] = 50

    merged = current_day_snapshot([snapshot_for_run(morning_run)], afternoon_run)

    recommended = {item["source_id"]: item["recommended"] for item in merged["evidence_items"]}
    assert recommended == {"org/repo-1": False, "org/repo-2": True}
    assert merged["selection"]["recommendation_score"] == 50


def test_current_day_snapshot_unions_attention_from_both_passes():
    morning_run = _run([_item(1)])
    morning_run.attention = [_attention(1)]
    afternoon_run = _run([_item(2)])
    afternoon_run.attention = [_attention(2)]

    merged = current_day_snapshot([snapshot_for_run(morning_run)], afternoon_run)

    assert {item["observation_id"] for item in merged["attention"]["observations"]} == {
        "producer:1",
        "producer:2",
    }


def test_daily_report_run_uses_the_merged_snapshot_scope():
    morning = snapshot_for_run(_run([_item(1)]))
    merged = current_day_snapshot([morning], _run([_item(2)]))

    report_run = daily_report_run(merged, _run([_item(2)]))

    assert {item.source_id for item in report_run.items} == {"org/repo-1", "org/repo-2"}
    assert report_run.selection["published_total"] == 2


def test_gpt_input_includes_descriptions_history_health_and_stable_evidence_ids():
    item = _item(1, title="MemoryBench: Long-horizon personal memory")
    item.summary = "Measures whether assistants preserve user preferences across long sessions."
    item.event_kind = "released"
    item.total_score = 77
    run = _run([item])
    fresh_attention = _attention(1)
    old_attention = _attention(2)
    old_attention.observed_at = datetime(2026, 8, 3, tzinfo=UTC)
    run.attention = [fresh_attention, old_attention]
    current = snapshot_for_run(run)
    current["ingest_health"] = [
        {"source": "github", "kind": "evidence", "ok": True, "item_count": 1},
        {"source": "hacker-news", "kind": "attention", "ok": True, "item_count": 2},
        {"source": "openreview", "kind": "evidence", "ok": False, "item_count": 0},
    ]

    value = briefing_input([current], current, ["Insufficient comparable history."])
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    assert len(encoded) <= MAX_INPUT_CHARS
    assert value["first_observed_evidence"][0]["id"] == "E001"
    assert "preserve user preferences" in value["first_observed_evidence"][0]["summary"]
    assert value["daily_series"][0]["measurement"]["taxonomy_version"] == "taxonomy-v2"
    assert value["daily_series"][0]["measurement"]["lookback_hours"] == 48
    assert value["daily_series"][0]["unavailable_sources"] == ["openreview"]
    assert value["daily_series"][0]["collection_signature"] == [
        "attention:hacker-news:ok",
        "evidence:github:ok",
        "evidence:openreview:failed",
    ]
    assert [signal["observed_today"] for signal in value["attention_signals"]] == [True, False]
    assert value["attention_signals"][1]["observed_at"].startswith("2026-08-03")
    assert value["category_composition_check"] == {
        "scope": (
            "Multi-day category-share shifts only. This check does not assess whether "
            "an individual new release or a group of today's releases is decision-useful."
        ),
        "result": ["Insufficient comparable history."],
    }


def test_gpt_input_ranks_releases_ahead_of_higher_scored_updates():
    updated = _item(1, title="Established benchmark update")
    updated.event_kind = "updated"
    updated.summary = "Adds another result to an established benchmark."
    updated.total_score = 99
    updated.recommended = True
    stronger_release = _item(2, title="Higher-priority new benchmark")
    stronger_release.event_kind = "released"
    stronger_release.summary = "Introduces a new evaluation protocol."
    stronger_release.total_score = 60
    weaker_release = _item(3, title="Lower-priority new benchmark")
    weaker_release.event_kind = "released"
    weaker_release.summary = "Introduces another new evaluation protocol."
    weaker_release.total_score = 20
    current = snapshot_for_run(_run([updated, weaker_release, stronger_release]))

    evidence = briefing_input([current], current, ["guardrail"])["first_observed_evidence"]

    assert [item["title"] for item in evidence] == [
        "Higher-priority new benchmark",
        "Lower-priority new benchmark",
        "Established benchmark update",
    ]


def test_gpt_input_excludes_summaryless_keyword_false_positives():
    relevant = _item(1, title="AgentBench: Tool-use evaluation")
    relevant.summary = "Measures AI agents completing multi-step tool tasks."
    relevant.event_kind = "released"
    false_positive = _item(
        2,
        title="Therapeutic agents against bacterial infection: biological evaluation",
    )
    false_positive.categories = ["evaluation", "agentic"]
    false_positive.summary = ""
    false_positive.event_kind = "released"
    current = snapshot_for_run(_run([false_positive, relevant]))

    value = briefing_input([current], current, ["guardrail"])
    titles = [item["title"] for item in value["first_observed_evidence"]]

    assert relevant.title in titles
    assert false_positive.title not in titles


def test_gpt_input_prioritizes_fresh_attention_before_the_cap():
    run = _run([_item(1)])
    old = [_attention(index) for index in range(1, MAX_ATTENTION_ITEMS + 2)]
    for item in old:
        item.observed_at = datetime(2026, 8, 3, tzinfo=UTC)
    fresh = _attention(99)
    run.attention = [*old, fresh]
    current = snapshot_for_run(run)

    signals = briefing_input([current], current, ["guardrail"])["attention_signals"]

    assert len(signals) == MAX_ATTENTION_ITEMS
    assert signals[0]["title"] == "Discussion 99"
    assert signals[0]["observed_today"] is True


def test_request_budget_counts_high_token_density_text():
    payload = _payload("gpt-5.6", "界" * 300_000)

    assert _request_token_estimate(payload, "gpt-5.6") > MAX_REQUEST_TOKENS


def test_request_budget_also_counts_server_character_estimate():
    payload = _payload("gpt-5.6", "a" * 1_100_000)

    assert _request_token_estimate(payload, "gpt-5.6") > MAX_REQUEST_TOKENS


def test_request_budget_has_an_offline_multibyte_fallback(monkeypatch):
    monkeypatch.setattr(
        "tiktoken.encoding_for_model", lambda model: (_ for _ in ()).throw(KeyError())
    )
    monkeypatch.setattr("tiktoken.get_encoding", lambda name: (_ for _ in ()).throw(OSError()))

    estimate = _request_token_estimate(_payload("gpt-5.6", "界" * 300_000), "gpt-5.6")

    assert estimate > MAX_REQUEST_TOKENS


def test_model_output_is_not_cut_mid_sentence_after_generation():
    complete = "A" * 420 + " complete ending."

    assert _output_text(complete, field="finding", max_chars=800) == complete


def test_output_text_rejects_oversize_prose_instead_of_cutting_it() -> None:
    with pytest.raises(BriefingError, match="overlong finding"):
        _output_text("A" * 801, field="finding", max_chars=800)


def test_generate_daily_briefing_uses_real_responses_contract_and_records_usage(monkeypatch):
    item = _item(1, title="MemoryBench: Long-horizon personal memory")
    item.summary = "Measures memory persistence."
    item.event_kind = "released"
    current = snapshot_for_run(_run([item]))
    captured = {}

    def fake_post(url, payload, **kwargs):
        captured.update(url=url, payload=payload, kwargs=kwargs)
        return {
            "id": "resp_real",
            "model": "gpt-5.6-2026-08-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "status": "insight",
                                    "insights": [
                                        {
                                            "finding": (
                                                "Memory evaluation is moving toward persistence."
                                            ),
                                            "why_it_matters": (
                                                "Teams need longitudinal tests, not "
                                                "single-session recall."
                                            ),
                                            "evidence_ids": ["E001"],
                                            "confidence": "medium",
                                        }
                                    ],
                                    "caveat": (
                                        "One captured release does not establish a "
                                        "field-wide trend."
                                    ),
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 8123,
                "output_tokens": 241,
                "total_tokens": 8364,
                "input_tokens_details": {"cached_tokens": 100},
                "output_tokens_details": {"reasoning_tokens": 80},
            },
        }

    monkeypatch.setattr("benchmark_radar.briefing.post_json", fake_post)

    result = generate_daily_briefing(
        [current],
        current,
        ["Insufficient comparable history."],
        "secret",
    )

    assert "Why it matters" in result.bullets[0]
    assert "Evidence: E001" in result.bullets[0]
    assert result.metadata["generator"] == "openai-responses"
    assert result.metadata["response_id"] == "resp_real"
    assert result.metadata["usage"]["input_tokens"] == 8123
    assert result.metadata["input"]["evidence_items"] == 1
    assert result.metadata["input"]["request_tokens_estimate"] <= MAX_REQUEST_TOKENS
    assert result.metadata["citations"][0]["url"] == item.url
    assert captured["payload"]["model"] == "gpt-5.6"
    assert captured["payload"]["reasoning"] == {"effort": "medium"}
    assert "between one and six evidence IDs" in captured["payload"]["instructions"]
    assert "identical collection_signature" in captured["payload"]["instructions"]
    assert "only when observed_today is true" in captured["payload"]["instructions"]
    assert "begin with first_observed_evidence" in captured["payload"]["instructions"]
    assert (
        "A negative category_composition_check alone is not sufficient"
        in captured["payload"]["instructions"]
    )
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert captured["payload"]["max_output_tokens"] == 16_000
    assert captured["payload"]["store"] is False
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer secret"}
    assert captured["kwargs"]["attempts"] == 5
    assert captured["kwargs"]["timeout"] == 90.0


def test_generate_daily_briefing_rejects_a_citation_not_in_the_injected_packet(monkeypatch):
    current = snapshot_for_run(_run([_item(1)]))

    monkeypatch.setattr(
        "benchmark_radar.briefing.post_json",
        lambda *args, **kwargs: {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "status": "insight",
                                    "insights": [
                                        {
                                            "finding": "Unsupported",
                                            "why_it_matters": "It does not.",
                                            "evidence_ids": ["E999"],
                                            "confidence": "low",
                                        }
                                    ],
                                    "caveat": "",
                                }
                            ),
                        }
                    ],
                }
            ]
        },
    )

    with pytest.raises(BriefingError, match="outside the injected packet"):
        generate_daily_briefing([current], current, ["guardrail"], "secret")


def test_generate_daily_briefing_rejects_insights_with_no_material_status(monkeypatch):
    current = snapshot_for_run(_run([_item(1)]))
    monkeypatch.setattr(
        "benchmark_radar.briefing.post_json",
        lambda *args, **kwargs: {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "status": "no_material_insight",
                                    "insights": [
                                        {
                                            "finding": "Contradictory finding",
                                            "why_it_matters": "It should not be published.",
                                            "evidence_ids": ["E001"],
                                            "confidence": "low",
                                        }
                                    ],
                                    "caveat": "No material insight.",
                                }
                            ),
                        }
                    ],
                }
            ]
        },
    )

    with pytest.raises(BriefingError, match="status contradicts"):
        generate_daily_briefing([current], current, ["guardrail"], "secret")


def test_snapshot_for_run_persists_the_briefing_with_its_day():
    run = _run([_item(1)])
    run.daily_briefing = ["One new benchmark.", "Evidence rose."]

    snapshot = snapshot_for_run(run)

    assert snapshot["briefing"] == {
        "date": "2026-08-04",
        "bullets": ["One new benchmark.", "Evidence rose."],
    }


def test_snapshot_for_run_omits_the_briefing_when_the_day_has_none():
    # An absent key is what tells a later pass the day still needs one, so it
    # must not be written as an empty placeholder.
    assert "briefing" not in snapshot_for_run(_run([_item(1)]))


def test_merge_snapshots_takes_the_recomputed_briefing_of_the_day():
    run = _run([_item(1)])
    run.daily_briefing = ["First pass."]
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_briefing = ["Second pass."]

    merged = merge_snapshots(existing, snapshot_for_run(later))

    # Findings are computed from the day's corpus (issue #127), and the incoming
    # pass derived its finding from the union this merge produces. Keeping the
    # first pass's text would persist a stale finding while the report and the
    # dashboard payload carried the recomputed one.
    assert merged["briefing"]["bullets"] == ["Second pass."]


def test_merge_snapshots_keeps_an_existing_briefing_when_the_incoming_pass_has_none():
    run = _run([_item(1)])
    run.daily_briefing = ["Already recorded."]
    existing = snapshot_for_run(run)

    merged = merge_snapshots(existing, snapshot_for_run(_run([_item(2)])))

    # A day never loses a briefing it already had.
    assert merged["briefing"]["bullets"] == ["Already recorded."]


def test_merge_snapshots_never_replaces_a_gpt_briefing_with_a_fallback():
    run = _run([_item(1)])
    run.daily_briefing = ["GPT synthesis."]
    run.daily_briefing_metadata = {"generator": "openai-responses", "model": "gpt-5.6"}
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_briefing = ["Deterministic finding."]
    later.daily_briefing_metadata = {"generator": "deterministic-fallback", "reason": "429"}

    merged = merge_snapshots(existing, snapshot_for_run(later))

    # A same-day rerun that hit a rate limit keeps the earlier GPT synthesis.
    assert merged["briefing"]["bullets"] == ["GPT synthesis."]
    assert merged["briefing"]["generator"] == "openai-responses"


def test_merge_snapshots_leaves_no_briefing_key_when_neither_pass_had_one():
    merged = merge_snapshots(snapshot_for_run(_run([_item(1)])), snapshot_for_run(_run([_item(2)])))

    assert "briefing" not in merged


def test_merge_snapshots_takes_the_recomputed_questions_of_the_day():
    run = _run([_item(1)])
    run.daily_questions = {"status": "generated", "groups": [{"id": "first"}]}
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_questions = {"status": "generated", "groups": [{"id": "second"}]}

    merged = merge_snapshots(existing, snapshot_for_run(later))

    assert merged["questions"]["groups"] == [{"id": "second"}]


def test_merge_snapshots_keeps_real_answers_when_the_incoming_pass_only_errored():
    # Issue #159: a day that already has real answers must not lose them to a
    # later pass's transient failure or a disabled second run.
    run = _run([_item(1)])
    run.daily_questions = {"status": "generated", "groups": [{"id": "first"}]}
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_questions = {"status": "error", "reason": "boom"}

    merged = merge_snapshots(existing, snapshot_for_run(later))

    assert merged["questions"]["status"] == "generated"
    assert merged["questions"]["groups"] == [{"id": "first"}]


def test_merge_snapshots_keeps_the_incoming_status_when_neither_pass_generated():
    run = _run([_item(1)])
    run.daily_questions = {"status": "disabled", "reason": "OPENAI_QUESTIONS is not enabled"}
    existing = snapshot_for_run(run)
    later = _run([_item(2)])
    later.daily_questions = {"status": "error", "reason": "boom"}

    merged = merge_snapshots(existing, snapshot_for_run(later))

    assert merged["questions"]["status"] == "error"


def test_markdown_bullet_escapes_interpolated_values():
    # Both model prose and source-derived values are data at this boundary.
    assert markdown_bullet("data_quality rose 5%") == "data\\_quality rose 5%"
    assert markdown_bullet("<img src=x> [link](http://evil.test)") == (
        "&lt;img src=x&gt; \\[link\\]\\(http://evil\\.test\\)"
    )


def _dated_run(items, *, day: int) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 8, day, 12, tzinfo=UTC),
        since=datetime(2026, 8, day - 1, 12, tzinfo=UTC),
        items=items,
        health=[],
        selection={"taxonomy_version": "taxonomy-v2", "lookback_hours": 48},
    )


def _metric_item(index: int, *, day: int, downloads: float) -> RadarItem:
    return RadarItem(
        source="Hugging Face",
        source_id=f"org/dataset-{index}",
        title=f"Benchmark dataset {index}",
        url=f"https://huggingface.co/datasets/org/dataset-{index}",
        published_at=datetime(2026, 8, day, tzinfo=UTC),
        categories=["benchmark"],
        summary="A scored evaluation dataset with documented tasks.",
        event_kind="updated",
        metrics={"downloads": downloads},
    )


def test_briefing_carries_artifacts_that_moved_since_they_were_first_seen():
    # The former packet supplied only first-seen items, so an artifact the
    # radar had watched all week was invisible no matter how much it moved.
    first = snapshot_for_run(_dated_run([_metric_item(1, day=4, downloads=100.0)], day=4))
    latest = snapshot_for_run(_dated_run([_metric_item(1, day=6, downloads=900.0)], day=6))

    packet = briefing_input([first, latest], latest, ["guardrail"])
    tracked = packet["tracked_artifacts"]

    assert [entry["title"] for entry in tracked] == ["Benchmark dataset 1"]
    assert tracked[0]["metric_deltas"] == {"downloads": 800.0}
    assert tracked[0]["seen_days"] == 2
    # The artifact is not first-seen today, so it reaches the model only as a
    # tracked record. That was the gap.
    assert packet["first_observed_evidence"] == []


def test_tracked_artifacts_omit_a_metric_that_lacks_both_endpoints():
    # A metric the connector only started publishing today has no delta:
    # reporting one would claim it "grew from zero" when nothing moved. Only
    # `downloads`, present at both endpoints, is real movement here.
    early = _metric_item(2, day=4, downloads=50.0)
    later = _metric_item(2, day=6, downloads=90.0)
    later.metrics = {"downloads": 90.0, "likes": 7.0}
    first = snapshot_for_run(_dated_run([early], day=4))
    latest = snapshot_for_run(_dated_run([later], day=6))

    tracked = briefing_input([first, latest], latest, ["guardrail"])["tracked_artifacts"]

    assert tracked[0]["metric_deltas"] == {"downloads": 40.0}


def test_briefing_packet_reports_how_much_of_the_corpus_reached_the_model():
    run = _dated_run([_item(index) for index in range(1, 6)], day=4)
    current = snapshot_for_run(run)

    coverage = briefing_input([current], current, ["guardrail"])["coverage"]

    assert coverage["corpus_evidence_records"] == 5
    assert coverage["evidence_injected"] == 5
    assert coverage["evidence_dropped_for_size"] == 0


def _briefing_zh_response(bullets_zh, caveat_zh):
    return {
        "id": "resp_zh",
        "model": "gpt-5.6-2026-08-01",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps({"bullets_zh": bullets_zh, "caveat_zh": caveat_zh}),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 500,
            "output_tokens": 300,
            "total_tokens": 800,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 20},
        },
    }


def test_generate_daily_briefing_translates_to_chinese_when_requested(monkeypatch):
    item = _item(1, title="MemoryBench: Long-horizon personal memory")
    item.summary = "Measures memory persistence."
    item.event_kind = "released"
    current = snapshot_for_run(_run([item]))

    def fake_briefing(url, payload, **kwargs):
        return {
            "id": "resp_real",
            "model": "gpt-5.6-2026-08-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "status": "insight",
                                    "insights": [
                                        {
                                            "finding": (
                                                "Memory evaluation is moving toward persistence."
                                            ),
                                            "why_it_matters": ("Teams need longitudinal tests."),
                                            "evidence_ids": ["E001"],
                                            "confidence": "medium",
                                        }
                                    ],
                                    "caveat": ("One captured release does not establish a trend."),
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 8123,
                "output_tokens": 241,
                "total_tokens": 8364,
                "input_tokens_details": {"cached_tokens": 100},
                "output_tokens_details": {"reasoning_tokens": 80},
            },
        }

    def fake_translate(url, payload, **kwargs):
        return _briefing_zh_response(
            [
                "记忆评估正在向持久化方向发展。Why it matters: 团队需要纵向测试。"
                "Evidence: E001. Medium confidence."
            ],
            "仅一个发布不足以确立趋势。",
        )

    monkeypatch.setattr("benchmark_radar.briefing.post_json", fake_briefing)
    monkeypatch.setattr("benchmark_radar.translate_zh.post_json", fake_translate)

    result = generate_daily_briefing(
        [current],
        current,
        ["Insufficient comparable history."],
        "secret",
        model="gpt-5.6",
        translate_zh=True,
    )

    assert "Evidence: E001" in result.bullets[0]
    assert result.metadata["bullets_zh"][0] == (
        "记忆评估正在向持久化方向发展。Why it matters: 团队需要纵向测试。"
        "Evidence: E001. Medium confidence."
    )
    assert result.metadata["caveat_zh"] == "仅一个发布不足以确立趋势。"
    assert result.metadata["zh_translation"]["response_id"] == "resp_zh"


def test_generate_daily_briefing_keeps_english_when_zh_translation_fails(monkeypatch):
    # A translation that drops the "Why it matters" marker would render as one
    # unparsable paragraph on the dashboard, so it is rejected and the day keeps
    # its English-only briefing rather than failing the whole run.
    item = _item(1, title="MemoryBench: Long-horizon personal memory")
    item.summary = "Measures memory persistence."
    item.event_kind = "released"
    current = snapshot_for_run(_run([item]))

    def fake_briefing(url, payload, **kwargs):
        return {
            "id": "resp_real",
            "model": "gpt-5.6-2026-08-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "status": "insight",
                                    "insights": [
                                        {
                                            "finding": (
                                                "Memory evaluation is moving toward persistence."
                                            ),
                                            "why_it_matters": ("Teams need longitudinal tests."),
                                            "evidence_ids": ["E001"],
                                            "confidence": "medium",
                                        }
                                    ],
                                    "caveat": "One captured release does not establish a trend.",
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 8123,
                "output_tokens": 241,
                "total_tokens": 8364,
                "input_tokens_details": {"cached_tokens": 100},
                "output_tokens_details": {"reasoning_tokens": 80},
            },
        }

    def fake_translate(url, payload, **kwargs):
        return _briefing_zh_response(
            ["记忆评估正在向持久化方向发展。团队需要纵向测试。Evidence: E001. Medium confidence."],
            "仅一个发布不足以确立趋势。",
        )

    monkeypatch.setattr("benchmark_radar.briefing.post_json", fake_briefing)
    monkeypatch.setattr("benchmark_radar.translate_zh.post_json", fake_translate)

    result = generate_daily_briefing(
        [current],
        current,
        ["Insufficient comparable history."],
        "secret",
        model="gpt-5.6",
        translate_zh=True,
    )

    assert "Why it matters" in result.bullets[0]
    assert "bullets_zh" not in result.metadata
    assert "caveat_zh" not in result.metadata


def test_instructions_enforce_humanized_writing_style():
    # Issue #377: the daily briefing must be readable by someone with no
    # context, grounded in evidence, and free of AI-slop tells (framework
    # jargon, all-purpose intensifiers, bundled-three-examples lists, and
    # imperative "evaluators should" directives). These rules live in the
    # writing-style block so a future "add more constraints" edit cannot
    # silently drop them.
    instructions = _INSTRUCTIONS

    # Assert against the Writing-style subsection only, not the whole prompt,
    # so a banned word or phrase that happens to appear elsewhere cannot make
    # the test pass or fail spuriously (and so a rule accidentally moved out of
    # the style block stops holding the test green).
    start = instructions.index("Writing style:")
    end = instructions.index("Output: at most ten")
    style_block = instructions[start:end]
    assert "Writing style:" in style_block

    # Anti-slop: no framework jargon / importance-inflation words.
    for banned in (
        "landscape",
        "pivotal",
        "underscore",
        "showcase",
        "vibrant",
        "robust",
        "critical role",
    ):
        assert banned in style_block, f"style block should name {banned!r} as a word to avoid"

    # Evidence-first neutrality is preserved even inside the style block.
    assert "never add an opinion" in style_block
    assert "never paper over absence" in style_block

    # Concrete-vs-abstract: force naming a specific artifact, not a theme.
    assert "Name the specific artifact" in style_block

    # Reader-relative framing instead of an imperative.
    assert "specific kind of user" in style_block
    assert "evaluators should" in style_block  # named only to forbid it

    # First-use abbreviations must be spelled out for a no-context reader.
    assert "Spell out the first occurrence of every" in style_block
    assert "Application Programming Interface" in style_block

    # Domain concepts must get a plain-language anchor for a generalist, so
    # "小白不需要上下文能读懂每一句" holds even for subfield jargon.
    assert "domain concepts a reader outside the subfield" in style_block
    assert "plain-language anchor that a generalist can picture" in style_block
    for concept in ("retrieval-", "corpus boundary", "quantization", "scaling law"):
        assert concept in style_block

    # The style block is part of the payload sent to the model, and it never
    # carries an internal issue reference of any number -- the model does not
    # need to know how the change was tracked. This asserts any "#NNN" reference
    # is absent, so it does not go stale when the issue number changes (a prior
    # version hard-coded "#365" and would silently pass the wrong contract once
    # the issue was retargeted).
    payload = _payload("gpt-5.6", "{}")
    assert "Writing style:" in payload["instructions"]
    assert not re.search(r"#\d+", payload["instructions"])


def test_generation_caps_fit_translation_bullet_ceiling():
    # The assembled bullet is: finding + " Why it matters: " + why + " Evidence: " +
    # evidence IDs + ". " + confidence + " confidence."
    marker_overhead = (
        len(" Why it matters: ")
        + len(" Evidence: ")
        + len(", ".join(f"E{i:03d}" for i in range(1, 7)))
        + len(". ")
        + len("Medium confidence.")
    )
    worst_bullet = MAX_FINDING_CHARS + MAX_WHY_CHARS + marker_overhead
    from benchmark_radar.translate_zh import MAX_BULLET_CHARS

    assert worst_bullet <= MAX_BULLET_CHARS


def test_zh_output_budget_covers_worst_case():
    # CJK characters are not uniformly one token. Exercise a deliberately
    # dense range and reserve room for the model's hidden reasoning tokens.
    from benchmark_radar.translate_zh import (
        MAX_BULLET_CHARS,
        MAX_ZH_CAVEAT_CHARS,
        MAX_ZH_OUTPUT_TOKENS,
        MIN_ZH_REASONING_HEADROOM_TOKENS,
    )

    cjk = "".join(chr(0x4E00 + index) for index in range(2_000))

    def sized_text(chars: int) -> str:
        return (cjk * (chars // len(cjk) + 1))[:chars]

    rendered = json.dumps(
        {
            "bullets_zh": [sized_text(MAX_BULLET_CHARS) for _ in range(MAX_BULLETS)],
            "caveat_zh": sized_text(MAX_ZH_CAVEAT_CHARS),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    visible_tokens = len(tiktoken.get_encoding("o200k_base").encode(rendered))

    assert visible_tokens > 24_000  # The former character approximation was unsafe.
    assert visible_tokens + MIN_ZH_REASONING_HEADROOM_TOKENS <= MAX_ZH_OUTPUT_TOKENS


def test_per_item_caps_bound_evidence_packet():
    # A single evidence record with huge metric values and URL gets truncated,
    # not the whole packet.
    huge_metrics = {
        "m1": "x" * 10_000,  # string value
        "m2": 42,  # numeric value
        "m3": ["y" * 100_000],  # malformed container value
        "k" * 10_000: 99,  # malformed key
        "m5": {"nested": "z" * 100_000},
        "m6": "w" * 2_000,
        "m7": "extra" * 1_000,  # 7th key - should be dropped
    }
    capped = _capped_metrics(huge_metrics)
    # Only first MAX_METRIC_KEYS kept
    assert len(capped) == MAX_METRIC_KEYS
    # Every serialized key and value is bounded, including malformed containers.
    assert all(len(key) <= MAX_METRIC_KEY_CHARS for key in capped)
    for v in capped.values():
        assert not isinstance(v, (list, dict))
        assert len(str(v)) <= MAX_METRIC_VALUE_CHARS
    # Numeric values pass through
    assert capped["m2"] == 42


def test_malformed_attention_metric_cannot_consume_the_packet():
    run = _run([_item(1)])
    attention = _attention(1)
    attention.metrics = {"bad": ["x" * 1_100_000]}
    run.attention = [attention]
    current = snapshot_for_run(run)

    value = briefing_input([current], current, [])

    assert len(value["attention_signals"][0]["metrics"]["bad"]) == MAX_METRIC_VALUE_CHARS
    assert len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) <= MAX_INPUT_CHARS
