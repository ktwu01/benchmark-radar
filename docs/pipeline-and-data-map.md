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
   After the run, `benchmark-radar share` adds a `share` block to that day's
   snapshot. The block holds the benchmarks the daily briefing covers (or the
   radar-score top 3 when the day has no model briefing) and who made them.
   `scripts/render_share_images.py` renders the day's images from that block
   only, and the daily workflow pushes them to `daily/YYYY-MM-DD/` on the
   `cards` branch of `ktwu01/benchmark-radar-cards`, which GitHub Pages serves
   at `https://cards.benchmark-radar.org/daily/YYYY-MM-DD/`. To change a card,
   fix the snapshot or the lookup, not the image.
2. **Benchmark registry snapshots.** `data/leaderboard_snapshots.yml` registers
   immutable crawl inputs under `data/leaderboard_snapshots/`. The reviewed
   join rules are `data/catalog/identity.yml` and
   `data/catalog/llm_stats_identity_overrides.yml`. Cited release and first-score
   dates missing from the crawls live in `data/catalog/benchmark_dates.yml`,
   keyed by exact source record. Numeric first-score evidence only verifies a
   date; it does not supply a highest score or merge records. Benchmark authors
   live in `data/catalog/benchmark_authors.yml`, also keyed by exact source
   record. They are read from the arXiv metadata of the record's own
   introducing paper by `scripts/fetch_arxiv_authors.py`; rerun the script
   rather than editing names. Benchmark institutions live in
   `data/catalog/benchmark_institutions.yml`, keyed the same way. They are the
   institutions OpenAlex links to that paper's authorships, read by
   `scripts/fetch_openalex_institutions.py`, and never replace `publisher`.
   Other JSONL and
   validation files under `data/catalog/` are normalization products; do not hand-edit or
   treat them as a separate corpus, even when Git currently tracks a generated
   copy.
3. **Model reports.** `data/model_cards.yml` registers cited model reports
   and every benchmark they mention. `data/benchmark_scores.yml` is its matched,
   protocol-aware score archive, and every score must cite a registry document.
   Normalize these records, scores and citations into the same catalog contract
   as every other source. Document type and protocol describe the evidence;
   they do not establish a preferred corpus or a source ranking.

4. **Release signals.** The Latest releases ranking (`attention-affiliation-v2`)
   reads two committed files beyond the snapshots, both keyed by exact
   identifier and written only by `scripts/fetch_release_signals.py`. The
   `refresh-release-signals` job in `.github/workflows/daily-radar.yml` runs
   it after each daily snapshot and may change only these two files. Rerun
   the script rather than editing them by hand.
   - `data/release_institutions.yml`: institutions behind each arXiv paper in
     the widest release window, keyed by arXiv id. `basis` says where they
     came from: `openalex_linked_institutions` (normalized names, counted in
     the institution ranking) or `arxiv_html_affiliations` (the paper's own
     printed names, shown "as written in the paper" and never counted). A
     paper is retried every three days until OpenAlex has it.
   - `data/release_repos.yml`: each GitHub repository the cohort is ranked
     on, keyed by `owner/name`: size, stars on the check date, archived flag,
     creation and last-push dates (search API, six per call), plus
     `placeholder` (README-only root, listed only for repositories up to
     2 MB; a README that links a dataset host such as Hugging Face datasets,
     Google Drive or Zenodo is not a placeholder, recorded as `data_link`) and `unavailable` (404 on the repository endpoint, which follows
     renames). A placeholder, archived or unavailable repository holds its
     release back: listed, unranked, with the reason. Stars and size never
     do. Placeholders and unknowns are rechecked daily, others weekly. A
     missing row or a null field means unknown, never a hold-back.
     `scripts/release_repo_findings.py` reproduces the cohort statistics from
     these files without the network.

   `snapshots.rebuild_dashboard` reads both through
   `release_signals.load_release_signals`, then `affiliation_rank` counts
   institutions across these papers and `data/catalog/benchmark_institutions.yml`.

Adding a document to either report file is one procedure, written up in
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
   `site/data/radar-window-{30,60,90}d.json`,
   `site/data/models.json`, `site/feed.xml`, the daily brief blog under
   `site/blog/`, and `site/blog/feed.xml`. The classifier currently uses
   the deterministic null extractor in CI; it makes no external model call.
   `radar.json` and its split files come from `snapshots.rebuild_dashboard`,
   which also reads the release signals above. `benchmark-radar rebuild` runs
   that same step on its own when only `radar.json` needs refreshing.
3. `benchmark-radar build-data-release` validates the local corpus through
   `QueryService` and writes `site/data/cli/manifest.json` plus the checksummed
   `site/data/cli/benchmark-radar-data.zip`. The manifest is published on Pages;
   the complete archive is uploaded to the rolling `cli-data` GitHub Release.
4. `benchmark-radar export` writes the full-catalog documentation ranking as JSON,
   CSV, Markdown, and badge files under `site/data/`. It does not write
   `radar.json`; after changing the release signals or the leaderboard code,
   rebuild with `classify` or `rebuild` before reading `radar.json`. Pages then runs
   `scripts/generate_og_image.py` and `scripts/build_logo_registry.py` before
   tests and deployment.
5. The Pages build then runs `scripts/render_share_images.py --catalog` on the
   validated `site/data/benchmark-index.json`, writing one `<slug>.png` per
   catalog benchmark to `site/cards/`. They deploy with the site at
   `https://benchmark-radar.org/cards/<slug>.png`, where each benchmark's
   Share button (`site/assets/share-card.js`) and its static page's `og:image`
   load them. The job `publish-benchmark-cards` archives the same files to the
   `cards` branch of `ktwu01/benchmark-radar-cards`. To change a card, fix the
   catalog record, not the image.

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
- Canonical citation: <https://arxiv.org/abs/2609.11115>. see repo main/CITATION.cff.
  Cite only this. The repository keeps no copy of published PDFs.

Before changing report claims, run the clean-checkout CI
sequence in `AGENTS.md` and recompute claims from its outputs. Rebuild the PDF
with `make` in `docs/technical-report/latex/`, inspect the rendered PDF, and
commit that exact file. The PDF is a dated interpretation, not a data source.
