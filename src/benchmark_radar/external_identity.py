"""Identity layer: the one hand-edited join between two crawls.

STRUCTURE.md Layer 2. Two crawls describe overlapping benchmarks under
different ids, and deciding that two rows are the same benchmark is a claim
that can be wrong in the exact direction that matters: publishing "GPQA
Diamond" numbers that came from GPQA full, or showing MMLU-Pro's 134 scores
under a card that measured something else. So the join is reviewed, not
computed. This module holds the two halves of that:

GENERATING CANDIDATES (`build_identity_candidates`). Every pair of records that
shares two or more independent anchors (a shared arXiv id, a shared
`gh:owner/repo`, or a shared `hf:owner/name`) is emitted for a human to promote.
A shared *name* is not an anchor: 76 names collide across the two crawls, and
the canonical-id count moved from 65 to 72 between two sessions purely by
changing the normalizer, which is why a name match alone only ever reaches the
separate `name_only` block marked insufficient.

Structurally, llm-stats carries no artifacts at all, so no llm-stats record has
any anchor and no llm-stats-to-OpenCompass pair can ever clear the two-anchor
bar automatically. That is not a gap to paper over here: a cross-source
equivalence between the score column and the identity column is exactly the
judgement a human has to make from the name and the description, and it lands in
`name_only` until they do.

LOADING THE REVIEWED FILE (`load_identity`). `identity.yml` is strict input, not
a suggestion. The loader rejects a member key that no record carries, an
`equivalent` group with fewer than two anchors, a duplicate `group_id`, and a
key claimed by two `equivalent` groups, because each of those would let a bad
merge reach the site looking reviewed.

THE TWO-ANCHOR GATE AND HAND REVIEW. The two-anchor rule governs the machine
pass: `build_identity_candidates` may only offer a pair a reviewer never has to
trust it. A group hand-written into `identity.yml` under `basis:
reviewer_asserted` is the other case -- llm-stats carries no anchor at all, so no
llm-stats-to-OpenCompass equivalence can ever clear two machine anchors, yet a
reviewer reading two cards can still confirm that llm-stats `gpqa` and
OpenCompass `1135` are one instrument. There the reviewer is one independent
warrant and the donor's own artifact is the second, so the floor drops to one
donor anchor and `reviewed_by` / `reviewed_at` become mandatory: the signature
is what replaces the missing second machine anchor, and it is recorded.

INHERITING IDENTITY ACROSS A REVIEWED GROUP (`apply_inherited_identity`). Once a
group is confirmed, a record that carries no identity of its own (every
llm-stats record) may show the donor's publisher, artifacts, release date, size
and openness instead of "not established". That crossing is deliberate and
attributed: an inherited value arrives wrapped in an `identity_inheritance` note
naming the donor source, never silently merged, and it never touches scores --
those stay partitioned by source in the shard and two rows stay two rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .external_catalog import CATALOG_SCHEMA_VERSION, ExternalCatalogError

DEFAULT_IDENTITY_PATH = Path("data/external/identity.yml")
DEFAULT_CANDIDATES_PATH = Path("data/external/identity_candidates.yml")

# The three anchor kinds STRUCTURE.md admits as evidence. A shared name is
# deliberately absent: it is vocabulary, not identity.
_ANCHOR_PREFIXES = ("arxiv:", "gh:", "hf:")


class IdentityError(ExternalCatalogError):
    """Raised when identity.yml contradicts the records it claims to join."""


def _anchors(record: dict[str, Any]) -> set[str]:
    """The arXiv / repo / dataset ids a record carries, folded for comparison.

    Ids arrive cased differently across crawls (`gh:Owner/Repo` one place,
    `gh:owner/repo` another), so they are lowercased before matching; two rows
    that cite the same repo under different casing are the same anchor.
    """
    anchors: set[str] = set()
    for artifact in record.get("artifacts") or []:
        identifier = (artifact.get("id") or "").strip().lower()
        if identifier.startswith(_ANCHOR_PREFIXES):
            anchors.add(identifier)
    return anchors


def _fold_name(name: str) -> str:
    """Case- and punctuation-folded name, for the name_only collision block."""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_identity_candidates(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Every pair worth a human's attention, split by how strong the evidence is.

    `equivalent_candidates`: pairs sharing two or more anchors, ready to be
    promoted into `identity.yml` after a look. `name_only`: cross-source pairs
    that share only a folded name, kept separate and marked insufficient so no
    one mistakes a name match for proof.
    """
    anchors_by_key = {record["key"]: _anchors(record) for record in records}
    record_by_key = {record["key"]: record for record in records}

    # Invert to anchor -> keys, then only pairs that co-occur on some anchor can
    # possibly share two; this avoids comparing all 1,148^2 pairs.
    keys_by_anchor: dict[str, set[str]] = {}
    for key, anchors in anchors_by_key.items():
        for anchor in anchors:
            keys_by_anchor.setdefault(anchor, set()).add(key)

    shared: dict[tuple[str, str], set[str]] = {}
    for anchor, keys in keys_by_anchor.items():
        ordered = sorted(keys)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                shared.setdefault((left, right), set()).add(anchor)

    equivalent_candidates: list[dict[str, Any]] = []
    for (left, right), anchors in sorted(shared.items()):
        if len(anchors) < 2:
            continue
        equivalent_candidates.append(
            {
                "members": [left, right],
                "anchors": sorted(anchors),
                "sources": [record_by_key[left]["source"], record_by_key[right]["source"]],
                "names": [record_by_key[left]["name"], record_by_key[right]["name"]],
            }
        )

    keys_by_name: dict[str, list[str]] = {}
    for record in records:
        keys_by_name.setdefault(_fold_name(record["name"]), []).append(record["key"])

    name_only: list[dict[str, Any]] = []
    for folded, keys in sorted(keys_by_name.items()):
        if not folded or len(keys) < 2:
            continue
        for i, left in enumerate(sorted(keys)):
            for right in sorted(keys)[i + 1 :]:
                # Cross-source only: two OpenCompass cards with the same name are
                # a within-crawl duplicate the anchor pass already catches when
                # it is real, and a name match inside one crawl is noise here.
                if record_by_key[left]["source"] == record_by_key[right]["source"]:
                    continue
                # A pair already provable by anchors does not need a name note.
                if len(shared.get((left, right), set())) >= 2:
                    continue
                name_only.append(
                    {
                        "members": [left, right],
                        "name": record_by_key[left]["name"],
                        "sources": [
                            record_by_key[left]["source"],
                            record_by_key[right]["source"],
                        ],
                    }
                )

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "equivalent_candidate_count": len(equivalent_candidates),
        "name_only_count": len(name_only),
        "equivalent_candidates": equivalent_candidates,
        "name_only": name_only,
    }


