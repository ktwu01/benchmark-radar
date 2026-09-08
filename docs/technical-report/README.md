# Benchmark Radar technical report

The manuscript, PDF, figures, and Overleaf instructions live in
**[benchmark-radar-paper](https://github.com/ktwu01/benchmark-radar-paper)**,
mounted here as the `latex/` Git submodule.

## Frozen paper data: v0.11.0

All paper data is cut off at the
[v0.11.0 release](https://github.com/ktwu01/benchmark-radar/releases/tag/v0.11.0),
software commit `8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`, with discovery
through **2026-09-07**. The release includes the frozen input archive, checksums,
and paper PDF. Follow the [paper's cutoff rule](latex/README.md#data-cutoff-rule-v0110).
Routine paper edits must not incorporate newer inputs or advance the cutoff.
The existing audit remains valid for unchanged inputs.

## Reproduce the paper's numbers with Python

The exporter stays in this software repository. It reads
`site/data/benchmark-index.json` and `site/data/radar.json`, then writes directly
to `docs/technical-report/latex/figure-data.tex` inside the paper submodule.

Use a clean checkout at the release commit above, then rebuild the inputs using the
[clean-checkout CI sequence](../../AGENTS.md#before-opening-a-pull-request).
From that Benchmark Radar checkout's root:

```bash
git submodule update --init --recursive
git -C docs/technical-report/latex switch -c paper/reproduce-v0.11.0
python scripts/export_report_figure_data.py
python scripts/export_report_figure_data.py --check
git -C docs/technical-report/latex diff -- figure-data.tex
```

The export contains the data cutoff, numerical macros, and SHA-256 hashes of the
two input JSON files. `--check` recomputes the export and fails if the exported
file differs from those local inputs. Do not hand-edit the numbers or hashes.
The script does not update manuscript prose or PDF files.

The paper's main findings use its `scripts/audit_findings.py` exporter, which
reads the same frozen index and every detail shard. Documentation, score, and
date analyses retain the full source-record population; percentage-scale or
model-report eligibility must not determine which records survive. Run both
paper audits in `--check` mode, as documented in the paper README. The generated
CSV and JSON provide all records and their available measurements.

Verify the exported hashes against the paper README and preserve the release
cutoff. For manuscript edits, rebuild and inspect the figures and manuscript using the
[paper's build instructions](https://github.com/ktwu01/benchmark-radar-paper#build-locally).
Commit and push the reviewed changes in the paper repository. Keep paper-only
work there by default. Update Benchmark Radar's `docs/technical-report/latex`
submodule pointer only when the user explicitly requests it, after pushing the
reviewed paper commit.
