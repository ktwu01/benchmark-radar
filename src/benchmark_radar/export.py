"""Standalone, citable exports of the Model Card Adoption Rank (issue #88).

The ranking already exists, and until now it existed in exactly one place: a
key inside `site/data/radar.json`, a multi-megabyte bundle that also carries the
full daily corpus, its entity graph, and every observation. Anyone wanting to
quote the ranking in a blog post, a README, a newsletter, or a paper appendix
had to download all of that and know which key to read.

That is the difference between a site people visit and a source people cite.
These exports close it by publishing the same ranking as small, self-describing
files, each one usable without the others:

`leaderboard.json`
    The ranking and its provenance, without the daily corpus.
`leaderboard.csv`
    One row per benchmark, for a spreadsheet or a dataframe.
`leaderboard.md`
    A paste-ready table for a README or a blog post.
`leaderboard-badge.json`
    A Shields endpoint, so a badge can track the registry instead of freezing
    at whatever the number was when someone typed it.

Every export is derived from `adoption_rank`, never from a re-read of the
dashboard bundle or a second pass over the registry. A consumer who cites the
CSV and a reader looking at the dashboard must not be able to see two different
rankings, and the only way to guarantee that is for one function to produce
both.

Each file restates the `measures` caveat rather than assuming the reader
arrived with it. These artifacts are built to travel: the CSV will be opened
without the README beside it, and a ranking that reads as a quality ordering
once separated from its disclaimer is precisely the misreading the registry is
careful to prevent.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .model_cards import DEFAULT_REGISTRY_PATH, build_adoption_rank

# The exports are versioned separately from the registry schema. A consumer
# pinning to a column layout is making a different promise than the registry
# makes about its own fields, and folding the two together would force a
# breaking bump on every reader whenever an internal registry detail moved.
EXPORT_SCHEMA_VERSION = 1

# The default top-N for the Markdown table. The full ranking runs to every
# benchmark in the registry including those no card reports, which is the right
# content for the JSON and CSV and the wrong content for a README: a table
# hundreds of rows long is not pasted, it is scrolled past.
DEFAULT_TABLE_LIMIT = 20

_CSV_COLUMNS = (
    "rank",
    "benchmark_id",
    "name",
    "domain",
    "card_count",
    "organization_count",
    "adoption_share",
    "released",
    "url",
    "organizations",
    "caveat",
)


def _rows(leaderboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten entries to one row per benchmark.

    `adopters` is dropped here and kept in the JSON export. It is a nested list
    of documents per benchmark, which has no faithful representation in a single
    CSV cell: joining it into one string produces a field that has to be parsed
    again to be used, and truncating it silently discards evidence. A consumer
    who needs the card-level edges needs the JSON, and the JSON is one file
    away.
    """
    rows = []
    for entry in leaderboard["entries"]:
        rows.append(
            {
                "rank": entry["rank"],
                "benchmark_id": entry["benchmark_id"],
                "name": entry["name"],
                "domain": entry["domain"],
                "card_count": entry["card_count"],
                "organization_count": entry["organization_count"],
                "adoption_share": entry["adoption_share"],
                "released": entry["released"] or "",
                "url": entry["url"] or "",
                # Semicolon-joined, not comma-joined: a comma inside a field
                # forces the whole cell into quotes and is the single most
                # common way a hand-inspected CSV column looks misaligned.
                "organizations": "; ".join(entry["organizations"]),
                "caveat": entry["caveat"] or "",
            }
        )
    return rows


