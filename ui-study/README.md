# Research explorer and shared site design proposal

Readers need to move from a research field to its benchmarks and inspect the
underlying scores without relearning navigation on each page. This opt-in
whole-site build proposes a shared header, two-level research filters, and a
consistent typography, spacing, and button system.

[Hosted design review](https://benchmark-radar-study.lynnzc.chatgpt.site)
is a September 18 snapshot. Local builds use this checkout's generated data.

## Scope

- Today, Leaderboard, Saturation, Trends, blog, CLI, citation, and record pages
  share the original radar logo and one navigation template.
- Explore starts with every source record, groups exact source tags into fields
  and research directions, and exposes source evidence, scores, and export.
- Leaderboard and Saturation retain field selection in the URL.
- Neutral surfaces, blue actions, consistent 44px header controls, and compact
  mobile disclosures address alignment and readability problems in the study.

This is a reviewable design proposal, not a production deployment switch.
It does not change the existing Pages workflow, canonical generators, query
service, source data, or root design principles. Its generated output is ignored.
The existing relationship explorer is retained at `/relationships/` within this
build; `/explore/` is the proposed field browser. That route change needs review
before production adoption.

## Build and preview

Install the repository's development dependencies as described in CONTRIBUTING.md,
then run from the repository root:

```sh
benchmark-radar normalize-catalog
benchmark-radar classify
benchmark-radar build-data-release
python ui-study/scripts/assemble_fullsite.py site
python -m http.server 8000 --directory ui-study/dist
```

Open `http://localhost:8000`. Run the builder again after regenerating the inputs;
it recreates only `ui-study/dist`. Do not point the source argument at that output.
The builder reads the complete index and every detail shard. Missing shards fail
the build; missing scores, dates, or model counts remain unknown.

## Design and ownership

See [design.md](design.md) for the proposed component rules. The repository's
[design principles](../design.md) and [corpus rules](../principle.md) take
precedence. `design/header.html` owns shared navigation, `design/study.css`
owns the layered theme, and `explorer-source/` owns the field browser.

The assembly adapter intentionally keeps the proposal separate from existing
source templates. It currently applies transformations to generated HTML and
JavaScript. Before production adoption, move approved changes into their owning
templates and modules, preserve established routes, and remove the adapter.

## Validation

Run the full clean-checkout CI sequence in AGENTS.md. Optional DOM and stylesheet
checks can then run against the generated study:

```sh
npm ci --prefix ui-study
node ui-study/scripts/verify-design.cjs
node --experimental-vm-modules ui-study/scripts/verify-interactions.cjs
```

These checks cover shared headers, catalog ID parity, eligible Frontier marks,
field selection, navigation history, score details, and language preference.
They do not replace visual review at desktop and mobile widths. In particular,
review 320px layouts, keyboard focus, long labels, and the resource menu.

The study omits analytics and uses a losslessly compressed discovery archive.
Archive-wide queries require browser `DecompressionStream` support and show a
visible error when unavailable. Name filtering in Explore is a literal catalog
filter, not a replacement for QueryService search or a suitability ranking.
