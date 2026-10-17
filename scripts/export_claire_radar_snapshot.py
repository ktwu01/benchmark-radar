#!/usr/bin/env python3
"""Export the complete Claire Radar corpus as an immutable catalog snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import re
import socket
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

FIELDS = (
    "benchmark_id",
    "name",
    "aliases",
    "description",
    "categories",
    "released",
    "detail_source_url",
    "paper_url",
    "repo_url",
    "dataset_url",
    "project_url",
    "origin_source",
    "origin_record_id",
    "display_eligible",
    "data_status",
    "confidence",
    "recognition_confidence",
    "relation",
    "review_state",
    "reviewed_at",
    "review_model",
    "admission_policy_version",
    "extra_json",
    "record_sha256",
)


def _url(value: Any) -> str:
    text = str(value or "").strip().rstrip("`")
    if "\\" in text:
        return ""
    try:
        parsed = urlsplit(text)
        raw_host = unquote(parsed.hostname or "")
        authority = parsed.netloc.rsplit("@", 1)[-1]
        if authority.endswith(":"):
            return ""
        port = parsed.port
        host = (
            unicodedata.normalize("NFKC", raw_host)
            .encode("idna")
            .decode("ascii")
            .rstrip(".")
            .casefold()
        )
    except (UnicodeError, ValueError):
        return ""
    if not host or len(host) > 253 or any(ord(char) <= 32 or ord(char) == 127 for char in raw_host):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            address = ipaddress.ip_address(socket.inet_aton(host))
        except (OSError, ValueError):
            address = None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    valid_domain = address is not None or all(
        0 < len(label) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in host.split(".")
    )
    blocked = (
        not valid_domain
        or host == "localhost"
        or host.endswith(".localhost")
        or (address is not None and (address.is_loopback or address.is_unspecified))
    )
    return (
        text
        if parsed.scheme in {"http", "https"}
        and parsed.netloc
        and (port is None or 0 < port <= 65535)
        and not blocked
        else ""
    )


def _artifact_url(value: Any, kind: str) -> str:
    text = _url(value)
    if not text:
        return ""
    parsed = urlsplit(text)
    host = parsed.netloc.casefold().removeprefix("www.")
    path = parsed.path.casefold()
    repo_hosts = {"github.com", "gitlab.com", "bitbucket.org", "codeberg.org"}
    paper_hosts = {
        "arxiv.org",
        "doi.org",
        "openreview.net",
        "aclanthology.org",
        "dl.acm.org",
        "proceedings.mlr.press",
    }
    dataset_hosts = {"kaggle.com", "zenodo.org", "figshare.com"}
    if kind == "repo":
        return text if host in repo_hosts else ""
    if kind == "paper":
        return text if host in paper_hosts or path.endswith(".pdf") else ""
    if kind == "dataset":
        is_hf_dataset = host == "huggingface.co" and path.startswith("/datasets/")
        return text if is_hf_dataset or host in dataset_hosts else ""
    if host == "img.shields.io" or path.endswith((".svg", ".png", ".jpg", ".jpeg", ".gif")):
        return ""
    if host in repo_hosts | paper_hosts | dataset_hosts or host == "huggingface.co":
        return ""
    return text


def _sha256(record: dict[str, Any]) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def export_rows(document: dict[str, Any]) -> list[dict[str, str]]:
    records = document.get("records")
    if not isinstance(records, list):
        raise ValueError("input must contain a records array")

    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for record in records:
        curation = record.get("curation") or {}
        state = str(curation.get("state") or "unreviewed")

        source = record.get("source") or {}
        source_id = str(source.get("id") or "").strip()
        name = str(record.get("name") or "").strip()
        source_url = _url(source.get("url"))
        if not source_id or not name or not source_url:
            raise ValueError(f"record {record.get('id')!r} lacks exact source identity")
        if source_id in seen_ids:
            raise ValueError(f"duplicate exact source id {source_id!r}")
        seen_ids.add(source_id)

        links = record.get("links") or {}
        categories = sorted(
            {
                str(value).strip()
                for value in [
                    record.get("area"),
                    *(record.get("applicationDomains") or []),
                    *(record.get("capabilities") or []),
                    *(record.get("topics") or []),
                ]
                if str(value or "").strip()
            }
        )
        rows.append(
            {
                "benchmark_id": source_id,
                "name": name,
                "aliases": json.dumps(record.get("aliases") or [], ensure_ascii=False),
                "description": str(
                    record.get("description") or record.get("oneLine") or ""
                ).strip(),
                "categories": json.dumps(categories, ensure_ascii=False),
                "released": str(record.get("releasedAt") or "").strip(),
                "detail_source_url": source_url,
                "paper_url": _artifact_url(links.get("paper"), "paper"),
                "repo_url": _artifact_url(links.get("code"), "repo"),
                "dataset_url": _artifact_url(links.get("data"), "dataset"),
                "project_url": _artifact_url(links.get("project"), "project"),
                "origin_source": str(source.get("type") or "").strip(),
                "origin_record_id": str(record.get("id") or "").strip(),
                "display_eligible": (
                    "true"
                    if record.get("displayEligible") is True
                    else "false"
                    if record.get("displayEligible") is False
                    else "unknown"
                ),
                "data_status": str(record.get("dataStatus") or "").strip(),
                "confidence": str(record.get("confidence") or "").strip(),
                "recognition_confidence": str(
                    record.get("recognitionConfidence")
                    if record.get("recognitionConfidence") is not None
                    else ""
                ).strip(),
                "relation": str(record.get("relation") or "").strip(),
                "review_state": state,
                "reviewed_at": str(curation.get("reviewedAt") or "").strip(),
                "review_model": str(curation.get("model") or "").strip(),
                "admission_policy_version": str(
                    curation.get("admissionPolicyVersion") or ""
                ).strip(),
                "extra_json": json.dumps(
                    record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
                "record_sha256": _sha256(record),
            }
        )

    return sorted(rows, key=lambda row: row["benchmark_id"])


def carry_forward(
    rows: list[dict[str, str]], previous: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Keep previously exported records that the upstream export no longer lists.

    Claire Radar's records file is a rolling window: on 2026-10-14 it no longer
    listed 156 reviewed, display-eligible benchmarks that the 2026-09-25 export
    carried. Replacing the snapshot wholesale would have deleted them from the
    catalog, and a record must not leave the corpus because a source stopped
    repeating it. Carried rows are copied byte for byte, so their embedded
    original object and its hash still verify.

    The rows carry no crawl time of their own. Record each carried set as a
    `carried_forward` cohort (snapshot, crawl time, ids) in
    data/leaderboard_snapshots.yml; `update_cohorts` computes that list for a
    refresh.
    """
    current = {row["benchmark_id"] for row in rows}
    kept = [row for row in previous if row["benchmark_id"] not in current]
    for row in kept:
        if list(row) != list(FIELDS):
            raise ValueError(f"previous row {row.get('benchmark_id')!r} has a different layout")
    return sorted([*rows, *kept], key=lambda row: row["benchmark_id"])


