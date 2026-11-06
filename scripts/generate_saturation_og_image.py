"""Render the share card for the /saturation/ page.

This is the score-plateau card every page shared before 2026-10-25, kept for
the one page it describes: reported score frontiers over time and their
approach to a ceiling, drawn from the same score data as the saturation view.
Every other page shares the search card from generate_og_image.py.

The record and source counts are read from the built catalog at deploy time, as
on the main card, so a shared link never advertises a number the catalog has
moved past (principle.md).
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from generate_og_image import (
    BLUE,
    CANVAS,
    DEFAULT_INDEX_PATH,
    EDGE,
    HEIGHT,
    LINE,
    MARGIN,
    MUTED,
    ORANGE,
    PANEL,
    SCALE,
    SITE_INK,
    WIDTH,
    _assert_scalable_fonts,
    catalog_counts,
    font,
    load_index,
    mono,
    wordmark,
)
from PIL import Image, ImageDraw

from benchmark_radar.benchmark_scores import DEFAULT_SCORES_PATH, build_score_progression

DEFAULT_OUTPUT = Path("site/assets/og-card-saturation.png")
COLORS = ("#2A7F8E", "#D26A3A", "#6D58A6", "#3D8B5D")
CHART_BENCHMARKS = ("gpqa_diamond", "hle", "terminal_bench", "swe_bench_verified")


def _short_name(name: str) -> str:
    return {
        "Gpqa Diamond": "GPQA",
        "Hle": "HLE",
        "Swe Bench Verified": "SWE-bench",
    }.get(name, name)


def _date_position(value: str, first: date, span: int, left: int, width: int) -> int:
    return left + round((date.fromisoformat(value) - first).days / span * width)


def render(progression: dict, index: dict, output: Path) -> Path:
    """Lay the card out like the main one: words on the left, the chart on the right."""
    records = [
        progression["benchmarks"][benchmark_id]
        for benchmark_id in CHART_BENCHMARKS
        if benchmark_id in progression.get("benchmarks", {})
    ]
    if not records:
        raise ValueError("score progression contains no configured chart benchmarks")

    s = SCALE
    image = Image.new("RGB", (WIDTH * s, HEIGHT * s), CANVAS)
    draw = ImageDraw.Draw(image)

    # Left: what the page shows, in words a newcomer can repeat.
    left = MARGIN * s
    wordmark(draw, left, 56 * s, s=s)
    headline = font(46 * s, bold=True)
    for offset, line in enumerate(("Where benchmark", "scores start", "to plateau.")):
        draw.text((left, (140 + offset * 58) * s), line, font=headline, fill=SITE_INK)
    body = font(22 * s)
    for offset, line in enumerate(("Best reported score over time,", "from cited model reports.")):
        draw.text((left, (330 + offset * 32) * s), line, font=body, fill=MUTED)

    benchmark_count, source_count = catalog_counts(index)
    figure = font(40 * s, bold=True)
    draw.text((left, 438 * s), f"{benchmark_count:,}", font=figure, fill=SITE_INK)
    figure_width = draw.textlength(f"{benchmark_count:,}", font=figure)
    draw.text(
        (left + figure_width + 14 * s, 466 * s),
        f"benchmark records from {source_count} sources",
        font=font(19 * s),
        fill=MUTED,
        anchor="ls",
    )
    draw.line([(left, 520 * s), (left + 64 * s, 520 * s)], fill=ORANGE, width=4 * s)
    draw.text((left, 548 * s), "benchmark-radar.org/saturation", font=mono(22 * s), fill=BLUE)

    # Right: the score frontiers, in a panel like the main card's search box.
    panel_left, panel_right = 600 * s, (WIDTH - 48) * s
    panel_top, panel_bottom = 48 * s, (HEIGHT - 48) * s
    draw.rounded_rectangle(
        [panel_left, panel_top, panel_right, panel_bottom],
        radius=14 * s,
        fill=PANEL,
        outline=EDGE,
        width=s,
    )
    inner_left, inner_right = panel_left + 28 * s, panel_right - 28 * s
    draw.text(
        (inner_left, panel_top + 36 * s),
        "Best reported score, %",
        font=mono(15 * s),
        fill=MUTED,
        anchor="lm",
    )
    axis = mono(14 * s)
    plot_left, plot_right = inner_left + 40 * s, inner_right
    top, bottom = panel_top + 76 * s, panel_top + 364 * s
    plot_width, plot_height = plot_right - plot_left, bottom - top
    for value in (0, 25, 50, 75, 100):
        grid_y = bottom - round(value / 100 * plot_height)
        draw.line([(plot_left, grid_y), (plot_right, grid_y)], fill=LINE, width=s)
        draw.text((plot_left - 10 * s, grid_y), str(value), font=axis, fill=MUTED, anchor="rm")

    first = min(date.fromisoformat(record["first_reported_at"]) for record in records)
    last = max(date.fromisoformat(record["last_reported_at"]) for record in records)
    span = max((last - first).days, 1)
    legend = font(17 * s)
    for position, record in enumerate(records):
        color = COLORS[position]
        xy = []
        for point in record["historical_best_frontier"]["points"]:
            x = _date_position(point["reported_at"], first, span, plot_left, plot_width)
            value = max(0, min(100, float(point["value"])))
            xy.append((x, bottom - round(value / 100 * plot_height)))
        if len(xy) > 1:
            draw.line(xy, fill=color, width=4 * s, joint="curve")
        for x, point_y in xy:
            draw.ellipse([x - 5 * s, point_y - 5 * s, x + 5 * s, point_y + 5 * s], fill=color)

        legend_x = inner_left + (position % 2) * 250 * s
        legend_y = bottom + (62 + (position // 2) * 32) * s
        draw.ellipse([legend_x, legend_y - 6 * s, legend_x + 12 * s, legend_y + 6 * s], fill=color)
        draw.text(
            (legend_x + 22 * s, legend_y),
            _short_name(record["benchmark_id"].replace("_", " ").title()),
            font=legend,
            fill=SITE_INK,
            anchor="lm",
        )

    draw.text((plot_left, bottom + 10 * s), first.strftime("%b %Y"), font=axis, fill=MUTED)
    draw.text(
        (plot_right, bottom + 10 * s), last.strftime("%b %Y"), font=axis, fill=MUTED, anchor="ra"
    )

    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES_PATH)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    _assert_scalable_fonts()
    path = render(build_score_progression(args.scores), load_index(args.index), args.output)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
