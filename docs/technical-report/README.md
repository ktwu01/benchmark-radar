# Benchmark Radar technical report

The manuscript, PDF, figures, and Overleaf instructions live in
**[benchmark-radar-paper](https://github.com/ktwu01/benchmark-radar-paper)**,
mounted here as the `latex/` Git submodule.

## Refresh the paper's numbers with Python

The exporter stays in this software repository. It reads
`site/data/benchmark-index.json` and `site/data/radar.json`, then writes directly
to `docs/technical-report/latex/figure-data.tex` inside the paper submodule.

First rebuild and audit the inputs using the
[clean-checkout CI sequence](../../AGENTS.md#before-opening-a-pull-request).
From that Benchmark Radar checkout's root:

```bash
git submodule update --init --recursive
git -C docs/technical-report/latex switch -c paper/refresh-figure-data
python scripts/export_report_figure_data.py
python scripts/export_report_figure_data.py --check
git -C docs/technical-report/latex diff -- figure-data.tex
```

The export contains the data cutoff, numerical macros, and SHA-256 hashes of the
two input JSON files. `--check` recomputes the export and fails if the exported
file differs from those local inputs. Do not hand-edit the numbers or hashes.
The script does not update manuscript prose or PDF files.

Review the changed numbers and cutoff, update affected prose, and rebuild and
inspect the figures and manuscript using the
[paper's build instructions](https://github.com/ktwu01/benchmark-radar-paper#build-locally).
Commit and push the reviewed changes in the paper repository first, then commit
the updated `docs/technical-report/latex` submodule pointer in Benchmark Radar.
