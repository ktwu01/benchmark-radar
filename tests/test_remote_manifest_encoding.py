import json

import pytest
from test_data_sync import _release, _Remote, _Response

from benchmark_radar.data_store import DataStore
from benchmark_radar.query import QueryService
from benchmark_radar.query_cli import run_query_cli


@pytest.mark.parametrize("command", ["init", "sync"])
@pytest.mark.parametrize("body", [b"\xff", b'{"data_version": "\xfe"}'])
def test_remote_manifest_encoding_stays_a_structured_cli_error(
    tmp_path, monkeypatch, capsys, command, body
):
    # A malformed remote body bypassed QueryError and leaked a traceback from
    # JSON's byte decoder; it must not replace the last verified local release.
    home = tmp_path / "home"
    manifest, bundle, url = _release(tmp_path / "release")
    store = DataStore(root=home, manifest_url=url, urlopen=_Remote(url, manifest, bundle).urlopen)
    if command == "sync":
        store.initialize()
    previous = store.state_path.read_bytes() if store.state_path.exists() else None
    monkeypatch.setenv("BENCHMARK_RADAR_HOME", str(home))
    monkeypatch.setattr(
        "benchmark_radar.data_store.urllib.request.urlopen",
        lambda request, **kwargs: _Response(body, url=request.full_url),
    )

    arguments = ["--manifest-url", url] if command == "init" else []
    assert run_query_cli([command, *arguments, "--json"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_manifest"
    assert "Traceback" not in captured.err
    assert not (home / "sync.lock").exists()
    assert not (home / ".download.tmp").exists()
    if previous is None:
        assert not store.state_path.exists()
    else:
        assert store.state_path.read_bytes() == previous
        assert QueryService(store.query_paths()).status()["status"] == "ok"
