"""Portable, versioned local storage for installed Benchmark Radar clients."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .data_release import DATA_RELEASE_SCHEMA_VERSION
from .query import QueryError, QueryPaths, QueryService

# Keep the tiny update manifest on the canonical public site. Its checksummed
# archive points to a GitHub Release asset so CLI downloads do not consume the
# dashboard's GitHub Pages bandwidth allowance.
DEFAULT_MANIFEST_URL = "https://benchmark-radar.org/data/cli/manifest.json"
STATE_SCHEMA_VERSION = 1
ENV_DATA_HOME = "BENCHMARK_RADAR_HOME"
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class DataSyncError(QueryError):
    """A public initialization or synchronization failure."""


def default_data_home() -> Path:
    override = os.getenv(ENV_DATA_HOME, "").strip()
    return Path(override).expanduser() if override else Path.home() / ".benchmark-radar"


def _allowed_download_url(value: str) -> bool:
    # urlsplit removes controls and delays port validation. Reject malformed
    # authorities before a request or its error can expose embedded credentials.
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        _port = parsed.port
    except ValueError:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def _utc_timestamp(value: Any, *, label: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise DataSyncError(f"{label} is invalid", code=code) from error
    if parsed.tzinfo is None:
        raise DataSyncError(f"{label} must include a timezone", code=code)
    return parsed.astimezone(UTC)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DataSyncError(
            "Benchmark Radar is not initialized; run `benchmark-radar init`",
            code="not_initialized",
            status=409,
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise DataSyncError(
            f"cannot read {label} at {path}: {type(error).__name__}: {error}",
            code="invalid_local_state",
        ) from error
    if not isinstance(value, dict):
        raise DataSyncError(f"{label} must be a JSON object", code="invalid_local_state")
    return value


class DataStore:
    def __init__(
        self,
        *,
        root: Path | None = None,
        manifest_url: str | None = None,
        urlopen: Callable[..., Any] | None = None,
    ):
        self.root = (root or default_data_home()).expanduser()
        self.manifest_url = manifest_url
        self.urlopen = urlopen

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def obsolete_path(self) -> Path:
        return self.root / "obsolete"

    def state(self) -> dict[str, Any]:
        state = _read_json(self.state_path, label="Benchmark Radar state")
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            raise DataSyncError(
                f"unsupported local state schema {state.get('schema_version')!r}",
                code="unsupported_schema",
            )
        version = state.get("data_version")
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            raise DataSyncError("local data_version is invalid", code="invalid_local_state")
        _utc_timestamp(
            state.get("generated_at"),
            label="local generated_at",
            code="invalid_local_state",
        )
        return state

    def query_paths(self) -> QueryPaths:
        state = self.state()
        current = self.root / "versions" / state["data_version"]
        if not current.is_dir():
            raise DataSyncError(
                f"active data version is missing at {current}",
                code="invalid_local_state",
            )
        return QueryPaths(
            index=current / "benchmark-index.json",
            shards=current / "benchmarks",
            snapshots=current / "snapshots",
            data_version=state["data_version"],
            generated_at=state.get("generated_at"),
            synced_at=state.get("synced_at"),
        )

    def initialize(self) -> dict[str, Any]:
        if self.state_path.exists():
            state = self.state()
            raise DataSyncError(
                f"Benchmark Radar is already initialized with {state['data_version']}; "
                "run `benchmark-radar sync`",
                code="already_initialized",
                status=409,
            )
        return self._update(initial=True)

    def sync(self) -> dict[str, Any]:
        self.state()
        try:
            status = QueryService(self.query_paths()).status()
        except QueryError as error:
            raise DataSyncError(
                "the active local dataset is invalid; move the managed data directory "
                "aside and run `benchmark-radar init` again",
                code="invalid_local_state",
            ) from error
        if status["status"] != "ok":
            raise DataSyncError(
                "the active local dataset is degraded; move the managed data directory "
                "aside and run `benchmark-radar init` again",
                code="invalid_local_state",
            )
        return self._update(initial=False)

    def _cleanup_obsolete(self) -> bool:
        if not self.obsolete_path.exists():
            return False
        try:
            shutil.rmtree(self.obsolete_path)
        except OSError as error:
            raise DataSyncError(
                f"cannot remove obsolete data at {self.obsolete_path}: "
                f"{type(error).__name__}: {error}",
                code="cleanup_failed",
            ) from error
        return True

    def _quarantine(self, path: Path) -> Path:
        self.obsolete_path.mkdir(parents=True, exist_ok=True)
        target = self.obsolete_path / path.name
        if target.exists():
            raise DataSyncError(
                f"obsolete data already exists at {target}",
                code="invalid_local_state",
            )
        os.replace(path, target)
        return target

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / "sync.lock"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise DataSyncError(
                f"another init or sync is active ({lock_path})",
                code="sync_in_progress",
                status=409,
            ) from error
        os.close(descriptor)
        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    def _open(self, request: urllib.request.Request, *, allow_not_modified: bool = False):
        opener = self.urlopen or urllib.request.urlopen
        try:
            response = opener(request, timeout=60)
            final_url = response.geturl() if hasattr(response, "geturl") else request.full_url
            if not _allowed_download_url(final_url):
                response.close()
                raise DataSyncError(
                    f"download redirected to an insecure URL: {final_url}",
                    code="invalid_manifest",
                )
            return response
        except urllib.error.HTTPError as error:
            if allow_not_modified and error.code == 304:
                return None
            raise DataSyncError(
                f"HTTP {error.code} while downloading {request.full_url}",
                code="remote_unavailable",
                status=503,
            ) from error
        except (OSError, urllib.error.URLError) as error:
            raise DataSyncError(
                f"cannot download {request.full_url}: {type(error).__name__}: {error}",
                code="remote_unavailable",
                status=503,
            ) from error

    def _manifest(
        self, *, previous_etag: str | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        manifest_url = self.manifest_url or DEFAULT_MANIFEST_URL
        if not _allowed_download_url(manifest_url):
            raise DataSyncError(
                "manifest URL must use HTTPS (HTTP is allowed only for loopback testing)",
                code="invalid_manifest",
            )
        headers = {
            "Accept": "application/json",
            "User-Agent": f"benchmark-radar/{__version__}",
            **({"If-None-Match": previous_etag} if previous_etag else {}),
        }
        request = urllib.request.Request(manifest_url, headers=headers)
        response = self._open(request, allow_not_modified=True)
        if response is None:
            return None, previous_etag
        with response:
            try:
                value = json.loads(response.read())
            except json.JSONDecodeError as error:
                raise DataSyncError(
                    "remote manifest is invalid JSON", code="invalid_manifest"
                ) from error
            etag = response.headers.get("ETag")
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != DATA_RELEASE_SCHEMA_VERSION
        ):
            raise DataSyncError("remote manifest schema is unsupported", code="invalid_manifest")
        version = value.get("data_version")
        artifact = value.get("artifact")
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            raise DataSyncError("remote data_version is invalid", code="invalid_manifest")
        _utc_timestamp(
            value.get("generated_at"),
            label="remote generated_at",
            code="invalid_manifest",
        )
        for field in ("benchmark_count", "snapshot_count"):
            if not isinstance(value.get(field), int) or value[field] < 1:
                raise DataSyncError(f"remote {field} is invalid", code="invalid_manifest")
        if not isinstance(artifact, dict):
            raise DataSyncError("remote artifact is missing", code="invalid_manifest")
        if artifact.get("format") != "zip":
            raise DataSyncError("remote artifact format must be zip", code="invalid_manifest")
        if not isinstance(artifact.get("url"), str) or not _allowed_download_url(artifact["url"]):
            raise DataSyncError(
                "remote artifact URL must use HTTPS (HTTP is allowed only for loopback testing)",
                code="invalid_manifest",
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256") or "")):
            raise DataSyncError("remote artifact checksum is invalid", code="invalid_manifest")
        if not isinstance(artifact.get("size"), int) or artifact["size"] < 1:
            raise DataSyncError("remote artifact size is invalid", code="invalid_manifest")
        if (
            not isinstance(artifact.get("uncompressed_size"), int)
            or artifact["uncompressed_size"] < 1
        ):
            raise DataSyncError(
                "remote artifact uncompressed_size is invalid", code="invalid_manifest"
            )
        if not isinstance(artifact.get("file_count"), int) or artifact["file_count"] < 3:
            raise DataSyncError("remote artifact file_count is invalid", code="invalid_manifest")
        return value, etag

    def _download(self, manifest: dict[str, Any], target: Path) -> None:
        artifact = manifest["artifact"]
        request = urllib.request.Request(
            artifact["url"],
            headers={
                "Accept": "application/zip",
                "User-Agent": f"benchmark-radar/{__version__}",
            },
        )
        digest = hashlib.sha256()
        size = 0
        with self._open(request) as response, target.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > artifact["size"]:
                    raise DataSyncError("download exceeds manifest size", code="invalid_artifact")
                digest.update(chunk)
                handle.write(chunk)
        if size != artifact["size"]:
            raise DataSyncError(
                f"download size mismatch: expected {artifact['size']}, received {size}",
                code="invalid_artifact",
            )
        if digest.hexdigest() != artifact["sha256"]:
            raise DataSyncError(
                "download checksum does not match manifest", code="invalid_artifact"
            )

    def _extract(self, bundle: Path, target: Path, manifest: dict[str, Any]) -> None:
        target_root = target.resolve()
        artifact = manifest["artifact"]
        try:
            with zipfile.ZipFile(bundle) as archive:
                infos = archive.infolist()
                if len(infos) != artifact["file_count"]:
                    raise DataSyncError(
                        "archive file count does not match manifest", code="invalid_artifact"
                    )
                if sum(info.file_size for info in infos) != artifact["uncompressed_size"]:
                    raise DataSyncError(
                        "archive expanded size does not match manifest", code="invalid_artifact"
                    )
                names: set[str] = set()
                for info in infos:
                    member = PurePosixPath(info.filename)
                    unix_type = (info.external_attr >> 16) & 0o170000
                    if (
                        info.is_dir()
                        or unix_type == 0o120000
                        or member.is_absolute()
                        or ".." in member.parts
                        or not member.parts
                        or info.filename in names
                    ):
                        raise DataSyncError(
                            f"unsafe archive path: {info.filename!r}",
                            code="invalid_artifact",
                        )
                    names.add(info.filename)
                    destination = (target / Path(*member.parts)).resolve()
                    if target_root not in destination.parents:
                        raise DataSyncError(
                            f"unsafe archive path: {info.filename!r}",
                            code="invalid_artifact",
                        )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
        except zipfile.BadZipFile as error:
            raise DataSyncError(
                "downloaded artifact is not a valid ZIP", code="invalid_artifact"
            ) from error

    def _write_state(self, value: dict[str, Any]) -> None:
        temporary = self.root / ".state.json.tmp"
        try:
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.state_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _current_result(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "status": "current",
            "downloaded": False,
            "data_version": state["data_version"],
            "generated_at": state["generated_at"],
            "synced_at": state.get("synced_at"),
            "data_home": str(self.root),
        }

    def _update(self, *, initial: bool) -> dict[str, Any]:
        with self._lock():
            previous = None if initial else self.state()
            if previous is not None:
                self._cleanup_obsolete()
            if self.manifest_url is None and previous is not None:
                stored_url = previous.get("manifest_url")
                if not isinstance(stored_url, str) or not _allowed_download_url(stored_url):
                    raise DataSyncError(
                        "local manifest_url is invalid",
                        code="invalid_local_state",
                    )
                self.manifest_url = stored_url
            if self.manifest_url is None:
                self.manifest_url = DEFAULT_MANIFEST_URL
            manifest, etag = self._manifest(
                previous_etag=(
                    str(previous.get("etag")) if previous and previous.get("etag") else None
                )
            )
            if manifest is None:
                return self._current_result(previous)
            version = manifest["data_version"]
            if previous and _utc_timestamp(
                manifest["generated_at"], label="remote generated_at", code="invalid_manifest"
            ) < _utc_timestamp(
                previous["generated_at"],
                label="local generated_at",
                code="invalid_local_state",
            ):
                raise DataSyncError(
                    f"remote data version {version} is older than active version "
                    f"{previous['data_version']}",
                    code="stale_manifest",
                    status=409,
                )
            if previous and previous["data_version"] == version:
                return self._current_result(previous)

            versions = self.root / "versions"
            versions.mkdir(parents=True, exist_ok=True)
            bundle = self.root / ".download.tmp"
            staging = versions / f".{version}.staging"
            destination = versions / version
            if destination.exists():
                raise DataSyncError(
                    f"unreferenced version already exists at {destination}",
                    code="invalid_local_state",
                )
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir()
            state_committed = False
            cleanup_pending = False
            try:
                self._download(manifest, bundle)
                self._extract(bundle, staging, manifest)
                staged_paths = QueryPaths(
                    index=staging / "benchmark-index.json",
                    shards=staging / "benchmarks",
                    snapshots=staging / "snapshots",
                )
                staged_status = QueryService(staged_paths).status()
                if staged_status["status"] != "ok":
                    raise DataSyncError("downloaded dataset is degraded", code="invalid_artifact")
                if staged_status["catalog"]["count"] != manifest["benchmark_count"]:
                    raise DataSyncError(
                        "downloaded benchmark count does not match manifest",
                        code="invalid_artifact",
                    )
                if staged_status["radar"]["snapshot_count"] != manifest["snapshot_count"]:
                    raise DataSyncError(
                        "downloaded snapshot count does not match manifest",
                        code="invalid_artifact",
                    )
                os.replace(staging, destination)
                synced_at = datetime.now(UTC).isoformat()
                state = {
                    "schema_version": STATE_SCHEMA_VERSION,
                    "data_version": version,
                    "generated_at": manifest["generated_at"],
                    "synced_at": synced_at,
                    "manifest_url": self.manifest_url,
                    **({"etag": etag} if etag else {}),
                }
                self._write_state(state)
                state_committed = True
                if previous is not None:
                    previous_path = versions / previous["data_version"]
                    try:
                        self._quarantine(previous_path)
                    except (OSError, DataSyncError) as error:
                        # The previous directory is still intact because rename
                        # is atomic. Restore its state, then quarantine the new
                        # version so a failed activation keeps the old one live.
                        self._write_state(previous)
                        self._quarantine(destination)
                        raise DataSyncError(
                            f"cannot retire previous data version: {type(error).__name__}: {error}",
                            code="cleanup_failed",
                        ) from error
                    try:
                        self._cleanup_obsolete()
                    except DataSyncError:
                        # Activation is already complete and versions/ contains
                        # only the new release. Report deferred physical cleanup
                        # explicitly; the next sync retries it before networking.
                        cleanup_pending = True
            finally:
                bundle.unlink(missing_ok=True)
                shutil.rmtree(staging, ignore_errors=True)
                if not state_committed:
                    shutil.rmtree(destination, ignore_errors=True)

            return {
                "schema_version": STATE_SCHEMA_VERSION,
                "status": "initialized" if initial else "updated",
                "downloaded": True,
                **({"previous_version": previous["data_version"]} if previous is not None else {}),
                "data_version": version,
                "generated_at": manifest["generated_at"],
                "synced_at": state["synced_at"],
                "benchmark_count": manifest.get("benchmark_count"),
                "snapshot_count": manifest.get("snapshot_count"),
                "cleanup_pending": cleanup_pending,
                "data_home": str(self.root),
            }
