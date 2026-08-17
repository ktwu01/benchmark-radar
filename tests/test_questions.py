from datetime import UTC, datetime

import pytest

from benchmark_radar import questions
from benchmark_radar.briefing import BriefingError
from benchmark_radar.models import RadarItem, RadarRun
from benchmark_radar.snapshots import snapshot_for_run
from benchmark_radar.stats import build_registry, stat_index


def _item(index: int, *, day: int = 4, downloads: float | None = None) -> RadarItem:
    return RadarItem(
        source="Hugging Face",
        source_id=f"org/dataset-{index}",
        title=f"Benchmark dataset {index}",
        url=f"https://huggingface.co/datasets/org/dataset-{index}",
        published_at=datetime(2026, 8, day, tzinfo=UTC),
        categories=["benchmark"],
        summary="A scored evaluation dataset with documented verifier behaviour.",
        event_kind="released",
        metrics={"downloads": downloads} if downloads is not None else {},
    )


def _run(items, *, day: int = 4) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 8, day, 12, tzinfo=UTC),
        since=datetime(2026, 8, day - 1, 12, tzinfo=UTC),
        items=items,
        health=[],
        selection={"taxonomy_version": "taxonomy-v2", "lookback_hours": 48},
    )


def _group():
    return {"id": "arrivals", "title": "What arrived", "questions": ("Q1?",)}


def _answer(**overrides):
    answer = {
        "question": "Q1?",
        "signal": "Three datasets arrived.",
        "plain_english": "Three new scored datasets showed up today.",
        "takeaway": "Check whether they document a verifier.",
        "counter_view": "No credible counter-view found.",
        "stat_ids": ["S001"],
        "evidence_ids": [],
        "confidence": "medium",
        "sufficient_evidence": True,
    }
    answer.update(overrides)
    return answer


def _fixture():
    current = snapshot_for_run(_run([_item(1), _item(2)]))
    registry = build_registry([current], current)
    return _group(), stat_index(registry), {"E001", "E002"}


def test_an_answer_citing_an_unknown_statistic_is_rejected():
    # The registry is the only source of numbers. A model that invents one must
    # not be able to publish it.
    group, stats_by_id, evidence = _fixture()

    with pytest.raises(BriefingError, match="unknown statistics"):
        questions._validate([_answer(stat_ids=["S999"])], group, stats_by_id, evidence)


def test_an_answer_citing_unknown_evidence_is_rejected():
    group, stats_by_id, evidence = _fixture()

    with pytest.raises(BriefingError, match="unknown evidence"):
        questions._validate([_answer(evidence_ids=["E404"])], group, stats_by_id, evidence)


def test_a_confident_answer_that_cites_nothing_is_rejected():
    # This is the generic-filler failure mode: confident prose grounded in
    # nothing at all.
    group, stats_by_id, evidence = _fixture()

    with pytest.raises(BriefingError, match="citing none"):
        questions._validate([_answer(stat_ids=[], evidence_ids=[])], group, stats_by_id, evidence)


def test_an_insufficient_evidence_answer_may_cite_nothing():
    # Saying "the data does not show this" is a useful answer, not a failure.
    group, stats_by_id, evidence = _fixture()

    validated = questions._validate(
        [_answer(stat_ids=[], evidence_ids=[], sufficient_evidence=False)],
        group,
        stats_by_id,
        evidence,
    )

    assert validated[0]["sufficient_evidence"] is False


def test_a_short_answer_set_is_rejected():
    group = {"id": "arrivals", "title": "t", "questions": ("Q1?", "Q2?")}
    _, stats_by_id, evidence = _fixture()

    with pytest.raises(BriefingError, match="answered 1 of 2"):
        questions._validate([_answer()], group, stats_by_id, evidence)


def test_validated_answers_carry_the_registry_values_not_model_prose():
    # The renderer prints from cited_stats, so the published number is the
    # computed one even if the model described it loosely.
    group, stats_by_id, evidence = _fixture()

    validated = questions._validate([_answer(stat_ids=["S001"])], group, stats_by_id, evidence)

    assert validated[0]["cited_stats"][0]["id"] == "S001"
    assert validated[0]["cited_stats"][0]["value"] == 2


def test_registry_refuses_trend_language_without_a_comparable_window():
    current = snapshot_for_run(_run([_item(1)]))

    registry = build_registry([current], current)

    assert registry["comparable"] is False
    assert "Do not use trend language" in registry["comparability_note"]


