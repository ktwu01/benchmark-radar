"""Normalize model reports into the benchmark catalog's record contract."""

from __future__ import annotations

import json
from typing import Any

from .benchmark_scores import score_progression
from .catalog import CATALOG_SCHEMA_VERSION, first_score_record
from .model_cards import adoption_rank
from .score_summary import score_summary

SOURCE = "model_reports"


def normalize_reports(registry: dict[str, Any], scores: dict[str, Any]) -> dict[str, Any]:
    """Keep every registered benchmark, its score rows and its cited documents.

    The report registry supplies evidence just like a leaderboard snapshot.
    Document mentions do not manufacture scores or identify individual models
    in reports that cover a whole family. Numeric rows identify the scored model.
    """
    progression = score_progression(scores, registry)["benchmarks"] if scores["results"] else {}
    entries = adoption_rank(registry)["entries"]
    cards = {str(card["id"]): card for card in registry["model_cards"]}
    # A benchmark's publisher can run the leaderboard itself. That document is
    # evidence like any card, so it joins the same citation map rather than
    # leaving its score rows pointing at a document the catalog never sees.
    owned_documents: dict[str, list[dict[str, Any]]] = {}
    for source in registry.get("source_documents", []):
        cards[str(source["id"])] = source
        for ref in source["benchmarks"]:
            owned_documents.setdefault(str(ref), []).append(source)
    records, series, observations = [], [], []
    for entry in entries:
        benchmark_id = entry["benchmark_id"]
        key = f"model-reports:{benchmark_id}"
        track = progression.get(benchmark_id) or {}
        documents = [
            {
                "id": f"{SOURCE}:{card['model_card_id']}",
                "source": SOURCE,
                "source_id": card["model_card_id"],
                "source_url": card["url"],
                "document_type": card["document_type"],
                "title": card["model"],
                "model_name": card["model"],
                "organization": card["organization"],
                "published": card["published"],
                "retrieved_at": str(cards[card["model_card_id"]].get("retrieved_at") or "") or None,
            }
            for card in entry["adopters"]
        ]
        documents.extend(
            {
                "id": f"{SOURCE}:{source['id']}",
                "source": SOURCE,
                "source_id": str(source["id"]),
                "source_url": str(source["url"]),
                "document_type": str(source["document_type"]),
                "title": str(source["name"]),
                "model_name": None,
                "organization": source["publisher"],
                "published": str(source.get("published") or "") or None,
                "retrieved_at": str(source.get("retrieved_at") or "") or None,
            }
            for source in owned_documents.get(benchmark_id, [])
        )
        url = entry["url"]
        artifact_kind = (
            "paper"
            if url and "arxiv.org/" in url
            else "repo"
            if url and "github.com/" in url
            else "website"
        )
        records.append(
            {
                "schema_version": CATALOG_SCHEMA_VERSION,
                "key": key,
                # Preserve existing ?lfrontier=hle and other report links.
                "slug": benchmark_id,
                "source": SOURCE,
                "source_benchmark_id": benchmark_id,
                "name": entry["name"],
                "aliases": entry["aliases"],
                # The registry's audit records are catalog evidence like the
                # documents below: dropping them here would leave them in the
                # YAML and out of every shard, index and page built from this
                # record.
                "audits": entry["audits"],
                "description": {"en": entry["caveat"]} if entry["caveat"] else {},
                "publisher": None,
                "artifacts": [{"kind": artifact_kind, "url": url}] if url else [],
                "openness": {
                    "status": "unknown",
                    "code_license": None,
                    "data_license": None,
                    "evidence": [],
                },
                "sizes": [],
                "released": entry["released"],
                "released_reference": {
                    "source_key": key,
                    "source_url": url,
                    "basis": "benchmark_release",
                }
                if entry["released"] and url
                else None,
                "modality": None,
                "categories": [entry["domain"]],
                "documents": documents,
                "provenance": {
                    "source_url": url,
                    "registry": "data/model_cards.yml",
                    "score_archive": "data/benchmark_scores.yml",
                },
            }
        )
        rows = []
        for result in track.get("observations", []):
            card = cards[result["source_id"]]
            publisher_run = result.get("measurement_kind") == "benchmark_publisher_run"
            rows.append(
                {
                    **result,
                    "key": key,
                    "obs_id": result["observation_id"],
                    "source": SOURCE,
                    "series_id": f"{SOURCE}:{benchmark_id}:default",
                    "model_id": json.dumps(
                        [result["organization"], result["model"]],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "model_name": result["model"],
                    "raw_value": str(result["value"]),
                    "value_kind": "number",
                    "reported_date": result["reported_at"],
                    "date_precision": "document_publication",
                    "source_url": str(card["url"]),
                    "reported_by": "third_party"
                    if publisher_run or result.get("reported_by")
                    else "self_reported",
                    "measured_by": card["publisher"]
                    if publisher_run
                    else result.get("reported_by") or result["organization"],
                    "document_id": f"{SOURCE}:{result['source_id']}",
                    "comparable_group": json.dumps(
                        [key, result["instrument"], result["protocol"]],
                        separators=(",", ":"),
                    ),
                    "rank_in_source_response": None,
                }
            )
        observations.extend(rows)
        if not rows:
            continue
        values = [row["value"] for row in rows]
        bound = (scores["benchmarks"].get(benchmark_id) or {}).get("bounds", {}).get("max")
        series.append(
            {
                "key": key,
                "series_id": f"{SOURCE}:{benchmark_id}:default",
                "metric": track["metric"],
                "direction": track["direction"],
                "direction_basis": "reported_metric",
                "unit": track["unit"],
                "declared_max": bound,
                "observed_max": max(values),
                "max_score_contradicted": bound is not None and max(values) > bound,
                "display_scale": None,
                "observation_count": len(rows),
                "first_score_report": first_score_record(rows, allow_model_dates=False),
                "first_score_record": first_score_record(rows),
                "score_summary": score_summary(rows, unit=track["unit"]),
            }
        )
    return {
        "source_records": sorted(records, key=lambda record: record["key"]),
        "score_series": sorted(series, key=lambda record: record["key"]),
        "score_observations": sorted(observations, key=lambda row: row["obs_id"]),
        "validation": {
            "source": SOURCE,
            "source_record_count": len(records),
            "score_observation_count": len(observations),
            "document_count": len(cards),
        },
    }
