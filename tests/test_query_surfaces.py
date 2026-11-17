from __future__ import annotations

import csv
import json
import shutil
import threading
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from benchmark_radar.citation import (
    ARXIV_ID,
    ARXIV_URL,
    apa_citation,
    bibtex_citation,
    citation_block,
    latex_citation,
)
from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.pipeline import deduplicate
from benchmark_radar.query import QueryError, QueryPaths, QueryService, _tokens
from benchmark_radar.query_cli import run_query_cli
from benchmark_radar.query_http import create_query_server
from benchmark_radar.snapshots import load_snapshots, write_snapshot
from benchmark_radar.sources import fetch_huggingface


def _unrelated_snapshot_registry(tmp_path: Path) -> None:
    """A valid crawl registry whose only snapshot belongs to no fixture source.

    A real checkout always has data/leaderboard_snapshots.yml, and trace
    reports its absence as a missing crawl input. Fixture records then take
    the "no snapshot for this source" path unless a test writes its own.
    """
    data_dir = tmp_path / "data"
    (data_dir / "leaderboard_snapshots").mkdir(parents=True, exist_ok=True)
    (data_dir / "leaderboard_snapshots" / "unrelated.csv").write_text(
        "benchmark_id,name\nunrelated,Unrelated\n", encoding="utf-8"
    )
    (data_dir / "leaderboard_snapshots.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "snapshots": [
                    {
                        "id": "unrelated_fixture_2026-08-17",
                        "source": "Unrelated Fixture",
                        "source_url": "https://example.com/unrelated",
                        "crawled_at": "2026-08-17T00:00:00Z",
                        "benchmark_file": "leaderboard_snapshots/unrelated.csv",
                        "benchmark_count": 1,
                        "score_series_policy": "preserve_empty",
                        "benchmark_columns": {
                            "benchmark_id": "benchmark_id",
                            "benchmark_name": "name",
                        },
                        "columns": {"benchmark_id": "benchmark_id", "benchmark_name": "name"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _catalog(tmp_path: Path) -> QueryPaths:
    index_path = tmp_path / "site" / "data" / "benchmark-index.json"
    shard_dir = index_path.parent / "benchmarks"
    snapshot_dir = tmp_path / "data" / "snapshots"
    index_path.parent.mkdir(parents=True)
    shard_dir.mkdir()
    _unrelated_snapshot_registry(tmp_path)
    records = [
        {
            "slug": "opencompass-agent-workbench",
            "key": "opencompass:agent-workbench",
            "name": "Agent Workbench",
            "source": "opencompass_hub",
            "publisher": "Example Lab",
            "released": "2026-01-01",
            "openness": "open",
            "modality": "text",
            "description": "Long-horizon coding agent evaluation with executable tasks.",
            "categories": ["agent", "coding"],
            "languages": ["en"],
            "score_count": 4,
            "has_paper": True,
            "has_repo": True,
            "has_dataset": True,
            "has_size": True,
        },
        {
            "slug": "llm-stats-agent-workbench-extended",
            "key": "llm-stats:agent-workbench-extended",
            "name": "Agent Workbench Extended",
            "source": "llm_stats",
            "publisher": None,
            "released": None,
            "openness": "unknown",
            "modality": "text",
            "description": "",
            "categories": ["agent"],
            "languages": [],
            "score_count": 12,
            "has_paper": False,
            "has_repo": False,
            "has_dataset": False,
            "has_size": False,
        },
        {
            "slug": "opencompass-science-discovery",
            "key": "opencompass:science-discovery",
            "name": "Science Discovery Suite",
            "source": "opencompass_hub",
            "publisher": "Research Institute",
            "released": "2025-12-01",
            "openness": "restricted",
            "modality": "multimodal",
            "description": "A benchmark for scientific discovery agents.",
            "categories": ["science"],
            "languages": ["en", "zh"],
            "score_count": 0,
            "has_paper": True,
            "has_repo": True,
            "has_dataset": False,
            "has_size": False,
        },
    ]
    index_path.write_text(
        json.dumps({"schema_version": 1, "count": len(records), "benchmarks": records}),
        encoding="utf-8",
    )
    for record in records:
        (shard_dir / f"{record['slug']}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "record": {
                        **record,
                        "artifacts": [
                            {"kind": "repo", "url": "https://github.com/example/benchmark"}
                        ]
                        if record["has_repo"]
                        else [],
                    },
                    "siblings": [],
                    "scores_by_source": {},
                }
            ),
            encoding="utf-8",
        )

    generated_at = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
    write_snapshot(
        RadarRun(
            generated_at=generated_at,
            since=generated_at - timedelta(hours=48),
            items=[
                RadarItem(
                    source="GitHub",
                    source_id="example/new-agent-bench",
                    title="New Agent Memory Benchmark",
                    url="https://github.com/example/new-agent-bench",
                    published_at=generated_at - timedelta(hours=1),
                    summary="Evaluates persistent memory in long-running coding agents.",
                    categories=["benchmark", "agentic"],
                    recommended=True,
                )
            ],
            health=[
                SourceHealth(source=source, ok=True, item_count=1, method="API")
                for source in ("arxiv", "github", "huggingface")
            ],
        ),
        snapshot_dir,
    )
    return QueryPaths(index=index_path, shards=shard_dir, snapshots=snapshot_dir)


