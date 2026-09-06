# Agent Weakness Blinded Sample

Date: 2026-09-01

Use only the taxonomy in `docs/technical-report/agent-weakness-coding-guide.md`. Assign exactly one fine code to each row and explain the choice. The main YAML table, prior reports, and any earlier code assignments are intentionally out of scope until all four assignments are complete.

## Sample `A`

- Benchmark: OSWorld 2.0
- Status: demonstrated
- Protocol: Long-horizon computer-use workflows under 500-step binary completion
- Authoritative source: `paper` at `https://arxiv.org/html/2606.29537v1`
- Evidence location: HTML abstract paragraph id abstract1.1, final two sentences on 20.6% binary completion, 54.8% partial score, and hidden-state recovery; Figure 8 caption at figure id S3.F8
- Evidence excerpt: Claude Opus 4.8 completes only 20.6% of tasks at a 54.8% partial score, and the paper explicitly says agents lose track of constraints, miss information arriving mid-task, and struggle when workflows hinge on hidden state recovery.
- Limitation: OSWorld 2.0 is a deliberately hard long-horizon benchmark with a strict binary-completion metric, so its headline failure rates are not interchangeable with shorter browser or desktop benchmarks.
- Counter-reading: Some of the failure burden may come from the intentionally long task horizon and binary end-state scoring rather than a pure hidden-state weakness rate in ordinary deployments.

## Sample `B`

- Benchmark: SWE-bench Science
- Status: demonstrated
- Protocol: Repository-level scientific software engineering tasks across issue, exploratory, and integration paradigms
- Authoritative source: `paper` at `https://arxiv.org/abs/2608.19799`
- Evidence location: arXiv abs abstract paragraph on pass@1 below 50%, the four recurring failure mechanisms, and the paired scientific-guidance ablation
- Evidence excerpt: The paper reports that the best-performing agent stays below 50% pass@1 and identifies misguided exploration or surface-level repair, along with incomplete repair coverage, as recurring scientific-engineering failure mechanisms.
- Limitation: The release spans 119 tasks across many scientific domains with hidden verifier tests, so the public paper supports family-level failure coding but not fine-grained per-domain prevalence estimates.
- Counter-reading: Some apparent execution failures may partly reflect missing domain knowledge or abstraction deficits rather than pure exploration or tool-choice mistakes.

## Sample `C`

- Benchmark: ResearchClawBench
- Status: demonstrated
- Protocol: End-to-end scientific rediscovery from raw data with hidden target papers
- Authoritative source: `paper` at `https://arxiv.org/html/2606.07591v5`
- Evidence location: HTML abstract paragraph on 21.5, 20.7, and protocol/evidence/scientific-core mismatch; HTML paragraph ids S4.SS2.p1.1 and S4.SS5.p1.1 under subsection 4.5 Error Analysis
- Evidence excerpt: The strongest autonomous agent averages 21.5, the strongest ResearchHarness LLM averages 20.7, and the error analysis says failures concentrate in experimental protocol mismatch, evidence mismatch, and missing scientific core rather than mere execution trouble.
- Limitation: ResearchClawBench uses expert-curated rubrics over 40 tasks from 10 scientific domains, so its errors are informative about rediscovery workflows but not a generic estimate for all scientific coding tasks.
- Counter-reading: Some low scores may reflect benchmark novelty and the hidden-target-paper setup instead of a stable tendency to drift from objectives in more scaffolded scientific tasks.

## Sample `D`

- Benchmark: SciCode
- Status: unmeasured
- Protocol: Benchmark-defect audit of scientific coding evaluation
- Authoritative source: `paper` at `https://arxiv.org/abs/2608.04975`
- Evidence location: arXiv abs abstract paragraph on 263 defects, 192 score-suppressing defects across 91% of main problems, and recovery to 84-98% / 69-92%
- Evidence excerpt: The audit finds 263 benchmark defects, with 192 defects across 91% of main problems causing correct instruction-following solutions to be rejected, so the original benchmark cannot be used as a clean prevalence estimate for agent failure on scientific coding.
- Limitation: This row is an instrument caution, not evidence that verification failures are absent. It shows that the measurement channel was contaminated enough to distort failure rates.
- Counter-reading: Even after correcting benchmark defects, some scientific-coding tasks remain difficult, so the audit does not prove that all prior failure signals were artifacts.

## Required output

For each row provide:

```text
sample_id: <A, B, C, or D>
secondary_code: <one fine-taxonomy code>
secondary_note: <one or two sentences grounded only in the evidence above>
```

Then state whether any row was impossible to code from the provided evidence.
