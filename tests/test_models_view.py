"""The Models matrix merged from benchmark-radar.com's Model Evals (#420)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import _model_value_text, _models_seed
from benchmark_radar.model_scores import (
    average_value,
    build_model_scores,
    capability_group,
    joined_map_from_groups,
    latest_date,
    model_family,
    order_models,
    score_scale,
    shared_average,
)

ROOT = Path(__file__).resolve().parents[1]
PERCENT = {"percent": True, "direction": "higher_is_better", "unit": "%"}


def test_models_behaviour_runs_against_the_production_functions():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/models_harness.mjs"], check=True, timeout=60, cwd=ROOT)


# --- The shared-benchmark average's three rules -----------------------------------


def test_rule_1_only_benchmarks_every_model_shares_count():
    # B also reported an easy benchmark; it must not lift B above A.
    benchmarks = {"hard": PERCENT, "easy": PERCENT}
    means, shared = shared_average([{"hard": 40.0}, {"hard": 40.0, "easy": 99.0}], benchmarks)
    assert means == [40.0, 40.0]
    assert shared == ["hard"]


def test_rule_2_scores_count_on_their_series_direction_and_scale():
    # A fraction declared out of 1 is put on 0-100 by the series' multiplier.
    fraction = {"declared_max": 1.0, "score_summary": {"display_multiplier": 100, "raw_max": 0.6}}
    assert score_scale(fraction) == (100, True)
    # The multiplier alone is display convention, not evidence of a percentage.
    assert score_scale({"score_summary": {"display_multiplier": 100, "raw_max": 0.6}}) == (
        100,
        False,
    )
    assert score_scale({"score_summary": {"display_multiplier": 1, "unit": "percent"}}) == (1, True)
    assert score_scale({"declared_max": 100.0, "score_summary": {"display_multiplier": 1}}) == (
        1,
        True,
    )
    # Elo, dollars and points out of 42 are not on a 0-100 scale.
    elo = {"declared_max": 3000.0, "score_summary": {"display_multiplier": 1, "raw_max": 1577}}
    assert score_scale(elo) == (1, False)
    assert (
        score_scale({"declared_max": 42.0, "score_summary": {"display_multiplier": 1}})[1] is False
    )
    # A reported value outside 0-100 contradicts a percent declaration.
    contradicted = {"score_summary": {"display_multiplier": 1, "unit": "percent", "raw_max": 140}}
    assert score_scale(contradicted)[1] is False
    benchmarks = {
        "hard": PERCENT,
        "elo": {"percent": False, "direction": "higher_is_better", "unit": "Elo"},
        "error": {"percent": True, "direction": "lower_is_better", "unit": "%"},
    }
    means, shared = shared_average(
        [
            {"hard": 60.0, "elo": 1577.0, "error": 10.0},
            {"hard": 80.0, "elo": 1200.0, "error": 30.0},
        ],
        benchmarks,
    )
    assert shared == ["error", "hard"]  # Elo left out
    assert means == [75.0, 75.0]  # lower-is-better flipped: (90 + 60) / 2, (70 + 80) / 2
    assert average_value(10.0, benchmarks["error"]) == 90.0
    assert average_value(1577.0, benchmarks["elo"]) is None
    assert average_value(5.0, {"percent": True, "direction": None}) is None


def test_rule_3_the_count_of_shared_benchmarks_is_returned_and_printed(tmp_path):
    means, shared = shared_average([{"a": 1.0}, {"b": 2.0}], {"a": PERCENT, "b": PERCENT})
    assert (means, shared) == ([None, None], [])
    payload, records = _fixture(tmp_path)
    _, _, matrix, _ = _models_seed(records, payload).values()
    assert "over the 1 benchmarks all 2 models share, 0–100" in matrix


def test_rule_1_a_record_counts_only_within_one_comparable_group(tmp_path):
    # Two scaffolds on one record are not one benchmark.
    benchmarks = {"hard": PERCENT, "easy": PERCENT}
    columns = [{"hard": 40.0, "easy": 50.0}, {"hard": 60.0, "easy": 70.0}]
    means, shared = shared_average(columns, benchmarks, [{"hard": 0}, {"hard": 1}])
    assert shared == ["easy"]
    assert means == [50.0, 70.0]
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    shard = _shard("k:fc", [("M", "Lab", 40.0, "2026-01-01"), ("M", "Lab", 60.0, "2026-01-02")])
    for row, group in zip(shard["scores_by_source"]["llm_stats"]["rows"], ["A", "B"], strict=True):
        row["comparable_group"] = group
    (shards / "fc.json").write_text(json.dumps(shard))
    payload = build_model_scores(shards)
    assert payload["benchmarks"][0]["groups"] == ["A", "B"]
    # Best value, its row count, and the group it came from.
    assert payload["models"][0]["scores"] == [[0, 60.0, 2, 1]]


def test_a_label_a_source_reuses_for_two_checkpoints_is_two_columns(tmp_path):
    # LLM Stats files gpt-4o-2024-05-13 and gpt-4o-2024-08-06 both as "GPT-4o".
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    shard = _shard(
        "k:mmlu",
        [("GPT-4o", "OpenAI", 88.7, "2024-05-13"), ("GPT-4o", "OpenAI", 85.7, "2024-08-06")],
    )
    for row, model_id in zip(
        shard["scores_by_source"]["llm_stats"]["rows"], ["gpt-4o-0513", "gpt-4o-0806"], strict=True
    ):
        row["model_id"] = model_id
    (shards / "mmlu.json").write_text(json.dumps(shard))
    payload = build_model_scores(shards)
    assert [(m["model"], m.get("source_model_id"), m["scores"]) for m in payload["models"]] == [
        ("GPT-4o", "gpt-4o-0513", [[0, 88.7]]),
        ("GPT-4o", "gpt-4o-0806", [[0, 85.7]]),
    ]


def test_averages_round_half_up_like_the_page():
    assert shared_average([{"a": 0.25}], {"a": PERCENT})[0] == [0.3]


# --- Joined benchmarks (#904) ---------------------------------------------------


def test_joined_records_share_one_benchmark():
    # Two columns score different records of one reviewed equivalent group.
    joined = {"llm-stats:gpqa": "gpqa", "opencompass:1135": "gpqa"}
    benchmarks = {"llm-stats:gpqa": PERCENT, "opencompass:1135": PERCENT}
    means, shared = shared_average(
        [{"llm-stats:gpqa": 40.0}, {"opencompass:1135": 60.0}],
        benchmarks,
        joined=joined,
    )
    assert means == [40.0, 60.0]
    assert shared == ["gpqa"]


def test_joined_records_do_not_share_across_different_groups():
    joined = {"a": "g1", "b": "g2"}
    benchmarks = {"a": PERCENT, "b": PERCENT}
    assert shared_average([{"a": 40.0}, {"b": 60.0}], benchmarks, joined=joined) == (
        [None, None],
        [],
    )


def test_joined_records_still_require_one_comparable_group():
    joined = {"a": "g", "b": "g"}
    benchmarks = {"a": PERCENT, "b": PERCENT}
    columns = [{"a": 40.0}, {"b": 60.0}]
    means, shared = shared_average(columns, benchmarks, [{"a": 0}, {"b": 1}], joined=joined)
    assert (means, shared) == ([None, None], [])
    means, shared = shared_average(columns, benchmarks, [{"a": 0}, {"b": 0}], joined=joined)
    assert (means, shared) == ([40.0, 60.0], ["g"])


def test_joined_records_compare_group_labels_not_local_indexes():
    # Codex P2 (#1129): index 0 is "cot" on record a and "plain" on record
    # b, so equal indexes must not share the joined benchmark; the same
    # protocol under different indexes must.
    joined = {"a": "g", "b": "g"}
    benchmarks = {
        "a": {**PERCENT, "groups": ["cot", "plain"]},
        "b": {**PERCENT, "groups": ["plain", "cot"]},
    }
    columns = [{"a": 40.0}, {"b": 60.0}]
    assert shared_average(columns, benchmarks, [{"a": 0}, {"b": 0}], joined=joined) == (
        [None, None],
        [],
    )
    assert shared_average(columns, benchmarks, [{"a": 1}, {"b": 0}], joined=joined) == (
        [40.0, 60.0],
        ["g"],
    )


def test_joined_map_ignores_single_member_groups():
    groups = [
        {"group_id": "lonely", "members": ["a"]},
        {"group_id": "g", "members": ["a", "b"]},
        {"members": ["c", "d"]},
    ]
    assert joined_map_from_groups(groups) == {"a": "g", "b": "g"}


def test_build_model_scores_marks_joined_benchmarks(tmp_path):
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    for name, key in {"a": "llm-stats:aime", "b": "model-reports:aime"}.items():
        (shards / f"{name}.json").write_text(
            json.dumps(_shard(key, [("M", "Lab", 50.0, "2026-01-01")]))
        )
    payload = build_model_scores(
        shards,
        equivalences=[{"group_id": "aime", "members": ["llm-stats:aime", "model-reports:aime"]}],
    )
    assert {benchmark["key"]: benchmark.get("joined") for benchmark in payload["benchmarks"]} == {
        "llm-stats:aime": "aime",
        "model-reports:aime": "aime",
    }
    # Without equivalences the payload is unchanged: no joined field appears.
    plain = build_model_scores(shards)
    assert all("joined" not in benchmark for benchmark in plain["benchmarks"])


# --- Data -------------------------------------------------------------------------


def _shard(key, rows, *, multiplier=1, unit="percent", direction="higher_is_better", **series):
    return {
        "record": {"key": key},
        "scores_by_source": {
            "llm_stats": {
                "series": {
                    "direction": direction,
                    "score_summary": {"display_multiplier": multiplier, "unit": unit},
                    **series,
                },
                "rows": [
                    {
                        "obs_id": f"{key}:{index}",
                        "model_name": model,
                        "organization": org,
                        "value": value,
                        "reported_date": date,
                        "date_precision": "model_announcement",
                    }
                    for index, (model, org, value, date) in enumerate(rows)
                ],
            }
        },
    }


def _fixture(tmp_path):
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    for name, shard in {
        "aime": _shard(
            "llm-stats:aime",
            [
                ("Acme-1", "Acme", 0.5, "2026-01-01"),
                ("Acme-1", "acme", 0.7, "2026-02-01"),
                ("Beta <1>", "Beta", 0.9, "2026-03-01"),
            ],
            multiplier=100,
            unit=None,
            declared_max=1.0,
        ),
        "arena": _shard(
            "llm-stats:arena",
            [("Acme-1", "Acme", 1500.0, "2026-01-01"), ("Beta <1>", "Beta", 1400.0, "2026-01-01")],
            unit="elo",
            declared_max=3000.0,
        ),
        "arc": _shard("model-reports:arc", [("Beta <1>", "Beta", 12.0, "2026-04-01")]),
    }.items():
        (shards / f"{name}.json").write_text(json.dumps(shard))
    records = [
        {
            "key": "llm-stats:aime",
            "slug": "llm-stats-aime",
            "name": "AIME",
            "source": "llm_stats",
            "categories": ["math"],
            "scored_models": [{"name": "Acme-1"}],
        },
        {
            "key": "llm-stats:arena",
            "slug": "llm-stats-arena",
            "name": "Arena",
            "source": "llm_stats",
            "categories": [],
            "scored_models": [{"name": "Acme-1"}],
        },
        {
            "key": "model-reports:arc",
            "slug": "arc",
            "name": "AIME",
            "source": "model_reports",
            "categories": ["reasoning"],
            "scored_models": [{"name": "Beta <1>"}],
        },
        {"key": "claire-radar:x", "slug": "x", "name": "X", "source": "claire_radar"},
    ]
    return build_model_scores(shards), records


def test_build_keeps_each_models_best_score_per_record_on_its_display_scale(tmp_path):
    payload, _ = _fixture(tmp_path)
    keys = [benchmark["key"] for benchmark in payload["benchmarks"]]
    by_model = {
        model["model"]: {keys[score[0]]: score[1:] for score in model["scores"]}
        for model in payload["models"]
    }
    # Case-only organization spellings are one registry model; its best of two
    # settings is kept with the row count, on the display scale.
    assert by_model["Acme-1"]["llm-stats:aime"] == [70.0, 2]
    assert by_model["Acme-1"]["llm-stats:arena"] == [1500.0]
    arena = payload["benchmarks"][keys.index("llm-stats:arena")]
    assert (arena["percent"], arena["unit"]) == (False, "Elo")
    beta = next(m for m in payload["models"] if m["model"] == "Beta <1>")
    # Each source's latest date and what that date is.
    assert beta["dates"] == {"llm_stats": ["2026-04-01", "model_announcement"]}


def test_lower_is_better_keeps_the_lowest_score(tmp_path):
    shards = tmp_path / "benchmarks"
    shards.mkdir()
    rows = [("M", "Lab", 9.0, "2026-01-01"), ("M", "Lab", 4.0, "2026-01-02")]
    shard = _shard("k:err", rows, direction="lower_is_better")
    (shards / "err.json").write_text(json.dumps(shard))
    payload = build_model_scores(shards)
    assert payload["models"][0]["scores"] == [[0, 4.0, 2]]


# --- Mirrors of app.js ---------------------------------------------------------------


def test_families_groups_and_order_match_the_page():
    assert model_family("Claude Opus 5 (Adaptive Reasoning, High Effort)") == (
        "Claude Opus 5",
        "Adaptive Reasoning, High Effort",
    )
    assert model_family("GPT-5") == ("GPT-5", "")
    assert capability_group({"categories": ["math", "reasoning"]}) == "Mathematics"
    assert capability_group({"library_direction": {"categories": ["agentic-coding"]}}) == "Coding"
    assert capability_group({"categories": ["safety"]}) == "Other"
    # Whole words: "multilingual" is language, not Multimodal.
    multilingual = {"library_direction": {"categories": ["multilingual"]}}
    assert capability_group(multilingual) == "Reasoning & Knowledge"
    dates = {"a": ["2026-01-01", "x"], "b": ["2026-02-01", "y"]}
    assert latest_date(dates) == ("2026-02-01", "y")
    assert latest_date(dates, "a") == ("2026-01-01", "x")
    assert latest_date({}, "a") == ("", "")
    family = [
        {"organization": "A", "model": "M (high)", "date": "2026-02-01", "cells": {"x": 1}},
        {"organization": "A", "model": "M", "date": "2026-01-01", "cells": {"x": 1}},
        {"organization": "A", "model": "N", "date": "2026-01-15", "cells": {"x": 1, "y": 1}},
        {"organization": "A", "model": "Old", "date": None, "cells": {"x": 1}},
    ]
    newest = order_models(family, "newest")
    assert [model["model"] for model in newest] == ["M", "M (high)", "N", "Old"]
    assert [model["model"] for model in order_models(family)] == ["N", "M", "M (high)", "Old"]
    assert _model_value_text(74.66, PERCENT) == "74.7%"
    assert _model_value_text(70.0, PERCENT) == "70%"
    assert _model_value_text(1577.0, {"unit": "Elo"}) == "1,577 Elo"
    assert _model_value_text(0.4763, {}) == "0.476"


# --- Seed -------------------------------------------------------------------------------


def test_seed_is_the_first_page_of_the_matrix(tmp_path):
    payload, records = _fixture(tmp_path)
    nav, page, matrix, status = _models_seed(records, payload).values()
    assert '<a class="library-direction" href="/models/?lab=Acme">' in nav
    assert "1–2 of 2 models, most benchmarks first" in page
    # A column's date says what it is.
    assert "announced Apr 1, 2026" in matrix
    # Most benchmarks first, then newest: both have scores on two records, and
    # Beta's latest (Apr) is after Acme's (Feb).
    assert matrix.index("Beta &lt;1&gt;") < matrix.index("Acme-1")
    # Two records named AIME keep their sources visible.
    assert '<span class="models-source">LLM Stats</span>' in matrix
    assert '<span class="models-source">Model reports</span>' in matrix
    # Elo is shown, not averaged; the best of two settings says so.
    assert "1,500 Elo" in matrix and "not averaged" in matrix
    assert "best of 2 settings" in matrix
    assert "<strong>90</strong>" in matrix and "<strong>70</strong>" in matrix
    assert "1 benchmark records have no reported model score." in matrix
    assert "2 models with a reported score on 3 of 4 benchmark records" in status


def test_seed_keeps_document_only_labs_and_publishes_nothing_without_scores(tmp_path):
    payload, records = _fixture(tmp_path)
    documents = {"documents": [{"id": "d", "document_type": "release_post", "organization": "Ai2"}]}
    nav = _models_seed(records, payload, documents)[next(iter(_models_seed(records, payload)))]
    assert "/models/?lab=Ai2" in nav
    assert _models_seed(records, None) == {}
    assert _models_seed([], payload) == {}
