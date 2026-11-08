#!/usr/bin/env python3
"""Regenerate assets/researchers.svg from the official logos in assets/researchers-logos/.

Each file in assets/researchers-logos/ is the official institution logo as
downloaded from Wikimedia Commons / Wikipedia, or supplied by the organization
where Commons has none (xtracta.svg: Xtracta's official full-colour RGB logo,
unmodified). zai.svg is the 2025 Z.ai logo from Wikimedia Commons
(File:Z.ai (company logo).svg); antgroup.png is the Ant Group logo from the
company's media library, via en.wikipedia File:Ant_Group_logo.png.
berkeley.svg is the University of California, Berkeley 2024 logo from
en.wikipedia File:University_of_California,_Berkeley_Logo_2024.svg
(public domain — typefaces only; trademarked). tesla.svg is the Tesla, Inc.
black-script wordmark from Wikimedia Commons
(File:Tesla,_Inc._-_Logo_(black_script_version).svg). Run this
script after adding, removing, or replacing a logo there:

    python scripts/build_researchers_svg.py

The strip layout (row order and file names) is defined in ROWS below.
"""

import base64
import io
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = REPO_ROOT / "assets" / "researchers-logos"
OUT = REPO_ROOT / "assets" / "researchers.svg"

ROWS = [
    ["google.svg", "amazon.svg", "aws.svg", "ibm.svg", "tesla.svg"],
    ["cmu.svg", "harvard.svg", "mit.svg", "berkeley.svg", "nus.svg", "auckland.svg", "xtracta.svg"],
    ["alibaba.svg", "hunyuan.svg", "qwen.svg", "bytedance.svg", "antgroup.png", "zai.svg"],
    [
        "stepfun.png",
        "kuaishou.png",
        "zhihu.svg",
        "tsinghua.svg",
        "sjtu.png",
        "tencent.svg",
    ],
    # Row 5 (issue #735): the remaining verified institutions. moreGeo and
    # Kultiva have no official logo on Wikimedia Commons, so they stay out.
    [
        "hebrew-university.svg",
        "fudan.svg",
        "chungnam.png",
        "rise.svg",
        "york.svg",
    ],
]

FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
H = 24  # logo target height
GAP = 26  # gap between logos in a row
ROW_H = 30  # row box height
ROW_GAP = 16
BOTTOM_PAD = 3
# Logos that look oversized at the common height.
LOGO_SCALE = {"alibaba.svg": 0.6, "tesla.svg": 0.6}
PNG_MAX_W = {"kuaishou.png": 1200, "sjtu.png": 120, "chungnam.png": 400}
# Many wordmarks are dark (Amazon, Qwen, Zhihu, StepFun, Xtracta), so the strip
# carries its own light backing: on GitHub's dark theme it would otherwise sit
# on a near-black canvas and those names would all but disappear.
BACKING = "#ffffff"
BACKING_PAD = 12
BACKING_RADIUS = 10


def load_svg(path):
    src = path.read_text(encoding="utf-8")
    src = re.sub(r"<\?xml[^>]*\?>", "", src)
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"<metadata[^>]*>.*?</metadata>", "", src, flags=re.S)
    src = re.sub(r"<sodipodi:[a-zA-Z-]+[^>]*/>", "", src)
    src = re.sub(r"\s+(sodipodi|inkscape):[a-zA-Z-]+=\"[^\"]*\"", "", src)
    src = re.sub(r"[ \t]+$", "", src, flags=re.M)
    m = re.search(r"<svg[^>]*>", src)
    end = src.rfind("</svg>")
    inner = src[m.end() : end]
    vb = re.search(r'viewBox="([^"]+)"', src)
    if vb:
        _, _, w, h = (float(v) for v in vb.group(1).split())
    else:
        w = float(re.search(r'width="([\d.]+)"', src).group(1))
        h = float(re.search(r'height="([\d.]+)"', src).group(1))
    return inner, w, h


def prefix_ids(xml, prefix):
    xml = re.sub(r'id="([^"]+)"', f'id="{prefix}\\1"', xml)
    xml = re.sub(r"url\(#([^)]+)\)", f"url(#{prefix}\\1)", xml)
    xml = re.sub(r'xlink:href="#([^"]+)"', f'xlink:href="#{prefix}\\1"', xml)
    return xml


def prefix_classes(xml, prefix):
    """Scope an SVG's CSS classes to one logo, as prefix_ids does for ids.

    Illustrator exports name classes .st0, .st1, ...; two logos in one strip
    can define the same class differently (Tsinghua's .st0 is purple, Z.ai's
    is light grey), and the later <style> block would win for both. Rewrite
    the selectors inside <style> blocks and the class attributes that use
    them, so each logo keeps its own definitions.
    """

    def _prefix_style(match):
        style = re.sub(r"\.([A-Za-z_][\w-]*)", f".{prefix}\\1", match.group(2))
        return f"<style{match.group(1)}>{style}</style>"

    xml = re.sub(r"<style([^>]*)>(.*?)</style>", _prefix_style, xml, flags=re.S)

    def _prefix_attr(match):
        names = " ".join(f"{prefix}{name}" for name in match.group(1).split())
        return f'class="{names}"'

    return re.sub(r'class="([^"]+)"', _prefix_attr, xml)


def png_data_uri(path, max_w):
    im = Image.open(path)
    if im.mode not in ("RGBA", "RGB"):
        im = im.convert("RGBA")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def logo_item(filename, idx):
    path = LOGO_DIR / filename
    if not path.exists():
        raise SystemExit(f"missing logo: {path}")
    if filename.lower().endswith(".png"):
        uri = png_data_uri(path, PNG_MAX_W.get(filename, 1200))
        with Image.open(path) as im:
            w, h = im.size
        s = H / h
        return (
            f'<image x="0" y="0" width="{w * s:.2f}" height="{H}" '
            f'href="{uri}" preserveAspectRatio="xMidYMid meet"/>',
            w * s,
            H,
        )
    inner, w, h = load_svg(path)
    s = H / h * LOGO_SCALE.get(filename, 1)
    inner = prefix_ids(inner, f"l{idx}_")
    inner = prefix_classes(inner, f"l{idx}_")
    return f'<g transform="scale({s:.4f})">{inner}</g>', w * s, h * s


def build_row(items, y_bottom):
    total = sum(w for _, w, _ in items) + GAP * (len(items) - 1)
    out = []
    x = 0
    for inner, w, h in items:
        y = y_bottom - H - BOTTOM_PAD + (H - h) / 2
        out.append(f'<g transform="translate({x},{y:.2f})">{inner}</g>')
        x += w + GAP
    return "".join(out), total


def main():
    rows = []
    y = ROW_H
    idx = 0
    for filenames in ROWS:
        items = [logo_item(fn, i) for i, fn in enumerate(filenames, idx)]
        idx += len(filenames)
        inner, w = build_row(items, y)
        rows.append((inner, w))
        content_h = y  # bottom of the last row placed
        y += ROW_H + ROW_GAP
    content_w = max(w for _, w in rows)
    width = round(content_w) + 2 * BACKING_PAD
    height = content_h + 2 * BACKING_PAD

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="{BACKING_RADIUS}" fill="{BACKING}"/>',
    ]
    for inner, w in rows:
        x = BACKING_PAD + (round(content_w) - w) / 2
        lines.append(f'<g transform="translate({x:.1f},{BACKING_PAD})">{inner}</g>')
    lines.append("</svg>")
    out = "\n".join(lines)
    try:
        ET.fromstring(out)
    except ET.ParseError:
        print(out, file=sys.stderr)
        raise
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({width}x{height}, {len(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
