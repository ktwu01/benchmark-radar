# Design principles

The full-corpus coverage requirements in [principle.md](principle.md) govern
every benchmark-facing surface. Missing measurements must not silently turn
1,259+ benchmark records across 4+ sources into a chart of a few dozen.

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
| Leaderboard | Compare Benchmark Frontier, recorded score counts and documentation |
| Saturation | Find benchmarks and inspect their reported scores over time |
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

## Keep page titles close and quiet

[Issue #581](https://github.com/ktwu01/benchmark-radar/issues/581) sets the
Leaderboard heading as the spacing baseline. Every primary page title should
start at the same compact distance below the menubar. Switching sections must
not make the title jump down the page. Controls beside a title align to the top;
a taller filter must not vertically center the title lower than its peers.

Good:

- `Leaderboard`, `Saturation`, `Trend`, and the Blog title share one top offset.
- The Blog title uses the same scale as `Saturation`, even when it is longer.
- `Trend` identifies the Trends page without a second label or open caveat.

Bad:

- Leaving the generic page padding on Saturation, Trends, or Blog while
  Leaderboard uses compact spacing.
- Stacking `Recent activity`, `Signals over time`, and “Counts describe
  discovery volume, not scientific quality” before the reader reaches the
  chart.
- Stacking `Daily brief`, the Blog title, a descriptive paragraph, and a
  collection-day count when the title already identifies the page.

Use one title when one title is enough. Eyebrows, decks, counts, and caveats do
not belong in the open title area merely because the data exists. If page-level
coverage context remains necessary, put it in one closed, keyboard- and
touch-accessible `(i)` immediately to the right of the title. Give the control
an accessible name and keep its contents out of the layout while closed. A
loading failure or empty state remains visible; it must never be hidden in the
note. Figure-specific coverage and method text still follow the figure-caption
rule below.

Mobile layout must preserve the surface's primary task. On Today, matching
results come first; the daily briefing follows as context for the scan date.

Explain a shared limitation once near the affected group. Do not repeat “not
comparable” or “not enough history” in every card.

## One catalog with typed evidence

Model reports, OpenCompass Hub, Artificial Analysis and LLM Stats contribute
benchmark records through the same contract. Source names identify provenance;
they do not grant priority in ranking or access to a chart.

| Evidence | What the interface must preserve |
| --- | --- |
| Benchmark record | Source identity, name and reviewed identity links |
| Score observation | Value, model ID, units, protocol, date basis and citation |
| Source document | Document identity, type, URL and benchmark references |
| Daily discovery observation | Source, date and the mention or release observed |

Search returns candidates, not recommendations. Recent attention, model-card
adoption, and model scores answer different questions and must not share an
unlabelled ranking.

Show empty, partial, stale, and incomparable states plainly. Do not replace
missing evidence with guessed content.

## Show all the data, unify the vocabulary

A benchmark is a benchmark. The corpus holds one benchmark population assembled
from several sources, not a first-class set and a lesser one. Any surface that
counts, ranks, charts, or searches benchmarks covers the whole population by
default.

Never call a benchmark "external" in the interface. That word describes where a
record was collected, not what the thing is, and it invites a reader to discount
most of the corpus. Name the source instead: "Artificial Analysis", "LLM Stats",
"OpenCompass Hub", "Model reports". Preserve the evidence fields above for
each source. Missing measurements do not remove benchmark records.

Each figure and browser starts from the complete catalog and states its own
filter scope. Leaderboard's slider filters only Benchmark Frontier. Saturation
shares that slider for browsing; a search queries the full catalog without
changing the cutoff. Clearing the query restores filtered browsing. Prefer the
count and unit the reader can already see over a private subset.

When a measurement cannot span the population, restrict the calculation, not
the represented records. Keep benchmarks with unknown or incompatible values
visible in a labelled area and make each one inspectable. User filters may
narrow the visible records, but the full, matching, unknown, and hidden counts
must reconcile. A footnote about omitted records does not replace showing them.

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
- Are Radar, Catalog, adoption, and scores still distinguishable by label,
  while every one of them still appears in counts, charts, and search?
- Does any user-facing string say "external"? Name the source instead.
- Do the figure and the list beside it cover the same rows and agree on totals?
- Do the first response and hydrated page agree?
- Does it work at 320px with long content, keyboard navigation, direct URLs,
  Back and Forward, slow loading, and empty or error states?
- Does it load only the data needed for the current task?

## Figure captions

Put legends below their figure. Leave only the keys needed to read its colors
and shapes expanded. Collect counts, coverage, exclusions and method text in
one closed information note beside the legend. Use [principle.md](principle.md)
for the full-corpus, missing-data and Frontier filter rules.

## Shared visual system

The production theme lives in `site/assets/design-system.css`. Preserve the original
radar mark. Use a #f6f7f9 canvas, white surfaces, #202733 body text, #55606f
secondary text, and #2b5fa8 interactive accents. Body text is 16px, controls
14px, metadata at least 13px; use the system sans-serif stack and tabular numerals.

The header comes from `site/index.html` on dashboard and generated pages. Keep
44px navigation and utility controls, fixed gaps, and stable scrollbar space.
Below 1280px, use a brand/utilities row and a horizontally scrolling navigation
row. Selection changes color rather than geometry. All page titles share the
same compact top spacing.

Use 4/8/12/16/24/32/48px spacing, 8px control radii, and 10px panel radii.
Primary actions are blue with white text; secondary actions have white surfaces
and neutral borders. Footer, export, pagination, and reset controls share these
rules, including keyboard focus and disabled states.

Research fields map exact source tags and may overlap. Secondary directions
collapse on mobile. The browser reads the shared index and loads evidence shards
only when requested. Saturation search pauses field filters as well as its score
cutoff. Existing public routes and raw data downloads remain available.
