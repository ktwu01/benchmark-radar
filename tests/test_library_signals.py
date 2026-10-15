"""benchmark-radar.com attention signals reach records by exact identity only."""

from __future__ import annotations

from benchmark_radar.app_seeds import _library_seed
from benchmark_radar.library_signals import assign_library_signals, stars_gained


def document(records):
    return {"schema_version": 1, "source": {"observed_on": "2026-10-14"}, "records": records}


def entry(stars, *, artifacts=(), llm_stats=(), history=()):
    return {
        "artifacts": list(artifacts),
        "llm_stats_ids": list(llm_stats),
        "github_stars": stars,
        "hf_paper_upvotes": None,
        "hf_dataset_downloads": None,
        "as_of": "2026-10-14",
        "github_stars_history": [list(point) for point in history],
    }


def test_thirty_day_gain_reads_the_sparse_history_and_refuses_to_guess():
    history = [["2026-08-19", 10], ["2026-09-10", 20], ["2026-10-01", 35]]
    # Value on 2026-09-14 is 20 (last change at or before it); on 2026-10-14, 35.
    assert stars_gained(history, "2026-10-14") == 15
    # History starting inside the window cannot say what the start value was.
    assert stars_gained([["2026-10-01", 35]], "2026-10-14") is None
    assert stars_gained([], "2026-10-14") is None


def test_signals_join_by_identity_and_skip_disagreeing_candidates():
    records = [
        {
            "key": "claire-radar:1",
            "source": "claire_radar",
            "source_metadata": {"claire_radar": {"id": "bm_a"}},
        },
        {"key": "opencompass:7", "source": "opencompass_hub", "artifacts": [{"id": "arxiv:1"}]},
        {"key": "opencompass:8", "source": "opencompass_hub", "artifacts": [{"id": "arxiv:2"}]},
    ]
    signals = assign_library_signals(
        records,
        document(
            {
                "bm_a": entry(5, history=[["2026-08-19", 1], ["2026-10-01", 5]]),
                # Two .com rows share arxiv:1 but track different repositories.
                "bm_b": entry(100, artifacts=["arxiv:1"]),
                "bm_c": entry(200, artifacts=["arxiv:1"]),
                "bm_d": entry(7, artifacts=["arxiv:2"]),
            }
        ),
    )
    assert signals["claire-radar:1"]["github_stars"] == 5
    assert signals["claire-radar:1"]["github_stars_30d"] == 4
    assert signals["claire-radar:1"]["join"] == "claire_record_id"
    assert "opencompass:7" not in signals
    assert signals["opencompass:8"]["join"] == "artifact:arxiv:2"


def test_seed_rows_carry_artifact_and_star_facts():
    taxonomy = {
        "groups": [{"id": "g", "name": "G"}],
        "categories": [{"id": "m", "group": "g", "name": "M"}],
    }
    record = {
        "slug": "a",
        "key": "k:a",
        "name": "A",
        "source": "claire_radar",
        "description": "",
        "released": "2026-10-01",
        "has_paper": True,
        "has_repo": True,
        "attention_signals": {"github_stars": 1275, "github_stars_30d": 676},
    }
    rows = _library_seed([record], taxonomy)['<div id="library-list" class="library-list"></div>']
    assert "Paper · Code · ★ 1,275 GitHub · +676 in 30 days" in rows
