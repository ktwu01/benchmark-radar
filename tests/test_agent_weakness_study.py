from __future__ import annotations

import copy
import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from benchmark_radar.query import QueryPaths, QueryService

SCRIPT_PATH = Path("scripts/analyze_agent_weaknesses.py")
DATA_PATH = Path("data/agent_weakness_evidence.yml")
GUIDE_PATH = Path("docs/technical-report/agent-weakness-coding-guide.md")
REVIEW_REPORT_PATH = Path("docs/technical-report/agent-weakness-independent-review.md")
BLIND_PACKET_PATH = Path("docs/technical-report/agent-weakness-blinded-sample.md")
BENCHMARK_INDEX_PATH = Path("site/data/benchmark-index.json")
BENCHMARK_SHARDS_PATH = Path("site/data/benchmarks")
REPORT_README_PATH = Path("docs/technical-report/README.md")

FINE_CODES = [
    "goal_plan_drift",
    "tool_selection_execution",
    "environment_grounding_state_tracking",
    "loop_stagnation_recovery",
    "verification_completion",
]

EXPECTED_SECONDARY_REVIEW = {
    "A": {
        "row_id": "osworld2_hidden_state",
        "primary_code": "environment_grounding_state_tracking",
        "secondary_code": "environment_grounding_state_tracking",
        "secondary_note": (
            "The evidence explicitly says agents lose track of constraints, miss "
            "information that arrives mid-task, and struggle with hidden-state "
            "recovery. That points most directly to failures to stay grounded in "
            "evolving environment state rather than a purely local execution mistake."
        ),
    },
    "B": {
        "row_id": "swe_science_misguided_exploration",
        "primary_code": "tool_selection_execution",
        "secondary_code": "tool_selection_execution",
        "secondary_note": (
            "The excerpt names misguided exploration and surface-level repair as "
            "recurring failure mechanisms. That fits agents choosing unproductive "
            "actions or incomplete repair operations rather than executing the "
            "needed scientific software fix cleanly."
        ),
    },
    "C": {
        "row_id": "researchclawbench_protocol_drift",
        "primary_code": "goal_plan_drift",
        "secondary_code": "goal_plan_drift",
        "secondary_note": (
            "The error analysis centers on protocol mismatch, evidence mismatch, "
            "and missing the scientific core. Those are strongest as departures "
            "from the target scientific objective and intended methodology, not "
            "just isolated tool-use errors."
        ),
    },
    "D": {
        "row_id": "scicode_instrument_gap",
        "primary_code": "verification_completion",
        "secondary_code": "verification_completion",
        "secondary_note": (
            "The audit shows the evaluation instrument rejected correct "
            "instruction-following solutions because benchmark defects "
            "contaminated the completion check. This makes the apparent failure "
            "signal unusable as a clean estimate because the required end state "
            "was not being verified reliably."
        ),
    },
}


def _load_module():
    assert SCRIPT_PATH.exists(), f"missing analysis script: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("agent_weakness_analysis", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    row_id: str,
    *,
    status: str,
    primary_code: str,
    benchmark_family_id: str = "family-a",
    benchmark_family_name: str = "Family A",
    radar_query: str = "Family A",
    radar_record_id: str | None = "family-a",
    source_url: str = "https://example.com/paper",
    source_kind: str = "paper",
    evidence_location: str = "Table 1; paragraph p1.1",
    published_date: str = "2026-08-01",
    observed_evidence: str | None = None,
    sampled: bool = False,
    secondary_code: str | None = None,
    secondary_note: str | None = None,
) -> dict:
    if secondary_note is None and secondary_code is not None:
        secondary_note = "Synthetic review rationale."
    return {
        "id": row_id,
        "benchmark_family_id": benchmark_family_id,
        "benchmark_family_name": benchmark_family_name,
        "radar_query": radar_query,
        "radar_record_id": radar_record_id,
        "task_or_protocol": "Representative task family",
        "status": status,
        "primary_code": primary_code,
        "authoritative_source_kind": source_kind,
        "source_url": source_url,
        "evidence_location": evidence_location,
        "published_date": published_date,
        "observed_evidence": observed_evidence
        or f"Observed evidence for {primary_code} in {benchmark_family_name}.",
        "limitations": "Single benchmark family; not a field-wide estimate.",
        "plausible_counter_reading": (
            "This could partly reflect harness setup rather than pure model weakness."
        ),
        "counterexample": "The same source reports a stronger sub-capability on a narrower slice.",
        "counterexample_location": "Section 5",
        "review": {
            "sampled_for_secondary_review": sampled,
            "secondary_code": secondary_code,
            "secondary_note": secondary_note,
        },
    }


