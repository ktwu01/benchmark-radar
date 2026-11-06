"""Reviewed reader requests for GitHub repositories the time windows missed.

Every discovery path is anchored to the run date: GitHub search filters on
`pushed:`, the organization connector keeps only repositories created inside
the window, and arXiv reads a few days of announcements. A repository that
entered a window and was dropped, or never entered one, cannot come back by
adding a query or an organization (issue #555). This registry names such a
repository directly, so a reader report becomes something a maintainer can act
on.

A request grants discovery only. The fetched record still flows through the
same summary rules, taxonomy, suppression and deduplication as a search hit.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

FULL_NAME_PATTERN = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
ISSUE_URL_PATTERN = re.compile(r"https://github\.com/ktwu01/benchmark-radar/issues/\d+")


class RequestedRepositoryRegistryError(ValueError):
    pass


def load_requested_github_repositories(path: str | Path) -> list[dict[str, Any]]:
    """Load the registry, rejecting rows a reviewer could not trace to a request."""
    registry_path = Path(path)
    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RequestedRepositoryRegistryError(
            f"Cannot read requested GitHub repository registry: {registry_path}"
        ) from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RequestedRepositoryRegistryError(
            "Requested GitHub repository registry must use schema_version 1"
        )
    rows = payload.get("repositories")
    if not isinstance(rows, list):
        raise RequestedRepositoryRegistryError(
            "Requested GitHub repository registry repositories must be an array"
        )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise RequestedRepositoryRegistryError(f"Repository #{index} must be an object")
        full_name = str(row.get("full_name") or "").strip()
        if not FULL_NAME_PATTERN.fullmatch(full_name):
            raise RequestedRepositoryRegistryError(
                f"Repository #{index} has an invalid owner/name: {full_name!r}"
            )
        issue = str(row.get("issue") or "").strip()
        if not ISSUE_URL_PATTERN.fullmatch(issue):
            raise RequestedRepositoryRegistryError(
                f"Repository {full_name} must cite the Benchmark Radar issue that requested it"
            )
        requested_at = row.get("requested_at")
        if not isinstance(requested_at, date):
            raise RequestedRepositoryRegistryError(
                f"Repository {full_name} needs requested_at as a YYYY-MM-DD date"
            )
        if full_name.casefold() in seen:
            raise RequestedRepositoryRegistryError(f"Duplicate repository: {full_name}")
        seen.add(full_name.casefold())
        normalized.append({"full_name": full_name, "issue": issue, "requested_at": requested_at})
    return normalized
