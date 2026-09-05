#!/usr/bin/env python3
"""Build the comprehensive Benchmark Radar system and data evaluation."""

# Keep ReportLab prose as readable source text.
# ruff: noqa: E501, E402, I001

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_technical_report import (
    AMBER,
    BLUE,
    BOLD,
    INK,
    ITALIC,
    MARGIN_X,
    MUTED,
    NAVY,
    PAGE_W,
    PALE_AMBER,
    PALE_TEAL,
    REGULAR,
    RULE,
    SKY,
    TEAL,
    WHITE,
    bullet,
    p,
    styles,
)
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Spacer,
    Table,
    TableStyle,
)
from benchmark_radar.saturation_audit import build_saturation_audit

GREEN = HexColor("#16794A")
PALE_GREEN = HexColor("#EAF7F0")
PURPLE = HexColor("#6D4AFF")
FROZEN_OUTPUT = Path("output/pdf/benchmark-radar-technical-report-v0.9.0.pdf")
NEXT_DRAFT_OUTPUT = Path("output/pdf/benchmark-radar-technical-report-next-draft.pdf")
FROZEN_AUTHORS = ("Koutian Wu",)
NEXT_DRAFT_AUTHORS = ("Koutian Wu", "Junjie Zhou", "Jiayu Wang")
NEXT_DRAFT_BYLINE = (
    "Koutian Wu<super>1,2,*</super>",
    "Junjie Zhou<super>3</super>",
    "Jiayu Wang<super>4</super>",
)
NEXT_DRAFT_AFFILIATIONS = (
    "<super>1</super> Independent researcher",
    "<super>2</super> Tacite AI",
    "<super>3</super> Hangzhou Dianzi University",
    "<super>4</super> Xi'an Jiaotong University",
)
NEXT_DRAFT_CORRESPONDING_AUTHOR = "Koutian Wu, k@tacite.ai"


def table(rows: list[list], widths: list[float], *, tiny: bool = False) -> Table:
    pad = 4 if tiny else 5
    return Table(
        rows,
        colWidths=widths,
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.42, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ]
        ),
    )


def figure(path: str, caption: str, st) -> list:
    """Scale a screenshot into the text column and return it with a caption."""
    reader = ImageReader(str(path))
    width_px, height_px = reader.getSize()
    scale = min((6.30 * inch) / width_px, (4.00 * inch) / height_px)
    image = Image(str(path), width=width_px * scale, height=height_px * scale)
    image.hAlign = "CENTER"
    style = ParagraphStyle(
        "FigCaption",
        parent=st["meta"],
        fontSize=6.4,
        leading=8.0,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceBefore=2,
        spaceAfter=12,
    )
    return [image, p(caption, style)]


def metric_strip(st) -> Table:
    values = ["7,540", "4,537", "1,242", "37"]
    labels = [
        "source observations<br/>across 37 snapshots",
        "unique artifacts in the<br/>cumulative evidence graph",
        "searchable entries<br/>across 4 search sources",
        "public collection<br/>sources monitored",
    ]
    cells = [
        [p(value, st["metric"]), p(label, st["metric_label"])]
        for value, label in zip(values, labels, strict=True)
    ]
    return Table(
        [cells],
        colWidths=[1.65 * inch] * 4,
        rowHeights=[0.76 * inch],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SKY),
                ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )


def search_surface(st) -> Table:
    input_box = Table(
        [
            [p("Search benchmarks, tasks, domains…", st["subtitle"])],
            [p("1,242 benchmarks  ·  4 sources", st["small"])],
        ],
        colWidths=[6.15 * inch],
        style=TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#AAB7C8")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, RULE),
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ]
        ),
    )
    return Table(
        [[p("Search every benchmark", st["callout"])], [input_box]],
        colWidths=[6.6 * inch],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SKY),
                ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ]
        ),
    )


def pipeline_figure() -> Drawing:
    drawing = Drawing(492, 101)
    boxes = [
        ("DISCOVER", "37 public sources"),
        ("VALIDATE", "health + schema"),
        ("RESOLVE", "exact identifiers"),
        ("INTERPRET", "taxonomy + rubric"),
        ("PUBLISH", "web, RSS, JSON"),
        ("QUERY", "offline CLI + HTTP"),
    ]
    box_w, gap = 72, 10
    for index, (title, caption) in enumerate(boxes):
        x = index * (box_w + gap)
        fill, stroke = (SKY, BLUE) if index % 2 == 0 else (PALE_TEAL, TEAL)
        drawing.add(
            Rect(x, 24, box_w, 51, 6, 6, fillColor=fill, strokeColor=stroke, strokeWidth=0.9)
        )
        drawing.add(
            String(
                x + box_w / 2,
                54,
                title,
                fontName=BOLD,
                fontSize=7.1,
                fillColor=NAVY,
                textAnchor="middle",
            )
        )
        drawing.add(
            String(
                x + box_w / 2,
                39,
                caption,
                fontName=REGULAR,
                fontSize=5.8,
                fillColor=MUTED,
                textAnchor="middle",
            )
        )
        if index < len(boxes) - 1:
            x1, x2 = x + box_w + 1, x + box_w + gap - 1
            drawing.add(Line(x1, 49, x2, 49, strokeColor=AMBER, strokeWidth=1.5))
            drawing.add(
                Polygon([x2, 49, x2 - 4, 52, x2 - 4, 46], fillColor=AMBER, strokeColor=AMBER)
            )
    drawing.add(
        String(
            246,
            6,
            "The same snapshots and code produce the same derived files.",
            fontName=ITALIC,
            fontSize=6.9,
            fillColor=MUTED,
            textAnchor="middle",
        )
    )
    return drawing