def test_search_and_detail_expose_reviewed_identity_siblings(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    related = {
        "slug": "claire-agent-workbench",
        "key": "claire-radar:agent-workbench",
        "name": "Agent Workbench",
        "source": "claire_radar",
        "publisher": None,
        "released": None,
        "openness": "unknown",
        "modality": "text",
        "description": "Imported source record for the same reviewed benchmark identity.",
        "categories": ["agent", "coding"],
        "languages": [],
        "score_count": 0,
        "has_paper": True,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }
    index["benchmarks"].append(related)
    index["count"] += 1
    paths.index.write_text(json.dumps(index), encoding="utf-8")
    (paths.shards / f"{related['slug']}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": related,
                "siblings": [
                    {
                        "key": "opencompass:agent-workbench",
                        "slug": "opencompass-agent-workbench",
                        "name": "Agent Workbench",
                        "source": "opencompass_hub",
                        "relation": "equivalent",
                    }
                ],
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )

    service = QueryService(paths)
    search = service.search("Agent Workbench", scope="catalog", limit=10)
    detail = service.show("claire-radar:agent-workbench")

    assert {row["key"] for row in search["results"]} >= {
        "claire-radar:agent-workbench",
        "opencompass:agent-workbench",
    }
    assert detail["benchmark"]["siblings"] == [
        {
            "key": "opencompass:agent-workbench",
            "slug": "opencompass-agent-workbench",
            "name": "Agent Workbench",
            "source": "opencompass_hub",
            "relation": "equivalent",
        }
    ]


def test_catalog_search_is_deterministic_and_explains_matches(tmp_path: Path) -> None:
    # Regression: interface-specific ranking would let CLI and HTTP disagree.
    service = QueryService(_catalog(tmp_path))

    result = service.search("agent workbench", scope="catalog", limit=10)

    assert [item["key"] for item in result["results"][:2]] == [
        "opencompass:agent-workbench",
        "llm-stats:agent-workbench-extended",
    ]
    assert result["retrieval_mode"] == "lexical"
    assert result["search_status"] == "full_matches_found"
    assert result["candidate_count"] == 2
    assert result["total_matches"] == 2
    assert result["full_match_count"] == 2
    assert result["partial_match_count"] == 0
    assert result["matching_policy"]["name"] == "lexical_candidates_v2"
    assert result["matching_policy"]["ranking"] == "bm25f_v3"
    assert result["results"][0]["match"]["matched_fields"] == [
        "name",
        "description",
        "categories",
    ]
    assert result["results"][0]["match"]["reason"] == "exact name match"
    assert result["results"][0]["match"]["retrieval_score"] > 0
    assert result["results"][0]["match"]["idf_coverage"] == pytest.approx(1.0)
    assert result["data"]["catalog_count"] == 3


def test_catalog_search_accepts_chinese_terms_present_in_source_text(tmp_path: Path) -> None:
    # OpenCompass descriptions contain Chinese evidence that ASCII-only tokens hid.
    paths = _catalog(tmp_path)
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    index["benchmarks"][0]["description"] = "中文语义相似度评测。"
    paths.index.write_text(json.dumps(index), encoding="utf-8")

    result = QueryService(paths).search("中文语义", scope="catalog")

    assert result["search_status"] == "full_matches_found"
    assert result["results"][0]["key"] == "opencompass:agent-workbench"
    assert result["results"][0]["match"]["matched_tokens"] == ["中文", "文语", "语义"]


def test_chinese_description_does_not_reweight_english_search(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    baseline = QueryService(paths).search("agent workbench", scope="catalog")
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    index["benchmarks"][2]["description"] += " 中文语义相似度评测。"
    paths.index.write_text(json.dumps(index), encoding="utf-8")

    after = QueryService(paths).search("agent workbench", scope="catalog")
    assert [item["key"] for item in after["results"]] == [
        item["key"] for item in baseline["results"]
    ]
    assert [item["match"]["retrieval_score"] for item in after["results"]] == [
        item["match"]["retrieval_score"] for item in baseline["results"]
    ]


def test_kana_before_han_does_not_hide_the_han_phrase(tmp_path: Path) -> None:
    # A generic letter run starting at kana used to swallow the following Han
    # characters into one token, so a Japanese description never matched them.
    paths = _catalog(tmp_path)
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    index["benchmarks"][0]["description"] = "ひらがなで書かれた中文語義の評価。"
    paths.index.write_text(json.dumps(index), encoding="utf-8")

    for query in ("中文語義", "ひらがな"):
        result = QueryService(paths).search(query, scope="catalog")
        assert result["search_status"] == "full_matches_found"
        assert result["results"][0]["key"] == "opencompass:agent-workbench"
    assert _tokens("ひらがな") == ("ひら", "らが", "がな")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Łódź", ("o", "dz")), ("Ørsted", ("rsted",)), ("café Straße", ("cafe", "strasse"))],
)
def test_latin_text_keeps_ascii_tokens(text: str, expected: tuple[str, ...]) -> None:
    # Non-ASCII Latin letters must not start new tokens; English scores depend
    # on the ASCII token population staying the same as before Unicode support.
    assert _tokens(text) == expected


@pytest.mark.parametrize("source", ["model_reports", "llm_stats", "artificial_analysis"])
def test_registered_aliases_are_searchable_for_every_source(tmp_path: Path, source: str) -> None:
    paths = _catalog(tmp_path)
    payload = json.loads(paths.index.read_text())
    payload["benchmarks"][0].update(source=source, aliases=["Exact Registered Alias"])
    paths.index.write_text(json.dumps(payload))
    result = QueryService(paths).search("Exact Registered Alias", scope="catalog")
    assert result["search_status"] == "full_matches_found"
    assert result["results"][0]["key"] == "opencompass:agent-workbench"
    assert "name" in result["results"][0]["match"]["matched_fields"]


def test_search_returns_partial_candidates_with_evidence_for_agent_judgment(
    tmp_path: Path,
) -> None:
    service = QueryService(_catalog(tmp_path))

    result = service.search("protein agent prediction", scope="catalog", limit=10)

    assert result["search_status"] == "partial_candidates_only"
    assert result["candidate_count"] == 2
    assert result["total_matches"] == 2
    assert result["full_match_count"] == 0
    assert result["partial_match_count"] == 2
    assert [item["key"] for item in result["results"]] == [
        "opencompass:agent-workbench",
        "llm-stats:agent-workbench-extended",
    ]
    assert all(item["match"]["matched_tokens"] == ["agent"] for item in result["results"])
    assert all(
        item["match"]["missing_tokens"] == ["prediction", "protein"] for item in result["results"]
    )
    assert all(
        item["match"]["query_coverage"] == pytest.approx(1 / 3, abs=0.0001)
        for item in result["results"]
    )
    assert all(
        item["match"]["retrieval_score"] > 0 and 0 < item["match"]["idf_coverage"] < 1
        for item in result["results"]
    )
    assert all(
        set(item["match"]["score_components"]) == {"bm25f", "name_bonus", "phrase_bonus"}
        for item in result["results"]
    )


def test_multi_word_query_drops_description_only_single_token_matches(tmp_path: Path) -> None:
    # Issue #432: "protein structure prediction" returned a page of records
    # matching one generic word ("prediction") in description only, ranked as
    # confident matches while the rarer words matched nothing. A lone
    # description-only token no longer qualifies for a multi-word query; a
    # token in a name, category or other field still does.
    service = QueryService(_catalog(tmp_path))

    result = service.search("scientific protein prediction", scope="catalog", limit=10)

    # "scientific" appears only in Science Discovery Suite's description.
    assert result["search_status"] == "no_lexical_candidates"
    assert result["candidate_count"] == 0
    assert result["total_matches"] == 0
    assert result["results"] == []
    assert result["decision"] == "no_confident_match"
    # Codex P2: the old reason ("no record matched any query token") was
    # false here — one record did share "scientific", and the #432 floor
    # hid it. The reason now says the policy hid weak hits, and the count
    # lets a caller tell that apart from true zero overlap.
    assert result["decision_reason"] == (
        "no candidate passed the matching policy; 1 record shared a query "
        "token but only a single token in description"
    )
    assert result["weak_filtered_count"] == 1

    # True zero overlap keeps the old reason and a zero count.
    empty = service.search("zzzzqqqq xxxxwwww", scope="catalog", limit=10)
    assert empty["search_status"] == "no_lexical_candidates"
    assert empty["decision"] == "no_confident_match"
    assert empty["decision_reason"] == "no record matched any query token"
    assert empty["weak_filtered_count"] == 0


def test_filter_excluded_matches_are_not_reported_as_no_match(tmp_path: Path) -> None:
    # Codex P2: an active filter skipped records before overlap was tracked,
    # so a benchmark-name query with has_repo=false fell through to "no
    # record matched any query token" even though the named record exists
    # outside the filter. The reason now says the filter hid the match, and
    # the count lets a caller tell that apart from true zero overlap.
    service = QueryService(_catalog(tmp_path))

    filtered = service.search("science discovery", scope="catalog", limit=10, has_repo=False)
    assert filtered["search_status"] == "no_lexical_candidates"
    assert filtered["decision"] == "no_confident_match"
    assert filtered["decision_reason"] == (
        "no candidate passed the matching policy; 1 record shared a query "
        "token but was excluded by the active filters"
    )
    assert filtered["weak_filtered_count"] == 0
    assert filtered["filter_excluded_match_count"] == 1

    # A filter-excluded sharer and a policy-dropped weak hit are reported
    # together, not one hiding the other: "evaluation scientific
    # prediction" with modality=multimodal leaves Science Discovery Suite
    # sharing only "scientific" in description (weak hit) while Agent
    # Workbench shares "evaluation" but is filtered out as text modality.
    combined = service.search(
        "evaluation scientific prediction", scope="catalog", limit=10, modality="multimodal"
    )
    assert combined["search_status"] == "no_lexical_candidates"
    assert combined["decision_reason"] == (
        "no candidate passed the matching policy; 1 record shared a query "
        "token but only a single token in description; 1 record shared a "
        "query token but was excluded by the active filters"
    )
    assert combined["weak_filtered_count"] == 1
    assert combined["filter_excluded_match_count"] == 1

    # True zero overlap under a filter keeps the old reason and zero counts.
    empty = service.search("zzzzqqqq xxxxwwww", scope="catalog", limit=10, has_repo=False)
    assert empty["search_status"] == "no_lexical_candidates"
    assert empty["decision_reason"] == "no record matched any query token"
    assert empty["weak_filtered_count"] == 0
    assert empty["filter_excluded_match_count"] == 0


def test_search_decision_marks_full_and_partial_coverage(tmp_path: Path) -> None:
    # Issue #432: the JSON contract carried a rank and prose but no signal a
    # caller could threshold on. `decision` states whether any record covered
    # every query token; the raw BM25 score is deliberately not called
    # confidence, since it is not comparable across queries.
    service = QueryService(_catalog(tmp_path))

    full = service.search("agent workbench", scope="catalog", limit=10)
    assert full["search_status"] == "full_matches_found"
    assert full["decision"] == "matches"
    assert full["decision_reason"] == "at least one record matched every query token"
    assert full["matching_policy"]["name"] == "lexical_candidates_v2"

    partial = service.search("protein agent prediction", scope="catalog", limit=10)
    assert partial["search_status"] == "partial_candidates_only"
    assert partial["decision"] == "no_confident_match"
    assert partial["decision_reason"] == (
        "no record matched every query token; partial candidates share only some query tokens"
    )
    # Name-field partials survive the floor: both records match "agent" in
    # their name, so the agent still gets candidates to inspect.
    assert partial["candidate_count"] == 2


def test_exact_name_and_phrase_are_controlled_boosts(tmp_path: Path) -> None:
    # Regression: hard-coded giant bonuses hid BM25 relevance and double-counted
    # a name phrase, making the score impossible to reason about or tune.
    service = QueryService(_catalog(tmp_path))

    exact = service.search("agent workbench", scope="catalog", limit=1)["results"][0]
    phrase = service.search("scientific discovery", scope="catalog", limit=1)["results"][0]

    assert exact["match"]["score_components"]["name_bonus"] > 0
    assert exact["match"]["score_components"]["phrase_bonus"] == 0
    assert phrase["key"] == "opencompass:science-discovery"
    assert phrase["match"]["score_components"]["phrase_bonus"] > 0


def test_full_coverage_is_a_soft_ranking_signal_not_an_eligibility_gate(tmp_path: Path) -> None:
    # Regression: deleting partial rows made retrieval look precise while hiding
    # candidates the consuming agent needed to compare with a full-coverage row.
    service = QueryService(_catalog(tmp_path))

    result = service.search("agent coding", scope="catalog", limit=10)

    assert result["total_matches"] == 2
    assert [item["key"] for item in result["results"]] == [
        "opencompass:agent-workbench",
        "llm-stats:agent-workbench-extended",
    ]
    assert [item["match"]["query_coverage"] for item in result["results"]] == [1.0, 0.5]
    assert [item["match"]["missing_tokens"] for item in result["results"]] == [[], ["coding"]]


def test_name_matching_does_not_cross_token_boundaries(tmp_path: Path) -> None:
    # `ntwo` exists only after concatenating "agent" + "workbench". The old
    # folded substring matcher treated that accidental character sequence as a
    # name hit and even returned an empty matched_tokens explanation.
    result = QueryService(_catalog(tmp_path)).search("ntwo", scope="catalog")

    assert result["search_status"] == "no_lexical_candidates"
    assert result["candidate_count"] == 0
    assert result["total_matches"] == 0
    assert result["full_match_count"] == 0
    assert result["partial_match_count"] == 0
    assert result["results"] == []


def test_search_filters_before_ranking(tmp_path: Path) -> None:
    # Regression: filtering a truncated result list can hide eligible matches.
    service = QueryService(_catalog(tmp_path))

    result = service.search(
        "agent",
        scope="catalog",
        limit=10,
        has_repo=True,
        has_dataset=True,
        openness="open",
        modality="text",
    )

    assert [item["key"] for item in result["results"]] == ["opencompass:agent-workbench"]
    assert result["filters"] == {
        "has_dataset": True,
        "has_repo": True,
        "modality": "text",
        "openness": "open",
    }

    without_repositories = service.search("agent", has_repo=False)
    assert [item["key"] for item in without_repositories["results"]] == [
        "llm-stats:agent-workbench-extended"
    ]


def test_all_scope_keeps_catalog_and_radar_identity_separate(tmp_path: Path) -> None:
    # Regression: same-looking names from two evidence layers are not proven identities.
    service = QueryService(_catalog(tmp_path))

    result = service.search("coding", scope="all", limit=10)

    assert {item["kind"] for item in result["results"]} == {"catalog", "radar"}
    assert len({item["key"] for item in result["results"]}) == len(result["results"])


def test_show_accepts_key_or_slug_and_rejects_missing_shards(tmp_path: Path) -> None:
    # Regression: an index hit without its detail shard must not look complete.
    paths = _catalog(tmp_path)
    service = QueryService(paths)

    by_key = service.show("opencompass:agent-workbench")
    by_slug = service.show("opencompass-agent-workbench")

    assert by_key == by_slug
    assert by_key["benchmark"]["record"]["key"] == "opencompass:agent-workbench"

    (paths.shards / "opencompass-agent-workbench.json").unlink()
    with pytest.raises(QueryError, match="detail shard is missing"):
        service.show("opencompass:agent-workbench")


_INDEX_ONLY_FIELDS = {
    "score_count",
    "has_paper",
    "has_repo",
    "has_dataset",
    "has_size",
}


def _normalized_record(row: dict, indexed: dict | None = None) -> dict:
    """Give an index-shaped fixture row the shape normalize-catalog writes.

    Missing identity fields come from the record's index row: a key prefix
    (``model-reports``) is not the source name (``model_reports``).
    """
    record = {key: value for key, value in row.items() if key not in _INDEX_ONLY_FIELDS}
    for field in ("slug", "name", "source"):
        if field not in record and indexed and field in indexed:
            record[field] = indexed[field]
    record.setdefault("slug", str(record["key"]).replace(":", "-"))
    record.setdefault("name", record["slug"])
    record.setdefault("source", str(record["key"]).split(":", 1)[0].replace("-", "_"))
    if isinstance(record.get("publisher"), str):
        record["publisher"] = {"name": record["publisher"]}
    if isinstance(record.get("openness"), str):
        record["openness"] = {"status": record["openness"]}
    return record


def _source_records(tmp_path: Path, rows: list[dict], *, rebuild_index: bool = True) -> None:
    """Write normalized source records and rebuild their index rows from them.

    Trace rebuilds each index row from the normalized artifacts, as
    normalize-catalog does, so a fixture index row must be what production
    would build from the fixture records rather than a hand-written stand-in.
    """
    from benchmark_radar.catalog import build_benchmark_index
    from benchmark_radar.catalog_evidence import attach_evidence

    catalog_dir = tmp_path / "data" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    index_path = tmp_path / "site" / "data" / "benchmark-index.json"
    index = (
        json.loads(index_path.read_text(encoding="utf-8"))
        if index_path.exists()
        else {"benchmarks": []}
    )
    indexed = {row["key"]: row for row in index["benchmarks"]}
    records = attach_evidence(
        [_normalized_record(row, indexed.get(row["key"])) for row in rows], [], []
    )
    path = catalog_dir / "opencompass_source_records.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    if rebuild_index:
        _sync_index(tmp_path, build_benchmark_index(records), records)


def _write_model_reports_catalog(tmp_path: Path, *, sync_index: bool = True) -> None:
    """Write model_reports artifacts the way normalize-catalog does.

    ``sync_index=False`` stops after write_catalog, before the index is
    rebuilt, leaving the index as the previous run wrote it.
    """
    from benchmark_radar.benchmark_scores import load_scores
    from benchmark_radar.catalog import build_benchmark_index, write_catalog
    from benchmark_radar.catalog_evidence import attach_evidence
    from benchmark_radar.catalog_identity import IdentityIndex
    from benchmark_radar.catalog_reports import normalize_reports
    from benchmark_radar.catalog_shards import build_shard
    from benchmark_radar.model_cards import load_registry

    scores_path = tmp_path / "data" / "benchmark_scores.yml"
    result = normalize_reports(
        load_registry(tmp_path / "data" / "model_cards.yml"),
        load_scores(scores_path)
        if scores_path.exists()
        else {"schema_version": 1, "benchmarks": [], "results": []},
    )
    result["source_records"] = attach_evidence(
        result["source_records"], result["score_series"], result["score_observations"]
    )
    write_catalog(result, tmp_path / "data" / "catalog")
    if not sync_index:
        return
    series_by_key = {row["key"]: row for row in result["score_series"]}
    _sync_index(
        tmp_path,
        build_benchmark_index(
            result["source_records"], series_by_key, result["score_observations"]
        ),
        result["source_records"],
        append=True,
    )
    # Shards carry the score payload build_shard writes for each record.
    observations_by_key: dict[str, list[dict]] = {}
    for row in result["score_observations"]:
        observations_by_key.setdefault(row["key"], []).append(row)
    shard_dir = tmp_path / "site" / "data" / "benchmarks"
    for record in result["source_records"]:
        shard_path = shard_dir / f"{record['slug']}.json"
        if not shard_path.exists():
            continue
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        shard["scores_by_source"] = json.loads(
            json.dumps(
                build_shard(
                    record,
                    identity=IdentityIndex(),
                    series_by_key=series_by_key,
                    observations_by_key=observations_by_key,
                )["scores_by_source"]
            )
        )
        shard_path.write_text(json.dumps(shard), encoding="utf-8")


def _sync_index(
    tmp_path: Path,
    rows: list[dict],
    records: list[dict],
    *,
    append: bool = False,
) -> None:
    """Replace fixture index rows with built rows, and shard records with the
    full normalized records build_shard writes (the index is a projection)."""
    index_path = tmp_path / "site" / "data" / "benchmark-index.json"
    if not index_path.exists():
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    rebuilt = {row["key"]: row for row in rows}
    full = {record["key"]: json.loads(json.dumps(record)) for record in records}
    if append:
        known = {row["key"] for row in index["benchmarks"]}
        for row in rows:
            if row["key"] in known:
                continue
            index["benchmarks"].append(row)
            index["count"] = len(index["benchmarks"])
            (index_path.parent / "benchmarks" / f"{row['slug']}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record": full.get(row["key"], row),
                        "siblings": [],
                        "scores_by_source": {},
                    }
                ),
                encoding="utf-8",
            )
    for position, row in enumerate(index["benchmarks"]):
        if row["key"] not in rebuilt:
            continue
        index["benchmarks"][position] = rebuilt[row["key"]]
        shard_path = index_path.parent / "benchmarks" / f"{row['slug']}.json"
        if shard_path.exists():
            shard = json.loads(shard_path.read_text(encoding="utf-8"))
            # A shard that already names another record is a fixture for
            # that mismatch; leave it as written.
            if isinstance(shard.get("record"), dict) and shard["record"].get("key") == row["key"]:
                shard["record"] = full.get(row["key"]) or {
                    **shard["record"],
                    **rebuilt[row["key"]],
                }
                # Shards are named by slug, so follow a slug the build changed.
                shard_path.unlink()
                shard_path = shard_path.with_name(f"{rebuilt[row['key']]['slug']}.json")
                shard_path.write_text(json.dumps(shard), encoding="utf-8")
    index_path.write_text(json.dumps(index), encoding="utf-8")


