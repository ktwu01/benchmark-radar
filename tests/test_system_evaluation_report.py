from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest
import yaml

SCRIPT_PATH = Path("scripts/build_system_evaluation.py")
LEGACY_SCRIPT_PATH = Path("scripts/build_technical_report.py")
DATA_PATH = Path("data/agent_weakness_evidence.yml")


class _FakeParagraph:
    def __init__(self, text, style=None):
        self.text = text
        self.style = style


class _FakeTable:
    def __init__(self, rows, **kwargs):
        self._cellvalues = rows
        self.kwargs = kwargs


class _FakeTableStyle:
    def __init__(self, commands):
        self.commands = commands


class _FakeSpacer:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakePageBreak:
    pass


class _FakeParagraphStyle:
    def __init__(self, name, parent=None, **kwargs):
        self.name = name
        self.parent = parent
        self.kwargs = kwargs


class _FakeDrawing:
    def __init__(self, *args, **kwargs):
        self.items = []

    def add(self, item):
        self.items.append(item)


class _FakeShape:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakeTTFont:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakeImageReader:
    def __init__(self, value):
        self.value = value

    def getSize(self):
        return (640, 480)


class _FakeBaseDocTemplate:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def addPageTemplates(self, templates):
        self.templates = templates

    def build(self, story):
        self.story = story


class _FakeFrame:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakePageTemplate:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


def _install_report_builder_stubs():
    fake_build = types.ModuleType("build_technical_report")
    fake_build.AMBER = "#AMBER"
    fake_build.BLUE = "#BLUE"
    fake_build.BOLD = "BOLD"
    fake_build.INK = "#INK"
    fake_build.ITALIC = "ITALIC"
    fake_build.MARGIN_X = 36
    fake_build.MUTED = "#MUTED"
    fake_build.NAVY = "#NAVY"
    fake_build.PAGE_W = 612
    fake_build.PALE_AMBER = "#PALE_AMBER"
    fake_build.PALE_TEAL = "#PALE_TEAL"
    fake_build.REGULAR = "REGULAR"
    fake_build.RULE = "#RULE"
    fake_build.SKY = "#SKY"
    fake_build.TEAL = "#TEAL"
    fake_build.WHITE = "#WHITE"
    fake_build.bullet = lambda text, style: _FakeParagraph(text, style)
    fake_build.p = lambda text, style: _FakeParagraph(text, style)

    def _legacy_parser():
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--output",
            type=Path,
            default=Path("output/pdf/benchmark-radar-technical-report-next-draft.pdf"),
        )
        return parser

    fake_build.build_parser = _legacy_parser
    fake_build.styles = lambda: {
        key: key
        for key in (
            "small",
            "meta",
            "title",
            "subtitle",
            "author",
            "callout",
            "section",
            "subsection",
            "body",
            "table_header",
            "small_bold",
            "metric",
            "metric_label",
            "reference",
        )
    }
    sys.modules["build_technical_report"] = fake_build

    reportlab = types.ModuleType("reportlab")
    graphics = types.ModuleType("reportlab.graphics")
    shapes = types.ModuleType("reportlab.graphics.shapes")
    shapes.Drawing = _FakeDrawing
    shapes.Line = _FakeShape
    shapes.Polygon = _FakeShape
    shapes.Rect = _FakeShape
    shapes.String = _FakeShape
    lib = types.ModuleType("reportlab.lib")
    colors = types.ModuleType("reportlab.lib.colors")
    colors.HexColor = lambda value: value
    colors.white = "#WHITE"
    enums = types.ModuleType("reportlab.lib.enums")
    enums.TA_CENTER = 1
    enums.TA_LEFT = 0
    pagesizes = types.ModuleType("reportlab.lib.pagesizes")
    pagesizes.letter = (612, 792)
    styles = types.ModuleType("reportlab.lib.styles")
    styles.ParagraphStyle = _FakeParagraphStyle
    styles.getSampleStyleSheet = lambda: {
        "Title": "Title",
        "Normal": "Normal",
        "Heading1": "Heading1",
        "Heading2": "Heading2",
        "BodyText": "BodyText",
    }
    units = types.ModuleType("reportlab.lib.units")
    units.inch = 72
    utils = types.ModuleType("reportlab.lib.utils")
    utils.ImageReader = _FakeImageReader
    pdfbase = types.ModuleType("reportlab.pdfbase")
    pdfmetrics = types.ModuleType("reportlab.pdfbase.pdfmetrics")
    pdfmetrics.registerFont = lambda font: None
    ttfonts = types.ModuleType("reportlab.pdfbase.ttfonts")
    ttfonts.TTFont = _FakeTTFont
    platypus = types.ModuleType("reportlab.platypus")
    platypus.BaseDocTemplate = _FakeBaseDocTemplate
    platypus.Frame = _FakeFrame
    platypus.PageBreak = _FakePageBreak
    platypus.PageTemplate = _FakePageTemplate
    platypus.Paragraph = _FakeParagraph
    platypus.Image = _FakeShape
    platypus.KeepTogether = lambda rows: rows
    platypus.Spacer = _FakeSpacer
    platypus.Table = _FakeTable
    platypus.TableStyle = _FakeTableStyle

    sys.modules["reportlab"] = reportlab
    sys.modules["reportlab.graphics"] = graphics
    sys.modules["reportlab.graphics.shapes"] = shapes
    sys.modules["reportlab.lib"] = lib
    sys.modules["reportlab.lib.colors"] = colors
    sys.modules["reportlab.lib.enums"] = enums
    sys.modules["reportlab.lib.pagesizes"] = pagesizes
    sys.modules["reportlab.lib.styles"] = styles
    sys.modules["reportlab.lib.units"] = units
    sys.modules["reportlab.lib.utils"] = utils
    sys.modules["reportlab.pdfbase"] = pdfbase
    sys.modules["reportlab.pdfbase.pdfmetrics"] = pdfmetrics
    sys.modules["reportlab.pdfbase.ttfonts"] = ttfonts
    sys.modules["reportlab.platypus"] = platypus


