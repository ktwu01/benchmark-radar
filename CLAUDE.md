# Repository Instructions

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

### Preserve visual identity during simplification

- Separate redundant text from visual identity. You may remove a person's name
  or handle when the destination already identifies that person. Keep the
  platform logo, brand treatment, badge shape, and platform label that help a
  reader recognize the link.
- Preserve the component type and its established style. Do not turn a badge,
  icon, or other visual affordance into a plain text link unless the task asks
  for that redesign.
- Keep destination specificity in the link target. A generic platform label
  may link to a specific person's profile; the visible label does not need to
  repeat the person's identity.
- Before deleting an element, classify its role: content, visual identity,
  interaction, or destination. Remove redundant content only. Keep the visual
  identity, interaction, and destination intact unless the request says to
  change them.

Examples:

- X: keep the original X badge and link it to `https://x.com/ktwu01`. Do not
  replace the badge with the plain handle `@ktwu01` or the person's name.
- LinkedIn: keep the original LinkedIn badge with the visible label `LinkedIn`
  and link it to the specific profile. Do not put `Koutian Wu` in the badge or
  use badge text such as `LinkedIn-Koutian%20Wu`.
- Google Scholar: keep the badge label `Google Scholar` and link it to the
  specific Scholar profile. Do not use badge text such as
  `Google%20Scholar-Koutian%20Wu`.

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

## Pull request merges

- Do not squash-merge pull requests.
- Merge pull requests with a merge commit so Git preserves branch ancestry and recognizes the branch as merged.

## Before opening a pull request

- Run the full CI sequence locally and get it passing before opening a PR. Do
  not open one against a red local run.
- Run it against a clean checkout (`git worktree add --detach <tmp> <branch>`),
  not your working copy. Generated files such as `site/data/radar.json`,
  `site/data/benchmark-index.json` and `site/data/benchmarks/` are gitignored
  and absent on a fresh CI runner, so a working copy that happens to have them
  on disk passes tests that CI fails.
- The sequence is the one in `.github/workflows/ci.yml`, in order:

      ruff check .
      ruff format --check .
      benchmark-radar normalize-external
      benchmark-radar classify
      pytest -q

- All five must pass. `ruff format --check` runs before everything else, so a
  formatting slip fails the run before a single test executes. Both generators
  run before `pytest` and in that order: `classify` reads the shard directory
  `normalize-external` writes, and the corpus-backed tests skip themselves when
  either artifact is missing.
