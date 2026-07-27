# Benchmark Radar

An evidence-first daily radar for newly released AI benchmarks, evaluation methods,
datasets, leaderboards, and data-quality work.

Every day, GitHub Actions queries primary or structured sources, deduplicates records,
classifies them with a transparent taxonomy, ranks them using explainable signals, and
publishes a GitHub Issue and a
[cumulative dashboard](https://ktwu01.github.io/benchmark-radar/). It is inspired by
[agents-radar](https://github.com/duanyytop/agents-radar), with sources and scoring
redesigned for benchmark and AI-data research.

## What it tracks

- New AI/LLM benchmarks and challenge sets
- Evaluation frameworks, judge models, safety/capability evals, and leaderboards
- Public AI datasets, preference data, synthetic data, and data releases
- Data contamination, leakage, provenance, deduplication, and annotation-quality work

Default sources:

| Source | Required secret | Role |
|---|---|---|
| arXiv | No | Primary paper discovery |
| Hugging Face Hub | No | Dataset repository discovery |
| GitHub | No in Actions | Code and artifact discovery |
| OpenAlex | `OPENALEX_API_KEY` | Scholarly metadata enrichment |
| Brave Search | `BRAVE_API_KEY` | Web and lab-blog discovery |

The report remains useful without optional secrets. Missing optional sources are shown
as warnings in the source-health table instead of being silently ignored.

## How ranking works

Each item receives four visible scores:

- **Relevance**: matches against benchmark, evaluation, dataset, and data-quality taxonomy
- **Evidence**: primary/structured source, authorship, and cross-source artifact evidence
- **Recency**: time since publication or material update
- **Adoption**: logarithmically scaled stars, downloads, likes, or citations

The default priority is:

```text
0.40 relevance + 0.25 evidence + 0.20 recency + 0.15 adoption
```

This is triage, not scientific quality adjudication or endorsement.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
benchmark-radar
```

Outputs:

- `out/report.md`: the exact GitHub Issue body
- `out/items.json`: machine-readable evidence and source-health snapshot
- `data/snapshots/YYYY-MM-DD.json`: versioned, idempotent UTC snapshot
- `site/data/radar.json`: deterministic browser-ready history

Automation keeps the growing corpus on the public `radar-data` branch so the protected
`main` branch remains pull-request-only. Dashboard builds restore that history before
validation and deployment.

Rebuild the dashboard data without collecting again:

```bash
benchmark-radar rebuild
```

Run checks:

```bash
ruff check .
pytest -q
```

## Configure

Edit [`config.yml`](config.yml) to change the lookback, threshold, queries, taxonomy, and
report size. Copy `.env.example` to `.env` only for local use; never commit credentials.

Optional repository secrets:

```text
OPENALEX_API_KEY
BRAVE_API_KEY
```

The built-in `GITHUB_TOKEN` is used automatically in Actions.

## Daily publishing

`.github/workflows/daily-radar.yml` runs at 12:15 UTC and can also be started manually.
It:

1. collects and renders with read-only repository permission;
2. validates and persists one snapshot for that UTC date;
3. creates or updates the date-filtered daily Issue;
4. rebuilds and deploys the static GitHub Pages dashboard;
5. prevents duplicate snapshots and daily Issues on reruns.

The workflow needs repository Issues enabled. The labels `daily-radar` and `automated`
must exist; they are created during initial repository setup.

## Provenance and limitations

- Every entry links to its discovered primary or structured record.
- Optional-source failures are visible.
- Persisted snapshots omit raw API payloads and credentials.
- Public attention feeds are displayed separately and never contribute to quality scores.
- Reports can contain false positives; always inspect the source.
- A repository update is not necessarily a new release.
- Publication dates differ across preprints, code, datasets, and formal publications.
- This system does not automatically create ANX-Bench events or research claims.

## Public observation feeds

The Explorer can load compatible public attention observations from separate, read-only
repositories. Feed producers must follow
[`docs/public-observation-feed.schema.json`](docs/public-observation-feed.schema.json).
The dashboard validates the feed version and HTTP(S) links, renders all source text as
plain text, and labels these records as attention rather than primary evidence.

## License

MIT
