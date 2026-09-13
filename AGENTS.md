# Repository Instructions

Read `principle.md` before changing a benchmark-facing surface. Its full-corpus
coverage rule applies to charts, search, tables, counts, and exports: start from
1,259+ benchmark records across 4+ sources, and investigate any unexplained
reduction to a few dozen. Missing measurements must not remove corpus records.
Benchmark Frontier and its linked score ranking explicitly exclude records
without numeric reported scores, as specified in `principle.md`.

## Reference guides

This file holds the rules that apply to every change. Detailed procedure lives
in the guides below. Each line states when the guide is required reading, and
the constraint that holds whether or not you open it.

| Guide | Read it before | Constraint that always holds |
| --- | --- | --- |
| [`docs/pipeline-and-data-map.md`](docs/pipeline-and-data-map.md) | Touching a source input, a generator, a generated artifact, or the technical report | Never reconstruct the system from a report, the deployed site, or leftover generated files. Never patch a derived file to fix a source-data problem. |
| [`docs/sop-add-model-cards.md`](docs/sop-add-model-cards.md) | Adding a model card, a benchmark, or a score | `data/model_cards.yml` and `data/benchmark_scores.yml` move together. Every value is read out of the cited document, never from memory. |
| [`docs/query-surfaces.md`](docs/query-surfaces.md) | Changing search, detail lookup, the CLI or HTTP query surface, or the consumer Skill | `QueryService` is the single source of truth. No interface-specific ranking, and no silent network fallback. |
| [`principle.md`](principle.md) | Changing any benchmark-facing surface | Start from the full corpus across all sources. |

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
- If you are an agent, say so on every pull request you open. Post a comment on
  the PR containing the marker `330226` and your model series (`GPT`, `Claude`,
  `Kimi`, and so on) as an annotation. The marker makes agent-authored PRs
  searchable in one query, and the model series tells a reviewer what produced
  the diff before they start reading it. A human opening a PR adds neither.

## Before opening a pull request

- Run the full CI sequence locally and get it passing before opening a PR. Do
  not open one against a red local run.
- A PR that adds a model card must also add that card's scores to
  `data/benchmark_scores.yml`. Follow
  [`docs/sop-add-model-cards.md`](docs/sop-add-model-cards.md); a card merged
  without its scores leaves a model the score progression cannot see.
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
