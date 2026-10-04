# Capability-theme coverage of the agent-benchmark literature

*Draft section for the Benchmark Radar technical report — evidence backing:
`analyze.py` (reproducible from two public inputs: the XBsleepy digest index
and the radar's committed snapshots). All numbers below are from the digest
index of 2026-09-13.*

---

## What the digest adds: capability themes over record types

The radar's own snapshot taxonomy classifies records by **what they are** —
of 24,570 category sightings across the committed snapshots, 9,439 are
`benchmark`, 6,744 `evaluation`, 6,240 `dataset`, 2,021 `agentic`, and 126
`data_quality`. This answers "is this a benchmark?" but not "what does this
benchmark test?". The XBsleepy digest supplies exactly that second layer: a
two-stage classifier tags each agent-benchmark paper with capability themes
(planning, tool-use, safety, coding, multimodal, memory, and twelve more),
and the radar ingests those tags as source-native categories. The two layers
are complementary rather than overlapping, and the `/themes/` browse page is
the reader-facing join between them.

## Distribution

The digest corpus spans 1,132 agent-benchmark papers announced between
2026-01-01 and 2026-09-10, carrying 1.94 theme labels on average. Coverage
is heavily concentrated: the top three themes — planning (431 papers, 38% of
papers), tool-use (407, 36%), and safety (298, 26%) — account for 52% of all
theme labels. The strongest co-occurrences are planning+tool-use (171
papers), safety+tool-use (124), and planning+safety (119): the literature's
center of gravity is LLM agents that plan and act in software environments,
measured for capability and for safety. A mid tier follows (coding 180,
multimodal 165, memory 151, multi-agent 127, science 94), and the tail thins
fast: web (48), conversation (44), computer-use (41), embodied (38),
workplace (20), mobile (14), and recursive self-improvement (3).

## Gaps

The sparse end of the distribution is arguably its most decision-useful
signal. Embodied and robot-agent evaluation — benchmarks where an agent acts
on a physical world through a robot rather than a browser or a terminal —
amount to 38 papers, 3% of the corpus, against 431 for planning. Workplace,
mobile, and recursive-self-improvement coverage is thinner still. For a
reader deciding where a new benchmark can matter, these are the open areas;
for the radar, they are the themes where a new digest or source would add
the most coverage.

## Trend

Monthly arrivals of tagged papers grew steadily from January (31 papers
carrying the planning label) to a May peak (91), and remained elevated
through August. The September figures are partial at the time of writing.
Nothing in the trend suggests saturation of the corpus itself: the digest
kept finding new agent benchmarks at a rate of roughly 100–140 papers per
month across the whole window.

---

*Reproducibility: `python3 docs/analysis/theme-coverage/analyze.py <digest
index.json> <snapshot dir> <out dir>` — no credentials, no network beyond
the two public inputs. Figures: `themes_coverage.svg`.*
