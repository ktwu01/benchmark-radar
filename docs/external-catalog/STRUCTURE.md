# The simplest useful structure

Target question set, from #227 and the #240 discussion: **find it fast, then in a few
seconds answer who made it, is it open, how big is it, and what scores exist.**

Everything below exists to answer those four, or to stop us answering them wrongly.

Revised after an independent review by Codex (2026-08-17); the review's substantive
objections are folded in and noted at the end.

## Files

```
llm-stats zip ─┐
               ├─> data/external/source_records.jsonl        (1,148 rows: 687 + 461)
opencompass ───┘   data/external/score_observations.jsonl    (~5,600 rows)
                   data/external/identity.yml                (hand-edited, ~90 groups)
                                    │
                    build ──────────┤
                                    ├─> site/data/benchmark-index.json     (search)
                                    └─> site/data/benchmarks/<slug>.json   (per-record shard)
```

`radar.json` is untouched. It stays the daily-collection payload. External data is a
**separate trust domain** from the curated `model_cards.yml` / `benchmark_scores.yml`
layers and never flows into `benchmark_score_progression`.

The identity layer is the one piece you could ship without. If we need to cut scope,
ship layers 1 and 3 with one search row per source record and let MMLU appear twice,
labelled by source. Two labelled duplicates are a smaller lie than one wrong merge.

The two sources fill different columns and are not interchangeable. OpenCompass supplies
identity (publisher, paper, repo, dataset, release) and almost no scores. llm-stats
supplies scores (4,608 of 5,544 rows from 2025-26 models) and, structurally, no identity
at all: its API has eight keys and none of them is a paper, org, licence or size. An
llm-stats-only record whose `publisher`, `artifacts`, `sizes` and `openness` are all empty
is not a gap to be filled by a later crawl. It is the accurate representation of what that
source knows, and the schema exists to hold it. See `AUDIT.md` §3-4.

## Layer 1 - `source_records.jsonl`

One line per `(source, source_benchmark_id)`. 1,148 lines. Never deduplicated across
sources: two sources describing the same benchmark stay two rows.

```json
{
  "key": "opencompass:1248__MMMU",
  "slug": "opencompass-1248-mmmu",
  "schema_version": 1,
  "source": "opencompass_hub",
  "source_benchmark_id": "1248__MMMU",
  "name": "MMMU",
  "description": {"en": "...", "zh": "..."},
  "publisher": {"name": "OpenCompass", "role": "hub_publisher", "locator": "card.detail.basicInfo.publishOrg"},
  "artifacts": [
    {"kind": "paper",   "url": "https://arxiv.org/abs/2311.16502", "id": "arxiv:2311.16502", "locator": "card.paper_link"},
    {"kind": "repo",    "url": "https://github.com/MMMU-Benchmark/MMMU", "id": "gh:MMMU-Benchmark/MMMU", "locator": "card.github_link"},
    {"kind": "dataset", "url": "https://huggingface.co/datasets/MMMU/MMMU", "id": "hf:MMMU/MMMU", "locator": "detail.basicInfo.downloadUrls[0]"}
  ],
  "openness": {"status": "unknown", "code_license": null, "data_license": null, "evidence": []},
  "sizes": [],
  "modality": "multimodal",
  "released": "2023-11-27",
  "provenance": {"source_url": "...", "crawled_at": "2026-08-17T18:56:09Z", "crawl_bundle": "OpenCompassHub_Public_Crawl_2026-08-17"}
}
```

**`key` is `source:source_benchmark_id`; `slug` is its filesystem- and URL-safe form.**
The key makes "unmatched benchmarks are counted, not dropped" real: all 1,148 rows are
addressable. The slug exists because raw external ids contain `:`, `/`, and non-ASCII
(`1248__MMMU`, `community:07c9946d-...`), and those cannot be shard filenames. Slug is
`lowercase, [a-z0-9-] only, collisions get a -2 suffix`, and it is emitted into the
record so nothing has to recompute it.

**`openness.status` is `open | restricted | unknown`, and it needs a truth table, not a
judgement call.** Ship this one; an agent or a build step that cannot satisfy a row
outputs `unknown`:

