import hashlib
import io
import zipfile

import pytest
from test_data_sync import _release, _Remote

from benchmark_radar.data_store import DataStore, DataSyncError


@pytest.mark.parametrize(
    "alias",
    [
        "./benchmark-index.json",
        "benchmarks//agent-workbench.json",
        "benchmarks/./agent-workbench.json",
        "BENCHMARK-INDEX.JSON",
        "benchmarks\\agent-workbench.json",
        "benchmark-index.json:alternate",
    ],
)
def test_archive_aliases_cannot_overwrite_verified_members(tmp_path, alias):
    # ZIP member counts used raw spellings, while extraction normalized paths.
    # Aliases could overwrite one file, or behave differently across OSes.
    manifest, original, url = _release(tmp_path / "release")
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(buffer, "w") as archive:
        for member in source.infolist():
            archive.writestr(member.filename, source.read(member))
        archive.writestr(alias, b"{}")
    bundle = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        expanded = sum(member.file_size for member in archive.infolist())
        count = len(archive.infolist())
    manifest["artifact"].update(
        sha256=hashlib.sha256(bundle).hexdigest(),
        size=len(bundle),
        uncompressed_size=expanded,
        file_count=count,
    )
    store = DataStore(
        root=tmp_path / "home", manifest_url=url, urlopen=_Remote(url, manifest, bundle).urlopen
    )

    with pytest.raises(DataSyncError) as captured:
        store.initialize()

    assert captured.value.code == "invalid_artifact"
    assert "unsafe archive path" in str(captured.value)
    assert not store.state_path.exists()
    assert not (store.root / "sync.lock").exists()
    assert not (store.root / ".download.tmp").exists()
    assert list((store.root / "versions").iterdir()) == []
