"""Today's radar items drawn as share cards in the browser (issue #1019)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from benchmark_radar.daily_top import _HANDLE_SOURCES

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_og_image  # noqa: E402
import render_share_images  # noqa: E402

RADAR_CARD = (ROOT / "site" / "assets" / "radar-card.js").read_text(encoding="utf-8")


def _js_value(name: str) -> str:
    match = re.search(rf'^\s*{name}: "?([^",\n]+)"?,$', RADAR_CARD, re.MULTILINE)
    assert match, name
    return match.group(1)


def test_drawn_card_uses_the_published_cards_colours_and_sizes():
    """The card design lives in Python and JS; this fails when they drift apart."""
    assert (int(_js_value("width")), int(_js_value("height"))) == render_share_images.CARD_SIZE
    assert int(_js_value("margin")) == render_share_images.MARGIN
    assert _js_value("watermark") == render_share_images.WATERMARK
    assert _js_value("background") == generate_og_image.BACKGROUND
    assert _js_value("ink") == generate_og_image.INK
    assert _js_value("teal") == generate_og_image.TEAL
    assert _js_value("slate") == generate_og_image.SLATE


def test_drawn_card_skips_the_same_categories_and_owner_handles():
    generic = re.search(r"GENERIC_CATEGORIES = new Set\(\[(.*?)\]\)", RADAR_CARD, re.DOTALL)
    handles = re.search(r"HANDLE_SOURCES = new Set\(\[(.*?)\]\)", RADAR_CARD, re.DOTALL)
    assert set(re.findall(r'"([^"]+)"', generic.group(1))) == set(
        render_share_images.GENERIC_CATEGORIES
    )
    assert set(_HANDLE_SOURCES) <= set(re.findall(r'"([^"]+)"', handles.group(1)))


def test_drawn_card_holds_only_the_facts_an_item_has():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/radar_card_harness.mjs"], check=True, timeout=60, cwd=ROOT)


def test_every_radar_card_has_a_share_button():
    """The button no longer depends on the day having published a card."""
    source = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    start = source.index("function evidenceCard(")
    card = source[start : source.index("function observationCard(")]
    assert 'radarShareButton(item, day, fullTitle, shareCard?.image || "")' in card
    assert "shareCard ?" not in card
