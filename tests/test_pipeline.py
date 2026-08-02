from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from benchmark_radar.models import ProducerHealth, RadarItem, SourceHealth
from benchmark_radar.pipeline import (
    apply_watchlist,
    assert_no_boilerplate_summaries,
    canonical_url,
    deduplicate,
    normalized_title,
    run_pipeline,
    score_item,
    simulate_backfill,
)

WATCHLIST = [
    {"name": "MLE-bench", "aliases": ["mlebench", "mle-bench"], "note": "ML engineering tasks."},
    {"name": "PaperBench", "aliases": ["paperbench"], "note": "Paper replication."},
]


def item(**overrides):
    values = {
        "source": "arXiv",
        "source_id": "1234.5678",
        "title": "A New LLM Evaluation Benchmark",
        "url": "https://arxiv.org/abs/1234.5678",
        "published_at": datetime(2026, 7, 27, tzinfo=UTC),
        "summary": "We release a benchmark dataset for language model evaluation.",
    }
    values.update(overrides)
    return RadarItem(**values)


def test_url_canonicalization_removes_tracking():
    assert (
        canonical_url("HTTPS://Example.COM/a/?utm_source=x&keep=y")
        == "https://example.com/a?keep=y"
    )


def test_title_normalization():
    assert normalized_title("  New: AI-Bench! ") == "new ai bench"


def test_dedupe_merges_cross_source_urls():
    first = item()
    second = item(source="GitHub", source_id="org/repo", url="https://github.com/org/repo")
    result = deduplicate([first, second])
    assert len(result) == 1
    assert result[0].artifact_urls == ["https://github.com/org/repo"]


def test_scoring_is_explainable_and_bounded():
    taxonomy = {
        "benchmark": ["benchmark"],
        "evaluation": ["evaluation"],
        "dataset": ["dataset"],
    }
    scored = score_item(item(), taxonomy, datetime(2026, 7, 27, 1, tzinfo=UTC))
    assert scored.categories == ["benchmark", "evaluation", "dataset"]
    assert 0 <= scored.total_score <= 100
    assert any("Matched:" in reason for reason in scored.rationale)


