"""Sharded files behind archive-wide homepage search (issue #1183).

`dashboard_search_index` picks the rows an All dates search can return. Shipping
them as one JSON file made the first search download every summary ever
collected: 18.4 MB of gzip on 2026-11-19, growing about 6 MB a month. This
module writes the same rows in three parts, so a search downloads only what the
query needs:

* ``radar-search.json`` holds, per row, only the fields Today filters and sorts
  on, in columns. Summaries, titles, and authors are not in it.
* ``<base>/g/<n>.json.gz`` holds a positional trigram index over the exact text the
  page searches (title, summary, and source, lowercased). A query downloads the
  shards of a few of its trigrams and still matches text anywhere, exactly as
  the radar.json path does; one- and two-character queries read row lists.
* ``<base>/r/<n>.json.gz`` holds the complete rows, ``ROW_SHARD_SIZE`` per file, so
  a page of results downloads only the rows it shows.

Shards are stored gzip-compressed, because GitHub Pages caps a site at 1 GB and
the uncompressed index alone would be about 300 MB; the page inflates them with
DecompressionStream, so disk size equals download size.

Positions and lengths count UTF-16 code units and the gram-to-shard hash is
defined on them, because that is how JavaScript slices and compares strings.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from array import array
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
ROW_SHARD_SIZE = 32
GRAM_SHARDS = 4096

# Read by filteredObservations, sortObservations, syncFilters, and the result
# counts. Everything a card shows comes from the row shards instead.
LIGHT_FIELDS = (
    "snapshot_date",
    "snapshot_generated_at",
    "observation_kind",
    "event_kind",
    "source",
    "categories",
    "organizations",
    "published_at",
    "updated_at",
    "discovered_at",
    "recency_score",
    "total_score",
    "metrics",
    "parser_version",
)
DICTIONARY_FIELDS = {
    "snapshot_date",
    "snapshot_generated_at",
    "observation_kind",
    "event_kind",
    "source",
    "parser_version",
}
LIST_FIELDS = {"categories", "organizations"}


def js_string(value: Any, *, missing: bool = False) -> str:
    """Return what a JavaScript template literal prints for a JSON value."""
    if missing:
        return "undefined"
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, list):
        return ",".join("" if item is None else js_string(item) for item in value)
    return "[object Object]"


def _field(item: dict[str, Any], key: str) -> str:
    return js_string(item.get(key), missing=key not in item)


def search_haystack(item: dict[str, Any]) -> str:
    """The text filteredObservations matches a query against."""
    return f"{_field(item, 'title')} {_field(item, 'summary')} {_field(item, 'source')}".lower()


def record_key(item: dict[str, Any]) -> str:
    """Python twin of observationRecordKey in app.js."""
    if item.get("observation_kind") == "attention":
        identity = (
            item.get("observation_id") or f"{_field(item, 'source')}\0{_field(item, 'source_id')}"
        )
        return f"attention\0{js_string(identity)}"
    return f"evidence\0{_field(item, 'source')}\0{_field(item, 'source_id')}"


def _tie_text(item: dict[str, Any]) -> str:
    url = item.get("url") or ""
    title = item.get("title") or ""
    return f"{js_string(url)}\0{js_string(title)}"


def _code_units(text: str) -> bytes:
    # Big-endian UTF-16 bytes compare in the same order JavaScript compares
    # strings with < and >.
    return text.encode("utf-16-be", "surrogatepass")


def gram_shard(units: tuple[int, ...] | list[int], shards: int = GRAM_SHARDS) -> int:
    """Shard of a gram, identical to gramShard in app.js."""
    value = 0
    for unit in units:
        value = (value * 31 + unit) & 0xFFFFFFFF
    return value % shards


def _gram_text(units: tuple[int, ...]) -> str:
    return "".join(chr(unit) for unit in units)


def _row_order(observations: list[dict[str, Any]]) -> list[int]:
    """Newest day first; within a day, sortObservations' final tie-break order.

    sortObservations reaches its last tie-break only between rows of the same
    day, so within a day the row number itself is that order and the page
    needs neither identifiers nor titles to sort. Newest first also puts the
    first page of an unfiltered All dates list in the first row shard.
    """
    by_tie = sorted(
        range(len(observations)),
        key=lambda index: (
            _code_units(record_key(observations[index])),
            _code_units(_tie_text(observations[index])),
        ),
    )
    # Stable, so each day keeps the tie-break order.
    return sorted(
        by_tie, key=lambda index: str(observations[index].get("snapshot_date") or ""), reverse=True
    )


def _shared_records(keys: list[str]) -> list[list[int]]:
    """Rows that are sightings of one record, for latestObservationsByRecord."""
    groups: dict[str, list[int]] = {}
    for row, key in enumerate(keys):
        groups.setdefault(key, []).append(row)
    return [rows for rows in groups.values() if len(rows) > 1]


def _columns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for field in LIGHT_FIELDS:
        values = [row.get(field) for row in rows]
        if field in LIST_FIELDS:
            vocabulary = sorted({value for items in values for value in items or []})
            position = {value: index for index, value in enumerate(vocabulary)}
            columns[field] = {
                "dictionary": vocabulary,
                "lists": [
                    None if items is None else [position[value] for value in items]
                    for items in values
                ],
            }
        elif field in DICTIONARY_FIELDS:
            vocabulary = sorted({value for value in values if value is not None})
            position = {value: index for index, value in enumerate(vocabulary)}
            columns[field] = {
                "dictionary": vocabulary,
                "values": [None if value is None else position[value] for value in values],
            }
        else:
            columns[field] = {"values": values}
    return columns


class _Postings:
    """Per-gram integer streams, built row by row in ascending row order."""

    def __init__(self) -> None:
        self.streams: dict[tuple[int, ...], array] = {}
        self.last_row: dict[tuple[int, ...], int] = {}

    def add_row(self, gram: tuple[int, ...], row: int, positions: list[int] | None) -> None:
        stream = self.streams.get(gram)
        if stream is None:
            stream = self.streams[gram] = array("I")
        stream.append(row - self.last_row.get(gram, -1) - 1)
        self.last_row[gram] = row
        if positions is not None:
            stream.append(len(positions))
            previous = 0
            for position in positions:
                stream.append(position - previous)
                previous = position


def _index_rows(haystacks: list[str]) -> _Postings:
    postings = _Postings()
    for row, haystack in enumerate(haystacks):
        units = array("H", _code_units(haystack))
        if sys.byteorder == "little":
            units.byteswap()
        positions: dict[tuple[int, ...], list[int]] = {}
        short: set[tuple[int, ...]] = set()
        count = len(units)
        for index in range(count):
            short.add((units[index],))
            if index + 1 < count:
                short.add((units[index], units[index + 1]))
                if index + 2 < count:
                    key = (units[index], units[index + 1], units[index + 2])
                    found = positions.get(key)
                    if found is None:
                        positions[key] = [index]
                    else:
                        found.append(index)
        for gram in short:
            postings.add_row(gram, row, None)
        for gram, found in positions.items():
            postings.add_row(gram, row, found)
    return postings


def search_index_files(
    dashboard: dict[str, Any], observations: list[dict[str, Any]]
) -> Iterator[tuple[str, Any]]:
    """Yield (relative path, JSON value) for the sharded search index.

    Shards are yielded one at a time so the writer never holds every posting
    list as Python integers at once.
    """
    order = _row_order(observations)
    rows = [observations[index] for index in order]
    keys = [record_key(row) for row in rows]
    generated_at = dashboard.get("generated_at")
    digest = hashlib.sha256(
        json.dumps([generated_at, rows], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    base = f"search/{digest}"
    yield (
        "radar-search.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "latest_date": dashboard.get("latest_date"),
            "row_count": len(rows),
            "base": base,
            "row_shard_size": ROW_SHARD_SIZE,
            "gram_shards": GRAM_SHARDS,
            "columns": _columns(rows),
            "shared_records": _shared_records(keys),
        },
    )
    for start in range(0, len(rows), ROW_SHARD_SIZE):
        yield (
            f"{base}/r/{start // ROW_SHARD_SIZE}.json.gz",
            {"rows": rows[start : start + ROW_SHARD_SIZE]},
        )
    postings = _index_rows([search_haystack(row) for row in rows]).streams
    by_shard: dict[int, list[tuple[int, ...]]] = {}
    for gram in postings:
        by_shard.setdefault(gram_shard(gram), []).append(gram)
    # Every shard exists, empty or not, so a missing file always means a
    # deploy mismatch and never silently reads as "no match".
    for shard in range(GRAM_SHARDS):
        yield (
            f"{base}/g/{shard}.json.gz",
            {_gram_text(gram): postings.pop(gram).tolist() for gram in by_shard.get(shard, [])},
        )


def write_search_index(
    search_path: Path, dashboard: dict[str, Any], observations: list[dict[str, Any]]
) -> None:
    """Write the search table at search_path and replace the shards beside it."""
    # Shards from an earlier build would only be dead weight in the Pages
    # artifact: the page reads the directory its radar-search.json names.
    shutil.rmtree(search_path.parent / "search", ignore_errors=True)
    for relative, value in search_index_files(dashboard, observations):
        path = search_path if relative == "radar-search.json" else search_path.parent / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # ASCII escapes keep lone surrogates, which a gram can split a
        # character into, valid in the file and intact for JSON.parse.
        text = json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n"
        if relative.endswith(".gz"):
            path.write_bytes(gzip.compress(text.encode("ascii"), compresslevel=6, mtime=0))
        else:
            path.write_text(text, encoding="utf-8")
