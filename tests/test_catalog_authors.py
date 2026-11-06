"""Benchmark authors from each benchmark's own introducing arXiv paper (#933)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from benchmark_radar.catalog import CatalogError
from benchmark_radar.catalog_authors import (
    DEFAULT_AUTHORS_PATH,
    apply_benchmark_authors,
    introducing_arxiv_id,
    load_benchmark_authors,
)


def _record(key, *, source="claire_radar", relation="introduces", papers=("2605.21858",)):
    return {
        "key": key,
        "source": source,
        "artifacts": [
            {"kind": "paper", "url": f"https://arxiv.org/abs/{paper}"} for paper in papers
        ],
        "provenance": {"relation": relation} if relation else {},
    }


def _write(tmp_path: Path, benchmarks: dict) -> Path:
    path = tmp_path / "authors.yml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "benchmarks": benchmarks}))
    return path


def _fact(paper="2605.21858", authors=("Mengqi Lei", "Yue Gao")):
    return {
        "source_url": f"https://arxiv.org/abs/{paper}",
        "retrieved_at": "2026-11-03",
        "authors": list(authors),
    }


def test_only_a_paper_that_introduces_the_benchmark_names_its_creators():
    assert introducing_arxiv_id(_record("a")) == "2605.21858"
    assert introducing_arxiv_id(_record("b", source="model_reports", relation=None)) == (
        "2605.21858"
    )
    # A paper that evaluates or aggregates benchmarks did not make this one.
    for relation in ("evaluates_only", "aggregates", "unclear", None):
        assert introducing_arxiv_id(_record("c", relation=relation)) is None
    # Two candidate papers is not certainty.
    assert introducing_arxiv_id(_record("d", papers=("2605.21858", "2605.22034"))) is None
    assert introducing_arxiv_id(_record("e", papers=())) is None


def test_load_rejects_facts_that_do_not_belong_to_the_record(tmp_path):
    records = [_record("claire-radar:a"), _record("claire-radar:b", relation="aggregates")]
    assert load_benchmark_authors(records, _write(tmp_path, {"claire-radar:a": _fact()}))
    bad = {
        "unknown key": {"claire-radar:zzz": _fact()},
        "not introducing": {"claire-radar:b": _fact()},
        "another paper": {"claire-radar:a": _fact(paper="2605.22034")},
        "no authors": {"claire-radar:a": _fact(authors=())},
        "padded name": {"claire-radar:a": _fact(authors=(" Yue Gao",))},
        "bad date": {"claire-radar:a": {**_fact(), "retrieved_at": "Nov 3"}},
    }
    for case, benchmarks in bad.items():
        with pytest.raises(CatalogError):
            load_benchmark_authors(records, _write(tmp_path, benchmarks))
            pytest.fail(case)


def test_apply_fills_exact_records_and_cites_the_paper():
    records = [_record("claire-radar:a"), _record("claire-radar:b")]
    facts = {"claire-radar:a": _fact()}
    a, b = apply_benchmark_authors(records, facts)
    assert a["authors"] == ["Mengqi Lei", "Yue Gao"]
    assert a["authors_reference"] == {
        "source_key": "claire-radar:a",
        "basis": "arxiv_metadata",
        "source_url": "https://arxiv.org/abs/2605.21858",
        "retrieved_at": "2026-11-03",
    }
    assert "authors" not in b


def test_committed_file_names_only_introducing_papers():
    payload = yaml.safe_load(DEFAULT_AUTHORS_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    for key, fact in payload["benchmarks"].items():
        assert key.startswith(("claire-radar:", "model-reports:")), key
        assert fact["source_url"].startswith("https://arxiv.org/abs/"), key
        assert fact["authors"], key
