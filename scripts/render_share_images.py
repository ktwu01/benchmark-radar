"""Render a day's share images from its snapshot (issue #671).

The images travel to X, WeChat groups and Discord on their own. WeChat does
not make a pasted URL clickable, so the bottom-right domain is the only way a
reader there finds the site again.

Input is the ``share`` block the daily run wrote into the snapshot; nothing
here reads the network, so a snapshot always renders the same images. Output:

- top3.png: the first three cards in one portrait (4:5) image, which X, WeChat
  and Discord all show uncropped on a phone.
- card-NN.png: one 1200x630 card per benchmark in the block, the size X and
  most chat apps use for a link preview.

With ``--catalog site/data/benchmark-index.json`` it renders one 1200x630
card per catalog benchmark instead, named ``<slug>.png``, in the look of the
site's link preview. The Pages workflow pushes them to the ``cards`` branch,
where each benchmark's Share button finds its card. Every record gets one: a
benchmark without a date, publisher or score keeps its card and leaves that
fact out.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from benchmark_radar.cards import benchmark_card_name
from benchmark_radar.daily_top import DEFAULT_LIMIT, card_image_name
from benchmark_radar.site_pages import _SAFE_SLUG
from benchmark_radar.site_shell import SOURCE_LABELS

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_og_image import (  # noqa: E402
    BACKGROUND,
    BLUE,
    CANVAS,
    EDGE,
    INK,
    LIGHT,
    MUTED,
    PANEL,
    SCALE,
    SITE_INK,
    SLATE,
    TEAL,
    _assert_scalable_fonts,
    _chip,
    _radar_mark,
    font,
    mono,
)

WATERMARK = "benchmark-radar.org"
MARGIN = 64
TOP_SIZE = (1080, 1350)
CARD_SIZE = (1200, 630)

# Every radar item is some mix of these, so naming them on a card tells the
# reader nothing. The topical categories after them (agentic, multimodal) do.
GENERIC_CATEGORIES = frozenset({"benchmark", "evaluation", "dataset"})

# The images are English only and DejaVu has no CJK glyphs, so "Vivien Jiaqian
# Zhu 朱佳谦" would end in empty boxes.
_CJK = re.compile(r"[　-ヿ㐀-鿿가-힯＀-￯]+")

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def _plain(text: str) -> str:
    # DataCite descriptions arrive as escaped HTML ("&lt;h3&gt;Recommended
    # Citation"), sometimes escaped twice.
    for _ in range(2):
        text = html.unescape(text)
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    latin = " ".join(_CJK.sub(" ", text).split())
    return latin or text


def _fit(text: str, face: Font, width: int) -> str:
    """Return ``text`` cut to ``width`` with an ellipsis when it does not fit."""
    if face.getlength(text) <= width:
        return text
    # Binary search: abstracts run to thousands of characters, and trimming one
    # character per measurement made a week of images take minutes.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if face.getlength(text[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip(" ,·;:-") + "…"


def _wrap(text: str, face: Font, width: int, max_lines: int) -> list[str]:
    if max_lines <= 0:
        return []
    words = _plain(text).split(" ")
    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if face.getlength(trial) <= width:
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
    shown = ", ".join(values[:limit])
    return _plain(f"{shown} et al." if len(values) > limit else shown)


def _institutions(values: list[str]) -> str:
    # Institution names carry commas ("University of California, Berkeley").
    shown = "; ".join(values[:2])
    return _plain(f"{shown} +{len(values) - 2}" if len(values) > 2 else shown)


def _day(value: Any) -> str:
    try:
        return date.fromisoformat(str(value or "")[:10]).strftime("%b %-d, %Y")
    except ValueError:
        return ""


def _meta_line(card: dict[str, Any]) -> str:
    topics = [
        str(name).replace("_", " ")
        for name in card.get("categories") or []
        if str(name).casefold() not in GENERIC_CATEGORIES
    ]
    parts = [str(card.get("source") or ""), _day(card.get("published_at")), *topics[:2]]
    return " · ".join(part for part in parts if part)


def _block(
    draw: ImageDraw.ImageDraw,
    card: dict[str, Any],
    x: int,
    y: int,
    width: int,
    bottom: int,
    *,
    title_size: int,
    title_lines: int,
    scale: float = 1.0,
) -> None:
    """Draw one benchmark from ``y`` down, no lower than ``bottom``."""
    body = round(22 * scale)
    step = round(body * 1.33)
    title_face = font(title_size, bold=True)
    for line in _wrap(str(card.get("title") or ""), title_face, width, title_lines):
        draw.text((x, y), line, font=title_face, fill=INK)
        y += round(title_size * 1.27)
    y += round(6 * scale)
    if card.get("authors"):
        face = font(body + 1)
        draw.text((x, y), _fit(_names(card["authors"], 3), face, width), font=face, fill=INK)
        y += step + 2
    if card.get("affiliations"):
        face = font(body + 1, bold=True)
        text = _fit(_names(card["affiliations"], 2), face, width)
        draw.text((x, y), text, font=face, fill=TEAL)
        y += step + 2
    y += round(6 * scale)
    meta = font(round(19 * scale))
    meta_height = round(19 * scale) + 8
    summary = font(body)
    lines = max(0, (bottom - meta_height - y) // step)
    for line in _wrap(str(card.get("blurb") or ""), summary, width, lines):
        draw.text((x, y), line, font=summary, fill=SLATE)
        y += step
    draw.text((x, y + 8), _meta_line(card), font=meta, fill=SLATE)


def _canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 12, size[1]], fill=TEAL)
    return image, draw


def _save(image: Image.Image, draw: ImageDraw.ImageDraw, output: Path) -> Path:
    width, height = image.size
    draw.text(
        (width - MARGIN, height - 40),
        WATERMARK,
        font=font(30, bold=True),
        fill=TEAL,
        anchor="rs",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Text on a flat background needs few colours; a palette PNG is about a
    # third of the size, which matters once every catalog benchmark has one.
    image.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(output, optimize=True)
    return output


def render_top(cards: list[dict[str, Any]], day: str, output: Path) -> Path:
    image, draw = _canvas(TOP_SIZE)
    width = TOP_SIZE[0] - 2 * MARGIN - 70
    draw.text((MARGIN, 58), "Benchmark Radar", font=font(50, bold=True), fill=INK)
    heading = f"Top {len(cards)} benchmarks · {_day(day)}"
    draw.text((MARGIN, 124), heading, font=font(30), fill=TEAL)
    row_top, row_height = 210, 340
    draw.line([(MARGIN, row_top - 24), (TOP_SIZE[0] - MARGIN, row_top - 24)], fill=LIGHT, width=2)
    for index, card in enumerate(cards):
        top = row_top + index * row_height
        draw.text((MARGIN, top), str(index + 1), font=font(44, bold=True), fill=TEAL)
        x = MARGIN + 70
        _block(
            draw,
            card,
            x,
            top,
            width,
            top + row_height - 24,
            title_size=34,
            title_lines=2,
            scale=1.2,
        )
        if index < len(cards) - 1:
            divider = top + row_height - 16
            draw.line([(x, divider), (TOP_SIZE[0] - MARGIN, divider)], fill=LIGHT, width=1)
    return _save(image, draw, output)


def render_card(card: dict[str, Any], label: str, output: Path) -> Path:
    """One benchmark on a 1200x630 card; ``label`` names where it was featured."""
    image, draw = _canvas(CARD_SIZE)
    width = CARD_SIZE[0] - 2 * MARGIN
    draw.text((MARGIN, 40), f"Benchmark Radar · {label}", font=font(24, bold=True), fill=TEAL)
    _block(
        draw, card, MARGIN, 96, width, CARD_SIZE[1] - 80, title_size=44, title_lines=3, scale=1.3
    )
    return _save(image, draw, output)


def render_day(snapshot: dict[str, Any], output_dir: Path) -> list[Path]:
    share = snapshot.get("share") or {}
    cards = share.get("cards") or []
    if not cards:
        return []
    day = str(share.get("date") or snapshot.get("date"))
    label = f"Daily briefing · {_day(day)}"
    written = [render_top(cards[:DEFAULT_LIMIT], day, output_dir / "top3.png")]
    for index, card in enumerate(cards, start=1):
        written.append(render_card(card, label, output_dir / card_image_name(index)))
    return written


def _benchmark_meta(record: dict[str, Any]) -> str:
    return " · ".join(
        part
        for part in (_plain(str(record.get("publisher") or "")), _day(record.get("released")))
        if part
    )


def render_benchmark(record: dict[str, Any], output: Path) -> Path:
    """One catalog benchmark on a 1200x630 card in the site's own look.

    The layout follows site/assets/og-card.png, so a shared card and a shared
    link look like the same product. A fact the record does not hold is left
    off; the card itself is never skipped.
    """
    s = SCALE
    width, height = CARD_SIZE
    image = Image.new("RGB", (width * s, height * s), CANVAS)
    draw = ImageDraw.Draw(image)
    left = MARGIN * s
    _radar_mark(draw, left, 40 * s, 40 * s)
    draw.text(
        (left + 54 * s, 60 * s), "Benchmark Radar", font=mono(20 * s), fill=SITE_INK, anchor="lm"
    )
    source = str(record.get("source") or "")
    label = SOURCE_LABELS.get(source, source)
    if label:
        draw.text(((width - MARGIN) * s, 60 * s), label, font=mono(16 * s), fill=MUTED, anchor="rm")

    panel = [left, 108 * s, (width - MARGIN) * s, 500 * s]
    draw.rounded_rectangle(panel, radius=14 * s, fill=PANEL, outline=EDGE, width=s)
    inner = left + 36 * s
    text_width = panel[2] - panel[0] - 72 * s
    y = 136 * s
    title_face = font(46 * s, bold=True)
    for line in _wrap(
        str(record.get("name") or record.get("slug") or ""), title_face, text_width, 2
    ):
        draw.text((inner, y), line, font=title_face, fill=SITE_INK)
        y += 58 * s
    y += 6 * s
    # Who made it is what researchers ask first (#933); only records whose
    # introducing paper names its authors carry them.
    authors = [str(name) for name in record.get("authors") or [] if str(name).strip()]
    if authors:
        face = font(22 * s, bold=True)
        draw.text(
            (inner, y + 4 * s), _fit(_names(authors, 3), face, text_width), font=face, fill=SITE_INK
        )
        y += 36 * s
    # Where it came from, as OpenAlex links the same paper; the first two keep
    # one line, and "+N" says the list goes on.
    institutions = [str(name) for name in record.get("institutions") or [] if str(name).strip()]
    if institutions:
        face = font(20 * s)
        draw.text(
            (inner, y + 4 * s),
            _fit(_institutions(institutions), face, text_width),
            font=face,
            fill=SITE_INK,
        )
        y += 32 * s
    meta = _benchmark_meta(record)
    if meta:
        face = font(22 * s)
        draw.text((inner, y + 4 * s), _fit(meta, face, text_width), font=face, fill=BLUE)
        y += 40 * s
    chips_top = 440 * s
    body = font(22 * s)
    lines = max(0, (chips_top - 16 * s - (y + 14 * s)) // (31 * s))
    y += 14 * s
    for line in _wrap(str(record.get("description") or ""), body, text_width, lines):
        draw.text((inner, y), line, font=body, fill=MUTED)
        y += 31 * s
    chip_x = inner
    for flag, chip in (("has_paper", "Paper"), ("has_repo", "Code"), ("has_dataset", "Dataset")):
        if record.get(flag):
            chip_x = _chip(draw, chip_x, chips_top, chip, s=s)
    scores = int(record.get("score_count") or 0)
    if scores:
        _chip(draw, chip_x, chips_top, f"{scores:,} scores", s=s, strong=True)

    draw.text((left, 562 * s), WATERMARK, font=mono(26 * s), fill=BLUE)
    image = image.resize(CARD_SIZE, Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Octree keeps the small orange accents that median cut folds into grey,
    # and the file is a quarter of the RGB size across thousands of cards.
    image.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(output, optimize=True)
    return output


def _render_one(job: tuple[dict[str, Any], Path]) -> Path:
    return render_benchmark(*job)


def render_catalog(
    index: dict[str, Any], output_dir: Path, *, workers: int | None = None
) -> list[Path]:
    """One card per benchmark record in the catalog index, named by its slug."""
    jobs = []
    for record in index.get("benchmarks") or []:
        slug = str(record.get("slug") or "")
        if not _SAFE_SLUG.fullmatch(slug):
            raise ValueError(f"unsafe slug {slug!r} for {record.get('key')}")
        jobs.append((record, output_dir / benchmark_card_name(slug)))
    # About a tenth of a second per card, and the catalog has thousands.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_render_one, jobs, chunksize=32))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--snapshot", type=Path)
    inputs.add_argument("--catalog", type=Path, help="site/data/benchmark-index.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    _assert_scalable_fonts()
    if args.catalog:
        written = render_catalog(
            json.loads(args.catalog.read_text(encoding="utf-8")), args.output_dir
        )
        if not written:
            raise SystemExit(f"{args.catalog} has no benchmarks; run normalize-catalog first.")
        print(f"Wrote {len(written)} benchmark cards to {args.output_dir}")
        return
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    written = render_day(snapshot, args.output_dir)
    if not written:
        print(f"{args.snapshot} has no share cards; nothing rendered.")
    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
