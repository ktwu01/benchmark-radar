import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_saturation_og_image as saturation_og  # noqa: E402


def test_render_writes_the_score_plateau_card_at_the_declared_size(tmp_path):
    # 1200x630 is what the og:image:width/height meta on /saturation/ declares.
    progression = saturation_og.build_score_progression(saturation_og.DEFAULT_SCORES_PATH)
    assert set(saturation_og.CHART_BENCHMARKS) & progression["benchmarks"].keys()
    index = {"benchmarks": [{"source": "llm_stats"}, {"source": "opencompass_hub"}]}
    output = saturation_og.render(progression, index, tmp_path / "card.png")
    with Image.open(output) as image:
        assert image.size == (1200, 630)
