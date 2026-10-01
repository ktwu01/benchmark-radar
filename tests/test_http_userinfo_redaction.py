import io
import urllib.error

import pytest

from benchmark_radar.http import RequestError, get_json


@pytest.mark.parametrize("status", [400, 503, None])
def test_source_failure_does_not_publish_url_credentials(monkeypatch, status):
    # Source-health messages are public; query stripping alone still leaked
    # URL userinfo through netloc on both permanent and exhausted failures.
    url = "https://fixture-user:fixture-password@example.test:8443/data?key=fixture-key"

    def fail(request, **kwargs):
        if status is None:
            raise urllib.error.URLError("fixture connection failed")
        raise urllib.error.HTTPError(request.full_url, status, "failed", {}, io.BytesIO())

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fail)
    with pytest.raises(RequestError) as captured:
        get_json(url, attempts=1)
    message = str(captured.value)
    assert "https://example.test:8443/data" in message
    for credential in ("fixture-user", "fixture-password", "fixture-key"):
        assert credential not in message


def test_redaction_preserves_ipv6_authority(monkeypatch):
    def fail(request, **kwargs):
        raise urllib.error.URLError("fixture connection failed")

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fail)
    with pytest.raises(RequestError, match=r"https://\[::1\]:8443/data"):
        get_json("https://[::1]:8443/data?key=fixture-key", attempts=1)
