"""Benchmark institutions from OpenAlex's record of the introducing paper (#933)."""

from __future__ import annotations

import json
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


def test_location_lookup_accepts_exactly_one_work(monkeypatch):
    # Issue #1081: OpenAlex merges an older arXiv preprint into the published
    # version's work, so the arXiv DOI finds nothing; the arXiv location
    # still finds the merged work.
    work = {
        "id": "https://openalex.org/W2",
        "doi": "https://doi.org/10.1016/j.example.2025.01.001",
        "authorships": [
            _authorship("MIT"),
            _authorship("MIT", "Stanford University"),
        ],
    }
    seen = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"results": [work]}).encode()

    def _urlopen(request, **kwargs):
        seen["url"] = request.full_url
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    payload = fetch.request_by_arxiv_location("2502.19187")
    assert "locations.landing_page_url" in seen["url"]
    assert "arxiv.org%2Fabs%2F2502.19187" in seen["url"]
    assert fetch.parse_location(payload, "2502.19187") == {
        "work": "https://openalex.org/W2",
        "institutions": ["MIT", "Stanford University"],
    }


def test_location_lookup_rejects_zero_or_two_works():
    # The same certainty rule as the DOI lookup: no work, or more than one,
    # records nothing.
    assert fetch.parse_location({"results": []}, "2502.19187") is None
    work = {"id": "https://openalex.org/W1", "authorships": [_authorship("MIT")]}
    assert fetch.parse_location({"results": [work, {**work, "id": "W2"}]}, "2502.19187") is None
    # A single work with no linked institution still records nothing.
    assert (
        fetch.parse_location({"results": [{"id": "W1", "authorships": []}]}, "2502.19187") is None
    )


def test_main_retries_doi_misses_by_arxiv_location(tmp_path, monkeypatch):
    # Issue #1081 end to end: the DOI pass resolves one paper and misses the
    # other; the location pass resolves the miss, and the output cites the
    # OpenAlex work for both.
    records_dir = tmp_path / "catalog"
    records_dir.mkdir()
    for name, key, paper in (
        ("model_reports_source_records.jsonl", "model-reports:bbeb", "2502.19187"),
        ("model_reports_source_records.jsonl", "model-reports:other", "2504.19314"),
        ("claire_radar_source_records.jsonl", "claire-radar:other", "2504.19314"),
    ):
        with (records_dir / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_record(key, papers=(paper,))) + "\n")

    def _doi_request(papers, **kwargs):
        assert papers == ["2502.19187", "2504.19314"]
        return {
            "results": [
                {
                    "id": "https://openalex.org/W9",
                    "doi": "https://doi.org/10.48550/arxiv.2504.19314",
                    "authorships": [_authorship("Tsinghua University")],
                }
            ]
        }

    def _location_request(paper, **kwargs):
        assert paper == "2502.19187"
        return {
            "results": [
                {
                    "id": "https://openalex.org/W2",
                    "doi": "https://doi.org/10.1016/j.example.2025.01.001",
                    "authorships": [_authorship("MIT")],
                }
            ]
        }

    monkeypatch.setattr(fetch, "request", _doi_request)
    monkeypatch.setattr(fetch, "request_by_arxiv_location", _location_request)
    output = tmp_path / "institutions.yml"
    checkpoint = tmp_path / "checkpoint.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "fetch_openalex_institutions.py",
            "--records-dir",
            str(records_dir),
            "--output",
            str(output),
            "--checkpoint",
            str(checkpoint),
            "--delay",
            "0",
        ],
    )

    fetch.main()

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert payload["benchmarks"]["model-reports:bbeb"] == {
        "source_url": "https://openalex.org/W2",
        "doi": "10.48550/arxiv.2502.19187",
        "retrieved_at": payload["benchmarks"]["model-reports:bbeb"]["retrieved_at"],
        "institutions": ["MIT"],
    }
    assert payload["benchmarks"]["model-reports:other"]["institutions"] == ["Tsinghua University"]
    assert not checkpoint.exists()


def test_committed_file_names_only_introducing_papers():
    payload = yaml.safe_load(DEFAULT_INSTITUTIONS_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    for key, fact in payload["benchmarks"].items():
        assert key.startswith(("claire-radar:", "model-reports:")), key
        assert fact["source_url"].startswith("https://openalex.org/W"), key
        assert fact["doi"].startswith("10.48550/arxiv."), key
        assert fact["institutions"], key