| code public | data fetchable | data licence | → status |
|---|---|---|---|
| yes | yes | permissive or share-alike SPDX | `open` |
| yes | yes | non-commercial / no-derivs / custom | `restricted` |
| any | yes | none found | `restricted` |
| any | gated (form, HF gate, registration) | any | `restricted` |
| any | not found | any | `unknown` |
| any | link dead (404/410) | any | `unknown` |

Today the honest answer is `unknown` for roughly 95% of rows: OpenCompass `public_flag=1`
on all 461 means "card is visible", and only 66 carry 开源收录 with no SPDX id.

**Code licence and data licence are separate fields, always.** Eval harnesses are
routinely Apache-2.0 while the data is CC-BY-NC. Collapsing them answers "is it open"
wrongly in the exact direction that matters.

**`sizes` is a list of `{value, unit, split, measures, evidence}`, and empty is normal.**
Units: `questions | tasks | items | images | videos | audio_clips | hours | tokens |
repos | episodes`. `measures` is `eval_set | train_set | total | unclear`, README counts
frequently describe training data or a superset, and a number with no idea what it counts
is worse than no number. Never sum across splits.

**No `verified` field.** llm-stats sets it `False` on all 687 benchmarks and all 5,544
scores; OpenCompass `public_flag` is `1` on all 461. Both are constants.

**`publisher` is one field with an explicit `role`, not an authors list.** OpenCompass
`publishOrg` identifies whoever published the hub card, which is often not the benchmark's
creator. Role is `hub_publisher | paper_org | maintainer`. We do not store paper author
lists: "who made it" is answered by an organization plus a paper link, and 461 × 8
author-affiliation assertions is 3,000 chances to be wrong for no added answer.

**`locator`, not `evidence_quote`, for machine-read fields.** A JSON pointer into the
retained raw response (`card.paper_link`) is exact, stable, and small. Quotes are reserved
for fields an agent *judged* rather than read: size extraction, licence interpretation,
identity claims. That is where a quote actually constrains anything.

## Layer 2 - `identity.yml`

The only hand-edited file. Two distinct relations, because conflating them is how you
publish "GPQA Diamond" scores that came from GPQA full.

```yaml
schema_version: 1

# Same benchmark, same instrument. Safe to show under one heading.
equivalent:
  - group_id: mmlu
    canonical_id: mmlu          # optional; absent = external-only group
    members: [llm-stats:mmlu, opencompass:0421__MMLU]
    anchors: [arxiv:2009.03300, gh:hendrycks/test]
    reviewed_by: ktwu01
    reviewed_at: 2026-08-18

# Related, NOT the same. Rendered as a cross-link, never merged, never co-ranked.
variants:
  - of: gpqa_diamond
    key: opencompass:1176__GPQA
    relation: superset
    note: OpenCompass card covers GPQA full; Diamond is a 198-question subset.
```

`anchors` is the reviewable evidence: a shared arXiv id, a shared `owner/repo`, or a
shared `hf:owner/name`. A shared *name* is not an anchor. **A machine-promoted group with
fewer than two independent anchors does not go in `equivalent`**, it goes in a
`candidates:` block for a human to clear.

