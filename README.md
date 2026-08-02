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
| OpenReview | No | Primary conference and workshop submissions |
| Hugging Face Hub | No | Dataset repository discovery |
| GitHub | No in Actions | Code and artifact discovery |
| GitHub Releases | No in Actions | Curated first-party release discovery |
| Semantic Scholar | Optional `SEMANTIC_SCHOLAR_API_KEY` | Structured scholarly discovery |
| OpenAlex | Free `OPENALEX_API_KEY` | Scholarly metadata enrichment |
| Brave Search | `BRAVE_API_KEY` | Web and lab-blog discovery |
| Hacker News | No | Public attention only; never quality-scored |

The report remains useful without optional secrets. Missing optional sources are shown
as warnings in the source-health table instead of being silently ignored.

## How ranking works

Each item receives four visible scores:

- **Relevance**: matches against benchmark, evaluation, dataset, and data-quality taxonomy
- **Evidence**: primary/structured source, authorship, and cross-source artifact evidence
- **Recency**: time since publication or material update
- **Adoption**: logarithmically scaled stars, downloads, likes, or citations

The default priority is reported on a 0–100 scale:

```text
0.35 relevance + 0.20 evidence + 0.20 recency + 0.25 adoption
```

The weights, per-component bands, and stated limits live in
[`src/benchmark_radar/rubric.py`](src/benchmark_radar/rubric.py) and are published into
`site/data/radar.json`, so the rubric the dashboard shows is read from the same definition
the pipeline applies. Every priority score on the dashboard is clickable: it opens the
rubric with that record's own component scores worked through the weighted sum.
Recency uses the full configured lookback window, and narrowly defined negative
signals demote follower-count leaderboards, result indexes, submission placeholders,
and visualization-only companions. The latter three are suppressed from the daily list;
the selection funnel reports the count, and every scored deduction remains auditable.

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
- `site/data/radar.json`: deterministic browser-ready history, cumulative entity graph,
  observations, edges, and precomputed aggregates generated for deployment

Validated snapshots are the canonical corpus and live on `main` beside the code and
schema that interpret them. A dedicated snapshot-writer GitHub App may append only
validated daily snapshots through the protected-branch bypass; human changes remain
pull-request-only. Dashboard builds derive `site/data/radar.json` without tracking it.

Rebuild the dashboard data without collecting again:

```bash
benchmark-radar rebuild
```

`benchmark-radar backfill` is the explicit corpus-replay alias. It validates every
snapshot, resolves entities from exact identifiers (DOI, arXiv, OpenReview, GitHub,
and Hugging Face), and deterministically regenerates the same entity/observation/edge
graph and aggregates under the
[versioned public schema](docs/cumulative-corpus.schema.json). No fuzzy match silently
merges similarly titled artifacts.

The dashboard exposes one filterable Today list, inline multi-record expansion, Trends,
and a keyboard-accessible Trend Map. Selecting a map node carries its exact topic,
source, organization, or artifact into the Today filters. Trend comparisons require
both the same report limit and the same connector-coverage signature; incomplete days
remain visible and are explicitly annotated.

Run checks:

```bash
ruff check .
pytest -q
```

## Configure

Edit [`config.yml`](config.yml) to change the lookback, threshold, queries, taxonomy, and
report size. Copy `.env.example` to `.env` only for local use; never commit credentials.

Record volume is controlled by three separate keys, so the daily Issue stays readable
without discarding the corpus behind it:

| Key | Effect |
|---|---|
| `max_items_per_source` | Upper bound on records fetched from each source |
| `report_limit` | Records scored, snapshotted, and published to the dashboard |
| `issue_item_limit` | Records written into the daily Issue body |

Every run records its own drop-off (`fetched → deduplicated → qualified → published`) in
the snapshot and at the top of the Issue, so the gap between what a source returned and
what was published is always auditable.

GitHub search is rate-limited to 10 requests per minute without a token and 30 with one,
so pagination is bounded by `sources.github.max_requests` and spaced by
`request_delay_seconds`. Both default by whether `GITHUB_TOKEN` is present; raising
`max_items_per_source` well beyond the defaults on a tokenless run risks a 403.

Trend comparisons only run between snapshots collected under the same `report_limit`.
Changing the cap lifts every count at once, and reporting that as domain momentum would
present a change in collection policy as a change in the field.

The `watchlist` block pins named artifacts, matched on title and source id by word
boundary. A hit is routed to the top and labelled with a one-line note; it never changes
a score, so the ranking stays explainable.

Optional repository secrets:

```text
SEMANTIC_SCHOLAR_API_KEY
OPENALEX_API_KEY
BRAVE_API_KEY
```

Daily snapshot persistence also requires a private GitHub App with **Contents: read and
write** access to this repository. Add the App to the `main-protect` ruleset's bypass
list with **Always allow**, then configure:

```text
Repository variable: RADAR_APP_ID
Actions secret:      RADAR_APP_PRIVATE_KEY
```

The built-in `GITHUB_TOKEN` continues to authenticate discovery and Issue publishing;
the snapshot push uses the App token so its `main` push can trigger deployment.

## Daily publishing

`.github/workflows/daily-radar.yml` targets 06:15 and 12:15 UTC and can also be
started manually. GitHub scheduled events are best-effort and may start late under
Actions load, so the two targets provide a same-day retry. Every scheduled run records
its target, actual runner start, and latency in the job summary, with a warning after
30 minutes. The workflow:

1. collects evidence plus public Hacker News attention and renders with read-only
   repository permission;
2. validates and uses the snapshot-writer App to persist one snapshot on `main`;
3. creates or updates the date-filtered daily Issue;
4. lets that App-authenticated push trigger the standalone Pages workflow;
5. prevents duplicate snapshots and daily Issues on reruns.

The workflow needs repository Issues enabled. The labels `daily-radar` and `automated`
must exist; they are created during initial repository setup.

## Provenance and limitations

- Every entry links to its discovered primary or structured record.
- Connector summaries quote upstream abstracts, cards, descriptions, or release
  notes; a missing upstream description stays empty rather than being synthesized.
- Evidence records persist retrieval time, parser version, and a SHA-256 raw-payload
  fingerprint while omitting the raw response itself from public snapshots.
- Optional-source failures are visible.
- Persisted snapshots omit raw API payloads and credentials.
- Public attention feeds are displayed separately and never contribute to quality scores.
- Reports can contain false positives; always inspect the source.
- A repository update is not necessarily a new release.
- Publication dates differ across preprints, code, datasets, and formal publications.
- This system does not automatically create ANX-Bench events or research claims.

## Public observation feeds

The daily pipeline collects public Hacker News attention directly through its anonymous
Algolia endpoint before persisting the snapshot. It preserves the original
`benchmark-social-signal:hacker-news:*` observation IDs so historical records remain
continuous after the collector migration. A failed collection is reported in source
health and carries forward the last healthy observations instead of publishing a false
empty result.

Additional read-only feed producers can follow
[`docs/public-observation-feed.schema.json`](docs/public-observation-feed.schema.json).
The radar validates feed versions and HTTP(S) links, records collection/producer health
separately from evidence ingest health, and stamps publication, producer discovery, and
first radar observation independently. The dashboard renders source text as plain text
and labels these records as unranked attention rather than evidence. No cookies,
authenticated sessions, private posts, LinkedIn, or X scraping are used.

## License

MIT
