"""CLI commands for local Benchmark Radar discovery."""

from __future__ import annotations

import argparse
import json
import logging
import os
import stat
import sys
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .citation import cite_reminder
from .data_store import DEFAULT_MANIFEST_URL, DataStore
from .query import (
    SEARCH_SCOPES,
    QueryError,
    QueryPaths,
    QueryService,
    error_payload,
)
from .query_http import serve_query_api

QUERY_COMMANDS = frozenset(
    {"init", "sync", "search", "show", "recent", "status", "serve", "related-work"}
)
RELATED_WORK_FORMATS = ("latex", "bibtex", "markdown")


def _data_parent() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--index", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--shards", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--snapshots", type=Path, default=None, help=argparse.SUPPRESS)
    return parser


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark-radar",
        description="Search the local Benchmark Radar catalog and daily Radar history.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    data_parent = _data_parent()

    init = subparsers.add_parser("init", help="Download and verify the current dataset.")
    init.add_argument("--data-dir", type=Path, default=None)
    init.add_argument("--manifest-url", default=DEFAULT_MANIFEST_URL)
    init.add_argument("--json", action="store_true")

    sync = subparsers.add_parser("sync", help="Update an initialized local dataset.")
    sync.add_argument("--data-dir", type=Path, default=None)
    sync.add_argument("--json", action="store_true")

    search = subparsers.add_parser(
        "search", parents=[data_parent], help="Search benchmark catalog and Radar records."
    )
    search.add_argument("query")
    search.add_argument("--scope", choices=SEARCH_SCOPES, default="catalog")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--has-paper", action=argparse.BooleanOptionalAction, default=None)
    search.add_argument("--has-repo", action=argparse.BooleanOptionalAction, default=None)
    search.add_argument("--has-dataset", action=argparse.BooleanOptionalAction, default=None)
    search.add_argument("--openness")
    search.add_argument("--modality")
    search.add_argument("--source")
    search.add_argument("--json", action="store_true")

    show = subparsers.add_parser(
        "show", parents=[data_parent], help="Show one catalog record by key or slug."
    )
    show.add_argument("identifier")
    show.add_argument("--json", action="store_true")

    recent = subparsers.add_parser(
        "recent", parents=[data_parent], help="List evidence from the latest Radar snapshot."
    )
    recent.add_argument("--limit", type=int, default=20)
    recent.add_argument("--category")
    recent.add_argument("--source")
    recent.add_argument("--recommended", action="store_true")
    recent.add_argument("--json", action="store_true")

    related = subparsers.add_parser(
        "related-work",
        parents=[data_parent],
        help="Draft a cited related-work section and BibTeX from topic queries.",
    )
    related.add_argument(
        "topics",
        nargs="+",
        metavar="TOPIC",
        help="A short query, or 'Label=query' to name the paragraph it becomes.",
    )
    related.add_argument("--per-topic", type=int, default=6)
    related.add_argument(
        "--include-partial",
        action="store_true",
        help="Keep candidates that miss some query tokens (noisier).",
    )
    related.add_argument("--no-radar", dest="include_radar", action="store_false")
    related.add_argument("--format", choices=RELATED_WORK_FORMATS, default="latex")
    related.add_argument("--tex", type=Path, help="Write the LaTeX section to this file.")
    related.add_argument("--bib", type=Path, help="Write the BibTeX entries to this file.")
    related.add_argument("--json", action="store_true")

    status = subparsers.add_parser(
        "status", parents=[data_parent], help="Inspect local catalog and snapshot health."
    )
    status.add_argument("--json", action="store_true")

    serve = subparsers.add_parser(
        "serve", parents=[data_parent], help="Serve the same query contract over local HTTP."
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _service(args: argparse.Namespace) -> QueryService:
    explicit = (args.index, args.shards, args.snapshots)
    if any(value is not None for value in explicit):
        if not all(value is not None for value in explicit):
            raise QueryError(
                "--index, --shards, and --snapshots must be passed together",
                code="invalid_paths",
                status=400,
            )
        return QueryService(
            QueryPaths(index=args.index, shards=args.shards, snapshots=args.snapshots)
        )
    return QueryService(DataStore(root=args.data_dir).query_paths())


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _print_cite_reminder(args: argparse.Namespace) -> None:
    """Issue #483: end every command round with the citation ask.

    Human output gets a blank separator line before the ask so it reads as
    a footer, not a continuation of the payload; JSON output keeps stdout
    parseable because the CLI/HTTP contract tests compare that stream
    byte-for-byte with the API payload, so the reminder rides stderr there,
    like the error contract already does. Either way an agent capturing
    both streams sees it last.
    """
    reminder = cite_reminder()
    if getattr(args, "json", False):
        print(reminder, file=sys.stderr)
    else:
        print()
        print(reminder)


def _print_search(payload: dict[str, Any]) -> None:
    if payload["search_status"] == "no_lexical_candidates":
        print(f"No lexical candidates found (scope={payload['scope']}).")
        return
    if payload["search_status"] == "partial_candidates_only":
        print(
            f"{payload['count']} of {payload['total_matches']} partial lexical candidates; "
            f"none matched every query token (scope={payload['scope']})"
        )
    else:
        print(
            f"{payload['count']} of {payload['total_matches']} lexical candidates "
            f"({payload['full_match_count']} full, {payload['partial_match_count']} partial, "
            f"scope={payload['scope']})"
        )
    for item in payload["results"]:
        locator = item.get("slug") or item["key"]
        print(f"{item['rank']:>3}. {item['name']}  [{item['kind']}]  {locator}")
        print(f"     {item['match']['reason']}; fields={','.join(item['match']['matched_fields'])}")


def _print_recent(payload: dict[str, Any]) -> None:
    print(f"{payload['count']} Radar items from {payload['date']}")
    for index, item in enumerate(payload["results"], start=1):
        print(f"{index:>3}. {item['title']}  [{item['source']}]  {item['source_id']}")


def _print_show(payload: dict[str, Any]) -> None:
    record = payload["benchmark"]["record"]
    print(f"{record['name']}\nkey: {record['key']}\nslug: {record['slug']}")
    print(f"source: {record['source']}\nopenness: {(record.get('openness') or {}).get('status')}")
    artifacts = record.get("artifacts") or []
    if artifacts:
        print("artifacts:")
        for artifact in artifacts:
            print(f"  {artifact.get('kind')}: {artifact.get('url')}")


def _stage_related_work_file(path: Path, content: str, mode: int | None) -> Path:
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        if mode is not None:
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(content)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _write_related_work_files(
    outputs: list[tuple[Path, str, str]],
) -> None:
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path | None]] = []
    try:
        destinations = [path for path, _, _ in outputs]
        canonical_destinations = [path.resolve(strict=False) for path in destinations]
        if len(set(canonical_destinations)) != len(canonical_destinations):
            raise OSError("related-work export destinations must be distinct")
        modes: dict[Path, int | None] = {}
        for path in destinations:
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise OSError(f"related-work export destination is not a regular file: {path}")
            modes[path] = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
        for path, _, content in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            staged.append((_stage_related_work_file(path, content, modes[path]), path))
        for temporary, path in staged:
            backup = None
            if path.exists():
                handle = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
                backup = Path(handle.name)
                handle.close()
                try:
                    os.replace(path, backup)
                except OSError:
                    backup.unlink(missing_ok=True)
                    raise
            backups.append((path, backup))
            os.replace(temporary, path)
    except OSError as error:
        rollback_errors = []
        for path, backup in reversed(backups):
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        for temporary, _ in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                rollback_errors.append(f"{temporary}: {cleanup_error}")
        message = f"could not write related-work artifact: {error}"
        if rollback_errors:
            message += f"; rollback incomplete: {'; '.join(rollback_errors)}"
        raise QueryError(message, code="artifact_write_failed") from error
    cleanup_errors = []
    for _, backup in backups:
        if backup is None:
            continue
        try:
            backup.unlink(missing_ok=True)
        except OSError as cleanup_error:
            cleanup_errors.append(f"{backup}: {cleanup_error}")
    if cleanup_errors:
        raise QueryError(
            "related-work outputs were committed, but backup cleanup failed: "
            + "; ".join(cleanup_errors),
            code="artifact_cleanup_failed",
        )