def source_bars() -> Drawing:
    drawing = Drawing(492, 157)
    entries = [
        ("Hugging Face", 2452, BLUE),
        ("GitHub", 2008, TEAL),
        ("arXiv", 1482, AMBER),
        ("Semantic Scholar", 877, PURPLE),
        ("OpenAlex", 557, HexColor("#14919B")),
        ("Seven other labels", 164, HexColor("#94A3B8")),
    ]
    maximum, x0, width = 2600, 112, 315
    for index, (label, value, color) in enumerate(entries):
        y = 134 - index * 22
        drawing.add(String(0, y + 2.5, label, fontName=REGULAR, fontSize=7.5, fillColor=INK))
        drawing.add(Rect(x0, y, width, 9, 4, 4, fillColor=HexColor("#EFF3F8"), strokeColor=None))
        drawing.add(
            Rect(x0, y, width * value / maximum, 9, 4, 4, fillColor=color, strokeColor=None)
        )
        drawing.add(
            String(
                x0 + width + 8, y + 1.5, f"{value:,}", fontName=BOLD, fontSize=7.4, fillColor=INK
            )
        )
    drawing.add(
        String(
            x0,
            1,
            "7,540 cumulative source observations through 29 August 2026",
            fontName=ITALIC,
            fontSize=6.9,
            fillColor=MUTED,
        )
    )
    return drawing


def _render_headroom(value: float | None) -> str:
    return "n/a" if value is None else f"{value:g}"


def saturation_audit_table(st, audit: dict) -> Table:
    rows = [
        [
            p("Benchmark", st["table_header"]),
            p("Raw gap", st["table_header"]),
            p("Same setup", st["table_header"]),
            p("Repeat gap", st["table_header"]),
            p("Claim decision", st["table_header"]),
            p("Note", st["table_header"]),
        ]
    ]
    for row in audit["benchmarks"]:
        repeated = row["selected_repeated_series"]
        if repeated is None:
            note = "no repeated setup"
        else:
            note = f"{repeated['dated_points']} dates · {repeated['organization_count']} org"
        rows.append(
            [
                p(row["name"], st["small_bold"]),
                p(_render_headroom(row["raw_headroom"]), st["small"]),
                p(f"{row['raw_best_stratum']['dated_points']} date", st["small"]),
                p(_render_headroom(row["repeat_controlled_headroom"]), st["small"]),
                p(row["recommendation"], st["small_bold"]),
                p(note, st["small"]),
            ]
        )
    return table(
        rows,
        [1.3 * inch, 0.65 * inch, 0.78 * inch, 0.78 * inch, 0.84 * inch, 2.25 * inch],
        tiny=True,
    )


def saturation_threshold_table(st, audit: dict) -> Table:
    rows = [
        [
            p("Threshold", st["table_header"]),
            p("Raw readings", st["table_header"]),
            p("Repeated setups", st["table_header"]),
        ]
    ]
    raw = audit["threshold_sensitivity"]["raw"]
    repeated = audit["threshold_sensitivity"]["repeated_protocol_series"]
    for threshold in ("<=5", "<=3", "<=2"):
        rows.append(
            [
                p(threshold, st["small_bold"]),
                p(f"{raw['hits'][threshold]} / {raw['eligible']}", st["small"]),
                p(
                    f"{repeated['hits'][threshold]} / {repeated['eligible']} "
                    f"({repeated['unknown']} unknown)",
                    st["small"],
                ),
            ]
        )
    return table(rows, [1.25 * inch, 1.55 * inch, 3.8 * inch], tiny=True)


def saturation_wording_table(st, audit: dict) -> Table:
    rows = [
        [
            p("Benchmark", st["table_header"]),
            p("Exact report wording", st["table_header"]),
        ]
    ]
    rows.extend(
        [p(row["name"], st["small_bold"]), p(row["recommended_wording"], st["small"])]
        for row in audit["benchmarks"]
    )
    return table(rows, [1.25 * inch, 5.35 * inch], tiny=True)


class EvaluationDoc(BaseDocTemplate):
    def __init__(self, filename: str, *, doi: str, authors: tuple[str, ...] = FROZEN_AUTHORS):
        super().__init__(
            filename,
            pagesize=letter,
            rightMargin=MARGIN_X,
            leftMargin=MARGIN_X,
            topMargin=0.58 * inch,
            bottomMargin=0.58 * inch,
            title="Benchmark Radar v0.9.0: Technical Report",
            author="; ".join(authors),
            subject="Benchmark Radar technical report, version 0.9.0",
            keywords="AI benchmarks, evaluation, research software, data provenance, model cards",
        )
        self.doi = doi
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=self._page))

    def _page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_X, 0.40 * inch, PAGE_W - MARGIN_X, 0.40 * inch)
        canvas.setFont(REGULAR, 6.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            MARGIN_X,
            0.22 * inch,
            "Benchmark Radar v0.9.0 Technical Report  |  https://github.com/ktwu01/benchmark-radar",
        )
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.22 * inch, str(doc.page))
        canvas.restoreState()