def test_agentic_taxonomy_requires_a_scoped_phrase_not_a_bare_word():
    """Regression for issue #52/#57: a bare 'agent' term would match almost
    every 2026 ML paper's related work, the same failure issue #51 hit with
    bare 'benchmark'/'evaluation'. The taxonomy phrase must name an agent
    benchmark/eval itself."""
    taxonomy = {"agentic": ["agent benchmark", "agentic evaluation"]}
    matched = score_item(
        item(
            title="AgentBench-Pro",
            summary="We introduce a new agent benchmark for tool-use reasoning.",
        ),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    unmatched = score_item(
        item(
            title="Scaling Transformers",
            summary="Our agent uses a transformer trained on web-scale data.",
        ),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert matched.categories == ["agentic"]
    assert unmatched.categories == []


AGENTIC_RULE = {
    "within": 15,
    "any_of": ["agent", "agents", "agentic"],
    "near": ["benchmark", "evaluation", "evaluating", "leaderboard", "harness", "bench"],
    "exclude": r"\b(?:position:|survey)",
}


def test_agentic_proximity_rule_matches_non_adjacent_phrasing():
    """Regression for issue #52: the adjacent-phrase list scored 21.7% recall
    because real titles put the agent noun last and interpose qualifiers.
    Neither 'agent benchmark' nor 'benchmark for agent' appears in this title,
    which is the single most common shape in the corpus."""
    scored = score_item(
        item(
            title="DBA-Bench: A Production-Fidelity Benchmark for LLM-Based Database Agents",
            summary="",
        ),
        {"agentic": AGENTIC_RULE},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert scored.categories == ["agentic"]


def test_agentic_proximity_rule_splits_hyphenated_repository_names():
    """A repository carries its whole description in one hyphenated slug, so
    splitting on whitespace alone hid six real agentic artifacts."""
    scored = score_item(
        item(title="solsticestudioai/agent-failure-atlas-benchmark", summary=""),
        {"agentic": AGENTIC_RULE},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert scored.categories == ["agentic"]


def test_agentic_proximity_rule_still_rejects_bare_agent_mentions():
    """Issue #51's lesson survives the widening: an artifact that merely
    mentions an agent, with no evaluation noun anywhere near it, must not be
    tagged agentic."""
    scored = score_item(
        item(
            title="Scaling Transformers",
            summary="Our agent uses a transformer trained on web-scale data.",
        ),
        {"agentic": AGENTIC_RULE},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert scored.categories == []


def test_agentic_proximity_rule_excludes_surveys_and_position_papers():
    """The residual false positives were artifacts that survey or build agents
    rather than evaluate them."""
    scored = score_item(
        item(
            title="Position: Evaluation Scores Are Perishable Knowledge Claims",
            summary="We argue that agent benchmark scores decay.",
        ),
        {"agentic": AGENTIC_RULE},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert scored.categories == []


def test_phrase_terms_do_not_match_inside_a_longer_word():
    """Regression: bare `corpora` matched inside "incorporates" and
    "corporate", tagging unrelated artifacts as datasets. This is the same
    bare-substring failure mode issue #51 raised."""
    taxonomy = {"dataset": ["corpora$"]}
    inside_word = score_item(
        item(title="LowAux-RDNet", summary="The framework incorporates metallic-aware modeling."),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    standalone = score_item(
        item(title="KletterMix", summary="We release two German pretraining corpora."),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert inside_word.categories == []
    assert standalone.categories == ["dataset"]


def test_stem_terms_keep_matching_their_inflections():
    """The right edge stays open without a trailing `$`, because `evaluat` is
    deliberately a stem covering "evaluating" and "evaluated"."""
    taxonomy = {"evaluation": ["evaluat"]}
    for summary in ("We are evaluating agents.", "The model was evaluated.", "An evaluation."):
        scored = score_item(
            item(title="Study", summary=summary),
            taxonomy,
            datetime(2026, 7, 27, 1, tzinfo=UTC),
        )
        assert scored.categories == ["evaluation"], summary


def test_agentic_exclusion_targets_the_genre_not_the_subject():
    """A bare `survey` in the exclusion would drop a real agent benchmark
    about survey responses, which is an active evaluation area."""
    rule = {
        **AGENTIC_RULE,
        "exclude": r"(?:^|: )(?:position:|a survey|survey of|scoping review)|\bwe survey\b",
    }
    genre = score_item(
        item(title="A Survey of LLM Agent Benchmarks", summary=""),
        {"agentic": rule},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    subject = score_item(
        item(
            title="When Synthetic Users Fail: A Benchmark of LLM-Simulated Survey Response",
            summary="We evaluate agents answering survey questions.",
        ),
        {"agentic": rule},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert genre.categories == []
    assert subject.categories == ["agentic"]


def test_taxonomy_still_accepts_plain_phrase_lists():
    """The three categories measured as working keep their exact semantics, so
    both config shapes must stay supported."""
    scored = score_item(
        item(title="A new benchmark", summary="We release a dataset."),
        {"benchmark": ["benchmark"], "dataset": ["dataset"]},
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert scored.categories == ["benchmark", "dataset"]


def test_templated_summaries_fail_the_run():
    """Regression: 26/30 records once shared 'Dataset repository updated on
    Hugging Face.', which told the reader nothing and inflated relevance
    because score_item reads `summary`."""
    templated = [
        item(source_id=f"org/repo-{n}", summary="Dataset repository updated on Hugging Face.")
        for n in range(5)
    ]
    with pytest.raises(RuntimeError, match="templated descriptions"):
        assert_no_boilerplate_summaries(templated)


def test_distinct_and_empty_summaries_are_allowed():
    varied = [item(source_id=f"org/repo-{n}", summary=f"Distinct finding {n}.") for n in range(5)]
    # Many empty summaries are legitimate: those repos published no card.
    varied.extend(item(source_id=f"org/bare-{n}", summary="") for n in range(5))
    assert_no_boilerplate_summaries(varied)


def test_boilerplate_summary_cannot_earn_relevance():
    """The old template contained taxonomy words, so every Hugging Face record
    scored a free `dataset` category regardless of its content."""
    taxonomy = {"benchmark": ["benchmark"], "dataset": ["dataset"]}
    bare = score_item(
        item(source="Hugging Face", title="Weyaxi/followers-leaderboard", summary=""),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    assert "dataset" not in bare.categories


def test_low_value_follower_leaderboard_is_explicitly_demoted():
    taxonomy = {"benchmark": ["leaderboard"], "dataset": ["dataset"]}
    low_value = score_item(
        item(
            source="Hugging Face",
            source_id="Weyaxi/followers-leaderboard",
            title="Weyaxi/followers-leaderboard",
            summary="Follower Leaderboard's History Dataset.",
        ),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )
    real_release = score_item(
        item(
            source="Hugging Face",
            source_id="org/model-eval",
            title="Model Evaluation Leaderboard",
            summary="Dataset of verified model evaluation results.",
        ),
        taxonomy,
        datetime(2026, 7, 27, 1, tzinfo=UTC),
    )

    assert low_value.relevance_score == 0
    assert real_release.relevance_score == 50
    assert real_release.total_score > low_value.total_score
    assert any("Demoted: follower-count leaderboard" in reason for reason in low_value.rationale)


def test_recency_uses_the_configured_collection_window():
    taxonomy = {"benchmark": ["benchmark"]}
    published = datetime(2026, 7, 27, tzinfo=UTC)

    halfway = score_item(
        item(published_at=published),
        taxonomy,
        published + timedelta(hours=24),
        lookback_hours=48,
    )
    expired = score_item(
        item(published_at=published),
        taxonomy,
        published + timedelta(hours=48),
        lookback_hours=48,
    )

    assert halfway.recency_score == 50
    assert expired.recency_score == 0


def test_visualization_companion_is_suppressed_from_pipeline(monkeypatch):
    companion = item(
        source="Hugging Face",
        source_id="org/leaderboard-cases",
        title="Leaderboard Case Assets",
        summary=(
            "This dataset stores compact browser assets and is a visualization "
            "companion, not an evaluation dataset."
        ),
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "huggingface",
        lambda config, since, limit: [companion],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {
            "benchmark": ["leaderboard"],
            "evaluation": ["evaluation"],
            "dataset": ["dataset"],
        },
        "sources": {"huggingface": {"enabled": True, "required": True}},
    }

    run = run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC))

    assert run.items == []
    assert run.selection["suppressed_low_value"] == 1


def test_watchlist_matches_aliases_across_fields():
    by_title = item(title="PaperBench: replicating research")
    by_source_id = item(source="GitHub", source_id="openai/mle-bench", title="openai/mle-bench")
    unrelated = item(title="An unrelated corpus release")

    tagged = apply_watchlist([by_title, by_source_id, unrelated], WATCHLIST)

    assert [record.watchlist for record in tagged] == ["PaperBench", "MLE-bench", None]
    assert tagged[0].watchlist_note == "Paper replication."
    assert "Watchlist: PaperBench" in tagged[0].rationale


def test_watchlist_ignores_passing_mentions_in_the_summary():
    # A watchlisted name inside an abstract is related work, not a release.
    mention = item(
        title="A survey of agent evaluation practice",
        summary="We compare against PaperBench and other suites.",
    )

    assert apply_watchlist([mention], WATCHLIST)[0].watchlist is None


def test_watchlist_matches_on_word_boundaries_and_separators():
    spaced = item(title="MLE bench results", source_id="a/b")
    underscored = item(title="mle_bench harness", source_id="a/c")
    embedded = item(title="Nonmlebenchmarking of models", source_id="a/d")

    tagged = apply_watchlist([spaced, underscored, embedded], WATCHLIST)

    assert [record.watchlist for record in tagged] == ["MLE-bench", "MLE-bench", None]


def test_watchlist_does_not_alter_scores():
    taxonomy = {"benchmark": ["benchmark"]}
    scored = score_item(item(title="PaperBench"), taxonomy, datetime(2026, 7, 27, tzinfo=UTC))
    before = scored.total_score

    apply_watchlist([scored], WATCHLIST)

    assert scored.watchlist == "PaperBench"
    assert scored.total_score == before


def test_watchlist_record_publishes_below_threshold(monkeypatch):
    # Named artifacts are published even when the generic score would drop them.
    tracked = item(title="mlebench release", summary="", source="GitHub", source_id="o/mlebench")
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [tracked],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 99,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True, "required": True}},
        "watchlist": WATCHLIST,
    }

    run = run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC))

    assert [record.watchlist for record in run.items] == ["MLE-bench"]


def test_selection_counts_expose_the_published_gap(monkeypatch):
    records = [
        item(
            source="GitHub",
            source_id=f"org/repo{index}",
            title=f"A distinct benchmark repository number {index}",
            url=f"https://github.com/org/repo{index}",
            summary=f"Benchmark suite number {index} for language model evaluation.",
        )
        for index in range(5)
    ]
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: records,
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 2,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True, "required": True}},
    }

    run = run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC))

    assert run.selection["fetched"] == 5
    assert run.selection["qualified"] == 5
    assert run.selection["published"] == 2
    assert len(run.items) == 2


