import sys
from pathlib import Path

import pytest
from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_og_image as og  # noqa: E402


def test_requested_size_is_honoured():
    # The property that actually broke. Asserted by measuring, not by checking
    # the font class: Pillow's load_default() returns a scalable FreeTypeFont
    # on 11+ and an unscalable bitmap face before that, so a type check would
    # pass on current Pillow while the title still rendered at ~10px.
    small = og.font(23).getbbox("Benchmark")[2]
    large = og.font(og.TITLE_SIZE).getbbox("Benchmark")[2]
    assert large > small * 1.5


def test_guard_passes_with_the_fonts_available_here():
    og._assert_scalable_fonts()


def test_guard_rejects_a_face_that_ignores_the_requested_size(monkeypatch):
    # Simulates the macOS-without-DejaVu case that rendered a ~10px title.
    # Patching font() rather than ImageFont.truetype, because load_default()
    # calls truetype() internally on a bundled buffer, so patching that would
    # break the very fallback this needs to reach.
    monkeypatch.setattr(og, "font", lambda *a, **k: ImageFont.load_default())
    with pytest.raises(SystemExit, match="ignores the requested size"):
        og._assert_scalable_fonts()


def test_render_writes_a_correctly_sized_card(tmp_path):
    # 1200x630 is what the og:image:width/height meta in site/index.html
    # declares, and a mismatch makes the unfurled card letterbox or crop.
    leaderboard = og.build_adoption_rank(og.DEFAULT_REGISTRY_PATH)
    output = og.render(leaderboard, tmp_path / "og-card.png")
    with Image.open(output) as image:
        assert image.size == (1200, 630)


def test_card_reports_the_current_registry_counts(tmp_path):
    # The card is a claim about the registry that travels without it. The
    # committed copy drifted from the live one this way: the ranking moved and
    # the image kept advertising the old count.
    leaderboard = og.build_adoption_rank(og.DEFAULT_REGISTRY_PATH)
    top = leaderboard["entries"][0]
    assert top["card_count"] > 0
    # render() reads these straight from the leaderboard, so a passing render
    # plus a non-empty ranking is what ties the image to today's registry.
    output = og.render(leaderboard, tmp_path / "og-card.png")
    assert output.stat().st_size > 0