def _load_module():
    assert SCRIPT_PATH.exists(), f"missing report builder: {SCRIPT_PATH}"
    _install_report_builder_stubs()
    spec = importlib.util.spec_from_file_location("build_system_evaluation", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_legacy_module():
    assert LEGACY_SCRIPT_PATH.exists(), f"missing legacy report builder: {LEGACY_SCRIPT_PATH}"
    _install_report_builder_stubs()
    canonical = types.ModuleType("build_system_evaluation")
    canonical.build_parser = sys.modules["build_technical_report"].build_parser
    sys.modules["build_system_evaluation"] = canonical
    spec = importlib.util.spec_from_file_location(
        "legacy_build_technical_report", LEGACY_SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_modified_study(tmp_path: Path, transform) -> Path:
    study = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8"))
    transform(study)
    path = tmp_path / "study.yml"
    path.write_text(yaml.safe_dump(study, sort_keys=False), encoding="utf-8")
    return path


def _collect_text(node) -> list[str]:
    if isinstance(node, _FakeParagraph):
        return [node.text]
    if isinstance(node, _FakeTable):
        texts: list[str] = []
        for row in node._cellvalues:
            for cell in row:
                texts.extend(_collect_text(cell))
        return texts
    if isinstance(node, list):
        texts: list[str] = []
        for item in node:
            texts.extend(_collect_text(item))
        return texts
    return []


def _agent_section_flowables(story) -> list[object]:
    start = None
    end = None
    for index, item in enumerate(story):
        if isinstance(item, _FakeParagraph) and item.text == (
            "6.5 Selected benchmark-family signal on agent weaknesses"
        ):
            start = index + 1
            continue
        if start is not None and isinstance(item, list):
            nested_text = _collect_text(item)
            if "6.6 Worked real use case: prior-art check for a new evaluation" in nested_text:
                end = index
                break
        if start is not None and isinstance(item, _FakeTable) and "Use it" in _collect_text(item):
            end = index
            break
    assert start is not None
    assert end is not None
    return story[start:end]


def test_default_output_targets_next_draft():
    module = _load_module()

    args = module.build_parser().parse_args([])

    assert args.output == Path("output/pdf/benchmark-radar-technical-report-next-draft.pdf")
    assert args.output.name != "benchmark-radar-technical-report-v0.9.0.pdf"


def test_agent_weakness_reference_citation_range_tracks_generated_references(tmp_path, monkeypatch):
    module = _load_module()

    def fake_analyze_study(study):
        return {
            "snapshot_date": "2026-09-01",
            "evidence_cutoff": "2026-09-01",
            "repository_commit_input": "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae",
            "demonstrated_family_count": 1,
            "state_control_count": 1,
            "decision_execution_count": 0,
            "agreement_match_count": 0,
            "completed_secondary_review_count": 0,
            "sampled_secondary_review_count": 0,
            "pending_secondary_review_count": 0,
            "design_implied_count": 1,
            "unmeasured_count": 1,
            "measurement_counterexample_only": ["SciCode"],
            "agreement": {
                "completed_row_count": 0,
                "sampled_row_count": 0,
                "pending_row_count": 0,
                "disagreements": [],
            },
            "coarse_recurrence": {
                "state_control": {"family_count": 1},
                "decision_execution": {"family_count": 0},
            },
            "status_counts": {
                "demonstrated": 1,
                "design_implied": 1,
                "unmeasured": 1,
            },
        }

    fake_analysis_module = types.SimpleNamespace(
        load_study=lambda path: yaml.safe_load(Path(path).read_text(encoding="utf-8")),
        analyze_study=fake_analyze_study,
    )
    monkeypatch.setattr(
        module,
        "_load_agent_weakness_analysis_module",
        lambda: fake_analysis_module,
    )

    def transform(study):
        selected_rows = []
        selected_statuses = set()
        for row in study["rows"]:
            status = row["status"]
            if status in selected_statuses:
                continue
            selected_rows.append(row)
            selected_statuses.add(status)
            if selected_statuses == {"demonstrated", "design_implied", "unmeasured"}:
                break
        study["rows"] = selected_rows
        study["study"]["demonstrated_family_scope"] = [
            row["benchmark_family_name"] for row in selected_rows if row["status"] == "demonstrated"
        ]
        study["study"]["measurement_counterexample_only"] = [
            family
            for family in study["study"]["measurement_counterexample_only"]
            if family not in study["study"]["demonstrated_family_scope"]
        ]

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    citation_range = module.agent_weakness_reference_citation_range(report_data)
    references = module.agent_weakness_reference_entries(report_data)

    assert len(report_data["primary_source_references"]) == 3
    assert citation_range == "[9-11]"
    assert "cited in [9-11]" in paragraphs[1]
    assert references[0].startswith("[9] Primary-source evidence for ")
    assert references[-1].startswith("[11] Primary-source evidence for ")


def test_legacy_builder_defaults_to_next_draft_but_allows_explicit_frozen_output():
    module = _load_legacy_module()

    default_args = module.build_parser().parse_args([])
    explicit_args = module.build_parser().parse_args(
        ["--output", "output/pdf/benchmark-radar-technical-report-v0.9.0.pdf"]
    )

    assert default_args.output == Path("output/pdf/benchmark-radar-technical-report-next-draft.pdf")
    assert explicit_args.output == Path("output/pdf/benchmark-radar-technical-report-v0.9.0.pdf")


def test_legacy_builder_main_delegates_to_canonical_builder(monkeypatch):
    module = _load_legacy_module()
    calls: list[str] = []

    fake_next = types.ModuleType("build_system_evaluation")

    def fake_main():
        calls.append("main")

    fake_next.main = fake_main
    fake_next.EvaluationDoc = lambda *args, **kwargs: pytest.fail("legacy wrapper should delegate")
    fake_next.story = lambda *args, **kwargs: pytest.fail("legacy wrapper should delegate")
    monkeypatch.setitem(sys.modules, "build_system_evaluation", fake_next)
    monkeypatch.setattr(sys, "argv", ["build_technical_report.py"])

    module.main()

    assert calls == ["main"]


def test_agent_weakness_section_reports_bounded_result_and_method():
    module = _load_module()

    report_data = module.load_agent_weakness_report_data()
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    section_text = "\n".join(paragraphs)

    assert report_data["issue_number"] == 455
    assert report_data["issue_url"] == "https://github.com/ktwu01/benchmark-radar/issues/455"
    assert report_data["contributor"] == "Junkai Wang / @JunkaiWang-TheoPhy"
    assert report_data["snapshot_date"] == "2026-09-01"
    assert report_data["evidence_cutoff"] == "2026-09-01"
    assert report_data["repository_commit_input"] == "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae"
    assert report_data["demonstrated_family_count"] == 8
    assert report_data["state_control_count"] == 6
    assert report_data["decision_execution_count"] == 2
    assert report_data["agreement_match_count"] == 4
    assert report_data["completed_secondary_review_count"] == 4
    assert report_data["sampled_secondary_review_count"] == 4
    assert report_data["pending_secondary_review_count"] == 0
    assert report_data["design_implied_count"] == 1
    assert report_data["unmeasured_count"] == 1
    assert report_data["measurement_counterexample_only"] == ["SciCode"]

    assert paragraphs[0].startswith("Across 8 demonstrated benchmark families")
    assert "family-deduplicated denominator" in section_text
    assert "6/8" in section_text
    assert "state-control" in section_text
    assert "2/8" in section_text
    assert "decision-execution" in section_text
    assert "selected sample" in section_text
    assert "not a field-wide prevalence estimate" in section_text
    assert "Junkai Wang / @JunkaiWang-TheoPhy" in section_text
    assert "https://github.com/ktwu01/benchmark-radar/issues/455" in section_text
    assert "2026-09-01" in section_text
    assert "98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae" in section_text
    assert "demonstrated" in section_text
    assert "design-implied" in section_text
    assert "unmeasured" in section_text
    assert "4/4" in section_text
    assert "sample-local result among completed rows in the main packet" in section_text
    assert "does not establish broad reliability" in section_text
    assert "SciCode" in section_text
    assert "instrument counterexample" in section_text
    assert "not exhaustive" in section_text
    assert len(paragraphs) == 2


def test_disagreement_fixture_uses_agreement_match_count_not_completed_count(tmp_path):
    module = _load_module()

    def transform(study):
        sampled_ids = {
            "osworld2_hidden_state",
            "swe_science_misguided_exploration",
            "researchclawbench_protocol_drift",
        }
        for row in study["rows"]:
            review = row["review"]
            review["sampled_for_secondary_review"] = row["id"] in sampled_ids
            if row["id"] == "osworld2_hidden_state":
                review["secondary_code"] = row["primary_code"]
                review["secondary_note"] = "Match."
            elif row["id"] == "swe_science_misguided_exploration":
                review["secondary_code"] = "goal_plan_drift"
                review["secondary_note"] = "Disagreement."
            elif row["id"] == "researchclawbench_protocol_drift":
                review["secondary_code"] = row["primary_code"]
                review["secondary_note"] = "Match."
            else:
                review["secondary_code"] = None
                review["secondary_note"] = None

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    section_text = "\n".join(paragraphs)

    assert report_data["sampled_secondary_review_count"] == 3
    assert report_data["completed_secondary_review_count"] == 3
    assert report_data["pending_secondary_review_count"] == 0
    assert report_data["agreement_match_count"] == 2
    assert "2/3" in section_text
    assert "3/3" not in section_text
    assert "4/4 sample-local result" not in section_text


def test_partial_review_fixture_reports_completed_agreement_and_pending_rows(tmp_path):
    module = _load_module()

    def transform(study):
        sampled_ids = {
            "osworld2_hidden_state",
            "swe_science_misguided_exploration",
            "researchclawbench_protocol_drift",
            "scicode_instrument_gap",
        }
        completed_ids = {
            "osworld2_hidden_state",
            "researchclawbench_protocol_drift",
        }
        for row in study["rows"]:
            review = row["review"]
            review["sampled_for_secondary_review"] = row["id"] in sampled_ids
            if row["id"] in completed_ids:
                review["secondary_code"] = row["primary_code"]
                review["secondary_note"] = "Match."
            else:
                review["secondary_code"] = None
                review["secondary_note"] = None

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    section_text = "\n".join(paragraphs)

    assert report_data["sampled_secondary_review_count"] == 4
    assert report_data["completed_secondary_review_count"] == 2
    assert report_data["pending_secondary_review_count"] == 2
    assert report_data["agreement_match_count"] == 2
    assert (
        "matched on 2/2 completed blinded sampled rows "
        "and 2 pending sampled rows out of 4 sampled rows" in section_text
    )
    assert "2/2 sample-local result among completed rows" in section_text
    assert "2/4" not in section_text


def test_partial_review_fixture_reports_pending_rows_in_summary_table(tmp_path, monkeypatch):
    module = _load_module()

    def transform(study):
        sampled_ids = {
            "osworld2_hidden_state",
            "swe_science_misguided_exploration",
            "researchclawbench_protocol_drift",
            "scicode_instrument_gap",
        }
        completed_ids = {
            "osworld2_hidden_state",
            "researchclawbench_protocol_drift",
        }
        for row in study["rows"]:
            review = row["review"]
            review["sampled_for_secondary_review"] = row["id"] in sampled_ids
            if row["id"] in completed_ids:
                review["secondary_code"] = row["primary_code"]
                review["secondary_note"] = "Match."
            else:
                review["secondary_code"] = None
                review["secondary_note"] = None

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)

    monkeypatch.setattr(
        module, "load_agent_weakness_report_data", lambda source_path=study_path: report_data
    )
    story = module.story("10.5281/zenodo.22167102")
    table_text = "\n".join(_collect_text(_agent_section_flowables(story)[0]))

    assert "2/2 agreement matches across 4 blinded sampled rows" in table_text
    assert "2 pending sampled rows" in table_text


def test_pending_only_review_fixture_reports_no_completed_secondary_reviews(tmp_path, monkeypatch):
    module = _load_module()

    def transform(study):
        sampled_ids = {
            "osworld2_hidden_state",
            "swe_science_misguided_exploration",
            "researchclawbench_protocol_drift",
            "scicode_instrument_gap",
        }
        for row in study["rows"]:
            review = row["review"]
            review["sampled_for_secondary_review"] = row["id"] in sampled_ids
            review["secondary_code"] = None
            review["secondary_note"] = None

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    section_text = "\n".join(paragraphs)

    assert report_data["sampled_secondary_review_count"] == 4
    assert report_data["completed_secondary_review_count"] == 0
    assert report_data["pending_secondary_review_count"] == 4
    assert "0/0" not in section_text
    assert (
        "No completed blinded sampled rows yet; 4 pending sampled rows out of 4 sampled rows."
        in section_text
    )

    monkeypatch.setattr(
        module, "load_agent_weakness_report_data", lambda source_path=study_path: report_data
    )
    story = module.story("10.5281/zenodo.22167102")
    table_text = "\n".join(_collect_text(_agent_section_flowables(story)[0]))

    assert "0/0" not in table_text
    assert (
        "No completed secondary reviews yet; 4 pending sampled rows out of 4 sampled rows"
        in table_text
    )


def test_no_sampled_review_fixture_reports_zero_pending_without_zero_fraction(
    tmp_path, monkeypatch
):
    module = _load_module()

    def transform(study):
        for row in study["rows"]:
            review = row["review"]
            review["sampled_for_secondary_review"] = False
            review["secondary_code"] = None
            review["secondary_note"] = None

    study_path = _write_modified_study(tmp_path, transform)
    report_data = module.load_agent_weakness_report_data(study_path)
    paragraphs = module.agent_weakness_section_paragraphs(report_data)
    section_text = "\n".join(paragraphs)

    assert report_data["sampled_secondary_review_count"] == 0
    assert report_data["completed_secondary_review_count"] == 0
    assert report_data["pending_secondary_review_count"] == 0
    assert "0/0" not in section_text
    assert (
        "No completed blinded sampled rows yet; 0 pending sampled rows out of 0 sampled rows."
        in section_text
    )

    monkeypatch.setattr(
        module, "load_agent_weakness_report_data", lambda source_path=study_path: report_data
    )
    story = module.story("10.5281/zenodo.22167102")
    table_text = "\n".join(_collect_text(_agent_section_flowables(story)[0]))

    assert "0/0" not in table_text
    assert (
        "No completed secondary reviews yet; 0 pending sampled rows out of 0 sampled rows"
        in table_text
    )


def test_story_places_agent_weakness_subsection_before_use_it_and_adds_primary_sources():
    module = _load_module()

    story = module.story("10.5281/zenodo.22167102")
    texts = _collect_text(story)

    subsection_index = texts.index("6.5 Selected benchmark-family signal on agent weaknesses")
    use_it_index = texts.index("Use it")
    refs_index = texts.index(
        "[9] Primary-source evidence for OSWorld 2.0. "
        "https://arxiv.org/html/2606.29537v1. Evidence anchor: HTML abstract "
        "paragraph id abstract1.1, final two sentences on 20.6% binary "
        "completion, 54.8% partial score, and hidden-state recovery; Figure 8 "
        "caption at figure id S3.F8"
    )

    assert subsection_index < use_it_index
    assert refs_index > texts.index("References")
    assert (
        "[17] Primary-source evidence for SciCode. https://arxiv.org/abs/2608.04975. "
        "Evidence anchor: arXiv abs abstract paragraph on 263 defects, 192 "
        "score-suppressing defects across 91% of main problems, and recovery "
        "to 84-98% / 69-92%"
    ) in texts

    section_flowables = _agent_section_flowables(story)
    assert len(section_flowables) == 3
    assert isinstance(section_flowables[0], _FakeTable)
    assert isinstance(section_flowables[1], _FakeParagraph)
    assert section_flowables[1].style == "body"
    assert isinstance(section_flowables[2], _FakeParagraph)
    assert section_flowables[2].style == "small"


def test_agent_weakness_reference_entries_include_exact_evidence_anchors():
    module = _load_module()

    report_data = module.load_agent_weakness_report_data()
    entries = module.agent_weakness_reference_entries(report_data)
    joined_entries = "\n".join(entries)

    assert "Evidence anchor:" in joined_entries
    assert (
        "[9] Primary-source evidence for OSWorld 2.0. https://arxiv.org/html/2606.29537v1. "
        "Evidence anchor: HTML abstract paragraph id abstract1.1, final two sentences on "
        "20.6% binary completion, 54.8% partial score, and hidden-state recovery; Figure 8 "
        "caption at figure id S3.F8"
    ) in entries
    assert (
        "GAIA2. https://arxiv.org/html/2602.11964v1. Evidence anchor: HTML abstract paragraph "
        "id abstract1.1 on 42% pass@1 and time-sensitive failures; HTML paragraph id "
        "S5.SS2.p1.1 and Figure 8 caption id S5.F8 on default-versus-instant Time behavior"
    ) in joined_entries
    assert (
        "SciCode. https://arxiv.org/abs/2608.04975. Evidence anchor: arXiv abs abstract "
        "paragraph on 263 defects, 192 score-suppressing defects across 91% of main problems, "
        "and recovery to 84-98% / 69-92%"
    ) in joined_entries


def test_story_uses_frozen_core_data_statement_and_separates_current_issue_455_study():
    module = _load_module()

    story = module.story("10.5281/zenodo.22167102")
    report_text = "\n".join(_collect_text(story))

    assert "frozen v0.9.0 audit" in report_text
    assert "98c7de3" in report_text
    assert "2026-08-29" in report_text
    assert "current issue #455 study is reported separately" in report_text
    assert "Counts were recomputed from site/data/radar.json" not in report_text
    assert "rolling dashboard may change after the cutoff" not in report_text


def test_story_uses_stable_ci_wording_without_hardcoded_test_counts():
    module = _load_module()

    story = module.story("10.5281/zenodo.22167102")
    report_text = "\n".join(_collect_text(story))

    assert "The current full CI suite passed." in report_text
    assert "All 1,028 tests passed." not in report_text
    assert re.search(r"\bAll\s+\d[\d,]*\s+tests\s+passed\b", report_text) is None
    assert re.search(r"\b\d[\d,]*\s+passing tests\b", report_text) is None