def write_identity_candidates(candidates: dict[str, Any], output: Path) -> Path:
    """Write the candidate file with a header a reviewer reads before promoting."""
    output.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Generated by `benchmark-radar normalize-external`. NOT loaded by the\n"
        "# build. A reviewer reads this, then hand-writes proven groups into\n"
        "# identity.yml. `equivalent_candidates` share two or more anchors and are\n"
        "# ready to promote; `name_only` share only a name, which STRUCTURE.md says\n"
        "# is not an anchor, so they need a human to confirm or reject them.\n"
    )
    output.write_text(
        header + yaml.safe_dump(candidates, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    return output


@dataclass
class IdentityIndex:
    """The reviewed join, resolved against the records it applies to."""

    equivalent_groups: list[dict[str, Any]] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    # key -> the other members of its equivalent group, as sibling descriptors.
    siblings_by_key: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # key -> the donor it inherits identity from, for records in a reviewed
    # `equivalent` group that named an `inherit_from`.
    inheritance_by_key: dict[str, dict[str, Any]] = field(default_factory=dict)

    def siblings_for(self, key: str) -> list[dict[str, Any]]:
        return self.siblings_by_key.get(key, [])

    def inheritance_for(self, key: str) -> dict[str, Any] | None:
        return self.inheritance_by_key.get(key)


def _sibling(record: dict[str, Any], relation: str) -> dict[str, Any]:
    """The lite descriptor a shard carries for a cross-linked record."""
    return {
        "key": record["key"],
        "slug": record["slug"],
        "name": record["name"],
        "source": record["source"],
        "relation": relation,
    }


def load_identity(
    records: list[dict[str, Any]],
    path: Path = DEFAULT_IDENTITY_PATH,
) -> IdentityIndex:
    """Load and validate the hand-edited identity file against the records.

    Missing file is not an error: the identity layer is the one piece the
    catalog can ship without, so an absent file resolves to no siblings rather
    than a failed build.
    """
    if not path.exists():
        return IdentityIndex()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise IdentityError(
            f"{path}: schema_version {data.get('schema_version')!r} != {CATALOG_SCHEMA_VERSION}"
        )

    record_by_key = {record["key"]: record for record in records}
    equivalent = data.get("equivalent") or []
    variants = data.get("variants") or []

    seen_group_ids: set[str] = set()
    key_to_group: dict[str, str] = {}
    siblings_by_key: dict[str, list[dict[str, Any]]] = {}
    inheritance_by_key: dict[str, dict[str, Any]] = {}

    for group in equivalent:
        group_id = group.get("group_id")
        if not group_id:
            raise IdentityError(f"{path}: an equivalent group is missing group_id")
        if group_id in seen_group_ids:
            raise IdentityError(f"{path}: duplicate group_id {group_id!r}")
        seen_group_ids.add(group_id)

        anchors = group.get("anchors") or []
        if group.get("basis") == "reviewer_asserted":
            # A hand-reviewed cross-source equivalence. The two-anchor bar
            # governs machine candidates; here the reviewer's signature is the
            # second warrant, so it is mandatory and the donor need supply only
            # one anchor (llm-stats can supply none). See the module docstring.
            if not group.get("reviewed_by") or not group.get("reviewed_at"):
                raise IdentityError(
                    f"{path}: reviewer_asserted group {group_id!r} needs "
                    "reviewed_by and reviewed_at"
                )
            if len(anchors) < 1:
                raise IdentityError(
                    f"{path}: reviewer_asserted group {group_id!r} has no donor anchor; "
                    "at least one is required"
                )
        elif len(anchors) < 2:
            # STRUCTURE.md: a group with fewer than two independent anchors is a
            # candidate, not an equivalence. This is the enforcement point.
            raise IdentityError(
                f"{path}: equivalent group {group_id!r} has {len(anchors)} anchor(s); "
                "two independent anchors are required"
            )

        members = group.get("members") or []
        for member in members:
            if member not in record_by_key:
                raise IdentityError(
                    f"{path}: equivalent group {group_id!r} names {member!r}, "
                    "which is not a source record"
                )
            if member in key_to_group:
                raise IdentityError(
                    f"{path}: {member!r} is in two equivalent groups "
                    f"({key_to_group[member]!r} and {group_id!r})"
                )
            key_to_group[member] = group_id

        for member in members:
            siblings_by_key[member] = [
                _sibling(record_by_key[other], "equivalent") for other in members if other != member
            ]

        # `inherit_from` names the member whose identity the others may show.
        # It must be one of the members, and it drives `apply_inherited_identity`.
        inherit_from = group.get("inherit_from")
        if inherit_from is not None:
            if inherit_from not in members:
                raise IdentityError(
                    f"{path}: equivalent group {group_id!r} inherit_from "
                    f"{inherit_from!r} is not one of its members"
                )
            # `reviewed_at` is often written unquoted, which YAML parses to a
            # date; the note lands in a shard and is JSON-serialized, so it is
            # stringified here rather than crashing json.dumps.
            reviewed_at = group.get("reviewed_at")
            for member in members:
                if member == inherit_from:
                    continue
                inheritance_by_key[member] = {
                    "donor_key": inherit_from,
                    "group_id": group_id,
                    "reviewed_by": group.get("reviewed_by"),
                    "reviewed_at": str(reviewed_at) if reviewed_at is not None else None,
                }

    for variant in variants:
        key = variant.get("key")
        if key not in record_by_key:
            raise IdentityError(f"{path}: variant names {key!r}, which is not a source record")
        of_key = variant.get("of")
        # `of` may reference a canonical benchmark id that has no crawled record,
        # so it is only cross-linked as a sibling when it resolves to one here.
        if of_key in record_by_key:
            siblings_by_key.setdefault(of_key, []).append(
                _sibling(record_by_key[key], f"variant:{variant.get('relation', 'related')}")
            )
            siblings_by_key.setdefault(key, []).append(
                _sibling(record_by_key[of_key], "variant:of")
            )

    return IdentityIndex(
        equivalent_groups=list(equivalent),
        variants=list(variants),
        siblings_by_key=siblings_by_key,
        inheritance_by_key=inheritance_by_key,
    )


# The identity fields a record may inherit from its equivalent-group donor.
# Scores are deliberately absent: they are partitioned by source in the shard
# and never join here, so inheritance can only ever fill in provenance.
INHERITED_IDENTITY_FIELDS = ("publisher", "artifacts", "released", "sizes", "openness")


def _is_empty_identity(value: Any) -> bool:
    """Whether a field holds nothing a reader could act on.

    None, an empty list and an empty dict are empty. An `openness` block is
    empty when it reached no verdict -- status `unknown` with neither licence --
    which is exactly the state every llm-stats record ships in.
    """
    if value is None:
        return True
    if isinstance(value, dict):
        if not value:
            return True
        if value.get("status") == "unknown":
            return not value.get("code_license") and not value.get("data_license")
        return False
    if isinstance(value, list):
        return not value
    return False


def apply_inherited_identity(
    records: list[dict[str, Any]],
    identity: IdentityIndex,
) -> list[dict[str, Any]]:
    """Fill a record's empty identity fields from its reviewed-group donor.

    A record is only ever *given* a value it did not already have, and the value
    arrives with an `identity_inheritance` note naming the donor source, so the
    site can say "Anthropic (via the OpenCompass card)" and never presents a
    borrowed value as the source's own. Records outside a reviewed `inherit_from`
    group pass through untouched, and no score is read or written: inheritance is
    Layer 2 identity only.
    """
    by_key = {record["key"]: record for record in records}
    resolved: list[dict[str, Any]] = []
    for record in records:
        inheritance = identity.inheritance_for(record["key"])
        donor = by_key.get(inheritance["donor_key"]) if inheritance else None
        if donor is None:
            resolved.append(record)
            continue
        merged = dict(record)
        inherited_fields: list[str] = []
        for field_name in INHERITED_IDENTITY_FIELDS:
            # Only ever fill a field the record itself left empty, and only from
            # a donor that actually carries one.
            if not _is_empty_identity(merged.get(field_name)):
                continue
            donor_value = donor.get(field_name)
            if _is_empty_identity(donor_value):
                continue
            merged[field_name] = donor_value
            inherited_fields.append(field_name)
        if inherited_fields:
            merged["identity_inheritance"] = {
                "donor_key": donor["key"],
                "donor_source": donor["source"],
                "donor_name": donor["name"],
                "group_id": inheritance["group_id"],
                "reviewed_by": inheritance["reviewed_by"],
                "reviewed_at": inheritance["reviewed_at"],
                "fields": inherited_fields,
            }
        resolved.append(merged)
    return resolved