def _study_payload(
    rows: list[dict],
    *,
    demonstrated_family_scope: list[str] | None = None,
    excluded_families: list[str] | None = None,
    measurement_counterexample_only: list[str] | None = None,
) -> dict:
    demonstrated_scope = demonstrated_family_scope
    if demonstrated_scope is None:
        demonstrated_scope = sorted(
            {row["benchmark_family_name"] for row in rows if row["status"] == "demonstrated"}
        )
    return {
        "schema_version": 1,
        "study": {
            "issue": 455,
            "snapshot_date": "2026-09-01",
            "repository_commit_input": "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae",
            "evidence_cutoff": "2026-09-01",
            "preregistration_url": "https://github.com/ktwu01/benchmark-radar/issues/455#issuecomment-5492496440",
            "statuses": ["demonstrated", "design_implied", "unmeasured"],
            "fine_taxonomy": FINE_CODES,
            "coarse_grouping": {
                "decision_execution": [
                    "goal_plan_drift",
                    "tool_selection_execution",
                ],
                "state_control": [
                    "environment_grounding_state_tracking",
                    "loop_stagnation_recovery",
                    "verification_completion",
                ],
            },
            "demonstrated_family_scope": demonstrated_scope,
            "excluded_families": excluded_families or ["General AgentBench", "ToolFailBench"],
            "measurement_counterexample_only": (
                measurement_counterexample_only
                if measurement_counterexample_only is not None
                else [
                    row["benchmark_family_name"] for row in rows if row["status"] == "unmeasured"
                ][:1]
            ),
        },
        "rows": rows,
    }


