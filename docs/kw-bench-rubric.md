# KW-Bench Capability Rubric

> **This file is the source of truth for the KW-Bench rubric in benchmark-radar.**
> The rubric was first drafted in `ktwu01/vendor-data-qc`. This repository no
> longer defers to that copy.
>
> **Version 0.2 merges two scales into one.** Version 0.1 had six levels, L0 to
> L5. The Levels of benchmarks post and the Cohere Labs talk had twelve. Version
> 0.2 is one scale, L0 to L12, ordered by how hard the tested ability is
> (issue #1345). Labels made under v0.1 keep their version; see the last section.
>
> **Status in this repository: dormant.** No classifier output is published.
> Assigning a level means reading a task and its verifier and judging which
> ability a passing score requires. That is a semantic judgment, and the
> deterministic pattern-matching classifier in `kw_bench.py` cannot make it: two
> rounds of adversarial review found 11 and then 7 misclassifications, each fix
> trading one error class for another. The classifier still implements v0.1
> (`KW_BENCH_VERSION = "0.1"`) and runs in CI, but nothing renders its levels.
> See issue #153, closed as not planned. Use this rubric as a human reference,
> applied by hand.

## Credits

- **Retrieval, replication, rediscovery, and frontier stages:** Hejia Geng,
  AItonomy Foundation,
  [The AI4S Benchmark Index Tree](https://aitonomy.org/projects/benchmark).
  KW-Bench v0.1 took its six stage names and their order from that index:
  L0 Retrieval, L1 Closed-form reasoning, L2 Execution, L3 Replication,
  L4 Rediscovery, and L5 Frontier advancement. In v0.2 they survive as L0,
  L1-L2, L3-L5, L7, and L9. The index labels 361 AI-for-science listings and
  pairs each stage with a V1-V7 verifier axis. Issue #111 recorded it on
  2026-08-04, two days before the first KW-Bench draft.
- **Rediscovery versus discovery:** Brian Keating,
  [The Artificial Einstein Test](https://keating.ai/einstein-test/). It
  separates the rediscovery of known theory from the discovery of new theory.
- **Prediction as the top of the scale:** Jakub Pachocki, Chief Scientist at
  OpenAI,
  [Perplexity and Intelligence](https://openai.com/index/perplexity-and-intelligence/)
  (2026-11-22). The essay treats capability as the prediction of unseen data,
  measured by perplexity on held-out data. It also notes that benchmarks were
  "largely saturated around GPT-4". This idea motivates L10 to L12.

KW-Bench adds these parts:

- the single scale from L0 to L12 and its ordering rule
- the pass test for each level
- the run-start cutoff, novelty check, and resolution event for unknown answers
- the evidence fields, the complexity tags, and the task card

| | |
|---|---|
| **Status** | Proposed v0.2 |
| **Purpose** | Classify the hardest ability a benchmark requires for a passing score |
| **Applies to** | Agent, model, and system benchmarks in any domain |
| **Companion** | SLIM Rubrics, which audits task quality (drafted in `ktwu01/vendor-data-qc`; not vendored here) |

KW-Bench records capability level. SLIM records whether the task and its
measurement process are Real, Diverse, Difficult, Valuable, and Solid. Publish
both assessments when both are available.

## Thirteen levels, ordered by the difficulty of the tested ability

A higher level tests a harder ability. L9, L10, and L11 are the exception:
they test three different kinds of unknown answer, and none of them is
necessarily harder than another. L12 is the hardest ability. That no finite
benchmark can test it follows from its difficulty; it is not the reason for its
place.

| Level | Name | A passing score requires | Example |
|---|---|---|---|
| **L0** | Retrieval | Finding and returning information that already exists in a source. | Lookup question answering |
| **L1** | Quiz questions | A short, fixed answer that a non-specialist could derive in minutes. | MMLU, GSM8K, LiveCodeBench |
| **L2** | Expert-level questions | A fixed answer that needs domain expertise. Experts wrote or checked the items to be hard. | Humanity's Last Exam, FrontierMath |
| **L3** | Real coding work | Changing code inside a real project, where running tests on that code decides the score. | SWE-bench |
| **L4** | Long agent tasks | Many tool or environment actions toward one stated goal, over a long human-time horizon. | OSWorld |
| **L5** | Whole jobs | A complete professional deliverable from real paid work, judged at professional quality. | GDPval |
| **L6** | Testing the tests | Judging whether a test, a grader, or a claimed result is valid. | — |
| **L7** | Reproducing research | A research result the evaluator already knows: replicating it when the task names it, or rediscovering it when the task does not. | PaperBench, ResearchClawBench |
| **L8** | Self-improvement | An output that measurably improves an AI system over a stated baseline. | RE-Bench, MLE-bench |
| **L9** | Open problems | A result that nobody had when the benchmark was built, checked by a verifier. | FrontierMath: Open Problems, Formal Conjectures |
| **L10** | Hidden facts | A prediction of a fact that nobody knows yet, scored when the world reveals it. | ForecastBench |
| **L11** | Chaotic systems | A prediction of a system sensitive to initial conditions, scored against observations made after the prediction. | Live weather forecasting |
| **L12** | Laplace's demon | A prediction of any state of the world. | None |

## The scored task determines the level

Assign the highest fully evidenced level that a passing score requires. Test
from L12 down to L0. When a task fits more than one of L9, L10, and L11, record
each as a separate track.

Separate tracks receive separate levels. A suite containing retrieval questions
and executable tasks reports L0 and L3 track labels instead of one suite-wide
average.

A benchmark that measures other benchmarks, such as a harness, a ranking
platform, or a validity study, tests no ability of the system under test.
Record it with the type `meta-evaluation` and no level. L6 applies only when
the system under test must judge validity itself.

## Boundary tests

### L0 to L1: the answer is derived

L0 returns information already present in a source. L1 transforms, combines, or
infers from that information. Using a search tool preserves L0 when the scored
answer is copied from the source.

### L1 to L2: the answer needs expertise

L1 items can be answered by a non-specialist in minutes. L2 items need domain
expertise, and experts wrote or checked them to be hard. Both score only a
returned answer.

### L2 to L3: running code decides the score

L3 scores code that the system changed inside a real or realistic project, by
running tests on it. A standalone contest problem stays at L1 or L2.

### L3 to L4: the task takes many actions over a long horizon

L4 needs many tool or environment actions toward one goal, over a long
human-time horizon. The horizon threshold is calibrated in the first labelling
pilot and recorded here with its version. Read-only browsing scored only by its
final answer stays at L1 or L2.

### L4 to L5: the output is a whole job

L5 tasks come from real paid work, and the scored output is the complete
deliverable, judged at professional quality.

### L5 to L6: the system judges validity

L6 scores whether the system correctly judges a test, a grader, or a claimed
result to be valid or invalid.

### L6 to L7: the target is a research result

L7 scores a research result that the evaluator already holds. Replication names
the target result. Rediscovery hides it: the system must choose what to
investigate and find it. A research task may state its question and still be
L7 when the system must produce the result from data or papers. A closed
question with one fixed answer, rather than a research result, stays at L1 or
L2.

### L7 to L8: an AI system gets better

L8 scores a measured improvement to an AI system over a stated baseline, such
as a faster kernel or a lower training loss. Reproducing an ML paper without
such an improvement stays at L7.

### L8 to L9, L10, and L11: nobody knows the answer

Below L9, the evaluator holds the answer or a checker for it before the run.
From L9 up, nobody holds the answer at the run-start cutoff.

- **L9** scores a result that the system creates. It needs a novelty check.
- **L10** scores a prediction. It needs a resolution event: the world reveals
  the fact after the prediction.
- **L11** scores a prediction of a chaotic system. It needs observations made
  after the prediction. Scoring forecasts against data that already existed at
  the cutoff, as WeatherBench 2 does for 2020, stays below L9.

A prior result found before the run caps the task at L7 or below. Later runs
begin from their own cutoff.

### L11 to L12: any state of the world

L12 would score a prediction of any state of the world. No finite benchmark
passes this test.

## Complexity is reported on separate axes

Tool count, token count, pass rate, environment realism, autonomy, safety, and
cost do not set the level. Horizon sets the level only at the L3 to L4
boundary. Record these as tags or measurements:

- **horizon:** single-turn, multi-turn, cross-session, streaming, lifelong
- **state:** stateless, workspace, memory, persistent learning state
- **interaction:** text, tools, browser, desktop, code, embodied, multi-agent
- **evaluation:** exact, executable, simulation, model judge, human expert
- **risk:** privacy, security, policy compliance, destructive action
- **resources:** latency, cost, compute, memory, network

## Every assignment ships with six evidence fields; L9 to L11 ship with eight

1. **Scored outcome:** the state or result that determines pass or fail.
2. **Agent-visible target:** the goal, finding, or protocol disclosed to the agent.
3. **Evaluator knowledge:** what the evaluator knew before the run.
4. **Verifier modality:** exact, executable, simulation, model judge, human expert, or hybrid.
5. **Verifier procedure:** the checks, equivalence criteria, and evidence link used to determine the outcome.
6. **Level rationale:** one sentence naming the requirement that sets the level.
7. **Evaluation cutoff, required for L9 to L11:** the run-start timestamp used to establish that the answer was unknown.
8. **Novelty check or resolution event, required for L9 to L11:** for L9, the prior-art scope, sources, search dates, provenance checks, and domain-expert attestation; for L10 and L11, the event that revealed the answer and its date.

Missing evidence produces `LEVEL: unclassified`. The reviewer records every
missing field on the task card. An L9, L10, or L11 assignment without fields 7
and 8 is unclassified. An unclassified record stays in the corpus.

## Classification follows four steps

1. Read the task instruction and verifier.
2. Identify the requirement that determines a passing score.
3. Test levels from L12 down to L0 and select the first fully evidenced level.
4. Record the level, evidence fields, and orthogonal tags.

Benchmark quality receives a separate report. Apply SLIM after the capability
classification to assess task acceptance and measurement confidence.

## The task card keeps the decision auditable

```text
TASK: <id>
KW-BENCH VERSION: 0.2
LEVEL: L0 / L1 / ... / L12 / meta-evaluation / unclassified

SCORED OUTCOME: <what determines pass or fail>
AGENT-VISIBLE TARGET: <what the agent receives>
EVALUATOR KNOWLEDGE: <what was known before the run>
EVALUATION CUTOFF: <run start timestamp; required for L9 to L11>
NOVELTY CHECK OR RESOLUTION EVENT: <required for L9 to L11>
VERIFIER MODALITY: <exact, executable, simulation, model judge, expert, hybrid>
VERIFIER PROCEDURE: <checks, equivalence criteria, and evidence link>
LEVEL RATIONALE: <one sentence>

TAGS
  horizon: <...>
  state: <...>
  interaction: <...>
  evaluation: <...>
  risk: <...>
  resources: <...>

SLIM ASSESSMENT: <link or pending>
CLASSIFIED BY: <name>
DATE: <date>
```

## Version changes preserve historical labels

Changes to a level boundary require a minor version bump. Wording edits that
preserve every decision boundary require a patch version bump. Every task card
stores the rubric version used for classification.

A v0.1 label does not convert to one v0.2 level, because v0.2 splits the old
levels by task scope. Reclassify a v0.1 task under v0.2 with the tests above.
This table shows where each v0.1 level can land:

| v0.1 level | Possible v0.2 levels |
|---|---|
| L0 Retrieval | L0 |
| L1 Closed-form reasoning | L1, L2 |
| L2 Execution | L3, L4, L5, L8 |
| L3 Replication | L7 |
| L4 Rediscovery | L7 |
| L5 Frontier advancement | L9, L10, L11 |
