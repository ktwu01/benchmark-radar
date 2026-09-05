# Benchmark Radar v0.9.0 technical report

This directory tracks the source and deposit metadata for the citable Benchmark
Radar technical report. The report evaluates software version 0.9.0, its full
collection and publication pipeline, all 37 public collection sources, the
1,242-entry web search surface, and the public data snapshot dated 2026-08-29
at frozen audit commit `98c7de3`. The current issue #455 agent-weakness study
is a separate 2026-09-01 analysis layered onto the draft report; it does not
recompute or replace the frozen v0.9.0 core counts.

Rebuild the issue #455 agent-weakness inputs from a clean checkout after
installing the development dependencies and ReportLab. Run the full repository
verification sequence before the issue-specific analysis, then keep the focused
tests as an additional check:

```bash
uv run ruff check .
uv run ruff format --check .
uv run benchmark-radar normalize-external
uv run benchmark-radar classify
uv run benchmark-radar build-data-release
uv run pytest -q
uv run pytest -q tests/test_agent_weakness_study.py tests/test_system_evaluation_report.py
uv run python scripts/analyze_agent_weaknesses.py \
  --source data/agent_weakness_evidence.yml \
  --json-output output/analysis/agent-weakness-study.json \
  --csv-output output/analysis/agent-weakness-coded-table.csv
uv run --with reportlab python scripts/build_system_evaluation.py \
  --doi 10.5281/zenodo.22167102 \
  --output output/pdf/benchmark-radar-technical-report-next-draft.pdf
```

The draft builder must write
`output/pdf/benchmark-radar-technical-report-next-draft.pdf` and leave the frozen
`output/pdf/benchmark-radar-technical-report-v0.9.0.pdf` artifact untouched. The
reserved DOI appears in the PDF itself. Upload only the reviewed release PDF to
the Zenodo record described by `zenodo-metadata.json`, then publish the record.

The published v0.9.0 PDF is frozen. Do not overwrite it when preparing a new
manuscript or adding a contributor. Build the working next draft explicitly:

```bash
python3 scripts/build_system_evaluation.py \
  --next-draft \
  --doi 10.5281/zenodo.22167102
```

This writes `output/pdf/benchmark-radar-technical-report-next-draft.pdf` and
uses the draft byline and contributor affiliations. Do not change the frozen
`zenodo-metadata.json` for draft work; prepare release metadata only when the
next report version is approved for deposit.

The draft byline is provisional until the contributor has reviewed and approved
the integrated manuscript, supplied a contribution statement, and accepted
accountability for the work, as described in
`docs/designs/technical-report-collaboration-scoring.md` and issue #447.

The software remains under the MIT License. The technical report and original
editorial content use CC BY-NC 4.0. Commercial republication, resale, paid
newsletters, dataset packaging, or commercial product integration requires
prior written permission from Koutian Wu. Third-party source material remains
under its original terms.

The frozen v0.9.0 core counts come from these versioned files at commit
`98c7de3` with cutoff `2026-08-29`:

- `site/data/radar.json` (generated from the dated snapshots)
- `site/data/benchmark-index.json` (generated from normalized catalogs)
- `data/snapshots/2026-08-29.json`
- `data/model_cards.yml`
- `data/benchmark_scores.yml`
- `site/data/models.json`
- `config.yml`

The current issue #455 study is reported separately from:

- `data/agent_weakness_evidence.yml`
- `docs/technical-report/agent-weakness-blinded-sample.md`
- `docs/technical-report/agent-weakness-independent-review.md`
- `output/analysis/agent-weakness-study.json`
- `output/analysis/agent-weakness-coded-table.csv`

Regenerate and review the report when any of those inputs, the issue #455 study
artifacts, or the report text changes.
