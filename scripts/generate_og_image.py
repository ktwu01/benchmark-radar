"""Render the Open Graph card that every Benchmark Radar page shares.

The card says what the site is for, which is finding benchmarks: a search box
with real catalog records under it, each showing the paper, code, dataset and
score links the catalog holds. The record and source counts are read from the
built catalog at deploy time, so a shared card never advertises a number the
catalog has moved past (principle.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 630
# Drawn at twice the size and scaled down, because Pillow does not antialias
# shapes and the radar glyph and rounded cards look jagged at 1x.
SCALE = 2
DEFAULT_INDEX_PATH = Path("site/data/benchmark-index.json")

# Shared with scripts/render_share_images.py, which draws the daily cards.
BACKGROUND = "#FAFAFA"
INK = "#1B2A4A"
TEAL = "#2A7F8E"
SLATE = "#6B7B8D"
LIGHT = "#DDE3E8"

# The site's own tokens (site/assets/styles.css), so a shared link looks like
# the page it opens.
PANEL = "#FFFFFF"
CANVAS = "#F4F6F7"
SITE_INK = "#172026"
MUTED = "#56636B"
EDGE = "#D3DADF"
LINE = "#E1E6E9"
BLUE = "#2A7F8E"
ORANGE = "#DC633F"

MARGIN = 64
TITLE_SIZE = 46
MIN_TITLE_PROBE_WIDTH = 150

# Benchmarks a reader is likely to recognise, shown as search results. Each
# row prints only what its catalog record holds; a key missing from the
# catalog is skipped rather than drawn from memory.
EXAMPLE_KEYS = (
    "llm-stats:swe-bench-verified",
    "llm-stats:humanity's-last-exam",
    "llm-stats:mmlu-pro",
)
# The search box shows its real placeholder; the rows under it are examples,
# not the answer to a query, so no query is typed.
EXAMPLE_QUERY = "Search benchmarks…"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc"
        if bold
        else "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def mono(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """The site's utility face: labels and figures."""
    for name in (
        "DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return font(size)


def _assert_scalable_fonts() -> None:
    """Refuse to write a card whose text ignored the requested size."""
    probe = "Benchmark"
    title_width = font(TITLE_SIZE, bold=True).getbbox(probe)[2]
    if title_width < MIN_TITLE_PROBE_WIDTH:
        raise SystemExit(
            f'Fonts resolved to a face that ignores the requested size: "{probe}" '
            f"measured {title_width}px wide at {TITLE_SIZE}px, expected at least "
            f"{MIN_TITLE_PROBE_WIDTH}px. Install DejaVu fonts and re-run."
        )


def load_index(index_path: Path = DEFAULT_INDEX_PATH) -> dict:
    return json.loads(index_path.read_text(encoding="utf-8"))


def catalog_counts(index: dict) -> tuple[int, int]:
    """Benchmark records and the sources they come from, across the whole catalog."""
    records = index["benchmarks"]
    return len(records), len({record.get("source") for record in records})


def example_rows(index: dict) -> list[dict]:
    by_key = {record.get("key"): record for record in index["benchmarks"]}
    return [by_key[key] for key in EXAMPLE_KEYS if key in by_key]


def _radar_mark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """The masthead glyph (site/icon.svg): dial, crosshairs and an orange sweep."""
    unit = size / 64
    box = [x + 2 * unit, y + 2 * unit, x + 62 * unit, y + 62 * unit]
    draw.ellipse(box, fill=PANEL, outline=SITE_INK, width=max(1, round(2 * unit)))
    centre = (x + 32 * unit, y + 32 * unit)
    draw.line(
        [(centre[0], y + 4 * unit), (centre[0], y + 60 * unit)],
        fill="#BDC9CE",
        width=round(1.5 * unit),
    )
    draw.line(
        [(x + 4 * unit, centre[1]), (x + 60 * unit, centre[1])],
        fill="#BDC9CE",
        width=round(1.5 * unit),
    )
    ring = [
        centre[0] - 22 * unit,
        centre[1] - 22 * unit,
        centre[0] + 22 * unit,
        centre[1] + 22 * unit,
    ]
    # The SVG arc runs from 12 o'clock to 3 o'clock, rotated 35 degrees.
    draw.arc(ring, start=-90 + 35, end=0 + 35, fill=ORANGE, width=round(4 * unit))


def wordmark(draw: ImageDraw.ImageDraw, x: int, y: int, *, s: int) -> None:
    """The radar glyph, the name, and a raised TM, shared by every share card."""
    _radar_mark(draw, x, y, 44 * s)
    face = mono(22 * s)
    name_x = x + 58 * s
    draw.text((name_x, y + 22 * s), "Benchmark Radar", font=face, fill=SITE_INK, anchor="lm")
    tm_x = name_x + draw.textlength("Benchmark Radar", font=face) + 3 * s
    draw.text((tm_x, y + 10 * s), "TM", font=font(10 * s, bold=True), fill=SITE_INK, anchor="lm")


def _chip(
    draw: ImageDraw.ImageDraw, x: int, y: int, text: str, *, s: int, strong: bool = False
) -> int:
    face = mono(13 * s)
    width = draw.textlength(text, font=face) + 20 * s
    draw.rounded_rectangle(
        [x, y, x + width, y + 26 * s],
        radius=13 * s,
        fill=LIGHT if strong else PANEL,
        outline=EDGE,
        width=s,
    )
    draw.text((x + 10 * s, y + 13 * s), text, font=face, fill=SITE_INK, anchor="lm")
    return round(x + width + 8 * s)


def _fit(draw: ImageDraw.ImageDraw, text: str, face, width: float) -> str:
    if draw.textlength(text, font=face) <= width:
        return text
    while text and draw.textlength(f"{text}…", font=face) > width:
        text = text[:-1]
    return f"{text.rstrip()}…"


def _result_card(
    draw: ImageDraw.ImageDraw, record: dict, x: int, y: int, width: int, *, s: int
) -> None:
    height = 104 * s
    draw.rounded_rectangle(
        [x, y, x + width, y + height], radius=10 * s, fill=PANEL, outline=EDGE, width=s
    )
    inner = x + 20 * s
    name = _fit(
        draw, record.get("name") or record.get("key", ""), font(23 * s, bold=True), width - 40 * s
    )
    draw.text((inner, y + 16 * s), name, font=font(23 * s, bold=True), fill=SITE_INK)
    meta = " · ".join(
        str(part) for part in (record.get("publisher"), (record.get("released") or "")[:4]) if part
    )
    if meta:
        draw.text(
            (inner, y + 46 * s),
            _fit(draw, meta, font(15 * s), width - 40 * s),
            font=font(15 * s),
            fill=MUTED,
        )
    chip_x = inner
    chip_y = y + 68 * s
    for flag, label in (("has_paper", "Paper"), ("has_repo", "Code"), ("has_dataset", "Dataset")):
        if record.get(flag):
            chip_x = _chip(draw, chip_x, chip_y, label, s=s)
    scores = int(record.get("score_count") or 0)
    if scores:
        _chip(draw, chip_x, chip_y, f"{scores:,} scores", s=s, strong=True)


def render(index: dict, output: Path) -> Path:
    s = SCALE
    image = Image.new("RGB", (WIDTH * s, HEIGHT * s), CANVAS)
    draw = ImageDraw.Draw(image)

    # Left: what this is, in words a newcomer can repeat.
    left = MARGIN * s
    wordmark(draw, left, 56 * s, s=s)

    headline = font(54 * s, bold=True)
    for offset, line in enumerate(("Find any", "AI benchmark.")):
        draw.text((left, (148 + offset * 66) * s), line, font=headline, fill=SITE_INK)
    body = font(22 * s)
    for offset, line in enumerate(
        (
            "Paper, code, dataset and reported",
            "scores for each one. New benchmarks",
            "added every day.",
        )
    ):
        draw.text((left, (300 + offset * 32) * s), line, font=body, fill=MUTED)

    records, sources = catalog_counts(index)
    figure = font(40 * s, bold=True)
    draw.text((left, 438 * s), f"{records:,}", font=figure, fill=SITE_INK)
    figure_width = draw.textlength(f"{records:,}", font=figure)
    draw.text(
        (left + figure_width + 14 * s, 466 * s),
        f"benchmark records from {sources} sources",
        font=font(19 * s),
        fill=MUTED,
        anchor="ls",
    )
    draw.line([(left, 520 * s), (left + 64 * s, 520 * s)], fill=ORANGE, width=4 * s)
    draw.text((left, 548 * s), "benchmark-radar.org", font=mono(24 * s), fill=BLUE)

    # Right: the product itself, a search box with catalog records under it.
    panel_left = 600 * s
    panel_right = (WIDTH - 48) * s
    draw.rounded_rectangle(
        [panel_left, 48 * s, panel_right, (HEIGHT - 48) * s],
        radius=14 * s,
        fill=PANEL,
        outline=EDGE,
        width=s,
    )
    inner_left = panel_left + 28 * s
    inner_width = panel_right - panel_left - 56 * s
    search_top = 76 * s
    draw.rounded_rectangle(
        [inner_left, search_top, inner_left + inner_width, search_top + 58 * s],
        radius=8 * s,
        fill="#FFFFFF",
        outline=SITE_INK,
        width=2 * s,
    )
    # A magnifier, the caret, then the placeholder.
    lens = (inner_left + 30 * s, search_top + 27 * s)
    draw.ellipse(
        [lens[0] - 9 * s, lens[1] - 9 * s, lens[0] + 9 * s, lens[1] + 9 * s],
        outline=MUTED,
        width=2 * s,
    )
    draw.line(
        [(lens[0] + 7 * s, lens[1] + 7 * s), (lens[0] + 14 * s, lens[1] + 14 * s)],
        fill=MUTED,
        width=3 * s,
    )
    query_face = font(22 * s)
    query_x = inner_left + 56 * s
    draw.line(
        [(query_x, search_top + 16 * s), (query_x, search_top + 42 * s)], fill=ORANGE, width=2 * s
    )
    draw.text(
        (query_x + 8 * s, search_top + 29 * s),
        EXAMPLE_QUERY,
        font=query_face,
        fill=MUTED,
        anchor="lm",
    )

    row_top = search_top + 80 * s
    rows = example_rows(index)
    for record in rows:
        _result_card(draw, record, inner_left, row_top, inner_width, s=s)
        row_top += 118 * s
    draw.text(
        (inner_left + inner_width, (HEIGHT - 72) * s),
        f"{len(rows)} of {records:,} records",
        font=mono(15 * s),
        fill=MUTED,
        anchor="rs",
    )

    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--output", type=Path, default=Path("site/assets/og-card.png"))
    args = parser.parse_args()
    _assert_scalable_fonts()
    path = render(load_index(args.index), args.output)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
