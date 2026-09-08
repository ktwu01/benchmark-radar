# Benchmark Radar technical report

The [paper repository](https://github.com/ktwu01/benchmark-radar-paper) holds the
LaTeX source, built PDF, and all figures. It is mounted here as the `latex/` Git
submodule, pinned to a reviewed paper commit. This directory keeps the software
audit notes and frozen deposit metadata. `latex/main.tex` remains the single
source of manuscript prose; edit it directly.

For Overleaf setup and the writing workflow, see the
[paper README](https://github.com/ktwu01/benchmark-radar-paper#write-together-in-overleaf).
Overleaf sync is manual and updates the paper repository. Updating this
repository requires a separate PR that advances the submodule pointer.

## Get the paper

New clones should use `git clone --recurse-submodules`. In an existing checkout
or a new clean worktree, run this from the repository root:

```bash
git submodule update --init --recursive
```

The submodule checks out a specific commit. Before editing it locally, create a
branch inside it with `git switch -c paper/my-revision`. Commit and push the
paper changes there first, then commit the `docs/technical-report/latex` pointer
in this repository. The paper README includes the update commands.

The current manuscript evaluates software version 0.10.0, its full collection and
publication pipeline, the public collection sources, the 1,283-entry web search
surface, and the public data snapshot dated 2026-09-06.

## Build

Requires a TeX distribution with `latexmk` (TinyTeX or TeX Live).

```bash
cd docs/technical-report/latex
make
```

That writes `latex/main.pdf`, tracked in the paper repository so the report
reads directly on GitHub. Commit the rebuilt PDF alongside any change to `main.tex`,
then update the parent repository's submodule pointer.

## arXiv upload

```bash
cd docs/technical-report/latex
make arxiv
```

That writes `arxiv.tar.gz`. arXiv runs no BibTeX pass of its own, so the tarball
ships the built `main.bbl` rather than `references.bib`, together with
`figure-data.tex` and the native figure sources. All images, including the
use-case screenshots, live in the paper repository's `figures/` directory, so the
package needs no parent-repository files.
Unpack the tarball and build it once on its own before uploading.

## Figures

The four PDF figures in `latex/figures/` now have native TikZ sources with
matching `.tex` names. `make` rebuilds them before the manuscript; `make figures`
builds just those four PDFs. Their shared styles live in
`figures/figure-style.tex`. TeX Live's `pgf` (TikZ) and `helvet` packages are
required in addition to the manuscript's existing dependencies. No ReportLab,
PDF-page extraction, or downloaded ZIP is needed.

`figure-data.tex` is a checked-in, dated export of numbers, shared by the figures
and the corresponding manuscript counts. Normal builds use that file so a
manuscript rebuild does not silently pick up a new corpus. To refresh it, first
run the six-step clean-checkout CI sequence in `AGENTS.md`, then:

```bash
python scripts/export_report_figure_data.py
python scripts/export_report_figure_data.py --check
make -C docs/technical-report/latex
```

Review the cutoff, related prose and tables, all four figures, and the rendered
manuscript together; commit `figure-data.tex`, the four figure PDFs, and
`main.pdf` with the source changes. The exporter writes only numbers and input
hashes, never manuscript prose. Missing inputs and incomplete corpus counts fail
visibly. Source-composition bars show the five largest normalized discovery
labels plus every remaining observation; these are not benchmark catalog source
counts. `make clean` preserves the tracked PDFs and removes build intermediates.

The reconstruction follows the legacy drawing routines in commit `6270ff3` and
the checked-in PDFs. The supplied `Benchmark_Radar (1).zip` contained PDFs but no
drawing sources. Rebuilding the catalog confirmed 1,283 records across four
sources: the older 1,259 figure omitted 24 model-report benchmarks without scores,
and the unused search illustration still said 1,242. Both now use the same full
catalog count as the manuscript. The search illustration remains unembedded.

The graphical abstract (`figures/abstract_overview.png`) is an authored raster
asset, not one of these four generated diagrams.

The use-case screenshots are included in `latex/figures/` so Overleaf and
standalone builds work. The original evidence remains in `assets/use-case-492/`.

## Deposit

The published v0.9.0 PDF at
`output/pdf/benchmark-radar-technical-report-v0.9.0.pdf` is frozen. It is the
artifact behind DOI 10.5281/zenodo.22167102 and must stay byte-for-byte
unchanged. Nothing in this repository writes to that path; do not overwrite it
by hand.

A new deposit copies the reviewed `latex/main.pdf` to
`output/pdf/benchmark-radar-technical-report-v<version>.pdf` and updates
`zenodo-metadata.json` in the same change. Prepare release metadata only when a
report version is approved for deposit.

## Byline and credit

The byline is provisional until each contributor has reviewed and approved the
integrated manuscript, supplied a contribution statement, and accepted
accountability for the work, as described in
`docs/designs/technical-report-collaboration-scoring.md` and issue #447.

## Historical score audit

`saturation-audit-6.2.json` records an analysis used by an earlier manuscript.
Its arithmetic can be reproduced from the score archive and model-report
registry with:

```bash
python3 -m benchmark_radar.saturation_audit
```

The current paper removes the saturation appendix. Matching instrument/protocol
labels and report dates does not establish identical experimental conditions or
independent repeated evaluations. For example, the HMMT group combines Flash
and Pro scores shown together in the
[DeepSeek-V4 report](https://arxiv.org/html/2606.19348); that report also specifies
a different math prompt for Pro-Max. The historical helper and artifact remain
available for inspection, but reproducing their numbers does not validate a
protocol-controlled saturation claim. They no longer supply tables to the paper.

## Audited inputs

The report derives its quantitative claims from versioned source evidence and
the catalog artifacts rebuilt from it:

- `site/data/radar.json` (generated from the dated snapshots)
- `site/data/benchmark-index.json` (generated from normalized catalogs)
- `data/snapshots/2026-09-06.json`
- `data/model_cards.yml`
- `data/benchmark_scores.yml`
- `site/data/models.json`
- `config.yml`

Rebuild and review the report when these inputs or the report text change.

## Licensing

The software remains under the MIT License. The technical report and original
editorial content use CC BY-NC 4.0. Commercial republication, resale, paid
newsletters, dataset packaging, or commercial product integration requires
prior written permission from Koutian Wu. Third-party source material remains
under its original terms.
