import io
import urllib.error

import pytest

from benchmark_radar.http import RequestError, get_json, post_json


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def test_http_retries_rate_limits_then_succeeds(monkeypatch):
    attempts = []
    sleeps = []

    def fake_urlopen(request, **kwargs):
        attempts.append(request.full_url)
        if len(attempts) < 3:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": "0"},
                io.BytesIO(),
            )
        return Response(b'{"ok": true}')

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.sleep", sleeps.append)

    assert get_json("https://example.test/data", attempts=3) == {"ok": True}
    assert len(attempts) == 3
    assert sleeps == [0.0, 0.0]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            urllib.error.HTTPError(
                "https://example.test/data",
                500,
                "server error",
                {},
                io.BytesIO(),
            ),
            "HTTP 500",
        ),
        (TimeoutError("timed out"), "TimeoutError"),
    ],
)
def test_http_exhaustion_is_bounded(monkeypatch, error, expected):
    calls = []
    monkeypatch.setattr("benchmark_radar.http.time.sleep", lambda seconds: None)

    def fake_urlopen(request, **kwargs):
        calls.append(request.full_url)
        raise error

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RequestError, match=expected):
        get_json("https://example.test/data", attempts=2)

    assert len(calls) == 2


def test_http_failure_never_exposes_query_credentials(monkeypatch):
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "unauthorized",
            {},
            io.BytesIO(),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RequestError) as captured:
        get_json(
            "https://example.test/data",
            params={"api_key": "do-not-print", "query": "benchmark"},
        )

    assert "do-not-print" not in str(captured.value)
    assert "?" not in str(captured.value)


def test_post_json_sends_compact_json_and_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, **kwargs):
        captured.update(request=request, kwargs=kwargs)
        return Response(b'{"output": []}')

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)

    assert post_json(
        "https://example.test/responses",
        {"input": "brief me"},
        headers={"Authorization": "Bearer secret"},
        attempts=1,
    ) == {"output": []}
    assert captured["request"].data == b'{"input":"brief me"}'
    assert captured["request"].get_header("Content-type") == "application/json"
    assert captured["request"].get_header("Authorization") == "Bearer secret"