def _identity_rules(
    tmp_path: Path,
    *,
    equivalent: list[dict] | None = None,
    variants: list[dict] | None = None,
) -> None:
    catalog_dir = tmp_path / "data" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "identity.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "equivalent": [
                    {"group_id": f"test-{i}", "anchors": ["paper", "repo"], **group}
                    for i, group in enumerate(equivalent or [])
                ],
                "variants": variants or [],
            }
        ),
        encoding="utf-8",
    )


def _snapshot_input(tmp_path: Path, rows: list[dict]) -> None:
    snapshot_dir = tmp_path / "data" / "leaderboard_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    csv_path = snapshot_dir / "opencompass_hub_catalog_2026-08-17.csv"
    # The production loader requires the declared name column in the header.
    fieldnames = sorted({field for row in rows for field in row} | {"name"})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    (tmp_path / "data" / "leaderboard_snapshots.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "snapshots": [
                    {
                        "id": "opencompass_hub_2026-08-17",
                        "source": "OpenCompass Hub",
                        "source_url": "https://hub.opencompass.org.cn/home",
                        "crawled_at": "2026-08-17T18:57:37Z",
                        "benchmark_file": (
                            "leaderboard_snapshots/opencompass_hub_catalog_2026-08-17.csv"
                        ),
                        "benchmark_count": len(rows),
                        "score_series_policy": "preserve_empty",
                        "benchmark_columns": {
                            "benchmark_id": "benchmark_id",
                            "benchmark_name": "name",
                        },
                        "columns": {"benchmark_id": "benchmark_id", "benchmark_name": "name"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    round2 = snapshot_dir / "opencompass_round2/opencompass_round2.jsonl"
    round2.parent.mkdir()
    round2.write_text(
        "".join(
            json.dumps(
                {"benchmark_id": row["benchmark_id"], "name": row.get("name", row["benchmark_id"])}
            )
            + "\n"
            for row in rows
        )
    )


def _model_cards_yaml(benchmark: dict) -> str:
    """A minimal model card registry that passes the production loader."""
    return yaml.safe_dump(
        {
            "schema_version": 1,
            "benchmarks": [{"domain": "agents", "caveat": "Fixture benchmark.", **benchmark}],
            "model_cards": [
                {
                    "id": "example_card",
                    "organization": "Example Lab",
                    "model": "Example-1",
                    "url": "https://example.com/card",
                    "benchmarks": [benchmark["id"]],
                }
            ],
        }
    )


def _score_archive(tmp_path: Path, benchmark_id: str) -> None:
    """A valid benchmark_scores.yml citing the _model_cards_yaml card.

    normalize-catalog refuses to run without the score archive, and trace
    reports its absence as a missing input.
    """
    (tmp_path / "data" / "benchmark_scores.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": [
                    {
                        "benchmark_id": benchmark_id,
                        "metric": "accuracy",
                        "direction": "higher_is_better",
                        "unit": "percent",
                    }
                ],
                "results": [
                    {
                        "benchmark_id": benchmark_id,
                        "instrument": "fixture_v1",
                        "protocol": "standard",
                        "model": "Example-1",
                        "organization": "Example Lab",
                        "source_id": "example_card",
                        "reported_at": "2026-01-01",
                        "read_from": "html_text",
                        "value": 50.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _trace_stages(payload: dict) -> dict[str, dict]:
    return {stage["stage"]: stage for stage in payload["stages"]}


def _claire_catalog_record() -> dict:
    return {
        "slug": "claire-agent-workbench",
        "key": "claire-radar:agent-workbench",
        "name": "Agent Workbench",
        "source": "claire_radar",
        "publisher": None,
        "released": None,
        "openness": "unknown",
        "modality": "text",
        "description": "Imported source record for the same reviewed benchmark identity.",
        "categories": ["agent", "coding"],
        "languages": [],
        "score_count": 0,
        "has_paper": True,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }


def _add_claire_record(paths: QueryPaths, tmp_path: Path, *, siblings: list[dict]) -> dict:
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    related = _claire_catalog_record()
    index["benchmarks"].append(related)
    index["count"] += 1
    paths.index.write_text(json.dumps(index), encoding="utf-8")
    (paths.shards / f"{related['slug']}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": related,
                "siblings": siblings,
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )
    _source_records(
        tmp_path,
        [
            {"key": "unrelated:record", "slug": "unrelated-record"},
            {**related, "source_benchmark_id": "agent-workbench"},
            # identity.yml is validated against the current source records,
            # so the peer the rules name must exist there as it does in a
            # real checkout.
            {
                **next(
                    row
                    for row in index["benchmarks"]
                    if row["key"] == "opencompass:agent-workbench"
                ),
                "source_benchmark_id": "agent-workbench",
            },
        ],
    )
    return related


def test_trace_joined_record_shows_declared_identity_siblings(tmp_path: Path) -> None:
    # Issue #1233: a record joined through reviewed identity rules must show
    # the sibling evidence at the identity stage, not silently merge it.
    paths = _catalog(tmp_path)
    _add_claire_record(
        paths,
        tmp_path,
        siblings=[
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "name": "Agent Workbench",
                "source": "opencompass_hub",
                "relation": "equivalent",
            }
        ],
    )
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": ["claire-radar:agent-workbench", "opencompass:agent-workbench"],
                "note": "Same benchmark imported from two sources.",
            }
        ],
    )

    payload = QueryService(paths).trace("claire-radar:agent-workbench")

    assert payload["status"] == "present"
    assert payload["first_change"] is None
    stages = _trace_stages(payload)
    assert list(stages) == ["source", "normalization", "identity", "enrichment", "outputs"]
    # The first jsonl row is unrelated; the source stage must not claim it.
    assert stages["source"]["output"]["key"] == "claire-radar:agent-workbench"
    assert stages["identity"]["status"] == "present"
    assert stages["identity"]["output"]["siblings"][0]["key"] == "opencompass:agent-workbench"


def test_trace_flags_sibling_missing_from_current_identity_rules(tmp_path: Path) -> None:
    # A shard sibling the current identity.yml no longer declares means the
    # shard was built from stale rules; the identity stage must say so.
    paths = _catalog(tmp_path)
    _add_claire_record(
        paths,
        tmp_path,
        siblings=[
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "name": "Agent Workbench",
                "source": "opencompass_hub",
                "relation": "equivalent",
            }
        ],
    )
    _identity_rules(tmp_path)

    payload = QueryService(paths).trace("claire-radar:agent-workbench")

    assert payload["first_change"] == "identity"
    stages = _trace_stages(payload)
    assert stages["identity"]["status"] == "changed"
    assert stages["identity"]["changes"][0]["field"] == "siblings.opencompass:agent-workbench"


def test_trace_unjoined_record_walks_every_stage(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _source_records(
        tmp_path,
        [
            {"key": "other:record", "slug": "other-record"},
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source_benchmark_id": "agent-workbench",
            },
        ],
    )

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    assert payload["status"] == "present"
    assert payload["first_change"] is None
    stages = _trace_stages(payload)
    assert all(stage["status"] == "present" for stage in stages.values())
    assert stages["identity"]["output"]["siblings"] == []
    outputs = stages["outputs"]["output"]
    assert outputs["benchmark-index.json"]["contains"] is True
    assert outputs["shard"]["record_key"] == "opencompass:agent-workbench"
    assert outputs["shard"]["matches_target"] is True


def test_trace_diffs_the_raw_snapshot_row_against_normalization(tmp_path: Path) -> None:
    # The source stage must show the committed crawl row, and normalization
    # must diff it against the catalog row instead of comparing a record to
    # itself.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _snapshot_input(
        tmp_path,
        [
            {"benchmark_id": "other-benchmark", "name": "Other Benchmark"},
            {
                "benchmark_id": "agent-workbench",
                "name": "Agent Workbench (raw crawl)",
                "description": "Raw description from the crawl.",
            },
        ],
    )
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source_benchmark_id": "agent-workbench",
                "name": "Agent Workbench",
                "description": "Normalized description.",
            }
        ],
    )

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    stages = _trace_stages(payload)
    assert stages["source"]["output"]["name"] == "Agent Workbench (raw crawl)"
    assert stages["source"]["path"].endswith("opencompass_hub_catalog_2026-08-17.csv")
    assert stages["normalization"]["status"] == "changed"
    assert payload["first_change"] == "normalization"
    changed_fields = {change["field"] for change in stages["normalization"]["changes"]}
    assert "name" in changed_fields
    assert "description" in changed_fields


