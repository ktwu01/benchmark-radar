"""Attach benchmark-radar.com research directions to catalog records.

The Library groups benchmarks into taxonomy-v5 research directions that
Claire Radar assigned by model or keyword review. Those assignments are a
classification, not source text, so they never enter `categories` (which search
ranks on) and every attached direction names its upstream basis and the exact
join that carried it.

A direction reaches a record only through exact identity, tried in order:

1. the Claire Radar record id embedded in a claire_radar source record;
2. the LLM Stats source id that the .com record lists for an llm_stats record;
3. an exact artifact identifier (arXiv, GitHub, Hugging Face) shared with
   .com records that all agree on one primary direction;
4. a reviewed `equivalent` group in identity.yml whose other members carry one
   agreed direction;
5. a hand-reviewed entry in library_direction_reviews.yml, for curated records
   no exact join reaches. It only fills gaps and never overrides 1-4.

A name is never a join key, and a record whose candidates disagree stays
without a direction rather than receiving a guess. Records without a direction
remain in the corpus; the Library lists them as not yet classified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .catalog import artifact_identifier

DEFAULT_LIBRARY_DIRECTIONS_PATH = Path("data/catalog/claire_library_categories.json")
DEFAULT_DIRECTION_REVIEWS_PATH = Path("data/catalog/library_direction_reviews.yml")


class LibraryDirectionError(ValueError):
    """The exported direction file is malformed."""


def load_library_directions(path: Path = DEFAULT_LIBRARY_DIRECTIONS_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise LibraryDirectionError(f"{path}: unsupported schema_version")
    categories = {category["id"] for category in document["taxonomy"]["categories"]}
    for record_id, assignment in document["records"].items():
        if (
            assignment["primary"] not in categories
            or not set(assignment["categories"]) <= categories
        ):
            raise LibraryDirectionError(
                f"{path}: {record_id} names a direction outside the taxonomy"
            )
    return document


def load_direction_reviews(path: Path = DEFAULT_DIRECTION_REVIEWS_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if document.get("schema_version") != 1:
        raise LibraryDirectionError(f"{path}: unsupported schema_version")
    if not document.get("reviewed_by") or not document.get("reviewed_at"):
        raise LibraryDirectionError(f"{path}: reviewed_by and reviewed_at are required")
    return document


def _direction(assignment: dict[str, Any], record_id: str, join: str) -> dict[str, Any]:
    return {
        "primary": assignment["primary"],
        "categories": list(assignment["categories"]),
        "basis": assignment["basis"],
        "join": join,
        "source_record": record_id,
    }


def _agreed(record_ids: set[str], assignments: dict[str, Any]) -> dict[str, Any] | None:
    """What every candidate agrees on, or None when their primaries differ.

    Candidates sharing a primary can still list different secondary
    directions (arxiv:2409.02813 maps to two .com rows for MMMU-Pro). Copying
    one row's list would assert a secondary the other row does not, so only the
    directions every candidate lists are kept, primary first.
    """
    rows = [assignments[record_id] for record_id in sorted(record_ids)]
    primaries = {row["primary"] for row in rows}
    if len(primaries) != 1:
        return None
    shared = set.intersection(*(set(row["categories"]) for row in rows))
    first = rows[0]
    return {
        **first,
        "categories": [first["primary"], *sorted(shared - {first["primary"]})],
        "id": sorted(record_ids)[0],
    }


def assign_library_directions(
    records: list[dict[str, Any]],
    document: dict[str, Any] | None,
    equivalent_groups: list[dict[str, Any]] | None = None,
    reviews: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Map catalog record keys to their research direction, by exact identity only."""
    if not document:
        return {}
    assignments: dict[str, Any] = document["records"]
    by_llm_stats: dict[str, set[str]] = {}
    by_artifact: dict[str, set[str]] = {}
    for record_id, assignment in assignments.items():
        for source_id in assignment["llm_stats_ids"]:
            by_llm_stats.setdefault(source_id, set()).add(record_id)
        for artifact in assignment["artifacts"]:
            by_artifact.setdefault(artifact, set()).add(record_id)

    directions: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record["key"]
        claire_id = ((record.get("source_metadata") or {}).get("claire_radar") or {}).get("id")
        if record.get("source") == "claire_radar" and claire_id in assignments:
            directions[key] = _direction(assignments[claire_id], claire_id, "claire_record_id")
            continue
        if record.get("source") == "llm_stats":
            candidates = by_llm_stats.get(key.split(":", 1)[1], set())
            chosen = _agreed(candidates, assignments) if candidates else None
            if chosen:
                directions[key] = _direction(chosen, chosen["id"], "llm_stats_id")
                continue
        matched: set[str] = set()
        anchors: list[str] = []
        for artifact in record.get("artifacts") or []:
            # Curated records carry only a URL; derive the same exact identifier.
            # Canonicalize like the export does: a source can keep repository
            # casing in its stored id (OpenCompass gh:OSU-NLP-Group/...), and the
            # exported anchors are artifact_identifier's lowercase form.
            identifier = (
                artifact_identifier(str(artifact.get("url") or ""))
                or str(artifact.get("id") or "").lower()
            )
            hits = by_artifact.get(identifier or "")
            if hits:
                matched |= hits
                anchors.append(identifier)
        chosen = _agreed(matched, assignments) if matched else None
        if chosen:
            directions[key] = _direction(chosen, chosen["id"], f"artifact:{min(anchors)}")

    # A reviewed equivalent group says its members are one benchmark, so a
    # member without a direction may show the one its siblings agree on.
    for group in equivalent_groups or []:
        members = group.get("members") or []
        found = {
            directions[key]["primary"]: directions[key] for key in members if key in directions
        }
        if len(found) != 1:
            continue
        [donor] = found.values()
        for key in members:
            if key not in directions:
                directions[key] = {**donor, "join": f"identity_group:{group['group_id']}"}

    if reviews:
        # A stale key or a direction outside the taxonomy is an error: a silent
        # skip would leave a reviewed record unclassified with no signal.
        known = {record["key"] for record in records}
        categories = {category["id"] for category in document["taxonomy"]["categories"]}
        for key, primary in (reviews.get("directions") or {}).items():
            if key not in known:
                raise LibraryDirectionError(f"direction review names unknown record {key!r}")
            if primary not in categories:
                raise LibraryDirectionError(f"direction review for {key!r} names {primary!r}")
            directions.setdefault(
                key,
                {
                    "primary": primary,
                    "categories": [primary],
                    "basis": "reviewer_asserted",
                    "join": f"review:{reviews['reviewed_by']}:{reviews['reviewed_at']}",
                    "source_record": None,
                },
            )
    return directions


def library_taxonomy(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """The direction vocabulary the site renders, with the upstream it came from."""
    if not document:
        return None
    return {**document["taxonomy"], "source": document["source"]}