def test_registry_marks_category_counts_as_overlapping():
    item = _item(1)
    item.categories = ["benchmark", "agentic"]
    current = snapshot_for_run(_run([item]))

    registry = build_registry([current], current)
    tagged = [stat for stat in registry["stats"] if stat["label"].startswith("records tagged")]

    assert len(tagged) == 2
    assert all("do not sum to 100%" in stat["detail"]["note"] for stat in tagged)


def test_composition_shift_stat_carries_the_values_it_actually_computed():
    # Regression: the stat detail was mapped from keys composition_shift never
    # returns (`shift`, `direction`, `contributing_sources`), so a verified
    # shift shipped with every detail field None and the Q&A layer could only
    # report an empty framing. The published values must be the finding's own.
    def day(index: int, agentic: int) -> dict:
        items = []
        for position in range(100):
            categories = ["benchmark"]
            if position < agentic:
                categories.append("agentic")
            items.append(
                RadarItem(
                    source=f"source-{position % 4}",
                    source_id=f"item-{index}-{position}",
                    title=f"Artifact {index}-{position}",
                    url=f"https://example.test/{index}/{position}",
                    published_at=datetime(2026, 8, 1, tzinfo=UTC),
                    categories=categories,
                    summary="A scored evaluation dataset with a documented verifier.",
                    event_kind="released",
                    metrics={},
                )
            )
        return snapshot_for_run(_run(items, day=index + 2))

    history = [day(index, 10 if index < 9 else 30) for index in range(14)]
    registry = build_registry(history, history[-1])
    shift = next(
        stat for stat in registry["stats"] if stat["label"].startswith("composition shift")
    )

    assert shift["value"] == 30.0
    assert shift["detail"]["baseline_share_pct"] == 10.0
    assert shift["detail"]["shift_points"] == 20.0
    assert shift["detail"]["direction"] == "rising"
    assert isinstance(shift["detail"]["contributing_sources"], int)


def test_question_set_omits_questions_the_corpus_cannot_answer():
    # The corpus keeps no query identity, rank, or per-query volume, so a
    # "which searches surged" question could only be answered by invention.
    asked = " ".join(
        question for group in questions.QUESTION_GROUPS for question in group["questions"]
    ).casefold()

    assert "search" not in asked
    assert "surge" not in asked


def test_report_prints_statistic_values_from_the_registry():
    # The published number is the computed one. A model that wrote "thousands"
    # in its prose still yields the registry's exact value on the page.
    from benchmark_radar.report import render_markdown

    run = _run([_item(1), _item(2)])
    current = snapshot_for_run(run)
    registry = build_registry([current], current)
    by_id = {stat["id"]: stat for stat in registry["stats"]}
    payload = {
        "model": "gpt-5.6",
        "calls": 1,
        "comparable": registry["comparable"],
        "usage": {"input_tokens": 100, "output_tokens": 10},
        "groups": [
            {
                "title": "What arrived",
                "answers": [
                    {
                        "question": "What arrived today?",
                        "signal": "Two datasets arrived.",
                        "plain_english": "Two new test sets showed up.",
                        "takeaway": "Check their verifiers.",
                        "counter_view": "One connector supplied both.",
                        "stat_ids": ["S001"],
                        "evidence_ids": [],
                        "confidence": "medium",
                        "sufficient_evidence": True,
                        "cited_stats": [by_id["S001"]],
                    }
                ],
            }
        ],
    }

    markdown = render_markdown(run, dashboard_url="https://x.test", daily_questions=payload)

    assert "## Questions for today" in markdown
    assert "**Counter-view:** One connector supplied both" in markdown
    assert "`S001` evidence records captured today: **2**" in markdown
    # No certified window today, so the report must not imply a trend.
    assert "No certified comparison window today" in markdown


def test_a_day_never_loses_answers_it_already_had():
    from benchmark_radar.snapshots import merge_snapshots

    morning_run = _run([_item(1)])
    morning_run.daily_questions = {"groups": [{"title": "t", "answers": []}]}
    morning = snapshot_for_run(morning_run)

    merged = merge_snapshots(morning, snapshot_for_run(_run([_item(2)])))

    assert merged["questions"]["groups"][0]["title"] == "t"


