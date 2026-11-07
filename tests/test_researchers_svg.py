"""The researchers logo strip: new logos land, and one logo's CSS classes
cannot repaint another's (issue #1096)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_researchers_svg", ROOT / "scripts" / "build_researchers_svg.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_new_logos_are_in_the_strip():
    builder = _builder()
    assert "zai.svg" in builder.ROWS[2]
    assert "antgroup.png" in builder.ROWS[2]
    assert (ROOT / "assets" / "researchers-logos" / "zai.svg").is_file()
    assert (ROOT / "assets" / "researchers-logos" / "antgroup.png").is_file()


def test_berkeley_and_tesla_logos_are_in_the_strip():
    builder = _builder()
    assert "berkeley.svg" in builder.ROWS[1]
    assert "mit.svg" in builder.ROWS[1]
    assert "harvard.svg" in builder.ROWS[1]
    assert "tesla.svg" in builder.ROWS[0]
    assert (ROOT / "assets" / "researchers-logos" / "berkeley.svg").is_file()
    assert (ROOT / "assets" / "researchers-logos" / "tesla.svg").is_file()


def test_logo_css_classes_are_scoped_per_logo():
    builder = _builder()
    fragment = (
        '<style type="text/css">.st0{fill:#E2E4E7;}.st23{fill:#2D2D2D;}</style>'
        '<path class="st23" d="M0 0h1v1H0z"/>'
    )
    scoped = builder.prefix_classes(fragment, "l15_")
    assert ".l15_st0{fill:#E2E4E7;}" in scoped
    assert ".l15_st23{fill:#2D2D2D;}" in scoped
    assert 'class="l15_st23"' in scoped
    assert ".st0{" not in scoped


def test_the_built_strip_keeps_both_definitions_of_st0():
    """Tsinghua's .st0 is purple, Z.ai's is light grey; the built strip must
    carry both under different names, not one definition for both logos."""
    strip = (ROOT / "assets" / "researchers.svg").read_text(encoding="utf-8")
    assert not re.search(r"(?<![\w-])\.st\d+\s*\{", strip)
    assert re.search(r"\.l\d+_st0\{fill:#930084;\}", strip)
    assert re.search(r"\.l\d+_st0\{opacity:0\.3;fill:#E2E4E7;\}", strip)
