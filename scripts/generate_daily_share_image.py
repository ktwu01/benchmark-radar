"""Render the day's top new benchmarks as one shareable image (issue #671).

The image travels to X, WeChat groups and Discord on its own. WeChat does not
make a pasted URL clickable, so the bottom-right domain is the only way a
reader there finds the site again. The image is portrait (4:5) because all
three apps show that ratio uncropped on a phone.

Each deploy writes one image per radar day for the last week, named by date,
so a daily social checklist keeps showing its own day after later deploys
replace the site. The newest is also copied to latest.png, a stable link to
share.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from benchmark_radar.daily_top import (
    DEFAULT_LIMIT,
    budgeted_fetchers,
    resolve_creators,
    select_top_items,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_og_image import (  # noqa: E402
    BACKGROUND,
    INK,
    LIGHT,
    SLATE,
    TEAL,
    _assert_scalable_fonts,
    font,
)

WIDTH = 1080
HEIGHT = 1350
MARGIN = 64
ROW_TOP = 210
ROW_HEIGHT = 262
WATERMARK = "benchmark-radar.org"
DEFAULT_RADAR_PATH = Path("site/data/radar.json")
DEFAULT_OUTPUT_DIR = Path("site/share/top4")
DAYS_BACK = 7

# Every radar item is some mix of these, so naming them on a row tells the
# reader nothing. The topical categories after them (agentic, multimodal) do.
GENERIC_CATEGORIES = frozenset({"benchmark", "evaluation", "dataset"})

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


# The image is English only and DejaVu has no CJK glyphs, so "Vivien Jiaqian
# Zhu 朱佳谦" would end in empty boxes.
_CJK = re.compile(r"[\u3000-\u30ff\u3400-\u9fff\uac00-\ud7af\uff00-\uffef]+")


def _plain(text: str) -> str:
    # DataCite descriptions arrive as escaped HTML ("&lt;h3&gt;Recommended
    # Citation"), sometimes escaped twice.
    for _ in range(2):
        text = html.unescape(text)
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    latin = " ".join(_CJK.sub(" ", text).split())
    return latin or text


def _width(text: str, face: Font) -> float:
    return face.getlength(text)


def _fit(text: str, face: Font, width: int) -> str:
    """Return ``text`` cut to ``width`` with an ellipsis when it does not fit."""
    if _width(text, face) <= width:
        return text
    # Binary search: abstracts run to thousands of characters, and trimming one
    # character per measurement made a week of images take minutes.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if _width(text[:middle] + "…", face) <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip(" ,·;:-") + "…"


def _wrap(text: str, face: Font, width: int, max_lines: int) -> list[str]:
    words = " ".join(str(text).split()).split(" ")
    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if _width(trial, face) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            current = " ".join([current, *words[index + 1 :]])
            break
    if current:
        lines.append(current)
    # Every line, not only the last: one Hugging Face "owner/repository" token
    # can be wider than the whole text area.
    return [_fit(line, face, width) for line in lines[:max_lines]]


def _names(values: list[str], limit: int) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    return f"{', '.join(values[:limit])} et al."


def _published(item: dict[str, Any]) -> str:
    value = str(item.get("published_at") or "")[:10]
    try:
        return date.fromisoformat(value).strftime("%b %-d, %Y")
    except ValueError:
        return ""


def _meta_line(item: dict[str, Any]) -> str:
    parts = [str(item.get("source") or ""), _published(item)]
    topics = [
        str(name).replace("_", " ")
        for name in item.get("categories") or []
        if str(name).casefold() not in GENERIC_CATEGORIES
    ]
    parts.extend(topics[:2])
    return " · ".join(part for part in parts if part)


def render(rows: list[dict[str, Any]], day: str, output: Path) -> Path:
    """Draw ``rows`` (item plus resolved creators) as the day's share image."""
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 12, HEIGHT], fill=TEAL)
    text_width = WIDTH - 2 * MARGIN - 70

    title_face = font(30, bold=True)
    author_face = font(23)
    affiliation_face = font(23, bold=True)
    summary_face = font(22)
    meta_face = font(19)

    draw.text((MARGIN, 58), "Benchmark Radar", font=font(50, bold=True), fill=INK)
    heading = date.fromisoformat(day).strftime("%b %-d, %Y")
    draw.text(
        (MARGIN, 124),
        f"Top {len(rows)} new benchmarks · {heading}",
        font=font(30),
        fill=TEAL,
    )
    draw.line([(MARGIN, ROW_TOP - 24), (WIDTH - MARGIN, ROW_TOP - 24)], fill=LIGHT, width=2)

    for index, row in enumerate(rows):
        item = row["item"]
        top = ROW_TOP + index * ROW_HEIGHT
        draw.text((MARGIN, top), str(index + 1), font=font(44, bold=True), fill=TEAL)
        x = MARGIN + 70
        y = top
        for line in _wrap(_plain(str(item.get("title") or "")), title_face, text_width, 2):
            draw.text((x, y), line, font=title_face, fill=INK)
            y += 38
        y += 4
        if row["authors"]:
            draw.text(
                (x, y),
                _fit(_plain(_names(row["authors"], 3)), author_face, text_width),
                font=author_face,
                fill=INK,
            )
            y += 31
        if row["affiliations"]:
            draw.text(
                (x, y),
                _fit(_plain(_names(row["affiliations"], 2)), affiliation_face, text_width),
                font=affiliation_face,
                fill=TEAL,
            )
            y += 35
        meta_top = top + ROW_HEIGHT - 50
        summary_lines = max(0, (meta_top - 6 - y) // 29)
        for line in _wrap(
            _plain(str(item.get("summary") or "")), summary_face, text_width, summary_lines
        ):
            draw.text((x, y), line, font=summary_face, fill=SLATE)
            y += 29
        draw.text((x, meta_top), _meta_line(item), font=meta_face, fill=SLATE)
        if index < len(rows) - 1:
            divider = top + ROW_HEIGHT - 16
            draw.line([(x, divider), (WIDTH - MARGIN, divider)], fill=LIGHT, width=1)

    draw.text(
        (WIDTH - MARGIN, HEIGHT - 44),
        WATERMARK,
        font=font(30, bold=True),
        fill=TEAL,
        anchor="rs",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return output


def build(
    radar_path: Path,
    output_dir: Path,
    *,
    days_back: int = DAYS_BACK,
    fetchers: tuple | None = None,
) -> list[Path]:
    radar = json.loads(radar_path.read_text(encoding="utf-8"))
    days = radar.get("days") or []
    dates = sorted({str(day.get("date")) for day in days if day.get("date")})[-days_back:]
    fetch, fetch_text = fetchers or budgeted_fetchers()
    written: dict[str, Path] = {}
    # Newest first: if the lookup budget runs out, older days lose
    # affiliations, not the image people share today.
    for day in reversed(dates):
        items = select_top_items(days, day, limit=DEFAULT_LIMIT)
        if not items:
            print(f"No new benchmarks on {day}; no share image written.")
            continue
        rows = [
            {"item": item, **resolve_creators(item, fetch=fetch, fetch_text=fetch_text)}
            for item in items
        ]
        written[day] = render(rows, day, output_dir / f"{day}.png")
    paths = [written[day] for day in sorted(written)]
    if paths:
        latest = output_dir / "latest.png"
        latest.write_bytes(paths[-1].read_bytes())
        paths.append(latest)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radar", type=Path, default=DEFAULT_RADAR_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    _assert_scalable_fonts()
    for path in build(args.radar, args.output_dir):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
