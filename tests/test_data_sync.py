from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import urllib.error
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from benchmark_radar.data_release import (
    DEFAULT_RELEASE_BASE_URL,
    DEFAULT_RELEASE_FILENAME,
    build_data_release,
)
from benchmark_radar.data_store import (
    DEFAULT_MANIFEST_URL,
    DataStore,
    DataSyncError,
    _allowed_download_url,
    default_data_home,
)
from benchmark_radar.models import RadarItem, RadarRun, SourceHealth
from benchmark_radar.query import QueryPaths, QueryService
from benchmark_radar.query_cli import run_query_cli
from benchmark_radar.snapshots import write_snapshot


class _Response(io.BytesIO):
    def __init__(
        self,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        url: str = "https://example.test/data",
    ):
        super().__init__(payload)
        self.headers = headers or {}
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def geturl(self):
        return self.url


class _Remote:
    def __init__(self, manifest_url: str, manifest: dict, bundle: bytes):
        self.manifest_url = manifest_url
        self.manifest = manifest
        self.bundle = bundle
        self.bundle_requests = 0

    def urlopen(self, request, **kwargs):
        url = request.full_url
        if url == self.manifest_url:
            return _Response(
                json.dumps(self.manifest).encode(),
                headers={"ETag": '"release-1"'},
                url=url,
            )
        if url == self.manifest["artifact"]["url"]:
            self.bundle_requests += 1
            return _Response(self.bundle, url=url)
        raise AssertionError(f"unexpected URL: {url}")


def _source_tree(tmp_path: Path, *, name: str = "Agent Workbench", day: int = 29) -> QueryPaths:
    index = tmp_path / "source" / "benchmark-index.json"
    shards = tmp_path / "source" / "benchmarks"
    snapshots = tmp_path / "source" / "snapshots"
    index.parent.mkdir(parents=True)
    shards.mkdir()
    record = {
        "slug": "agent-workbench",
        "key": "catalog:agent-workbench",
        "name": name,
        "source": "fixture",
        "publisher": "Example Lab",
        "released": "2026-01-01",
        "openness": "open",
        "modality": "text",
        "description": "Long-horizon coding agent evaluation.",
        "categories": ["agent"],
        "languages": ["en"],
        "score_count": 1,
        "has_paper": True,
        "has_repo": True,
        "has_dataset": True,
        "has_size": True,
    }
    index.write_text(
        json.dumps({"schema_version": 1, "count": 1, "benchmarks": [record]}),
        encoding="utf-8",
    )
    (shards / "agent-workbench.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": {**record, "artifacts": []},
                "siblings": [],
                "scores_by_source": {},
            }
        ),
        encoding="utf-8",
    )
    generated_at = datetime(2026, 8, day, 5, 0, tzinfo=UTC)
    write_snapshot(
        RadarRun(
            generated_at=generated_at,
            since=generated_at - timedelta(hours=48),
            items=[
                RadarItem(
                    source="GitHub",
                    source_id="example/agent-bench",
                    title="New Agent Benchmark",
                    url="https://github.com/example/agent-bench",
                    published_at=generated_at,
                    summary="New evaluation for coding agents.",
                )
            ],
            health=[
                SourceHealth(source=source, ok=True, item_count=1, method="API")
                for source in ("arxiv", "github", "huggingface")
            ],
        ),
        snapshots,
    )
    return QueryPaths(index=index, shards=shards, snapshots=snapshots)


def _release(tmp_path: Path, *, name: str = "Agent Workbench", day: int = 29):
    paths = _source_tree(tmp_path, name=name, day=day)
    output = tmp_path / "published"
    manifest = build_data_release(paths=paths, output_dir=output)
    bundle_path = output / manifest["artifact"]["filename"]
    manifest_url = "https://example.test/data/cli/manifest.json"
    remote_manifest = {
        **manifest,
        "artifact": {
            **manifest["artifact"],
            "url": f"https://example.test/data/cli/{bundle_path.name}",
        },
    }
    return remote_manifest, bundle_path.read_bytes(), manifest_url


def test_default_data_home_is_cross_platform_and_overridable(monkeypatch, tmp_path: Path) -> None:
    # Regression: repository-relative defaults made an installed CLI depend on cwd.
    monkeypatch.setenv("BENCHMARK_RADAR_HOME", str(tmp_path / "custom"))
    assert default_data_home() == tmp_path / "custom"

    monkeypatch.delenv("BENCHMARK_RADAR_HOME")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "person"))
    assert default_data_home() == tmp_path / "person" / ".benchmark-radar"


