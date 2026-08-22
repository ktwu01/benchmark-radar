"""One record per model, whichever layer reported it.

A model is a model. Gemini 3.1 Pro and MiMo-V2.5-Pro are both things a lab
shipped, both carry benchmark scores, and both draw a brand glyph on a chart.
Until now they lived in two shapes that shared exactly one field name --
`organization` -- because the project had never modelled the *model*. It
modelled the two things that mention one: a curated document (`model_cards.yml`,
with a URL and a publication date) and a crawled score observation (an
aggregator row, with a value and a rank). Asking "what models do we know about?"
meant reading two structures and reconciling them at every call site, and every
consumer that forgot the second one silently dropped 323 models.

This module is that missing structure. One `ModelRecord` per (model,
organization), built from both layers, with a stable id.

WHAT UNIFYING DOES AND DOES NOT MEAN

The record is unified; the evidence stays labelled. Every field that only one
layer can support is carried per-source in `sources`, never flattened up into
the record as though both layers had established it:

  * A curated card establishes a document -- `url`, `published`, `retrieved_at`.
    A crawled row has no document, and inventing one would be a wrong citation.
  * A crawled row establishes an observation -- a value, an aggregator, a rank.
    It records no protocol and no evaluation date, so `comparable_group` stays
    null and two crawled values never join.

So `ModelRecord.sources` is a list, and `layers` says which kinds are present.
A model known to both layers is ONE record carrying both, which is the join the
old shape could not express at all. What the record never does is average them,
pick a winner, or let a crawled row inherit a curated document's authority.

This is the single source of truth for "which models exist". Consumers read it
instead of walking `model_cards` and the shards separately.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

DEFAULT_REGISTRY_OUTPUT = Path("site/data/models.json")

CURATED = "curated"
CRAWLED = "crawled"


def model_key(model: str, organization: str) -> str:
    """A stable, filesystem- and URL-safe id for a model.

    Keyed on (name, organization) rather than on either alone: two labs ship
    models whose short names collide, and one lab renames across versions.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", f"{organization} {model}".lower()).strip("-")
    return slug or "unnamed"


@dataclass(frozen=True)
class ModelSource:
    """One layer's evidence about a model.

    `layer` is CURATED or CRAWLED. `payload` is that layer's own record,
    unaltered -- the curated card or the crawled observation as it was written.
    Nothing is renamed into a shared vocabulary, because a shared name would
    imply the two carry the same kind of claim.
    """

    layer: str
    source_id: str
    payload: dict[str, Any]


@dataclass
class ModelRecord:
    """Everything known about one model, across every layer that reported it."""

    key: str
    model: str
    organization: str
    sources: list[ModelSource] = field(default_factory=list)

    @property
    def layers(self) -> list[str]:
        """Which layers reported this model, curated first."""
        seen = {source.layer for source in self.sources}
        return [layer for layer in (CURATED, CRAWLED) if layer in seen]

    @property
    def is_curated(self) -> bool:
        return CURATED in self.layers

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "model": self.model,
            "organization": self.organization,
            "layers": self.layers,
            "sources": [
                {"layer": s.layer, "source_id": s.source_id, "payload": s.payload}
                for s in self.sources
            ],
        }


def _curated_models(radar: dict[str, Any]) -> Iterable[tuple[str, str, str, dict]]:
    board = radar.get("model_card_leaderboard") or {}
    for card in board.get("model_cards") or []:
        model = card.get("model")
        organization = card.get("organization")
        if model and organization:
            yield model, organization, card.get("model_card_id") or "", card


def _crawled_models(shard_dir: Path) -> Iterable[tuple[str, str, str, dict]]:
    for shard in sorted(shard_dir.glob("*.json")):
        payloads = json.loads(shard.read_text(encoding="utf-8")).get("scores_by_source") or {}
        for source, payload in payloads.items():
            for row in payload.get("rows") or []:
                model = row.get("model_name")
                organization = row.get("organization")
                if model and organization:
                    yield model, organization, row.get("obs_id") or source, row


def build_registry(radar: dict[str, Any], shard_dir: Path) -> dict[str, ModelRecord]:
    """Every model either layer knows about, keyed by `model_key`.

    Curated sources are added first so a model present in both reads as curated
    at a glance, but both are kept: the point of one structure is that neither
    layer's evidence disappears because the other exists.
    """
    registry: dict[str, ModelRecord] = {}

    def add(model: str, organization: str, source_id: str, payload: dict, layer: str) -> None:
        key = model_key(model, organization)
        record = registry.get(key)
        if record is None:
            record = ModelRecord(key=key, model=model, organization=organization)
            registry[key] = record
        record.sources.append(ModelSource(layer=layer, source_id=source_id, payload=payload))

    for model, organization, source_id, card in _curated_models(radar):
        add(model, organization, source_id, card, CURATED)
    for model, organization, source_id, row in _crawled_models(shard_dir):
        add(model, organization, source_id, row, CRAWLED)

    return dict(sorted(registry.items()))


def summarize(registry: dict[str, ModelRecord]) -> dict[str, Any]:
    """The counts a consumer needs without walking every source."""
    both = sum(1 for r in registry.values() if len(r.layers) > 1)
    return {
        "schema_version": SCHEMA_VERSION,
        "model_count": len(registry),
        "curated_only": sum(1 for r in registry.values() if r.layers == [CURATED]),
        "crawled_only": sum(1 for r in registry.values() if r.layers == [CRAWLED]),
        "both_layers": both,
        "organizations": sorted({r.organization for r in registry.values()}),
    }


def write_model_registry(radar_path: Path, shard_dir: Path, output: Path) -> dict[str, Any]:
    """Build the registry and write it beside the rest of the site's data.

    Raises when the shard directory is absent. The shards are derived and
    untracked, so a fresh checkout has none until `benchmark-radar
    normalize-external` writes them, and `_crawled_models()` reaches them with a
    glob: a missing directory yields nothing rather than failing. Without this
    check the crawled half of the registry silently disappears and the file is
    rewritten with the 34 curated models in place of all 355, which is the kind
    of wrong answer that reads as a real one. Refusing to write is the honest
    outcome, and the message names the command that fixes it.
    """
    shard_dir = Path(shard_dir)
    if not shard_dir.is_dir():
        raise FileNotFoundError(
            f"{shard_dir} does not exist, so the crawled half of the model registry "
            "would be silently dropped and models.json rewritten with the curated "
            "models alone. Run `benchmark-radar normalize-external` first."
        )
    radar = json.loads(Path(radar_path).read_text(encoding="utf-8"))
    registry = build_registry(radar, shard_dir)
    report = summarize(registry)
    output.parent.mkdir(parents=True, exist_ok=True)
    # The index, not the payloads. Every source record embedded inline came to
    # 5.1MB, which is a page-weight cost for data no reader of the index needs:
    # a consumer asking "which models exist" wants identity and layer, and a
    # consumer wanting one model's evidence already has radar.json and the
    # shards. Counting sources per layer keeps the join visible without
    # carrying it.
    output.write_text(
        json.dumps(
            {
                **report,
                "models": [
                    {
                        "key": record.key,
                        "model": record.model,
                        "organization": record.organization,
                        "layers": record.layers,
                        "source_counts": {
                            layer: sum(1 for s in record.sources if s.layer == layer)
                            for layer in record.layers
                        },
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
