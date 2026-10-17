"""Library research directions reach records only through exact identity."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from benchmark_radar.library_directions import (
    LibraryDirectionError,
    assign_library_directions,
    load_direction_reviews,
    load_library_directions,
)

ROOT = Path(__file__).resolve().parents[1]

TAXONOMY = {
    "version": "taxonomy-v5",
    "groups": [{"id": "g", "name": "Group"}],
    "categories": [
        {"id": "math", "group": "g", "name": "Math", "description": ""},
        {"id": "science", "group": "g", "name": "Science", "description": ""},
    ],
}


def document(records: dict) -> dict:
    return {"schema_version": 1, "source": {}, "taxonomy": TAXONOMY, "records": records}


def assignment(primary: str, *, artifacts=(), llm_stats=()) -> dict:
    return {
        "primary": primary,
        "categories": [primary],
        "basis": "model-review",
        "artifacts": list(artifacts),
        "llm_stats_ids": list(llm_stats),
    }


def test_each_exact_join_carries_its_basis():
    records = [
        {
            "key": "claire-radar:1",
            "source": "claire_radar",
            "source_metadata": {"claire_radar": {"id": "bm_a"}},
        },
        {"key": "llm-stats:aime", "source": "llm_stats"},
        {
            "key": "opencompass:7",
            "source": "opencompass_hub",
            "artifacts": [{"id": "arxiv:2401.00001"}],
        },
        {
            "key": "model-reports:x",
            "source": "model_reports",
            "artifacts": [{"url": "https://arxiv.org/abs/2401.00002"}],
        },
    ]
    directions = assign_library_directions(
        records,
        document(
            {
                "bm_a": assignment("science"),
                "cat_aime": assignment("math", llm_stats=["aime"]),
                "bm_b": assignment("math", artifacts=["arxiv:2401.00001"]),
                "bm_c": assignment("science", artifacts=["arxiv:2401.00002"]),
            }
        ),
    )

    assert directions["claire-radar:1"]["join"] == "claire_record_id"
    assert directions["llm-stats:aime"] == {
        "primary": "math",
        "categories": ["math"],
        "basis": "model-review",
        "join": "llm_stats_id",
        "source_record": "cat_aime",
    }
    assert directions["opencompass:7"]["join"] == "artifact:arxiv:2401.00001"
    # A curated record carries only a URL; the same exact identifier is derived.
    assert directions["model-reports:x"]["primary"] == "science"


def test_disagreeing_candidates_and_names_never_produce_a_direction():
    records = [
        {
            "key": "opencompass:1",
            "source": "opencompass_hub",
            "name": "MathBench",
            "artifacts": [{"id": "gh:o/r"}],
        },
        {"key": "opencompass:2", "source": "opencompass_hub", "name": "Same Name Bench"},
    ]
    directions = assign_library_directions(
        records,
        document(
            {
                "bm_1": assignment("math", artifacts=["gh:o/r"]),
                "bm_2": assignment("science", artifacts=["gh:o/r"]),
            }
        ),
    )
    assert directions == {}


def test_reviewed_identity_groups_share_one_agreed_direction():
    records = [
        {"key": "llm-stats:mmlu", "source": "llm_stats"},
        {"key": "opencompass:9", "source": "opencompass_hub"},
    ]
    directions = assign_library_directions(
        records,
        document({"cat_mmlu": assignment("math", llm_stats=["mmlu"])}),
        [{"group_id": "mmlu", "members": ["llm-stats:mmlu", "opencompass:9"]}],
    )
    assert directions["opencompass:9"]["join"] == "identity_group:mmlu"


def test_reviews_fill_gaps_but_never_override_an_exact_join():
    records = [
        {"key": "llm-stats:aime", "source": "llm_stats"},
        {"key": "model-reports:aime", "source": "model_reports"},
    ]
    reviews = {
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-10-15",
        "directions": {"llm-stats:aime": "science", "model-reports:aime": "math"},
    }
    directions = assign_library_directions(
        records, document({"cat": assignment("math", llm_stats=["aime"])}), reviews=reviews
    )
    assert directions["llm-stats:aime"]["join"] == "llm_stats_id"
    assert directions["model-reports:aime"]["join"] == "review:reviewer:2026-10-15"
    assert directions["model-reports:aime"]["basis"] == "reviewer_asserted"


@pytest.mark.parametrize(
    ("key", "primary"), [("model-reports:gone", "math"), ("model-reports:aime", "not-a-direction")]
)
def test_a_stale_review_fails_loudly(key, primary):
    records = [{"key": "model-reports:aime", "source": "model_reports"}]
    reviews = {"reviewed_by": "r", "reviewed_at": "2026-10-15", "directions": {key: primary}}
    with pytest.raises(LibraryDirectionError):
        assign_library_directions(records, document({}), reviews=reviews)


def test_committed_inputs_load_and_reference_the_taxonomy():
    exported = load_library_directions()
    reviews = load_direction_reviews()
    assert exported is not None and reviews is not None
    assert exported["source"]["commit"] == "522482b200274cf0b6d656df9fc4cd061f5fac23"
    assert len(exported["taxonomy"]["categories"]) == 36
    categories = {category["id"] for category in exported["taxonomy"]["categories"]}
    assert set(reviews["directions"].values()) <= categories


def test_export_keeps_only_assigned_records_with_their_exact_anchors():
    path = ROOT / "scripts" / "export_claire_library_categories.py"
    spec = importlib.util.spec_from_file_location("export_claire_library_categories", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    library = {
        "records": [
            {
                "id": "bm_a",
                "categoryAssignment": {"primary": "math", "basis": "model-review"},
                "libraryCategories": ["science"],
                "links": {"report": "https://arxiv.org/abs/2401.00001"},
                "catalogSources": [{"catalog": "llm-stats", "sourceId": "aime"}],
            },
            {"id": "bm_b", "categoryAssignment": {"primary": None, "basis": "unclassified"}},
        ]
    }

    exported = module.export_categories(
        library, TAXONOMY, repository="r", commit="c", library_sha256="s"
    )

    assert list(exported["records"]) == ["bm_a"]
    assert exported["records"]["bm_a"] == {
        "primary": "math",
        "categories": ["math", "science"],
        "basis": "model-review",
        "artifacts": ["arxiv:2401.00001"],
        "llm_stats_ids": ["aime"],
    }
    json.dumps(exported)


def test_candidates_agreeing_on_primary_keep_only_shared_secondaries():
    # Two .com rows for one paper agree on the primary but list different
    # secondaries; copying either row's list would assert one the other lacks.
    records = [
        {"key": "model-reports:x", "source": "model_reports", "artifacts": [{"id": "arxiv:1"}]}
    ]
    first = assignment("math", artifacts=["arxiv:1"])
    first["categories"] = ["math", "science"]
    second = assignment("math", artifacts=["arxiv:1"])
    directions = assign_library_directions(records, document({"bm_a": first, "bm_b": second}))
    assert directions["model-reports:x"]["categories"] == ["math"]
    assert directions["model-reports:x"]["source_record"] == "bm_a"


def test_mixed_case_artifact_ids_are_canonicalized_before_joining():
    # OpenCompass keeps repository casing in stored ids; the export's anchors
    # are artifact_identifier's lowercase form.
    records = [
        {
            "key": "opencompass:1125",
            "source": "opencompass_hub",
            "artifacts": [
                {
                    "id": "gh:OSU-NLP-Group/Mind2Web",
                    "url": "https://github.com/OSU-NLP-Group/Mind2Web",
                }
            ],
        }
    ]
    directions = assign_library_directions(
        records, document({"bm": assignment("math", artifacts=["gh:osu-nlp-group/mind2web"])})
    )
    assert directions["opencompass:1125"]["join"] == "artifact:gh:osu-nlp-group/mind2web"
