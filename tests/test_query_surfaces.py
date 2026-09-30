from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from benchmark_radar.citation import (
    ARXIV_ID,
    ARXIV_URL,
    apa_citation,
    bibtex_citation,
    citation_block,
    latex_citation,
)
from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.query import QueryError, QueryPaths, QueryService, _tokens
from benchmark_radar.query_cli import run_query_cli
from benchmark_radar.query_http import create_query_server
from benchmark_radar.snapshots import write_snapshot


def _catalog(tmp_path: Path) -> QueryPaths:
    index_path = tmp_path / "site" / "data" / "benchmark-index.json"
    shard_dir = index_path.parent / "benchmarks"
    snapshot_dir = tmp_path / "data" / "snapshots"
    index_path.parent.mkdir(parents=True)
    shard_dir.mkdir()
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
    assert result["matching_policy"]["name"] == "lexical_candidates_v1"
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


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/?repo=github.com/a/b&paper=arxiv.org/abs/2601.12345"
        "&dataset=huggingface.co/datasets/a/b",
        "https://example.org/github.com/arxiv.org/huggingface.co/datasets/a/b",
        "https://github.com.evil.example/arxiv.org/huggingface.co/datasets/a/b",
        "https://arxiv.org.evil.example/github.com/huggingface.co/datasets/a/b",
        "https://huggingface.co.evil.example/datasets/a/b?paper=arxiv.org&repo=github.com",
        "https://github.com@evil.example/?paper=arxiv.org&dataset=kaggle.com/datasets/a/b",
    ],
)
def test_radar_artifact_filters_use_url_authority_instead_of_embedded_text(
    tmp_path: Path, url: str
) -> None:
    # Regression: domain strings in unrelated URLs falsely satisfied artifact filters.
    paths = _catalog(tmp_path)
    path = next(paths.snapshots.glob("*.json"))
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["evidence_items"][0]["url"] = url
    snapshot["evidence_items"][0]["artifact_urls"] = []
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    service = QueryService(paths)
    candidate = service.search("agent", scope="radar")["results"][0]
    for flag in ("has_repo", "has_paper", "has_dataset"):
        assert candidate[flag] is False
        assert service.search("agent", scope="radar", **{flag: True})["count"] == 0
        assert service.search("agent", scope="radar", **{flag: False})["count"] == 1


@pytest.mark.parametrize(
    ("url", "flag"),
    [
        ("https://GITHUB.COM/example/benchmark/tree/main", "has_repo"),
        ("https://github.com/", "has_repo"),
        ("https://arxiv.org/abs/2601.12345", "has_paper"),
        ("https://www.arxiv.org/pdf/2601.12345.pdf", "has_paper"),
        ("https://arxiv.org/format/hep-th/9901001v3", "has_paper"),
        ("https://arxiv.org/src/hep-th/9901001v3", "has_paper"),
        ("https://arxiv.org/ftp/hep-th/papers/9901/9901001.pdf", "has_paper"),
        ("https://arxiv.org/html/2601.12345v2", "has_paper"),
        ("https://HUGGINGFACE.CO/datasets/example/benchmark", "has_dataset"),
        ("https://huggingface.co/datasets/example", "has_dataset"),
        ("https://www.kaggle.com/datasets/example/benchmark", "has_dataset"),
    ],
)
@pytest.mark.parametrize("location", ["main", "artifact"])
def test_radar_artifact_filters_keep_first_party_artifact_links(
    tmp_path: Path, url: str, flag: str, location: str
) -> None:
    paths = _catalog(tmp_path)
    path = next(paths.snapshots.glob("*.json"))
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["evidence_items"][0]["url"] = (
        url if location == "main" else "https://example.org/benchmark"
    )
    snapshot["evidence_items"][0]["artifact_urls"] = [url] if location == "artifact" else []
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = QueryService(paths).search("agent", scope="radar", **{flag: True})
    assert result["count"] == 1
    assert result["results"][0][flag] is True


def test_radar_non_string_artifact_urls_do_not_break_url_flags(tmp_path: Path) -> None:
    # Regression: accepted snapshots may contain an empty artifact object; parsing
    # it as a URL introduced an AttributeError that the old flags did not raise.
    paths = _catalog(tmp_path)
    path = next(paths.snapshots.glob("*.json"))
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["evidence_items"][0]["url"] = "https://example.org/benchmark"
    snapshot["evidence_items"][0]["artifact_urls"] = [{}]
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    candidate = QueryService(paths).search("agent", scope="radar")["results"][0]
    assert all(candidate[flag] is False for flag in ("has_paper", "has_repo", "has_dataset"))


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


def test_cli_labels_partial_candidates_without_hiding_them(tmp_path: Path, capsys) -> None:
    # Regression: the terminal rendered weak one-token evidence as ordinary
    # matches, so an agent had no top-level signal that no full lexical match existed.
    paths = _catalog(tmp_path)

    exit_code = run_query_cli(
        [
            "search",
            "protein agent prediction",
            "--scope",
            "catalog",
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
    assert "2 of 2 partial lexical candidates" in output
    assert "none matched every query token" in output
    assert "Agent Workbench" in output


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
        "schema_version": 6,
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
        "schema_version": 6,
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
        "Wu, K., Zhou, J., Shang, E., Wang, J., Han, P., Wang, J., & Xu, W. (2026). "
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
