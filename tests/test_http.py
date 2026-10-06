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


@pytest.mark.parametrize(("seconds", "expected"), [(30, 30.0), (-30, 0.0), (120, 60.0)])
def test_http_honors_http_date_retry_after(monkeypatch, seconds, expected):
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    calls = 0
    sleeps = []

    def fake_urlopen(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": format_datetime(now + timedelta(seconds=seconds), usegmt=True)},
                io.BytesIO(),
            )
        return Response(b'{"ok": true}')

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.time", lambda: now.timestamp())
    monkeypatch.setattr("benchmark_radar.http.time.sleep", sleeps.append)
    # RFC 9110 permits an HTTP-date, not only delta seconds. Retrying in one
    # second despite a future date consumes the rate-limit quota again.
    assert get_json("https://example.test/data", attempts=2) == {"ok": True}
    assert sleeps == [expected]


@pytest.mark.parametrize("host_timezone", ["UTC0", "EST5", "CET-1"])
def test_http_asctime_retry_after_uses_utc_in_every_host_timezone(monkeypatch, host_timezone):
    import os
    import time
    from datetime import UTC, datetime

    if not hasattr(time, "tzset"):
        pytest.skip("Native timezone switching requires time.tzset")
    original_timezone = os.environ.get("TZ")
    monkeypatch.setenv("TZ", host_timezone)
    time.tzset()
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    calls = 0
    sleeps = []

    def fake_urlopen(request, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {"Retry-After": "Tue Oct  6 12:00:30 2026"},
                io.BytesIO(),
            )
        return Response(b'{"ok": true}')

    monkeypatch.setattr("benchmark_radar.http.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("benchmark_radar.http.time.time", lambda: now.timestamp())
    monkeypatch.setattr("benchmark_radar.http.time.sleep", sleeps.append)
    try:
        assert get_json("https://example.test/data", attempts=2) == {"ok": True}
        assert sleeps == [30.0]
    finally:
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        time.tzset()