def _write_study(tmp_path: Path, rows: list[dict], **kwargs) -> Path:
    path = tmp_path / "study.yml"
    path.write_text(
        yaml.safe_dump(_study_payload(rows, **kwargs), sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_repository_task1_artifacts_exist_and_load():
    assert GUIDE_PATH.exists(), f"missing coding guide: {GUIDE_PATH}"
    assert DATA_PATH.exists(), f"missing evidence table: {DATA_PATH}"
    module = _load_module()

    study = module.load_study(DATA_PATH)
    analysis = module.analyze_study(study)

    assert analysis["snapshot_date"] == "2026-09-01"
    assert analysis["repository_commit_input"] == "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae"
    assert analysis["status_counts"]["demonstrated"] >= 1
    assert analysis["status_counts"]["design_implied"] >= 1
    assert analysis["status_counts"]["unmeasured"] >= 1
    agreement = analysis["agreement"]
    assert agreement["sampled_row_count"] >= 1
    assert (
        agreement["completed_row_count"] + agreement["pending_row_count"]
        == agreement["sampled_row_count"]
    )
    if agreement["completed_row_count"] == 0:
        assert agreement["percent_agreement"] is None
        assert agreement["cohens_kappa"] is None
    else:
        assert 0.0 <= agreement["percent_agreement"] <= 1.0
        if agreement["percent_agreement"] == pytest.approx(1.0):
            assert agreement["cohens_kappa"] in (None, pytest.approx(1.0))
        else:
            assert agreement["cohens_kappa"] is not None


def test_repository_task2_secondary_review_is_complete():
    assert REVIEW_REPORT_PATH.exists(), f"missing independent review report: {REVIEW_REPORT_PATH}"
    assert BLIND_PACKET_PATH.exists(), f"missing blind packet: {BLIND_PACKET_PATH}"
    module = _load_module()

    study = module.load_study(DATA_PATH)
    analysis = module.analyze_study(study)
    sampled_rows = [row for row in study["rows"] if row["review"]["sampled_for_secondary_review"]]

    assert [row["id"] for row in sampled_rows] == [
        EXPECTED_SECONDARY_REVIEW["A"]["row_id"],
        EXPECTED_SECONDARY_REVIEW["B"]["row_id"],
        EXPECTED_SECONDARY_REVIEW["C"]["row_id"],
        EXPECTED_SECONDARY_REVIEW["D"]["row_id"],
    ]
    assert [
        {
            "id": row["id"],
            "primary_code": row["primary_code"],
            "secondary_code": row["review"]["secondary_code"],
            "secondary_note": row["review"]["secondary_note"],
        }
        for row in sampled_rows
    ] == [
        {
            "id": expected["row_id"],
            "primary_code": expected["primary_code"],
            "secondary_code": expected["secondary_code"],
            "secondary_note": expected["secondary_note"],
        }
        for expected in EXPECTED_SECONDARY_REVIEW.values()
    ]

    agreement = analysis["agreement"]
    assert agreement["sampled_row_count"] == 4
    assert agreement["completed_row_count"] == 4
    assert agreement["pending_row_count"] == 0
    assert agreement["pending_row_ids"] == []
    assert agreement["percent_agreement"] == pytest.approx(1.0)
    assert agreement["cohens_kappa"] == pytest.approx(1.0)
    assert agreement["disagreements"] == []


def test_repository_task2_report_records_blind_review_and_adjudication_state():
    assert REVIEW_REPORT_PATH.exists(), f"missing independent review report: {REVIEW_REPORT_PATH}"
    assert BLIND_PACKET_PATH.exists(), f"missing blind packet: {BLIND_PACKET_PATH}"
    module = _load_module()

    study = module.load_study(DATA_PATH)
    analysis = module.analyze_study(study)
    report_text = REVIEW_REPORT_PATH.read_text(encoding="utf-8")
    blind_packet_text = BLIND_PACKET_PATH.read_text(encoding="utf-8")
    report_lines = [line.strip() for line in report_text.splitlines() if line.strip()]

    assert "independent Codex analyst" in report_text
    assert "blinded" in report_text
    assert report_lines[:4] == [
        "# Agent Weakness Independent Review",
        "Date: 2026-09-01",
        "## Result",
        "The replacement independent review matched the primary coding on all 4 of 4 sampled rows.",
    ]
    assert "earlier independent pass was discarded before use" in report_text
    assert "sample-local" in report_text
    assert "predeclared four-row sample only" in report_text
    assert "## Neutral blind procedure" in report_text
    assert "## Post-hoc mapping and raw assignments" in report_text
    assert "## Disagreement and adjudication log" in report_text
    assert str(BLIND_PACKET_PATH) in report_text
    assert ".superpowers/" not in report_text
    assert ".superpowers/" not in blind_packet_text
    assert "## Sample `A`" in blind_packet_text
    assert "## Sample `B`" in blind_packet_text
    assert "## Sample `C`" in blind_packet_text
    assert "## Sample `D`" in blind_packet_text
    assert "## Row `" not in blind_packet_text
    assert "row_id:" not in blind_packet_text
    assert "sample_id: <A, B, C, or D>" in blind_packet_text

    sampled_rows = [row for row in study["rows"] if row["review"]["sampled_for_secondary_review"]]
    for sample_id, expected in EXPECTED_SECONDARY_REVIEW.items():
        row = next(row for row in sampled_rows if row["id"] == expected["row_id"])
        assert f"| `{sample_id}` | `{row['id']}` |" in report_text
        assert f"| `{sample_id}` | `{row['id']}` | `{row['primary_code']}` |" in report_text
        assert expected["secondary_note"] in report_text
        assert row["primary_code"] in report_text
        assert row["review"]["secondary_code"] in report_text
        assert row["review"]["secondary_note"] in report_text
        assert row["observed_evidence"] in blind_packet_text
        assert row["evidence_location"] in blind_packet_text
        assert row["limitations"] in blind_packet_text
        assert row["plausible_counter_reading"] in blind_packet_text
        assert row["primary_code"] not in blind_packet_text
        assert row["id"] not in "\n".join(
            line for line in blind_packet_text.splitlines() if line.startswith("## ")
        )

    disagreements = analysis["agreement"]["disagreements"]
    if disagreements:
        for disagreement in disagreements:
            assert disagreement["id"] in report_text
            assert disagreement["primary_code"] in report_text
            assert disagreement["secondary_code"] in report_text
    else:
        assert "No disagreements required adjudication." in report_text


def test_repository_non_null_radar_record_ids_match_catalog_keys_when_generated():
    if not BENCHMARK_INDEX_PATH.exists():
        pytest.skip("requires generated site/data/benchmark-index.json from normalize-external")
    if not BENCHMARK_SHARDS_PATH.exists():
        pytest.skip("requires generated site/data/benchmarks shards from normalize-external")

    module = _load_module()
    study = module.load_study(DATA_PATH)
    index_payload = json.loads(BENCHMARK_INDEX_PATH.read_text(encoding="utf-8"))
    exact_name_keys: dict[str, list[str]] = {}
    for record in index_payload["benchmarks"]:
        exact_name_keys.setdefault(str(record["name"]).strip().casefold(), []).append(record["key"])
    service = QueryService(
        QueryPaths(
            index=BENCHMARK_INDEX_PATH,
            shards=BENCHMARK_SHARDS_PATH,
            snapshots=Path("data/snapshots"),
        )
    )
    expected_ids = {
        "OSWorld 2.0": "llm-stats:osworld-2.0",
        "WebArena": "llm-stats:webarena-verified",
        "Mind2Web": "opencompass:1125",
        "GAIA2": "llm-stats:gaia2",
        "ResearchClawBench": "llm-stats:researchclawbench",
        "SWE-bench Verified": "llm-stats:swe-bench-verified",
        "SciCode": "llm-stats:scicode",
    }

    non_null_rows = [row for row in study["rows"] if row["radar_record_id"] is not None]
    null_rows = [row for row in study["rows"] if row["radar_record_id"] is None]
    assert non_null_rows
    assert null_rows
    for row in non_null_rows:
        expected_identifier = expected_ids.get(row["benchmark_family_name"], row["radar_record_id"])
        assert row["radar_record_id"] == expected_identifier
        result = service.show(row["radar_record_id"])
        assert result["identifier"] == row["radar_record_id"]
        assert result["benchmark"]["record"]["key"] == row["radar_record_id"]
    for row in null_rows:
        assert exact_name_keys.get(row["benchmark_family_name"].casefold(), []) == []


def test_demonstrated_null_radar_id_requires_a_searchable_query(tmp_path):
    module = _load_module()
    index = tmp_path / "benchmark-index.json"
    index.write_text(json.dumps({"benchmarks": [{"name": "Known benchmark", "key": "known"}]}))
    module.DEFAULT_BENCHMARK_INDEX = index
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            radar_record_id=None,
            radar_query="Unknown benchmark",
        ),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]
    with pytest.raises(ValueError, match="no Radar search result"):
        module.load_study(_write_study(tmp_path, rows, measurement_counterexample_only=[]))


