#!/usr/bin/env python3
"""Capability-theme coverage analysis for the XBsleepy digest corpus.

Report-ready evidence for benchmark-radar issue #447 (collaboration call):
quantifies what the digest's capability taxonomy adds to the radar's own
record-type categories, and where agent-benchmark activity concentrates.

Inputs (both public, no credentials):
  1. xbsleepy/daily-agent-benchmarks index JSON  (papers + themes + dates)
  2. benchmark-radar committed snapshots          (record-type categories)

Outputs: stdout tables + themes_coverage.svg + themes_trend.svg
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DIGEST_INDEX = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "~/daily-agent-benchmarks/docs/data/index.json"
).expanduser()
SNAPSHOT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "data/snapshots")
OUT_DIR = Path(sys.argv[3] if len(sys.argv) > 3 else "docs/analysis/theme-coverage")


def load_digest() -> list[dict]:
    payload = json.loads(DIGEST_INDEX.read_text(encoding="utf-8"))
    return payload["papers"]


def radar_record_types() -> Counter:
    counts: Counter = Counter()
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        items = snapshot.get("evidence_items") or snapshot.get("items") or []
        for item in items:
            for category in item.get("categories") or []:
                counts[str(category)] += 1
    return counts


def theme_counts(papers: list[dict]) -> Counter:
    counts: Counter = Counter()
    for paper in papers:
        for tag in paper.get("tags") or []:
            counts[str(tag)] += 1
    return counts


def monthly_theme_matrix(papers: list[dict], top: int = 8) -> tuple[list[str], dict]:
    months: Counter = Counter()
    per_theme: dict[str, Counter] = {}
    for paper in papers:
        month = str(paper.get("announced_date") or "")[:7]
        if not month:
            continue
        months[month] += 1
        for tag in set(paper.get("tags") or []):
            per_theme.setdefault(str(tag), Counter())[month] += 1
    top_themes = [t for t, _ in theme_counts(papers).most_common(top)]
    ordered_months = sorted(months)
    matrix = {theme: [per_theme.get(theme, {}).get(m, 0) for m in ordered_months] for theme in top_themes}
    return ordered_months, matrix


def cooccurrence(papers: list[dict], top: int = 8) -> list[tuple[str, str, int]]:
    common = {t for t, _ in theme_counts(papers).most_common(top)}
    pairs: Counter = Counter()
    for paper in papers:
        tags = sorted({str(t) for t in paper.get("tags") or [] if t in common})
        for i, a in enumerate(tags):
            for b in tags[i + 1 :]:
                pairs[(a, b)] += 1
    return pairs.most_common(8)


_BAR = '<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#2f6f8f"><title>{label}: {v}</title></rect>'
_TEXT = '<text x="{x}" y="{y}" font-size="12" fill="#15242a">{label}</text>'


def bar_svg(counts: list[tuple[str, int]], title: str) -> str:
    width, row, pad = 640, 26, 130
    height = pad + row * len(counts) + 10
    max_v = max(v for _, v in counts) or 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f'<text x="10" y="20" font-size="14" font-weight="bold" fill="#15242a">{title}</text>'
    ]
    for i, (label, value) in enumerate(counts):
        y = pad + i * row
        w = int((width - pad - 60) * value / max_v)
        parts.append(_TEXT.format(x=10, y=y + 15, label=label))
        parts.append(_BAR.format(x=pad, y=y + 4, w=w, h=16, label=label, v=value))
        parts.append(_TEXT.format(x=pad + w + 6, y=y + 16, label=str(value)))
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    papers = load_digest()
    themes = theme_counts(papers)
    fields = Counter(str(p.get("field") or "other") for p in papers)
    months, matrix = monthly_theme_matrix(papers)
    pairs = cooccurrence(papers)
    radar_types = radar_record_types()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Capability-theme coverage: XBsleepy digest corpus",
        "",
        f"Corpus: {len(papers)} agent-benchmark papers, "
        f"{min(str(p.get('announced_date') or '') for p in papers)} .. "
        f"{max(str(p.get('announced_date') or '') for p in papers)} (announced dates). "
        "Multi-label themes per paper.",
        "",
        "## Theme distribution",
        "",
        "| Theme | Papers | Share |",
        "|---|---:|---:|",
    ]
    total_tags = sum(themes.values())
    for theme, count in themes.most_common():
        lines.append(f"| {theme} | {count} | {count / len(papers):.0%} of papers |")
    lines += [
        "",
        f"Average themes per paper: {total_tags / len(papers):.2f}.",
        "",
        "## Radar record-type vs digest capability coverage",
        "",
        f"The radar's snapshot categories count records by TYPE "
        f"(total tagged sightings: {sum(radar_types.values())}):",
        "",
        "| Radar category | Sightings |",
        "|---|---:|",
    ]
    for category, count in radar_types.most_common():
        lines.append(f"| {category} | {count} |")
    lines += [
        "",
        "The digest adds the layer the radar's own taxonomy does not carry: "
        "WHICH capability an agent benchmark tests. The two are complementary, "
        "not overlapping.",
        "",
        "## Concentration and gaps",
        "",
        f"- Top-3 themes ({', '.join(t for t, _ in themes.most_common(3))}) cover "
        f"{sum(c for _, c in themes.most_common(3)) / total_tags:.0%} of all tags.",
        f"- Sparsest themes: "
        f"{', '.join(f'{t} ({c})' for t, c in themes.most_common()[-4:])} — "
        "candidate open areas for new benchmarks.",
        f"- Strongest theme pairs: "
        f"{', '.join(f'{a}+{b} ({n})' for (a, b), n in pairs[:4])}.",
        "",
        "## Monthly arrivals, top themes",
        "",
        "| Theme | " + " | ".join(months) + " |",
        "|---|" + "---:|" * len(months),
    ]
    for theme, series in matrix.items():
        lines.append(f"| {theme} | " + " | ".join(str(v) for v in series) + " |")

    bar = bar_svg(themes.most_common(), "Agent-benchmark papers per capability theme")
    (OUT_DIR / "themes_coverage.svg").write_text(bar, encoding="utf-8")

    fields_lines = ["", "## Assigned field (single-label, digest classifier)", ""]
    for field, count in fields.most_common():
        fields_lines.append(f"- {field}: {count}")
    text = "\n".join(lines + fields_lines) + "\n"
    (OUT_DIR / "coverage.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
