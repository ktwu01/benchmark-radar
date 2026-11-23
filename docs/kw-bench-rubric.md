# KW-Bench Capability Rubric

> **This file is the source of truth for the KW-Bench rubric in benchmark-radar.**
> The rubric was first drafted in `ktwu01/vendor-data-qc`. This repository no
> longer defers to that copy: the levels, boundaries, and evidence fields
> implemented in `src/benchmark_radar/kw_bench.py` are defined here, and
> `KW_BENCH_VERSION` tracks the `KW-BENCH VERSION` field on the task card below.
>
> **Status in this repository: dormant.** No classifier output is published.
> Assigning L0-L5 means reading a task and its verifier and judging what the
> evaluator knew before the run. That is a semantic judgment, and the
> deterministic pattern-matching classifier in `kw_bench.py` cannot make it: two
> rounds of adversarial review found 11 and then 7 misclassifications, each fix
> trading one error class for another. The classifier stays in the tree and runs
> in CI, but nothing renders its levels. See issue #153, closed as not planned.
> Use this rubric as a human reference, applied by hand.

## Credits

- **Stage names and order:** Hejia Geng, AItonomy Foundation,
  [The AI4S Benchmark Index Tree](https://aitonomy.org/projects/benchmark).
  The six stages, from L0 Retrieval to L5 Frontier advancement, come from that
  index. It labels 361 AI-for-science listings and pairs each stage with a
  V1-V7 verifier axis. Issue #111 recorded the index on 2026-08-04, two days
  before the first KW-Bench draft.
- **Rediscovery versus discovery:** Brian Keating,
  [The Artificial Einstein Test](https://keating.ai/einstein-test/). It
  separates the rediscovery of known theory from the discovery of new theory.
- **Prediction as the top of the levels framing:** Jakub Pachocki, Chief
  Scientist at OpenAI,
  [Perplexity and Intelligence](https://openai.com/index/perplexity-and-intelligence/)
  (2026-11-22). The essay treats capability as the prediction of unseen data,
  measured by perplexity on held-out data. It also notes that benchmarks were
  "largely saturated around GPT-4". This idea motivates the upper levels of
  the Levels of benchmarks post, from hidden facts to Laplace's demon. It came
  after the L0-L5 stages, so it does not affect them.

KW-Bench adds these parts:

- the rule that the level follows what the evaluator knew before the run
- the run-start cutoff and the novelty check for L5
- the boundary tests and the evidence fields
- the complexity tags and the task card

| | |
|---|---|
| **Status** | Proposed v0.1 |
| **Purpose** | Classify the highest capability an agent must demonstrate to pass a benchmark |
| **Applies to** | Agent, model, and system benchmarks in any domain |
| **Companion** | SLIM Rubrics, which audits task quality (drafted in `ktwu01/vendor-data-qc`; not vendored here) |

KW-Bench records capability level. SLIM records whether the task and its
measurement process are Real, Diverse, Difficult, Valuable, and Solid. Publish
both assessments when both are available.

## Six levels locate the scored capability frontier

| Level | Name | Passing requirement |
|---|---|---|
| **L0** | Retrieval | Locate and return existing information from supplied or accessible sources. |
| **L1** | Closed-form reasoning | Derive a checkable answer from supplied or read-only retrieved information without changing external state. |
| **L2** | Execution | Take actions in an environment to reach a specified, verifiable end state. |
| **L3** | Replication | Reproduce a known artifact, workflow, experiment, or result under controlled conditions. |
| **L4** | Rediscovery | Identify and validate an undisclosed problem, phenomenon, relationship, or mechanism in an open-ended environment; the evaluator already knows the finding. |
| **L5** | Frontier advancement | Produce a result absent from the declared prior-art scope at the start of the evaluation run and validate it through new external evidence. |

## The scored task determines the level

Assign the highest fully evidenced level required for a passing score. Test from
L5 down to L0. Discovery status takes precedence over output form: an open-ended,
read-only bug hunt receives L4 when it satisfies the rediscovery requirements. A
task that retrieves documentation, reasons about it, and edits a repository
receives L2 when the verifier scores the repository end state.

Separate tracks receive separate levels. A suite containing retrieval questions
and executable tasks reports L0 and L2 track labels instead of one suite-wide
average.

## Five boundaries separate retrieval, reasoning, execution, and discovery

### L0 to L1: the answer is derived

L0 returns information already present in a source. L1 transforms, combines, or
infers from supplied or retrieved information to produce a derived answer. Using
a search tool to access a source preserves L0 when the scored answer is copied
from that source. Synthesizing across retrieved sources receives L1.

### L1 to L2: external state determines success

After L4 and L5 have been excluded, L1 scores an answer produced from information
available during the run. L2 scores an action outcome or an environment state
changed by the agent. Read-only use of a shell, browser, or database preserves L1
when the verifier checks only the returned answer.

### L2 to L3: the task reproduces a known target

L2 supplies a goal and checks successful execution. L3 additionally identifies a
known artifact, protocol, experiment, or result that the agent must reproduce.
The benchmark records the target provenance and the equivalence criteria used by
the verifier.

### L3 to L4: the target finding is hidden

L3 gives the agent the replication target. L4 presents an open-ended environment
without naming the target problem, phenomenon, relationship, or mechanism. The
agent must choose what to investigate, identify the undisclosed finding, and
validate it. The evaluator already knows the finding and can verify rediscovery
against recorded evidence. A task that states the question and withholds only
the answer remains L1, L2, or L3 according to its scored outcome.

Examples include discovering an undocumented known bug, recovering a hidden
scientific relationship, or identifying a known failure mechanism from raw
observations.

### L4 to L5: the result is created prospectively

L4 uses evaluator-held knowledge that predates the evaluation run. L5 starts
with an open frontier and judges a result created during that run. L5 evidence
requires prospective validation such as a new experiment, independent
reproduction, deployment outcome, or qualified expert adjudication.

A prior-art or provenance check that finds the result before the evaluation run
establishes a ceiling of L4. L5 evaluation records the run-start cutoff, declared
search scope, sources and dates checked, domain-expert attestation, and the
validation event that occurred after the agent produced the candidate result.
Later runs begin from their own cutoff. A prior result in evaluator knowledge
establishes an L4 ceiling. A prior result accessible to the agent may reduce the
task to L0, L1, L2, or L3. Apply all five boundary tests to every later run.

## Complexity is reported on separate axes

Time horizon, tool count, token count, pass rate, environment realism, autonomy,
safety, and cost do not set the L0-L5 level. Record them as tags or measurements:

- **horizon:** single-turn, multi-turn, cross-session, streaming, lifelong
- **state:** stateless, workspace, memory, persistent learning state
- **interaction:** text, tools, browser, desktop, code, embodied, multi-agent
- **evaluation:** exact, executable, simulation, model judge, human expert
- **risk:** privacy, security, policy compliance, destructive action
- **resources:** latency, cost, compute, memory, network

## Every assignment ships with six evidence fields; L5 ships with eight

1. **Scored outcome:** the state or result that determines pass or fail.
2. **Agent-visible target:** the goal, finding, or protocol disclosed to the agent.
3. **Evaluator knowledge:** what the evaluator knew before the run.
4. **Verifier modality:** exact, executable, simulation, model judge, human expert, or hybrid.
5. **Verifier procedure:** the checks, equivalence criteria, and evidence link used to determine the outcome.
6. **Level rationale:** one sentence naming the requirement that sets the level.
7. **Evaluation cutoff, required for L5:** the run-start timestamp used to establish that the result was unknown.
8. **Novelty check, required for L5:** the prior-art scope, sources, search dates, provenance checks, and domain-expert attestation.

Missing evidence produces `LEVEL: unclassified`. The reviewer records every
missing field on the task card. An L5 assignment without an evaluation cutoff or
novelty check is unclassified.

## Classification follows four steps

1. Read the task instruction and verifier.
2. Identify the requirement that determines a passing score.
3. Test levels from L5 down to L0 and select the first fully evidenced level.
4. Record the level, evidence fields, and orthogonal tags.

Difficulty and benchmark quality receive separate reports. Apply SLIM after the
capability classification to assess task acceptance and measurement confidence.

## The task card keeps the decision auditable

```text
TASK: <id>
KW-BENCH VERSION: 0.1
LEVEL: L0 / L1 / L2 / L3 / L4 / L5 / unclassified

SCORED OUTCOME: <what determines pass or fail>
AGENT-VISIBLE TARGET: <what the agent receives>
EVALUATOR KNOWLEDGE: <what was known before the run>
EVALUATION CUTOFF: <run start timestamp; required for L5>
NOVELTY CHECK: <prior-art scope, sources, dates, provenance, expert attestation; required for L5>
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
