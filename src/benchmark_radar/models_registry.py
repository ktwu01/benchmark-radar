"""Model identities and their evidence from the shared benchmark catalog."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
DEFAULT_REGISTRY_OUTPUT = Path("site/data/models.json")


def model_key(model: str, organization: str) -> str:
    """Readable base slug; collisions are resolved after exact label grouping."""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{organization} {model}".lower()).strip("-")
    return slug or "unnamed"


@dataclass(frozen=True)
class ModelSource:
    source: str
    evidence_id: str
    payload: dict[str, Any]


@dataclass
class ModelRecord:
    key: str
    model: str
    organization: str
    sources: list[ModelSource] = field(default_factory=list)

    @property
    def provenance_sources(self) -> list[str]:
        return sorted({entry.source for entry in self.sources})

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "model": self.model,
            "organization": self.organization,
            "provenance_sources": self.provenance_sources,
            "sources": [
                {"source": row.source, "evidence_id": row.evidence_id, "payload": row.payload}
                for row in self.sources
            ],
        }


def build_registry(radar: dict[str, Any], shard_dir: Path) -> dict[str, ModelRecord]:
    """Read model observations and document subjects through one evidence path.

    ``radar`` remains an unused positional argument for local caller compatibility.
    The catalog now includes those reports. Reading them again would double count.
    Display labels choose the same deterministic spelling regardless of source or
    input order. This does not merge distinct source model IDs used by chart counts.
    """
    by_identity: dict[tuple[str, str], ModelRecord] = {}
    seen: set[tuple[str, str]] = set()

    def add(source: str, evidence_id: str, model: str, organization: str, payload: dict) -> None:
        if not model or not organization or (source, evidence_id) in seen:
            return
        seen.add((source, evidence_id))
        # A filename-safe slug discards meaningful characters (Command A+)
        # and organization/model boundaries. It cannot establish equivalence.
        # Only case-only spellings of the same two labels share a record.
        identity = (organization.lower(), model.lower())
        key = model_key(model, organization)
        record = by_identity.setdefault(identity, ModelRecord(key, model, organization))
        record.model = min(record.model, model, key=lambda value: (value.casefold(), value))
        record.organization = min(
            record.organization, organization, key=lambda value: (value.casefold(), value)
        )
        record.sources.append(ModelSource(source, evidence_id, payload))

    for path in sorted(Path(shard_dir).glob("*.json")):
        shard = json.loads(path.read_text(encoding="utf-8"))
        record = shard.get("record") or {}
        for document in record.get("documents") or []:
            if document.get("model_name"):
                add(
                    document["source"],
                    document["id"],
                    document["model_name"],
                    document.get("organization") or "",
                    document,
                )
        for source, payload in (shard.get("scores_by_source") or {}).items():
            for row in payload.get("rows") or []:
                add(
                    source,
                    row.get("obs_id") or "",
                    row.get("model_name") or "",
                    row.get("organization") or "",
                    row,
                )
    slug_counts = Counter(record.key for record in by_identity.values())
    # Reserve natural slugs too: a generated suffix must not take a different
    # model's ordinary key. Common non-colliding keys remain unchanged.
    reserved = set(slug_counts)
    registry = {}
    for identity, record in sorted(by_identity.items()):
        if slug_counts[record.key] > 1:
            digest = sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()
            base = f"{record.key}-{digest}"
            key = base
            suffix = 1
            while key in reserved:
                suffix += 1
                key = f"{base}-{suffix}"
            record.key = key
            reserved.add(key)
        record.sources.sort(key=lambda row: (row.source, row.evidence_id))
        registry[record.key] = record
    return dict(sorted(registry.items()))


def summarize(registry: dict[str, ModelRecord]) -> dict[str, Any]:
    counts = Counter(source for record in registry.values() for source in record.provenance_sources)
    return {
        "schema_version": SCHEMA_VERSION,
        "model_count": len(registry),
        "source_counts": dict(sorted(counts.items())),
        "multiple_sources": sum(len(record.provenance_sources) > 1 for record in registry.values()),
        "organizations": sorted({record.organization for record in registry.values()}),
    }


def write_model_registry(radar_path: Path, shard_dir: Path, output: Path) -> dict[str, Any]:
    """Publish model identities; source observations and citations stay in shards."""
    shard_dir = Path(shard_dir)
    if not shard_dir.is_dir() or next(shard_dir.glob("*.json"), None) is None:
        raise FileNotFoundError(
            f"{shard_dir} holds no benchmark shards. Run `benchmark-radar normalize-catalog` "
            "before building the model registry; a partial corpus is not a substitute."
        )
    registry = build_registry({}, shard_dir)
    report = summarize(registry)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                **report,
                "models": [
                    {
                        "key": record.key,
                        "model": record.model,
                        "organization": record.organization,
                        "provenance_sources": record.provenance_sources,
                        "source_counts": dict(
                            sorted(Counter(row.source for row in record.sources).items())
                        ),
                    }
                    for record in registry.values()
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return report
