"""Freeze the organization/model IDs the logo audit page cites.

The audit page exists so a wrong brand mark is caught by eye before it ships
(issue #261: Google DeepMind rendered the Google "G", GPT rendered a
hand-drawn rosette, and Meta's path was invented past character 395). Review
feedback has to survive a rebuild, so "O-07" must mean the same organization
next month as it does today. That is what this file freezes: IDs are assigned
once, in sorted order, and an entry that later disappears from the data keeps
its number rather than letting every later card renumber.

Freezing IDs is now this script's ONLY job. It used to walk radar.json and the
shards itself to work out which models exist, which made it a second answer to
that question -- and the two answers disagreed, 357 here against 355 in
models.json, because this one keyed on the display name while the registry
keys on (name, organization). Models now come from models.json, the single
structure that answers "which models exist" for both layers, and this script
only decides what each one is called in review.

Run after `classify` has written models.json:

    python scripts/build_logo_registry.py
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY = Path("site/data/logo-registry.json")
MODELS = Path("site/data/models.json")


def main() -> None:
    models_doc = json.loads(MODELS.read_text(encoding="utf-8"))
    records = models_doc["models"]

    # Organizations come from the same file, so the two sections of the page
    # cannot disagree about which organizations exist either.
    organizations = sorted({record["organization"] for record in records})
    models = [(record["model"], record["organization"]) for record in records]

    previous = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    org_ids: dict[str, str] = dict(previous.get("organizations") or {})
    model_ids: dict[str, str] = dict(previous.get("models") or {})

    high_water = (
        json.loads(REGISTRY.read_text(encoding="utf-8")).get("high_water", {})
        if REGISTRY.exists()
        else {}
    )

    def assign(existing: dict[str, str], keys: list[str], prefix: str) -> None:
        used = {int(value.split("-")[1]) for value in existing.values()}
        used.add(int(high_water.get(prefix, 0)))
        nxt = max(used) + 1 if used else 1
        for key in keys:
            if key not in existing:
                existing[key] = f"{prefix}-{nxt:02d}"
                nxt += 1

    # The highest number ever issued, kept even for entries about to be
    # dropped, so a retired ID is never handed to a different model later.
    retired = {
        "O": max(
            int(high_water.get("O", 0)),
            max((int(v.split("-")[1]) for v in org_ids.values()), default=0),
        ),
        "M": max(
            int(high_water.get("M", 0)),
            max((int(v.split("-")[1]) for v in model_ids.values()), default=0),
        ),
    }

    assign(org_ids, organizations, "O")
    model_keys = [f"{model}␟{organization}" for model, organization in models]
    from benchmark_radar.models_registry import model_key

    # A renamed model inherits its old label's ID, but only from a label the
    # data no longer carries. models.json can keep two live records whose
    # slugs collide ("Gemini 2.5 Flash" and "Gemini-2.5-Flash"); letting the
    # new one inherit from a still-live twin handed both cards the same ID.
    live_labels = set(model_keys)
    by_identity: dict[str, list[str]] = {}
    for label, identifier in model_ids.items():
        if label in live_labels:
            continue
        model, organization = label.split("␟", 1)
        by_identity.setdefault(model_key(model, organization), []).append(identifier)
    for label in model_keys:
        if label in model_ids:
            continue
        model, organization = label.split("␟", 1)
        donors = by_identity.get(model_key(model, organization))
        if donors:
            model_ids[label] = donors.pop(0)
    assign(model_ids, model_keys, "M")

    # An entry the data no longer carries is dropped. Freezing an ID protects a
    # reviewer's note from renumbering; it does not mean the page should keep
    # rendering a card for a model that no longer exists. Two survived a rename
    # this way -- "Gemma 4 31B" became "Gemma 4 (31B)", "Grok-4" became
    # "Grok 4" -- and kept the registry disagreeing with models.json about how
    # many models there are. Numbers still are not reused: `assign` counts from
    # the highest ever issued, so a dropped ID stays retired.
    live_models = set(model_keys)
    model_ids = {key: value for key, value in model_ids.items() if key in live_models}
    live_orgs = set(organizations)
    org_ids = {key: value for key, value in org_ids.items() if key in live_orgs}

    REGISTRY.write_text(
        json.dumps(
            {
                "note": (
                    "Frozen IDs for the logo audit page (site/logos.html). An ID is "
                    "assigned once and never reused, so review feedback citing it "
                    "stays valid across rebuilds. Which models and organizations "
                    "exist is decided by models.json, not here."
                ),
                # The highest number ever issued per prefix. A dropped entry
                # frees its card, never its number.
                "high_water": {
                    "O": max(
                        retired["O"],
                        max((int(v.split("-")[1]) for v in org_ids.values()), default=0),
                    ),
                    "M": max(
                        retired["M"],
                        max((int(v.split("-")[1]) for v in model_ids.values()), default=0),
                    ),
                },
                "organizations": dict(sorted(org_ids.items(), key=lambda kv: kv[1])),
                "models": dict(sorted(model_ids.items(), key=lambda kv: kv[1])),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"organizations: {len(org_ids)}  models: {len(model_ids)} -> {REGISTRY}")


if __name__ == "__main__":
    main()
