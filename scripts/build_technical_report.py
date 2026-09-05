#!/usr/bin/env python3
"""Build the Benchmark Radar v0.9.0 technical report PDF."""

# Ruff cannot wrap the long prose strings that become ReportLab paragraphs.
# ruff: noqa: E501

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

NAVY = HexColor("#12233F")
BLUE = HexColor("#2563EB")
SKY = HexColor("#EAF1FF")
INK = HexColor("#243247")
MUTED = HexColor("#5C6B80")
RULE = HexColor("#D7DFEA")
AMBER = HexColor("#E89217")
PALE_AMBER = HexColor("#FFF4DD")
TEAL = HexColor("#0F766E")
PALE_TEAL = HexColor("#E7F6F3")
WHITE = colors.white

PAGE_W, PAGE_H = letter
MARGIN_X = 0.68 * inch
TOP = 0.62 * inch
BOTTOM = 0.62 * inch
FROZEN_OUTPUT = Path("output/pdf/benchmark-radar-technical-report-v0.9.0.pdf")
NEXT_DRAFT_OUTPUT = Path("output/pdf/benchmark-radar-technical-report-next-draft.pdf")


def register_fonts() -> tuple[str, str, str]:
    """Use a clean system sans face when present, with safe fallbacks."""
    font_candidates = [
        (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ),
    ]
    for regular, bold, italic in font_candidates:
        if all(Path(path).exists() for path in (regular, bold, italic)):
            pdfmetrics.registerFont(TTFont("ReportSans", regular))
            pdfmetrics.registerFont(TTFont("ReportSans-Bold", bold))
            pdfmetrics.registerFont(TTFont("ReportSans-Italic", italic))
            return "ReportSans", "ReportSans-Bold", "ReportSans-Italic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


