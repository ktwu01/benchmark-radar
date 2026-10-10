# Contributing

Thanks for considering a contribution. This page is the single starting point:
what we merge, what we don't merge, and the problems that most often hold a pull
request back. Read it before you open a PR. It takes five minutes and can save
you a week of review rounds.

| You want to… | Read |
| --- | --- |
| Add a model card, benchmark or score | [`docs/sop-add-model-cards.md`](docs/sop-add-model-cards.md) |
| Change a chart, search, table, count or export | [`principle.md`](principle.md) |
| Touch a source, generator or generated file | [`docs/pipeline-and-data-map.md`](docs/pipeline-and-data-map.md) |
| Earn points | [`docs/contributor-points.md`](docs/contributor-points.md) |
| Work as an AI agent | [`AGENTS.md`](AGENTS.md) |

## 1. What we merge

### The most useful thing you can add: a model card

The [Model Card Adoption Rank](README.md#model-card-adoption-rank) answers a
question nobody else is tracking: which benchmarks do frontier vendors actually
report when they ship a model? Its value grows with every document it has read,
and it is curated by hand because no reliable parser for vendor PDFs and release
posts exists. The registry is schema-validated, so a mistake fails the build
loudly rather than silently shifting the ranking.

Append an entry to `model_cards:` in [`data/model_cards.yml`](data/model_cards.yml):

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

The loader enforces these rules:

- **Record what the document reports, not what the model can do.** The counted
  unit is the document. A card reporting AIME three ways contributes one
  adoption, so a long appendix cannot outvote a different vendor.
- **Every benchmark id must already exist** in the `benchmarks:` block. A typo
  would otherwise invent a phantom benchmark with exactly one adopter.
- **One URL per document.** The same report under two ids would count twice.
- **A card cannot report a benchmark released after it.** If a living document
  really gained a benchmark later, record the real `revised` date.
- **A new benchmark needs a `caveat`:** what would mislead someone comparing two
  reported numbers, such as a small split or a score that depends on tool access.

One more rule is yours to check by hand, because no loader can see what the
document left out: **scores move with the card.** Every number you can read with
certainty from the document goes in
[`data/benchmark_scores.yml`](data/benchmark_scores.yml), with the document
cited. Read every value out of the document, never from memory. A card merged
without its readable scores leaves that model invisible to the score history.

### Every PR we merge does these things

- **Starts from the full corpus.** Every benchmark-facing chart, search, table,
  count and export covers all records across all sources (1,259+ records across
  4+ sources at minimum). Missing measurements never remove a record. If your
  surface shows a few dozen benchmarks, records are missing. One exception:
  Benchmark Frontier and its linked score ranking exclude records without a
  numeric reported score, and account for them in their counts. See
  [`principle.md`](principle.md).
- **Makes one change.** One logical change per PR. A connector, a page and a
  restyle are three PRs. Stacked PRs say so and land in order.
- **Is current and green.** Rebased on the latest `main`, with the full CI
  sequence passing from a clean checkout (`git worktree add`, then
  `git submodule update --init --recursive`). Give that checkout its own
  environment first; a global install can run code from the wrong checkout:

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -e '.[dev]'

  ruff check .
  ruff format --check .
  benchmark-radar normalize-catalog
  benchmark-radar classify
  benchmark-radar build-data-release
  pytest -q
  ```

  A docs-only PR may skip the sequence when this prints nothing, meaning no
  test, source or site file refers to the files you changed:

  ```bash
  git diff --name-only origin/main... | xargs -n1 basename \
    | xargs -I{} git grep -lF {} -- tests src site
  ```

- **Shows UI changes.** Before/after screenshots at desktop and phone width,
  light and dark. Keep the existing header, logo, colors and layout. UI changes
  are merged on design quality, so keep the first screen simple.
- **Cites primary evidence.** Every entry links to the official paper, card,
  dataset or leaderboard it came from. Nothing asks a reader to take our word.
- **Carries a regression test when it fixes a bug.** Name the failure, show
  the test failing before the fix and passing after. Comments explain what the design
  prevents, not what the code does.
- **Discloses authorship.** You may add a benchmark you wrote. Say so in the PR.

## 2. What we don't merge

Stated up front so nobody writes work that has to be turned down.

- **Scores in the adoption registry.** Vendors differ on prompt, scaffold, tool
  access, reasoning budget, pass@k and evaluator. A mention survives all of
  those caveats, which is why it is the unit the ranking publishes.
- **Any ranking presented as a quality judgement.** Adoption measures vendor
  attention, not benchmark quality.
- **Fuzzy matching that silently merges records.** Entities resolve on exact
  identifiers (DOI, arXiv, OpenReview, GitHub, Hugging Face).
- **Synthesized summaries.** A missing upstream description stays empty.
- **Scraping behind authentication.** No cookies, logged-in sessions, private
  posts, or LinkedIn and X scraping.
- **Hand-edited generated files.** `site/data/models.json`,
  `site/data/logo-registry.json`, `site/data/radar.json` and the catalog index
  and shards are regenerated by the build. Fix the source data and rerun the
  generator; never patch the output.
- **Self-cited source documents without official data.** Your own system
  report, solution repository or participant paper registered as a benchmark's
  leaderboard or evidence. Cite the organizers' official leaderboard or paper.
- **Stale or unrelated history.** A branch that no longer shares history with
  `main`, or that brings back old commits, snapshots or files. Replay your own
  commits onto a fresh branch from `main`.
- **Paper material.** Report drafts, figures and analysis folders for the
  technical report go to
  [`benchmark-radar-paper`](https://github.com/ktwu01/benchmark-radar-paper),
  not this code repository.
- **Useless bug fixes.** Changes without a reproducible failure a user could
  hit: cosmetic churn, defensive code for impossible inputs, rewording, or
  tests that pin source text or today's data counts instead of behavior.
- **Floods of AI-generated PRs.** AI-assisted work is welcome when a person has
  read and checked it and it states the model (`330226 <model-id>` in a PR
  comment, see `AGENTS.md`). Many near-identical or unverified agent PRs are
  closed without review.

### A real example of a flood

Between 2026-09-29 and 2026-10-09, one account opened **58 pull requests and
11 issues**. At the peak, 56 PRs and 11 issues were open at the same time.

- **Bursts faster than anyone can review.** 15 PRs in 37 minutes on
  2026-09-30 ([#716](https://github.com/ktwu01/benchmark-radar/pull/716) to
  [#730](https://github.com/ktwu01/benchmark-radar/pull/730)). On 2026-10-06,
  29 PRs in one day, including 8 in 27 seconds
  ([#768](https://github.com/ktwu01/benchmark-radar/pull/768) to
  [#775](https://github.com/ktwu01/benchmark-radar/pull/775)).
- **Self-issue, self-PR.** On the afternoon of 2026-10-06 the account filed 11
  issues ([#782](https://github.com/ktwu01/benchmark-radar/issues/782) to
  [#798](https://github.com/ktwu01/benchmark-radar/issues/798)), then opened a
  PR "fixing" each one minutes later. For example, issue
  [#788](https://github.com/ktwu01/benchmark-radar/issues/788) at 14:01 became
  PR [#799](https://github.com/ktwu01/benchmark-radar/pull/799) at 14:15. An
  issue written by the PR's own author, to justify that PR, is not evidence
  that anyone needs the change.
- **Hypothetical edge cases.** Most reproductions were inputs no user or source
  had produced: a JSON number `1e400` turning into Infinity, a single-quoted
  `url('a/*b*/c.png')` in the CSS minifier, an HTTP-date `Retry-After` header,
  `xml:base` in Atom feeds, a source title crafted as `MemoryBench](https://wrong.test)`.
  Each came with long, polished, AI-generated verification text.
- **Outcome.** Five PRs were merged, the ones that fixed silent data loss in
  the corpus or a real report bug
  ([#706](https://github.com/ktwu01/benchmark-radar/pull/706),
  [#723](https://github.com/ktwu01/benchmark-radar/pull/723),
  [#773](https://github.com/ktwu01/benchmark-radar/pull/773),
  [#774](https://github.com/ktwu01/benchmark-radar/pull/774),
  [#815](https://github.com/ktwu01/benchmark-radar/pull/815)). The other 53
  PRs and all 11 issues were closed as not planned on 2026-10-07, so the queue
  could be reviewed again.

The lesson is not "never send fixes". It is: **send the few that a real user or
caller would hit, one at a time, and wait for review before sending the next.**
Five merged fixes from 58 PRs means 53 reviews nobody needed.

### Open item limit

One author can have at most **10 open issues and pull requests combined**. A new
one past that is closed automatically with a note, and can be reopened once
earlier ones are merged or closed. Maintainers are exempt. Pick the few changes
that matter most and finish them.

## 3. How points work

Points, scored issues, collaborator seats and the public ledger are described in
[`docs/contributor-points.md`](docs/contributor-points.md).

## 4. Other problems

- **CI has not run on your PR.** Workflows from forks wait for a maintainer to
  approve them. Say in the PR that you ran the six steps from a clean checkout,
  and with what result. "Relying on CI" is not a verification. CI does not run
  at all for most Markdown-only changes; for a docs-only PR, say that the
  docs-only check above printed nothing.
- **Your branch conflicts.** Rebase on `main`. When both sides append to a YAML
  file or a test file, keep both blocks. When a generated file conflicts, take
  `main`'s copy and regenerate it.
- **Your local run passes but CI fails.** Gitignored generated files on disk can
  hide failures. Run from a clean worktree with its own venv; see
  [`docs/agent-gotchas.md`](docs/agent-gotchas.md).
- **Review asks go unanswered.** A PR that has had no reply to review comments
  for two weeks may be closed. Reopen it, or open a fresh one, when you return.
- **Who merges.** Only maintainers merge, with a merge commit.
- **A wrong row in the ranking.** That is a real bug, not a nitpick. Open an
  issue with the document URL and what it actually reports, and the benchmark
  id if you know it.
