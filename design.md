# Design principles

Benchmark Radar helps people find benchmarks, understand what changed, and
inspect the evidence. Every part of the product should make one of those tasks
easier.

## Start with the reader's question

The first screen should answer:

- What am I looking at?
- Why does it matter?
- What should I inspect next?

Lead with the result or insight. Counts, methods, and pipeline details support
the answer; they are not the answer.

Design for two readers at once. A newcomer should understand the point without
knowing benchmark jargon. An expert should be able to inspect sources,
protocols, dates, and limitations.

## Choose the simplest sufficient design

Use the fewest concepts, controls, and layers needed to answer the reader's
question.

Before adding something, ask whether an existing page, filter, or detail view
already does the job. A new topic does not need a new tab. A collected field
does not need a card. An available count does not need a badge.

Each element must earn its place through a clear user task. Remove duplicate
labels, repeated caveats, decorative precision, and actions that are already
available in context.

Simplicity must not hide evidence. Provenance, uncertainty, protocols,
accessible names, downloads, and citations are part of the product's trust.

## Give each surface one job

| Surface | Primary job |
| --- | --- |
| Today | Explain what appeared recently and why it matters |
| Search | Find possible benchmarks across the corpus |
| Leaderboard | Compare attention, adoption, or reported scores as separate modes |
| Trends | Show change across comparable time windows |
| Blog | Publish dated, shareable analysis |
| CLI and Skill | Let people and agents query local data |

One answer or action should dominate each surface. Secondary controls should
remain available without competing with it.

## Treat navigation as scarce space

Global navigation is for frequent, distinct tasks. A useful route does not
automatically deserve a tab.

Prefer a filter, mode, contextual link, or detail view when the task already
has a home. Rubrics, methods, citations, contact, and contribution links should
appear where readers need them.

Removing a route from global navigation does not require deleting the route.
Demote it first when it still has expert or contextual value.

Navigation is also state. Direct links must work, one state should have one
active indicator, and Back and Forward should restore meaningful states.

## Put insight before detail

Show a concise answer first, then offer the evidence and method behind it.
Expansion should be clear and reversible.

Mobile layout must preserve the surface's primary task. On Today, matching
results come first; the daily briefing follows as context for the scan date.

Explain a shared limitation once near the affected group. Do not repeat “not
comparable” or “not enough history” in every card.

## Keep evidence layers distinct

| Layer | Meaning | What the interface must show |
| --- | --- | --- |
| Radar | Daily discovery evidence | Source and date; label it as a signal |
| Catalog | Normalized external records | Provenance and source identity |
| Curated measurements | Reviewed adoption and score history | Protocol, date, and comparability |

Search returns candidates, not recommendations. Recent attention, model-card
adoption, and model scores answer different questions and must not share an
unlabelled ranking.

Show empty, partial, stale, and incomparable states plainly. Do not replace
missing evidence with guessed content.

## Load only what the current task needs

A view should respond without downloading unrelated data. Opening a route or
dialog must not wait for the complete research corpus.

Give each surface a bounded payload and a visible failure state. Tables and
charts may scroll inside their containers; the page itself must not overflow
horizontally.

## Keep one source of truth

Server-rendered pages and hydrated pages must show the same facts. Shared
navigation, citations, labels, and public metadata should come from one owner
or have parity tests.

Do not fix source-data problems in generated files. Do not copy the same public
fact into Python, JavaScript, and Markdown without naming its canonical source.

## Measure tasks, not clicks

Use behavior data to learn whether a surface helps readers finish a task. For a
navigation destination, review:

- intentional selections;
- direct visits;
- useful next actions;
- quick returns, errors, and loading time;
- differences between mobile and desktop.

Set the observation window and decision threshold before reading the results.
Low use may justify removing an item from global navigation, but it does not
make a trust-critical or direct-linked capability useless.

Use one analytics system. Review its audience policy, consent requirements,
data collection, and masking settings before relying on its data.

## Require evidence for additions

Before adding a field, control, model, route, or layer, name:

- the user question it answers;
- evidence that the problem exists;
- the source of truth;
- what success looks like;
- its mobile, accessibility, performance, and trust costs;
- what it replaces if it competes for attention.

Defer fields with no owner for collection, display, and maintenance.

## Review checklist

Before merging a user-facing change, check:

- Can a newcomer explain the page after seeing the first screen?
- Can an expert reach the provenance, protocol, and caveats?
- Is one answer or action clearly primary?
- Did a new choice replace or demote an old one?
- Are Radar, Catalog, adoption, and scores still distinguishable?
- Do the first response and hydrated page agree?
- Does it work at 320px with long content, keyboard navigation, direct URLs,
  Back and Forward, slow loading, and empty or error states?
- Does it load only the data needed for the current task?
