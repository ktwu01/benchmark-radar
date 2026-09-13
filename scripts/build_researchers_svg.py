#!/usr/bin/env python3
"""Regenerate assets/researchers.svg from the official logos in assets/researchers-logos/.

Each file in assets/researchers-logos/ is the official institution logo as
downloaded from Wikimedia Commons / Wikipedia. Run this script after adding,
removing, or replacing a logo there:

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
    ["amazon.svg", "google.svg", "bytedance.svg", "alibaba.svg"],
    ["stepfun.png", "kuaishou.png", "zhihu.svg"],
    ["cmu.svg", "auckland.svg", "tsinghua.svg", "sjtu.png",
     "harvard.svg", "mit.svg", "nus.svg"],
]

FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
H = 24          # logo target height
GAP = 26        # gap between logos in a row
ROW_H = 30      # row box height
ROW_GAP = 16
BOTTOM_PAD = 3
PNG_MAX_W = {"kuaishou.png": 1200, "sjtu.png": 120}


def load_svg(path):
    src = path.read_text(encoding="utf-8")
    src = re.sub(r"<\?xml[^>]*\?>", "", src)
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"<metadata[^>]*>.*?</metadata>", "", src, flags=re.S)
    src = re.sub(r"<sodipodi:[a-zA-Z-]+[^>]*/>", "", src)
    src = re.sub(r"\s+(sodipodi|inkscape):[a-zA-Z-]+=\"[^\"]*\"", "", src)
    m = re.search(r"<svg[^>]*>", src)
    end = src.rfind("</svg>")
    inner = src[m.end():end]
    vb = re.search(r'viewBox="([^"]+)"', src)
    if vb:
        _, _, w, h = (float(v) for v in vb.group(1).split())
    else:
        w = float(re.search(r'width="([\d.]+)"', src).group(1))
        h = float(re.search(r'height="([\d.]+)"', src).group(1))
    return inner, w, h


def prefix_ids(xml, prefix):
    xml = re.sub(r'id="([^"]+)"', f'id="{prefix}\\1"', xml)
    xml = re.sub(r'url\(#([^)]+)\)', f'url(#{prefix}\\1)', xml)
    xml = re.sub(r'xlink:href="#([^"]+)"', f'xlink:href="#{prefix}\\1"', xml)
    return xml


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
        return (f'<image x="0" y="0" width="{w * s:.2f}" height="{H}" '
                f'href="{uri}" preserveAspectRatio="xMidYMid meet"/>', w * s, H)
    inner, w, h = load_svg(path)
    s = H / h
    inner = prefix_ids(inner, f"l{idx}_")
    return f'<g transform="scale({s:.4f})">{inner}</g>', w * s, H


def build_row(items, y_bottom):
    total = sum(w for _, w, _ in items) + GAP * (len(items) - 1)
    out = []
    x = 0
    for inner, w, _ in items:
        out.append(f'<g transform="translate({x},{y_bottom - H - BOTTOM_PAD})">{inner}</g>')
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
        y += ROW_H + ROW_GAP
    height = y - ROW_GAP
    width = max(w for _, w in rows)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width:.0f}" height="{height}" viewBox="0 0 {width:.0f} {height}">',
    ]
    for inner, w in rows:
        lines.append(f'<g transform="translate({(width - w) / 2:.1f},0)">{inner}</g>')
    lines.append("</svg>")
    out = "\n".join(lines)
    try:
        ET.fromstring(out)
    except ET.ParseError:
        print(out, file=sys.stderr)
        raise
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({width:.0f}x{height}, {len(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()