"""Merge a frozen Claire Library, retaining every original field and decision.

Only exact registry identities or a name plus two independent resource anchors
reuse an existing record. Ambiguous candidates remain separate, so benchmark
variants never inherit each other's reported scores through a fuzzy name join.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date as calendar_date
from pathlib import Path
from urllib.parse import urlsplit

from .catalog import CatalogError, assign_slugs

DEFAULT_IMPORT = Path("data/imports/claire_library/manifest.json")
ORDER = (
    "public/library_index.json",
    "public/benchmarks.json",
    "local/library_index.json",
    "local/benchmarks.json",
)
CATEGORY_FIELDS = (
    "libraryCategories",
    "researchDirections",
    "researchTopics",
    "area",
    "applicationDomains",
    "capabilities",
    "topics",
    "capabilityGroups",
    "catalogCategories",
    "primaryDomain",
    "industrySectors",
)


def folded(value: str) -> str:
    # '+' and version digits distinguish HumanEval-X++ from HumanEval-X.
    return re.sub(r"[\s_\-]+", "", unicodedata.normalize("NFKC", value).casefold())


def anchor(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.strip("/")
    if host == "arxiv.org":
        match = re.match(r"(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$", path)
        return f"arxiv:{match[1]}" if match else None
    if host == "github.com" and len(path.split("/")) == 2:
        return "gh:" + path.removesuffix(".git").lower()
    if host == "huggingface.co" and path.startswith("datasets/"):
        parts = path.split("/")
        if len(parts) == 3:
            return "hf:" + "/".join(parts[1:]).lower()
    return None


def http_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.hostname else None


def artifacts(row: dict) -> list[dict]:
    result = {}
    for field, url in (row.get("links") or {}).items():
        url = http_url(url)
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.hostname == "img.shields.io" or parsed.path.lower().endswith(
            (".svg", ".png", ".jpg", ".gif", ".jpeg")
        ):
            continue
        identifier = anchor(url)
        kind = {"code": "repo", "data": "dataset", "paper": "paper", "pdf": "paper"}.get(field)
        if identifier:
            kind = {"arxiv": "paper", "gh": "repo", "hf": "dataset"}[identifier.split(":")[0]]
        if kind is None:
            kind = (
                "paper"
                if field == "report"
                and parsed.hostname in {"doi.org", "openreview.net", "aclanthology.org"}
                else "website"
            )
        item = {"kind": kind, "url": url}
        if identifier:
            item["id"] = identifier
        result.setdefault(identifier or url, item)
    return list(result.values())


def load_bundle(path: Path = DEFAULT_IMPORT) -> dict:
    manifest = json.loads(path.read_text())
    payload = (path.parent / manifest["file"]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
        raise CatalogError("Claire Library snapshot checksum mismatch")
    bundle = json.loads(gzip.decompress(payload))
    ids = [entry["id"] for entry in bundle["records"]]
    if len(ids) != manifest["record_count"] or len(ids) != len(set(ids)):
        raise CatalogError("Claire Library snapshot count or identity mismatch")
    return bundle


def selected(entry: dict) -> dict:
    result = {}
    for label in ORDER:
        for key, value in entry["versions"].get(label, {}).items():
            if key in {"source", "links"} and isinstance(value, dict):
                target = result.setdefault(key, {})
                for field, field_value in value.items():
                    if target.get(field) is None:
                        target[field] = copy.deepcopy(field_value)
            elif key not in result or result[key] is None:
                result[key] = copy.deepcopy(value)
    return result


def merge_library(records: list[dict], bundle: dict) -> tuple[list[dict], dict]:
    """Enrich exact matches and add unmatched records, with a total input ledger."""
    result = copy.deepcopy(records)
    by_key = {row["key"]: row for row in result}
    labels = {}
    category_spelling = {}
    for record in records:
        for value in record.get("categories") or []:
            category_spelling.setdefault(value.strip().casefold(), value)
    taxonomies = {}
    for label, manifest in bundle["manifests"].items():
        taxonomies[label] = {k: v for k, v in manifest.items() if "Taxonomy" in k}
        for taxonomy in taxonomies[label].values():
            for direction in taxonomy.get("directions", []):
                labels.setdefault(direction["id"], direction.get("name", direction["id"]))
    anchor_keys = defaultdict(set)
    name_keys = defaultdict(set)
    exact_source = {}

    def register(record):
        for item in record.get("artifacts", []):
            identity = item.get("id") or anchor(item.get("url") or "")
            if identity:
                anchor_keys[identity.casefold()].add(record["key"])
        name_keys[folded(record["name"])].add(record["key"])

    for record in result:
        register(record)
    decisions = []
    conflicts = []
    unmapped_dates = []
    existing_keys = set(by_key)
    new_keys = [f"claire-radar:{entry['id']}" for entry in bundle["records"]]
    slugs = assign_slugs(new_keys)
    used_slugs = {record["slug"] for record in records}
    for entry in bundle["records"]:
        row = selected(entry)
        name = str(row.get("name") or entry["id"])
        incoming_artifacts = artifacts(row)
        anchors = {item["id"].casefold() for item in incoming_artifacts if item.get("id")}
        source = row.get("source") or {}
        record_type = row.get("recordType") or "benchmark"
        # Family and variant records with one shared paper are not duplicates.
        fingerprint = (source.get("type"), source.get("id"), folded(name), record_type)
        matches = set()
        basis = "new_record"
        for origin in row.get("catalogSources") or []:
            prefix = {"llm-stats": "llm-stats", "opencompass": "opencompass"}.get(
                origin.get("catalog")
            )
            candidate = f"{prefix}:{origin.get('sourceId')}"
            if prefix and candidate in by_key:
                matches.add(candidate)
                basis = "exact_catalog_source_id"
        if not matches and source.get("id") and fingerprint in exact_source:
            matches.add(exact_source[fingerprint])
            basis = "exact_source_id_name_and_type"
        if not matches and record_type not in {"family", "variant"}:
            shared = defaultdict(set)
            for value in anchors:
                for key in anchor_keys[value]:
                    shared[key].add(value)
            matches = {
                key
                for key, values in shared.items()
                if len({value.split(":")[0] for value in values}) >= 2
                and folded(by_key[key]["name"]) == folded(name)
                and by_key[key].get("claire_record_type") not in {"family", "variant"}
            }
            if matches:
                basis = "exact_name_and_two_resource_types"
        candidates = sorted(matches)
        if len(matches) == 1:
            key = next(iter(matches))
            target = by_key[key]
            action = "enrich_existing" if key in existing_keys else "deduplicate_import"
        else:
            key = f"claire-radar:{entry['id']}"
            slug = slugs[key]
            while slug in used_slugs:
                slug += "-claire"
            used_slugs.add(slug)
            source_url = http_url(source.get("url")) or next(
                (
                    url
                    for url in (
                        http_url((row.get("links") or {}).get(k))
                        for k in ("report", "paper", "code", "data", "project")
                    )
                    if url
                ),
                None,
            )
            # Generated editorial prose remains in extensions, never relabelled
            # as an upstream quote in the common description field.
            target = {
                "key": key,
                "slug": slug,
                "schema_version": 1,
                "source": "claire_radar",
                "source_benchmark_id": entry["id"],
                "name": name,
                "aliases": [],
                "description": {},
                "publisher": None,
                "artifacts": [],
                "categories": [],
                "modality": None,
                "released": None,
                "sizes": [],
                "openness": {
                    "status": "unknown",
                    "code_license": None,
                    "data_license": None,
                    "evidence": [],
                },
                "provenance": {
                    "source_url": source_url,
                    "source_revision": bundle["public_revision"],
                    "origin_source_id": source.get("id"),
                    "local_only": not any(k.startswith("public/") for k in entry["versions"]),
                },
                "claire_record_type": record_type,
            }
            by_key[key] = target
            result.append(target)
            action = "add_ambiguous" if matches else "add"
        categories = set(target.get("categories") or [])
        incoming_categories = set()
        # Preserve every recorded category assignment, with its original axis
        # and public/local version available in the extension.
        for version in entry["versions"].values():
            for field in CATEGORY_FIELDS:
                values = version.get(field) or []
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    if isinstance(value, str) and value.strip():
                        label = labels.get(value, value).strip()
                        incoming_categories.add(
                            category_spelling.setdefault(label.casefold(), label)
                        )
        # Org uses the first category as a display domain. Keep its order;
        # append the imported union rather than silently recolouring charts.
        target["categories"] = list(dict.fromkeys(target.get("categories") or [])) + sorted(
            incoming_categories - categories
        )
        target["aliases"] = sorted(
            set(target.get("aliases") or [])
            | {
                alias
                for version in entry["versions"].values()
                for alias in version.get("aliases", [])
            }
        )
        existing_artifacts = {item.get("id") or item.get("url") for item in target["artifacts"]}
        for item in incoming_artifacts:
            if (item.get("id") or item["url"]) not in existing_artifacts:
                target["artifacts"].append({**item, "imported_from": entry["id"]})
        date = row.get("releasedAt")
        precision = row.get("releaseDatePrecision")
        try:
            valid_date = calendar_date.fromisoformat(str(date)).year >= 1900
        except ValueError:
            valid_date = False
        # A year/month estimate or sentinel must not become a precise day on
        # org's timeline. The original value and evidence remain lossless.
        date_source = http_url(source.get("url")) or http_url(
            (target.get("provenance") or {}).get("source_url")
        )
        can_map_date = valid_date and precision in {None, "day"} and date_source is not None
        if date and not can_map_date:
            unmapped_dates.append({"input_id": entry["id"], "value": date, "precision": precision})
        if date and target.get("released") and str(target["released"]) != str(date):
            conflicts.append(
                {
                    "input_id": entry["id"],
                    "target_key": key,
                    "field": "released",
                    "existing": target["released"],
                    "incoming": date,
                }
            )
        elif can_map_date and key not in existing_keys and not target.get("released"):
            target["released"] = date
            target["released_reference"] = {
                "source": "claire_radar",
                "input_id": entry["id"],
                "source_url": date_source,
                "precision": precision,
                "evidence": row.get("releaseEvidence")
                or row.get("firstRelease")
                or row.get("releaseDateEvidence"),
            }
        extension = target.setdefault("extensions", {}).setdefault(
            "claire_radar",
            {
                "public_revision": bundle["public_revision"],
                "records": [],
            },
        )
        extension["records"].append(copy.deepcopy(entry))
        decisions.append(
            {
                "input_id": entry["id"],
                "name": name,
                "target_key": key,
                "action": action,
                "basis": basis,
                "candidates": candidates,
                "categories": sorted(incoming_categories),
                "name_only_candidates": sorted(name_keys[folded(name)] - {key}),
            }
        )
        if source.get("id"):
            exact_source.setdefault(fingerprint, key)
        # Do not let borrowed identifiers prove subsequent identity matches.
        if action.startswith("add"):
            register(target)
    counts = defaultdict(int)
    for decision in decisions:
        counts[decision["action"]] += 1
    report = {
        "schema_version": 1,
        "input_count": len(bundle["records"]),
        "existing_count": len(records),
        "output_count": len(result),
        "actions": dict(counts),
        "decisions": decisions,
        "conflicts": conflicts,
        "unmapped_dates": unmapped_dates,
        "source_inputs": bundle["inputs"],
        "taxonomies": taxonomies,
    }
    return result, report