def test_pipeline_quarantines_future_dated_records_before_scoring(monkeypatch):
    current = item(
        source="GitHub",
        source_id="org/current",
        url="https://github.com/org/current",
        published_at=datetime(2026, 7, 27, 11, tzinfo=UTC),
    )
    future = item(
        source="GitHub",
        source_id="org/future",
        url="https://github.com/org/future",
        published_at=datetime(2050, 1, 1, tzinfo=UTC),
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [current, future],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True, "required": True}},
    }

    run = run_pipeline(config, datetime(2026, 7, 27, 12, tzinfo=UTC))

    assert [record.source_id for record in run.items] == ["org/current"]
    assert run.health[0].item_count == 1
    assert run.health[0].error == "Discarded 1 future-dated record(s)"
    assert run.selection["fetched"] == 2
    assert run.selection["suppressed_future_dated"] == 1


def test_pipeline_accounts_for_future_records_rejected_inside_a_connector(monkeypatch):
    current = item(
        source="Hugging Face",
        source_id="org/current",
        published_at=datetime(2026, 7, 27, 11, tzinfo=UTC),
    )

    def fetch(config, since, limit):
        config["_future_rejections"] = 1
        return [current]

    pipeline = __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"])
    monkeypatch.setitem(pipeline.SOURCE_FETCHERS, "huggingface", fetch)
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"huggingface": {"enabled": True, "required": True}},
    }

    run = run_pipeline(config, datetime(2026, 7, 27, 12, tzinfo=UTC))

    assert run.health[0].item_count == 1
    assert run.health[0].error == "Discarded 1 future-dated record(s)"
    assert run.selection["fetched"] == 2
    assert run.selection["suppressed_future_dated"] == 1


