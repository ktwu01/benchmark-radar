# Contributing

Thanks for considering a contribution. This project has one contribution that
is worth more than any other, so it comes first.

## The most useful thing you can add: a model card

The [Model Card Adoption Rank](README.md#model-card-adoption-rank) answers a
question nobody else is tracking: which benchmarks do frontier vendors actually
report when they ship a model? Its value scales directly with how many
documents it has read, and it is curated by hand because no reliable parser for
vendor PDFs and release posts exists.

Every model card, system card, technical report, or release post you add makes
the ranking more defensible. This is a genuinely low-risk contribution: the
registry is schema-validated, and a mistake fails the build loudly rather than
silently shifting the ranking.

To add one, append an entry to `model_cards:` in
[`data/model_cards.yml`](data/model_cards.yml):

```yaml
  - id: acme_frontier_1
    organization: Acme
    model: Frontier-1
    document_type: model_card       # or system_card, technical_report, release_post
    published: 2026-05-14           # the document's date, not the model's
    retrieved_at: 2026-08-02        # when you read it
    url: https://acme.example/frontier-1-model-card
    benchmarks: [gpqa_diamond, swe_bench_verified, aime]
```

Then rebuild and check:

```bash
benchmark-radar rebuild
pytest -q
```

Rules the loader enforces, and the reason for each:

- **Record what the document reports, not what the model can do.** The counted
  unit is the document. A card reporting AIME at pass@1, at consensus@64, and
  with a Python tool contributes exactly one adoption, so a long appendix
  cannot outvote a different vendor.
- **Every benchmark id must already exist** in the `benchmarks:` block. An
  unknown id is a hard error, because a typo would otherwise invent a phantom
  benchmark with exactly one adopter, indistinguishable from a real benchmark
  nobody adopted.
- **One URL per document.** The same report entered twice under two ids would
  add two adoptions to every benchmark it lists.
- **A card cannot report a benchmark released after it.** If the document
  genuinely gained a benchmark later (an arXiv report at v2+, a living card the
  vendor edits in place), record the real `revised` date rather than using it
  to silence the check.

Adding a new benchmark to the `benchmarks:` block needs a `caveat`. It is
required, not optional: the ranking's headline risk is being read as a quality
ordering, and the per-row caveat is what stops a saturated or contaminated
benchmark from sitting near the top with no qualification. Write what would
mislead someone comparing two reported numbers, for example a small split with
wide variance, or a score that depends on scaffold and tool access.

The full maintenance contract is documented at the top of
[`data/model_cards.yml`](data/model_cards.yml).

## What this project will not accept

Stating these up front so nobody writes code that has to be turned down.

- **Scores in the adoption registry.** Vendors differ on prompt, scaffold, tool
  access, reasoning budget, pass@k, and evaluator, so two reported numbers for
  the same benchmark are usually not comparable. A mention survives all of
  those caveats, which is why it is the unit this ranking publishes.
- **Any ranking presented as a quality judgement.** Adoption measures vendor
  attention. A saturated benchmark can rank highly precisely because reporting
  it is conventional.
- **Fuzzy matching that silently merges records.** Entities resolve on exact
  identifiers (DOI, arXiv, OpenReview, GitHub, Hugging Face). A near-match that
  quietly merges two artifacts corrupts the corpus in a way no reader can see.
- **Synthesized summaries.** Connector summaries quote upstream text. A missing
  upstream description stays empty rather than being generated.
- **Scraping behind authentication.** No cookies, no logged-in sessions, no
  private posts, no LinkedIn or X scraping.

## Code changes

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Before opening a pull request:

```bash
ruff check .
ruff format --check .
pytest -q
benchmark-radar rebuild
```

Two conventions matter more here than in most repositories:

**Comments explain what a design prevents, not what the code does.** Much of
this codebase encodes a decision that looks arbitrary until you know the
failure it rules out. If you are fixing a bug, the comment should say what went
wrong, so the next reader does not undo the fix.

**Tests carry their regression.** A test named for the behaviour it protects,
with a comment naming the real failure, is worth several that only assert
current output.

Commits are atomic: one logical change each. Keep unrelated fixes in separate
commits.

## Reporting data errors

A wrong row in the adoption ranking is a real bug, not a nitpick. Open an issue
with the document URL and what it actually reports. Include the benchmark id if
you know it.

## Provenance

Every entry must link to the primary or structured record it came from. Nothing
in this project asks a reader to take its word for something.
