#!/usr/bin/env python3
"""Export the complete Claire Radar corpus as an immutable catalog snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

FIELDS = (
    "benchmark_id",
    "name",
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
    "record_sha256",
)


def _url(value: Any) -> str:
    text = str(value or "").strip()
    return text if urlsplit(text).scheme in {"http", "https"} else ""


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
                "record_sha256": _sha256(record),
            }
        )

    return sorted(rows, key=lambda row: row["benchmark_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    document = json.loads(args.source.read_text(encoding="utf-8"))
    rows = export_rows(document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"exported {len(rows)} corpus records to {args.output}")


if __name__ == "__main__":
    main()