**`basis: reviewer_asserted` is the hand-review escape from the two-anchor bar.** llm-stats
carries no artifacts, so no llm-stats-to-OpenCompass equivalence can ever clear two machine
anchors, yet a reviewer reading both cards can still confirm the two rows are one
instrument (#262). On such a group the reviewer's signature is the second warrant: the
loader drops the floor to one donor anchor and makes `reviewed_by` / `reviewed_at`
mandatory. The `anchors` listed are then the *donor's* artifacts that ground the identity,
not anchors shared with the scoreless side.

```yaml
equivalent:
  - group_id: gpqa
    basis: reviewer_asserted
    members: [llm-stats:gpqa, opencompass:1135]
    inherit_from: opencompass:1135   # whose identity the others may display
    anchors: [arxiv:2311.12022, gh:idavidrein/gpqa]
    reviewed_by: ktwu01
    reviewed_at: 2026-08-22
```

**`inherit_from` carries identity across the group, never scores.** It names the member
whose publisher, artifacts, release date, size and openness the other members may display
when they carry none of their own. `apply_inherited_identity` only ever fills an empty
field and attaches an `identity_inheritance` note naming the donor source, so a GPQA record
showing "Anthropic" makes clear the value came from the OpenCompass card. The two rows stay
two rows: no score joins another source's series, and `openness.status` is inherited already
mechanically-derived, never hand-set.

`equivalent` groups do not require a `canonical_id`. 76 names collide between the two
crawls and most of those benchmarks are in neither the registry nor each other's
canonical set; a group of two external keys with no canonical id is the normal case.

Explicit rather than computed because the join count moved from 65 to 72 canonical ids
between two sessions purely by changing the normalizer. An automatic join hides that;
a checked-in file makes it reviewable.

## Layer 3 - `score_observations.jsonl`

One line per reported cell.

```json
{
  "obs_id": "llm_stats:gpqa-diamond:claude-opus-4-6:accuracy",
  "key": "llm-stats:gpqa-diamond",
  "series_id": "llm_stats:gpqa-diamond:default",
  "model_name": "Claude Opus 4.6",
  "organization": "Anthropic",
  "raw_value": "0.887",
  "value": 0.887,
  "value_kind": "number",
  "reported_by": "self_reported",
  "comparable_group": null,
  "crawled_at": "2026-08-17T18:49:35Z",
  "reported_date": null,
  "source_url": "https://api.zeroeval.com/leaderboard/benchmarks/gpqa-diamond?top_n=500"
}
```

Metric, direction, and bounds live once per `series_id` in a sibling
`score_series.jsonl`, not on every row. OpenCompass proves metrics are *column*-specific,
not benchmark-specific (`node(n-f1)` and `chain(ned)` on one card have opposite
directions), so per-row duplication guarantees drift.

```json
{"series_id": "llm_stats:gpqa-diamond:default", "metric": "accuracy",
 "direction": "higher_is_better", "bounds": {"min": 0, "max": 1, "basis": "aggregator_declared"},
 "display_scale": null}
```

**`obs_id` is the dedup key.** Without it a re-crawl duplicates all 5,544 rows silently.

**`crawled_at` is crawl time and is named that.** No llm-stats row carries an evaluation
or publication date. Calling it `observed_at` invites someone to plot it as a time axis.
`reported_date` is separate and is usually null.

**`raw_value` is kept and `value` may be null.** OpenCompass leaderboard cells are not
reliably numeric: they include ranks, "N/A", percentages, and composite strings.
`value_kind` is `number | rank | text | missing`. Coercing everything to a float
manufactures scores out of rank columns.

**`display_scale: null` unless bounds pass an allowlist.** This is the enforcement point,
not a note in a doc. The build emits `display_scale` only when `bounds.basis` is
`from_paper` and min/max are sane; every llm-stats row therefore gets `null`, and the
renderer has no number to draw a percentage bar from. `vending-bench-2` declares
`max=1.0` and carries 8017.59, so permission-based honesty ("the renderer *can* refuse")
is not enough.

**`comparable_group: null` blocks joins structurally.** Rows may be connected by a line or
ranked together only within a non-null `comparable_group`. Every llm-stats row is null,
because no row carries shots, harness, tool access, or attempts. Null is not a group:
two nulls never join. This mirrors the rule `benchmark_scores.py` already enforces for the
curated layer on `(instrument, protocol)`.

**Saturation is not derived from this layer.** `benchmark_scores.yml` already states that
saturation stays an editorial judgement in `model_cards.yml`. 5,410 self-reported
unverified rows do not change that.

## Build contract

Without this the honesty rules are prose an implementer will route around.

- New CLI subcommand `benchmark-radar build-external`, inputs `data/external/*`, outputs
  `site/data/benchmark-index.json` + `site/data/benchmarks/*.json`. Separate from the
  daily `export` so a crawl refresh does not require a collection run.
- `.github/workflows/pages.yml` currently rebuilds only on known inputs and runs
  `benchmark-radar export`; it needs `data/external/**` added to its triggers and the new
  subcommand added to the build step, or none of this ever reaches the site.
- Strict loaders with `schema_version` on every file, mirroring the referential-integrity
  checks `model_cards.py` and `benchmark_scores.py` already do, and reusing
  `leaderboard_snapshots.py` from the legacy branch rather than replacing it. Reject: duplicate `key`,
  duplicate `obs_id`, a score whose `key` has no source record, an `identity.yml` member
  that does not exist, a machine-promoted `equivalent` group with fewer than two anchors, a
  `reviewer_asserted` group missing `reviewed_by`/`reviewed_at` or a donor anchor, an
  `inherit_from` that is not a member.
- Deterministic output: sorted keys, stable row order, no build timestamp inside the
  payload. Otherwise every rebuild is a full diff.
- Shards are written to a fresh directory and swapped, and stale shards are deleted, so a
  removed benchmark does not leave a live URL serving last month's data.
- Descriptions and README excerpts are crawled third-party HTML. Escape on render; never
  `innerHTML`.
- The zips live outside the repo, but this is already solved on
  `origin/legacy/leaderboard-snapshots`: the crawl CSVs are checked in under
  `data/leaderboard_snapshots/` and `data/leaderboard_snapshots.yml` declares per-snapshot
  `benchmark_count` / `score_row_count` that the loader refuses to publish against if they
  drift, plus an explicit `columns` map so no header is guessed. Extend that contract to
  the new files rather than inventing a second one; a build that depends on a zip on one
  laptop is not a build.

Tests that must exist, because these are the claims the whole design rests on:
null-`comparable_group` rows never join; two sources never appear in one sorted list;
`display_scale: null` never yields a percentage; an `identity.yml` group with one anchor
fails the loader; external scores never enter `benchmark_score_progression`.

## Artifacts out

`site/data/benchmark-index.json`, one entry **per source record**, not per merged group.
Merging happens in the UI at render time using `identity.yml`, so a bad group is a display
bug rather than baked-in data loss.

```json
{"slug":"opencompass-1248-mmmu","key":"opencompass:1248__MMMU","name":"MMMU",
 "source":"opencompass_hub","group_id":"mmmu","canonical_id":"mmmu","publisher":"OpenCompass",
 "released":"2023-11-27","openness":"unknown","modality":"multimodal",
 "score_count":0,"has_paper":true,"has_repo":true}
```

~180 bytes × 1,148 ≈ 200 KB, loadable up front for typeahead over everything. Rows sharing
a `group_id` collapse into one result showing both source badges; ungrouped duplicates
show as separate rows, labelled.

`site/data/benchmarks/<slug>.json`, full record, its group siblings, and its score rows
partitioned by source in the file itself, so no client code can flatten them.

## Minimum viable display

Search result row: **name · publisher · release year · source badges · openness chip ·
score-row count**. Every field is either present today or honestly renderable as `unknown`.

Detail page, above the fold: name; description; publisher with role; artifact links
(paper / repo / dataset); openness with its evidence or an explicit "not established";
sizes or "not established"; then score tables, one heading per source, each labelled
`self-reported, no protocol recorded`.

Openness, sizes, licence and protocol must render as an explicit "not established" rather
than being hidden. Hiding them reads as "not applicable"; the user's question is precisely
whether these are known, and today the answer is usually no.

## Review notes

Codex's review drove: splitting `equivalent` from `variants` (the original GPQA example
asserted identity and incomparability in the same entry), external↔external groups with
no canonical id, `obs_id` dedup, `crawled_at` naming, `series_id` deduplication of
metric/bounds, `raw_value` + `value_kind`, the openness truth table, the slug scheme, the
build contract and Pages integration, and turning `bounds.basis` / `protocol: null` into
`display_scale: null` / `comparable_group: null` build outputs with tests.

Not adopted: dropping the identity layer entirely (76 cross-crawl collisions make explicit
review worth the file, and the fallback is documented above instead); dropping evidence
quotes entirely (kept for agent-judged fields, replaced by `locator` for machine-read
ones); dropping dead-link detection (`repo_status: 404` feeds the openness table, though
stars and last-commit are cut).
