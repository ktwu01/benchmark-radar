"""Benchmark authors read from the arXiv paper that introduces each benchmark.

Researchers most want to know who made a benchmark, and no catalog crawl
records it (#933). These facts fill exact source records from the arXiv
metadata of the record's own paper. They never join records by name, and a
paper that only evaluates or aggregates benchmarks names its own authors, not
a benchmark's creators, so such records stay without authors.

``scripts/fetch_arxiv_authors.py`` writes the reviewed file this module reads.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .catalog import CatalogError

DEFAULT_AUTHORS_PATH = Path("data/catalog/benchmark_authors.yml")
ARXIV_ABS = re.compile(r"^https://arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?$")

# Model-report registry entries link the benchmark's own paper. A Claire Radar
# paper is the benchmark's only when the corpus says it introduces it.
INTRODUCING_SOURCES = frozenset({"model_reports"})
INTRODUCING_RELATIONS = frozenset({"introduces"})


def introducing_arxiv_id(record: dict[str, Any]) -> str | None:
    """Return the arXiv id of the paper that introduces ``record``, if certain.

    Certain means exactly one arXiv paper among the record's artifacts, and a
    source that says this paper introduces the benchmark.
    """
    papers = {
        match.group(1)
        for artifact in record.get("artifacts") or []
        if artifact.get("kind") == "paper"
        for match in [ARXIV_ABS.match(str(artifact.get("url") or ""))]
        if match
    }
    if len(papers) != 1:
        return None
    relation = (record.get("provenance") or {}).get("relation")
    if record.get("source") in INTRODUCING_SOURCES or relation in INTRODUCING_RELATIONS:
        return next(iter(papers))
    return None


def load_benchmark_authors(
    records: list[dict[str, Any]], path: Path = DEFAULT_AUTHORS_PATH
) -> dict[str, dict[str, Any]]:
    """Validate the author facts against the current source-record population."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"{path}: cannot read benchmark authors: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CatalogError(f"{path}: expected benchmark authors schema_version 1")
    facts = payload.get("benchmarks")
    if not isinstance(facts, dict):
        raise CatalogError(f"{path}: benchmarks must be a mapping")
    by_key = {row["key"]: row for row in records}
    validated = {}
    for key, fact in facts.items():
        record = by_key.get(key)
        if record is None:
            raise CatalogError(f"{path}: unknown benchmark key {key!r}")
        if not isinstance(fact, dict):
            raise CatalogError(f"{path}: {key}: expected an authors record")
        paper = introducing_arxiv_id(record)
        if paper is None:
            raise CatalogError(f"{path}: {key}: the record has no introducing arXiv paper")
        source_url = str(fact.get("source_url") or "")
        match = ARXIV_ABS.match(source_url)
        if not match or match.group(1) != paper:
            raise CatalogError(f"{path}: {key}: source_url must be the record's paper, {paper}")
        authors = fact.get("authors")
        if (
            not isinstance(authors, list)
            or not authors
            or not all(isinstance(name, str) and name.strip() == name and name for name in authors)
        ):
            raise CatalogError(f"{path}: {key}: authors must be a non-empty list of names")
        retrieved = str(fact.get("retrieved_at") or "")
        try:
            valid = date.fromisoformat(retrieved).isoformat() == retrieved
        except ValueError:
            valid = False
        if not valid:
            raise CatalogError(f"{path}: {key}: retrieved_at must be an exact ISO date")
        validated[key] = {
            "authors": list(authors),
            "source_url": source_url,
            "retrieved_at": retrieved,
        }
    return validated


def apply_benchmark_authors(
    records: list[dict[str, Any]], facts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach authors, with the paper they were read from, to exact records."""
    enriched = []
    for record in records:
        fact = facts.get(record["key"])
        if not fact:
            enriched.append(record)
            continue
        enriched.append(
            {
                **record,
                "authors": fact["authors"],
                "authors_reference": {
                    "source_key": record["key"],
                    "basis": "arxiv_metadata",
                    "source_url": fact["source_url"],
                    "retrieved_at": fact["retrieved_at"],
                },
            }
        )
    return enriched
