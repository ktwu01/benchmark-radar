"""Render the Open Graph card for the repository and dashboard (issue #88).

Without a custom image, every share of this project on Slack, X, LinkedIn, or
Hacker News renders as a grey placeholder with a URL under it. The share is the
first and often only impression, and a blank card wastes it on a project whose
whole point is a specific, checkable finding.

So the card *is* the finding: the question, the top rows of the current ranking,
and the denominator they were counted against. A reader who never clicks still
learns what the project measured, and one who does arrives already knowing.

Generated from the same registry as the ranking, never hand-edited, so a card
advertising counts the registry no longer supports cannot survive a rebuild.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from benchmark_radar.model_cards import DEFAULT_REGISTRY_PATH, build_adoption_rank

# 1200x630 is the size Open Graph consumers crop to. Rendering at exactly that
# ratio is what keeps the bottom line from being cut off in a Slack unfurl.
WIDTH = 1200
HEIGHT = 630

# The report figures' palette, so a shared card and a figure from the same
# project do not look like they came from two different ones.
BACKGROUND = "#FAFAFA"
INK = "#1B2A4A"
TEAL = "#2A7F8E"
SLATE = "#6B7B8D"
LIGHT = "#DDE3E8"
PALE = "#EEF2F4"

MARGIN = 64
ROWS = 5


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _truncate(draw: ImageDraw.ImageDraw, text: str, typeface, limit: int) -> str:
    """Shorten to fit `limit` pixels, with an ellipsis when anything was cut.

    Benchmark names are registry data and a long one would otherwise run under
    the count column and collide with it. Measured rather than counted in
    characters, because the face is proportional: "Humanity's Last Exam" and
    "MMMU" differ far more in width than in length.
    """
    if draw.textlength(text, font=typeface) <= limit:
        return text
    ellipsis = "…"
    while text and draw.textlength(text + ellipsis, font=typeface) > limit:
        text = text[:-1]
    return text.rstrip() + ellipsis


def render(leaderboard: dict, output: Path) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # A teal spine rather than a full banner: it identifies the card at a
    # glance in a feed without spending vertical space the ranking needs.
    draw.rectangle([0, 0, 12, HEIGHT], fill=TEAL)

    title = font(46, bold=True)
    question = font(31)
    row_face = font(30)
    row_bold = font(30, bold=True)
    small = font(23)
    # A step down from `small`: the URL is provenance, not a line of the
    # finding, and the size difference is what buys it room on the caveat's
    # line without either being truncated.
    attribution = font(21)

    y = MARGIN - 12
    draw.text((MARGIN, y), "Benchmark Radar", font=title, fill=INK)
    y += 60
    draw.text(
        (MARGIN, y),
        "Which benchmarks do frontier labs actually report?",
        font=question,
        fill=TEAL,
    )
    y += 58

    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=LIGHT, width=2)
    y += 26

    count_x = WIDTH - MARGIN - 210
    org_x = WIDTH - MARGIN - 60
    draw.text((MARGIN, y), "BENCHMARK", font=small, fill=SLATE)
    draw.text((count_x, y), "CARDS", font=small, fill=SLATE, anchor="ra")
    draw.text((org_x, y), "ORGS", font=small, fill=SLATE, anchor="ra")
    y += 40

    row_height = 54
    for index, entry in enumerate(leaderboard["entries"][:ROWS]):
        # Zebra striping instead of rules: at feed thumbnail size, hairlines
        # between rows disappear while a fill still reads as separation.
        if index % 2 == 0:
            draw.rectangle(
                [MARGIN - 16, y - 10, WIDTH - MARGIN + 16, y + row_height - 16],
                fill=PALE,
            )
        rank = f"{entry['rank']}."
        draw.text((MARGIN, y), rank, font=row_face, fill=SLATE)
        name_x = MARGIN + 46
        name = _truncate(draw, entry["name"], row_bold, count_x - name_x - 90)
        draw.text((name_x, y), name, font=row_bold, fill=INK)
        draw.text((count_x, y), str(entry["card_count"]), font=row_face, fill=INK, anchor="ra")
        draw.text(
            (org_x, y),
            str(entry["organization_count"]),
            font=row_face,
            fill=SLATE,
            anchor="ra",
        )
        y += row_height

    y += 14
    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=LIGHT, width=2)
    y += 22

    draw.text(
        (MARGIN, y),
        (
            f"Across {leaderboard['model_card_count']} model cards from "
            f"{leaderboard['organization_count']} organizations, "
            f"tracking {leaderboard['benchmark_count']} benchmarks"
        ),
        font=small,
        fill=INK,
    )
    y += 32
    # The caveat travels on the card too. This image is the most widely seen
    # and least clicked-through representation of the ranking, so it is the
    # worst place to let a bare top-five read as a quality ordering.
    #
    # Phrased without a leading "Measures" so it clears the attribution to its
    # right. The two are measured to fit on one line at these faces with ~75px
    # between them; lengthening either, or raising `small`, will collide before
    # it wraps, because Pillow does not wrap.
    draw.text(
        (MARGIN, y),
        "Vendor reporting convention, not benchmark quality",
        font=small,
        fill=SLATE,
    )
    # The card is built to be reposted, and a screenshot of a ranking with no
    # source is a claim nobody can check. Bottom right, sharing the caveat's
    # baseline: an unfamiliar reader meets the attribution and the disclaimer
    # in one glance, and the footer has no room for a third line.
    draw.text(
        (WIDTH - MARGIN, y + 2),
        "github.com/ktwu01/benchmark-radar",
        font=attribution,
        fill=TEAL,
        anchor="ra",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--output", type=Path, default=Path("site/assets/og-card.png"))
    args = parser.parse_args()

    path = render(build_adoption_rank(args.registry), args.output)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
