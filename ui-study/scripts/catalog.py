"""Project the generated catalog into the UI study without dropping source records."""

import json
from pathlib import Path


def build_explorer_catalog(site: Path, destination: Path) -> None:
    index = json.loads((site / "data/benchmark-index.json").read_text())
    result = []
    for entry in index["benchmarks"]:
        detail = json.loads((site / "data/benchmarks" / f"{entry['slug']}.json").read_text())
        record = detail["record"]
        summary = entry.get("score_summary") or {}
        evidence = entry.get("evidence_summary") or {}
        multiplier = summary.get("display_multiplier") or 1
        history = []
        for source in detail.get("scores_by_source", {}).values():
            for row in source.get("rows", []):
                value = row.get("value")
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                protocol = row.get("protocol") or row.get("conditions")
                if protocol and not isinstance(protocol, str):
                    protocol = json.dumps(protocol, ensure_ascii=False)
                history.append(
                    [
                        row.get("reported_date"),
                        value * multiplier if entry.get("unit") == "percent" else value,
                        row.get("model_name") or row.get("model_id"),
                        protocol,
                        row.get("source_url"),
                        row.get("date_precision"),
                    ]
                )
        result.append(
            {
                "id": entry["key"],
                "slug": entry["slug"],
                "name": entry["name"],
                "aliases": entry.get("aliases", []),
                "source": entry["source"],
                "tags": entry.get("categories", []),
                "description": entry.get("description"),
                "publisher": entry.get("publisher"),
                "date": entry.get("released"),
                "url": entry.get("source_url"),
                "max": summary.get("display_max"),
                "raw": summary.get("raw_max"),
                "unit": entry.get("unit"),
                "direction": entry.get("score_direction"),
                "multiplier": multiplier,
                "models": evidence.get("model_count"),
                "docs": evidence.get("document_count"),
                "observations": entry.get("score_count"),
                "metric": record.get("metric"),
                "documents": record.get("documents", []),
                "artifacts": record.get("artifacts", []),
                "history": history,
            }
        )
    # A missing shard must fail above instead of quietly shrinking the catalog.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