def test_release_bundle_is_complete_deterministic_and_self_describing(tmp_path: Path) -> None:
    # Regression: publishing only the search index made show/recent fail after init.
    paths = _source_tree(tmp_path)
    first = build_data_release(paths=paths, output_dir=tmp_path / "published")
    first_bytes = (tmp_path / "published" / first["artifact"]["filename"]).read_bytes()
    second = build_data_release(paths=paths, output_dir=tmp_path / "published")
    second_bytes = (tmp_path / "published" / second["artifact"]["filename"]).read_bytes()

    assert first == second
    assert first_bytes == second_bytes
    assert first["benchmark_count"] == 1
    assert first["snapshot_count"] == 1
    assert first["artifact"]["filename"] == DEFAULT_RELEASE_FILENAME
    assert first["artifact"]["sha256"] == hashlib.sha256(first_bytes).hexdigest()
    with zipfile.ZipFile(io.BytesIO(first_bytes)) as archive:
        assert sorted(archive.namelist()) == [
            "benchmark-index.json",
            "benchmarks/agent-workbench.json",
            "snapshots/2026-08-29.json",
        ]


def test_deploy_and_ci_build_the_downloadable_release_after_its_inputs() -> None:
    # Regression: an init command is useless when Pages never publishes its artifact.
    pages = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in ci
    for workflow in (pages, ci):
        assert (
            workflow.index("benchmark-radar normalize-external")
            < workflow.index("benchmark-radar classify")
            < workflow.index("benchmark-radar build-data-release")
        )
    assert "gh release upload cli-data" in pages
    # The rolling data drop must never take the "Latest" slot from a versioned release.
    assert "--latest=false" in pages
    assert "needs: [build, publish-cli-data]" in pages
    assert (
        pages.index("Upload CLI data release for publishing")
        < pages.index("Remove CLI archive from Pages artifact")
        < pages.index("Upload Pages artifact")
    )


def test_public_defaults_keep_bulk_downloads_off_pages() -> None:
    assert DEFAULT_MANIFEST_URL == "https://benchmark-radar.org/data/cli/manifest.json"
    assert DEFAULT_RELEASE_BASE_URL.startswith(
        "https://github.com/ktwu01/benchmark-radar/releases/download/"
    )


def test_init_downloads_validates_and_queries_managed_data(monkeypatch, tmp_path: Path) -> None:
    # Regression: users had to clone the repository and run a maintainer normalizer.
    manifest, bundle, manifest_url = _release(tmp_path)
    remote = _Remote(manifest_url, manifest, bundle)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=remote.urlopen,
    )

    result = store.initialize()
    service = QueryService(store.query_paths())

    assert result["status"] == "initialized"
    assert result["data_version"] == manifest["data_version"]
    assert remote.bundle_requests == 1
    assert service.search("agent workbench")["results"][0]["name"] == "Agent Workbench"
    assert service.recent()["results"][0]["source_id"] == "example/agent-bench"
    assert service.status()["catalog"]["validated_shard_count"] == 1
    assert [path.name for path in (store.root / "versions").iterdir()] == [manifest["data_version"]]


def test_sync_current_release_does_not_redownload_bundle(tmp_path: Path) -> None:
    # Regression: checking freshness downloaded the full dataset on every research run.
    manifest, bundle, manifest_url = _release(tmp_path)
    remote = _Remote(manifest_url, manifest, bundle)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=remote.urlopen,
    )
    store.initialize()

    result = store.sync()

    assert result["status"] == "current"
    assert result["downloaded"] is False
    assert remote.bundle_requests == 1


def test_sync_uses_etag_to_avoid_reloading_unchanged_manifest(tmp_path: Path) -> None:
    # Regression: repeated agent sessions should reduce an unchanged sync to HTTP 304.
    manifest, bundle, manifest_url = _release(tmp_path)
    remote = _Remote(manifest_url, manifest, bundle)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=remote.urlopen,
    )
    store.initialize()

    def not_modified(request, **kwargs):
        assert request.headers["If-none-match"] == '"release-1"'
        raise urllib.error.HTTPError(request.full_url, 304, "Not Modified", {}, None)

    store.urlopen = not_modified
    result = store.sync()

    assert result["status"] == "current"
    assert result["downloaded"] is False


def test_sync_does_not_call_current_when_active_data_is_corrupt(tmp_path: Path) -> None:
    # Regression: manifest equality must not bless damaged local files as current.
    manifest, bundle, manifest_url = _release(tmp_path)
    remote = _Remote(manifest_url, manifest, bundle)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=remote.urlopen,
    )
    store.initialize()
    store.query_paths().index.write_text("{}", encoding="utf-8")

    with pytest.raises(DataSyncError, match="active local dataset is invalid"):
        store.sync()
    assert remote.bundle_requests == 1


def test_plain_http_is_limited_to_loopback_development(tmp_path: Path) -> None:
    # Regression: update endpoints transport the checksum and must not allow HTTP downgrade.
    store = DataStore(root=tmp_path / "home", manifest_url="http://example.test/manifest.json")
    with pytest.raises(DataSyncError, match="must use HTTPS"):
        store.initialize()