def test_trace_reads_the_model_reports_source_row(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    catalog_dir = tmp_path / "data" / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "model_cards.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": [
                    {
                        "id": "agent-workbench",
                        "name": "Agent Workbench (registry)",
                        "domain": "agents",
                        "caveat": "Fixture benchmark.",
                        "url": "https://example.com/aw",
                    }
                ],
                "model_cards": [
                    {
                        "id": "example_card",
                        "organization": "Example Lab",
                        "model": "Example-1",
                        "document_type": "system_card",
                        "url": "https://example.com/card",
                        "benchmarks": ["agent-workbench"],
                    }
                ],
                "source_documents": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "benchmark_scores.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": [
                    {
                        "benchmark_id": "agent-workbench",
                        "metric": "accuracy",
                        "direction": "higher_is_better",
                        "unit": "percent",
                    }
                ],
                "results": [
                    {
                        "benchmark_id": "agent-workbench",
                        "instrument": "aw_v1",
                        "protocol": "standard",
                        "model": "Example-1",
                        "organization": "Example Lab",
                        "source_id": "example_card",
                        "reported_at": "2026-01-01",
                        "value": 91.5,
                        "read_from": "html_text",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    record = {
        "slug": "model-reports-agent-workbench",
        "key": "model-reports:agent-workbench",
        "name": "Agent Workbench",
        "source": "model_reports",
        "publisher": None,
        "released": None,
        "openness": "unknown",
        "modality": "text",
        "description": "",
        "categories": [],
        "languages": [],
        "score_count": 0,
        "has_paper": False,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }
    index["benchmarks"].append(record)
    index["count"] += 1
    paths.index.write_text(json.dumps(index), encoding="utf-8")
    (paths.shards / f"{record['slug']}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": record,
                "siblings": [],
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )
    _source_records(
        tmp_path,
        [
            {
                "key": "model-reports:agent-workbench",
                "slug": "model-reports-agent-workbench",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )

    payload = QueryService(paths).trace("model-reports:agent-workbench")

    stages = _trace_stages(payload)
    source = stages["source"]["output"]
    assert source["name"] == "Agent Workbench (registry)"
    assert stages["source"]["path"].endswith("model_cards.yml")
    # normalize_reports also consumes the score archive and citing documents,
    # so the source stage must show them, not just the benchmarks: row.
    assert source["metric_identity"]["metric"] == "accuracy"
    assert source["score_rows"][0]["value"] == 91.5
    assert source["adopting_documents"][0]["id"] == "example_card"
    assert source["sources"]["score_archive"].endswith("benchmark_scores.yml")


def test_trace_rejects_a_shard_for_a_different_record(tmp_path: Path) -> None:
    # A stale or misnamed shard must not be reported as this record's
    # enrichment; the embedded record key has to match the catalog key.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    shard_path = paths.shards / "opencompass-agent-workbench.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["record"]["key"] = "opencompass:other-benchmark"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    assert payload["first_change"] == "enrichment"
    stages = _trace_stages(payload)
    assert stages["enrichment"]["status"] == "changed"
    assert stages["enrichment"]["changes"][0]["field"] == "record.key"
    assert stages["outputs"]["output"]["shard"]["matches_target"] is False


def test_trace_in_an_installed_bundle_reports_pipeline_inputs_absent(tmp_path: Path) -> None:
    # Installed clients keep the index outside ``site/data``; the catalog
    # pipeline inputs are not shipped, so those stages must say absent rather
    # than probe a directory that does not exist.
    bundle = tmp_path / "bundle"
    index_path = bundle / "benchmark-index.json"
    shard_dir = bundle / "benchmarks"
    snapshot_dir = tmp_path / "data" / "snapshots"
    shard_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    record = {
        "slug": "opencompass-agent-workbench",
        "key": "opencompass:agent-workbench",
        "name": "Agent Workbench",
        "source": "opencompass_hub",
        "publisher": None,
        "released": None,
        "openness": "unknown",
        "modality": "text",
        "description": "",
        "categories": [],
        "languages": [],
        "score_count": 0,
        "has_paper": False,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }
    index_path.write_text(
        json.dumps({"schema_version": 1, "count": 1, "benchmarks": [record]}),
        encoding="utf-8",
    )
    (shard_dir / f"{record['slug']}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": record,
                "siblings": [],
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )
    generated_at = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
    write_snapshot(
        RadarRun(
            generated_at=generated_at,
            since=generated_at - timedelta(hours=48),
            items=[],
            health=[
                SourceHealth(source=source, ok=True, item_count=0, method="API")
                for source in ("arxiv", "github", "huggingface")
            ],
        ),
        snapshot_dir,
    )
    paths = QueryPaths(index=index_path, shards=shard_dir, snapshots=snapshot_dir)

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    stages = _trace_stages(payload)
    assert stages["source"]["status"] == "absent"
    assert stages["normalization"]["status"] == "absent"
    assert stages["identity"]["status"] == "absent"
    assert stages["enrichment"]["status"] == "present"
    assert stages["outputs"]["status"] == "present"
    assert payload["first_change"] == "source"


def test_trace_names_source_when_the_raw_row_is_gone(tmp_path: Path) -> None:
    # The raw snapshot row was deleted but the normalized catalog row
    # survives; promoting the normalized row to "source" would hide the drop.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _snapshot_input(tmp_path, [{"benchmark_id": "other-benchmark", "name": "Other"}])
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source": "opencompass_hub",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    assert payload["first_change"] == "source"
    stages = _trace_stages(payload)
    assert stages["source"]["status"] == "absent"
    assert "no raw input row" in stages["source"]["error"]
    assert stages["normalization"]["status"] == "present"
    assert "raw input row absent" in stages["normalization"]["note"]


def test_trace_finds_the_raw_row_when_the_catalog_dropped_the_record(tmp_path: Path) -> None:
    # Inverse drop: the record never reached the catalog index, but the raw
    # snapshot row and normalized row still exist, so the first change is
    # identity rather than source.
    paths = _catalog(tmp_path)
    _snapshot_input(
        tmp_path,
        [
            {
                "benchmark_id": "dropped-benchmark",
                "name": "Agent Workbench (raw crawl)",
            }
        ],
    )
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:dropped-benchmark",
                "slug": "opencompass-dropped-benchmark",
                "source": "opencompass_hub",
                "source_benchmark_id": "dropped-benchmark",
                "name": "Agent Workbench (raw crawl)",
            }
        ],
    )

    payload = QueryService(paths).trace("opencompass:dropped-benchmark")

    assert payload["status"] == "missing"
    assert payload["first_change"] == "identity"
    stages = _trace_stages(payload)
    assert stages["source"]["status"] == "present"
    assert stages["source"]["output"]["name"] == "Agent Workbench (raw crawl)"
    assert stages["normalization"]["status"] == "present"
    assert stages["identity"]["status"] == "absent"


def test_trace_reports_a_corrupt_leaderboard_export(tmp_path: Path) -> None:
    # A model_reports record whose leaderboard.json is malformed must surface
    # the corruption at the outputs stage, not silently omit the export.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    (tmp_path / "data" / "model_cards.yml").write_text(
        _model_cards_yaml({"id": "agent-workbench", "name": "Agent Workbench (registry)"}),
        encoding="utf-8",
    )
    _score_archive(tmp_path, "agent-workbench")
    data_dir = tmp_path / "site" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "leaderboard.json").write_text("{not json", encoding="utf-8")
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    record = {
        "slug": "model-reports-agent-workbench",
        "key": "model-reports:agent-workbench",
        "name": "Agent Workbench",
        "source": "model_reports",
        "publisher": None,
        "released": None,
        "openness": "unknown",
        "modality": "text",
        "description": "",
        "categories": [],
        "languages": [],
        "score_count": 0,
        "has_paper": False,
        "has_repo": False,
        "has_dataset": False,
        "has_size": False,
    }
    index["benchmarks"].append(record)
    index["count"] += 1
    paths.index.write_text(json.dumps(index), encoding="utf-8")
    (paths.shards / f"{record['slug']}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": record,
                "siblings": [],
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )
    _write_model_reports_catalog(tmp_path)

    payload = QueryService(paths).trace("model-reports:agent-workbench")

    assert payload["first_change"] == "outputs"
    stages = _trace_stages(payload)
    assert stages["outputs"]["status"] == "changed"
    export = stages["outputs"]["output"]["export:leaderboard.json"]
    assert export["contains"] is None
    assert export["error"]


def test_trace_flags_identity_peer_missing_from_shard(tmp_path: Path) -> None:
    # A pair added to identity.yml before shards were rebuilt leaves the
    # shard's sibling list incomplete; the identity stage must catch the
    # missing join in the other direction too.
    paths = _catalog(tmp_path)
    _add_claire_record(paths, tmp_path, siblings=[])
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": ["claire-radar:agent-workbench", "opencompass:agent-workbench"],
            }
        ],
    )

    payload = QueryService(paths).trace("claire-radar:agent-workbench")

    assert payload["first_change"] == "identity"
    stages = _trace_stages(payload)
    assert stages["identity"]["status"] == "changed"
    assert stages["identity"]["changes"][0]["field"] == "identity.opencompass:agent-workbench"


def test_trace_diffs_a_same_key_but_stale_shard_record(tmp_path: Path) -> None:
    # A shard rewritten for the same key can still carry stale fields; the
    # enrichment stage diffs the embedded record against the catalog row.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )
    shard_path = paths.shards / "opencompass-agent-workbench.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["record"]["name"] = "Agent Workbench (stale)"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    assert payload["first_change"] == "enrichment"
    stages = _trace_stages(payload)
    assert stages["enrichment"]["status"] == "changed"
    assert any(change["field"] == "name" for change in stages["enrichment"]["changes"])


def test_trace_reports_a_non_object_shard_record(tmp_path: Path) -> None:
    # Corrupt shard JSON must surface as a changed enrichment stage, not an
    # AttributeError traceback.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    shard_path = paths.shards / "opencompass-agent-workbench.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["record"] = "corrupt"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "slug": "opencompass-agent-workbench",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )

    payload = QueryService(paths).trace("opencompass-agent-workbench")

    assert payload["first_change"] == "enrichment"
    stages = _trace_stages(payload)
    assert stages["enrichment"]["status"] == "changed"
    assert stages["enrichment"]["changes"][0]["field"] == "record"


def test_trace_names_the_stage_that_drops_a_record(tmp_path: Path) -> None:
    # A catalog record whose detail shard is absent must name enrichment as the
    # first missing stage instead of reporting a complete trace.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _source_records(
        tmp_path,
        [{"key": "opencompass:science-discovery", "slug": "opencompass-science-discovery"}],
    )
    (paths.shards / "opencompass-science-discovery.json").unlink()

    payload = QueryService(paths).trace("opencompass:science-discovery")

    assert payload["status"] == "present"
    assert payload["first_change"] == "enrichment"
    stages = _trace_stages(payload)
    assert stages["enrichment"]["status"] == "absent"
    assert "artifact is missing locally" in stages["enrichment"]["error"]


def test_trace_missing_record_reports_every_stage_absent(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)

    payload = QueryService(paths).trace("no-such-benchmark")

    assert payload["status"] == "missing"
    assert payload["first_change"] == "source"
    assert all(stage["status"] == "absent" for stage in payload["stages"])


def test_cli_trace_prints_stages_and_json_contract(tmp_path: Path, capsys) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    common = [
        "--index",
        str(paths.index),
        "--shards",
        str(paths.shards),
        "--snapshots",
        str(paths.snapshots),
    ]

    exit_code = run_query_cli(["trace", "opencompass-agent-workbench", *common])
    text_out = capsys.readouterr().out
    assert exit_code == 0
    assert "Trace: opencompass-agent-workbench (present)" in text_out
    assert "identity: present" in text_out

    exit_code = run_query_cli(["trace", "opencompass-agent-workbench", "--json", *common])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["identifier"] == "opencompass-agent-workbench"
    assert payload["retrieval_mode"] == "direct_trace"
    assert _trace_stages(payload)["outputs"]["status"] == "present"


def test_research_payloads_carry_required_citation_contract(tmp_path: Path) -> None:
    service = QueryService(_catalog(tmp_path))

    payloads = [
        service.search("agent workbench", scope="catalog"),
        service.show("opencompass-agent-workbench"),
        service.recent(limit=1),
    ]

    for payload in payloads:
        assert payload["required_citations"] == [
            {
                "id": "benchmark-radar",
                "key": "wu2026benchmarkradarlivingdatabase",
                "reason": (
                    "You used Benchmark Radar for this material. "
                    "Please cite it; we can add it for you."
                ),
                "bibtex": bibtex_citation(),
            }
        ]
    assert "required_citations" not in service.status()


def test_recent_and_status_report_snapshot_health(tmp_path: Path) -> None:
    # Regression: freshness without required-source coverage overstates local health.
    service = QueryService(_catalog(tmp_path))

    recent = service.recent(limit=5)
    status = service.status()

    assert recent["date"] == "2026-08-29"
    assert recent["retrieval_mode"] == "latest_snapshot"
    assert recent["results"][0]["source_id"] == "example/new-agent-bench"
    assert status["catalog"]["count"] == 3
    assert status["retrieval_mode"] == "health_check"
    assert status["data"] == {"source": "local", "citation": citation_block()}
    assert status["catalog"]["complete"] is True
    assert status["catalog"]["shard_count"] == 3
    assert status["catalog"]["validated_shard_count"] == 3
    assert status["radar"]["snapshot_count"] == 1
    assert status["radar"]["latest_date"] == "2026-08-29"
    assert status["radar"]["required_coverage_complete"] is True


def test_radar_results_carry_derived_science_domains(tmp_path: Path) -> None:
    # Issue #511 review BLOCKER: stored snapshots predate the field, so the
    # query surface must derive domains from record text -- a plain field
    # copy would return [] for every historical record and still pass a
    # "field exists" test. These assertions require the actual tag value.
    paths = _catalog(tmp_path)
    generated_at = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
    write_snapshot(
        RadarRun(
            generated_at=generated_at,
            since=generated_at - timedelta(hours=48),
            items=[
                RadarItem(
                    source="arXiv",
                    source_id="2608.17345",
                    title="BrainBench: Benchmarking Large Language Models for "
                    "Comprehensive EEG Understanding",
                    url="https://arxiv.org/abs/2608.17345",
                    published_at=generated_at - timedelta(hours=2),
                    summary="A real corpus title replayed by the shared derivation.",
                    categories=["benchmark", "evaluation"],
                )
            ],
            health=[
                SourceHealth(source=source, ok=True, item_count=1, method="API")
                for source in ("arxiv", "github", "huggingface")
            ],
        ),
        paths.snapshots,
    )
    service = QueryService(paths)

    recent = service.recent(limit=5)
    searched = service.search("brainbench", scope="radar", limit=5)

    assert recent["schema_version"] == 8
    assert recent["results"][0]["science_domains"] == ["neuroscience"]
    radar_hits = [record for record in searched["results"] if record["kind"] == "radar"]
    assert radar_hits and radar_hits[0]["science_domains"] == ["neuroscience"]


