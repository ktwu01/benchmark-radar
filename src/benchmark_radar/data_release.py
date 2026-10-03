"""Build the verified data bundle consumed by installed Benchmark Radar CLIs."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .query import QueryPaths, QueryService
from .snapshots import load_snapshots

DATA_RELEASE_SCHEMA_VERSION = 1
DEFAULT_RELEASE_DIR = Path("site/data/cli")
DEFAULT_RELEASE_BASE_URL = "https://github.com/ktwu01/benchmark-radar/releases/download/cli-data"
DEFAULT_RELEASE_FILENAME = "benchmark-radar-data.zip"
_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def _data_version(generated_at: str) -> str:
    value = generated_at.replace("+00:00", "Z").replace(":", "-")
    if not re.fullmatch(r"[0-9TZ.+-]+", value):
        raise ValueError(f"generated_at cannot form a data version: {generated_at!r}")
    return value


def _write_zip_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload, compresslevel=9)


def build_data_release(
    *,
    paths: QueryPaths,
    output_dir: Path = DEFAULT_RELEASE_DIR,
    base_url: str = DEFAULT_RELEASE_BASE_URL,
) -> dict[str, Any]:
    """Write one deterministic, complete CLI data bundle and its manifest."""

    status = QueryService(paths).status()
    # An optional collector warning must be visible in `status`, but it does
    # not make this checksummed archive incomplete. Gate publication on the
    # catalog and required-source coverage rather than the broader health flag.
    if not status["catalog"]["complete"] or not status["radar"]["required_coverage_complete"]:
        raise ValueError("refusing to publish an incomplete Benchmark Radar dataset")
    snapshots = load_snapshots(paths.snapshots)
    generated_at = snapshots[-1]["generated_at"]
    # The timestamp gives humans a useful release ordering, while the digest
    # makes the version immutable even when catalog/shard data changes without
    # a new snapshot.  Without the content suffix, clients could mistake a
    # changed archive for an already-installed release and stay stale forever.
    timestamp_version = _data_version(generated_at)
    output_dir.mkdir(parents=True, exist_ok=True)

    members: list[tuple[str, Path]] = [("benchmark-index.json", paths.index)]
    members.extend(
        (f"benchmarks/{path.name}", path) for path in sorted(paths.shards.glob("*.json"))
    )
    members.extend(
        (f"snapshots/{path.name}", path) for path in sorted(paths.snapshots.glob("*.json"))
    )
    temporary = output_dir / f".{DEFAULT_RELEASE_FILENAME}.tmp"
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for archive_name, source in members:
                _write_zip_member(archive, archive_name, source.read_bytes())
        payload = temporary.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        data_version = f"{timestamp_version}-{digest[:12]}"
        filename = DEFAULT_RELEASE_FILENAME
        bundle_path = output_dir / filename
        temporary.replace(bundle_path)
    finally:
        temporary.unlink(missing_ok=True)

    manifest = {
        "schema_version": DATA_RELEASE_SCHEMA_VERSION,
        "data_version": data_version,
        "generated_at": generated_at,
        "benchmark_count": status["catalog"]["count"],
        "snapshot_count": status["radar"]["snapshot_count"],
        "artifact": {
            "filename": filename,
            "url": f"{base_url.rstrip('/')}/{filename}",
            "sha256": digest,
            "size": len(payload),
            "uncompressed_size": sum(path.stat().st_size for _, path in members),
            "file_count": len(members),
            "format": "zip",
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