def test_loopback_http_is_allowed_for_local_release_tests() -> None:
    # Regression: the URL policy accidentally made the documented local HTTP
    # smoke-test path unreachable, so every local server looked insecure.
    assert _allowed_download_url("http://localhost:8899/manifest.json")
    assert _allowed_download_url("http://127.0.0.1:8899/manifest.json")
    assert _allowed_download_url("http://[::1]:8899/manifest.json")
    assert not _allowed_download_url("http://192.0.2.1/manifest.json")


def test_https_download_rejects_redirect_downgrade(tmp_path: Path) -> None:
    # Regression: urllib follows redirects, so checking only the requested URL misses downgrade.
    manifest, bundle, manifest_url = _release(tmp_path)

    def downgraded(request, **kwargs):
        return _Response(b"{}", url="http://evil.example/download")

    store = DataStore(root=tmp_path / "home", manifest_url=manifest_url, urlopen=downgraded)
    with pytest.raises(DataSyncError, match="redirected to an insecure URL"):
        store.initialize()


def test_sync_switches_atomically_and_keeps_only_latest_version(tmp_path: Path) -> None:
    # Regression: daily versions accumulated forever in the user's home directory.
    first_manifest, first_bundle, manifest_url = _release(tmp_path / "first", day=29)
    first_remote = _Remote(manifest_url, first_manifest, first_bundle)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=first_remote.urlopen,
    )
    store.initialize()

    second_manifest, second_bundle, _ = _release(
        tmp_path / "second", name="Agent Workbench 2", day=30
    )
    second_remote = _Remote(manifest_url, second_manifest, second_bundle)
    store.urlopen = second_remote.urlopen
    result = store.sync()

    assert result["status"] == "updated"
    assert result["previous_version"] == first_manifest["data_version"]
    assert QueryService(store.query_paths()).search("workbench 2")["results"][0]["name"] == (
        "Agent Workbench 2"
    )
    assert [path.name for path in (store.root / "versions").iterdir()] == [
        second_manifest["data_version"]
    ]


def test_sync_detects_catalog_change_with_same_snapshot_timestamp(tmp_path: Path) -> None:
    # Regression: timestamp-only versions treated changed catalog data as
    # current when the latest radar snapshot had not changed.
    first_manifest, first_bundle, manifest_url = _release(
        tmp_path / "first", name="Agent Workbench", day=29
    )
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, first_manifest, first_bundle).urlopen,
    )
    store.initialize()

    second_manifest, second_bundle, _ = _release(
        tmp_path / "second", name="Agent Workbench Revised", day=29
    )
    assert second_manifest["generated_at"] == first_manifest["generated_at"]
    assert second_manifest["data_version"] != first_manifest["data_version"]
    remote = _Remote(manifest_url, second_manifest, second_bundle)
    store.urlopen = remote.urlopen

    result = store.sync()

    assert result["status"] == "updated"
    assert result["downloaded"] is True
    assert remote.bundle_requests == 1
    assert QueryService(store.query_paths()).search("revised")["results"][0]["name"] == (
        "Agent Workbench Revised"
    )


def test_sync_rejects_manifest_count_mismatch(tmp_path: Path) -> None:
    # Regression: checksum-valid archives with self-inconsistent manifest
    # counts must not be activated as verified data.
    manifest, bundle, manifest_url = _release(tmp_path)
    manifest["benchmark_count"] = 2
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, manifest, bundle).urlopen,
    )

    with pytest.raises(DataSyncError, match="benchmark count does not match manifest"):
        store.initialize()
    assert not (store.root / "state.json").exists()
    assert list((store.root / "versions").iterdir()) == []


def test_sync_rejects_remote_rollback(tmp_path: Path) -> None:
    # Regression: a stale CDN manifest must not roll a client back to older evidence.
    current_manifest, current_bundle, manifest_url = _release(tmp_path / "current", day=30)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, current_manifest, current_bundle).urlopen,
    )
    store.initialize()
    old_manifest, old_bundle, _ = _release(tmp_path / "old", day=29)
    store.urlopen = _Remote(manifest_url, old_manifest, old_bundle).urlopen

    with pytest.raises(DataSyncError, match="older than active version"):
        store.sync()
    assert store.state()["data_version"] == current_manifest["data_version"]


def test_failed_sync_preserves_current_version(tmp_path: Path) -> None:
    # Regression: a truncated update must never replace the last verified dataset.
    first_manifest, first_bundle, manifest_url = _release(tmp_path / "first", day=29)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, first_manifest, first_bundle).urlopen,
    )
    store.initialize()
    second_manifest, second_bundle, _ = _release(tmp_path / "second", day=30)
    second_manifest["artifact"]["sha256"] = "0" * 64
    store.urlopen = _Remote(manifest_url, second_manifest, second_bundle).urlopen

    with pytest.raises(DataSyncError, match="checksum"):
        store.sync()

    assert store.state()["data_version"] == first_manifest["data_version"]
    assert QueryService(store.query_paths()).status()["status"] == "ok"
    assert [path.name for path in (store.root / "versions").iterdir()] == [
        first_manifest["data_version"]
    ]


