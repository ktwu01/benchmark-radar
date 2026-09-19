"""The review build must not turn missing measurements into missing records."""

import json
import runpy
from pathlib import Path

import pytest


def test_study_preserves_unknowns_zero_scores_and_source_ids(tmp_path):
    build = runpy.run_path(str(Path(__file__).parents[1] / "ui-study/scripts/catalog.py"))[
        "build_explorer_catalog"
    ]
    shards = tmp_path / "data/benchmarks"
    shards.mkdir(parents=True)
    entries = []
    for source in ("model_reports", "opencompass_hub", "artificial_analysis", "llm_stats"):
        entry = {
            "key": f"{source}:same-name",
            "slug": source,
            "name": "Same name",
            "source": source,
            "evidence_summary": {"model_count": None},
        }
        entries.append(entry)
        (shards / f"{source}.json").write_text(
            json.dumps(
                {
                    "record": {"documents": []},
                    "scores_by_source": {
                        source: {
                            "rows": [
                                {
                                    "value": 0,
                                    "model_id": "model",
                                    "reported_date": None,
                                    "date_precision": "model_announcement",
                                    "protocol": {"tools": True},
                                    "source_url": "https://example.org/evidence",
                                }
                            ]
                        }
                    },
                }
            )
        )
    (tmp_path / "data/benchmark-index.json").write_text(json.dumps({"benchmarks": entries}))
    output = tmp_path / "result.json"
    build(tmp_path, output)
    rows = json.loads(output.read_text())
    assert [row["id"] for row in rows] == [entry["key"] for entry in entries]
    assert all(row["models"] is None and row["raw"] is None for row in rows)
    assert all(row["history"][0][1] == 0 for row in rows)
    assert all(row["history"][0][0] is None for row in rows)
    assert all(json.loads(row["history"][0][3]) == {"tools": True} for row in rows)
    # Missing shards used to be easy to overlook when copying a hosted snapshot.
    (shards / "llm_stats.json").unlink()
    with pytest.raises(FileNotFoundError):
        build(tmp_path, output)
