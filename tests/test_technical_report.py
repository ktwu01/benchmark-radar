from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_system_evaluation.py"


def _assignment(name: str) -> ast.Assign:
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )


def test_frozen_and_next_draft_outputs_are_distinct() -> None:
    frozen = ast.literal_eval(_assignment("FROZEN_OUTPUT").value.args[0])
    draft = ast.literal_eval(_assignment("NEXT_DRAFT_OUTPUT").value.args[0])

    assert frozen == "output/pdf/benchmark-radar-technical-report-v0.9.0.pdf"
    assert draft == "output/pdf/benchmark-radar-technical-report-next-draft.pdf"
    assert frozen != draft


def test_next_draft_records_contributor_name_and_affiliation() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    draft_authors = ast.literal_eval(_assignment("NEXT_DRAFT_AUTHORS").value)
    draft_byline = ast.literal_eval(_assignment("NEXT_DRAFT_BYLINE").value)
    draft_affiliations = ast.literal_eval(_assignment("NEXT_DRAFT_AFFILIATIONS").value)
    corresponding_author = ast.literal_eval(_assignment("NEXT_DRAFT_CORRESPONDING_AUTHOR").value)

    assert draft_authors == ("Koutian Wu", "Junjie Zhou", "Jiayu Wang")
    assert draft_byline == (
        "Koutian Wu<super>1,2,*</super>",
        "Junjie Zhou<super>3</super>",
        "Jiayu Wang<super>4</super>",
    )
    assert draft_affiliations == (
        "<super>1</super> Independent researcher",
        "<super>2</super> Tacite AI",
        "<super>3</super> Hangzhou Dianzi University",
        "<super>4</super> Xi'an Jiaotong University",
    )
    assert corresponding_author == "Koutian Wu, k@tacite.ai"
    assert "Corresponding author: {corresponding_author}" in source
    assert "WORKING DRAFT — NOT THE FROZEN v0.9.0 DEPOSIT" not in source


def test_next_draft_records_real_use_case_section() -> None:
    source = BUILDER.read_text(encoding="utf-8")

    assert "6.6 Worked real use case: prior-art check for a new evaluation" in source
    assert "github.com/ktwu01/benchmark-radar/issues/492" in source
    assert "Contributor.</b> Jiayu Wang" in source


def test_next_draft_embeds_use_case_screenshots() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    names = (
        "agent-session.png",
        "artifact-status-paper.png",
        "artifact-status-code.png",
        "cross-validation.png",
        "survey-table.png",
        "aarri-bench-manual-table.png",
    )

    for name in names:
        assert f"assets/use-case-492/{name}" in source
        assert (ROOT / "assets" / "use-case-492" / name).is_file()