def test_failed_retirement_rolls_back_to_previous_version(monkeypatch, tmp_path: Path) -> None:
    # Regression: failing to retire an old version after writing state made sync
    # report failure while silently leaving the new version active.
    first_manifest, first_bundle, manifest_url = _release(tmp_path / "first", day=29)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, first_manifest, first_bundle).urlopen,
    )
    store.initialize()
    second_manifest, second_bundle, _ = _release(tmp_path / "second", day=30)
    store.urlopen = _Remote(manifest_url, second_manifest, second_bundle).urlopen
    previous_path = store.root / "versions" / first_manifest["data_version"]
    real_replace = os.replace

    def fail_old_version_replace(source, target):
        if Path(source) == previous_path:
            raise PermissionError("old version is busy")
        return real_replace(source, target)

    monkeypatch.setattr("benchmark_radar.data_store.os.replace", fail_old_version_replace)

    with pytest.raises(DataSyncError, match="cannot retire previous data version"):
        store.sync()

    assert store.state()["data_version"] == first_manifest["data_version"]
    assert [path.name for path in (store.root / "versions").iterdir()] == [
        first_manifest["data_version"]
    ]


def test_physical_cleanup_is_visible_and_retried(monkeypatch, tmp_path: Path) -> None:
    # Regression: a post-activation Windows file lock either lied about rollback
    # or left an extra version forever after the next sync returned current.
    first_manifest, first_bundle, manifest_url = _release(tmp_path / "first", day=29)
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, first_manifest, first_bundle).urlopen,
    )
    store.initialize()
    second_manifest, second_bundle, _ = _release(tmp_path / "second", day=30)
    store.urlopen = _Remote(manifest_url, second_manifest, second_bundle).urlopen
    real_rmtree = shutil.rmtree

    def fail_obsolete_cleanup(path, *args, **kwargs):
        if Path(path) == store.obsolete_path:
            raise PermissionError("obsolete version is busy")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("benchmark_radar.data_store.shutil.rmtree", fail_obsolete_cleanup)
    result = store.sync()

    assert result["status"] == "updated"
    assert result["cleanup_pending"] is True
    assert store.state()["data_version"] == second_manifest["data_version"]
    assert [path.name for path in (store.root / "versions").iterdir()] == [
        second_manifest["data_version"]
    ]
    assert store.obsolete_path.exists()

    monkeypatch.setattr("benchmark_radar.data_store.shutil.rmtree", real_rmtree)
    current = store.sync()

    assert current["status"] == "current"
    assert not store.obsolete_path.exists()


def test_sync_requires_init_and_cli_uses_managed_store(monkeypatch, tmp_path: Path, capsys) -> None:
    # Regression: sync silently creating state made init and corruption indistinguishable.
    home = tmp_path / "home"
    monkeypatch.setenv("BENCHMARK_RADAR_HOME", str(home))
    assert run_query_cli(["sync", "--json"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"]["code"] == "not_initialized"

    manifest, bundle, manifest_url = _release(tmp_path / "release")
    remote = _Remote(manifest_url, manifest, bundle)
    monkeypatch.setattr("benchmark_radar.data_store.urllib.request.urlopen", remote.urlopen)
    assert run_query_cli(["init", "--manifest-url", manifest_url, "--json"]) == 0
    capsys.readouterr()

    assert run_query_cli(["search", "agent workbench", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["data_version"] == manifest["data_version"]
    assert payload["results"][0]["name"] == "Agent Workbench"


def test_unsafe_archive_member_is_rejected(tmp_path: Path) -> None:
    # Regression: an untrusted release archive must not write outside managed storage.
    manifest, _, manifest_url = _release(tmp_path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escaped.json", "{}")
        archive.writestr("benchmark-index.json", "{}")
        archive.writestr("snapshots/example.json", "{}")
    bundle = buffer.getvalue()
    manifest["artifact"]["sha256"] = hashlib.sha256(bundle).hexdigest()
    manifest["artifact"]["size"] = len(bundle)
    manifest["artifact"]["uncompressed_size"] = 6
    manifest["artifact"]["file_count"] = 3
    store = DataStore(
        root=tmp_path / "home",
        manifest_url=manifest_url,
        urlopen=_Remote(manifest_url, manifest, bundle).urlopen,
    )

    with pytest.raises(DataSyncError, match="unsafe archive path"):
        store.initialize()
    assert not (tmp_path / "escaped.json").exists()