def test_optional_source_failure_streak_persists_and_resets(monkeypatch):
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"])

    def fail(config, since, limit):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setitem(pipeline.SOURCE_FETCHERS, "optional_fixture", fail)
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"optional_fixture": {"enabled": True}},
    }
    previous = None
    for hour in range(3):
        run = run_pipeline(
            config,
            datetime(2026, 7, 27, hour, tzinfo=UTC),
            previous_snapshot=previous,
        )
        previous = {"discovery_state": run.discovery_state}

    assert run.discovery_state["source_failure_streaks"] == {'["evidence","optional_fixture"]': 3}

    monkeypatch.setitem(pipeline.SOURCE_FETCHERS, "optional_fixture", lambda c, s, limit: [])
    recovered = run_pipeline(
        config,
        datetime(2026, 7, 27, 4, tzinfo=UTC),
        previous_snapshot=previous,
    )
    assert recovered.discovery_state["source_failure_streaks"] == {}


def test_attention_failure_participates_in_persistent_streaks(monkeypatch):
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["fetch_attention_feeds"])
    monkeypatch.setattr(
        pipeline,
        "fetch_attention_feeds",
        lambda *args, **kwargs: (
            [],
            [
                SourceHealth(
                    source="Hacker News collector",
                    kind="attention",
                    ok=False,
                    error="HTTP 503",
                )
            ],
            [],
            {},
        ),
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {},
        "attention": {"hacker_news": {"enabled": True}},
    }
    previous = None
    for hour in range(3):
        run = run_pipeline(
            config,
            datetime(2026, 7, 27, hour, tzinfo=UTC),
            previous_snapshot=previous,
        )
        previous = {"discovery_state": run.discovery_state}

    assert run.discovery_state["source_failure_streaks"] == {
        '["attention","Hacker News collector"]': 3
    }


