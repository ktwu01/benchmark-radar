# Shared benchmark catalog

Use this contract for benchmark charts, search, detail pages, counts and exports.
The population includes 1,259+ source records across Model reports, OpenCompass
Hub, Artificial Analysis and LLM Stats. Read the current count from a fresh
build. Model-report records already belong to the index; adding the report
score tracks again double counts them.

## Inputs and build order

`data/leaderboard_snapshots.yml` registers immutable source snapshots.
`data/model_cards.yml` registers report documents and their benchmark references;
`data/benchmark_scores.yml` supplies numeric observations cited to those reports.
Adapters parse these inputs into the same record contract.

The frozen Claire Library union in `data/imports/claire_library/` supplies
additional benchmark metadata and categories, with every original input field
retained in shard extensions. See [the merge report](CLAIRE-LIBRARY-MERGE.md)
for the input census, exact identity rules and field mapping.

Reviewed identity links, source corrections and cited dates live in
`data/catalog/identity.yml`, `llm_stats_identity_overrides.yml` and
`benchmark_dates.yml`. Other files in that directory are generated products.
Never repair a count by editing an index, shard or normalization output.

Run, in order:

```sh
benchmark-radar normalize-catalog
benchmark-radar classify
benchmark-radar build-data-release
benchmark-radar export
```

The old `normalize-external` command remains an alias. Source-specific module
names describe their job, such as `catalog_opencompass` and `catalog_reports`.
Original field names inside immutable snapshots remain unchanged.

## Records, scores and documents

`site/data/benchmark-index.json` contains every source benchmark, including
records without numeric scores, documents or dates. It also contains the common
`document_registry` used by the documentation ranking and exports.

Each index row has a stable `slug`, source `key`, `source`, name, aliases,
identity metadata, `score_summary` and `evidence_summary`. Source names carry
provenance. Consumers apply the same field checks regardless of source.

`site/data/benchmarks/<slug>.json` carries the full record, reviewed identity
links and `scores_by_source`. Each score has an observation ID, source model ID,
value, units via its series, date and date precision, and a cited document ID.
Available protocol and instrument fields remain attached to the observation.
A missing protocol stays unknown; two unknown protocols do not establish an
identical evaluation setup.

Documents use one shape: identity, source, URL, document type and the recorded
title, publication date and organization. Model cards and registry pages use
the same citation edges. Type records what the document is; it grants no
priority. A document counts once per source benchmark, even if it contains
multiple scores or repeated mentions.

The document registry includes all benchmark IDs and the reverse links from
each document to the benchmarks it records. JSON and CSV exports preserve the
full ID set. A top-N Markdown table declares its truncation.

## Identities and measurements

Keep one benchmark record per `(source, source_benchmark_id)`. Preserve existing
report slugs so shared links continue to work. A reviewed equivalent or variant
link connects records; it does not collapse them, transfer model counts, average
scores or declare protocols interchangeable.

Count scored models by the source's model ID. Model reports identify scored
models by their exact organization and model name. Repeated scores, protocols
and documents for the same model contribute one model. Missing model IDs make
the distinct model count unknown; a display name is not a replacement source ID.

`model_count`, `numeric_count` and `document_count` answer different questions.
Do not add or substitute them. The source snapshots contain 577 distinct scored
model IDs for both Artificial Analysis HLE and SciCode, and 492 for CritPt.
These observations must reach the default Frontier height without borrowing
report counts or merging similarly named benchmarks.

`site/data/models.json` indexes model identities and their named provenance
sources from the shared catalog. Its display-name grouping supports navigation;
benchmark heights retain the exact source model IDs and evaluated configurations.

## Scores and dates

A declared maximum alone does not establish a percentage scale. Some source
observations exceed their declared maximum. Carry that contradiction as evidence.
Only verified common scales enter the Frontier Pareto calculation. Scored
records on other scales retain inspectable marks with their known dimensions.

Preserve the distinction between benchmark release, score publication, model
release and crawl time. Prefer benchmark release, then the first actual dated
numeric score. A model-release proxy stays labelled as such. Crawl timestamps
and citation-only mentions cannot manufacture a benchmark date.

Frontier and its linked score ranking require numeric scores and apply the
2024+ timeline and user filters described in [principle.md](../../principle.md).
General catalog search and exports retain unscored records. Reconcile all
exclusions against the complete input population.

## Consumer and UI checks

Website search, local `QueryService` and the offline data release use the same
index and shard IDs. No source-specific ranking bonus or report-only fallback
is allowed. A failed catalog load must remain visible.

Place legends below their figure. Collect source counts, coverage, date and
scale qualifications, and method text in one collapsed information note there.
Check keyboard and touch operation and inspect both desktop and mobile layouts.
Compare actual rendered mark IDs with the filtered catalog, and verify the
577 / 577 / 492 model-count cases after rebuilding.

`AUDIT.md` preserves the dated raw-input audit. Older display plans record the
initial implementation; this contract and `principle.md` supersede their source
hierarchy and population rules.