def test_load_study_rejects_missing_evidence_location(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            evidence_location="",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="evidence_location"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_section_only_evidence_location_for_demonstrated_row(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            evidence_location="Section 4",
        ),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="replayable|evidence_location"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_demonstrated_row_without_authoritative_source(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            source_url="",
            source_kind="paper",
        ),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="authoritative source"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_secondary_code_on_unsampled_row(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=False,
            secondary_code="tool_selection_execution",
        ),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="secondary_code|sampled_for_secondary_review"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_completed_secondary_code_without_a_rationale(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=True,
            secondary_code="goal_plan_drift",
            secondary_note="",
        ),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="secondary_note"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_requires_declared_counterexamples_to_have_unmeasured_rows(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-b",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="require unmeasured rows"):
        module.load_study(
            _write_study(tmp_path, rows, measurement_counterexample_only=["Family B"])
        )


@pytest.mark.parametrize("status", ["demonstrated", "design_implied", "unmeasured"])
def test_load_study_rejects_rows_without_authoritative_source_url(tmp_path, status):
    module = _load_module()
    rows = [
        _row(
            "target-row",
            status=status,
            primary_code="goal_plan_drift",
            source_url="",
        ),
        _row(
            "other-design",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "other-unmeasured",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]
    if status == "design_implied":
        rows[1] = _row(
            "other-demonstrated",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        )
    if status == "unmeasured":
        rows[2] = _row(
            "other-demonstrated",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        )

    with pytest.raises(ValueError, match="authoritative source URL"):
        module.load_study(_write_study(tmp_path, rows))


@pytest.mark.parametrize("status", ["demonstrated", "design_implied", "unmeasured"])
def test_load_study_rejects_non_http_authoritative_source_url_for_all_statuses(tmp_path, status):
    module = _load_module()
    rows = [
        _row(
            "target-row",
            status=status,
            primary_code="goal_plan_drift",
            source_url="doi:10.1234/example",
        ),
        _row(
            "demo-support",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "design-support",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
        _row(
            "unmeasured-support",
            status="unmeasured",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
        ),
    ]
    support_ids_by_status = {
        "demonstrated": {"demo-support"},
        "design_implied": {"design-support"},
        "unmeasured": {"unmeasured-support"},
    }
    rows = [row for row in rows if row["id"] not in support_ids_by_status[status]]

    with pytest.raises(ValueError, match="HTTP|http"):
        module.load_study(_write_study(tmp_path, rows))


@pytest.mark.parametrize("status", ["demonstrated", "design_implied", "unmeasured"])
def test_load_study_rejects_section_only_evidence_location_for_all_statuses(tmp_path, status):
    module = _load_module()
    rows = [
        _row(
            "target-row",
            status=status,
            primary_code="goal_plan_drift",
            evidence_location="Section 4",
        ),
        _row(
            "demo-support",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "design-support",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
        _row(
            "unmeasured-support",
            status="unmeasured",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
        ),
    ]
    support_ids_by_status = {
        "demonstrated": {"demo-support"},
        "design_implied": {"design-support"},
        "unmeasured": {"unmeasured-support"},
    }
    rows = [row for row in rows if row["id"] not in support_ids_by_status[status]]

    with pytest.raises(ValueError, match="replayable|evidence_location"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_requires_all_three_statuses_and_benchmark_family_ids(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
    ]

    with pytest.raises(ValueError, match="benchmark_family_id|statuses"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_coarse_grouping_that_omits_a_fine_taxonomy_code(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]
    payload = _study_payload(rows)
    payload["study"]["coarse_grouping"]["state_control"] = [
        "environment_grounding_state_tracking",
        "loop_stagnation_recovery",
    ]
    path = tmp_path / "study.yml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="coarse_grouping|verification_completion|missing"):
        module.load_study(path)


def test_load_study_rejects_duplicate_fine_code_within_one_coarse_group(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]
    payload = _study_payload(rows)
    payload["study"]["coarse_grouping"]["decision_execution"] = [
        "goal_plan_drift",
        "goal_plan_drift",
        "tool_selection_execution",
    ]
    path = tmp_path / "study.yml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="coarse_grouping|duplicates|goal_plan_drift"):
        module.load_study(path)


def test_readme_distinguishes_frozen_v090_core_from_current_issue_455_study():
    readme_text = REPORT_README_PATH.read_text(encoding="utf-8")

    assert "2026-08-29" in readme_text
    assert "98c7de3" in readme_text
    assert "frozen v0.9.0" in readme_text
    assert "current issue #455 study" in readme_text
    assert "recomputed from rolling current generated files" not in readme_text
    assert "current README and report documentation" not in readme_text


def test_load_study_rejects_same_family_name_with_different_ids(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family A",
            radar_query="Family A",
            radar_record_id="family-b",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="identity mismatch|Family A|family-a|family-b"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_rejects_same_family_id_with_different_names(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-a",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-a",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]

    with pytest.raises(ValueError, match="identity mismatch|family-a|Family A|Family B"):
        module.load_study(_write_study(tmp_path, rows))


def test_load_study_requires_study_scope_fields(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-a",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "unmeasured-a",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
    ]
    payload = _study_payload(rows)
    payload["study"].pop("measurement_counterexample_only")
    path = tmp_path / "study.yml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="demonstrated_family_scope|excluded_families|measurement_counterexample_only",
    ):
        module.load_study(path)


def test_load_study_rejects_missing_demonstrated_family_from_scope(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "design-c",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
        _row(
            "unmeasured-d",
            status="unmeasured",
            primary_code="loop_stagnation_recovery",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
        ),
    ]

    with pytest.raises(ValueError, match="demonstrated family scope|missing"):
        module.load_study(_write_study(tmp_path, rows, demonstrated_family_scope=["Family A"]))


def test_load_study_rejects_extra_demonstrated_family_outside_scope(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
        ),
        _row(
            "design-c",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
        _row(
            "unmeasured-d",
            status="unmeasured",
            primary_code="loop_stagnation_recovery",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
        ),
    ]

    with pytest.raises(ValueError, match="demonstrated family scope|extra"):
        module.load_study(
            _write_study(tmp_path, rows, demonstrated_family_scope=["Family A", "Family C"])
        )


def test_load_study_rejects_measurement_counterexample_as_demonstrated(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="family-b",
            benchmark_family_name="SciCode",
            radar_query="SciCode",
            radar_record_id="scicode",
        ),
        _row(
            "design-c",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
        ),
        _row(
            "unmeasured-d",
            status="unmeasured",
            primary_code="loop_stagnation_recovery",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
        ),
    ]

    with pytest.raises(ValueError, match="measurement counterexample|SciCode"):
        module.load_study(
            _write_study(
                tmp_path,
                rows,
                demonstrated_family_scope=["Family A", "SciCode"],
                measurement_counterexample_only=["SciCode"],
            )
        )


@pytest.mark.parametrize("status", ["demonstrated", "design_implied", "unmeasured"])
def test_load_study_enforces_evidence_cutoff_boundary_and_preserves_date_strings(tmp_path, status):
    module = _load_module()
    rows = [
        _row(
            "target-row",
            status=status,
            primary_code="goal_plan_drift",
            published_date="2026-09-01",
        ),
        _row(
            "demo-support",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "design-support",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "unmeasured-support",
            status="unmeasured",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
        ),
    ]
    support_ids_by_status = {
        "demonstrated": {"demo-support"},
        "design_implied": {"design-support"},
        "unmeasured": {"unmeasured-support"},
    }
    rows = [row for row in rows if row["id"] not in support_ids_by_status[status]]

    study = module.load_study(_write_study(tmp_path, rows))
    loaded_row = next(row for row in study["rows"] if row["id"] == "target-row")
    assert loaded_row["published_date"] == "2026-09-01"
    assert study["study"]["evidence_cutoff"] == "2026-09-01"

    late_rows = copy.deepcopy(rows)
    late_rows[0]["published_date"] = "2026-09-02"

    with pytest.raises(ValueError, match="published_date|evidence_cutoff|2026-09-02|2026-09-01"):
        module.load_study(_write_study(tmp_path, late_rows))


@pytest.mark.parametrize("status", ["demonstrated", "design_implied", "unmeasured"])
def test_load_study_rejects_excluded_family_in_any_coded_status(tmp_path, status):
    module = _load_module()
    rows = [
        _row(
            "target-row",
            status=status,
            primary_code="goal_plan_drift",
            benchmark_family_id="excluded-family",
            benchmark_family_name="ToolFailBench",
            radar_query="ToolFailBench",
            radar_record_id="excluded-family",
        ),
        _row(
            "demo-support",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "design-support",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "unmeasured-support",
            status="unmeasured",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
        ),
    ]
    support_ids_by_status = {
        "demonstrated": {"demo-support"},
        "design_implied": {"design-support"},
        "unmeasured": {"unmeasured-support"},
    }
    rows = [row for row in rows if row["id"] not in support_ids_by_status[status]]
    demonstrated_scope = ["ToolFailBench"] if status == "demonstrated" else ["Family B"]

    with pytest.raises(ValueError, match="excluded_families|ToolFailBench"):
        module.load_study(
            _write_study(
                tmp_path,
                rows,
                demonstrated_family_scope=demonstrated_scope,
                excluded_families=["ToolFailBench", "General AgentBench"],
            )
        )


def test_analyze_study_deduplicates_families_for_fine_and_coarse_recurrence(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a1", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "demo-a2",
            status="demonstrated",
            primary_code="goal_plan_drift",
            observed_evidence="A second row in the same family should not increase recurrence.",
        ),
        _row(
            "demo-b1",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "demo-c1",
            status="demonstrated",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "design-d1",
            status="design_implied",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
        ),
        _row(
            "unmeasured-e1",
            status="unmeasured",
            primary_code="loop_stagnation_recovery",
            benchmark_family_id="family-e",
            benchmark_family_name="Family E",
            radar_query="Family E",
            radar_record_id="family-e",
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)

    assert analysis["demonstrated_family_count"] == 3
    assert analysis["fine_recurrence"]["goal_plan_drift"]["family_count"] == 1
    assert analysis["fine_recurrence"]["tool_selection_execution"]["family_count"] == 1
    assert analysis["fine_recurrence"]["verification_completion"]["family_count"] == 1
    assert analysis["coarse_recurrence"]["decision_execution"]["family_count"] == 2
    assert analysis["coarse_recurrence"]["state_control"]["family_count"] == 1
    assert analysis["status_counts"] == {
        "demonstrated": 4,
        "design_implied": 1,
        "unmeasured": 1,
    }


def test_analyze_study_computes_agreement_and_lists_disagreements(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=True,
            secondary_code="goal_plan_drift",
        ),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
            sampled=True,
            secondary_code="verification_completion",
        ),
        _row(
            "design-c",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "unmeasured-d",
            status="unmeasured",
            primary_code="environment_grounding_state_tracking",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
            sampled=True,
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)
    agreement = analysis["agreement"]

    assert agreement["sampled_row_count"] == 3
    assert agreement["completed_row_count"] == 2
    assert agreement["pending_row_count"] == 1
    assert agreement["percent_agreement"] == pytest.approx(0.5)
    assert agreement["cohens_kappa"] == pytest.approx(0.333333, abs=1e-5)
    assert agreement["pending_row_ids"] == ["unmeasured-d"]
    assert agreement["disagreements"] == [
        {
            "id": "demo-b",
            "primary_code": "tool_selection_execution",
            "secondary_code": "verification_completion",
        }
    ]


def test_analyze_study_returns_none_kappa_for_single_completed_match(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=True,
            secondary_code="goal_plan_drift",
        ),
        _row(
            "design-b",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)
    agreement = analysis["agreement"]

    assert agreement["sampled_row_count"] == 1
    assert agreement["completed_row_count"] == 1
    assert agreement["pending_row_count"] == 0
    assert agreement["percent_agreement"] == pytest.approx(1.0)
    assert agreement["cohens_kappa"] is None
    assert agreement["disagreements"] == []


def test_analyze_study_returns_none_kappa_for_same_category_matches(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=True,
            secondary_code="goal_plan_drift",
        ),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="goal_plan_drift",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
            sampled=True,
            secondary_code="goal_plan_drift",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "design-d",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)
    agreement = analysis["agreement"]

    assert agreement["sampled_row_count"] == 2
    assert agreement["completed_row_count"] == 2
    assert agreement["pending_row_count"] == 0
    assert agreement["percent_agreement"] == pytest.approx(1.0)
    assert agreement["cohens_kappa"] is None
    assert agreement["disagreements"] == []


def test_analyze_study_keeps_nondegenerate_perfect_agreement_kappa(tmp_path):
    module = _load_module()
    rows = [
        _row(
            "demo-a",
            status="demonstrated",
            primary_code="goal_plan_drift",
            sampled=True,
            secondary_code="goal_plan_drift",
        ),
        _row(
            "demo-b",
            status="demonstrated",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
            sampled=True,
            secondary_code="tool_selection_execution",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
        _row(
            "design-d",
            status="design_implied",
            primary_code="verification_completion",
            benchmark_family_id="family-d",
            benchmark_family_name="Family D",
            radar_query="Family D",
            radar_record_id="family-d",
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)
    agreement = analysis["agreement"]

    assert agreement["sampled_row_count"] == 2
    assert agreement["completed_row_count"] == 2
    assert agreement["pending_row_count"] == 0
    assert agreement["percent_agreement"] == pytest.approx(1.0)
    assert agreement["cohens_kappa"] == pytest.approx(1.0)
    assert agreement["disagreements"] == []


def test_analysis_exposes_counterexamples_and_missing_measurements(tmp_path):
    module = _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-b",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
    ]

    study = module.load_study(_write_study(tmp_path, rows))
    analysis = module.analyze_study(study)

    assert [item["id"] for item in analysis["missing_measurements"]] == ["unmeasured-c"]
    assert [item["id"] for item in analysis["counterexamples"]] == [
        "demo-a",
        "design-b",
        "unmeasured-c",
    ]


def test_cli_writes_json_and_csv_outputs(tmp_path):
    _load_module()
    rows = [
        _row("demo-a", status="demonstrated", primary_code="goal_plan_drift"),
        _row(
            "design-b",
            status="design_implied",
            primary_code="tool_selection_execution",
            benchmark_family_id="family-b",
            benchmark_family_name="Family B",
            radar_query="Family B",
            radar_record_id="family-b",
        ),
        _row(
            "unmeasured-c",
            status="unmeasured",
            primary_code="verification_completion",
            benchmark_family_id="family-c",
            benchmark_family_name="Family C",
            radar_query="Family C",
            radar_record_id="family-c",
        ),
    ]
    study_path = _write_study(tmp_path, rows)
    json_path = tmp_path / "analysis.json"
    csv_path = tmp_path / "coded-table.csv"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(study_path),
            "--json-output",
            str(json_path),
            "--csv-output",
            str(csv_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["snapshot_date"] == "2026-09-01"
    assert payload["repository_commit_input"] == "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae"
    assert payload["fine_recurrence"]["goal_plan_drift"]["family_count"] == 1

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["id"] for row in rows] == ["demo-a", "design-b", "unmeasured-c"]
    assert rows[0]["coarse_group"] == "decision_execution"
