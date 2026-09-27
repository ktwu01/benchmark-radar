"""Freeze the complete public/local Library union without discarding source fields."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path


def freeze(repository: Path, output: Path) -> dict:
    revision = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "origin/main"], text=True
    ).strip()
    documents = {}
    receipts = []
    for label in ("public", "local"):
        for filename in ("library_index.json", "benchmarks.json"):
            relative = f"data/{filename}"
            payload = (
                subprocess.check_output(
                    ["git", "-C", str(repository), "show", f"{revision}:{relative}"]
                )
                if label == "public"
                else (repository / relative).read_bytes()
            )
            document = json.loads(payload)
            key = f"{label}/{filename}"
            rows = document["records"]
            if len({row["id"] for row in rows}) != len(rows):
                raise ValueError(f"duplicate record IDs in {key}")
            documents[key] = document
            receipts.append(
                {
                    "input": key,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "record_count": len(rows),
                    "revision": revision if label == "public" else "working-tree",
                }
            )
    entries = {}
    # All four representations survive. Priority affects the mapped fields,
    # never whether a conflicting or local-only value can be recovered.
    for label in ("public", "local"):
        for filename in ("library_index.json", "benchmarks.json"):
            key = f"{label}/{filename}"
            for row in documents[key]["records"]:
                entries.setdefault(row["id"], {"id": row["id"], "versions": {}})["versions"][
                    key
                ] = row
    bundle = {
        "schema_version": 1,
        "source_repository": "https://github.com/Claire1217/benchmark-radar",
        "public_revision": revision,
        "inputs": receipts,
        "manifests": {key: doc.get("manifest", {}) for key, doc in documents.items()},
        "records": [entries[key] for key in sorted(entries)],
    }
    payload = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    compressed = gzip.compress(payload, mtime=0)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "library.json.gz"
    path.write_bytes(compressed)
    manifest = {
        "schema_version": 1,
        "file": path.name,
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "record_count": len(entries),
        "public_revision": revision,
        "inputs": receipts,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(freeze(args.repository, args.output), indent=2))
