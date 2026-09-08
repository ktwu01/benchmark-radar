# Repository Instructions

Read `principle.md` before changing a benchmark-facing surface. Its full-corpus
coverage rule applies to charts, search, tables, counts, and exports: start from
1,259+ benchmark records across 4+ sources, and investigate any unexplained
reduction to a few dozen. Missing measurements must not remove corpus records.
Benchmark Frontier and its linked score ranking explicitly exclude records
without numeric reported scores, as specified in `principle.md`.

## Glob rule: showcase and UI communication

Applies to `README*`, `docs/**`, `.github/ISSUE_TEMPLATE/**`, `site/**`, and
any report, launch note, TLDR, screenshot, GIF, demo, dashboard, or UI surface.

- Treat what is shown as part of the work. What was done and what is displayed
  are both important; in many communication surfaces, what is displayed is more
  important because it is the receiver's entry point.
- Start from the receiver's perspective, not the implementer's. Ask what the
  reader most wants to know, what will help them decide quickly, and what is
  most worth remembering or sharing.
- Do not let engineering effort bury the message. Data work and implementation
  details often take most of the time, but reports and TLDRs should foreground
  the result, implication, and decision-useful signal before the process.
- Prefer strong information hierarchy, plain language, concrete examples,
  screenshots, short GIFs, and compact summaries that make the work easy to
  scan, review, forward, or explain upward.

### Example: simplify badge copy and keep its style

Before:

```html
<p align="center">
  <a href="https://koutian.is-a.dev/benchmark-radar/"><img alt="Benchmark records collected" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://koutian.is-a.dev/benchmark-radar/data/radar.json"><img alt="Download dataset" src="https://img.shields.io/badge/Dataset-download%20JSON-2f81f7?style=for-the-badge&amp;logo=json&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/X-%40ktwu01-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-Koutian%20Wu-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-Koutian%20Wu-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>
```

After:

```html
<p align="center">
  <a href="https://koutian.is-a.dev/benchmark-radar/"><img alt="Benchmark records collected" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://koutian.is-a.dev/benchmark-radar/data/radar.json"><img alt="Download dataset" src="https://img.shields.io/badge/Dataset-download%20JSON-2f81f7?style=for-the-badge&amp;logo=json&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>
```

The after example removes the handle or name from three badge labels. It keeps
the five-badge layout, badge styles, logos, colors, and profile URLs.

## Glob rule: Benchmark Radar audience

Applies to `README*`, `docs/**`, `.github/ISSUE_TEMPLATE/**`, `site/**`,
`assets/**`, and benchmark-facing generated artifacts.

- Assume two audiences at once: a benchmark freshman who may be 16 and should
  understand the point without technical jargon, and a benchmark expert who
  expects credible signal, precise framing, and non-obvious insight.
- Make the first screen or first paragraph an efficient entry point: what this
  shows, why it matters, what is surprising, and where to click next.
- Optimize for spread without sacrificing rigor. The artifact should be easy to
  share, screenshot, and quote, while still looking professional to people who
  know benchmarks well.
- Show the insight before the pipeline. Crawling, normalization, scoring, and
  data-cleaning details matter, but they should support the takeaway instead of
  becoming the takeaway.
- Use bilingual guidance when it helps contributors or readers provide better
  signal. Avoid jargon-heavy summaries that only say what changed; explain why
  the change matters to someone reading, reviewing, or sharing the project.

## Branches and pull requests

- Keep work on the task branch. Update local or remote `main`, or merge a pull
  request, only when the user explicitly requests it. Creating or updating a PR
  does not authorize a merge.
- Do not squash-merge pull requests.
- Merge pull requests with a merge commit so Git preserves branch ancestry and recognizes the branch as merged.

## Pipeline and data map

Do not reconstruct the system from a report, the deployed site, or whatever
generated files happen to be present in a long-lived checkout. Start with the
sources below, run the generators in order, and measure the rebuilt outputs.

### Source inputs and the shared catalog

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

### Generator order and outputs

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

### Which artifact answers which question

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

