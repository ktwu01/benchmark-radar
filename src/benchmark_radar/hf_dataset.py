"""Export Benchmark Radar datasets in standard formats for Hugging Face Hub.

Produces four subsets (configs) aligning with the Benchmark Radar paper:
1. `catalog` (default): Normalized metadata for all 1,284+ benchmarks.
2. `scores`: 12,900+ benchmark evaluation score observations across models.
3. `radar_artifacts`: 8,500+ emerging benchmarks, papers, and repositories tracked by radar.
4. `radar_observations`: 14,800+ daily dynamic discovery events and attention metrics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .corpus import CorpusError, validate_corpus
from .query import QueryPaths, QueryService

DEFAULT_EXPORT_DIR = Path("site/data/hf_dataset")
MIN_CATALOG_RECORDS = 1259
REQUIRED_CATALOG_SOURCES = frozenset(
    {"artificial_analysis", "llm_stats", "model_reports", "opencompass_hub"}
)


@dataclass
class DatasetExportResult:
    export_dir: Path
    catalog_count: int
    scores_count: int
    artifacts_count: int
    observations_count: int
    manifest: dict[str, Any]


def generate_dataset_card(
    *,
    catalog_count: int,
    scores_count: int,
    artifacts_count: int,
    observations_count: int,
    catalog_sources: Iterable[str],
) -> str:
    """Generate Hugging Face Dataset Card README.md with YAML frontmatter."""
    # Rendered from the exported rows so the card names every catalog source,
    # including ones added after REQUIRED_CATALOG_SOURCES was written.
    source_list = ", ".join(f"`{source}`" for source in sorted(catalog_sources))
    card = f"""---
pretty_name: "Benchmark Radar: AI Benchmarks and Evaluation Scores"
license: other
license_name: benchmark-radar-mixed-terms
license_link: https://github.com/ktwu01/benchmark-radar/blob/main/LICENSE-CONTENT.md
task_categories:
  - text-generation
  - question-answering
  - tabular-classification
language:
  - en
  - zh
tags:
  - benchmark
  - evaluation
  - llm
  - leaderboard
  - ai-evaluation
  - benchmark-radar
  - ai-benchmark
  - benchmark-datasets
  - llm-evaluation
  - model-evaluation
  - agent-benchmark
  - multimodal
  - model-cards
  - benchmark-discovery
size_categories:
  - 10K<n<100K
configs:
  - config_name: catalog
    default: true
    data_files: "data/catalog.jsonl"
  - config_name: scores
    data_files: "data/scores.jsonl"
  - config_name: radar_artifacts
    data_files: "data/radar_artifacts.jsonl"
  - config_name: radar_observations
    data_files: "data/radar_observations.jsonl"
---

# Benchmark Radar: AI Benchmarks and Evaluation Scores

<p align="center">
  <a href="https://huggingface.co/papers/2609.11115"><img alt="Paper" src="https://img.shields.io/badge/Paper-arXiv%3A2609.11115-B31B1B.svg"></a>
  <a href="https://benchmark-radar.org"><img alt="Website" src="https://img.shields.io/badge/Website-benchmark--radar.org-blue.svg"></a>
  <a href="https://github.com/ktwu01/benchmark-radar"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-Benchmark%20Radar-black.svg"></a>
  <a href="https://huggingface.co/datasets/ktwu01/benchmark-radar"><img alt="HF Dataset" src="https://img.shields.io/badge/Hugging%20Face-Datasets-yellow.svg"></a>
</p>

