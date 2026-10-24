# Search relevance contract

Benchmark Radar serves two different evidence layers through one read-only query
service:

- **Catalog** contains normalized benchmark records from declared aggregator
  snapshots.
- **Radar** contains recently observed papers, repositories, datasets, releases,
  and other evidence. A Radar hit is a discovery lead, not proof that the item is
  itself a benchmark.

The interfaces keep those identities and provenance separate. CLI and HTTP call
`QueryService`; neither interface may add its own ranking, fallback, or network
lookup.

## Source-to-index boundary

Source metadata that is present in a declared immutable snapshot must survive
normalization unless the field would assert something the source did not say.
OpenCompass round 1 contains card descriptions, dimensions, and tags. Round 2
enriches those same 461 ids with paper, repository, dataset, openness, and size
evidence. Normalization joins the two exact id sets and fails when they differ;
round 2 must not replace the card search text with empty values. Modality is
normalized only from explicit English dimension values, never guessed from prose.

LLM Stats is different: its API has no paper, repository, licence, size, creator,
or evaluation protocol fields. Those values remain unknown rather than being
guessed from a name.

## Candidate retrieval and ranking

Search has three explicit stages:

1. Any shared token creates an observable candidate. A query token of at least two
   letters that is not already a whole word in the catalog also matches a longer
   ASCII word that starts with it, so typing `saf` or `hu` does not return an empty
   page. A token that is already a word stays exact, so `agent` does not match
   `agents`, and a token with no letter stays exact, so `10` does not match `100`.
2. BM25F over weighted fields is the primary score. Exact, prefix, and contiguous
   name matches receive bounded query-IDF-scaled boosts. A name prefix includes a
   name whose leading words start with the query words, so `human` ranks a
   benchmark named Humanity's Last Exam with that boost even though `human` is
   already a whole word elsewhere. A contiguous query phrase
   in a non-name field receives a smaller query-IDF-scaled boost. Name phrases are
   not counted twice.
3. Candidates are returned with the evidence an agent needs to make the final
   relevance and suitability judgment. Weighted query coverage is a tie-breaker and
   explanation, never an eligibility gate or an additive score component.

The response exposes `candidate_count`, `total_matches`, `full_match_count`,
`partial_match_count`, `search_status`, policy identity, matched and missing tokens,
lexical coverage, fields, phrase fields, the raw retrieval score, and its score
components. Candidate count and total matches are equal because search no longer
hides partial lexical evidence behind a service-side acceptance policy. The score
orders one query; it is not calibrated confidence and must not be compared across
queries. `retrieval_score` is a ranking signal only. `idf_coverage` reports the
fraction of smoothed query-IDF mass matched by a record; it is evidence for the
consuming agent, not a semantic acceptance threshold.

Status is a lexical decision separate from candidate retrieval:

- `full_matches_found`: at least one candidate covers every unique query token;
- `partial_candidates_only`: candidates exist, but all have missing query tokens;
- `no_lexical_candidates`: no record shares any query token.

Partial candidates remain in `results` for agent inspection. The status prevents
them from being presented as confident answers without reintroducing an all-terms
eligibility gate.

When no record shares even one token with the query, the result is:

```json
{
  "search_status": "no_lexical_candidates",
  "candidate_count": 0,
  "total_matches": 0,
  "full_match_count": 0,
  "partial_match_count": 0,
  "results": []
}
```

This is a retrieval fact about the current local data version. It does not prove
that the wider world contains no such benchmark. Likewise, complete lexical coverage
does not assert that a candidate satisfies the user's task.

This follows the same broad decomposition used by established lexical engines:

- [Elasticsearch multi-match](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query)
  supports per-field boosts and phrase queries;
- [Elasticsearch match phrase](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-match-query-phrase)
  treats analyzed token proximity as a separate query signal;
- [Meilisearch ranking rules](https://www.meilisearch.com/docs/learn/relevancy/ranking_rules)
  separate broad word/proximity matching from later attribute and exactness rules;
- [Typesense search](https://typesense.org/docs/29.0/api/search.html) exposes field
  weights and explicit exact-phrase matching.

Benchmark Radar keeps the same ideas in a small deterministic implementation rather
than introducing a search server for 1,173 local Catalog records.

## Agent query expansion

The Skill may issue two to four short variants grounded in the user's stated task,
terminology, modality, and constraints. It keeps query provenance, searches Catalog
and Radar separately, and never adds raw scores across queries. Query expansion can
bridge vocabulary differences; it cannot repair missing sources, discarded metadata,
stale snapshots, identity errors, or insufficient benchmark detail.

Catalog candidates must be inspected with `show` before suitability claims. The
agent, not the query service, decides whether a full or partial match answers the
user's intent. Radar results remain labelled unverified evidence until their primary
artifact establishes the task and benchmark identity.

## Regression gates

The versioned relevance suite covers:

- navigational and topical positive queries;
- known Catalog-gap queries whose partial evidence must remain inspectable;
- source-metadata survival for opaque names such as ClimateViz;
- token-boundary safety;
- Catalog/Radar identity separation;
- CLI/HTTP JSON equality.

The broader evaluation dataset lives at `tests/fixtures/search_evaluation.yml` and
runs through `scripts/evaluate_search.py`. It contains navigational, topical, and
known Catalog-gap queries with sparse positive relevance judgments. Because unlisted
records are unjudged rather than negative, its valid aggregate metrics are Hit@K,
MRR@K, and Recall@K. Catalog-gap labels additionally test partial-candidate retention
and unexpected full matches. Precision and NDCG require a completely judged result
pool and are intentionally not reported yet.

Every confirmed search failure becomes a labelled regression case. Do not update an
expectation merely to make a new ranking pass: inspect the underlying records and state
why the result is relevant or should be rejected.