def leaderboard_json(leaderboard: dict[str, Any], *, source_url: str | None = None) -> str:
    """The ranking as a standalone document, corpus excluded.

    Deliberately carries `measures`, the counting rule, and the totals it was
    computed against. A count of 23 is not interpretable without knowing that
    the denominator is 30 documents, and a reader who fetched this file
    directly has no other way to learn it.
    """
    document = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "registry_schema_version": leaderboard["schema_version"],
        "measures": leaderboard["measures"],
        # Stated explicitly because it is the question every reader of a
        # ranking asks first, and the answer here is unusual enough that
        # leaving it implicit invites the wrong assumption.
        "counting_unit": (
            "One document, not one result row. A card reporting a benchmark in "
            "several configurations contributes exactly one adoption."
        ),
        "model_card_count": leaderboard["model_card_count"],
        "benchmark_count": leaderboard["benchmark_count"],
        "organization_count": leaderboard["organization_count"],
        "organizations": leaderboard["organizations"],
        "domains": leaderboard["domains"],
        "entries": leaderboard["entries"],
        "model_cards": leaderboard["model_cards"],
    }
    if source_url:
        document["source_url"] = source_url
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def leaderboard_csv(leaderboard: dict[str, Any]) -> str:
    r"""The ranking as one row per benchmark.

    Written with `\r\n`, the line terminator RFC 4180 specifies, rather than
    the platform default. These files are published as release assets and read
    by tools on every platform, so the terminator is fixed by the format rather
    than by whichever runner generated the file.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(_rows(leaderboard))
    return buffer.getvalue()


def _escape_cell(value: str) -> str:
    """Neutralize characters that would break out of a Markdown table cell.

    A caveat containing a pipe would end its cell early and shift every column
    after it. The registry's caveats are prose written by contributors, so this
    is a matter of when rather than whether. Newlines get the same treatment:
    a table row is a single line by definition.
    """
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def leaderboard_markdown(
    leaderboard: dict[str, Any],
    *,
    limit: int | None = DEFAULT_TABLE_LIMIT,
    source_url: str | None = None,
) -> str:
    """A paste-ready table, truncated to the rows worth pasting.

    The truncation is announced in the output rather than performed silently. A
    table that stops at 20 with no note reads as a complete ranking of 20
    benchmarks, which is a different and false claim about the registry.
    """
    entries = leaderboard["entries"]
    shown = entries if limit is None else entries[:limit]

    lines = [
        "| Rank | Benchmark | Domain | Model cards | Organizations |",
        "|---:|---|---|---:|---:|",
    ]
    for entry in shown:
        name = _escape_cell(entry["name"])
        # Linked only when the registry recorded a URL. A bare `[name]()` renders
        # as a dead link, which is worse than plain text.
        label = f"[{name}]({entry['url']})" if entry["url"] else name
        lines.append(
            f"| {entry['rank']} | {label} | {_escape_cell(entry['domain'])} "
            f"| {entry['card_count']} | {entry['organization_count']} |"
        )

    total_cards = leaderboard["model_card_count"]
    total_orgs = leaderboard["organization_count"]
    footer = [
        "",
        (
            f"Across {total_cards} curated model cards, system cards, and technical "
            f"reports from {total_orgs} organizations. The counted unit is the "
            f"document, not the result row."
        ),
        "",
        f"_{leaderboard['measures']}_",
    ]
    if limit is not None and len(entries) > len(shown):
        # Appended to the scope sentence rather than added as its own line, so
        # the reader learns the denominator and the truncation in one place
        # instead of meeting a bare row count before knowing what it is out of.
        footer[1] += (
            f" Showing the top {len(shown)} of {len(entries)} tracked benchmarks; "
            "benchmarks reported by no card are tracked and ranked last."
        )
    if source_url:
        footer.append("")
        footer.append(f"Source: <{source_url}>")
    return "\n".join([*lines, *footer]) + "\n"


def leaderboard_badge(leaderboard: dict[str, Any]) -> str:
    """A Shields.io endpoint describing registry coverage.

    Reports what the registry contains, not what rank a benchmark holds. A badge
    is a single number seen without context, and "GPQA Diamond is #1" shown
    that way is exactly the quality claim the ranking does not make. Coverage
    carries no such reading and is the number that actually changes as the
    registry grows.
    """
    document = {
        "schemaVersion": 1,
        "label": "model cards tracked",
        "message": (
            f"{leaderboard['model_card_count']} cards · {leaderboard['benchmark_count']} benchmarks"
        ),
        "color": "blue",
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write_exports(
    output_dir: Path,
    *,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    table_limit: int | None = DEFAULT_TABLE_LIMIT,
    source_url: str | None = None,
) -> dict[str, Path]:
    """Build every export from one ranking and write them side by side.

    `build_adoption_rank` is called exactly once. Calling it per format would
    read and validate the registry four times for identical output, and would
    open the door to four files disagreeing if the registry changed underneath
    a slow run.
    """
    leaderboard = build_adoption_rank(registry_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "json": (
            output_dir / "leaderboard.json",
            leaderboard_json(leaderboard, source_url=source_url),
        ),
        "csv": (output_dir / "leaderboard.csv", leaderboard_csv(leaderboard)),
        "markdown": (
            output_dir / "leaderboard.md",
            leaderboard_markdown(leaderboard, limit=table_limit, source_url=source_url),
        ),
        "badge": (output_dir / "leaderboard-badge.json", leaderboard_badge(leaderboard)),
    }

    written: dict[str, Path] = {}
    for name, (path, content) in artifacts.items():
        # newline="" keeps the CSV's explicit \r\n terminators intact; without
        # it Python's translation would turn them into \r\r\n on Windows.
        path.write_text(content, encoding="utf-8", newline="")
        written[name] = path
    return written