def _related_work_printer(args: argparse.Namespace) -> Callable[[dict[str, Any]], None]:
    """Write requested files first, then print one format for the terminal."""

    def printer(payload: dict[str, Any]) -> None:
        outputs = [
            (path, field, payload[field])
            for path, field in ((args.tex, "latex"), (args.bib, "bibtex"))
            if path is not None
        ]
        _write_related_work_files(outputs)
        for path, field, _ in outputs:
            print(f"wrote {field} to {path}", file=sys.stderr)
        if args.json:
            _print_json(payload)
            return
        print(payload[args.format], end="")
        flagged = [
            entry for entry in payload["entries"] if "authors_missing" in entry["verification"]
        ]
        if flagged:
            print(
                f"\n% {len(flagged)} of {payload['count']} entries lack authors in local data; "
                "complete them before citing.",
                file=sys.stderr,
            )

    return printer


def _print_status(payload: dict[str, Any]) -> None:
    print(f"status: {payload['status']}")
    print(f"catalog: {payload['catalog']['count']} records at {payload['catalog']['path']}")
    print(
        f"radar: {payload['radar']['snapshot_count']} snapshots; "
        f"latest={payload['radar']['latest_date']}"
    )
    gaps = payload["radar"]["required_coverage_gaps"]
    print(f"required source gaps: {', '.join(gaps) if gaps else 'none'}")


