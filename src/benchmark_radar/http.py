from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import certifi

USER_AGENT = "benchmark-radar/0.1 (+https://github.com/ktwu01/benchmark-radar)"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RETRY_DELAY_SECONDS = 30.0


class RequestError(RuntimeError):
    """Credential-safe HTTP failure suitable for public source-health output."""


def _safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    if params:
        clean = {key: value for key, value in params.items() if value is not None}
        url = f"{url}?{urllib.parse.urlencode(clean)}"
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    return json.loads(_request(url, request_headers, attempts, timeout=timeout).decode("utf-8"))


def get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request_headers = {"User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    return _request(url, request_headers, attempts, timeout=timeout).decode("utf-8")


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    attempts: int = 2,
    timeout: float = 10.0,
) -> Any:
    request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    request_headers.update(headers or {})
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return json.loads(
        _request(url, request_headers, attempts, timeout=timeout, data=body).decode("utf-8")
    )


def _request(
    url: str,
    headers: dict[str, str],
    attempts: int,
    *,
    timeout: float,
    data: bytes | None = None,
) -> bytes:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers, data=data),
                timeout=timeout,
                context=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            # Only rate limits and server failures are transient. Never expose
            # a query string: some APIs carry credentials there.
            if error.code != 429 and error.code < 500:
                raise RequestError(f"HTTP {error.code} from {_safe_url(url)}") from None
            last_error = error
            retry_after = error.headers.get("Retry-After") if error.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            if attempt + 1 < attempts:
                time.sleep(min(delay, MAX_RETRY_DELAY_SECONDS))
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, MAX_RETRY_DELAY_SECONDS))
    assert last_error is not None
    if isinstance(last_error, urllib.error.HTTPError):
        raise RequestError(
            f"HTTP {last_error.code} from {_safe_url(url)} after {attempts} attempts"
        ) from None
    raise RequestError(
        f"{type(last_error).__name__} from {_safe_url(url)} after {attempts} attempts"
    ) from None
