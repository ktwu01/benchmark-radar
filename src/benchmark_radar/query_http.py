"""Local HTTP surface for the shared Benchmark Radar query service."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .query import QUERY_SCHEMA_VERSION, SEARCH_SCOPES, QueryError, QueryService, error_payload

LOGGER = logging.getLogger(__name__)


def _parse_parameters(
    query: str, *, allowed: set[str], repeatable: frozenset[str] = frozenset()
) -> dict[str, list[str]]:
    parameters = parse_qs(query, keep_blank_values=True)
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise QueryError(
            f"unknown query parameter(s): {', '.join(unknown)}",
            code="invalid_request",
            status=400,
        )
    repeated = sorted(
        key for key, values in parameters.items() if len(values) != 1 and key not in repeatable
    )
    if repeated:
        raise QueryError(
            f"query parameter(s) must occur once: {', '.join(repeated)}",
            code="invalid_request",
            status=400,
        )
    return parameters


def _value(parameters: dict[str, list[str]], name: str) -> str | None:
    values = parameters.get(name)
    return values[0] if values else None


def _integer(parameters: dict[str, list[str]], name: str, *, default: int) -> int:
    raw = _value(parameters, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise QueryError(
            f"{name} must be an integer",
            code="invalid_request",
            status=400,
        ) from error


def _boolean(parameters: dict[str, list[str]], name: str, *, default: bool = False) -> bool:
    raw = _value(parameters, name)
    if raw is None:
        return default
    normalized = raw.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise QueryError(
        f"{name} must be true or false",
        code="invalid_request",
        status=400,
    )


def create_query_server(
    service: QueryService,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Create, but do not start, a local query server backed by ``service``."""

    class QueryRequestHandler(BaseHTTPRequestHandler):
        server_version = "BenchmarkRadarQuery/1"

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _route_get(self) -> dict[str, Any]:
            request = urlsplit(self.path)
            path = request.path.rstrip("/") or "/"

            if path == "/api/v1/search":
                parameters = _parse_parameters(
                    request.query,
                    allowed={
                        "q",
                        "scope",
                        "limit",
                        "has_paper",
                        "has_repo",
                        "has_dataset",
                        "openness",
                        "modality",
                        "source",
                    },
                )
                query = _value(parameters, "q")
                if query is None:
                    raise QueryError("q is required", code="invalid_request", status=400)
                scope = _value(parameters, "scope") or "catalog"
                if scope not in SEARCH_SCOPES:
                    raise QueryError(
                        f"scope must be one of {', '.join(SEARCH_SCOPES)}",
                        code="invalid_scope",
                        status=400,
                    )
                return service.search(
                    query,
                    scope=scope,
                    limit=_integer(parameters, "limit", default=20),
                    has_paper=(
                        _boolean(parameters, "has_paper") if "has_paper" in parameters else None
                    ),
                    has_repo=(
                        _boolean(parameters, "has_repo") if "has_repo" in parameters else None
                    ),
                    has_dataset=(
                        _boolean(parameters, "has_dataset") if "has_dataset" in parameters else None
                    ),
                    openness=_value(parameters, "openness"),
                    modality=_value(parameters, "modality"),
                    source=_value(parameters, "source"),
                )

            if path == "/api/v1/related-work":
                parameters = _parse_parameters(
                    request.query,
                    allowed={"q", "per_topic", "include_partial", "include_radar"},
                    repeatable=frozenset({"q"}),
                )
                topics = parameters.get("q") or []
                if not topics:
                    raise QueryError("q is required", code="invalid_request", status=400)
                return service.related_work(
                    topics,
                    per_topic=_integer(parameters, "per_topic", default=6),
                    include_partial=_boolean(parameters, "include_partial"),
                    include_radar=_boolean(parameters, "include_radar", default=True),
                )

            if path.startswith("/api/v1/benchmarks/"):
                _parse_parameters(request.query, allowed=set())
                identifier = unquote(path.removeprefix("/api/v1/benchmarks/"))
                return service.show(identifier)

            if path == "/api/v1/recent":
                parameters = _parse_parameters(
                    request.query,
                    allowed={"limit", "category", "source", "recommended"},
                )
                return service.recent(
                    limit=_integer(parameters, "limit", default=20),
                    category=_value(parameters, "category"),
                    source=_value(parameters, "source"),
                    recommended=_boolean(parameters, "recommended"),
                )

            if path == "/api/v1/status":
                _parse_parameters(request.query, allowed=set())
                return service.status()

            if path == "/healthz":
                _parse_parameters(request.query, allowed=set())
                status = service.status()
                return {
                    "schema_version": QUERY_SCHEMA_VERSION,
                    "retrieval_mode": "health_check",
                    "data": status["data"],
                    "status": "ok",
                    "data_status": status["status"],
                }

            raise QueryError(
                f"route {path!r} was not found",
                code="not_found",
                status=404,
            )

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            try:
                self._send_json(HTTPStatus.OK, self._route_get())
            except QueryError as error:
                LOGGER.info(
                    "query request rejected method=GET path=%s code=%s status=%d",
                    self.path,
                    error.code,
                    error.status,
                )
                self._send_json(error.status, error_payload(error))
            except Exception:
                LOGGER.exception("query request failed method=GET path=%s", self.path)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    error_payload(
                        QueryError("internal server error", code="internal_error", status=500)
                    ),
                )

        def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            self._send_json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                error_payload(
                    QueryError(
                        "only GET and OPTIONS are supported",
                        code="method_not_allowed",
                        status=405,
                    )
                ),
            )

        do_DELETE = do_POST
        do_PATCH = do_POST
        do_PUT = do_POST

        def log_message(self, format: str, *args: Any) -> None:
            LOGGER.info("query_http client=%s %s", self.client_address[0], format % args)

    server = ThreadingHTTPServer((host, port), QueryRequestHandler)
    server.daemon_threads = True
    return server


def serve_query_api(
    service: QueryService,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Run the local query API until interrupted."""

    server = create_query_server(service, host=host, port=port)
    LOGGER.info("Benchmark Radar query API listening on http://%s:%d", host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Benchmark Radar query API stopped")
    finally:
        server.server_close()
