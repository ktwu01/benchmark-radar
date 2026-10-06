"""Build the verified data bundle consumed by installed Benchmark Radar CLIs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
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
    if status["status"] != "ok":
        raise ValueError("refusing to publish a degraded Benchmark Radar dataset")
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
    manifest_temporary = output_dir / ".manifest.json.tmp"
    bundle_path = output_dir / DEFAULT_RELEASE_FILENAME
    manifest_path = output_dir / "manifest.json"
    backup_root = None
    published = False
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for archive_name, source in members:
                _write_zip_member(archive, archive_name, source.read_bytes())
        payload = temporary.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        data_version = f"{timestamp_version}-{digest[:12]}"
        manifest = {
            "schema_version": DATA_RELEASE_SCHEMA_VERSION,
            "data_version": data_version,
            "generated_at": generated_at,
            "benchmark_count": status["catalog"]["count"],
            "snapshot_count": status["radar"]["snapshot_count"],
            "artifact": {
                "filename": DEFAULT_RELEASE_FILENAME,
                "url": f"{base_url.rstrip('/')}/{DEFAULT_RELEASE_FILENAME}",
                "sha256": digest,
                "size": len(payload),
                "uncompressed_size": sum(path.stat().st_size for _, path in members),
                "file_count": len(members),
                "format": "zip",
            },
        }
        manifest_temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # A failed manifest write must not leave the old checksum pointing at
        # a new ZIP. Stage both files and retain the previous bundle for rollback.
        if bundle_path.exists():
            backup_root = Path(tempfile.mkdtemp(prefix=".release-backup-", dir=output_dir))
            bundle_path.replace(backup_root / DEFAULT_RELEASE_FILENAME)
        try:
            temporary.replace(bundle_path)
            manifest_temporary.replace(manifest_path)
        except OSError:
            if backup_root is not None:
                (backup_root / DEFAULT_RELEASE_FILENAME).replace(bundle_path)
            else:
                bundle_path.unlink(missing_ok=True)
            raise
        published = True
        return manifest
    finally:
        temporary.unlink(missing_ok=True)
        manifest_temporary.unlink(missing_ok=True)
        if backup_root is not None and (
            published or not (backup_root / DEFAULT_RELEASE_FILENAME).exists()
        ):
            # If restoring the old bundle itself fails, retain its backup.
            shutil.rmtree(backup_root, ignore_errors=True)