### Technical report and deposit files

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
sequence below and recompute claims from its outputs. Rebuild the PDF with `make`
in `docs/technical-report/latex/`, inspect the rendered PDF, and commit that
exact file. A deposit copies the reviewed PDF to a versioned name under
`output/pdf/`. The PDF is a dated interpretation, not a data source.

## Query surfaces

- `benchmark_radar.query.QueryService` is the single source of truth for local
  benchmark search, detail lookup, recent evidence, and data health.
- CLI and HTTP query surfaces must call that service and return the same stable
  JSON contract. Do not add interface-specific ranking, filtering, identity
  merging, or silent network fallback.
- Query responses must state their local data provenance and retrieval mode.
  Missing or malformed generated artifacts fail visibly with machine-readable
  errors; they must not be replaced with guessed metadata.
- Lexical search is a high-recall candidate retriever for agents, not a final
  suitability judge. Any shared query token may produce a candidate. BM25F is
  the primary retrieval score. Exact/prefix/token-sequence name matches and
  non-name contiguous phrases are bounded, query-IDF-scaled boosts; lexical
  coverage is only a tie-breaker and explanation because BM25F already rewards
  additional matched terms. Every result must expose matched and missing tokens,
  fields, coverage, `retrieval_score`, `idf_coverage`, and score components.
  `full_matches_found` means at least one candidate covers every query token,
  `partial_candidates_only` preserves weaker evidence without claiming an answer,
  and zero token overlap uses `no_lexical_candidates`. Semantic acceptance belongs
  to the consuming Agent/Skill, which may issue focused query variants and inspect
  `show` details before making a suitability claim.
- Catalog records and daily discovery observations describe different things.
  Label a discovery observation as evidence of a mention or release, and retain
  the benchmark record it refers to. Source membership must not establish a
  preferred trust tier or change the shared query ranking. A search result is a candidate, not a suitability claim. Agent query
  expansion and final relevance judgment happen in the public Skill as a small
  number of short variants and never change service-side ranking per interface.
- Installed clients read the active version under the cross-platform
  `.benchmark-radar` user data directory. `init` and `sync` are the only
  consumer update paths; search must stay offline and must not hide an update
  failure behind stale data.
- Pages publishes the small CLI manifest, while the Pages workflow uploads the
  complete checksummed bundle to the rolling `cli-data` GitHub Release. Sync
  validates it before atomically switching state and removes old versions only
  after the new version is active.
- The public consumer Skill lives at `skills/benchmark-radar/SKILL.md`. Keep it
  purpose-neutral and limited to routing user intent through consumer CLI
  commands; do not make maintainer build commands part of its normal workflow.
- Search evaluation is a manual review tool, not a CI gate while relevance labels
  are LLM-assisted and only sparsely human-reviewed. Ranking changes should run
  `scripts/evaluate_search.py` locally and inspect the qualitative judge cases.
  Unlisted records are unjudged, not negative; do not report precision or NDCG
  until result pools are completely labelled. A source refresh that changes a
  judgement requires record review, not a mechanical fixture update.

## Before opening a pull request

- Run the full CI sequence locally and get it passing before opening a PR. Do
  not open one against a red local run.
- Run it against a clean checkout (`git worktree add --detach <tmp> <branch>`),
  not your working copy. Run `git submodule update --init --recursive` in that
  worktree before checks. Generated files such as `site/data/radar.json`,
  `site/data/benchmark-index.json` and `site/data/benchmarks/` are gitignored
  and absent on a fresh CI runner, so a working copy that happens to have them
  on disk passes tests that CI fails.
- The sequence is the one in `.github/workflows/ci.yml`, in order:

      ruff check .
      ruff format --check .
      benchmark-radar normalize-catalog
      benchmark-radar classify
      benchmark-radar build-data-release
      pytest -q

- All six must pass. `ruff format --check` runs before everything else, so a
  formatting slip fails the run before a single test executes. Both generators
  run before `pytest` and in that order: `classify` reads the shard directory
  `normalize-catalog` writes, while `build-data-release` packages the validated
  index, shards, and snapshots that installed clients consume.