Find AI benchmarks for LLMs, agents, and multimodal models. Benchmark Radar
brings benchmark metadata, reported model scores, and daily discoveries
together, with links to original sources where available.
[Search benchmarks](https://benchmark-radar.org/) or load the four dataset
subsets below.

## Overview

**Benchmark Radar** is a living database and search engine for AI benchmarks
and evaluation, described in the technical report
*"Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and
Evaluation"* ([arXiv:2609.11115](https://arxiv.org/abs/2609.11115)). This
dataset is the live export, refreshed as sources change. The paper's analyses
use the frozen v0.11.0 catalog, so counts here differ from the paper.

As described in the paper's *Two Input Paths* framework, Benchmark Radar
combines two complementary systems:
1. **Catalog & Scores**: A curated, normalized cross-registry archive of
   **{catalog_count:,}** benchmark suites and **{scores_count:,}** reported
   model score observations from catalog source providers including
   LLM Stats, OpenCompass Hub, Artificial Analysis, Claire Radar, and model
   technical reports.
2. **Radar Discoveries**: A 24/7 automated intelligence pipeline tracking emerging
   papers, code repositories, datasets, and community attention across 37+ sources,
   capturing **{artifacts_count:,}** research artifacts and **{observations_count:,}**
   daily observations.

---

## Dataset Structure & Usage

The dataset is partitioned into 4 configs (subsets), easily loaded via
Hugging Face `datasets`:

```python
from datasets import load_dataset

# 1. Load benchmark catalog (default)
catalog = load_dataset("ktwu01/benchmark-radar", "catalog")

# 2. Load model evaluation scores
scores = load_dataset("ktwu01/benchmark-radar", "scores")

# 3. Load emerging radar artifacts (papers, repositories, datasets)
artifacts = load_dataset("ktwu01/benchmark-radar", "radar_artifacts")

# 4. Load daily discovery observations (attention, downloads, events)
observations = load_dataset("ktwu01/benchmark-radar", "radar_observations")
```

### 1. `catalog` (Default Config)
Contains {catalog_count:,} normalized benchmark records.
- `benchmark_id`: Canonical unique identifier (e.g. `llm-stats:mmlu-pro`, `opencompass:1580`)
- `slug`: URL-safe unique identifier
- `name`: Benchmark display name
- `source`: Catalog source provider ({source_list})
- `source_url`: URL to original source entry
- `description`: Plaintext description and task summary
- `categories`: Assigned category tags (e.g. `Reasoning`, `Code`, `Multimodal`)
- `languages`: Languages evaluated (e.g. `en`, `zh`)
- `modality`: Evaluated modality (`text`, `multimodal`, `code`, etc.)
- `publisher`: Creator organization or research lab
- `released_at`: Official release date (YYYY-MM-DD proxy)
- `openness`: Data and code openness tier
- `paper_url`: Associated paper URL (arXiv or DOI)
- `repo_url`: Associated code repository URL (GitHub)
- `dataset_url`: Direct dataset download or Hub URL
- `document_count`: Number of verified source documents citing this benchmark
- `model_count`: Number of distinct models evaluated
- `score_count`: Number of numeric scores recorded
- `highest_score`: Maximum observed score across all evaluated models
- `score_unit`: Score metric / unit (e.g. `%`, `accuracy`, `Elo`)

### 2. `scores`
Contains {scores_count:,} reported evaluation score observations across 870+ frontier models.
- `obs_id`: Unique observation identifier
- `key`: Benchmark key
- `model_id`: Source-specific stable model identifier, or null when the source does not provide one
- `model_name`: Model display name
- `organization`: Model creator/lab (e.g. `DeepSeek`, `OpenAI`, `Anthropic`, `Google`, `Meta`)
- `value`: Numeric reported score
- `raw_value`: Original score string from source
- `value_kind`: Value data type (`number`, `percentage`, etc.)
- `reported_date`: Model announcement or report publication date
- `date_precision`: Precision level of reported date
- `reported_by`: Source reporting modality (`self_reported`, `third_party`)
- `source`: Score ingestion source
- `source_url`: URL of source leaderboard or technical report
- `document_id`: Source document citation ID

### 3. `radar_artifacts`
Contains {artifacts_count:,} academic artifacts surfaced by daily radar.
- `id`: Artifact identifier (e.g. `artifact:github:ktwu01/benchmark-radar`)
- `type`: Entity type (`artifact`)
- `label`: Title or repository name
- `url`: Primary external URL
- `categories`: Extracted capability categories
- `sources`: Discovery sources that observed this artifact
- `first_seen_at`: First discovery date (YYYY-MM-DD)
- `last_seen_at`: Latest discovery date (YYYY-MM-DD)
- `observation_count`: Total appearances across snapshots
- `latest_score`: Attention and composite radar score
- `metrics`: Dictionary of observed signals (e.g. stars, citations, downloads)

### 4. `radar_observations`
Contains {observations_count:,} discrete daily discovery events.
- `id`: Observation identifier
- `entity_id`: Referenced artifact ID
- `snapshot_date`: Radar snapshot date (YYYY-MM-DD)
- `source`: Discovery source platform
- `source_id`: Upstream source identifier
- `url`: Surfaced event URL
- `discovered_at`: Timestamp of discovery
- `published_at`: Original creation / publication timestamp
- `total_score`: Radar composite relevance score
- `event_kind`: Event category (`discovered`, `released`, `updated`)
- `organizations`: Identified affiliated organizations
- `metrics`: Point-in-time metrics (stars, likes, downloads)

---

## Data Provenance and Principles

- **Full-Corpus Coverage**: All {catalog_count:,} benchmarks across all sources are preserved.
  Unscored benchmarks are retained with verified paper, code, and dataset links.
- **Strict Evidence Citation**: Every score links directly to its source document
  or technical report.
- **Daily Automated Sync**: Radar discoveries are refreshed daily at 05:00 UTC via GitHub Actions.

## Licensing

The technical report and Benchmark Radar's original editorial content are
available under CC BY-NC-SA 4.0. Commercial dataset packaging or product
integration requires prior written permission. Third-party benchmark metadata
and source material retain their original terms. Review the
[repository licensing notice](https://github.com/ktwu01/benchmark-radar/blob/main/LICENSE-CONTENT.md)
before reuse, especially for commercial dataset packaging.

## Citation

```bibtex
@misc{{wu2026benchmarkradarlivingdatabase,
  title={{Benchmark Radar: A Living Database and Search Engine
         for AI Benchmarks and Evaluation}},
  author={{Wu, Koutian and Zhang, Wenjun and Zhou, Junjie and Han, Pengqian
          and Shang, Ergan and Wang, Jiayu and Wang, Junkai and Xu, Wanghan
          and Lu, Songyuanyi and Li, Yixuan and Mizrahi Celekli, Rudy
          and Ravshanov, Lazizbek and Bian, Yaoliang and Han, Xudong
          and Shi, Lin}},
  year={{2026}},
  eprint={{2609.11115}},
  archivePrefix={{arXiv}},
  primaryClass={{cs.AI}},
  url={{https://arxiv.org/abs/2609.11115}},
}}
```
"""
    return card.strip() + "\n"


def export_hf_dataset(
    output_dir: Path = DEFAULT_EXPORT_DIR,
    paths: QueryPaths | None = None,
    radar_path: Path | None = None,
) -> DatasetExportResult:
    """Export the benchmark catalog, scores, and radar snapshots to JSONL format.

    Files written:
    - `output_dir/README.md` (Dataset card with YAML metadata)
    - `output_dir/data/catalog.jsonl`
    - `output_dir/data/scores.jsonl`
    - `output_dir/data/radar_artifacts.jsonl`
    - `output_dir/data/radar_observations.jsonl`
    - `output_dir/manifest.json`
    """
    resolved_paths = paths or QueryPaths()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load the catalog through the shared query contract so the export cannot
    # bypass index schema, identity, count, or detail-shard validation.
    index_data = QueryService(resolved_paths).validated_catalog_index()
    benchmarks = index_data["benchmarks"]
    if not benchmarks:
        raise ValueError(
            f"Catalog index at {resolved_paths.index} contains no benchmarks; "
            "investigate corpus reduction."
        )
    if len(benchmarks) < MIN_CATALOG_RECORDS:
        raise ValueError(
            f"Catalog index at {resolved_paths.index} contains only {len(benchmarks)} "
            f"benchmarks; expected at least {MIN_CATALOG_RECORDS}. Investigate corpus reduction."
        )
    sources = {benchmark["source"] for benchmark in benchmarks}
    missing_sources = sorted(REQUIRED_CATALOG_SOURCES - sources)
    if missing_sources:
        raise ValueError(
            "Catalog index is missing required source families: " + ", ".join(missing_sources)
        )

    # 2. Extract catalog & scores with strict shard validation
    catalog_rows = []
    score_rows = []
    score_ids = set()

    for b in benchmarks:
        slug = b.get("slug", "")
        key = b.get("key")
        shard_path = resolved_paths.shards / f"{slug}.json"
        if not shard_path.exists():
            raise FileNotFoundError(
                f"Detail shard missing at {shard_path} for key {key!r}; "
                "run `benchmark-radar normalize-catalog` first."
            )
        shard = json.loads(shard_path.read_text(encoding="utf-8"))
        shard_record = shard.get("record") or {}
        actual_key = shard_record.get("key")
        if actual_key != key:
            raise ValueError(
                f"Detail shard {shard_path} key mismatch: expected {key!r}, got {actual_key!r}"
            )

        artifacts = shard_record.get("artifacts", [])
        benchmark_score_rows = []
        scores_by_source = shard.get("scores_by_source")
        if not isinstance(scores_by_source, dict):
            raise ValueError(f"Detail shard {shard_path} scores_by_source must be an object")
        for source, source_data in scores_by_source.items():
            rows = source_data.get("rows") if isinstance(source_data, dict) else None
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError(
                    f"Detail shard {shard_path} score rows for {source!r} must be objects"
                )
            for row in rows:
                if row.get("key") != key:
                    raise ValueError(
                        f"Detail shard {shard_path} contains a score for {row.get('key')!r}; "
                        f"expected {key!r}"
                    )
                if row.get("source") != source or source != b["source"]:
                    raise ValueError(
                        f"Detail shard {shard_path} score source {row.get('source')!r} "
                        f"does not match bucket {source!r} and catalog source {b['source']!r}"
                    )
                for field in (
                    "obs_id",
                    "model_name",
                    "raw_value",
                    "value_kind",
                    "source_url",
                ):
                    if not isinstance(row.get(field), str) or not row[field]:
                        raise ValueError(
                            f"Detail shard {shard_path} score {field} must be a non-empty string"
                        )
                model_id = row.get("model_id")
                if "model_id" not in row or (
                    model_id is not None and (not isinstance(model_id, str) or not model_id.strip())
                ):
                    raise ValueError(
                        f"Detail shard {shard_path} score model_id must be null or a "
                        "non-empty string"
                    )
                if isinstance(row.get("value"), bool) or not isinstance(
                    row.get("value"), (int, float)
                ):
                    raise ValueError(f"Detail shard {shard_path} score value must be numeric")
                if row["obs_id"] in score_ids:
                    raise ValueError(f"Duplicate score observation ID {row['obs_id']!r}")
                score_ids.add(row["obs_id"])
            benchmark_score_rows.extend(rows)
        expected_score_count = b.get("score_count")
        if expected_score_count != len(benchmark_score_rows):
            raise ValueError(
                f"Detail shard {shard_path} has {len(benchmark_score_rows)} score rows; "
                f"index declares {expected_score_count!r}"
            )
        score_rows.extend(benchmark_score_rows)

        paper_url = next(
            (a["url"] for a in artifacts if a.get("kind") == "paper"),
            None,
        )
        repo_url = next(
            (a["url"] for a in artifacts if a.get("kind") == "repo"),
            None,
        )
        dataset_url = next(
            (a["url"] for a in artifacts if a.get("kind") == "dataset"),
            None,
        )

        catalog_rows.append(
            {
                "benchmark_id": b.get("key"),
                "slug": b.get("slug"),
                "name": b.get("name"),
                "source": b.get("source"),
                "source_url": b.get("source_url"),
                "description": b.get("description"),
                "categories": b.get("categories", []),
                "languages": b.get("languages", []),
                "modality": b.get("modality"),
                "publisher": b.get("publisher"),
                "released_at": b.get("released"),
                "openness": b.get("openness"),
                "paper_url": paper_url,
                "repo_url": repo_url,
                "dataset_url": dataset_url,
                "document_count": (b.get("evidence_summary") or {}).get("document_count", 0),
                "model_count": (b.get("evidence_summary") or {}).get("model_count"),
                "score_count": b.get("score_count", 0),
                "highest_score": (b.get("score_summary") or {}).get("raw_max"),
                "score_unit": b.get("unit"),
            }
        )

    # 3. Extract radar artifacts & observations from radar corpus
    radar_file = radar_path or (resolved_paths.index.parent / "radar.json")
    if not radar_file.exists():
        raise FileNotFoundError(
            f"Radar corpus missing at {radar_file}; run `benchmark-radar classify` first."
        )
    radar_data = json.loads(radar_file.read_text(encoding="utf-8"))
    if not isinstance(radar_data, dict):
        raise CorpusError("radar data must be an object")
    corpus = radar_data.get("corpus")
    if not isinstance(corpus, dict):
        raise CorpusError("radar corpus must be an object")
    for field in ("entities", "observations", "edges"):
        rows = corpus.get(field)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise CorpusError(f"radar corpus {field} must be an array of objects")
    validate_corpus(corpus)
    entities = corpus["entities"]
    observation_rows = corpus["observations"]
    if corpus.get("entity_count") != len(entities):
        raise CorpusError("radar corpus entity_count does not match its entities")
    if corpus.get("observation_count") != len(observation_rows):
        raise CorpusError("radar corpus observation_count does not match its observations")
    if corpus.get("edge_count") != len(corpus["edges"]):
        raise CorpusError("radar corpus edge_count does not match its edges")
    artifact_rows = [entity for entity in entities if entity.get("type") == "artifact"]
    aggregates = corpus.get("aggregates")
    if not isinstance(aggregates, dict) or not isinstance(aggregates.get("entity_types"), dict):
        raise CorpusError("radar corpus aggregates.entity_types must be an object")
    entity_types = aggregates["entity_types"]
    if entity_types.get("artifact") != len(artifact_rows):
        raise CorpusError("radar corpus artifact count does not match its entities")
    if not artifact_rows or not observation_rows:
        raise CorpusError("radar corpus must contain artifacts and observations")

    # 4. Write JSONL files
    catalog_file = data_dir / "catalog.jsonl"
    with catalog_file.open("w", encoding="utf-8") as f:
        for row in catalog_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    scores_file = data_dir / "scores.jsonl"
    with scores_file.open("w", encoding="utf-8") as f:
        for row in score_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    artifacts_file = data_dir / "radar_artifacts.jsonl"
    with artifacts_file.open("w", encoding="utf-8") as f:
        for row in artifact_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    observations_file = data_dir / "radar_observations.jsonl"
    with observations_file.open("w", encoding="utf-8") as f:
        for row in observation_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 5. Write Dataset Card README.md
    readme_content = generate_dataset_card(
        catalog_count=len(catalog_rows),
        scores_count=len(score_rows),
        artifacts_count=len(artifact_rows),
        observations_count=len(observation_rows),
        catalog_sources=sources,
    )
    (output_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # 6. Write Manifest
    manifest = {
        "version": "1.0.0",
        "paper_id": "2609.11115",
        "counts": {
            "catalog": len(catalog_rows),
            "scores": len(score_rows),
            "radar_artifacts": len(artifact_rows),
            "radar_observations": len(observation_rows),
        },
        "files": {
            "catalog": "data/catalog.jsonl",
            "scores": "data/scores.jsonl",
            "radar_artifacts": "data/radar_artifacts.jsonl",
            "radar_observations": "data/radar_observations.jsonl",
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return DatasetExportResult(
        export_dir=output_dir,
        catalog_count=len(catalog_rows),
        scores_count=len(score_rows),
        artifacts_count=len(artifact_rows),
        observations_count=len(observation_rows),
        manifest=manifest,
    )