def update_cohorts(
    cohorts: list[dict[str, Any]],
    upstream_ids: set[str],
    carried_ids: set[str],
    *,
    from_snapshot: str,
    crawled_at: str,
) -> list[dict[str, Any]]:
    """The carried_forward cohorts after a refresh.

    A record upstream lists again was just recollected, so it leaves every older
    cohort; keeping it there would stamp the fresh row with the old crawl time.
    Records newly carried this time form a cohort dated to the crawl they were
    last seen in (the previous snapshot), and records already in a cohort keep
    the one they have.
    """
    updated = []
    claimed: set[str] = set()
    for cohort in cohorts:
        ids = sorted(set(cohort["benchmark_ids"]) - upstream_ids)
        claimed.update(ids)
        if ids:
            updated.append({**cohort, "benchmark_ids": ids})
    fresh = sorted(carried_ids - claimed)
    if fresh:
        updated.append(
            {"from_snapshot": from_snapshot, "crawled_at": crawled_at, "benchmark_ids": fresh}
        )
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--carry-forward",
        type=Path,
        help="previous snapshot CSV whose records absent from SOURCE are kept unchanged",
    )
    args = parser.parse_args()

    document = json.loads(args.source.read_text(encoding="utf-8"))
    rows = export_rows(document)
    if args.carry_forward:
        csv.field_size_limit(1 << 30)
        with args.carry_forward.open(encoding="utf-8", newline="") as handle:
            previous = list(csv.DictReader(handle))
        before = len(rows)
        rows = carry_forward(rows, previous)
        print(f"carried forward {len(rows) - before} records from {args.carry_forward}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"exported {len(rows)} corpus records to {args.output}")


if __name__ == "__main__":
    main()
