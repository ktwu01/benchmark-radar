#!/usr/bin/env python3
"""Minify the dashboard stylesheet for the published site (SEO issue).

GitHub Pages serves the committed source CSS as-is, so a page that carries 100
KB of hand-written styles ships all of it. This script strips comments and
blank runs from the stylesheet in place during the Pages build. It is
deliberately conservative: it only removes `/* ... */` comments and trims
whitespace, never reorders rules, renames selectors, or collapses the last
semicolon, so the rendered page cannot change. JavaScript is left alone; a
355 KB handwritten module with strings, templates, and regexes is not worth
regex-minifying for a cosmetic factor.

Usage: python scripts/minify_css.py site/assets/styles.css
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TOKEN = re.compile(r"/\*.*?\*/" r"|\"(?:\\.|[^\"\\])*\"" r"|'(?:\\.|[^'\\])*'", flags=re.DOTALL)
_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")
_BLANK_RUN = re.compile(r"\n{3,}")


def minify_css(source: str) -> str:
    """Return the stylesheet with comments and blank runs removed."""
    # Match comments and strings in one pass: quotes inside comments cannot
    # hide the terminator, and comment markers inside strings remain literal.
    cleaned = _TOKEN.sub(
        lambda match: "" if match.group(0).startswith("/*") else match.group(0), source
    )
    cleaned = _TRAILING_WS.sub("", cleaned)
    return _BLANK_RUN.sub("\n\n", cleaned).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(f"usage: {Path(sys.argv[0]).name} <stylesheet.css>", file=sys.stderr)
        return 2
    path = Path(args[0])
    source = path.read_text(encoding="utf-8")
    minified = minify_css(source)
    path.write_text(minified, encoding="utf-8")
    saved = len(source.encode("utf-8")) - len(minified.encode("utf-8"))
    print(f"minified {path}: {saved / 1024:.0f} KiB saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
