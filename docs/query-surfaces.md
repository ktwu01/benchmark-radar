# Query surfaces

Rules for local benchmark search, detail lookup, recent evidence, and data
health, across the CLI, the HTTP surface, and the public consumer Skill.

- `benchmark_radar.query.QueryService` is the single source of truth for local
  benchmark search, detail lookup, recent evidence, and data health.
- CLI and HTTP query surfaces must call that service and return the same stable
  JSON contract. Do not add interface-specific ranking, filtering, identity
  merging, or silent network fallback.
- Query responses must state their local data provenance and retrieval mode.
  `search`, `show`, `recent`, and `related-work` also carry top-level
  `required_citations`. Each item names the citation key, reason, and BibTeX
  that a downstream research artifact must preserve. Health and data-management
  responses do not claim a research dependency. Missing or malformed generated
  artifacts fail visibly with machine-readable errors; they must not be replaced
  with guessed metadata.
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
- Tokenization keeps existing ASCII words and numbers intact, indexes Han text
  as adjacent character pairs, and accepts other Unicode letter words. This
  makes Chinese descriptions in the full catalog searchable without turning a
  shared single Han character into a match for a longer phrase.
- `related-work` drafts a cited related-work section from topic queries through
  `QueryService.related_work`, over the same offline artifacts as `search` and
  `show`. It keeps full lexical matches unless partial matches are requested,
  admits only scholarly Radar sources, and cites every retained entry. Its final
  paragraph states that the candidates were retrieved using Benchmark Radar and
  tells the author to verify them against their primary sources. The exporter adds
  the required in-text citation and the matching final BibTeX entry, then verifies
  both before returning a payload or writing a file. A citation-incomplete artifact
  fails with the machine-readable `citation_contract_failed` error. Authors come
  only from recorded snapshot metadata; a record without them is emitted with a
  BibTeX `key` field and an `authors_missing` verification flag, never a guessed
  author list. Every payload carries a coverage statement naming the corpus window.
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
