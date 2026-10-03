"""Protect exact HN title identity across scripts, without changing attention ranking."""

from datetime import UTC, datetime

import pytest

from benchmark_radar.hacker_news import collect_hacker_news, normalized_title


@pytest.mark.parametrize(
    "first,second",
    [
        ("中文模型 benchmark", "测试集 benchmark"),
        ("日本語の模型 benchmark", "한국어 모델 benchmark"),
        ("παράδειγμα benchmark", "пример benchmark"),
        ("résumé benchmark", "resume benchmark"),
        ("कि benchmark", "कु benchmark"),
        ("عَلَم benchmark", "عِلْم benchmark"),
    ],
)
def test_distinct_non_latin_title_words_do_not_collapse(first, second):
    # #742: removing every non-ASCII word merged unrelated HN submissions,
    # combined their engagement, and hid the later title from readers.
    assert normalized_title(first) != normalized_title(second)


def test_canonical_unicode_spelling_case_and_punctuation_still_cluster():
    assert normalized_title("CAFÉ: 模型 Benchmark!") == normalized_title(
        "Cafe\u0301 — 模型 benchmark?"
    )


def test_non_latin_titles_survive_the_native_collector_as_separate_observations():
    config = {
        "lookback_hours": 24,
        "queries": ["benchmark"],
        "taxonomy": {"benchmark": ["benchmark"]},
    }
    hits = [
        {
            "objectID": str(index),
            "title": title,
            "created_at": "2026-10-02T08:00:00Z",
            "points": index,
            "num_comments": 0,
        }
        for index, title in enumerate(["中文模型 benchmark", "测试集 benchmark"], start=1)
    ]
    observations, health = collect_hacker_news(
        config,
        datetime(2026, 10, 2, 12, tzinfo=UTC),
        fetcher=lambda _url, _params: {"hits": hits},
    )
    assert health["ok"] is True
    assert health["item_count"] == 2
    assert {row["title"] for row in observations} == {hit["title"] for hit in hits}
    assert {row["source_id"] for row in observations} == {"1", "2"}
    assert sorted(row["metrics"]["points"] for row in observations) == [1.0, 2.0]
    assert all(row["metrics"]["submissions"] == 1.0 for row in observations)
    assert all("supporting_observations" not in row for row in observations)
