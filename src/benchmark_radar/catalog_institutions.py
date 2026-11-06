"""Institutions behind a benchmark, from OpenAlex's record of its introducing paper.

Researchers ask who made a benchmark, and the author list alone often does not
say where it came from (#933). These facts list the institutions OpenAlex
links to the authorships of the record's own arXiv paper, in first-appearance
order. They are OpenAlex's linked institutions (``display_name``), never the
raw affiliation strings, so one institution reads the same on every card.
``publisher`` is a separate, cited fact and is left as it is.

The same eligibility as authors applies: a paper that only evaluates or
aggregates benchmarks names its own institutions, not a benchmark's makers.
``scripts/fetch_openalex_institutions.py`` writes the file this module reads.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .catalog import CatalogError
from .catalog_authors import introducing_arxiv_id

DEFAULT_INSTITUTIONS_PATH = Path("data/catalog/benchmark_institutions.yml")
OPENALEX_WORK = re.compile(r"^https://openalex\.org/W\d+$")


def arxiv_doi(paper: str) -> str:
    """The DOI arXiv registers for a paper, as OpenAlex stores it."""
    return f"10.48550/arxiv.{paper}"


def load_benchmark_institutions(
    records: list[dict[str, Any]], path: Path = DEFAULT_INSTITUTIONS_PATH
) -> dict[str, dict[str, Any]]:
    """Validate the institution facts against the current source-record population."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"{path}: cannot read benchmark institutions: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CatalogError(f"{path}: expected benchmark institutions schema_version 1")
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
            raise CatalogError(f"{path}: {key}: expected an institutions record")
        paper = introducing_arxiv_id(record)
        if paper is None:
            raise CatalogError(f"{path}: {key}: the record has no introducing arXiv paper")
        doi = str(fact.get("doi") or "")
        if doi != arxiv_doi(paper):
            raise CatalogError(f"{path}: {key}: doi must be the record's paper, {arxiv_doi(paper)}")
        source_url = str(fact.get("source_url") or "")
        if not OPENALEX_WORK.match(source_url):
            raise CatalogError(f"{path}: {key}: source_url must be an OpenAlex work URL")
        institutions = fact.get("institutions")
        if (
            not isinstance(institutions, list)
            or not institutions
            or not all(
                isinstance(name, str) and name.strip() == name and name for name in institutions
            )
            or len(set(institutions)) != len(institutions)
        ):
            raise CatalogError(
                f"{path}: {key}: institutions must be a non-empty list of distinct names"
            )
        retrieved = str(fact.get("retrieved_at") or "")
        try:
            valid = date.fromisoformat(retrieved).isoformat() == retrieved
        except ValueError:
            valid = False
        if not valid:
            raise CatalogError(f"{path}: {key}: retrieved_at must be an exact ISO date")
        validated[key] = {
            "institutions": list(institutions),
            "source_url": source_url,
            "doi": doi,
            "retrieved_at": retrieved,
        }
    return validated


def apply_benchmark_institutions(
    records: list[dict[str, Any]], facts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach institutions, with the OpenAlex work they were read from, to exact records."""
    enriched = []
    for record in records:
        fact = facts.get(record["key"])
        if not fact:
            enriched.append(record)
            continue
        enriched.append(
            {
                **record,
                "institutions": fact["institutions"],
                "institutions_reference": {
                    "source_key": record["key"],
                    "basis": "openalex_linked_institutions",
                    "source_url": fact["source_url"],
                    "doi": fact["doi"],
                    "retrieved_at": fact["retrieved_at"],
                },
            }
        )
    return enriched
