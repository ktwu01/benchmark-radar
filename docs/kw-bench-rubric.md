# KW-Bench Capability Rubric

KW-Bench places a benchmark on one scale, L0 to L12, by the hardest ability a
passing score requires. It applies to model, agent, and system benchmarks in
any domain. Version 0.2, proposed.

## Thirteen levels, ordered by the difficulty of the tested ability

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

A higher level tests a harder ability, with one exception: L9, L10, and L11
test three kinds of unknown answer, and none of them is necessarily harder than
another. L12 is the hardest ability; that no finite benchmark can test it
follows from its difficulty.

## How to classify

1. Read the task instruction and the verifier.
2. Identify the requirement that decides a passing score.
3. Test levels from L12 down to L0. Assign the first level whose boundary test
   passes and whose evidence fields are complete.
4. Record the level, the evidence fields, and the tags on the task card.

- **Missing evidence** gives `unclassified`. The record stays in the corpus.
- **Mixed suites:** separate tracks get separate levels. A suite with retrieval
  questions and coding tasks reports L0 and L3 tracks, not one average. A task
  that fits more than one of L9, L10, and L11 is recorded as separate tracks.
- **Meta-evaluation:** a harness, ranking platform, or validity study tests no
  ability of the system under test. Record it with the type `meta-evaluation`
  and no level. L6 applies only when the system itself must judge validity.

## Boundary tests

| Boundary | The higher level passes when |
|---|---|
| L0 → L1 | The answer is derived from information, not copied from a source. Search that returns a copied answer stays at L0. |
| L1 → L2 | The items need domain expertise, and experts wrote or checked them to be hard. Both levels score only a returned answer. |
| L2 → L3 | Running tests on code the system changed inside a real or realistic project decides the score. A standalone contest problem stays at L1 or L2. |
| L3 → L4 | The task takes many tool or environment actions toward one goal, over a long human-time horizon. The first labelling pilot sets the threshold. Read-only browsing scored by its final answer stays at L1 or L2. |
| L4 → L5 | The task comes from real paid work, and the complete deliverable is judged at professional quality. |
| L5 → L6 | The score depends on the system correctly judging a test, a grader, or a claimed result as valid or invalid. |
| L6 → L7 | The score is a research result that the evaluator already holds. Replication names the target; rediscovery hides it. A research task may state its question and still be L7. A closed question with one fixed answer stays at L1 or L2. |
| L7 → L8 | The score measures an improvement to an AI system over a stated baseline, such as a faster kernel or a lower training loss. Reproducing an ML paper without such an improvement stays at L7. |
| L8 → L9, L10, L11 | Nobody holds the answer at the run-start cutoff. L9 scores a result the system creates and needs a novelty check. L10 scores a prediction the world later resolves. L11 scores a prediction of a chaotic system against observations made after the prediction. Forecasts scored against data that existed at the cutoff, as WeatherBench 2 does for 2020, stay below L9. A prior result found before the run caps the task at L7 or below. |
| L11 → L12 | The task predicts any state of the world. No finite benchmark passes. |

## Evidence fields

Every assignment records fields 1 to 6. L9, L10, and L11 also record fields 7
and 8; without them the record is `unclassified`.

1. **Scored outcome:** the state or result that decides pass or fail.
2. **Agent-visible target:** the goal, finding, or protocol given to the agent.
3. **Evaluator knowledge:** what the evaluator knew before the run.
4. **Verifier modality:** exact, executable, simulation, model judge, human expert, or hybrid.
5. **Verifier procedure:** the checks, equivalence criteria, and evidence link.
6. **Level rationale:** one sentence naming the requirement that sets the level.
7. **Evaluation cutoff:** the run-start timestamp that shows the answer was unknown.
8. **Novelty check or resolution event:** for L9, the prior-art scope, sources, search dates, and domain-expert attestation; for L10 and L11, the event that revealed the answer and its date.

## Task card

```text
TASK: <id>
KW-BENCH VERSION: 0.2
LEVEL: L0 / L1 / ... / L12 / meta-evaluation / unclassified

SCORED OUTCOME: <what decides pass or fail>
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

## Tags

Tags describe a benchmark without setting its level. Horizon also sets the
L3 to L4 boundary.

- **horizon:** single-turn, multi-turn, cross-session, streaming, lifelong
- **state:** stateless, workspace, memory, persistent learning state
- **interaction:** text, tools, browser, desktop, code, embodied, multi-agent
- **evaluation:** exact, executable, simulation, model judge, human expert
- **risk:** privacy, security, policy compliance, destructive action
- **resources:** latency, cost, compute, memory, network

---

## Background

### Credits

- **Hejia Geng, AItonomy Foundation**,
  [The AI4S Benchmark Index Tree](https://aitonomy.org/projects/benchmark):
  the stage names and order of v0.1 (Retrieval to Frontier advancement). In
  v0.2 they survive as L0, L1-L2, L3-L5, L7, and L9. Issue #111 recorded the
  index on 2026-08-04, two days before the first KW-Bench draft.
- **Brian Keating**, [The Artificial Einstein Test](https://keating.ai/einstein-test/):
  the split between rediscovering known theory and discovering new theory.
- **Jakub Pachocki, OpenAI**,
  [Perplexity and Intelligence](https://openai.com/index/perplexity-and-intelligence/)
  (2026-11-22): capability as the prediction of unseen data, which motivates
  L10 to L12.

KW-Bench adds the single L0-L12 scale, the boundary tests, the evidence fields,
the tags, and the task card.

### Status

This file is the source of truth for KW-Bench in benchmark-radar; the first
draft was in `ktwu01/vendor-data-qc`. Apply the rubric by hand. The
pattern-matching classifier in `kw_bench.py` is dormant: it still implements
v0.1, and two reviews found 11 and then 7 misclassifications (issue #153). Do
not publish its output.

SLIM Rubrics, drafted in `ktwu01/vendor-data-qc`, audit task quality
separately from the level.

### Versions

A change to a level boundary is a minor version; a wording edit that keeps
every boundary is a patch. Every task card stores its rubric version.

v0.2 (issue #1345) merged the six-level v0.1 scale with the twelve levels of
the Levels of benchmarks post into one scale. A v0.1 label does not convert
directly; reclassify the task. Each v0.1 level can land on these v0.2 levels:

| v0.1 | v0.2 |
|---|---|
| L0 Retrieval | L0 |
| L1 Closed-form reasoning | L1, L2 |
| L2 Execution | L3, L4, L5, L8 |
| L3 Replication | L7 |
| L4 Rediscovery | L7 |
| L5 Frontier advancement | L9, L10, L11 |
