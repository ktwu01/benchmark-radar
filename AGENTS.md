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
| [`docs/agent-gotchas.md`](docs/agent-gotchas.md) | Verifying locally, merging, or answering a literature question | A local result counts only from a clean worktree with its own venv. |

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

## Working rules

- Finish the task without nudges. Stop only for a merge, a credential, or a
  destructive action.
- If a request has two opposite readings, state your reading in one line, then
  proceed.
- Keep each fix minimal. File each follow-up as its own issue.
- End with a link to the rendered result, after you open it yourself.

## Branches and pull requests

- Never push to `main`. Every change goes through a pull request.
- Start each task from the latest `main`:

      git fetch origin main:main
      git switch --no-track -c <branch> main
      git push -u origin <branch>

  The first command updates local `main` without a checkout. If it fails,
  local `main` has diverged: stop and report it. Keep `--no-track` so a bare
  `git push` never targets `main`.
- To update an existing branch, run `git fetch origin main:main`, then
  `git rebase main`. Re-read the diff before you push.
- Never merge a pull request unless the user asks. When asked, use a merge
  commit. Do not squash.
- Agents: comment `330226 <model-id>` on every pull request you open, for
  example `330226 claude-opus-5-5`. Use the exact model ID, not only `Claude`
  or `GPT`.

## Before opening a pull request

- Run the full CI sequence locally and get it passing before opening a PR. Do
  not open one against a red local run.
- A PR that adds a model card must also add every numeric score that card
  reports and that can be read with certainty to `data/benchmark_scores.yml`.
  Follow [`docs/sop-add-model-cards.md`](docs/sop-add-model-cards.md); a card
  merged without its readable scores leaves a model the score progression
  cannot see. A card whose results are only qualitative, or whose table is an
  image nobody can read with certainty, is still a valid addition with no score
  rows.
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
