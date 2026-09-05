# Benchmark Radar v0.9.0 technical report

This directory tracks the source and deposit metadata for the citable Benchmark
Radar technical report. The report evaluates software version 0.9.0, its full
collection and publication pipeline, all 37 public collection sources, the
1,242-entry web search surface, and the public data snapshot dated 2026-08-29.

Build the PDF after installing ReportLab:

```bash
python3 scripts/build_system_evaluation.py \
  --next-draft \
  --doi 10.5281/zenodo.22167102
```

The builder writes the working
`output/pdf/benchmark-radar-technical-report-next-draft.pdf`. The reserved DOI
appears in the PDF itself. Review the draft before any deposit.

The published v0.9.0 PDF is frozen. Do not overwrite it when preparing a new
manuscript or adding a contributor. Replacing it requires an explicit opt-in:

```bash
python3 scripts/build_system_evaluation.py \
  --overwrite-frozen \
  --doi 10.5281/zenodo.22167102
```

The next-draft build uses the draft byline and contributor affiliations. Its
section 6.2 table is reproduced from
`docs/technical-report/saturation-audit-6.2.json`, which is generated from the
curated score archive and model-card registry with:

```bash
python3 -m benchmark_radar.saturation_audit
```

Do not change the frozen `zenodo-metadata.json` for draft work; prepare release
metadata only when the next report version is approved for deposit.

The draft byline is provisional until the contributor has reviewed and approved
the integrated manuscript, supplied a contribution statement, and accepted
accountability for the work, as described in
`docs/designs/technical-report-collaboration-scoring.md` and issue #447.

The software remains under the MIT License. The technical report and original
editorial content use CC BY-NC 4.0. Commercial republication, resale, paid
newsletters, dataset packaging, or commercial product integration requires
prior written permission from Koutian Wu. Third-party source material remains
under its original terms.

The report derives its quantitative claims from these versioned files and from
the current README and report documentation:

- `site/data/radar.json` (generated from the dated snapshots)
- `site/data/benchmark-index.json` (generated from normalized catalogs)
- `data/snapshots/2026-08-29.json`
- `data/model_cards.yml`
- `data/benchmark_scores.yml`
- `site/data/models.json`
- `config.yml`
- `docs/reports/ai-benchmark-landscape-report.md`
- `docs/source-probe-evidence.md`

Regenerate and review the report when any of those inputs or the report text
changes.

## Independent section 6.2 reproduction

On 2026-09-05, a Codex-assisted maintainer review regenerated the audit from the
two canonical YAML files. It reproduced four counts: eight raw near-ceiling
readings; no raw-best setup spanning two dates; four benchmarks with a different
repeated setup; and one of those four within five points. The review also checked
the HMMT sample against Table 7 of the
[DeepSeek-V4 primary report](https://arxiv.org/html/2606.19348): HMMT 2026 Feb,
Pass@1, Think Max is 94.8 for DeepSeek-V4-Flash and 95.2 for
DeepSeek-V4-Pro. Those values match the `deepseek_v4_technical_report` and
`deepseek_v4_model_card` rows in `data/benchmark_scores.yml`.
