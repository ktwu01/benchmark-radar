import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_og_image as og  # noqa: E402


def _index(records):
    return {"count": 999, "benchmarks": records}


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
    index = _index(
        [
            {
                "key": og.EXAMPLE_KEYS[0],
                "name": "Example Bench",
                "source": "llm_stats",
                "publisher": "Example Lab",
                "released": "2024-08-13",
                "has_paper": True,
                "has_repo": False,
                "has_dataset": True,
                "score_count": 12,
            }
        ]
    )
    output = og.render(index, tmp_path / "og-card.png")
    with Image.open(output) as image:
        assert image.size == (1200, 630)


def test_catalog_counts_include_every_record_and_source():
    # Count records, never the stale header or a second registry, and count
    # sources from the records themselves rather than a constant.
    index = _index(
        [
            {"source": "llm_stats"},
            {"source": "opencompass_hub"},
            {"source": "artificial_analysis"},
            {"source": "llm_stats"},
        ]
    )
    assert og.catalog_counts(index) == (4, 3)


def test_examples_come_from_the_catalog_and_skip_missing_records():
    index = _index([{"key": og.EXAMPLE_KEYS[1], "name": "Present"}, {"key": "other"}])
    assert [row["name"] for row in og.example_rows(index)] == ["Present"]


def test_examples_exist_in_the_built_catalog():
    path = og.DEFAULT_INDEX_PATH
    if not path.exists():
        pytest.skip("run benchmark-radar normalize-catalog first")
    rows = og.example_rows(json.loads(path.read_text(encoding="utf-8")))
    assert [row["key"] for row in rows] == list(og.EXAMPLE_KEYS)