REGULAR, BOLD, ITALIC = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=BOLD,
            fontSize=27,
            leading=30,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName=REGULAR,
            fontSize=13.2,
            leading=18,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "author": ParagraphStyle(
            "Author",
            parent=base["Normal"],
            fontName=BOLD,
            fontSize=10.5,
            leading=14,
            textColor=INK,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base["Normal"],
            fontName=REGULAR,
            fontSize=8.7,
            leading=12,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading1"],
            fontName=BOLD,
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            parent=base["Heading2"],
            fontName=BOLD,
            fontSize=11.3,
            leading=14,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=9.25,
            leading=13.2,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=7.9,
            leading=10.5,
            textColor=MUTED,
        ),
        "small_bold": ParagraphStyle(
            "SmallBold",
            parent=base["BodyText"],
            fontName=BOLD,
            fontSize=8.1,
            leading=10.5,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName=BOLD,
            fontSize=8.1,
            leading=10.5,
            textColor=WHITE,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName=BOLD,
            fontSize=19,
            leading=21,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=7.4,
            leading=9.2,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName=BOLD,
            fontSize=11,
            leading=15,
            textColor=NAVY,
            alignment=TA_LEFT,
        ),
        "reference": ParagraphStyle(
            "Reference",
            parent=base["BodyText"],
            fontName=REGULAR,
            fontSize=7.4,
            leading=9.6,
            textColor=INK,
            leftIndent=12,
            firstLineIndent=-12,
            spaceAfter=3,
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def bullet(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(
        f"<bullet>&bull;</bullet>{text}",
        ParagraphStyle(
            f"Bullet-{abs(hash(text))}",
            parent=style,
            leftIndent=13,
            firstLineIndent=-7,
            bulletIndent=0,
            spaceAfter=3,
        ),
    )


def metric_strip(st: dict[str, ParagraphStyle]) -> Table:
    values = ["7,540", "4,537", "1,173", "36"]
    labels = [
        "source observations<br/>across 37 snapshots",
        "unique artifacts in the<br/>cumulative evidence graph",
        "searchable benchmark<br/>catalog records",
        "model cards and<br/>release documents",
    ]
    cells = []
    for value, label in zip(values, labels, strict=True):
        cells.append([p(value, st["metric"]), p(label, st["metric_label"])])
    table = Table([cells], colWidths=[1.65 * inch] * 4, rowHeights=[0.76 * inch])
    table.setStyle(
        TableStyle(
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
        )
    )
    return table


def pipeline_figure() -> Drawing:
    drawing = Drawing(500, 96)
    labels = [
        ("DISCOVER", "37 public sources"),
        ("NORMALIZE", "stable fields + IDs"),
        ("ASSESS", "taxonomy + rubric"),
        ("PUBLISH", "site, RSS, JSON"),
        ("QUERY", "offline CLI + HTTP"),
    ]
    x_positions = [2, 103, 204, 305, 406]
    for index, ((title, caption), x) in enumerate(zip(labels, x_positions, strict=True)):
        fill = SKY if index % 2 == 0 else PALE_TEAL
        stroke = BLUE if index % 2 == 0 else TEAL
        drawing.add(Rect(x, 18, 90, 56, 7, 7, fillColor=fill, strokeColor=stroke, strokeWidth=1))
        drawing.add(
            String(
                x + 45, 52, title, fontName=BOLD, fontSize=8, fillColor=NAVY, textAnchor="middle"
            )
        )
        drawing.add(
            String(
                x + 45,
                35,
                caption,
                fontName=REGULAR,
                fontSize=6.8,
                fillColor=MUTED,
                textAnchor="middle",
            )
        )
        if index < len(labels) - 1:
            drawing.add(Line(x + 90, 46, x + 99, 46, strokeColor=AMBER, strokeWidth=1.8))
            drawing.add(Line(x + 95, 50, x + 99, 46, strokeColor=AMBER, strokeWidth=1.8))
            drawing.add(Line(x + 95, 42, x + 99, 46, strokeColor=AMBER, strokeWidth=1.8))
    drawing.add(
        String(
            250,
            4,
            "Each published record retains a URL to the evidence that produced it.",
            fontName=ITALIC,
            fontSize=7.2,
            fillColor=MUTED,
            textAnchor="middle",
        )
    )
    return drawing


def source_bars() -> Drawing:
    drawing = Drawing(492, 142)
    entries = [
        ("Hugging Face", 2452, BLUE),
        ("GitHub", 2008, TEAL),
        ("arXiv", 1482, AMBER),
        ("Semantic Scholar", 877, HexColor("#7C3AED")),
        ("Eight other sources", 721, HexColor("#94A3B8")),
    ]
    maximum = 2600
    x0 = 116
    width = 325
    for index, (label, value, color) in enumerate(entries):
        y = 119 - index * 24
        drawing.add(String(0, y + 3, label, fontName=REGULAR, fontSize=7.8, fillColor=INK))
        drawing.add(Rect(x0, y, width, 10, 5, 5, fillColor=HexColor("#EFF3F8"), strokeColor=None))
        drawing.add(
            Rect(x0, y, width * value / maximum, 10, 5, 5, fillColor=color, strokeColor=None)
        )
        drawing.add(
            String(x0 + width + 9, y + 2, str(value), fontName=BOLD, fontSize=7.8, fillColor=INK)
        )
    drawing.add(
        String(
            x0,
            1,
            "Cumulative observations by source, 37 snapshots through 2026-08-29",
            fontName=ITALIC,
            fontSize=7.2,
            fillColor=MUTED,
        )
    )
    return drawing


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, *, doi: str):
        super().__init__(
            filename,
            pagesize=letter,
            rightMargin=MARGIN_X,
            leftMargin=MARGIN_X,
            topMargin=TOP,
            bottomMargin=BOTTOM,
            title="Benchmark Radar: An Evidence-First Index for Tracking AI Benchmarks",
            author="Koutian Wu",
            subject="Benchmark Radar technical report, version 0.9.0",
            keywords="AI benchmarks, evaluation, dataset, evidence, model cards",
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
        canvas.line(MARGIN_X, 0.42 * inch, PAGE_W - MARGIN_X, 0.42 * inch)
        canvas.setFont(REGULAR, 6.9)
        canvas.setFillColor(MUTED)
        footer = f"Benchmark Radar Technical Report v0.9.0  |  29 August 2026  |  DOI: {self.doi}"
        canvas.drawString(MARGIN_X, 0.24 * inch, footer)
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.24 * inch, str(doc.page))
        canvas.restoreState()


def report_story(doi: str) -> list:
    st = styles()
    story: list = []

    # Page 1: the receiver's entry point.
    story.extend(
        [
            Spacer(1, 0.25 * inch),
            p(
                "TECHNICAL REPORT  |  BENCHMARK RADAR v0.9.0",
                ParagraphStyle(
                    "Kicker",
                    parent=st["meta"],
                    fontName=BOLD,
                    fontSize=8.5,
                    textColor=BLUE,
                    spaceAfter=10,
                ),
            ),
            p("Benchmark Radar", st["title"]),
            p("An evidence-first index for tracking AI benchmarks", st["subtitle"]),
            Spacer(1, 0.05 * inch),
            p("Koutian Wu", st["author"]),
            p("29 August 2026  |  Benchmark Radar v0.9.0", st["meta"]),
            p(f"DOI: {doi}", st["meta"]),
            Spacer(1, 0.28 * inch),
            metric_strip(st),
            Spacer(1, 0.28 * inch),
            Table(
                [
                    [
                        p(
                            "Benchmark Radar helps an evaluator find a new benchmark, inspect the source that announced it, and check how vendors use it without treating adoption as proof of quality.",
                            st["callout"],
                        )
                    ]
                ],
                colWidths=[6.6 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER),
                        ("BOX", (0, 0), (-1, -1), 0.8, AMBER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 14),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                        ("TOPPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ]
                ),
            ),
            Spacer(1, 0.25 * inch),
            p("Abstract", st["section"]),
            p(
                "Researchers now encounter new evaluation suites across papers, code repositories, datasets, model cards, and release posts. Benchmark Radar collects benchmark-related signals from 37 public sources each day, normalizes them into evidence-linked records, and publishes the result through a dashboard, RSS feed, JSON corpus, and offline query client. Through 29 August 2026, the cumulative corpus contains 7,540 source observations covering 4,537 unique artifacts across 37 snapshots; a separate catalog contains 1,173 searchable benchmark records. The project also maintains a curated model-card registry and a protocol-aware score layer. It records adoption and scores as separate facts, which prevents a benchmark with many mentions from becoming a performance claim.",
                st["body"],
            ),
            p("Suggested citation", st["subsection"]),
            p(
                f"Wu, K. (2026). <i>Benchmark Radar: An evidence-first index for tracking AI benchmarks</i> (Version 0.9.0). DOI: {doi}",
                st["body"],
            ),
        ]
    )

    # Page 2: methods.
    story.extend(
        [
            PageBreak(),
            p("1. System design", st["section"]),
            p(
                "Benchmark Radar gives benchmark researchers one place to scan new releases and trace each claim to its source. The collector reads public APIs, feeds, repositories, and scholarly indexes. The pipeline preserves eligible records below the recommendation threshold, so readers can audit the long tail instead of seeing a hand-picked digest.",
                st["body"],
            ),
            Spacer(1, 5),
            pipeline_figure(),
            p("1.1 Collection and normalization", st["subsection"]),
            p(
                "The configured sources cover scholarly papers, datasets, code, release notes, model cards, and community attention. Required connectors fail the collection run when they break. Optional connectors report health without blocking the other sources. The normalizer maps each item to a shared record shape and retains the source URL, publication time, description, and available artifact identifiers.",
                st["body"],
            ),
            p(
                "Identity rules merge records on exact evidence such as a DOI, arXiv identifier, or repository URL. The system reports unresolved candidates instead of joining items on title similarity alone. This choice leaves some duplicates in the corpus, but it protects distinct benchmarks with similar names.",
                st["body"],
            ),
            p("1.2 Classification and recommendation", st["subsection"]),
            p(
                "A declared taxonomy identifies benchmark, evaluation, dataset, data-quality, and agentic signals. The agentic rule requires an agent term near an evaluation term and excludes survey genres. A scoring rubric ranks records for the daily briefing. In v0.9.0, a score of 40 marks a recommendation; the pipeline still publishes eligible records below 40.",
                st["body"],
            ),
            p("1.3 Two curated measurement layers", st["subsection"]),
            Table(
                [
                    [
                        p("Layer", st["table_header"]),
                        p("Recorded fact", st["table_header"]),
                        p("Guardrail", st["table_header"]),
                    ],
                    [
                        p("Model-card adoption", st["small_bold"]),
                        p("A named vendor document reports a canonical benchmark.", st["small"]),
                        p(
                            "One document adds one mention. A mention carries no score claim.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Score observations", st["small_bold"]),
                        p(
                            "A document prints a numeric result for a named instrument.",
                            st["small"],
                        ),
                        p(
                            "Each row stores protocol, source, and reading method. Charts do not connect unrelated points.",
                            st["small"],
                        ),
                    ],
                ],
                colWidths=[1.25 * inch, 2.55 * inch, 2.8 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("GRID", (0, 0), (-1, -1), 0.45, RULE),
                        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F8FAFC")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
        ]
    )

    # Page 3: what the snapshot supports.
    story.extend(
        [
            PageBreak(),
            p("2. Cumulative corpus and query surface", st["section"]),
            p(
                "The repository stores dated snapshots and replays them into a cumulative evidence graph. Through 29 August 2026, that graph contains 7,540 source observations for 4,537 unique artifacts across 37 snapshots. The normalized benchmark catalog adds 1,173 searchable records. The latest daily snapshot contributes 528 records, of which 186 meet the recommendation threshold. The curated adoption registry contains 94 canonical benchmarks and 36 model cards or release documents. The score layer defines 70 benchmark metrics and records 285 sourced results.",
                st["body"],
            ),
            source_bars(),
            p("2.1 Local retrieval", st["subsection"]),
            p(
                f"Installed clients download a checksummed data bundle through explicit <font name='{BOLD}'>init</font> and <font name='{BOLD}'>sync</font> commands. Search then reads the active local version. The CLI and local HTTP API call the same query service and return the same JSON contract. Version 0.9.0 ranks lexical and token matches; it does not claim semantic retrieval.",
                st["body"],
            ),
            Table(
                [
                    [
                        p("Question", st["table_header"]),
                        p("Use", st["table_header"]),
                        p("Evidence returned", st["table_header"]),
                    ],
                    [
                        p("Which benchmarks cover long-horizon agents?", st["small"]),
                        p("Search the catalog and evidence history.", st["small"]),
                        p(
                            "Matched fields, token coverage, ranking reason, source URLs.",
                            st["small"],
                        ),
                    ],
                    [
                        p("Which benchmarks appear in model cards?", st["small"]),
                        p("Open the adoption ranking.", st["small"]),
                        p("Canonical benchmark and the documents that report it.", st["small"]),
                    ],
                    [
                        p("Did a score rise?", st["small"]),
                        p("Inspect points that share an instrument and protocol.", st["small"]),
                        p("Value, date, model, protocol, and cited document.", st["small"]),
                    ],
                ],
                colWidths=[2.25 * inch, 1.85 * inch, 2.5 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("GRID", (0, 0), (-1, -1), 0.45, RULE),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F8FAFC")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            p("2.2 Limits", st["subsection"]),
            bullet(
                "Public-source coverage changes with API availability, rate limits, and the configured search terms.",
                st["body"],
            ),
            bullet(
                "Taxonomy and score rules can miss relevant records or retain false positives. Source links let readers check those decisions.",
                st["body"],
            ),
            bullet(
                "Model-card adoption counts the benchmarks vendors choose to report. Score comparisons use the instrument and protocol fields stored with each observation.",
                st["body"],
            ),
            bullet(
                "Score comparisons require matching instruments and protocols. Missing protocol details limit the claim to a sourced observation.",
                st["body"],
            ),
        ]
    )

    # Page 4: reproducibility and references.
    story.extend(
        [
            PageBreak(),
            p("3. Reproducibility and access", st["section"]),
            p(
                f"This report describes Benchmark Radar v0.9.0 at Git commit <font name='{BOLD}'>98c7de3</font> and the dated data snapshot <font name='{BOLD}'>2026-08-29</font>. The repository publishes source code under the MIT License. Its CI rebuilds normalized external records, classification outputs, and the release bundle before running the test suite.",
                st["body"],
            ),
            Table(
                [
                    [
                        p("Artifact", st["table_header"]),
                        p("Permanent or canonical location", st["table_header"]),
                    ],
                    [p("Technical report", st["small"]), p(f"https://doi.org/{doi}", st["small"])],
                    [
                        p("Project and source code", st["small"]),
                        p("https://github.com/ktwu01/benchmark-radar", st["small"]),
                    ],
                    [p("Dashboard", st["small"]), p("https://benchmark-radar.org/", st["small"])],
                    [
                        p("Public JSON corpus", st["small"]),
                        p("https://benchmark-radar.org/data/radar.json", st["small"]),
                    ],
                    [
                        p("Machine-readable citation", st["small"]),
                        p(
                            "https://github.com/ktwu01/benchmark-radar/blob/main/CITATION.cff",
                            st["small"],
                        ),
                    ],
                ],
                colWidths=[1.75 * inch, 4.85 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("GRID", (0, 0), (-1, -1), 0.45, RULE),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F8FAFC")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            ),
            p("Data statement", st["subsection"]),
            p(
                f"The report statistics come from generated and versioned files in the v0.9.0 repository. <font name='{BOLD}'>site/data/radar.json</font> supplies cumulative observation, artifact, source, and snapshot counts after replaying the dated files under <font name='{BOLD}'>data/snapshots/</font>. <font name='{BOLD}'>site/data/benchmark-index.json</font> supplies the catalog count. <font name='{BOLD}'>data/model_cards.yml</font> and <font name='{BOLD}'>data/benchmark_scores.yml</font> supply the adoption and score counts.",
                st["body"],
            ),
            p("References", st["section"]),
            p(
                "[1] K. Wu. Benchmark Radar, version 0.9.0. GitHub, 2026. https://github.com/ktwu01/benchmark-radar",
                st["reference"],
            ),
            p(
                "[2] K. Wu. Benchmark Radar cumulative corpus schema. 2026. https://github.com/ktwu01/benchmark-radar/blob/main/docs/cumulative-corpus.schema.json",
                st["reference"],
            ),
            p(
                "[3] D. S. Katz et al. Recognizing the value of software: a software citation guide. F1000Research 9:1257, 2021. https://doi.org/10.12688/f1000research.26932.2",
                st["reference"],
            ),
            p(
                "[4] A. Smith, D. S. Katz, and K. E. Niemeyer. Software citation principles. PeerJ Computer Science 2:e86, 2016. https://doi.org/10.7717/peerj-cs.86",
                st["reference"],
            ),
            p(
                "[5] C. E. Jimenez et al. SWE-bench: Can language models resolve real-world GitHub issues? ICLR, 2024. https://arxiv.org/abs/2310.06770",
                st["reference"],
            ),
            p(
                "[6] Citation File Format developers. Citation File Format 1.2.0. https://citation-file-format.github.io/",
                st["reference"],
            ),
            Spacer(1, 10),
            Table(
                [
                    [
                        p(
                            "Repository: github.com/ktwu01/benchmark-radar<br/>Dashboard: benchmark-radar.org<br/>License: MIT",
                            ParagraphStyle(
                                "EndCard",
                                parent=st["body"],
                                fontName=BOLD,
                                fontSize=9,
                                leading=13,
                                textColor=NAVY,
                                alignment=TA_CENTER,
                            ),
                        )
                    ]
                ],
                colWidths=[6.6 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SKY),
                        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                ),
            ),
        ]
    )
    return story


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=NEXT_DRAFT_OUTPUT,
    )
    parser.add_argument(
        "--doi",
        default="10.5281/zenodo.22167102",
        help="Reserved DOI without the https://doi.org/ prefix.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output = args.output
    if output.resolve() == FROZEN_OUTPUT.resolve():
        parser.error("--next-draft cannot overwrite the frozen v0.9.0 PDF")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the original entry point working while the expanded system audit
    # lives in its own readable source module.
    from build_system_evaluation import EvaluationDoc, story

    doc = EvaluationDoc(str(output), doi=args.doi)
    doc.build(story(args.doi))
    print(output)


if __name__ == "__main__":
    main()
