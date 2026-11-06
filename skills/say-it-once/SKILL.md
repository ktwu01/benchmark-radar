---
name: say-it-once
description: Find and remove repeated or meaningless elements on a Benchmark Radar page, panel, card, README, or brief. Use when the maintainer asks to declutter, remove duplicates, or review a UI surface, and before opening a PR that adds a visible element.
---

# Say it once

Each fact a reader sees appears in one place on the screen. A second copy costs
space above the answer and makes the reader check whether the two copies differ.
`design.md` holds the rules; this skill is the procedure for applying them.

## Steps

1. Open the rendered surface in Chromium at 1450px and at 390px. Use the built
   site from a clean worktree, or the live site for an unchanged surface. Do not
   judge from source alone: most past duplicates were assembled at runtime.
2. List every element above the main answer (chart, ranking, list), top to
   bottom. For each, write the one fact it carries.
3. Group the elements by fact. A group with two or more members is a candidate.
   Also flag any element whose fact is unreadable alone, such as a bare number
   with no label (`94.6` above a chart that already says `Best reported score: 94.6`).
4. For each candidate, keep the copy in the place the reader looks for that fact,
   and remove the others. Before removing, check that the copy is not the only
   one that:
   - carries state or a control: keyboard, phone width, Back and Forward, the URL;
   - carries an accessible name. Move that text into `aria-label`, as `eb1b872`
     did, instead of dropping it;
   - is unique evidence: provenance, a caveat no other element states, a citation.
5. Machine copies are not duplicates. Meta description, `og:` tags, JSON-LD,
   feeds, and `datePublished` serve crawlers and previews (`cbda65c`). Leave them.
6. Check order as well as count. A block shared across surfaces follows each
   surface's job (`design.md`, "A shared block follows the surface's job").
7. Take before and after screenshots at the same viewport. For each removal,
   name in the commit message the element that already says it: "X already says
   Y".

## Patterns from this repo's history

| Commit | Repeated element | Kept |
| --- | --- | --- |
| `8741e16` (#298) | Eyebrow, title, source chip and a second heading: four elements for two facts, 150px above the chart | One title and one subline |
| `cbda65c` | Eyebrow "Daily brief", a date line, fixed tags, and a clipped lede above its full text | The title; the clipped text stays in meta and the feed |
| `eb1b872` | Number, "/ 100", bar, caption, and rubric mark for one score | Number, bar, mark; the caption moves to `aria-label` |
| `69a261d` | Owner in the title and in the byline | Owner once, as "By" |
| `7fa1725` | A Code link that opens the same repository as the rail | Skipped only when it opens the same kind of page on the same site |
| `2c21c37` | A dataset card that repeated the footer's Data link | The footer link |
| `887ae5f` | An info mark beside an already-blue link | The blue |
| `ca7c1cc` (#976) | "About {name}" under an `<h1>` naming the benchmark | The `<h1>` |

## Constraints

- Never remove a record, a score row, or a count that only one element shows.
  The full-corpus rule in `principle.md` outranks tidiness.
- Keep crawlable links and page titles. State the SEO effect in the PR
  (`maintainer-review.md`, question 7).
- One surface per PR. File other findings as issues.
