"""Institution ranking and the affiliation signal (affiliation-signal-v2, #1120).

This is triage by a disclosed signal, not a grade of any benchmark
(principle.md, "No quality judgement is not no judgement").

* **Institution ranking.** Each institution is counted once per distinct paper
  it appears on: the catalog's introducing papers
  (``data/catalog/benchmark_institutions.yml``) plus the release cohort's
  papers (``data/release_institutions.yml``). Only OpenAlex's linked names are
  counted, so one institution is one row; a paper's own HTML spelling
  ("Shanghai AI Lab") is shown on its card but never counted. Papers are keyed
  by arXiv id, so a benchmark present in both files counts once.
* **Affiliation signal.** An institution's weight is
  ``log1p(count) / log1p(max count)``. A release's affiliation is the highest
  weight among its first three institutions: a collaboration is not averaged
  down for listing a smaller partner. A paper OpenAlex has not indexed yet is
  scored on the printed names that exactly match a counted OpenAlex name
  ("Fudan University"), never on a near match ("Shanghai AI Lab"). A release
  with no known institution has an unknown affiliation, never zero by
  imputation.

#1098 introduced this module counting only "scored" records through field
names the catalog does not use, so every benchmark came out unknown; it now
reads the institution files directly.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .catalog_institutions import DEFAULT_INSTITUTIONS_PATH
from .paper_institutions import BASIS_OPENALEX, SHOWN_INSTITUTIONS, arxiv_id
from .release_signals import ReleaseSignals

METHOD_VERSION = "affiliation-signal-v2"
DEFAULT_RANKING_LIMIT = 25


def catalog_paper_institutions(path: Path = DEFAULT_INSTITUTIONS_PATH) -> dict[str, list[str]]:
    """``{arXiv id: OpenAlex institutions}`` from the catalog's institution facts."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    papers: dict[str, list[str]] = {}
    for fact in (payload.get("benchmarks") or {}).values():
        paper = arxiv_id(str((fact or {}).get("doi") or ""))
        names = (fact or {}).get("institutions") or []
        if paper and names:
            papers.setdefault(paper, [str(name) for name in names])
    return papers


def paper_institutions(
    signals: ReleaseSignals | None,
    catalog_path: Path = DEFAULT_INSTITUTIONS_PATH,
) -> dict[str, list[str]]:
    """Every paper's countable (OpenAlex) institutions, catalog first."""
    papers = catalog_paper_institutions(catalog_path)
    for paper, row in (signals.institutions if signals else {}).items():
        if row.get("basis") == BASIS_OPENALEX and row.get("institutions"):
            papers.setdefault(paper, [str(name) for name in row["institutions"]])
    return papers


def institution_counts(papers: dict[str, list[str]]) -> Counter[str]:
    """Distinct papers per institution."""
    counts: Counter[str] = Counter()
    for names in papers.values():
        counts.update(set(names))
    return counts


def institution_weights(counts: Counter[str]) -> dict[str, float]:
    """``log1p(count) / log1p(max)``, so the most frequent institution is 1.0."""
    if not counts:
        return {}
    top = math.log1p(max(counts.values()))
    return {name: math.log1p(count) / top for name, count in counts.items()}


def institution_ranking(
    counts: Counter[str], *, paper_count: int, limit: int = DEFAULT_RANKING_LIMIT
) -> dict[str, Any]:
    """The institutions behind the most benchmark papers, ties broken by name."""
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    entries, rank, previous = [], 0, None
    for position, (name, count) in enumerate(ordered[:limit], start=1):
        if count != previous:
            rank, previous = position, count
        entries.append({"rank": rank, "name": name, "benchmark_count": count})
    return {
        "method_version": METHOD_VERSION,
        "basis": "openalex_linked_institutions",
        "paper_count": paper_count,
        "institution_count": len(counts),
        "entries": entries,
    }


def affiliation_normalized(institutions: list[str], weights: dict[str, float]) -> float | None:
    """Highest weight among the first three institutions, or None if none is known."""
    known = [weights[name] for name in institutions[:SHOWN_INSTITUTIONS] if name in weights]
    return round(max(known), 4) if known else None
