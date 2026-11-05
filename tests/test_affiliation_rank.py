"""Release ranking beyond attention (#1120): institutions, affiliation, placeholders.

Fixtures are shaped like the real files: data/catalog/benchmark_institutions.yml
keys benchmarks by catalog key with an arXiv DOI, and data/release_institutions.yml
keys papers by arXiv id. #1098 counted records through score fields the catalog
does not use, so every benchmark came out unknown; these tests read the files.
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import yaml

from benchmark_radar.affiliation_rank import (
    affiliation_normalized,
    catalog_paper_institutions,
    institution_counts,
    institution_ranking,
    institution_weights,
    paper_institutions,
)
from benchmark_radar.release_leaderboard import AFFILIATION_WEIGHT, compute_window_ranking
from benchmark_radar.release_signals import (
    ReleaseSignals,
    is_placeholder_root,
    load_release_signals,
    needs_institution_refresh,
    write_release_institutions,
    write_release_repos,
)


def _catalog_file(tmp_path: Path) -> Path:
    path = tmp_path / "benchmark_institutions.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "benchmarks": {
                    "claire-radar:2605.00001": {
                        "doi": "10.48550/arxiv.2605.00001",
                        "institutions": ["Tsinghua University", "Peking University"],
                    },
                    "model-reports:x": {
                        "doi": "10.48550/arxiv.2605.00002",
                        "institutions": ["Tsinghua University"],
                    },
                    # The same paper under a second catalog key counts once.
                    "claire-radar:dup": {
                        "doi": "10.48550/arxiv.2605.00002",
                        "institutions": ["Tsinghua University"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_catalog_institutions_are_read_by_arxiv_id(tmp_path):
    papers = catalog_paper_institutions(_catalog_file(tmp_path))
    assert papers == {
        "2605.00001": ["Tsinghua University", "Peking University"],
        "2605.00002": ["Tsinghua University"],
    }


def test_only_openalex_names_are_counted(tmp_path):
    signals = ReleaseSignals(
        institutions={
            "2610.00001": {"basis": "openalex_linked_institutions", "institutions": ["MIT"]},
            # A paper's own spelling is shown, never counted.
            "2610.00002": {"basis": "arxiv_html_affiliations", "institutions": ["Shanghai AI Lab"]},
            # Already in the catalog: not counted twice.
            "2605.00002": {
                "basis": "openalex_linked_institutions",
                "institutions": ["Tsinghua University"],
            },
        }
    )
    papers = paper_institutions(signals, _catalog_file(tmp_path))
    counts = institution_counts(papers)
    assert counts == Counter({"Tsinghua University": 2, "Peking University": 1, "MIT": 1})
    ranking = institution_ranking(counts, paper_count=len(papers))
    assert ranking["paper_count"] == 3
    assert [(e["rank"], e["name"]) for e in ranking["entries"]] == [
        (1, "Tsinghua University"),
        (2, "MIT"),
        (2, "Peking University"),
    ]


def test_affiliation_is_the_best_known_of_the_first_three():
    weights = institution_weights(Counter({"A": 9, "B": 1}))
    assert weights["A"] == 1.0
    assert math.isclose(weights["B"], math.log1p(1) / math.log1p(9))
    # A collaboration is not averaged down by a smaller partner.
    assert affiliation_normalized(["B", "A"], weights) == 1.0
    # Only the first three count, the same three the card shows.
    assert affiliation_normalized(["X", "Y", "Z", "A"], weights) is None
    assert affiliation_normalized([], weights) is None


def _candidate(name, stars, *, affiliation=None, placeholder=False):
    candidate = {
        "canonical_artifact_id": f"artifact:arxiv:{name}",
        "name": name,
        "release_date": "2026-11-01T00:00:00+00:00",
        "has_dated_attention": True,
        "signals": {
            "github_stars": {
                "value": stars,
                "status": "fresh",
                "source_url": "https://github.com/a/b",
            }
        },
    }
    if affiliation is not None:
        candidate["affiliation"] = affiliation
    if placeholder:
        candidate["placeholder_repository"] = True
    return candidate


def test_v1_is_unchanged_without_an_affiliation_weight():
    ranking = compute_window_ranking([_candidate("a", 100)], window_days=30)
    entry = ranking["entries"][0]
    assert entry["score"] == 55
    assert entry["components"]["github_stars"]["weight"] == 0.55
    assert "affiliation" not in entry["components"]


def test_affiliation_adds_twenty_percent_and_unknown_adds_nothing():
    ranking = compute_window_ranking(
        [_candidate("known", 100, affiliation=1.0), _candidate("unknown", 100)],
        window_days=30,
        affiliation_weight=AFFILIATION_WEIGHT,
    )
    by_name = {entry["name"]: entry for entry in ranking["entries"]}
    assert by_name["known"]["score"] == 64  # 0.55 * 0.8 + 0.20
    assert by_name["unknown"]["score"] == 44  # not redistributed
    assert by_name["unknown"]["components"]["affiliation"]["status"] == "unknown"
    assert by_name["known"]["rank"] == 1
    # Stars alone still qualify: the threshold reads attention, not affiliation.
    assert by_name["unknown"]["status"] == "ranked"


def test_affiliation_alone_never_ranks_a_release():
    candidate = _candidate("quiet", None, affiliation=1.0)
    ranking = compute_window_ranking(
        [candidate], window_days=30, affiliation_weight=AFFILIATION_WEIGHT
    )
    assert ranking["entries"][0]["status"] == "limited_signals"
    assert ranking["entries"][0]["score"] is None


def test_placeholder_repository_is_listed_but_not_ranked():
    ranking = compute_window_ranking(
        [_candidate("empty", 5000, placeholder=True), _candidate("ships", 10)],
        window_days=30,
        affiliation_weight=AFFILIATION_WEIGHT,
    )
    by_name = {entry["name"]: entry for entry in ranking["entries"]}
    assert by_name["empty"]["status"] == "limited_signals"
    assert by_name["empty"]["limited_reason"] == "placeholder_repository"
    assert by_name["ships"]["rank"] == 1
    assert ranking["total_cohort_count"] == 2


def test_placeholder_root_detection():
    assert is_placeholder_root(["README.md", "LICENSE", ".gitignore", "assets", "teaser.png"])
    assert is_placeholder_root(["readme.md", "CITATION.cff", ".github", "figures"])
    assert not is_placeholder_root(["README.md", "data"])
    assert not is_placeholder_root(["README.md", "eval.py"])
    assert not is_placeholder_root(["README.md", "docs"])
    # An empty listing is a placeholder too: nothing shipped.
    assert is_placeholder_root([])


def test_signal_files_round_trip(tmp_path):
    institutions = tmp_path / "release_institutions.yml"
    repos = tmp_path / "release_repos.yml"
    write_release_institutions(
        institutions,
        {
            "2610.22131": {
                "basis": "arxiv_html_affiliations",
                "source_url": "https://arxiv.org/html/2610.22131",
                "retrieved_at": "2026-11-05",
                "institutions": ["Shanghai AI Lab"],
            }
        },
    )
    write_release_repos(
        repos,
        {"a/b": {"placeholder": True, "root": ["README.md"], "retrieved_at": "2026-11-05"}},
    )
    signals = load_release_signals(institutions, repos)
    assert signals.paper("2610.22131")["institutions"] == ["Shanghai AI Lab"]
    assert signals.is_placeholder("https://github.com/A/B")
    assert not signals.is_placeholder("https://github.com/c/d")
    assert load_release_signals(tmp_path / "none.yml", tmp_path / "none2.yml") == ReleaseSignals()


def test_papers_are_retried_until_openalex_has_them():
    from datetime import date

    today = date(2026, 11, 5)
    assert needs_institution_refresh(None, today)
    assert not needs_institution_refresh(
        {"basis": "openalex_linked_institutions", "retrieved_at": "2026-01-01"}, today
    )
    assert not needs_institution_refresh(
        {"basis": "arxiv_html_affiliations", "retrieved_at": "2026-11-04"}, today
    )
    assert needs_institution_refresh({"basis": None, "retrieved_at": "2026-11-01"}, today)


def test_committed_release_signals_load():
    signals = load_release_signals()
    for paper, row in signals.institutions.items():
        for name in row["institutions"]:
            assert any(ch.isalpha() for ch in name), (paper, name)


def test_affiliation_counts_as_an_observed_signal_for_confidence():
    # Stars (44%) plus a known affiliation (20%) are two observed signals
    # covering 64% of the score: "Medium", not "Low".
    ranking = compute_window_ranking(
        [_candidate("known", 100, affiliation=0.5)],
        window_days=30,
        affiliation_weight=AFFILIATION_WEIGHT,
    )
    entry = ranking["entries"][0]
    assert entry["coverage"] == 0.64
    assert entry["confidence"] == "Medium"