def _print_sync(payload: dict[str, Any]) -> None:
    print(f"data: {payload['status']} ({payload['data_version']})")
    print(f"location: {payload['data_home']}")
    if payload.get("cleanup_pending"):
        print("cleanup: pending; the next sync will retry obsolete data removal")


def run_query_cli(argv: Sequence[str] | None = None) -> int:
    """Run one query command and return a process-style exit code."""

    args = _parser().parse_args(argv)
    try:
        # Every payload command collects (payload, printer) and falls through
        # to one shared tail that prints both, so a new command cannot forget
        # the citation reminder (issue #483 review); `serve` is the lone
        # long-lived exception and prints it once at startup.
        printer: Callable[[dict[str, Any]], None] | None = None
        payload: dict[str, Any]
        if args.command == "init":
            payload = DataStore(root=args.data_dir, manifest_url=args.manifest_url).initialize()
            printer = _print_json if args.json else _print_sync
        elif args.command == "sync":
            payload = DataStore(root=args.data_dir).sync()
            printer = _print_json if args.json else _print_sync
        else:
            service = _service(args)
            if args.command == "search":
                payload = service.search(
                    args.query,
                    scope=args.scope,
                    limit=args.limit,
                    has_paper=args.has_paper,
                    has_repo=args.has_repo,
                    has_dataset=args.has_dataset,
                    openness=args.openness,
                    modality=args.modality,
                    source=args.source,
                )
                printer = _print_json if args.json else _print_search
            elif args.command == "show":
                payload = service.show(args.identifier)
                printer = _print_json if args.json else _print_show
            elif args.command == "recent":
                payload = service.recent(
                    limit=args.limit,
                    category=args.category,
                    source=args.source,
                    recommended=args.recommended,
                )
                printer = _print_json if args.json else _print_recent
            elif args.command == "related-work":
                payload = service.related_work(
                    args.topics,
                    per_topic=args.per_topic,
                    include_partial=args.include_partial,
                    include_radar=args.include_radar,
                )
                printer = _related_work_printer(args)
            elif args.command == "status":
                payload = service.status()
                printer = _print_json if args.json else _print_status
            elif args.command == "serve":
                logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
                status = service.status()
                if not status["catalog"]["complete"]:
                    raise QueryError(
                        "catalog detail shards are incomplete; run `benchmark-radar sync`",
                        code="data_unavailable",
                        status=503,
                    )
                print(f"Serving Benchmark Radar at http://{args.host}:{args.port}", file=sys.stderr)
                print(cite_reminder(), file=sys.stderr)
                serve_query_api(service, host=args.host, port=args.port)
                return 0
        assert printer is not None  # every non-serve command above sets it
        printer(payload)
        _print_cite_reminder(args)
        return 0
    except QueryError as error:
        print(json.dumps(error_payload(error), ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2 if 400 <= error.status < 500 else 1
    raise AssertionError(f"unhandled query command: {args.command}")
