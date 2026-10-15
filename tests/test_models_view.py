"""The Models view merged from benchmark-radar.com's Model Evals (#420)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_seeds import _models_seed, model_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_models_behaviour_runs_against_the_production_functions():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/models_harness.mjs"], check=True, timeout=60, cwd=ROOT)


def test_seed_lists_every_scored_model_by_lab_with_benchmark_links():
    records = [
        {
            "slug": "aime",
            "key": "llm-stats:aime",
            "name": "AIME",
            "source": "llm_stats",
            "scored_models": [{"name": "Acme <One>", "date": "2026-02-01"}],
        },
        {"slug": "x", "key": "claire-radar:x", "name": "X", "source": "claire_radar"},
    ]
    registry = {"models": [{"model": "Acme <One>", "organization": "Acme"}]}

    nav, rows, status = _models_seed(records, registry).values()

    assert '<a class="library-direction" href="/models/?lab=Acme">' in nav
    assert "Acme &lt;One&gt;" in rows
    assert '<a class="model-benchmark" href="/benchmarks/aime/">AIME</a>' in rows
    assert "1 models with a reported score on 1 of 2 benchmark records" in status


def test_seed_order_matches_the_live_catalog():
    records = [
        {
            "slug": "a",
            "key": "k:a",
            "name": "A",
            "source": "s",
            "scored_models": [
                {"name": "beta", "date": "2026-01-01"},
                {"name": "Alpha", "date": "2026-01-01"},
                {"name": "Zed", "date": "2026-05-01"},
            ],
        },
    ]
    assert [model["name"] for model in model_catalog(records, None)] == ["Zed", "Alpha", "beta"]


def test_no_scored_models_publish_no_models_page():
    assert _models_seed([{"slug": "a", "key": "k", "name": "A", "source": "s"}], None) == {}
    assert _models_seed([], None) == {}


def test_models_view_never_aggregates_or_prints_scores():
    # Two reported numbers are rarely comparable (CONTRIBUTING.md), so the
    # merged view lists which benchmarks a model has scores on and never a
    # value, an average or a ranking by score.
    script = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    code = script.split("const MODEL_DOCUMENT_TYPES", 1)[1].split("// --- Research-direction", 1)[0]
    code = code.split("// --- Catalog detail", 1)[0]
    for forbidden in ("average", "score_summary", "display_max"):
        assert forbidden not in code
    # A score value would be read as `.value`; `Map.values()` is not one.
    assert not re.search(r"\.value\b", code)


def test_a_model_name_under_two_labs_is_listed_under_both():
    records = [
        {
            "slug": "a",
            "key": "k:a",
            "name": "A",
            "source": "s",
            "scored_models": [{"name": "Qwen2.5-Omni-7B", "date": "2026-01-01"}],
        }
    ]
    registry = {
        "models": [
            {"model": "Qwen2.5-Omni-7B", "organization": "Alibaba"},
            {"model": "Qwen2.5-Omni-7B", "organization": "Qwen"},
        ]
    }
    [model] = model_catalog(records, registry)
    assert model["organizations"] == ["Alibaba", "Qwen"]
    nav, rows, _ = _models_seed(records, registry).values()
    assert "/models/?lab=Alibaba" in nav and "/models/?lab=Qwen" in nav
    assert "Alibaba / Qwen" in rows


def test_case_only_spellings_are_one_model_and_unscored_records_are_counted():
    records = [
        {
            "slug": "a",
            "key": "k:a",
            "name": "A",
            "source": "s",
            "scored_models": [{"name": "MiniMax M1 40k", "date": "2026-01-01"}],
        },
        {
            "slug": "b",
            "key": "k:b",
            "name": "B",
            "source": "s",
            "scored_models": [{"name": "MiniMax M1 40K", "date": "2026-01-02"}],
        },
        {"slug": "c", "key": "k:c", "name": "C", "source": "s"},
    ]
    registry = {"models": [{"model": "MiniMax M1 40K", "organization": "MiniMax"}]}
    [model] = model_catalog(records, registry)
    assert model["name"] == "MiniMax M1 40K"
    assert [record["slug"] for record in model["records"]] == ["a", "b"]
    _, rows, _ = _models_seed(records, registry).values()
    assert "1 benchmark records have no reported model score." in rows
    assert '<a href="/library/">Browse them in the Library</a>' in rows


def test_seed_lists_sources_and_document_only_labs():
    records = [
        {
            "slug": "a",
            "key": "k:a",
            "name": "A",
            "source": "llm_stats",
            "scored_models": [{"name": "Olmo 3", "date": "2026-01-01"}],
        },
    ]
    registry = {"models": [{"model": "Olmo 3", "organization": "Allen Institute for AI"}]}
    documents = {"documents": [{"id": "d", "document_type": "release_post", "organization": "Ai2"}]}
    nav, rows, _ = _models_seed(records, registry, documents).values()
    assert "/models/?lab=Ai2" in nav
    assert "scores on 1 benchmark record · LLM Stats" in rows