def story(
    doi: str,
    *,
    authors: tuple[str, ...] = FROZEN_AUTHORS,
    byline: tuple[str, ...] | None = None,
    affiliations: tuple[str, ...] = (),
    corresponding_author: str | None = None,
    draft: bool = False,
) -> list:
    st = styles()
    tiny = ParagraphStyle("Tiny", parent=st["small"], fontSize=6.45, leading=8.0)
    audit = build_saturation_audit() if draft else None
    saturation_section = (
        [
            p(
                "6.2 All eight raw near-ceiling readings come from one-date setups",
                st["subsection"],
            ),
            p(
                "All eight raw best readings leave five points of headroom or less, and every exact raw-best instrument+protocol setup appears on only one date. Four benchmarks have a different setup repeated across dates. Only HMMT's closest repeated setup is also within five points, and all four repeated setups are two-date, single-organization pairs. The remaining four benchmarks have no repeated setup. The evidence supports protocol-specific headroom claims only.",
                st["body"],
            ),
            saturation_audit_table(st, audit),
            Spacer(1, 7),
            saturation_threshold_table(st, audit),
            p(
                "Repeated-setup sensitivity is 1 of 4 assessable benchmarks at five points; using 8 as the denominator would count four unknowns as negatives. No raw-best setup qualifies as repeat-controlled. The machine-readable audit beside the report source records every protocol stratum, score ID, exclusion, counterexample, and exact decision wording.",
                st["body"],
            ),
            p("Per-benchmark claim wording", st["subsection"]),
            saturation_wording_table(st, audit),
        ]
        if draft
        else [
            p("6.2 Several bounded metrics are near their ceiling", st["subsection"]),
            p(
                "The curated layer records five points of headroom or less for AIME, Arena-Hard, DeepSearchQA, HMMT, MATH-500, MathVision, SWE-bench Verified, and tau2-bench. Read each value with its reasoning budget, tools, attempts, and evaluator. Those settings often explain score movement between model reports.",
                st["body"],
            ),
        ]
    )
    story: list = []

    story.extend(
        [
            Spacer(1, 0.18 * inch),
            p(
                "TECHNICAL REPORT  |  BENCHMARK RADAR v0.9.0",
                ParagraphStyle(
                    "Kicker",
                    parent=st["meta"],
                    fontName=BOLD,
                    fontSize=8.1,
                    textColor=BLUE,
                    spaceAfter=9,
                ),
            ),
            p("Benchmark Radar v0.9.0", st["title"]),
            p(
                "From daily collection to benchmark search and score history",
                st["subtitle"],
            ),
            p(" · ".join(byline or authors), st["author"]),
            *[p(affiliation, st["meta"]) for affiliation in affiliations],
            *(
                [p(f"Corresponding author: {corresponding_author}", st["meta"])]
                if corresponding_author
                else []
            ),
            p(
                "29 August 2026  |  Software v0.9.0  |  Data cutoff 2026-08-29  |  Git 98c7de3",
                st["meta"],
            ),
            p(
                (f"Reference DOI (frozen v0.9.0): {doi}" if draft else f"Reserved DOI: {doi}"),
                st["meta"],
            ),
            Spacer(1, 0.20 * inch),
            metric_strip(st),
            Spacer(1, 0.20 * inch),
            Table(
                [
                    [
                        p(
                            "Benchmark Radar brings daily discoveries, catalog search, vendor reporting, and sourced model scores into one place. Each layer keeps its own count because each records a different kind of evidence.",
                            st["callout"],
                        )
                    ]
                ],
                colWidths=[6.6 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER),
                        ("BOX", (0, 0), (-1, -1), 0.8, AMBER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 13),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                ),
            ),
            Spacer(1, 0.16 * inch),
            p("Executive findings", st["section"]),
            bullet(
                "<b>Search covers 1,242 entries.</b> Three external catalogs supply 1,173 rows. The curated score archive adds 69 benchmark tracks.",
                st["body"],
            ),
            bullet(
                "<b>The daily corpus holds 7,540 observations for 4,537 artifacts.</b> Primary or structured sources supplied 7,523 observations, and each record keeps its source URL and retrieval metadata.",
                st["body"],
            ),
            bullet(
                "<b>Thirty-six model reports cover 94 curated benchmarks.</b> The same documents supply 285 scores across 69 benchmark tracks when the report includes a readable value and evaluation setup.",
                st["body"],
            ),
            bullet(
                "<b>Identity and task classification need more work.</b> Forty-one artifacts link across multiple sources. KW-Bench has produced 4,129 tracks, with classification still empty in v0.9.0.",
                st["body"],
            ),
            p("Abstract", st["subsection"]),
            p(
                "Benchmark Radar collects benchmark work from 37 public sources and publishes it through a dashboard, RSS, JSON, and an offline client. This report checks the full path from collection to search. It covers source health, exact-identifier matching, the ranking rubric, the 1,242-entry search index, model-card adoption, score histories, and the reports already in the repository. The system has strong provenance and reproducible builds. Cross-source matching, protocol capture, semantic search, and KW-Bench classification remain active work.",
                st["body"],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("1. Product tour", st["section"]),
            p(
                "The README leads with the user task: find a benchmark in seconds, then inspect model-card adoption and score movement. The dashboard and RSS feed serve readers. JSON, the local CLI, and the local HTTP API support reproducible research.",
                st["body"],
            ),
            p(
                "Benchmark Radar's daily-intelligence logic was inspired by BuilderPulse, an AI-powered daily intelligence project for indie hackers and builders that answers 20 questions from 10+ sources every morning [8]. Benchmark Radar adapts that multi-source briefing pattern to benchmark discovery, normalized catalog search, and score history.",
                st["body"],
            ),
            search_surface(st),
            Spacer(1, 7),
            p("1.1 Search coverage", st["subsection"]),
            table(
                [
                    [
                        p("Search layer", st["table_header"]),
                        p("Rows", st["table_header"]),
                        p("Best field", st["table_header"]),
                        p("Score data", st["table_header"]),
                    ],
                    [
                        p("LLM Stats", st["small_bold"]),
                        p("687", st["small"]),
                        p("Benchmark names and descriptions", st["small"]),
                        p("5,544 rows; evaluation setup is sparse", st["small"]),
                    ],
                    [
                        p("OpenCompass Hub", st["small_bold"]),
                        p("461", st["small"]),
                        p("Paper, repository, release, and dataset links", st["small"]),
                        p("Historical leaderboards stay source-labelled", st["small"]),
                    ],
                    [
                        p("Artificial Analysis", st["small_bold"]),
                        p("25", st["small"]),
                        p("Current commercial evaluation catalog", st["small"]),
                        p("7,050 third-party rows", st["small"]),
                    ],
                    [
                        p("Curated score tracks", st["small_bold"]),
                        p("69", st["small"]),
                        p("Scores read from primary model reports", st["small"]),
                        p("285 rows with instrument and protocol fields", st["small"]),
                    ],
                    [
                        p("Search box", st["small_bold"]),
                        p("1,242", st["small_bold"]),
                        p("All four layers in one index", st["small_bold"]),
                        p("Source label shown on every result", st["small_bold"]),
                    ],
                ],
                [1.35 * inch, 0.55 * inch, 2.25 * inch, 2.45 * inch],
            ),
            p(
                "The UI adds 1,173 external rows and 69 curated score tracks. It keeps source records separate, so the same benchmark name can appear in more than one catalog. The label “4 sources” refers to these four search layers. The daily collector uses 37 public endpoints.",
                st["body"],
            ),
            p("1.2 Dashboard and local tools", st["subsection"]),
            table(
                [
                    [
                        p("Surface", st["table_header"]),
                        p("Reader question", st["table_header"]),
                        p("Evaluation", st["table_header"]),
                    ],
                    [
                        p("Today", st["small_bold"]),
                        p("What appeared or changed?", st["small"]),
                        p("Ranks new records and links the source evidence.", st["small"]),
                    ],
                    [
                        p("Search", st["small_bold"]),
                        p("Which records match this name, task, or domain?", st["small"]),
                        p("Ranks exact names, phrases, and field-token matches.", st["small"]),
                    ],
                    [
                        p("Leaderboard", st["small_bold"]),
                        p("Which benchmarks do labs report?", st["small"]),
                        p("Counts benchmark mentions across vendor reports.", st["small"]),
                    ],
                    [
                        p("Scores", st["small_bold"]),
                        p("Which printed values can be connected?", st["small"]),
                        p("Matching instrument + protocol creates a series.", st["small"]),
                    ],
                    [
                        p("Trends / map", st["small_bold"]),
                        p("Which topics and sources recur?", st["small"]),
                        p("Coverage signatures gate comparisons.", st["small"]),
                    ],
                    [
                        p("CLI + HTTP", st["small_bold"]),
                        p("Can an analyst reproduce search offline?", st["small"]),
                        p("One QueryService and stable JSON contract.", st["small"]),
                    ],
                ],
                [1.15 * inch, 2.65 * inch, 2.8 * inch],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("2. Pipeline evaluation", st["section"]),
            pipeline_figure(),
            p("2.1 Collection and health", st["subsection"]),
            p(
                "Each run queries enabled connectors inside a 48-hour window, records counts and errors, drops future-dated rows, then requires the configured core sources to be healthy. arXiv, Hugging Face, and GitHub are required. On the cutoff run all three were healthy; Semantic Scholar returned HTTP 429 and Brave had no API key; OpenReview was healthy but empty.",
                st["body"],
            ),
            p(
                "The cutoff run fetched 826 rows, deduplicated them to 783, classified 273 as eligible, and recommended 97. Two collections ran that day. Their merged page contains 528 records, including 186 recommendations.",
                st["body"],
            ),
            p("2.2 Normalization, identity, and retention", st["subsection"]),
            bullet(
                "Stable fields include source ID, URL, title, timestamps, authors or organizations when supplied, parser version, retrieval time, and a SHA-256 payload fingerprint. The publisher omits raw responses and credentials.",
                st["body"],
            ),
            bullet(
                "The resolver merges observations that share a DOI, arXiv ID, OpenReview ID, GitHub repository, or Hugging Face artifact. A similar title leaves two records in place until a reviewer confirms the match.",
                st["body"],
            ),
            bullet(
                "The corpus includes eligible records below the recommendation threshold. The recommended tag controls display priority.",
                st["body"],
            ),
            p("2.3 Interpretation, publication, and query", st["subsection"]),
            p(
                "Priority combines relevance (35%), evidence (20%), recency (20%), and adoption (25%) on a 0–100 scale. Scoring version 5 ships with the data. Generators replay validated snapshots into the cumulative graph, normalize external catalogs, classify KW-Bench tracks, and package a checksummed release. Installed clients switch to a new data version after checksum and schema validation. Search reads the active local version.",
                st["body"],
            ),
            table(
                [
                    [
                        p("Area", st["table_header"]),
                        p("Working today", st["table_header"]),
                        p("Current gap", st["table_header"]),
                    ],
                    [
                        p("Reproducibility", st["small_bold"]),
                        p(
                            "Snapshots, schemas, parser versions, hashes, deterministic rebuilds.",
                            st["small"],
                        ),
                        p("Four early snapshots are simulated.", st["small"]),
                    ],
                    [
                        p("Reliability", st["small_bold"]),
                        p(
                            "Required-source gate; optional failures visible; atomic client activation.",
                            st["small"],
                        ),
                        p("Rate limits and secrets change realized coverage.", st["small"]),
                    ],
                    [
                        p("Identity", st["small_bold"]),
                        p("Exact-anchor merges and reviewed external groups.", st["small"]),
                        p("Forty-one artifacts have more than one source.", st["small"]),
                    ],
                    [
                        p("Interfaces", st["small_bold"]),
                        p("CLI and HTTP share QueryService and JSON.", st["small"]),
                        p("Local token matching misses some paraphrases.", st["small"]),
                    ],
                    [
                        p("Verification", st["small_bold"]),
                        p("Clean-worktree rebuild plus 1,028 passing tests.", st["small"]),
                        p("Source coverage still depends on public endpoints.", st["small"]),
                    ],
                ],
                [1.15 * inch, 2.75 * inch, 2.70 * inch],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("3. Counts and units", st["section"]),
            p(
                "The dashboard publishes several counts because it tracks several units. Use the unit and cutoff beside the number.",
                st["body"],
            ),
            table(
                [
                    [
                        p("Unit / product", st["table_header"]),
                        p("Count", st["table_header"]),
                        p("Definition", st["table_header"]),
                        p("Use it for", st["table_header"]),
                    ],
                    [
                        p("Snapshot", st["small_bold"]),
                        p("37", st["small"]),
                        p("33 observed, 4 simulated.", st["small"]),
                        p("The dated history available for replay.", st["small"]),
                    ],
                    [
                        p("Source observation", st["small_bold"]),
                        p("7,540", st["small"]),
                        p("Persisted source record.", st["small"]),
                        p("Evidence volume in cumulative replay.", st["small"]),
                    ],
                    [
                        p("Unique artifact", st["small_bold"]),
                        p("4,537", st["small"]),
                        p("Exact-ID-resolved paper, repo, dataset, release, or page.", st["small"]),
                        p("Distinct artifacts observed.", st["small"]),
                    ],
                    [
                        p("External catalog row", st["small_bold"]),
                        p("1,173", st["small"]),
                        p("One row from three catalog sources.", st["small"]),
                        p("Broad, source-labelled catalog search.", st["small"]),
                    ],
                    [
                        p("Searchable entry", st["small_bold"]),
                        p("1,242", st["small"]),
                        p("1,173 external + 69 curated score tracks.", st["small"]),
                        p("Current web-search reach.", st["small"]),
                    ],
                    [
                        p("Adoption benchmark", st["small_bold"]),
                        p("94", st["small"]),
                        p("Canonical identity in curated registry.", st["small"]),
                        p("Model-card adoption and missing adoption.", st["small"]),
                    ],
                    [
                        p("Model-card document", st["small_bold"]),
                        p("36", st["small"]),
                        p("Curated reports from 11 organizations.", st["small"]),
                        p("Documents read for mentions.", st["small"]),
                    ],
                    [
                        p("Curated score", st["small_bold"]),
                        p("285", st["small"]),
                        p("Numeric result from a cited document; 69 tracks.", st["small"]),
                        p("Score histories grouped by evaluation setup.", st["small"]),
                    ],
                    [
                        p("Model registry", st["small_bold"]),
                        p("861", st["small"]),
                        p("Models across curated and crawled layers; 19 in both.", st["small"]),
                        p("Finding a model across both data layers.", st["small"]),
                    ],
                ],
                [1.30 * inch, 0.55 * inch, 2.45 * inch, 2.30 * inch],
                tiny=True,
            ),
            p("3.1 Cumulative source composition", st["subsection"]),
            source_bars(),
            p(
                "Five normalized source labels supply 7,376 of 7,540 observations (97.8%). The other endpoints add discovery routes and publish their own yield and health status.",
                st["body"],
            ),
            p("3.2 Adoption and score findings", st["subsection"]),
            p(
                "GPQA Diamond appears in 26 of 36 documents from 10 organizations. Humanity's Last Exam, SWE-bench Verified, Terminal-Bench, AIME, LiveCodeBench, MMLU-Pro, and BrowseComp form the rest of the top eight. These counts show which benchmarks vendors choose to report. The score archive finds eight bounded metrics with five points of headroom or less. Six benchmarks gained model-card mentions after their last readable score.",
                st["body"],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("4. Source inventory and health", st["section"]),
            p(
                "The daily collector reads 12 discovery connectors, 24 first-party feeds, and Hacker News. The search box draws from four catalog layers.",
                st["body"],
            ),
            p("4.1 Direct discovery connectors (12)", st["subsection"]),
            table(
                [
                    [
                        p("Connector", st["table_header"]),
                        p("Role", st["table_header"]),
                        p("Cutoff run", st["table_header"]),
                        p("Core?", st["table_header"]),
                    ],
                    [
                        p("arXiv", tiny),
                        p("Primary papers via cs.AI/CL/CV/SE RSS", tiny),
                        p("Healthy · 23", tiny),
                        p("Yes", tiny),
                    ],
                    [
                        p("Hugging Face Hub", tiny),
                        p("Datasets and Spaces", tiny),
                        p("Healthy · 126", tiny),
                        p("Yes", tiny),
                    ],
                    [
                        p("GitHub Search", tiny),
                        p("Code and artifacts", tiny),
                        p("Healthy · 300; at cap", tiny),
                        p("Yes", tiny),
                    ],
                    [
                        p("GitHub Organizations", tiny),
                        p("Reviewed organization repos", tiny),
                        p("Healthy · 15", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("Hugging Face Papers", tiny),
                        p("Community-surfaced papers", tiny),
                        p("Healthy · 23", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("Kaggle Datasets", tiny),
                        p("Public benchmark datasets", tiny),
                        p("Healthy · 28", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("Zenodo", tiny),
                        p("DOI-bearing artifacts", tiny),
                        p("Healthy · 77", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("OpenReview", tiny),
                        p("Conference submissions", tiny),
                        p("Healthy · 0", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("Semantic Scholar", tiny),
                        p("Structured scholarly discovery", tiny),
                        p("Failed · HTTP 429", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("GitHub Releases", tiny),
                        p("Curated first-party releases", tiny),
                        p("Healthy · 3", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("OpenAlex", tiny),
                        p("Scholarly discovery", tiny),
                        p("Healthy · 228", tiny),
                        p("No", tiny),
                    ],
                    [
                        p("Brave Search", tiny),
                        p("Web and official domains", tiny),
                        p("Unavailable · no key", tiny),
                        p("No", tiny),
                    ],
                ],
                [1.35 * inch, 2.45 * inch, 1.80 * inch, 0.70 * inch],
                tiny=True,
            ),
            p("4.2 First-party feeds (24)", st["subsection"]),
            table(
                [
                    [p("Feeds 1–12", st["table_header"]), p("Feeds 13–24", st["table_header"])],
                    [
                        p(
                            "Meituan Engineering<br/>OpenAI News<br/>Google AI<br/>Google DeepMind<br/>Google Research<br/>Apple Machine Learning Research<br/>AWS Machine Learning<br/>Hugging Face Blog<br/>Microsoft Research<br/>NVIDIA AI Blog<br/>Mistral AI<br/>Meta Research",
                            tiny,
                        ),
                        p(
                            "Ai2<br/>Together AI<br/>Sakana AI<br/>Qwen<br/>Ollama<br/>Stability AI<br/>Nomic AI<br/>Replicate<br/>NVIDIA Developer<br/>IBM Research<br/>Databricks<br/>LangChain",
                            tiny,
                        ),
                    ],
                ],
                [3.3 * inch, 3.3 * inch],
                tiny=True,
            ),
            p(
                "The feed collector yielded three relevant records. Some healthy feeds produced zero matches after relevance filtering. Domain-constrained searches cover organizations that lack a verified feed. The collector excludes third-party mirrors.",
                st["body"],
            ),
            p("4.3 Public attention (1)", st["subsection"]),
            p(
                "The Hacker News collector uses the public Algolia API. It found 12 records on the cutoff run and places them in a separate attention feed. The priority calculation uses evidence sources only.",
                st["body"],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("5. Data quality and report history", st["section"]),
            table(
                [
                    [
                        p("Finding", st["table_header"]),
                        p("Evidence", st["table_header"]),
                        p("Interpretation", st["table_header"]),
                    ],
                    [
                        p("High provenance", st["small_bold"]),
                        p("7,523 / 7,540 primary or structured (99.77%).", st["small"]),
                        p(
                            "Readers can open the upstream record for almost every observation.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Low corroboration", st["small_bold"]),
                        p("41 / 4,537 artifacts have >1 normalized source (0.90%).", st["small"]),
                        p(
                            "Exact identity prevents bad joins but leaves plausible duplicates.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Uneven yield", st["small_bold"]),
                        p("Five source labels provide 97.8% of observations.", st["small"]),
                        p("Caps or outages can change apparent topic mix.", st["small"]),
                    ],
                    [
                        p("Simulation", st["small_bold"]),
                        p("23–26 July are simulated snapshots.", st["small"]),
                        p("Use them to test replay and UI history.", st["small"]),
                    ],
                    [
                        p("Classification gap", st["small_bold"]),
                        p("KW-Bench: 4,129 tracks, 0 classified.", st["small"]),
                        p(
                            "The task-capability view has no classifications yet.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Protocol sparsity", st["small_bold"]),
                        p(
                            "12,594 aggregator scores stay outside curated progression.",
                            st["small"],
                        ),
                        p(
                            "Comparison needs shots, harness, tools, attempts, and date.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Lexical retrieval", st["small_bold"]),
                        p("Field tokens drive rank; no semantic reranker.", st["small"]),
                        p("Reproducible, but paraphrases can be missed.", st["small"]),
                    ],
                ],
                [1.45 * inch, 2.35 * inch, 2.80 * inch],
            ),
            p("5.1 Existing reports", st["subsection"]),
            table(
                [
                    [
                        p("Document", st["table_header"]),
                        p("Use today", st["table_header"]),
                        p("Date limit", st["table_header"]),
                    ],
                    [
                        p("Landscape report, 31 Jul", st["small_bold"]),
                        p(
                            "A dated study of 791 sightings, 645 artifacts, and 78 agentic-evaluation artifacts.",
                            st["small"],
                        ),
                        p(
                            "Its totals stop on 31 July, before the external catalog and newer connectors.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Source probes, 27 Aug", st["small_bold"]),
                        p("Verified HF Papers, Kaggle, Spaces, and Zenodo endpoints.", st["small"]),
                        p("The probes record one check on 27 August.", st["small"]),
                    ],
                    [
                        p("External catalog audit", st["small_bold"]),
                        p(
                            "OpenCompass identity fields and the score-heavy peer catalogs.",
                            st["small"],
                        ),
                        p(
                            "The audit keeps same-name records separate until identity review.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Daily report / briefing", st["small_bold"]),
                        p("Triage with citations and source health.", st["small"]),
                        p("Each edition covers one collection window.", st["small"]),
                    ],
                ],
                [1.65 * inch, 2.75 * inch, 2.20 * inch],
            ),
            p("5.2 Reading the evidence", st["subsection"]),
            bullet(
                "You can trace a new or updated record to its source, inspect why the taxonomy matched it, and find the vendor document behind each curated benchmark mention.",
                st["body"],
            ),
            bullet(
                "For score comparisons, match the instrument and protocol fields. For trend comparisons, use days with the same connector coverage and report limit. Market-size estimates need a separate benchmark-family census.",
                st["body"],
            ),
        ]
    )

    story.extend(
        [
            PageBreak(),
            p("6. Findings from the current data", st["section"]),
            p(
                "Benchmark Radar turns papers, repositories, datasets, and model reports into records you can search, filter, download, and query offline. Three results stand out in the current data.",
                st["body"],
            ),
            p("6.1 Vendor attention has converged on a small reporting core", st["subsection"]),
            p(
                "Eight benchmarks appear in documents from at least six organizations: GPQA Diamond, Humanity's Last Exam, SWE-bench Verified, Terminal-Bench, AIME, LiveCodeBench, MMLU-Pro, and BrowseComp. Teams comparing new model reports will encounter this group most often. The score archive shows where these familiar tests have little headroom left.",
                st["body"],
            ),
            *saturation_section,
            p("6.3 Broad search, deeper curation", st["subsection"]),
            p(
                "The external catalog holds 1,173 rows, more than twelve times the 94-benchmark adoption registry. Use catalog search to find candidates. The curated registry adds the model reports, organizations, instruments, and protocols needed for comparison.",
                st["body"],
            ),
            p("6.4 What to build next", st["subsection"]),
            table(
                [
                    [
                        p("Priority", st["table_header"]),
                        p("Measurement work", st["table_header"]),
                        p("Result", st["table_header"]),
                    ],
                    [
                        p("1", st["small_bold"]),
                        p("Show the count unit beside every UI total and export.", st["small"]),
                        p("Readers can see which population each number counts.", st["small"]),
                    ],
                    [
                        p("2", st["small_bold"]),
                        p(
                            "Resolve high-value cross-source identities with anchors and review.",
                            st["small"],
                        ),
                        p("More records gain paper, code, and dataset links.", st["small"]),
                    ],
                    [
                        p("3", st["small_bold"]),
                        p("Complete KW-Bench extraction and reviewed coverage.", st["small"]),
                        p("Turns 4,129 unclassified tracks into a task map.", st["small"]),
                    ],
                    [
                        p("4", st["small_bold"]),
                        p("Expand protocol capture from newer model cards.", st["small"]),
                        p("Closes the mention-versus-score recency gap.", st["small"]),
                    ],
                    [
                        p("5", st["small_bold"]),
                        p(
                            "Add optional semantic retrieval while retaining lexical reasons.",
                            st["small"],
                        ),
                        p("Finds paraphrases while retaining visible match reasons.", st["small"]),
                    ],
                ],
                [0.55 * inch, 3.35 * inch, 2.70 * inch],
            ),
            KeepTogether(
                [
                    p(
                        "6.5 Worked real use case: prior-art check for a new evaluation",
                        st["subsection"],
                    ),
                    p(
                        "Jiayu Wang, a researcher working on agent evaluation, used Benchmark Radar to decide whether a proposed new evaluation would duplicate existing work. The check decides whether the design is still novel, and it used to be slow: comparing a candidate against the field required long manual searches, and completeness was hard to guarantee. The case ran during August 2026 with a concrete task: survey recent work on credit assignment in agentic training, keeping small Qwen-series baselines as a reproducibility constraint.",
                        st["body"],
                    ),
                ]
            ),
            p(
                "The author gave the task to a coding agent together with the public consumer prompt for Benchmark Radar. The agent installed the CLI and the benchmark-radar Skill, initialized the local corpus with benchmark-radar init, and queried candidate records with benchmark-radar search.",
                st["body"],
            ),
            *figure(
                "assets/use-case-492/agent-session.png",
                "<b>Figure 1.</b> A coding agent follows the consumer setup prompt, installs the Benchmark Radar CLI and Skill, and runs local queries.",
                st,
            ),
            p(
                "Radar links one artifact across papers, code, releases, and datasets. The agent could therefore see at a glance whether a candidate was announced as a paper with no released code, or shipped code without its dataset.",
                st["body"],
            ),
            *figure(
                "assets/use-case-492/artifact-status-paper.png",
                "<b>Figure 2.</b> Radar consolidates the sources and status of one artifact.",
                st,
            ),
            *figure(
                "assets/use-case-492/artifact-status-code.png",
                "<b>Figure 3.</b> A companion record in which code is public but the dataset is not yet released.",
                st,
            ),
            p(
                "Radar search is deterministic lexical matching, so the agent also ran its own web search and cross-checked the two candidate sets before accepting a record. This double pass keeps a differently worded version of the same idea from being missed.",
                st["body"],
            ),
            *figure(
                "assets/use-case-492/cross-validation.png",
                "<b>Figure 4.</b> Cross-checking Radar candidates against the agent's own web search before accepting a record.",
                st,
            ),
            p(
                "The session ended with a focused summary table of related work that the author judged complete enough to act on.",
                st["body"],
            ),
            *figure(
                "assets/use-case-492/survey-table.png",
                "<b>Figure 5.</b> Summary table of recent work on credit assignment in agentic training assembled during the session.",
                st,
            ),
            p(
                "The savings are easiest to measure against the author's earlier benchmark, AARRI-Bench, whose equivalent prior-art comparison consumed effort second only to producing the benchmark data itself, for a table of just 12 rows and 7 columns.",
                st["body"],
            ),
            *figure(
                "assets/use-case-492/aarri-bench-manual-table.png",
                "<b>Figure 6.</b> The manually built 12-by-7 prior-art table for AARRI-Bench, the workflow that Radar now shortens.",
                st,
            ),
            p(
                "Limits: Radar search is deterministic lexical matching rather than semantic retrieval, so a differently worded query can change the candidate set. The session used the Radar CLI together with the agent's general web search, so it does not isolate Radar alone. Repository and dataset availability is a snapshot, not a permanent label. The case documents one contributor's workflow; it is not a measured user study. Full evidence, including the summary table and session screenshots, is public in issue #492.",
                st["body"],
            ),
            p(
                "<b>Contributor.</b> Jiayu Wang, Xi'an Jiaotong University. Case and evidence: github.com/ktwu01/benchmark-radar/issues/492",
                st["body"],
            ),
            Spacer(1, 10),
            Table(
                [
                    [
                        p("Use it", st["callout"]),
                        p(
                            "Cite Benchmark Radar for source-linked benchmark discovery, catalog search, and vendor-reporting evidence. Use the source and protocol fields when you compare records or scores.",
                            st["body"],
                        ),
                    ]
                ],
                colWidths=[1.1 * inch, 5.5 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN),
                        ("BOX", (0, 0), (-1, -1), 0.8, GREEN),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ]
                ),
            ),
        ]
    )

    draft_sections = (
        [
            p("7.1 Methods and limitations", st["subsection"]),
            p(
                "The 6.2 audit uses the curated score archive and model-card registry. Raw headroom is the distance from one reported value to the metric bound. Repeat-controlled evidence requires the same instrument and protocol across at least two dates. Two dates support only a paired comparison. Because each repeated setup comes from one organization, the audit cannot estimate a field-wide trend. Sensitivity tables keep unknowns out of the eligible denominator.",
                st["body"],
            ),
            p("7.2 Contributor credit", st["subsection"]),
            p(
                "Junjie Zhou prepared the protocol audit, machine-readable table, and report revision for issue #457.",
                st["body"],
            ),
            p("7.3 Issue link", st["subsection"]),
            p(
                '<link href="https://github.com/ktwu01/benchmark-radar/issues/457">Issue #457</link> Near-ceiling metrics under protocol controls.',
                st["body"],
            ),
        ]
        if draft
        else []
    )
    story.extend(
        [
            PageBreak(),
            p("7. Reproducibility, access, and citation", st["section"]),
            p(
                "This report evaluates Benchmark Radar v0.9.0 at Git commit 98c7de3 and data cutoff 2026-08-29. The clean worktree ran the CI sequence: lint and formatting checks, external normalization, KW-Bench classification, checksummed data-release construction, and the full test suite. All 1,028 tests passed.",
                st["body"],
            ),
            *draft_sections,
            table(
                [
                    [
                        p("Artifact", st["table_header"]),
                        p("Canonical or permanent location", st["table_header"]),
                    ],
                    [
                        p("Technical report", st["small_bold"]),
                        p(f"https://doi.org/{doi}", st["small"]),
                    ],
                    [
                        p("Source code", st["small_bold"]),
                        p("https://github.com/ktwu01/benchmark-radar", st["small"]),
                    ],
                    [
                        p("Dashboard", st["small_bold"]),
                        p("https://benchmark-radar.org/", st["small"]),
                    ],
                    [
                        p("Cumulative JSON", st["small_bold"]),
                        p("https://benchmark-radar.org/data/radar.json", st["small"]),
                    ],
                    [
                        p("Benchmark catalog", st["small_bold"]),
                        p("https://benchmark-radar.org/data/benchmark-index.json", st["small"]),
                    ],
                    [
                        p("RSS", st["small_bold"]),
                        p("https://benchmark-radar.org/feed.xml", st["small"]),
                    ],
                    [
                        p("Citation metadata", st["small_bold"]),
                        p(
                            "https://github.com/ktwu01/benchmark-radar/blob/main/CITATION.cff",
                            st["small"],
                        ),
                    ],
                ],
                [1.55 * inch, 5.05 * inch],
            ),
            p(
                "Published v0.9.0 citation" if draft else "Suggested citation",
                st["subsection"],
            ),
            p(
                f"Wu, K. (2026). <i>Benchmark Radar v0.9.0: Technical Report</i>. Zenodo. https://doi.org/{doi}",
                st["body"],
            ),
            p("Data statement", st["subsection"]),
            p(
                "Counts were recomputed from site/data/radar.json, site/data/benchmark-index.json, site/data/models.json, data/model_cards.yml, data/benchmark_scores.yml, normalized files under data/external/, and config.yml. The PDF is a dated interpretation. The rolling dashboard may change after the cutoff; cite its current number with a retrieval date.",
                st["body"],
            ),
            p("References", st["section"]),
            p(
                "[1] K. Wu. Benchmark Radar, version 0.9.0. GitHub, 2026. https://github.com/ktwu01/benchmark-radar",
                st["reference"],
            ),
            p(
                "[2] K. Wu. AI Benchmark Landscape Report. 2026. https://github.com/ktwu01/benchmark-radar/blob/main/docs/reports/ai-benchmark-landscape-report.md",
                st["reference"],
            ),
            p(
                "[3] K. Wu. Benchmark Radar cumulative corpus schema. 2026. https://github.com/ktwu01/benchmark-radar/blob/main/docs/cumulative-corpus.schema.json",
                st["reference"],
            ),
            p(
                "[4] K. Wu. Source probe evidence. 2026. https://github.com/ktwu01/benchmark-radar/blob/main/docs/source-probe-evidence.md",
                st["reference"],
            ),
            p(
                "[5] D. S. Katz et al. Recognizing the value of software: a software citation guide. F1000Research 9:1257, 2021. https://doi.org/10.12688/f1000research.26932.2",
                st["reference"],
            ),
            p(
                "[6] A. Smith, D. S. Katz, and K. E. Niemeyer. Software citation principles. PeerJ Computer Science 2:e86, 2016. https://doi.org/10.7717/peerj-cs.86",
                st["reference"],
            ),
            p(
                "[7] Citation File Format developers. Citation File Format 1.2.0. https://citation-file-format.github.io/",
                st["reference"],
            ),
            p(
                "[8] L. Xiaopai. BuilderPulse: AI-powered daily intelligence for indie hackers and builders. GitHub, 2026. https://github.com/BuilderPulse/BuilderPulse",
                st["reference"],
            ),
            Spacer(1, 9),
            Table(
                [
                    [
                        p(
                            "Software: MIT License.<br/>Technical report and original editorial content: CC BY-NC 4.0.<br/>Commercial republication, resale, paid newsletters, dataset packaging, or commercial product integration requires prior written permission from Koutian Wu.<br/>Third-party source material remains under its original terms.",
                            ParagraphStyle(
                                "EndCard",
                                parent=st["body"],
                                fontName=BOLD,
                                fontSize=8.6,
                                leading=12.5,
                                textColor=NAVY,
                            ),
                        )
                    ]
                ],
                colWidths=[6.6 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SKY),
                        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ]
                ),
            ),
        ]
    )
    return story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument("--doi", default="10.5281/zenodo.22167102")
    parser.add_argument(
        "--next-draft",
        action="store_true",
        help="build the working next-draft artifact with the current contributor byline",
    )
    parser.add_argument(
        "--overwrite-frozen",
        action="store_true",
        help="explicitly allow replacing the deposited v0.9.0 PDF",
    )
    args = parser.parse_args()
    output = args.output or (NEXT_DRAFT_OUTPUT if args.next_draft else FROZEN_OUTPUT)
    if output.resolve() == FROZEN_OUTPUT.resolve() and not args.overwrite_frozen:
        parser.error(
            "cannot overwrite the frozen v0.9.0 PDF; use --next-draft or --overwrite-frozen"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    authors = NEXT_DRAFT_AUTHORS if args.next_draft else FROZEN_AUTHORS
    byline = NEXT_DRAFT_BYLINE if args.next_draft else None
    affiliations = NEXT_DRAFT_AFFILIATIONS if args.next_draft else ()
    corresponding_author = NEXT_DRAFT_CORRESPONDING_AUTHOR if args.next_draft else None
    EvaluationDoc(str(output), doi=args.doi, authors=authors).build(
        story(
            args.doi,
            authors=authors,
            byline=byline,
            affiliations=affiliations,
            corresponding_author=corresponding_author,
            draft=args.next_draft,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
