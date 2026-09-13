# Pipeline and data map

Do not reconstruct the system from a report, the deployed site, or whatever
generated files happen to be present in a long-lived checkout. Start with the
sources below, run the generators in order, and measure the rebuilt outputs.

## Source inputs and the shared catalog

1. **Daily discovery corpus.** `config.yml` defines the collection and scoring
   configuration; connectors live under `src/benchmark_radar/`. A daily
   `benchmark-radar` run writes its durable evidence to
   `data/snapshots/YYYY-MM-DD.json`. Those dated snapshots are the source of
   truth for cumulative observations, artifacts, source health, and history.
2. **Benchmark registry snapshots.** `data/leaderboard_snapshots.yml` registers
   immutable crawl inputs under `data/leaderboard_snapshots/`. The reviewed
   join rules are `data/catalog/identity.yml` and
   `data/catalog/llm_stats_identity_overrides.yml`. Cited release and first-score
   dates missing from the crawls live in `data/catalog/benchmark_dates.yml`,
   keyed by exact source record. Numeric first-score evidence only verifies a
   date; it does not supply a highest score or merge records. Other JSONL and
   validation files under `data/catalog/` are normalization products; do not hand-edit or
   treat them as a separate corpus, even when Git currently tracks a generated
   copy.
3. **Model reports.** `data/model_cards.yml` registers cited model reports
   and every benchmark they mention. `data/benchmark_scores.yml` is its matched,
   protocol-aware score archive, and every score must cite a registry document.
   Normalize these records, scores and citations into the same catalog contract
   as every other source. Document type and protocol describe the evidence;
   they do not establish a preferred corpus or a source ranking.

Adding a document to either file is one procedure, written up in
[`docs/sop-add-model-cards.md`](sop-add-model-cards.md).

## Generator order and outputs

Run these from the repository root, in this order:

1. `benchmark-radar normalize-catalog` reads the crawl registry, raw crawl
   files, model reports, score archives, and reviewed identity rules. It writes
   normalized intermediates under
   `data/catalog/`, then the generated search index
   `site/data/benchmark-index.json` and detail shards under
   `site/data/benchmarks/`.
2. `benchmark-radar classify` reads the dated snapshots plus the shared
   catalog shards and model-report YAML files. It regenerates
   `data/kw_bench_classifications.jsonl`, `site/data/radar.json`,
   `site/data/radar-bootstrap.json`, `site/data/radar-trends.json`,
   `site/data/models.json`, `site/feed.xml`, the daily brief blog under
   `site/blog/`, and `site/blog/feed.xml`. The classifier currently uses
   the deterministic null extractor in CI; it makes no external model call.
3. `benchmark-radar build-data-release` validates the local corpus through
   `QueryService` and writes `site/data/cli/manifest.json` plus the checksummed
   `site/data/cli/benchmark-radar-data.zip`. The manifest is published on Pages;
   the complete archive is uploaded to the rolling `cli-data` GitHub Release.
4. `benchmark-radar export` writes the full-catalog documentation ranking as JSON,
   CSV, Markdown, and badge files under `site/data/`. Pages then runs
   `scripts/generate_og_image.py` and `scripts/build_logo_registry.py` before
   tests and deployment.

Most `site/data/` files and `data/kw_bench_classifications.jsonl` are derived
and gitignored. Their absence in a fresh checkout is normal. Never patch them
to fix a source-data problem; update the relevant snapshot, crawl input,
identity rule, or report/score YAML and regenerate. Never report counts from a stale
working tree: rebuild first and read the JSON that was just produced. A derived
file that is tracked, such as `site/data/models.json` or current normalization
outputs under `data/catalog/`, is still not an independent source of truth.

## Which artifact answers which question

- `site/data/radar.json`: cumulative daily-discovery corpus, source health,
  findings, and report-specific historical analyses. It is not a second
  population to append to the benchmark catalog.
- `site/data/benchmark-index.json`: the complete benchmark catalog and common document
  registry, one row per source record across all sources; reviewed identities do not silently collapse the
  underlying evidence.
- `site/data/benchmarks/<slug>.json`: benchmark detail, provenance, identity,
  score series, observations and cited documents through one shared contract.
- `site/data/models.json`: one model registry assembled from the catalog, with
  named provenance sources for each model.
- `data/snapshots/*.json`: committed historical evidence used for local radar
  search and for rebuilding `radar.json`.
- `site/blog/`: daily brief blog pages and full archive built from committed
  snapshots, with an independent feed at `site/blog/feed.xml`.
- `site/data/cli/`: distributable copy of the index, shards, and snapshots for
  installed offline clients.

The web, CLI and exported catalog use the exact same benchmark IDs from the
freshly generated `benchmark-index.json`. Model-report records are already in
that index, including benchmarks with no scores or citations. Never add
`radar.json` score tracks to that total or fall back to a smaller report registry
when the catalog fails to load. Compute records and sources from rebuilt outputs;
1,259+ records across 4+ sources is the minimum scale to investigate against.

`normalize-catalog` is the current command. `normalize-external` remains an
alias for existing maintainer scripts. Implementation modules use `catalog_*`
and shared data lives under `data/catalog/`; original fields in immutable crawl
inputs retain their source spelling.

## Technical report and deposit files

The paper lives in `ktwu01/benchmark-radar-paper`, mounted as a Git submodule at
`docs/technical-report/latex`. Initialize it with
`git submodule update --init --recursive`, including in clean worktrees. Keep
paper-only edits and PRs in the paper repository by default. Update the parent
Benchmark Radar repository, including its submodule pointer, only when the user
explicitly requests it. For a requested pointer update, push the reviewed paper
commit first, then commit the pointer here. Overleaf sync changes the paper
repository, not this pinned pointer.

- Report source: `docs/technical-report/latex/main.tex`. This is the single
  source of truth for the report. Edit it directly. Nothing generates it from
  Python, Markdown, or the running site.
- Built PDF: `docs/technical-report/latex/main.pdf`, tracked so the report reads
  on GitHub in the paper repository. Rebuild and commit it with any change to
  `main.tex`.
- The four PDF figures have native TikZ sources under `latex/figures/`.
  `make` builds them from the dated `latex/figure-data.tex` export. Refresh that
  export only after auditing a clean corpus rebuild; review and commit the
  figure PDFs and manuscript PDF together. The exporter writes no report prose.
- Build instructions and audited inputs: `docs/technical-report/README.md`
- Zenodo metadata: `docs/technical-report/zenodo-metadata.json`. It describes
  the frozen v0.9.0 deposit, so its version and counts are a record of that
  deposit rather than drift. A new deposit rewrites it in the same change.
- Frozen deposit: `output/pdf/benchmark-radar-technical-report-v0.9.0.pdf`. This
  is the artifact behind DOI 10.5281/zenodo.22167102. Nothing writes to that
  path; leave it byte-for-byte unchanged.

Before changing report claims or Zenodo metadata, run the clean-checkout CI
sequence in `AGENTS.md` and recompute claims from its outputs. Rebuild the PDF
with `make` in `docs/technical-report/latex/`, inspect the rendered PDF, and
commit that exact file. A deposit copies the reviewed PDF to a versioned name
under `output/pdf/`. The PDF is a dated interpretation, not a data source.
