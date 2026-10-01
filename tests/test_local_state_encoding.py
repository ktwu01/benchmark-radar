import json

import pytest

from benchmark_radar.data_store import DataStore, DataSyncError
from benchmark_radar.query_cli import run_query_cli


def test_invalid_state_encoding_has_the_local_state_error_contract(tmp_path):
    # A damaged UTF-8 state file bypassed DataSyncError, so offline clients
    # received a traceback instead of the same contract as malformed JSON.
    original = b'{"schema_version": 1, "data_version": "\xff"}'
    (tmp_path / "state.json").write_bytes(original)
    with pytest.raises(DataSyncError) as captured:
        DataStore(root=tmp_path).state()
    assert captured.value.code == "invalid_local_state"
    assert (tmp_path / "state.json").read_bytes() == original


@pytest.mark.parametrize("command", [["sync"], ["search", "agent"]])
def test_corrupted_state_stays_structured_in_installed_cli(tmp_path, monkeypatch, capsys, command):
    original = b"\xff"
    (tmp_path / "state.json").write_bytes(original)
    monkeypatch.setenv("BENCHMARK_RADAR_HOME", str(tmp_path))
    assert run_query_cli([*command, "--json"]) == 1
    output = capsys.readouterr()
    payload = json.loads(output.err)
    assert payload["error"]["code"] == "invalid_local_state"
    assert output.out == ""
    assert "Traceback" not in output.err
    assert (tmp_path / "state.json").read_bytes() == original
