---
name: benchmark-radar
description: Find, inspect, and check AI benchmark records with the Benchmark Radar CLI. Use when a request needs benchmark discovery, details, recent Radar evidence, or local data health; do not assume why the user needs the results.
---

# Benchmark Radar

Use the local `benchmark-radar` CLI as the source of truth. Keep the user's purpose,
selection criteria, and desired output open unless they specify them.

## Prepare the data

1. Check availability with `benchmark-radar status --json`.
2. If the command is missing or exits before returning a JSON status response, report
   that the CLI is missing or broken. Offer installation, but do not install it without
   permission:

   ```bash
   python -m pip install 'git+https://github.com/ktwu01/benchmark-radar.git'
   ```

   If an existing installation cannot import `benchmark_radar`, offer a clean repair:

   ```bash
   python -m pip install --force-reinstall 'git+https://github.com/ktwu01/benchmark-radar.git'
   ```

3. If the CLI reports `not_initialized`, run `benchmark-radar init --json`; that
   successful init is already current, so do not immediately sync again.
4. Otherwise, when the request depends on current data, run
   `benchmark-radar sync --json` once before querying. Skip sync when the user asks
   to stay offline or retain a fixed local version. If sync fails, report it instead
   of silently presenting stale data as current.

## Choose the smallest command

- Discover records:
  `benchmark-radar search "<query>" --scope catalog|radar|all --json`
- Inspect one known key or slug:
  `benchmark-radar show "<identifier>" --json`
- Inspect the newest Radar evidence:
  `benchmark-radar recent --json`
- Check local data and provenance:
  `benchmark-radar status --json`
- Start the local HTTP interface only when requested:
  `benchmark-radar serve --host 127.0.0.1 --port 8765`

Use `catalog` for normalized benchmark records and `radar` for observed recent
evidence. Search them separately during discovery: a Radar item is a lead such as
a paper, repository, or dataset, not a verified catalog benchmark. Use `all` only
when the user explicitly wants one mixed evidence list; never compare ranking
scores across the two layers.

Search is deterministic lexical/token matching, not semantic search. Any shared
token can retrieve a candidate. BM25F is the main retrieval score, with controlled
name and phrase boosts; IDF coverage is a tie-breaker and explanation, not a
service-side acceptance decision. The `retrieval_score` is query-local ranking
evidence, not confidence and not comparable across queries. Partial matches remain
visible with matched and missing tokens so you can judge them against the user's request. A search result
is a candidate, not a suitability claim. For topical discovery, use two to four
short, discriminative variants drawn from the user's stated need:

1. the task phrase, such as `medical VQA`;
2. one terminology or morphology variant, such as `robotics manipulation`;
3. a task-plus-modality variant when the user supplied that constraint;
4. a known benchmark name only when the user named it or a result supplies it.

Do not add unrelated requirements or generate a large query spray. Keep which
query produced each candidate. A candidate found by several variants is useful
support, but raw BM25F scores are query-specific and must not be added or compared
across queries.

Interpret `search_status: full_matches_found` as complete lexical coverage in at
least one candidate, not proof of suitability. Interpret `partial_candidates_only`
as inspectable evidence that still needs query refinement or record review, never as
an answer. Interpret `no_lexical_candidates` as “no record shared any query token in
this local data version,” not proof that no such benchmark exists. If Catalog
candidates remain insufficient and recent discovery is relevant, search `radar` with
the same task terms and label every result as unverified Radar evidence.

Use `--json` for agent work; omit it only when the user wants terminal-friendly
text. Apply supported filters only when they come from the request. Do not run
maintainer commands such as `normalize-external`, `classify`, or
`build-data-release` for ordinary use.

The service does not decide whether a benchmark satisfies the user's intent. After
retrieval, the Agent should remove conversational wrapper text from the next query,
compare a small set of focused variants, inspect `missing_tokens` and
`idf_coverage`, and call `show` for any candidate it may present as suitable. The
Agent may report `no confident match` when the details do not support the request;
that is an agent judgment, not a lexical search status.

Before presenting a catalog record as suitable, call `show` and check that its
description, modality, artifacts, openness, and provenance support the user's
actual criteria. Use `matched_tokens`, `missing_tokens`, `matched_fields`, and the
record detail as evidence for your own final relevance judgment. Return relevant
records and their match reasons. Preserve the reported `data_version`,
`retrieval_mode`, and query provenance. Distinguish catalog records from Radar
evidence, and do not turn search results into a recommendation unless the user asked
for one.
