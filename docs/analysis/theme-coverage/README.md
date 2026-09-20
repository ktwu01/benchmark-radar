# Theme-coverage analysis

Report-ready evidence for the Benchmark Radar technical report (issue #447
collaboration call): what the XBsleepy digest's capability-theme taxonomy
adds to the radar's record-type categories, where agent-benchmark activity
concentrates, and which capability areas remain near-empty.

## Contents

- `analyze.py` — reproducible analysis. Two public inputs: the digest's
  `docs/data/index.json` and the radar's committed `data/snapshots/`. Writes
  the markdown tables and an SVG bar chart. No credentials, no network.
- `coverage.md` — generated tables (theme distribution, record-type vs
  capability layers, concentration/gaps, monthly arrivals).
- `themes_coverage.svg` — papers per capability theme.
- `REPORT_SECTION_DRAFT.md` — draft technical-report section built on those
  numbers.

## Reproduce

```bash
python3 analyze.py <path to index.json> <path to data/snapshots> <out dir>
```
