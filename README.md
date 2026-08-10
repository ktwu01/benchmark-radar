# Benchmark Radar

**Which AI benchmarks do frontier labs actually report when they ship a model?**

[![model cards tracked](https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Fleaderboard-badge.json)](https://koutian.is-a.dev/benchmark-radar/?view=leaderboard)

Not which benchmarks exist, and not which are cited most in papers: which ones a
vendor chooses to put in front of readers in a model card. That is a question about
what the field currently treats as the standard set, and it is answered here by
reading the documents rather than by asking anyone's opinion.

| Rank | Benchmark | Domain | Model cards | Organizations |
|---:|---|---|---:|---:|
| 1 | [GPQA Diamond](https://arxiv.org/abs/2311.12022) | science | 23 | 10 |
| 2 | [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/) | coding_agent | 18 | 8 |
| 3 | [LiveCodeBench](https://livecodebench.github.io/) | coding | 15 | 7 |
| 4 | [Humanity's Last Exam](https://lastexam.ai/) | reasoning | 14 | 8 |
| 5 | [AIME](https://maa.org/maa-invitational-competitions/) | math | 14 | 7 |
| 6 | [Terminal-Bench](https://www.tbench.ai/) | agent | 13 | 8 |
| 7 | [BrowseComp](https://openai.com/index/browsecomp/) | agent | 11 | 6 |
| 8 | [MMLU-Pro](https://github.com/TIGER-AI-Lab/MMLU-Pro) | knowledge | 11 | 6 |

Across 30 curated model cards, system cards, and technical reports from 10
organizations, tracking 79 benchmarks.
**[See the full ranking](https://ktwu01.github.io/benchmark-radar/?view=leaderboard)**
or read [how it is counted](#model-card-adoption-rank).

This measures vendor attention, not benchmark quality. A saturated or contaminated
benchmark can rank highly precisely because reporting it is conventional, so every row
carries its own caveat.

Take it with you: [`leaderboard.json`][json] · [`leaderboard.csv`][csv] ·
[`leaderboard.md`][md] (paste-ready table). Every artifact restates the caveat, so the
ranking cannot be separated from what it means.

The coverage badge above reads the same registry, so it reports the current denominator
rather than whatever it was when someone copied it:

```markdown
[![model cards tracked](https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Fleaderboard-badge.json)](https://koutian.is-a.dev/benchmark-radar/?view=leaderboard)
```

It deliberately shows coverage and not a rank: a badge is a single number read without
context, and "GPQA Diamond is #1" seen that way is the quality claim this ranking does
not make.

[json]: https://ktwu01.github.io/benchmark-radar/data/leaderboard.json
[csv]: https://ktwu01.github.io/benchmark-radar/data/leaderboard.csv
[md]: https://ktwu01.github.io/benchmark-radar/data/leaderboard.md

## The daily radar

The ranking above is the curated half of this project. The other half runs every day:
GitHub Actions queries primary or structured sources for newly released benchmarks,
evaluation methods, datasets, and data-quality work, deduplicates records, classifies
them with a transparent taxonomy, ranks them using explainable signals, and publishes a
[cumulative dashboard](https://ktwu01.github.io/benchmark-radar/) with a
[daily RSS feed](https://ktwu01.github.io/benchmark-radar/feed.xml). The dashboard and RSS
feed are the reading and subscription surfaces; the daily GitHub Issue that once served as a
secondary discussion channel was retired (issue #37), and the day's social posting material
ships as `out/social.md` in each run's evidence artifact. It is inspired by
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
| First-party feeds | No | Curated official lab and engineering announcements |
| Semantic Scholar | Optional `SEMANTIC_SCHOLAR_API_KEY` | Structured scholarly discovery |
| OpenAlex | Free `OPENALEX_API_KEY` | Scholarly metadata enrichment |
| Brave Search | `BRAVE_API_KEY` | Web and lab-blog discovery |
| Hacker News | No | Public attention only; never quality-scored |

The report remains useful without optional secrets. Missing optional sources are shown
as warnings in the source-health table instead of being silently ignored.
In GitHub Actions, an optional source that fails for three consecutive runs also emits a
workflow warning; `radar.optional_source_failure_warning_runs` controls that threshold.

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

## Model Card Adoption Rank

A separate, curated view answering a different question: which benchmarks do frontier
vendors actually report when they ship a model? It is published at `?view=leaderboard`
on the dashboard and built from
[`data/model_cards.yml`](data/model_cards.yml), a hand-maintained list of model cards,
system cards, and technical reports with the benchmarks each one reports.

The counted unit is the **document, not the result row**. A card reporting AIME at
pass@1, at consensus@64, and with a Python tool contributes exactly one adoption, the
same as a card reporting it once, so a long appendix cannot outvote a different vendor.
Two counts are published side by side and neither is folded into a single score:
`card_count` is the headline, and `organization_count` breaks ties, because the same
count from six vendors is a shared standard while from one vendor it is a house style.

This measures vendor attention, not benchmark quality. A saturated or contaminated
benchmark can rank highly precisely because reporting it is conventional, so every row
carries its own caveat and that disclaimer is published in `radar.json` rather than only
stated in the browser. Benchmarks tracked but reported by no card are kept and ranked
last: "in the registry, adopted by nobody" is itself a finding.

Scores are deliberately out of scope. Vendors differ on prompt, scaffold, tool access,
reasoning budget, pass@k, and evaluator, so two reported numbers for the same benchmark
are usually not comparable. A mention survives all of those caveats, which is why it is
the unit this ranking can honestly publish today.

To extend it, add a benchmark to the `benchmarks:` block and a document to
`model_cards:`, then run `benchmark-radar rebuild`. A card referencing an unknown
benchmark id fails the build rather than silently creating a phantom entry.
Adding a model card is the most useful contribution this project can receive, and
[CONTRIBUTING.md](CONTRIBUTING.md) walks through it.

### Citing the ranking

The ranking is published as standalone files, so quoting it does not mean parsing the
multi-megabyte dashboard bundle:

| Artifact | URL | Use |
|---|---|---|
| JSON | [`data/leaderboard.json`][json] | The ranking and its card-level edges, without the daily corpus |
| CSV | [`data/leaderboard.csv`][csv] | One row per benchmark, for a spreadsheet or dataframe |
| Markdown | [`data/leaderboard.md`][md] | A paste-ready table for a README or post |
| Badge | [`data/leaderboard-badge.json`][badge] | A Shields endpoint that tracks registry coverage |

Generate them locally with:

```bash
benchmark-radar export
```

Each artifact restates what the ranking measures and the denominator it was counted
against. These files are built to travel, and a ranking separated from its caveat reads
as a quality ordering, which is the misreading the registry exists to prevent.

The badge reports coverage rather than a top rank, for the same reason: a badge is a
single number seen with no context, and "GPQA Diamond is #1" shown that way is a claim
this ranking does not make.

```markdown
![Model cards tracked](https://img.shields.io/endpoint?url=https://ktwu01.github.io/benchmark-radar/data/leaderboard-badge.json)
```

[badge]: https://ktwu01.github.io/benchmark-radar/data/leaderboard-badge.json

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
- `site/data/leaderboard.{json,csv,md}` and `leaderboard-badge.json`: the standalone
  adoption-rank exports, written by `benchmark-radar export`

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

The dashboard exposes one filterable Today list, inline multi-record expansion, the
Model Card Adoption Rank leaderboard, Trends, and a keyboard-accessible Trend Map. Selecting a map node carries its exact topic,
source, organization, or artifact into the Today filters. Trend comparisons require
both the same report limit and the same connector-coverage signature; incomplete days
remain visible and are explicitly annotated.

Run checks:

```bash
ruff check .
pytest -q
```

## Configure

Edit [`config.yml`](config.yml) to change the lookback, recommendation threshold, queries,
taxonomy, and report size. Copy `.env.example` to `.env` only for local use; never commit
credentials.

Record volume and presentation are controlled separately, so the daily report stays
readable without discarding eligible records from the corpus:

| Key | Effect |
|---|---|
| `max_items_per_source` | Upper bound on records fetched from each source |
| `issue_item_limit` | Records written into the daily report body |
| `minimum_score` | Adds the **Recommended** badge; never controls inclusion |

Every taxonomy-matching, non-suppressed record is retained. Explicitly watchlisted records
are retained even without a taxonomy match. Every run records its drop-off
(`fetched → deduplicated → eligible → retained`) plus the recommended/not-recommended split
in the snapshot and at the top of the report.

GitHub search is rate-limited to 10 requests per minute without a token and 30 with one,
so pagination is bounded by `sources.github.max_requests` and spaced by
`request_delay_seconds`. Both default by whether `GITHUB_TOKEN` is present; raising
`max_items_per_source` well beyond the defaults on a tokenless run risks a 403.

Trend comparisons do not cross the transition from historically capped snapshots to the
uncapped eligible corpus, and only compare snapshots classified by the same taxonomy.
Editing the taxonomy re-tags the whole corpus; reporting that as domain momentum would
present a change in measurement as a change in the field.

Each snapshot records a `taxonomy_version`, a fingerprint derived from the taxonomy's own
content rather than a hand-bumped number, so editing any keyword changes it and forgetting
to bump it is not possible. `benchmark-radar rescore` stamps every record it evaluates and
marks the ones whose categories actually moved:

```json
"reclassified": {"from": ["benchmark"], "to": ["benchmark", "agentic"],
                 "taxonomy_version": "sha256:5ee3bd8146ce"}
```

This makes a reclassification a third kind of event beside `released` and `updated`. When
the `agentic` count went from 3 to 78, that was a rules correction rather than 75 new
agent benchmarks, and nothing in the data distinguished the two. The marker describes only
the most recent pass: re-running `rescore` with settled rules clears it, because a record
reclassified weeks ago is not evidence about a trend today. `event_kind` is never rewritten
by a rescore, since it records what the source announced, not what the radar did to its own
records.

The `watchlist` block pins named artifacts, matched on title and source id by word
boundary. A hit is routed to the top and labelled with a one-line note; it never changes
a score, so the ranking stays explainable.

Optional repository secrets:

```text
SEMANTIC_SCHOLAR_API_KEY
OPENALEX_API_KEY
BRAVE_API_KEY
```

OpenAlex replaced its old `mailto` polite pool with free API keys in February 2026.
Create the key at <https://openalex.org/settings/api>. Semantic Scholar keys also start
with a one-request-per-second limit, so its connector is paced by
`sources.semantic_scholar.request_delay_seconds`.

Daily snapshot persistence also requires a private GitHub App with **Contents: read and
write** access to this repository. Add the App to the `main-protect` ruleset's bypass
list with **Always allow**, then configure:

```text
Repository variable: RADAR_APP_ID
Actions secret:      RADAR_APP_PRIVATE_KEY
```

The built-in `GITHUB_TOKEN` authenticates discovery; the snapshot push uses the App token so
its `main` push can trigger deployment.

## Daily publishing

`.github/workflows/daily-radar.yml` runs once daily at 01:00 UTC and can also be started
manually. GitHub scheduled events are best-effort and may start late under Actions load.
Every scheduled run records its target, actual runner start, and latency in the job summary,
with a warning after 240 minutes. The workflow:

1. collects evidence plus public Hacker News attention and renders with read-only
   repository permission;
2. validates and uses the snapshot-writer App to persist one snapshot on `main`;
3. renders the day's social posting material into `out/social.md` inside the evidence
   artifact;
4. lets that App-authenticated push trigger the standalone Pages workflow;
5. prevents duplicate snapshots on reruns.

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
