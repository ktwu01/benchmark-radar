import http.client
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


class TruncatedResponse:
    def read(self, *args):
        raise http.client.IncompleteRead(b'{"error":')

    def close(self):
        pass


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


def test_http_honors_decimal_retry_after(monkeypatch):
    sleeps = []
    calls = 0

    def fake_urlopen(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": "1.5"},
                io.BytesIO(),
            )
        return Response(b'{"ok": true}')

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.sleep", sleeps.append)

    assert get_json("https://example.test/data", attempts=2) == {"ok": True}
    assert sleeps == [1.5]


def test_openai_failure_exposes_codes_without_error_prose(monkeypatch):
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {},
            io.BytesIO(
                b'{"error":{"message":"secret-looking prose","type":"insufficient_quota",'
                b'"code":"insufficient_quota"}}'
            ),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RequestError) as captured:
        post_json("https://api.openai.com/v1/responses", {"input": "private"}, attempts=1)

    assert "type=insufficient_quota" in str(captured.value)
    assert "code=insufficient_quota" in str(captured.value)
    assert "secret-looking prose" not in str(captured.value)


def test_truncated_openai_error_body_stays_a_request_error(monkeypatch):
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {},
            TruncatedResponse(),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RequestError, match="HTTP 429"):
        post_json("https://api.openai.com/v1/responses", {"input": "private"}, attempts=1)


def test_openai_rate_limit_headers_survive_in_exhaustion_message(monkeypatch):
    # A token-bucket 429 is undiagnosable from its body alone: the numbers that
    # separate "request too big for the plan" from "bucket already drained" live
    # only in these response headers.
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {
                "x-ratelimit-limit-tokens": "30000",
                "x-ratelimit-remaining-tokens": "0",
                "x-ratelimit-reset-tokens": "1m0s",
            },
            io.BytesIO(),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.sleep", lambda seconds: None)

    with pytest.raises(RequestError) as captured:
        post_json(
            "https://api.openai.com/v1/responses",
            {"input": "private"},
            attempts=2,
        )

    message = str(captured.value)
    assert "x-ratelimit-limit-tokens=30000" in message
    assert "x-ratelimit-remaining-tokens=0" in message
    assert "x-ratelimit-reset-tokens=1m0s" in message


def test_openai_rate_limit_header_prose_is_dropped(monkeypatch):
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {
                "x-ratelimit-remaining-tokens": "please rotate key sk-abc now",
                "x-ratelimit-reset-tokens": "1m0s",
            },
            io.BytesIO(),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.sleep", lambda seconds: None)

    with pytest.raises(RequestError) as captured:
        post_json("https://api.openai.com/v1/responses", {"input": "x"}, attempts=1)

    message = str(captured.value)
    assert "sk-abc" not in message
    assert "please rotate" not in message
    assert "x-ratelimit-reset-tokens=1m0s" in message


def test_non_openai_429_carries_no_rate_header_fields(monkeypatch):
    def fake_urlopen(request, **kwargs):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "rate limited",
            {"x-ratelimit-limit-tokens": "30000"},
            io.BytesIO(),
        )

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.sleep", lambda seconds: None)

    with pytest.raises(RequestError) as captured:
        get_json("https://example.test/data", attempts=1)

    assert "x-ratelimit" not in str(captured.value)


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


@pytest.mark.parametrize("status", [401, 429, 503])
def test_http_failures_close_real_error_response_streams(monkeypatch, status):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    errors = []
    native_urlopen = urllib.request.urlopen

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(b"upstream failure")

        def log_message(self, *_args):
            pass

    def capture_error(*args, **kwargs):
        try:
            return native_urlopen(*args, **kwargs)
        except urllib.error.HTTPError as error:
            errors.append(error)
            raise

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", capture_error)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(RequestError, match=f"HTTP {status}"):
            get_json(f"http://127.0.0.1:{server.server_port}/data", attempts=2)
        assert len(errors) == (1 if status == 401 else 2)
        # urllib's HTTPError owns the response stream. Suppressing its cause
        # does not close it, including each abandoned retry response.
        assert all(error.fp.closed for error in errors)
    finally:
        for error in errors:
            error.close()
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