def test_prose_may_not_state_a_number_the_registry_does_not_hold():
    # Citing a valid statistic is not enough: an answer can cite S001 (=2) and
    # still write "three datasets arrived". The registry is the authority for
    # every quantity in the text, not only the ones the answer points at.
    group, stats_by_id, evidence = _fixture()

    with pytest.raises(BriefingError, match="uncited quantity"):
        questions._validate(
            [_answer(signal="A total of 847 datasets arrived today.")],
            group,
            stats_by_id,
            evidence,
        )


def test_prose_may_not_state_an_uncited_hundred():
    # 100 is not in the bare-number allowlist: it is a plausible corpus
    # measurement, not an ordinal or a self-referential count, so a model may
    # not state it without a statistic that computes to 100. Previously it was
    # allowlisted (issue #165) and let a fabricated quantity through.
    stats = {"S001": {"id": "S001", "label": "x", "value": 2, "unit": "count"}}
    answer = {
        "signal": "100 benchmarks arrived today.",
        "plain_english": "",
        "takeaway": "",
        "counter_view": "",
    }

    with pytest.raises(BriefingError, match="uncited quantity"):
        questions._reject_uncited_quantities(answer, stats)


def test_an_uncited_hundred_is_fine_when_a_statistic_is_hundred():
    # Removing 100 from the bare allowlist must not reject a quantity the
    # registry actually computed: a registry value of 100 remains citable.
    stats = {"S001": {"id": "S001", "label": "share", "value": 100, "unit": "percent"}}

    questions._reject_uncited_quantities(
        {"signal": "100 percent share.", "plain_english": "", "takeaway": "", "counter_view": ""},
        stats,
    )


def test_an_uncited_hundred_percent_caveat_is_fine():
    # The registry's own notes and the instructions supply the caveat "shares do
    # not sum to 100%". The model may reproduce that sanctioned wording even
    # when no statistic computes to 100; the exemption is the caveat, not every
    # percentage (issue #165 / Codex review).
    stats = {"S001": {"id": "S001", "label": "x", "value": 2, "unit": "count"}}

    questions._reject_uncited_quantities(
        {
            "signal": "category shares do not sum to 100%.",
            "plain_english": "",
            "takeaway": "",
            "counter_view": "",
        },
        stats,
    )


def test_an_unsupported_percentage_is_still_rejected():
    # Only the sanctioned negative caveat exempts a 100; a fabricated percentage
    # such as "100% of today's records" must still fail when no statistic
    # computes to 100 (issue #165 / Codex review).
    stats = {"S001": {"id": "S001", "label": "x", "value": 2, "unit": "count"}}

    with pytest.raises(BriefingError, match="uncited quantity"):
        questions._reject_uncited_quantities(
            {
                "signal": "100% of today's records are benchmarks.",
                "plain_english": "",
                "takeaway": "",
                "counter_view": "",
            },
            stats,
        )


def test_a_positive_sum_to_hundred_is_not_the_sanctioned_caveat():
    # The exemption is the registry's negative caveat ("do not sum to 100%").
    # The affirmative "shares sum to 100%" is a fabricated claim, not that
    # caveat, and must be rejected when no statistic computes to 100.
    stats = {"S001": {"id": "S001", "label": "x", "value": 2, "unit": "count"}}

    with pytest.raises(BriefingError, match="uncited quantity"):
        questions._reject_uncited_quantities(
            {
                "signal": "category shares sum to 100%.",
                "plain_english": "",
                "takeaway": "",
                "counter_view": "",
            },
            stats,
        )


def test_the_caveat_exemption_only_applies_to_category_shares():
    # The sanctioned caveat is about category tags overlapping. Applying the
    # same negative phrase to another quantity is a fabricated percentage and
    # must be rejected when no statistic computes to 100.
    stats = {"S001": {"id": "S001", "label": "x", "value": 2, "unit": "count"}}

    with pytest.raises(BriefingError, match="uncited quantity"):
        questions._reject_uncited_quantities(
            {
                "signal": "Source shares do not sum to 100%.",
                "plain_english": "",
                "takeaway": "",
                "counter_view": "",
            },
            stats,
        )


