"""Issue #902: Latest releases must list benchmarks, not models, methods or version tags."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from benchmark_radar.release_kind import (
    BENCHMARK,
    METHOD,
    MODEL,
    SOFTWARE_RELEASE,
    UNCLEAR,
    classify_release_record,
    is_benchmark_release,
)
from benchmark_radar.release_leaderboard import filter_release_cohort

AS_OF = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

# Titles and the sentence that introduces each artifact, taken from the records
# reported in issue #902.
RECORDS: list[dict[str, Any]] = [
    {
        "title": "OmniCompass: A Holistic Benchmark for Omni-Modal Video Grounding",
        "summary": "We introduce OmniCompass, a holistic benchmark for omni-modal video grounding.",
        "source": "arXiv",
        "arxiv": "2610.18829",
        "kind": BENCHMARK,
    },
    {
        "title": "FDE-Gym: The Last Mile of AI Delivery",
        "summary": (
            "Existing agent benchmarks typically evaluate agents on well-specified tasks. "
            "We introduce FDE-Gym, a benchmark of 95 end-to-end delivery tasks."
        ),
        "source": "arXiv",
        "arxiv": "2610.22350",
        "kind": BENCHMARK,
    },
    {
        "title": "VideoJev: System One Model for Video Understanding and Interaction",
        "summary": (
            "We introduce VideoJev, a family of models that cast video understanding as "
            "structured decision tasks. Across three grounding benchmarks, it improves mIoU."
        ),
        "source": "Hugging Face Papers",
        "arxiv": "2610.18615",
        "kind": MODEL,
    },
    {
        "title": "GroundingPI: A Grounding Foundation Model towards Physical Intelligence",
        "summary": (
            "We introduce GroundingPI, a 4B grounding foundation model. Against 44 baselines "
            "across 34 grounding benchmarks it sets a new state of the art."
        ),
        "source": "Semantic Scholar",
        "arxiv": "2609.39601",
        "kind": MODEL,
    },
    {
        "title": "Agent-Reflex: Teaching Language Agents to Act Reflectively",
        "summary": (
            "We propose Agent-Reflex, a general training framework for incentivizing proactive "
            "reflection in agents. It reaches 58.6 on five long-horizon tool-use benchmarks."
        ),
        "source": "arXiv",
        "arxiv": "2610.17953",
        "kind": METHOD,
    },
    {
        "title": "REMORY: Learning Residual Memory for Context Compaction",
        "summary": (
            "We introduce REMORY, a neural memory network that supplements the summary with "
            "soft memory tokens. Across long-horizon agent benchmarks it shows consistent gains."
        ),
        "source": "arXiv",
        "arxiv": "2610.11287",
        "kind": METHOD,
    },
    {
        "title": "openclaw 2026.8.34",
        "summary": "Extended-stable release with security updates and evaluation fixes.",
        "source": "GitHub Release",
        "parser_version": "github-releases/3",
        "kind": SOFTWARE_RELEASE,
    },
]


def _item(record: dict[str, Any], *, event_kind: str = "released") -> dict[str, Any]:
    arxiv = record.get("arxiv")
    url = (
        f"https://arxiv.org/abs/{arxiv}"
        if arxiv
        else "https://github.com/openclaw/openclaw/releases/tag/v2026.8.34"
    )
    return {
        "title": record["title"],
        "summary": record["summary"],
        "source": record["source"],
        "source_id": arxiv or "openclaw/openclaw@v2026.8.34",
        "parser_version": record.get("parser_version", "arxiv-rss/1"),
        "url": url,
        "artifact_urls": [url] if arxiv else ["https://github.com/openclaw/openclaw"],
        "event_kind": event_kind,
        "published_at": "2026-10-13T00:00:00+00:00",
        "discovered_at": "2026-10-14T00:00:00+00:00",
        "categories": ["benchmark"],
    }


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["title"].split(":")[0])
def test_issue_902_records_are_typed(record: dict[str, Any]) -> None:
    assert classify_release_record(_item(record)) == record["kind"]
    assert is_benchmark_release(_item(record)) is (record["kind"] == BENCHMARK)


def test_record_without_a_clear_headline_stays_eligible() -> None:
    item = {
        "title": "Stuck on Shuffle",
        "summary": "Models bind attributes poorly.",
        "source": "arXiv",
    }
    assert classify_release_record(item) == UNCLEAR
    assert is_benchmark_release(item)


def test_benchmark_framework_is_not_mistaken_for_a_method() -> None:
    item = {
        "title": "RealClaw: Sessions from Real Developers",
        "summary": "We introduce RealClaw, a live benchmark framework built from real sessions.",
        "source": "arXiv",
    }
    assert classify_release_record(item) == BENCHMARK


def test_latest_releases_keeps_only_the_two_benchmarks() -> None:
    items = [_item(record) for record in RECORDS]
    snapshot = {
        "date": "2026-10-24",
        "generated_at": AS_OF.isoformat(),
        "evidence_items": items,
    }
    # Published 11 days before AS_OF: outside the 7 day window, inside 30 and 90.
    for window, expected in (
        (7, set()),
        (30, {"OmniCompass", "FDE-Gym"}),
        (90, {"OmniCompass", "FDE-Gym"}),
    ):
        cohort = filter_release_cohort(
            [snapshot], window_days=window, as_of=AS_OF, include_unconfirmed=True
        )
        assert {entry["name"].split(":")[0] for entry in cohort} == expected


def test_typed_out_records_stay_in_the_snapshot_corpus() -> None:
    items = [_item(record) for record in RECORDS]
    snapshot = {"date": "2026-10-24", "generated_at": AS_OF.isoformat(), "evidence_items": items}
    filter_release_cohort([snapshot], window_days=30, as_of=AS_OF, include_unconfirmed=True)
    assert len(snapshot["evidence_items"]) == len(RECORDS)


def test_model_noun_inside_a_benchmark_name_does_not_make_it_a_model() -> None:
    item = {
        "title": "World Models' Last Exam in Physics",
        "summary": (
            "We introduce World Models' Last Exam in Physics, a measurement-based benchmark "
            "for physical reasoning."
        ),
        "source": "arXiv",
    }
    assert classify_release_record(item) == BENCHMARK
    # The title carries no benchmark word, so only the descriptor can decide.
    item["title"] = "Last Exam in Physics"
    assert classify_release_record(item) == BENCHMARK


def test_coordinated_descriptor_with_a_benchmark_noun_is_a_benchmark() -> None:
    item = {
        "title": "WOVEN",
        "summary": "We introduce WOVEN, a training source and benchmark for video reasoning.",
        "source": "arXiv",
    }
    assert classify_release_record(item) == BENCHMARK
    item["summary"] = "We propose X, a training framework for agents evaluated on benchmarks."
    assert classify_release_record(item) == METHOD


# Headline sentences from the committed snapshots named in issue #961.
# OneSearch-VL is data/snapshots/2026-10-09.json; HybridResearcher is
# 2026-10-20.json; Orchestra is 2026-10-14.json. Each is event_kind released,
# and the title does not itself contain a benchmark word.
AGENT_HARNESS_RECORDS: list[dict[str, Any]] = [
    {
        "title": "OneSearch-VL: Unified Multimodal Deep Research Agent for Image and Video",
        "summary": (
            "We introduce OneSearch-VL, a unified agent centered on the Visually Grounded "
            "Evidence Graph (VGEG), which encodes these dependencies as a shared task-level "
            "reference for data construction, process supervision, and operation-level evaluation."
        ),
        "source": "arXiv",
        "arxiv": "2610.12419",
        "kind": "agent",
    },
    {
        "title": (
            "HybridResearcher: Bridging the Structured-Unstructured Boundary "
            "for Deep Research Agents"
        ),
        "summary": (
            "To address this, we introduce HybridResearcher, a 4B agent trained to bridge "
            "evidence across the structured and unstructured boundary."
        ),
        "source": "arXiv",
        "arxiv": "2610.24899",
        "kind": "agent",
    },
    {
        "title": (
            "Let the Mind Conceive, Let the Hand Achieve: Following Multimodal Instructions "
            "for Long-Horizon Robotic Manipulation"
        ),
        "summary": (
            "To address these challenges, we introduce Orchestra, an agent harness that "
            "separates task planning and execution management from action generation."
        ),
        "source": "arXiv",
        "arxiv": "2610.18352",
        "kind": "agent",
    },
]


@pytest.mark.parametrize(
    "record",
    AGENT_HARNESS_RECORDS,
    ids=("OneSearch-VL", "HybridResearcher", "Orchestra"),
)
def test_issue_961_agent_papers_are_not_benchmark_releases(record: dict[str, Any]) -> None:
    item = _item(record)
    assert classify_release_record(item) == record["kind"]
    assert is_benchmark_release(item) is False


def test_a_standalone_harness_is_not_a_benchmark_release() -> None:
    item = {
        "title": "StepKeeper",
        "summary": "We introduce StepKeeper, a harness for long-horizon robot instructions.",
        "source": "arXiv",
    }
    assert classify_release_record(item) == "harness"
    assert is_benchmark_release(item) is False


def test_agent_and_harness_papers_leave_latest_releases_and_stay_in_the_corpus() -> None:
    items = [_item(record) for record in AGENT_HARNESS_RECORDS]
    snapshot = {
        "date": "2026-10-24",
        "generated_at": AS_OF.isoformat(),
        "evidence_items": items,
    }
    corpus_count = len(snapshot["evidence_items"])
    cohort = filter_release_cohort(
        [snapshot], window_days=30, as_of=AS_OF, include_unconfirmed=True
    )
    assert cohort == []
    assert len(snapshot["evidence_items"]) == corpus_count


def test_an_agent_benchmark_and_an_evaluation_harness_stay_benchmarks() -> None:
    agent_benchmark = {
        "title": "ToolLoop",
        "summary": "We introduce ToolLoop, an agent benchmark for multi-step tools.",
        "source": "arXiv",
    }
    evaluation_harness = {
        "title": "EvalLoop",
        "summary": "We introduce EvalLoop, an evaluation harness for tool-using agents.",
        "source": "arXiv",
    }
    assert classify_release_record(agent_benchmark) == BENCHMARK
    assert classify_release_record(evaluation_harness) == BENCHMARK


# Introducing sentences from the committed snapshots cited in PR #962's review.
# CABRA: 2026-10-09; WideSWE: 2026-09-29; ReproBAIT: 2026-10-16;
# BACKDROP: 2026-10-01. The final case covers the same shape for a harness.
@pytest.mark.parametrize(
    ("title", "summary"),
    [
        (
            "Code Understanding is a Bottleneck for Coding Agents",
            "We present CABRA: a Coding Ability Blueprint for Rigorous Agent evaluation.",
        ),
        (
            "WideSWE: Can Coding Agents Coordinate Changes Across Repositories?",
            "We introduce WideSWE to evaluate coding agents on such cross-repository tasks.",
        ),
        (
            "ReproBAIT: Can coding agents build their own biological AI tools?",
            "We introduce an evaluation titled ReproBAIT (Reproducing Biological AI Tools), "
            "which measures the ability of coding agents to design, implement, and train "
            "biological AI tools taken from published research across a range of "
            "information access conditions.",
        ),
        (
            "The Backdrop Exposes What the World Around an Agent Costs It",
            "We present BACKDROP, which asks how much of an agent's capability in a clean "
            "world survives in such a world.",
        ),
        (
            "ToolScope",
            "We present ToolScope, a diagnostic for tool harnesses.",
        ),
    ],
    ids=("CABRA", "WideSWE", "ReproBAIT", "BACKDROP", "harness-target"),
)
def test_evaluation_targets_do_not_exclude_benchmark_releases(title: str, summary: str) -> None:
    item = _item({"title": title, "summary": summary, "source": "arXiv", "arxiv": "2610.10610"})
    assert classify_release_record(item) == UNCLEAR
    assert is_benchmark_release(item)
    snapshot = {"date": "2026-10-24", "generated_at": AS_OF.isoformat(), "evidence_items": [item]}
    cohort = filter_release_cohort(
        [snapshot], window_days=30, as_of=AS_OF, include_unconfirmed=True
    )
    assert [entry["name"] for entry in cohort] == [title]
    assert snapshot["evidence_items"] == [item]