def test_attention_producer_failure_participates_in_persistent_streaks(monkeypatch):
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["fetch_attention_feeds"])
    monkeypatch.setattr(
        pipeline,
        "fetch_attention_feeds",
        lambda *args, **kwargs: (
            [],
            [SourceHealth(source="Fixture feed", kind="attention", ok=True)],
            [
                ProducerHealth(
                    producer="fixture-producer",
                    source="Hacker News",
                    ok=False,
                    error="HTTP 503",
                )
            ],
            {},
        ),
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {},
    }
    previous = {
        "discovery_state": {
            "source_failure_streaks": {'["producer","fixture-producer","Hacker News"]': 2}
        }
    }

    run = run_pipeline(
        config,
        datetime(2026, 7, 27, tzinfo=UTC),
        previous_snapshot=previous,
    )

    assert run.discovery_state["source_failure_streaks"] == {
        '["producer","fixture-producer","Hacker News"]': 3
    }


def test_attention_producer_streaks_do_not_cross_producer_boundaries(monkeypatch):
    pipeline = __import__("benchmark_radar.pipeline", fromlist=["fetch_attention_feeds"])
    monkeypatch.setattr(
        pipeline,
        "fetch_attention_feeds",
        lambda *args, **kwargs: (
            [],
            [],
            [
                ProducerHealth(
                    producer="producer-b",
                    source="Hacker News",
                    ok=False,
                    error="HTTP 503",
                )
            ],
            {},
        ),
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {},
        "sources": {},
    }
    previous = {
        "discovery_state": {
            "source_failure_streaks": {'["producer","producer-a","Hacker News"]': 2}
        }
    }

    run = run_pipeline(
        config,
        datetime(2026, 7, 27, tzinfo=UTC),
        previous_snapshot=previous,
    )

    assert run.discovery_state["source_failure_streaks"] == {
        '["producer","producer-b","Hacker News"]': 1
    }


def test_attention_producer_streak_key_is_unambiguous():
    from benchmark_radar.pipeline import _failure_streak_key

    first = ProducerHealth(producer="a:b", source="c", ok=False)
    second = ProducerHealth(producer="a", source="b:c", ok=False)

    assert _failure_streak_key("producer", first) != _failure_streak_key("producer", second)


def test_funnel_counts_suppressed_arxiv_records_as_fetched(monkeypatch):
    # Source health counts these as fetched, so the funnel must agree rather
    # than reporting zero for a source that plainly returned records.
    seen = item(source_id="2607.12345", updated_at=datetime(2026, 7, 26, 18, tzinfo=UTC))
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "arxiv",
        lambda config, since, limit: [seen],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"arxiv": {"enabled": True, "required": True}},
    }
    previous = {
        "discovery_state": {
            "arxiv": {
                "2607.12345": {
                    "discovered_at": "2026-07-26T19:00:00+00:00",
                    "last_activity_at": "2026-07-26T18:00:00+00:00",
                }
            }
        }
    }

    run = run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC), previous_snapshot=previous)

    assert run.items == []
    assert run.health[0].item_count == 1
    assert run.selection["fetched"] == 1
    assert run.selection["suppressed_as_seen"] == 1


def test_funnel_names_watchlist_bypasses_separately(monkeypatch):
    tracked = item(title="mlebench release", summary="", source="GitHub", source_id="o/mlebench")
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [tracked],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 99,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"github": {"enabled": True, "required": True}},
        "watchlist": WATCHLIST,
    }

    run = run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC))

    assert run.selection["qualified"] == 1
    assert run.selection["watchlisted"] == 1


