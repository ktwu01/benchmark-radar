import json
import urllib.error

import pytest
from test_data_sync import _release, _Remote, _Response

from benchmark_radar.data_store import DataStore
from benchmark_radar.query import QueryService


@pytest.mark.parametrize(
    "override",
    [
        "https://another.test/data/cli/manifest.json",
        "https://example.test/another/manifest.json",
    ],
)
def test_manifest_override_does_not_reuse_another_resources_etag(tmp_path, override):
    # An opaque ETag only describes its original resource. Sending it to a new
    # manifest can produce a valid-looking 304 that hides the new dataset.
    first, first_bundle, original_url = _release(tmp_path / "first", day=29)
    home = tmp_path / "home"
    DataStore(
        root=home,
        manifest_url=original_url,
        urlopen=_Remote(original_url, first, first_bundle).urlopen,
    ).initialize()
    second, second_bundle, _ = _release(tmp_path / "second", name="Updated Workbench", day=30)
    requests = []

    def new_source(request, **kwargs):
        requests.append(request)
        if request.full_url == override:
            if request.headers.get("If-none-match") == '"release-1"':
                raise urllib.error.HTTPError(request.full_url, 304, "Not Modified", {}, None)
            return _Response(
                json.dumps(second).encode(), headers={"ETag": '"release-1"'}, url=override
            )
        assert request.full_url == second["artifact"]["url"]
        return _Response(second_bundle, url=request.full_url)

    store = DataStore(root=home, manifest_url=override, urlopen=new_source)
    result = store.sync()

    assert "If-none-match" not in requests[0].headers
    assert result["status"] == "updated"
    assert result["data_version"] == second["data_version"]
    assert store.state()["manifest_url"] == override
    assert store.state()["etag"] == '"release-1"'
    assert QueryService(store.query_paths()).search("Updated Workbench")["count"] == 1