def test_prose_may_state_identifier_fragments_the_registry_does_not_hold():
    # "26-001", "S001", "v2.001", "2026-001," are version and artifact codes,
    # not corpus measurements, so they must not fail a day's Q&A (a production
    # run rejected '001,' and aborted the whole pipeline).
    group, stats_by_id, evidence = _fixture()

    validated = questions._validate(
        [_answer(signal=("The 26-001 entry and S001 sit next to v2.001; 2026-001, arrived too."))],
        group,
        stats_by_id,
        evidence,
    )

    assert validated[0]["signal"].startswith("The 26-001 entry")


def test_prose_may_restate_a_value_the_registry_computed():
    group, stats_by_id, evidence = _fixture()

    validated = questions._validate(
        [_answer(signal="The radar captured 2 evidence records today.")],
        group,
        stats_by_id,
        evidence,
    )

    assert validated[0]["signal"].endswith("today.")


def test_evidence_validation_is_scoped_to_what_the_call_actually_saw():
    # The movement group receives no first-observed evidence, so an E ID the
    # model guessed must not validate against the wider base packet.
    group = {"id": "movement", "title": "t", "questions": ("Q1?",)}
    _, stats_by_id, _ = _fixture()

    with pytest.raises(BriefingError, match="unknown evidence"):
        questions._validate([_answer(evidence_ids=["E001"])], group, stats_by_id, set(), {})


def test_a_metric_reported_by_one_connector_is_not_corroborated():
    # Two connectors seeing an artifact says nothing about whether both
    # measured the number that moved.
    from benchmark_radar.stats import build_registry as build

    early = _item(1, day=4, downloads=10.0)
    later = _item(1, day=6, downloads=99.0)
    sighting = _item(1, day=6)
    sighting.source = "GitHub"
    sighting.url = early.url
    first = snapshot_for_run(_run([early], day=4))
    latest = snapshot_for_run(_run([later, sighting], day=6))

    tracked = build([first, latest], latest)["tracked_artifacts"]

    assert tracked[0]["metric_deltas"] == {"downloads": 89.0}
    assert tracked[0]["metric_sources"]["downloads"] == ["Hugging Face"]
    assert tracked[0]["corroborated"] is False


def test_question_requests_do_not_retain_data_server_side():
    payload = questions._payload("gpt-5.6", "{}")

    assert payload["store"] is False


def test_generate_daily_questions_translates_answers_to_chinese_when_requested(monkeypatch):
    import json

    current = snapshot_for_run(_run([_item(1), _item(2)]))

    def fake_questions(url, payload, **kwargs):
        prompt_questions = json.loads(payload["input"])["questions"]
        return {
            "id": "resp_qa",
            "model": "gpt-5.6-2026-08-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "answers": [
                                        {
                                            "question": question,
                                            "signal": "No supporting evidence today.",
                                            "plain_english": (
                                                "Nothing in the captured feed supports an "
                                                "answer today."
                                            ),
                                            "takeaway": "Treat the day as quiet.",
                                            "counter_view": "No credible counter-view found.",
                                            "stat_ids": [],
                                            "evidence_ids": [],
                                            "confidence": "low",
                                            "sufficient_evidence": False,
                                        }
                                        for question in prompt_questions
                                    ]
                                }
                            ),
                        }
                    ],
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

    def fake_translate(url, payload, **kwargs):
        count = len(json.loads(payload["input"])["answers"])
        return {
            "id": "resp_zh",
            "model": "gpt-5.6-2026-08-01",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "answers_zh": [
                                        {
                                            "index": index,
                                            "signal_zh": "今天没有支持性的证据。",
                                            "plain_chinese": "今天的捕获流中没有任何内容支持答案。",
                                            "takeaway_zh": "把今天视为平静的一天。",
                                            "counter_view_zh": "未找到可信的反方观点。",
                                        }
                                        for index in range(count)
                                    ]
                                }
                            ),
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

    monkeypatch.setattr("benchmark_radar.questions.post_json", fake_questions)
    monkeypatch.setattr("benchmark_radar.translate_zh.post_json", fake_translate)

    result = questions.generate_daily_questions(
        [], current, [], "secret", model="gpt-5.6", translate_zh=True
    )

    answers = [a for group in result["groups"] for a in group["answers"]]
    assert len(answers) == 6
    assert all(
        a["signal_zh"] and a["plain_chinese"] and a["takeaway_zh"] and a["counter_view_zh"]
        for a in answers
    )
    assert result["zh_translation"]["response_id"] == "resp_zh"
