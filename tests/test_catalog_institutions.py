"""Benchmark institutions from OpenAlex's record of the introducing paper (#933)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from benchmark_radar.catalog import CatalogError
from benchmark_radar.catalog_institutions import (
    DEFAULT_INSTITUTIONS_PATH,
    apply_benchmark_institutions,
    load_benchmark_institutions,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_openalex_institutions as fetch  # noqa: E402


def _record(key, *, relation="introduces", papers=("2605.21858",)):
    return {
        "key": key,
        "source": "claire_radar",
        "artifacts": [
            {"kind": "paper", "url": f"https://arxiv.org/abs/{paper}"} for paper in papers
        ],
        "provenance": {"relation": relation},
    }


def _write(tmp_path: Path, benchmarks: dict) -> Path:
    path = tmp_path / "institutions.yml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "benchmarks": benchmarks}))
    return path


def _fact(paper="2605.21858", institutions=("Tsinghua University", "Peking University")):
    return {
        "source_url": "https://openalex.org/W7162115175",
        "doi": f"10.48550/arxiv.{paper}",
        "retrieved_at": "2026-11-04",
        "institutions": list(institutions),
    }


def test_load_rejects_facts_that_do_not_belong_to_the_record(tmp_path):
    records = [_record("claire-radar:a"), _record("claire-radar:b", relation="aggregates")]
    assert load_benchmark_institutions(records, _write(tmp_path, {"claire-radar:a": _fact()}))
    bad = {
        "unknown key": {"claire-radar:zzz": _fact()},
        "not introducing": {"claire-radar:b": _fact()},
        "another paper": {"claire-radar:a": _fact(paper="2605.22034")},
        "not openalex": {"claire-radar:a": {**_fact(), "source_url": "https://example.org/W1"}},
        "no institutions": {"claire-radar:a": _fact(institutions=())},
        "repeated": {"claire-radar:a": _fact(institutions=("MIT", "MIT"))},
        "padded name": {"claire-radar:a": _fact(institutions=(" MIT",))},
        "bad date": {"claire-radar:a": {**_fact(), "retrieved_at": "Nov 4"}},
    }
    for case, benchmarks in bad.items():
        with pytest.raises(CatalogError):
            load_benchmark_institutions(records, _write(tmp_path, benchmarks))
            pytest.fail(case)


def test_apply_fills_exact_records_and_cites_the_openalex_work():
    records = [_record("claire-radar:a"), _record("claire-radar:b")]
    a, b = apply_benchmark_institutions(records, {"claire-radar:a": _fact()})
    assert a["institutions"] == ["Tsinghua University", "Peking University"]
    assert a["institutions_reference"] == {
        "source_key": "claire-radar:a",
        "basis": "openalex_linked_institutions",
        "source_url": "https://openalex.org/W7162115175",
        "doi": "10.48550/arxiv.2605.21858",
        "retrieved_at": "2026-11-04",
    }
    assert "institutions" not in b
    assert "publisher" not in a


def _authorship(*institutions, raw=()):
    return {
        "institutions": [{"id": f"I{name}", "display_name": name} for name in institutions],
        "raw_affiliation_strings": list(raw),
    }


def test_fetch_keeps_linked_names_in_first_appearance_order():
    work = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.48550/arxiv.2605.21858",
        "authorships": [
            _authorship("Peking University", raw=("School of CS, PKU",)),
            _authorship("Tsinghua University", "Peking University"),
            # A raw string OpenAlex did not link is never a name on its own.
            _authorship(raw=("Some Lab",)),
        ],
    }
    assert fetch.institutions(work) == ["Peking University", "Tsinghua University"]
    found = fetch.parse({"results": [work]}, ["2605.21858", "2605.22034"])
    assert found["2605.21858"] == {
        "work": "https://openalex.org/W1",
        "institutions": ["Peking University", "Tsinghua University"],
    }
    # A paper OpenAlex does not hold records nothing.
    assert found["2605.22034"] is None
    # Two works behind one DOI is not certainty.
    assert fetch.parse({"results": [work, {**work, "id": "W2"}]}, ["2605.21858"]) == {
        "2605.21858": None
    }


def test_committed_file_names_only_introducing_papers():
    payload = yaml.safe_load(DEFAULT_INSTITUTIONS_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    for key, fact in payload["benchmarks"].items():
        assert key.startswith(("claire-radar:", "model-reports:")), key
        assert fact["source_url"].startswith("https://openalex.org/W"), key
        assert fact["doi"].startswith("10.48550/arxiv."), key
        assert fact["institutions"], key