def test_every_required_source_must_return_records(monkeypatch):
    def empty_fetcher(config, since, limit):
        return []

    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "required_fixture",
        empty_fetcher,
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"required_fixture": {"enabled": True, "required": True}},
    }

    with pytest.raises(
        RuntimeError,
        match="required_fixture returned no records",
    ):
        run_pipeline(config, datetime(2026, 7, 27, tzinfo=UTC))


def test_required_source_can_explicitly_allow_empty(monkeypatch):
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "required_fixture",
        lambda config, since, limit: [],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {
            "required_fixture": {
                "enabled": True,
                "required": True,
                "allow_empty": True,
            }
        },
    }

    run = run_pipeline(config, datetime(2026, 8, 1, tzinfo=UTC))

    assert run.items == []
    assert run.health[0].ok is True
    assert run.health[0].item_count == 0


def test_arxiv_discovery_state_suppresses_unchanged_overlap(monkeypatch):
    unchanged = item(
        source_id="2607.12345",
        updated_at=datetime(2026, 7, 26, 18, tzinfo=UTC),
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "arxiv",
        lambda config, since, limit: [unchanged],
    )
    config = {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {"arxiv": {"enabled": True, "required": True}},
    }
    previous = {
        "discovery_state": {
            "arxiv": {
                "2607.12345": {
                    "discovered_at": "2026-07-26T19:00:00+00:00",
                    "last_activity_at": "2026-07-26T18:00:00+00:00",
                }
            }
        }
    }

    run = run_pipeline(
        config,
        datetime(2026, 7, 27, tzinfo=UTC),
        previous_snapshot=previous,
    )

    assert run.items == []
    assert run.health[0].item_count == 1
    assert run.discovery_state["arxiv"]["2607.12345"]["discovered_at"] == (
        "2026-07-26T19:00:00+00:00"
    )


def test_dedupe_merges_short_titles_across_sources():
    # A title under the 24-character threshold used to fall back to a URL key,
    # which can never match across sources, so well-known short-named repos
    # were the ones dedup could not merge.
    repo = item(
        source="GitHub",
        source_id="torchgeo/torchgeo",
        title="torchgeo/torchgeo",
        url="https://github.com/torchgeo/torchgeo",
    )
    mirror = item(
        source="Hugging Face",
        source_id="x/y",
        title="torchgeo/torchgeo",
        url="https://huggingface.co/datasets/x/y",
        artifact_urls=["https://github.com/torchgeo/torchgeo"],
    )
    result = deduplicate([repo, mirror])

    assert len(result) == 1
    assert any("Also found via" in reason for reason in result[0].rationale)


def test_dedupe_matches_on_a_weaker_shared_identifier():
    # The paper resolves to its arXiv id and the repository to its owner/repo,
    # so comparing only the strongest identifier never merges them.
    paper = item(artifact_urls=["https://github.com/org/repo"])
    repo = item(
        source="GitHub",
        source_id="org/repo",
        title="A Completely Different Repository Name",
        url="https://github.com/org/repo",
    )

    assert len(deduplicate([paper, repo])) == 1


def test_dedupe_keeps_unrelated_records_apart():
    first = item(
        source_id="1111.2222",
        title="First Distinct Benchmark Paper About Things",
        url="https://arxiv.org/abs/1111.2222",
    )
    second = item(
        source_id="3333.4444",
        title="Second Unrelated Dataset Paper Entirely",
        url="https://arxiv.org/abs/3333.4444",
    )

    assert len(deduplicate([first, second])) == 2


def test_dedupe_preserves_authors_and_summary_from_the_absorbed_copy():
    described = item(
        source="GitHub",
        source_id="org/repo2",
        title="Same Long Title For Merge Testing Purposes",
        url="https://github.com/org/repo2",
        authors=["Alice"],
        summary="A real card.",
    )
    bare = item(
        title="Same Long Title For Merge Testing Purposes",
        url="https://arxiv.org/abs/9999.1111",
        source_id="9999.1111",
        summary="",
        authors=["Bob"],
        published_at=datetime(2026, 7, 27, 6, tzinfo=UTC),
    )
    merged = deduplicate([described, bare])[0]

    assert set(merged.authors) == {"Alice", "Bob"}
    assert merged.summary == "A real card."