@pytest.mark.parametrize("repository_id", ["lab/suite", "lab/a-long-benchmark-suite-name", None])
def test_hub_kinds_survive_collection_snapshot_and_public_search(
    tmp_path: Path, monkeypatch, capsys, repository_id: str | None
) -> None:
    paths = _catalog(tmp_path)
    generated_at = datetime(2026, 8, 30, 8, tzinfo=UTC)

    def get_hub_rows(url, **_kwargs):
        kind = url.rsplit("/", 1)[-1]
        return [
            {
                "id": repository_id or f"lab/{kind}-suite",
                "createdAt": "2026-08-30T06:00:00Z",
                "lastModified": "2026-08-30T07:00:00Z",
                "downloads": 3,
                "likes": 2,
            }
        ]

    monkeypatch.setattr("benchmark_radar.sources.get_json", get_hub_rows)
    items = fetch_huggingface(
        {"kinds": ["datasets", "models", "spaces"], "searches": ["suite", "suite"]},
        generated_at - timedelta(days=1),
        10,
    )
    assert len(items) == 3
    items = deduplicate(items)
    assert len(items) == 3
    run = RadarRun(
        generated_at=generated_at,
        since=generated_at - timedelta(days=1),
        items=items,
        health=[SourceHealth(source="huggingface", ok=True, item_count=3, method="API")],
    )
    write_snapshot(run, paths.snapshots)
    write_snapshot(run, paths.snapshots)
    assert len(load_snapshots(paths.snapshots)[-1]["evidence_items"]) == 3

    initial = QueryService(paths).search("suite", scope="radar", limit=10)
    assert initial["total_matches"] == 3
    keys_by_url = {row["url"]: row["key"] for row in initial["results"]}
    assert len(set(keys_by_url.values())) == 3
    assert {row["source_id"] for row in initial["results"]} == {item.source_id for item in items}

    # A later observation of only the dataset replaces that kind, while its
    # same-named model and Space remain discoverable with stable public keys.
    dataset = deepcopy(next(item for item in items if "/datasets/" in item.url))
    dataset.summary = "A newer dataset observation."
    dataset.updated_at = generated_at + timedelta(days=1)
    write_snapshot(
        RadarRun(
            generated_at=generated_at + timedelta(days=1),
            since=generated_at,
            items=[dataset],
            health=[SourceHealth(source="huggingface", ok=True, item_count=1, method="API")],
        ),
        paths.snapshots,
    )
    searched = QueryService(paths).search("suite", scope="radar", limit=10)
    assert searched["total_matches"] == 3
    assert {row["url"]: row["key"] for row in searched["results"]} == keys_by_url
    for row in searched["results"]:
        if row["url"] == dataset.url:
            assert row["description"] == dataset.summary
            assert row["snapshot_date"] == "2026-08-31"
        else:
            assert row["snapshot_date"] == "2026-08-30"

    exit_code = run_query_cli(
        [
            "search",
            "suite",
            "--scope",
            "radar",
            "--limit",
            "10",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == searched


def test_status_exposes_incomplete_detail_shards(tmp_path: Path) -> None:
    # Regression: counting only the index used to hide absent detail artifacts.
    paths = _catalog(tmp_path)
    (paths.shards / "opencompass-agent-workbench.json").unlink()

    status = QueryService(paths).status()

    assert status["status"] == "degraded"
    assert status["catalog"]["complete"] is False
    assert status["catalog"]["missing_shards"] == ["opencompass-agent-workbench.json"]


def test_status_rejects_malformed_detail_shards(tmp_path: Path) -> None:
    # Regression: matching filenames alone let corrupt shard JSON pass serve preflight.
    paths = _catalog(tmp_path)
    (paths.shards / "opencompass-agent-workbench.json").write_text("{}", encoding="utf-8")

    with pytest.raises(QueryError, match="does not match catalog key"):
        QueryService(paths).status()


def test_cli_and_http_return_the_same_search_contract(tmp_path: Path, capsys) -> None:
    # Regression: separate serializers drift even when ranking happens to agree.
    paths = _catalog(tmp_path)
    service = QueryService(paths)
    exit_code = run_query_cli(
        [
            "search",
            "agent workbench",
            "--scope",
            "catalog",
            "--limit",
            "2",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    cli_payload = json.loads(capsys.readouterr().out)

    server = create_query_server(service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        query = urllib.parse.urlencode({"q": "agent workbench", "scope": "catalog", "limit": 2})
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/api/v1/search?{query}", timeout=5
        ) as response:
            http_payload = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert exit_code == 0
    assert cli_payload == http_payload


@pytest.mark.parametrize(
    ("scope", "query", "count", "name"),
    [
        ("catalog", "protein agent prediction", 2, "Agent Workbench"),
        ("radar", "agent workbench", 1, "New Agent Memory Benchmark"),
    ],
)
def test_cli_labels_partial_candidates_without_hiding_them(
    tmp_path: Path, capsys, scope: str, query: str, count: int, name: str
) -> None:
    # Regression: the terminal rendered weak one-token evidence as ordinary
    # matches, so an agent had no top-level signal that no full lexical match existed.
    paths = _catalog(tmp_path)
    if scope == "radar":
        assert QueryService(paths).search(query, scope="catalog")["full_match_count"] == 2

    exit_code = run_query_cli(
        [
            "search",
            query,
            "--scope",
            scope,
            "--limit",
            "2",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No record in the searched scope matched every query token" in output
    assert f"(scope={scope})" in output
    assert "partial candidates are not answers" in output
    assert f"Showing {count} of {count} partial lexical candidates" in output
    assert name in output


def test_cli_search_accepts_query_flag(tmp_path: Path, capsys) -> None:
    # Issue #421: the request shows the query as `--query "..."`. The flag
    # form must return the same contract as the positional form, including
    # the issue's `--scope` / `--limit` / `--json` shape.
    paths = _catalog(tmp_path)
    common = ["--scope", "catalog", "--limit", "10", "--json"]
    cases = [
        ["search", "agent workbench", *common],
        ["search", "--query", "agent workbench", *common],
        ["search", "agent workbench", "--query", "agent workbench", *common],
    ]
    payloads = []
    for arguments in cases:
        exit_code = run_query_cli(
            [
                *arguments,
                "--index",
                str(paths.index),
                "--shards",
                str(paths.shards),
                "--snapshots",
                str(paths.snapshots),
            ]
        )
        assert exit_code == 0
        payloads.append(json.loads(capsys.readouterr().out))
    assert payloads[0] == payloads[1] == payloads[2]
    assert payloads[0]["query"] == "agent workbench"


def test_cli_search_rejects_conflicting_or_missing_query(tmp_path: Path, capsys) -> None:
    # Giving both forms with different values is an error, not a silent pick;
    # giving neither is an error too. Both fail non-zero with the machine
    # error contract on stderr.
    paths = _catalog(tmp_path)
    base = [
        "--json",
        "--index",
        str(paths.index),
        "--shards",
        str(paths.shards),
        "--snapshots",
        str(paths.snapshots),
    ]
    for arguments in (
        ["search", "agent workbench", "--query", "science discovery", *base],
        ["search", *base],
    ):
        exit_code = run_query_cli(arguments)
        assert exit_code == 2
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_query"


def test_cli_search_validates_query_before_loading_uninitialized_data(
    tmp_path: Path, capsys
) -> None:
    for query_arguments in (["--query", "   "], ["!!!"]):
        exit_code = run_query_cli(
            ["search", *query_arguments, "--data-dir", str(tmp_path / "not-initialized"), "--json"]
        )

        assert exit_code == 2
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_query"


def test_cli_and_http_return_the_same_non_search_contracts(tmp_path: Path, capsys) -> None:
    # Regression: shared search alone did not prevent detail/status serializers drifting.
    paths = _catalog(tmp_path)
    service = QueryService(paths)
    server = create_query_server(service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cases = [
            (
                ["show", "opencompass-agent-workbench"],
                "/api/v1/benchmarks/opencompass-agent-workbench",
            ),
            (["recent", "--limit", "1"], "/api/v1/recent?limit=1"),
            (["status"], "/api/v1/status"),
            (
                ["trace", "opencompass-agent-workbench"],
                "/api/v1/trace/opencompass-agent-workbench",
            ),
        ]
        for arguments, route in cases:
            exit_code = run_query_cli(
                [
                    *arguments,
                    "--json",
                    "--index",
                    str(paths.index),
                    "--shards",
                    str(paths.shards),
                    "--snapshots",
                    str(paths.snapshots),
                ]
            )
            cli_payload = json.loads(capsys.readouterr().out)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}{route}", timeout=5
            ) as response:
                http_payload = json.load(response)
            assert exit_code == 0
            assert cli_payload == http_payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_healthz_identifies_local_health_check_contract(tmp_path: Path) -> None:
    # Regression: the lightweight health route omitted provenance and retrieval mode.
    server = create_query_server(QueryService(_catalog(tmp_path)), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/healthz", timeout=5
        ) as response:
            payload = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload == {
        "schema_version": 8,
        "retrieval_mode": "health_check",
        "data": {"source": "local", "citation": citation_block()},
        "status": "ok",
        "data_status": "ok",
    }


def test_cli_can_filter_for_absent_artifacts(tmp_path: Path, capsys) -> None:
    # Regression: one-way CLI flags could not express the HTTP false filters.
    paths = _catalog(tmp_path)

    exit_code = run_query_cli(
        [
            "search",
            "agent",
            "--no-has-repo",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["filters"] == {"has_repo": False}
    assert [item["key"] for item in payload["results"]] == ["llm-stats:agent-workbench-extended"]


def test_malformed_index_is_a_machine_readable_cli_error(tmp_path: Path, capsys) -> None:
    # Regression: malformed rows escaped as KeyError tracebacks instead of JSON errors.
    paths = _catalog(tmp_path)
    malformed = json.loads(paths.index.read_text(encoding="utf-8"))
    del malformed["benchmarks"][0]["slug"]
    paths.index.write_text(json.dumps(malformed), encoding="utf-8")

    exit_code = run_query_cli(
        [
            "search",
            "agent",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err)["error"] == {
        "code": "invalid_data",
        "message": "benchmark index record 0 slug must be a non-empty string",
    }


def test_http_errors_are_machine_readable(tmp_path: Path) -> None:
    # Regression: agent callers need a stable error envelope, not an HTML error page.
    service = QueryService(_catalog(tmp_path))
    server = create_query_server(service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as captured:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/v1/search", timeout=5
            )
        payload = json.loads(captured.value.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert captured.value.code == 400
    assert payload == {
        "schema_version": 8,
        "error": {"code": "invalid_request", "message": "q is required"},
    }


def test_cli_ends_human_output_with_citation_reminder(tmp_path: Path, capsys) -> None:
    # Issue #483: every query round closes by asking for a citation, with the
    # APA preview and the full-formats link.
    paths = _catalog(tmp_path)

    exit_code = run_query_cli(
        [
            "search",
            "agent workbench",
            "--scope",
            "catalog",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "please cite it" in output
    assert (
        "Wu, K., Zhang, W., Zhou, J., Han, P., Bao, Q., Shang, E., Wang, J., Wang, J., Xu, W., "
        "Lu, S., Li, Y., Mizrahi Celekli, R., Ravshanov, L., Bian, Y., Han, X., & Shi, L. (2026). "
        "Benchmark Radar: A living database and search engine for AI benchmarks and evaluation. "
        "arXiv:2609.11115. https://arxiv.org/abs/2609.11115"
    ) in output
    assert "https://benchmark-radar.org/#cite" in output


def test_search_payload_carries_the_paper_for_stdout_only_agents(tmp_path: Path) -> None:
    # Issue #483 follow-up: the reminder rides stderr, so an agent that reads
    # stdout alone (a `jq` pipe, a framework that captures one stream) never
    # sees the paper. The same citation has to travel in the payload, in a form
    # that goes straight into a related-work table.
    service = QueryService(_catalog(tmp_path))

    result = service.search("agent workbench", scope="catalog")

    citation = result["data"]["citation"]
    assert citation["arxiv_id"] == ARXIV_ID
    assert citation["url"] == ARXIV_URL
    assert citation["apa"] == apa_citation()
    assert citation["bibtex"] == bibtex_citation()
    assert citation["latex"] == latex_citation()
    assert citation["latex"] == "\\cite{wu2026benchmarkradarlivingdatabase}"


def test_cli_json_mode_keeps_stdout_parseable_and_cites_on_stderr(tmp_path: Path, capsys) -> None:
    # The JSON stream must stay byte-identical to the HTTP contract, so the
    # reminder rides stderr there instead of corrupting the payload.
    paths = _catalog(tmp_path)

    exit_code = run_query_cli(
        [
            "status",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert "please cite it" in captured.err
    assert "please cite it" not in captured.out


@pytest.mark.parametrize("field,value", [("name", "Updated name"), ("released", "2026-02-01")])
def test_trace_detects_stale_index(tmp_path: Path, field: str, value: str) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    record = json.loads(paths.index.read_text())["benchmarks"][0]
    # The index was built before this source change, so leave it stale.
    _source_records(tmp_path, [{**record, field: value}], rebuild_index=False)
    payload = QueryService(paths).trace(record["key"])
    assert payload["first_change"] == "identity"
    assert any(change["field"] == field for change in _trace_stages(payload)["identity"]["changes"])


@pytest.mark.parametrize("siblings", ["broken", {"key": "broken"}, [42], 0])
def test_trace_rejects_malformed_siblings(tmp_path: Path, siblings, capsys) -> None:
    paths = _catalog(tmp_path)
    shard_path = paths.shards / "opencompass-agent-workbench.json"
    shard = json.loads(shard_path.read_text())
    shard["siblings"] = siblings
    shard_path.write_text(json.dumps(shard))
    result = run_query_cli(
        [
            "trace",
            "opencompass-agent-workbench",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    captured = capsys.readouterr()
    assert result != 0
    assert "invalid_data" in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


@pytest.mark.parametrize(
    "reverse,relation", [(False, "subset"), (True, "related"), (False, "related")]
)
def test_trace_checks_variant_relation_and_direction(
    tmp_path: Path, reverse: bool, relation: str
) -> None:
    paths = _catalog(tmp_path)
    key = "claire-radar:agent-workbench"
    peer = "opencompass:agent-workbench"
    _add_claire_record(
        paths,
        tmp_path,
        # The full descriptor IdentityIndex.siblings_for writes for the peer.
        siblings=[
            {
                "key": peer,
                "slug": "opencompass-agent-workbench",
                "name": "Agent Workbench",
                "source": "opencompass_hub",
                "relation": "variant:related",
            }
        ],
    )
    _identity_rules(
        tmp_path,
        variants=[
            {"of": peer if reverse else key, "key": key if reverse else peer, "relation": relation}
        ],
    )
    payload = QueryService(paths).trace(key)
    stage = _trace_stages(payload)["identity"]
    assert stage["status"] == ("changed" if reverse or relation != "related" else "present")


def test_trace_rejects_ambiguous_radar_id(tmp_path: Path, monkeypatch) -> None:
    service = QueryService(_catalog(tmp_path))
    candidates = [
        {"key": "radar:arxiv:2608.26623", "source_id": "2608.26623"},
        {"key": "radar:hugging face papers:2608.26623", "source_id": "2608.26623"},
    ]
    monkeypatch.setattr(service, "_radar_candidates", lambda: candidates)
    with pytest.raises(QueryError, match="ambiguous") as error:
        service.trace("2608.26623")
    assert error.value.code == "ambiguous_identifier"
    assert service.trace(candidates[0]["key"])["identifier"] == candidates[0]["key"]


@pytest.mark.parametrize(
    "identifier", ["opencompass:agent-workbench", "opencompass-agent-workbench"]
)
def test_trace_uses_qualified_normalized_key(tmp_path: Path, identifier: str) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _source_records(
        tmp_path,
        [
            {
                "key": "opencompass:agent-workbench",
                "source": "opencompass_hub",
                "source_benchmark_id": "agent-workbench",
            }
        ],
    )
    wrong = tmp_path / "data/catalog/aaa_source_records.jsonl"
    wrong.write_text(
        json.dumps(
            {
                "key": "wrong:agent-workbench",
                "source_benchmark_id": "agent-workbench",
                "slug": "opencompass-agent-workbench",
            }
        )
        + "\n"
    )
    stage = _trace_stages(QueryService(paths).trace(identifier))["normalization"]
    assert stage["output"]["key"] == "opencompass:agent-workbench"


def test_trace_catalog_does_not_require_radar_snapshots(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    paths = QueryPaths(index=paths.index, shards=paths.shards, snapshots=tmp_path / "missing")
    payload = QueryService(paths).trace("opencompass-agent-workbench")
    assert _trace_stages(payload)["enrichment"]["status"] == "present"


def test_trace_missing_joined_shard_is_enrichment_failure(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    _add_claire_record(paths, tmp_path, siblings=[])
    _identity_rules(
        tmp_path,
        equivalent=[{"members": ["claire-radar:agent-workbench", "opencompass:agent-workbench"]}],
    )
    (paths.shards / "claire-agent-workbench.json").unlink()
    payload = QueryService(paths).trace("claire-radar:agent-workbench")
    assert payload["first_change"] == "enrichment"
    assert _trace_stages(payload)["identity"]["status"] == "present"


def test_trace_variant_without_crawled_parent_is_not_a_missing_join(tmp_path: Path) -> None:
    paths = _catalog(tmp_path)
    _source_records(
        tmp_path, [{"key": "opencompass:agent-workbench", "source_benchmark_id": "agent-workbench"}]
    )
    _identity_rules(
        tmp_path,
        variants=[
            {"key": "opencompass:agent-workbench", "of": "uncrawled-parent", "relation": "subset"}
        ],
    )
    payload = QueryService(paths).trace("opencompass-agent-workbench")
    assert _trace_stages(payload)["identity"]["status"] == "present"


@pytest.mark.parametrize(
    "rules",
    [
        [],
        ["bad"],
        {"equivalent": [42]},
        {"variants": [42]},
        {"equivalent": [{"members": "bad"}]},
        {"variants": "bad"},
        {"variants": [{"key": ["bad"], "of": "x"}]},
    ],
)
def test_trace_malformed_identity_is_machine_readable(tmp_path: Path, rules, capsys) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    (tmp_path / "data/catalog/identity.yml").write_text(yaml.safe_dump(rules))
    result = run_query_cli(
        [
            "trace",
            "opencompass-agent-workbench",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    captured = capsys.readouterr()
    assert result != 0
    assert "invalid_data" in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_trace_cli_serializes_unquoted_registry_dates(tmp_path: Path, capsys) -> None:
    paths = _catalog(tmp_path)
    index = json.loads(paths.index.read_text())
    record = {
        **index["benchmarks"][0],
        "key": "model-reports:dated",
        "slug": "dated",
        "source": "model_reports",
    }
    index["benchmarks"].append(record)
    index["count"] += 1
    paths.index.write_text(json.dumps(index))
    (tmp_path / "data/model_cards.yml").write_text(
        _model_cards_yaml({"id": "dated", "name": "Dated"}).replace(
            "  name: Dated\n", "  name: Dated\n  released: 2026-01-01\n"
        )
    )
    _score_archive(tmp_path, "dated")
    result = run_query_cli(
        [
            "trace",
            "dated",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert _trace_stages(payload)["source"]["output"]["released"] == "2026-01-01"


@pytest.mark.parametrize(
    "source,snapshot_id,prefix",
    [
        ("llm_stats", "llm_stats_2026-08-17", "llm-stats"),
        ("artificial_analysis", "artificial_analysis_2026-08-25", "artificial-analysis"),
        ("benchmark_saturation", "benchmark_saturation_2026-11-04", "benchmark-saturation"),
    ],
)
@pytest.mark.parametrize("mutation", ["unchanged", "changed", "deleted", "missing_file"])
def test_trace_tracks_snapshot_score_inputs(
    tmp_path: Path, source: str, snapshot_id: str, prefix: str, mutation: str
) -> None:
    from benchmark_radar.catalog import normalize_snapshot

    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    benchmark = {"benchmark_id": "aw", "name": "Agent Workbench"}
    score = {
        "benchmark_id": "aw",
        "benchmark_name": "Agent Workbench",
        "model_id": "m1",
        "model_name": "Model 1",
        "organization_name": "Org",
        "benchmark_score": "80",
        "rank": "1",
    }
    directory = tmp_path / "data/leaderboard_snapshots"
    directory.mkdir(exist_ok=True)
    for filename, rows in [("benchmarks.csv", [benchmark]), ("scores.csv", [score])]:
        with (directory / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    entry = {
        "id": snapshot_id,
        "source": source,
        "source_url": "https://example.com/leaderboard",
        "crawled_at": "2026-08-17T00:00:00Z",
        "benchmark_file": "leaderboard_snapshots/benchmarks.csv",
        "benchmark_count": 1,
        "scores_file": "leaderboard_snapshots/scores.csv",
        "score_row_count": 1,
        "benchmark_columns": {"benchmark_id": "benchmark_id", "benchmark_name": "name"},
        "columns": {
            "benchmark_id": "benchmark_id",
            "benchmark_name": "benchmark_name",
            "model": "model_name",
            "model_id": "model_id",
            "organization": "organization_name",
            "rank": "rank",
            "score": "benchmark_score",
        },
        "score_series_policy": "preserve_empty",
    }
    (tmp_path / "data/leaderboard_snapshots.yml").write_text(
        yaml.safe_dump({"schema_version": 1, "snapshots": [entry]})
    )
    normalized = normalize_snapshot({**entry, "benchmark_rows": [benchmark], "score_rows": [score]})
    record = normalized["source_records"][0]
    assert record["key"] == f"{prefix}:aw"
    index = json.loads(paths.index.read_text())
    # Keep the index's compact field types while supplying the real source identity.
    index["benchmarks"].append(
        {
            **index["benchmarks"][0],
            "key": record["key"],
            "slug": record["slug"],
            "source": source,
            "released": record["released"],
        }
    )
    index["count"] += 1
    paths.index.write_text(json.dumps(index))
    _source_records(tmp_path, [record])
    observations_path = tmp_path / f"data/catalog/{source}_score_observations.jsonl"
    observations_path.write_text(
        "".join(json.dumps(row) + "\n" for row in normalized["score_observations"])
    )
    (paths.shards / f"{record['slug']}.json").write_text(
        json.dumps({"record": record, "siblings": []})
    )
    scores_path = directory / "scores.csv"
    if mutation == "changed":
        scores_path.write_text(scores_path.read_text().replace(",80,", ",91,"))
    elif mutation == "deleted":
        scores_path.write_text(scores_path.read_text().splitlines()[0] + "\n")
    elif mutation == "missing_file":
        scores_path.unlink()
    if mutation in {"deleted", "missing_file"}:
        # The registry now declares a row the file no longer has, so
        # normalize-catalog would refuse it; trace must not report it present.
        with pytest.raises(QueryError) as error:
            QueryService(paths).trace(record["key"])
        assert error.value.code == "invalid_data"
        return
    stages = _trace_stages(QueryService(paths).trace(record["key"]))
    raw = stages["source"]["output"]
    assert raw["input_paths"]["scores_file"] == str(scores_path)
    assert len(raw["score_rows"]) == 1
    score_changes = [
        row
        for row in stages["normalization"]["changes"]
        if row["field"].startswith("score_observations.")
    ]
    assert bool(score_changes) == (mutation != "unchanged")


@pytest.mark.parametrize("mutation", ["unchanged", "changed", "deleted", "missing_file"])
def test_trace_tracks_opencompass_round2_input(tmp_path: Path, mutation: str) -> None:
    from benchmark_radar.catalog_opencompass import normalize_opencompass

    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    benchmark = {"benchmark_id": "agent-workbench", "name": "Agent Workbench"}
    _snapshot_input(tmp_path, [benchmark])
    round2 = tmp_path / "data/leaderboard_snapshots/opencompass_round2/opencompass_round2.jsonl"
    snapshot = yaml.safe_load((tmp_path / "data/leaderboard_snapshots.yml").read_text())[
        "snapshots"
    ][0]
    normalized = normalize_opencompass(
        round2, catalog_snapshot={**snapshot, "benchmark_rows": [benchmark]}
    )["source_records"][0]
    _source_records(tmp_path, [normalized])
    if mutation == "changed":
        row = json.loads(round2.read_text())
        row["name"] = "Changed benchmark name"
        round2.write_text(json.dumps(row) + "\n")
    elif mutation == "deleted":
        round2.write_text("")
    elif mutation == "missing_file":
        round2.unlink()
    if mutation in {"deleted", "missing_file"}:
        with pytest.raises(QueryError) as error:
            QueryService(paths).trace("opencompass:agent-workbench")
        assert error.value.code == "invalid_data"
        return
    stages = _trace_stages(QueryService(paths).trace("opencompass:agent-workbench"))
    assert stages["source"]["output"]["round2_evidence"]["name"] == (
        "Changed benchmark name" if mutation == "changed" else "Agent Workbench"
    )
    assert stages["normalization"]["status"] == ("changed" if mutation == "changed" else "present")


@pytest.mark.parametrize("registry", [["bad"], {"snapshots": [42]}, {"snapshots": "bad"}])
def test_trace_invalid_snapshot_registry_returns_query_error(tmp_path: Path, registry) -> None:
    paths = _catalog(tmp_path)
    _snapshot_input(tmp_path, [{"benchmark_id": "agent-workbench"}])
    (tmp_path / "data/leaderboard_snapshots.yml").write_text(yaml.safe_dump(registry))
    with pytest.raises(QueryError) as error:
        QueryService(paths).trace("opencompass-agent-workbench")
    assert error.value.code == "invalid_data"


@pytest.mark.parametrize(
    "rules",
    [
        {"schema_version": 99},
        {"schema_version": 1, "equivalent": [{"members": ["opencompass:agent-workbench"]}]},
        {"schema_version": 1, "equivalent": [{"group_id": "g", "members": [], "anchors": []}]},
        {
            "schema_version": 1,
            "equivalent": [{"group_id": "g", "basis": "reviewer_asserted", "anchors": ["paper"]}],
        },
        {
            "schema_version": 1,
            "equivalent": [
                {
                    "group_id": name,
                    "anchors": ["paper", "repo"],
                    "members": ["opencompass:agent-workbench"],
                }
                for name in ("a", "b")
            ],
        },
    ],
)
def test_trace_rejects_identity_rules_the_pipeline_rejects(tmp_path: Path, rules) -> None:
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    (tmp_path / "data/catalog/identity.yml").write_text(yaml.safe_dump(rules))
    with pytest.raises(QueryError) as error:
        QueryService(paths).trace("opencompass-agent-workbench")
    assert error.value.code == "invalid_data"


@pytest.mark.parametrize("kind", ["dates", "authors", "institutions", "overrides"])
@pytest.mark.parametrize("mutation", ["unchanged", "changed", "deleted"])
def test_trace_replays_reviewed_source_facts(tmp_path: Path, kind: str, mutation: str) -> None:
    from benchmark_radar.catalog import normalize_snapshot
    from benchmark_radar.catalog_authors import apply_benchmark_authors, load_benchmark_authors
    from benchmark_radar.catalog_dates import apply_benchmark_dates, load_benchmark_dates
    from benchmark_radar.catalog_evidence import attach_evidence
    from benchmark_radar.catalog_institutions import (
        apply_benchmark_institutions,
        load_benchmark_institutions,
    )
    from benchmark_radar.catalog_overrides import (
        apply_llm_stats_identity_overrides,
        load_llm_stats_identity_overrides,
    )
    from benchmark_radar.query import _trace_snapshot_changes

    directory = tmp_path / "data/catalog"
    directory.mkdir(parents=True)
    benchmark = {
        "benchmark_id": "aw",
        "name": "Example benchmark",
        "paper_url": "https://arxiv.org/abs/2601.00624",
        "relation": "introduces",
    }
    snapshot = {
        "id": "llm_stats_2026-08-17",
        "crawled_at": "2026-08-17T00:00:00Z",
        "benchmark_rows": [benchmark],
        "score_rows": [],
        "score_series_policy": "preserve_empty",
    }
    result = normalize_snapshot(snapshot)
    record = attach_evidence(result["source_records"], result["score_series"], [])[0]
    benchmark_path = directory / "benchmarks.csv"
    with benchmark_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=benchmark.keys())
        writer.writeheader()
        writer.writerow(benchmark)
    raw = {
        "snapshot": snapshot,
        "score_rows": [],
        "input_paths": {"benchmark_file": str(benchmark_path)},
    }
    (directory / "llm_stats_score_observations.jsonl").write_text("")
    facts = {
        "dates": {
            "released": "2026-01-01",
            "basis": "paper_first_version",
            "source_url": "https://arxiv.org/abs/2601.00624",
            "note": "Introducing paper",
        },
        "authors": {
            "authors": ["Alice"],
            "source_url": "https://arxiv.org/abs/2601.00624",
            "retrieved_at": "2026-11-01",
        },
        "institutions": {
            "institutions": ["Example University"],
            "doi": "10.48550/arxiv.2601.00624",
            "source_url": "https://openalex.org/W123",
            "retrieved_at": "2026-11-01",
        },
        "overrides": {
            "resolution_status": "not_found",
            "repo_kind": "not_found",
            "note": "Unresolved benchmark",
            "candidate_matches": [{"url": "https://example.com/candidate", "note": "Needs review"}],
        },
    }
    filename = (
        "llm_stats_identity_overrides.yml" if kind == "overrides" else f"benchmark_{kind}.yml"
    )
    path = directory / filename
    key = "aw" if kind == "overrides" else record["key"]
    payload = {"schema_version": 1, "benchmarks": {key: facts[kind]}}
    path.write_text(yaml.safe_dump(payload))
    normalized_path = directory / "llm_stats_source_records.jsonl"
    normalized_path.write_text(json.dumps(record) + "\n")
    loaders = {
        "dates": (load_benchmark_dates, apply_benchmark_dates),
        "authors": (load_benchmark_authors, apply_benchmark_authors),
        "institutions": (load_benchmark_institutions, apply_benchmark_institutions),
        "overrides": (load_llm_stats_identity_overrides, apply_llm_stats_identity_overrides),
    }
    load, apply = loaders[kind]
    stored = apply([record], load([record], path))[0]
    stored = json.loads(json.dumps(stored).replace(str(tmp_path) + "/", ""))
    normalized_path.write_text(json.dumps(stored) + "\n")
    if mutation == "changed":
        field = {
            "dates": "released",
            "authors": "authors",
            "institutions": "institutions",
            "overrides": "note",
        }[kind]
        payload["benchmarks"][key][field] = {
            "dates": "2026-01-02",
            "authors": ["Bob"],
            "institutions": ["Other University"],
            "overrides": "Reviewed again",
        }[kind]
    elif mutation == "deleted":
        payload["benchmarks"] = {}
    path.write_text(yaml.safe_dump(payload))
    changes = _trace_snapshot_changes(raw, stored, normalized_path)
    assert bool(changes) == (mutation != "unchanged")


@pytest.mark.parametrize("change", ["schema_version", "benchmark_count"])
def test_trace_rejects_snapshot_metadata_the_pipeline_rejects(tmp_path: Path, change: str) -> None:
    # A mapping-shaped registry with an unsupported schema_version or a stale
    # declared row count is refused by leaderboard_snapshots.load_snapshots,
    # so normalize-catalog cannot run; trace must not report source present.
    paths = _catalog(tmp_path)
    _snapshot_input(tmp_path, [{"benchmark_id": "agent-workbench", "name": "Agent Workbench"}])
    registry_path = tmp_path / "data/leaderboard_snapshots.yml"
    registry = yaml.safe_load(registry_path.read_text())
    if change == "schema_version":
        registry["schema_version"] = 99
    else:
        registry["snapshots"][0]["benchmark_count"] = 2
    registry_path.write_text(yaml.safe_dump(registry))
    with pytest.raises(QueryError) as error:
        QueryService(paths).trace("opencompass-agent-workbench")
    assert error.value.code == "invalid_data"


@pytest.mark.parametrize("content", ["- not\n- a mapping\n", "just a scalar\n"])
def test_trace_cli_rejects_a_non_mapping_model_card_registry(
    tmp_path: Path, capsys, content: str
) -> None:
    # A list- or scalar-shaped model_cards.yml used to reach registry.get and
    # escape run_query_cli as an AttributeError traceback.
    paths = _catalog(tmp_path)
    index = json.loads(paths.index.read_text())
    record = {
        **index["benchmarks"][0],
        "key": "model-reports:dated",
        "slug": "dated",
        "source": "model_reports",
    }
    index["benchmarks"].append(record)
    index["count"] += 1
    paths.index.write_text(json.dumps(index))
    (tmp_path / "data/model_cards.yml").write_text(content)
    result = run_query_cli(
        [
            "trace",
            "dated",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    captured = capsys.readouterr()
    assert result != 0
    assert "invalid_data" in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_trace_validates_identity_rules_against_current_source_records(tmp_path: Path) -> None:
    # The sources advanced past a deleted identity member but the published
    # index is stale and still lists it. normalize-catalog validates
    # identity.yml against the current source records and would refuse the
    # rule, so trace must not report identity present for the survivor.
    paths = _catalog(tmp_path)
    related = _add_claire_record(paths, tmp_path, siblings=[])
    _source_records(tmp_path, [{**related, "source_benchmark_id": "agent-workbench"}])
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": ["claire-radar:agent-workbench", "opencompass:agent-workbench"],
                "note": "Same benchmark imported from two sources.",
            }
        ],
    )
    with pytest.raises(QueryError) as error:
        QueryService(paths).trace("claire-radar:agent-workbench")
    assert error.value.code == "invalid_data"
    assert "opencompass:agent-workbench" in str(error.value)


def test_trace_resolves_normalized_only_record_without_radar_snapshots(tmp_path: Path) -> None:
    # A record present only in data/catalog/*_source_records.jsonl must trace
    # in a checkout without data/snapshots; loading Radar first used to raise
    # data_unavailable before any stage was reported.
    paths = _catalog(tmp_path)
    shutil.rmtree(paths.snapshots)
    _source_records(
        tmp_path,
        [{"key": "opencompass:fresh-bench", "slug": "fresh-bench", "name": "Fresh Bench"}],
    )
    stages = _trace_stages(QueryService(paths).trace("fresh-bench"))
    assert stages["normalization"]["status"] == "present"
    assert stages["normalization"]["output"]["key"] == "opencompass:fresh-bench"


@pytest.mark.parametrize(
    ("root", "separator"),
    [("/home/me/benchmark-radar", "/"), ("C:\\Users\\me\\benchmark-radar", "\\")],
)
def test_trace_relativizes_lineage_paths_on_any_platform(root: str, separator: str) -> None:
    # On Windows the old text replace of str(root) + "/" ran on serialized
    # JSON, where backslashes are escaped, so absolute paths survived and
    # every replayed identity override looked like a normalization change.
    from benchmark_radar.query import _trace_relativize

    path = separator.join([root, "data", "catalog", "llm_stats_identity_overrides.yml"])
    record = {
        "identity_override": {
            "source_path": path,
            "evidence": [{"locator": f"{path}#benchmarks.aw.note"}],
        },
        "note": "untouched",
    }
    assert _trace_relativize(record, root) == {
        "identity_override": {
            "source_path": "data/catalog/llm_stats_identity_overrides.yml",
            "evidence": [
                {"locator": "data/catalog/llm_stats_identity_overrides.yml#benchmarks.aw.note"}
            ],
        },
        "note": "untouched",
    }


def test_trace_replays_library_enrichment_before_accepting_the_index(tmp_path: Path) -> None:
    # library_direction exists only on index rows, so the normalized-to-index
    # diff never saw it. A direction review added after the last rebuild must
    # surface as an identity-stage change instead of every stage reading
    # present while a rebuild would change the index.
    paths = _catalog(tmp_path)
    _add_claire_record(paths, tmp_path, siblings=[])
    _identity_rules(tmp_path)
    catalog_dir = tmp_path / "data/catalog"
    (catalog_dir / "claire_library_categories.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "taxonomy": {"categories": [{"id": "agents", "label": "Agents"}]},
                "records": {},
            }
        )
    )
    service = QueryService(paths)
    assert service.trace("claire-radar:agent-workbench")["first_change"] is None

    (catalog_dir / "library_direction_reviews.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "reviewed_by": "reviewer",
                "reviewed_at": "2026-11-17",
                "directions": {"claire-radar:agent-workbench": "agents"},
            }
        )
    )
    payload = QueryService(paths).trace("claire-radar:agent-workbench")
    assert payload["first_change"] == "identity"
    change = next(
        row
        for row in _trace_stages(payload)["identity"]["changes"]
        if row["field"] == "library_direction"
    )
    assert change["before"] is None
    assert change["after"]["primary"] == "agents"


def test_trace_cli_reports_invalid_utf8_source_records(tmp_path: Path, capsys) -> None:
    # read_text raised UnicodeDecodeError, which the scan did not catch, so
    # the CLI printed a traceback instead of the invalid_data envelope.
    paths = _catalog(tmp_path)
    catalog_dir = tmp_path / "data/catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "opencompass_source_records.jsonl").write_bytes(b'{"key": "\xff"}\n')
    result = run_query_cli(
        [
            "trace",
            "opencompass-agent-workbench",
            "--json",
            "--index",
            str(paths.index),
            "--shards",
            str(paths.shards),
            "--snapshots",
            str(paths.snapshots),
        ]
    )
    captured = capsys.readouterr()
    assert result != 0
    assert "invalid_data" in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def _model_reports_inputs(
    tmp_path: Path, results: list[dict], *, cited: bool = True, released: str | None = None
) -> None:
    (tmp_path / "data" / "model_cards.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": [
                    {
                        "id": bench,
                        "name": bench.title(),
                        "domain": "agents",
                        "caveat": "Fixture benchmark.",
                        "url": f"https://example.com/{bench}",
                        **(
                            {"released": released}
                            if released and bench == "agent-workbench"
                            else {}
                        ),
                    }
                    for bench in ("agent-workbench", "other-bench")
                ],
                "model_cards": [
                    {
                        "id": "example_card",
                        "organization": "Example Lab",
                        "model": "Example-1",
                        "document_type": "system_card",
                        "url": "https://example.com/card",
                        "benchmarks": ["agent-workbench"],
                    },
                    # A card that mentions the benchmark without scoring it.
                    {
                        "id": "mention_card",
                        "organization": "Other Lab",
                        "model": "Other-1",
                        "document_type": "technical_report",
                        "url": "https://example.com/mention",
                        "benchmarks": ["agent-workbench", "other-bench"]
                        if cited
                        else ["other-bench"],
                    },
                ],
                "source_documents": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "benchmark_scores.yml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": [
                    {
                        "benchmark_id": "agent-workbench",
                        "metric": "accuracy",
                        "direction": "higher_is_better",
                        "unit": "percent",
                    }
                ],
                "results": [
                    {
                        "benchmark_id": "agent-workbench",
                        "instrument": "aw_v1",
                        "protocol": "standard",
                        "organization": "Example Lab",
                        "source_id": "example_card",
                        "reported_at": "2026-01-01",
                        "read_from": "html_text",
                        **result,
                    }
                    for result in results
                ],
            }
        ),
        encoding="utf-8",
    )


_TWO_SCORES = [{"model": "Example-1", "value": 91.5}, {"model": "Example-2", "value": 88.0}]


@pytest.mark.parametrize(
    ("results", "cited", "field"),
    [
        # A changed score, a deleted score, and a dropped card mention.
        ([{"model": "Example-1", "value": 75.0}, _TWO_SCORES[1]], True, "score_observations"),
        (_TWO_SCORES[:1], True, "score_observations"),
        (_TWO_SCORES, False, "documents"),
    ],
)
def test_trace_replays_model_report_inputs_before_accepting_normalization(
    tmp_path: Path, results: list[dict], cited: bool, field: str
) -> None:
    # A model_reports raw value has no snapshot, so normalization used to
    # return no changes at all: a changed or deleted score or a dropped card
    # mention left every stage present against stale generated artifacts.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES)
    _write_model_reports_catalog(tmp_path)
    service = QueryService(paths)
    assert service.trace("model-reports:agent-workbench")["first_change"] is None

    _model_reports_inputs(tmp_path, results, cited=cited)
    payload = QueryService(paths).trace("model-reports:agent-workbench")
    assert payload["first_change"] == "normalization"
    changed = {
        change["field"].split(".")[0]
        for change in _trace_stages(payload)["normalization"]["changes"]
    }
    assert field in changed


def test_trace_rebuilds_index_only_score_fields(tmp_path: Path) -> None:
    # normalize-catalog stopped after write_catalog: the normalized rows carry
    # a second scored model but the index was not rebuilt. score_count and
    # scored_models exist only on the index, so a shared-key diff missed it.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _model_reports_inputs(tmp_path, [{"model": "Example-1", "value": 91.5}])
    _write_model_reports_catalog(tmp_path)
    _model_reports_inputs(
        tmp_path,
        [{"model": "Example-1", "value": 91.5}, {"model": "Example-2", "value": 88.0}],
    )
    _write_model_reports_catalog(tmp_path, sync_index=False)

    payload = QueryService(paths).trace("model-reports:agent-workbench")
    stages = _trace_stages(payload)
    assert stages["normalization"]["status"] == "present"
    assert payload["first_change"] == "identity"
    changed = {change["field"] for change in stages["identity"]["changes"]}
    assert {"score_count", "scored_models"} <= changed


def test_trace_rejects_ambiguous_normalized_source_identifiers(tmp_path: Path) -> None:
    # llm-stats and Artificial Analysis both carry aime-2025. With no index
    # match the scan used to keep whichever file sorted first.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _source_records(
        tmp_path,
        [
            {"key": "llm-stats:aime-2025", "source_benchmark_id": "aime-2025"},
            {"key": "artificial-analysis:aime-2025", "source_benchmark_id": "aime-2025"},
        ],
    )
    service = QueryService(paths)
    with pytest.raises(QueryError) as error:
        service.trace("aime-2025")
    assert error.value.code == "ambiguous_identifier"
    assert "llm-stats:aime-2025" in str(error.value)
    assert "artificial-analysis:aime-2025" in str(error.value)
    for key in ("llm-stats:aime-2025", "artificial-analysis:aime-2025"):
        stage = _trace_stages(service.trace(key))["normalization"]
        assert stage["output"]["key"] == key


def test_trace_replays_identity_donor_source_inputs(tmp_path: Path) -> None:
    # The recipient inherits its release date from a model_reports donor. The
    # donor's registry changed but the normalized JSONLs did not; rebuilding
    # the recipient from the stored donor row reapplied the old date and left
    # every stage present.
    paths = _catalog(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES, released="2026-01-01")
    _write_model_reports_catalog(tmp_path)
    _add_claire_record(paths, tmp_path, siblings=[])
    donor = "model-reports:agent-workbench"
    recipient = "claire-radar:agent-workbench"
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": [recipient, donor],
                "inherit_from": donor,
                "note": "Same benchmark; the report registry carries the release.",
            }
        ],
    )

    def donor_changes() -> list[str]:
        stage = _trace_stages(QueryService(paths).trace(recipient))["identity"]
        return [row["field"] for row in stage["changes"] if row["field"].startswith("donor.")]

    assert donor_changes() == []
    _model_reports_inputs(tmp_path, _TWO_SCORES, released="2026-03-01")
    assert f"donor.{donor}.released" in donor_changes()


def test_trace_compares_full_sibling_descriptors(tmp_path: Path) -> None:
    # Key and relation still match, but the peer's slug changed and shard
    # generation was interrupted: the detail link is broken.
    paths = _catalog(tmp_path)
    _add_claire_record(
        paths,
        tmp_path,
        siblings=[
            {
                "key": "opencompass:agent-workbench",
                "slug": "stale-slug",
                "name": "Agent Workbench",
                "source": "opencompass_hub",
                "relation": "equivalent",
            }
        ],
    )
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": ["claire-radar:agent-workbench", "opencompass:agent-workbench"],
                "note": "Same benchmark imported from two sources.",
            }
        ],
    )
    payload = QueryService(paths).trace("claire-radar:agent-workbench")
    assert payload["first_change"] == "identity"
    change = next(
        row
        for row in _trace_stages(payload)["identity"]["changes"]
        if row["field"] == "siblings.opencompass:agent-workbench.slug"
    )
    assert change == {
        "field": "siblings.opencompass:agent-workbench.slug",
        "before": "stale-slug",
        "after": "opencompass-agent-workbench",
    }


def test_trace_compares_shard_score_payload(tmp_path: Path) -> None:
    # The record agrees but an interrupted shard swap left an old score.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES)
    _write_model_reports_catalog(tmp_path)
    slug = next(
        row["slug"]
        for row in json.loads(paths.index.read_text(encoding="utf-8"))["benchmarks"]
        if row["key"] == "model-reports:agent-workbench"
    )
    shard_path = paths.shards / f"{slug}.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["scores_by_source"]["model_reports"]["rows"].pop()
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    payload = QueryService(paths).trace("model-reports:agent-workbench")
    assert payload["first_change"] == "enrichment"
    fields = {row["field"] for row in _trace_stages(payload)["enrichment"]["changes"]}
    assert "scores_by_source.model_reports" in fields


@pytest.mark.parametrize(
    ("missing_from", "flagged"),
    [
        ("leaderboard.csv", True),
        ("leaderboard.json", True),
        # Markdown is top-N by design, so absence there is not a change.
        ("leaderboard.md", False),
    ],
)
def test_trace_checks_full_export_membership_for_every_source(
    tmp_path: Path, missing_from: str, flagged: bool
) -> None:
    # write_exports refuses CSV/JSON unless every index slug is an entry; the
    # trace used to inspect exports only for model_reports and to flag only a
    # read error, so an OpenCompass record missing from a stale export passed.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    slug = "opencompass-agent-workbench"
    data_dir = tmp_path / "site" / "data"
    members = {
        "leaderboard.csv": missing_from != "leaderboard.csv",
        "leaderboard.json": missing_from != "leaderboard.json",
        "leaderboard.md": missing_from != "leaderboard.md",
    }
    ids = lambda present: [slug, "other"] if present else ["other"]  # noqa: E731
    (data_dir / "leaderboard.csv").write_text(
        "benchmark_id\n" + "".join(f"{i}\n" for i in ids(members["leaderboard.csv"])),
        encoding="utf-8",
    )
    (data_dir / "leaderboard.json").write_text(
        json.dumps({"entries": [{"benchmark_id": i} for i in ids(members["leaderboard.json"])]}),
        encoding="utf-8",
    )
    (data_dir / "leaderboard.md").write_text(
        "\n".join(ids(members["leaderboard.md"])), encoding="utf-8"
    )

    payload = QueryService(paths).trace(slug)
    outputs = _trace_stages(payload)["outputs"]
    assert outputs["output"][f"export:{missing_from}"]["contains"] is False
    fields = {row["field"] for row in outputs["changes"]}
    assert (f"export:{missing_from}" in fields) is flagged
    assert outputs["status"] == ("changed" if flagged else "present")


def test_trace_reports_a_missing_crawl_registry(tmp_path: Path) -> None:
    # Issue #1292: without data/leaderboard_snapshots.yml the crawl input was
    # classed unavailable and the normalized row stood in as the source, so
    # every stage read present.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    index = json.loads(paths.index.read_text(encoding="utf-8"))
    _source_records(tmp_path, [index["benchmarks"][0]])
    (tmp_path / "data" / "leaderboard_snapshots.yml").unlink()

    payload = QueryService(paths).trace("opencompass-agent-workbench")
    source = _trace_stages(payload)["source"]
    assert source["status"] == "absent"
    assert "leaderboard_snapshots.yml" in source["error"]
    assert payload["first_change"] == "source"


def test_trace_reports_a_missing_score_archive(tmp_path: Path) -> None:
    # Issue #1292: normalize-catalog fails without data/benchmark_scores.yml,
    # but trace replayed an empty archive for an unscored benchmark.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES)
    _write_model_reports_catalog(tmp_path)
    (tmp_path / "data" / "benchmark_scores.yml").unlink()

    payload = QueryService(paths).trace("model-reports:agent-workbench")
    source = _trace_stages(payload)["source"]
    assert source["status"] == "absent"
    assert "benchmark_scores.yml" in source["error"]
    assert payload["first_change"] == "source"


def test_trace_reports_a_donor_gone_from_its_input(tmp_path: Path) -> None:
    # Issue #1292: the donor's benchmark left model_cards.yml but its stored
    # normalized row remained, so inheritance was replayed from stale data.
    paths = _catalog(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES, released="2026-01-01")
    _write_model_reports_catalog(tmp_path)
    _add_claire_record(paths, tmp_path, siblings=[])
    donor = "model-reports:agent-workbench"
    recipient = "claire-radar:agent-workbench"
    _identity_rules(
        tmp_path,
        equivalent=[
            {
                "members": [recipient, donor],
                "inherit_from": donor,
                "note": "Same benchmark; the report registry carries the release.",
            }
        ],
    )
    registry_path = tmp_path / "data" / "model_cards.yml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["benchmarks"] = [
        row for row in registry["benchmarks"] if row["id"] != "agent-workbench"
    ]
    for card in registry["model_cards"]:
        card["benchmarks"] = [
            bench for bench in card["benchmarks"] if bench != "agent-workbench"
        ] or ["other-bench"]
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")

    stage = _trace_stages(QueryService(paths).trace(recipient))["identity"]
    change = next(row for row in stage["changes"] if row["field"] == f"donor.{donor}")
    assert change["after"].startswith("absent from its source input")
    assert stage["status"] == "changed"


def test_trace_compares_the_full_shard_record(tmp_path: Path) -> None:
    # Issue #1292: the shard was compared only with the compact index row, so
    # a stale shard-only field (here the record's documents) passed while
    # every index field agreed.
    paths = _catalog(tmp_path)
    _identity_rules(tmp_path)
    _model_reports_inputs(tmp_path, _TWO_SCORES)
    _write_model_reports_catalog(tmp_path)
    key = "model-reports:agent-workbench"
    index_row = next(
        row
        for row in json.loads(paths.index.read_text(encoding="utf-8"))["benchmarks"]
        if row["key"] == key
    )
    shard_path = paths.shards / f"{index_row['slug']}.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    assert "documents" in shard["record"] and "documents" not in index_row
    shard["record"]["documents"] = []
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    payload = QueryService(paths).trace(key)
    stage = _trace_stages(payload)["enrichment"]
    assert stage["status"] == "changed"
    change = next(row for row in stage["changes"] if row["field"] == "documents")
    assert change["before"] == []
    assert change["after"]