def test_suppression_is_not_bypassed_by_the_watchlist():
    # `item.watchlist or (not item.suppression_reasons and ...)` short-circuited,
    # so a watchlisted record published even after matching a suppress rule.
    source = Path("src/benchmark_radar/pipeline.py").read_text(encoding="utf-8")

    assert "if not item.suppression_reasons" in source
    index = source.index("if not item.suppression_reasons")
    assert "item.watchlist" in source[index : index + 400]
    assert "if item.watchlist\n        or (" not in source


def _backfill_config():
    return {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {
            "arxiv": {"enabled": True, "required": True},
            "github": {"enabled": True, "required": True},
            "huggingface": {"enabled": True, "required": True},
        },
    }


def test_simulate_backfill_fetches_each_source_once_for_every_date(monkeypatch):
    calls = []

    def fake_github(config, since, limit):
        calls.append(since)
        return [
            item(
                source="GitHub",
                source_id="org/repo",
                title="A benchmark repository for evaluation",
                url="https://github.com/org/repo",
                summary="Benchmark suite for language model evaluation.",
                published_at=datetime(2026, 7, 10, tzinfo=UTC),
            )
        ]

    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        fake_github,
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "huggingface",
        lambda config, since, limit: [],
    )
    dates = [datetime(2026, 7, 11, tzinfo=UTC), datetime(2026, 7, 12, tzinfo=UTC)]

    runs = simulate_backfill(_backfill_config(), dates)

    assert len(calls) == 1, "each connector must be queried once, not once per simulated date"
    assert [run.generated_at for run in runs] == dates
    assert all(
        item_.title.startswith("A benchmark repository") for run in runs for item_ in run.items
    )


def test_simulate_backfill_excludes_items_published_after_the_simulated_date(monkeypatch):
    early = item(
        source="GitHub",
        source_id="org/early",
        title="An early benchmark repository release",
        url="https://github.com/org/early",
        summary="Benchmark suite released early for language model evaluation.",
        published_at=datetime(2026, 7, 4, tzinfo=UTC),
    )
    late = item(
        source="GitHub",
        source_id="org/late",
        title="A later benchmark repository release",
        url="https://github.com/org/late",
        summary="Benchmark suite released later for language model evaluation.",
        published_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [early, late],
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "huggingface",
        lambda config, since, limit: [],
    )

    [run] = simulate_backfill(_backfill_config(), [datetime(2026, 7, 5, tzinfo=UTC)])

    titles = {item_.source_id for item_ in run.items}
    assert titles == {"org/early"}


def test_simulate_backfill_marks_arxiv_as_a_known_limitation(monkeypatch):
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [],
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "huggingface",
        lambda config, since, limit: [],
    )

    [run] = simulate_backfill(_backfill_config(), [datetime(2026, 7, 5, tzinfo=UTC)])

    arxiv_health = [health for health in run.health if health.source == "arxiv"]
    assert arxiv_health and arxiv_health[0].ok is False
    assert run.selection["simulated"] is True


def test_simulate_backfill_requires_dates_sorted_oldest_first():
    with pytest.raises(ValueError):
        simulate_backfill(
            _backfill_config(),
            [datetime(2026, 7, 12, tzinfo=UTC), datetime(2026, 7, 11, tzinfo=UTC)],
        )


def test_simulate_backfill_chains_discovery_state_across_simulated_dates(monkeypatch):
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "github",
        lambda config, since, limit: [],
    )
    monkeypatch.setitem(
        __import__("benchmark_radar.pipeline", fromlist=["SOURCE_FETCHERS"]).SOURCE_FETCHERS,
        "huggingface",
        lambda config, since, limit: [],
    )
    previous = {
        "discovery_state": {"arxiv": {"seed": {"discovered_at": "2026-07-01T00:00:00+00:00"}}}
    }

    runs = simulate_backfill(
        _backfill_config(),
        [datetime(2026, 7, 11, tzinfo=UTC), datetime(2026, 7, 12, tzinfo=UTC)],
        previous_snapshot=previous,
    )

    assert all(run.discovery_state["arxiv"]["seed"] for run in runs)
