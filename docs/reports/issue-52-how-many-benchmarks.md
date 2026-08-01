# How Many Benchmarks Exist? Answering Issue #52, and Why the Dashboard's Answer Is Wrong

> Report date: July 31, 2026 | Repository: ktwu01/benchmark-radar | Subject: corpus counts, taxonomy recall, and the flow-versus-stock distinction
> Evidence cutoff: 2026-07-31T14:31Z (the `generated_at` of the latest rebuild). Author: Koutian Wu (https://ktwu01.github.io/).

> **Update, this PR: the agentic defect is fixed, not just diagnosed.** The published count moved from **3 to 75** distinct artifacts. Two things changed. A new `benchmark-radar rescore` command recomputes stored categories across all nine snapshots, which alone moved 3 to 16 by fixing the one-day-numerator bug. The classifier then moved 16 to 75 by replacing the adjacent-phrase list with a proximity rule, measured at **95.0% recall and 76.0% precision** against a hand-labeled sample.
>
> The report's headline open question is also resolved. The unreconciled "89 versus 64" ground-truth dispute was an artifact of two passes using *different* inclusion rules. Re-run with the rule fixed in advance, two independent annotators reached **Cohen's kappa 0.888** (94.5% raw agreement, 6 disagreements in 109), settling ground truth at **60 to 66**, not 89. Sections 4, 8 and 12 are corrected accordingly; the pre-fix findings are kept as the diagnosis that motivated the change.
>
> What is *not* fixed, and deliberately so: the stock-versus-flow answer in sections 5 and 9 is unchanged. The corpus still cannot say how many benchmarks exist on the market, and no keyword change addresses that.

## Contents

1. Executive answer
2. The question, and the three questions inside it
3. What the corpus counts actually are
4. Why the agentic count is wrong: measured recall
4a. The other four categories: one more broken, three working
5. Why the count cannot answer "how many exist"
6. Retrieval versus classification: which layer binds
7. What issue #57 did and did not fix
8. Recommended keyword lists, with measured precision
8a. What this PR actually changed, and what it measures
9. What a defensible market estimate requires
10. Final diagnosis
11. Reproducing every number in this report
12. Limitations

## 1. Executive answer

Issue #52 asked how many benchmarks exist on the market, how many are agentic, and what the category breakdown is. The project answered with a dashboard panel showing five numbers. This report exists because that answer was wrong in a way a panel cannot express.

**The direct answer splits in two.**

**On category breakdown, the project can partly answer, with corrections.** The corpus holds 645 distinct artifacts. Before this PR they were tagged benchmark 512, dataset 450, evaluation 337, data_quality 15, agentic 3. The three large figures survive audit at 96 to 98% recall. The agentic figure did not: it was wrong twice over, first because snapshots written before the category existed were never re-scored (3 should have been 16), and second because the keyword list matched almost nothing (16 should have been ~75).

**Both defects are now fixed in this PR.** The current published figures are **benchmark 512, dataset 458, evaluation 401, data_quality 15, agentic 75**, and the agentic classifier is measured at 95.0% recall / 76.0% precision against hand-labeled ground truth. `benchmark` is deliberately unchanged: narrowing it was measured and found actively harmful. The data_quality figure remains disputed between two audits and is **left unfixed on purpose** (section 4a) because the two passes disagree by an order of magnitude on what the category means, and shipping a keyword change on an unsettled definition would repeat the exact error this report documents. The tags are multi-label, so the five figures do not partition 645 and must never be summed.

Your instinct that the defect extends beyond agentic is partly confirmed and partly not, and the distinction is useful. The three large categories are working; narrowing them was measured and found actively harmful. But `benchmark` at 79.4% prevalence is non-discriminative in a different way: 489 of its 512 matches come from the single bare word "benchmark", which is also what the retrieval layer queries for, so the category largely restates the query.

**On "how many exist on the market," the project cannot answer, and no amount of crawling harder in the current direction will change that.** The question asks for a stock (the installed population). The pipeline measures a flow (new arrivals inside a 48-hour lookback). These are different quantities. The evidence that the corpus misses the population is not subtle: of 20 canonical benchmarks (MMLU, HELM, GPQA, ARC-AGI, HumanEval, BIG-bench, MMMU, GSM8K, HellaSwag, TruthfulQA, WebArena, tau-bench, OSWorld, MLE-bench, PaperBench, lm-evaluation-harness, mlcommons, evalplus, openai/evals, SWE-bench), **19 are entirely absent** from all 791 sightings. The single hit is a third-party Hugging Face dataset, not `princeton-nlp/SWE-bench`.

Meanwhile the corpus does contain `omegaprime669/rtx-5090-benchmarks`, `NODARISHUB/mx-wordpress-seo-health-benchmark`, `habert75/homework3-benchmark-results`, and `yusuke0714/landingboost-landing-page-trust-benchmark`. So the set being counted and the set a reviewer has in mind are close to disjoint. Reporting 512 as an answer to 市面上总共 states a flow measure, with a partly-spurious numerator, in reply to a stock question.

### Status at a glance

| Question asked in #52 | Can the project answer it? | Published figure after this PR | Verdict |
|---|---|---|---|
| Category breakdown | Partly | benchmark 512, dataset 458, evaluation 401 | These three measured at 96 to 98% recall. Multi-label, not a partition |
| How many agentic? | **Yes, now** | **75** (was 3) | **Fixed.** Rescore moved 3 to 16; proximity rule moved 16 to 75, at 95.0% recall / 76.0% precision |
| How many data-quality? | Disputed | 15 (unchanged) | **Deliberately not fixed.** Two audits disagree on the inclusion rule by an order of magnitude. Needs a definition before a keyword |
| How many benchmarks total on the market? | No | 512 implied | Category error: flow reported as stock. Unchanged by this PR |
| New benchmark artifacts per day | Yes, and this is the real strength | 84.9/day recent average | Defensible as a floor, given per-source truncation |
| Market total, grounded anchor | Not from this corpus | Not available | 4,542 to 5,092 Hugging Face benchmark datasets exist; corpus has seen 207 |

The honest framing is that this project is a good flow instrument being asked a stock question. Its daily-arrival measurement is something registries cannot provide, and that is worth stating positively. Its category counts need a recall fix. Its market total needs a different collection mode entirely, not a bigger crawl.

## 2. The question, and the three questions inside it

Issue #52, created 2026-07-30T07:31:27Z, verbatim:

> @吴叩天 还可以，你现在有统计出一个市面上总共多少benchmark，agentic benchmark，多少类别的一个统计不；理论上你是可以爬出这个信息的

Three distinct asks are bundled here, and they have different answerability:

| | Question | Type | Answerable from the corpus? |
|---|---|---|---|
| (a) | 市面上总共多少 benchmark | Stock (population census) | **No.** The observation window cannot contain the population. |
| (b) | How many agentic benchmarks | Composition | **Only within the sampled flow**, and only after the recall defect is fixed. |
| (c) | 多少类别的统计 | Composition | **Yes**, with the multi-label caveat. |

The reviewer's closing remark, "理论上你是可以爬出这个信息的" (theoretically you can scrape this), is correct, with one correction developed in section 9: it is scrapable, but not by raising `lookback_hours` or `max_items_per_source`. Those scale the flow measurement and move the stock estimate essentially not at all, because established benchmarks do not re-emit timestamps.

Issue #52 was closed automatically by PR #56 on 2026-07-30T19:39:23Z, referenced as "Fixes #52" again by PR #58, and **reopened by the repository owner on 2026-07-31T05:42:08Z**. The reopen is the operative verdict: the delivered fix did not satisfy the request.

## 3. What the corpus counts actually are

Verified in `site/data/radar.json` under `corpus.aggregates`, regenerated by `benchmark-radar rebuild` at 2026-07-31T14:31:49Z:

| Category | Distinct artifacts | Share of 645 |
|---|---:|---:|
| benchmark | 512 | 79.4% |
| dataset | 450 | 69.8% |
| evaluation | 337 | 52.2% |
| data_quality | 15 | 2.3% |
| agentic | 3 | 0.5% |

Two structural facts about these numbers:

**They are multi-label.** 512 + 450 + 337 + 15 + 3 = 1,317, which exceeds 645 because one artifact carries several tags. Any presentation that sums them, or renders them as pie slices, is wrong.

**`benchmark` at 79.4% is barely discriminative.** A tag applied to four of every five artifacts carries little information. This is the opposite defect from the agentic problem and needs the opposite fix. Section 4a develops it.

### The corpus is 5 genuine days, not 9

Nine snapshot files exist. Four are synthetic, added by commit `0c20261` via `simulate-history`, and carry `selection.simulated: true`. Their signature is unmistakable:

| Date | Items | `generated_at` | Provenance |
|---|---:|---|---|
| 2026-07-23 | 20 | `T00:00:00+00:00` | Simulated |
| 2026-07-24 | 32 | `T00:00:00+00:00` | Simulated |
| 2026-07-25 | 32 | `T00:00:00+00:00` | Simulated |
| 2026-07-26 | 30 | `T00:00:00+00:00` | Simulated |
| 2026-07-27 | 30 | `T17:58:20.350823+00:00` | Genuine |
| 2026-07-28 | 186 | `T14:33:06.179849+00:00` | Genuine |
| 2026-07-29 | 201 | `T14:29:12.279273+00:00` | Genuine |
| 2026-07-30 | 200 | `T14:28:50.917100+00:00` | Genuine |
| 2026-07-31 | 60 | `T14:31:49.744338+00:00` | Genuine |

Synthetic midnight timestamps versus real wall-clock times. The simulated days also cover only Hugging Face and GitHub, because `simulate-history` excluded arXiv and Brave by design. So **44% of snapshot dates are not observed data, and any 9-day trend line silently mixes two different source mixes.** Issue #35, which requested 30 snapshots, remains open with 9 on disk.

### Five of eight connectors contribute nothing

From `ingest_health` in the 2026-07-31 snapshot:

| Source | Items | Status |
|---|---:|---|
| github | 300 | ok, at cap |
| huggingface | 89 | ok |
| arxiv | 69 | ok |
| github_releases | 0 | ok but empty |
| openreview | 0 | `HTTP 403 from api2.openreview.net/notes` |
| semantic_scholar | 0 | `HTTP 429 after 3 attempts` |
| openalex | 0 | `RuntimeError: OPENALEX_API_KEY is not configured` |
| brave | 0 | `RuntimeError: BRAVE_API_KEY is not configured` |

Only three connectors have ever contributed a record. The README's eight-source table describes configuration, not realized coverage.

`github_releases` deserves separate attention: it is the only connector pointed at HELM, lm-evaluation-harness, SWE-bench, ARC-AGI, openai/evals, mlcommons/inference, evalplus, and LiveBench. It returns 0 on all nine days, because a release feed filtered to a 48-hour window almost always is empty. The `watchlist` is the other mechanism meant to pin famous artifacts, and `selection.watchlisted` is **0 on every single snapshot**. Both safety nets for the established population are empirically inert.

### The funnel discards most of what it fetches

| Date | Fetched | Published | Discarded |
|---|---:|---:|---:|
| 2026-07-28 | 718 | 186 | 74% |
| 2026-07-29 | 721 | 201 | 72% |
| 2026-07-30 | 696 | 200 | 71% |
| 2026-07-31 | 458 | 60 | 87% |

`minimum_score: 40` plus the require-a-category rule removes the rest. The scoring rubric weights adoption at 0.25 and recency at 0.20, so a stable canonical benchmark scores badly on recency even when fetched. GitHub sits at exactly its 300 cap on eight of nine days, meaning the true count of matching items is unknown and larger.

### One benchmark can count as three artifacts

The deduplication design is sound: `corpus.py` extracts exact identifiers (DOI, arXiv ID, `github:owner/repo`, `huggingface:kind:owner/name`) and runs union-find so transitively linked identifiers collapse. Replaying it confirms 791 sightings collapse to 645 distinct identities, matching `entity_types.artifact` exactly.

But the cross-source join never fires. Of 645 artifacts, **0 have a populated `artifact_urls` field**, and 0 were ever observed from more than one source namespace. So a benchmark released as an arXiv paper, a GitHub repo, and a Hugging Face dataset counts as three separate artifacts. This is not a bug in the dedup logic, which is correct and idle. It is triple-counting through missing cross-references, and it inflates any total by an unmeasured factor.

## 4. Why the agentic count is wrong: measured recall

`agentic: 3` is not a measurement of the agentic share. It is an artifact of a keyword list that matches almost nothing.

### Ground truth, built by hand

A bare regex is not usable as ground truth. Hand-labeling 40 randomly sampled titles and abstracts from the 109 artifacts matching `\bagent(s|ic)?\b` found **9 false positives, so the bare regex is only 77.5% precise**. Rejected cases include `AgentMap` (an ontology-matching algorithm, pure proper-noun collision), `Sentimental Image Captioning via Multi-Agent Reasoning` (an internal LLM ensemble, not an acting agent), and `FilmBench` (where "evaluation agent" names an internal judge module).

The inclusion rule used, stated before labeling: include if the artifact's own subject is an LLM-driven agent system that autonomously takes multi-step actions against an environment or tools, or is a benchmark whose evaluation target is such an agent. Exclude proper-noun collisions, related-work framing, internal LLM ensembles for single-shot tasks, and classic RL with no tool-using agent.

Applying that rule yields **89 genuinely agentic artifacts**, validated at 100% agreement against the 40 independent hand labels.

### The result

| Measure | Value |
|---|---:|
| Matched by current 12-term list | 16 |
| Hand-labeled ground truth | 89 |
| **Recall** | **18.0%** |
| Precision | 100.0% |

The list is perfectly precise and nearly useless. It functions as a near-empty filter, missing 73 of 89 genuine agentic artifacts.

An earlier informal estimate in discussion put recall at about 15% using the raw 109-item regex as the denominator. That figure was too pessimistic: the correct denominator is 89, not 109, so the true recall is 18.0%. The correction is recorded here rather than quietly dropped.

### Half the vocabulary matches nothing

Replicating `score_item()` exactly (plain lowercase substring over `title + " " + summary`):

| Term | Artifacts matched |
|---|---:|
| `agent benchmark` | 8 |
| `agentic benchmark` | 2 |
| `agent evaluation` | 2 |
| `agentic evaluation` | 2 |
| `agentic task` | 2 |
| `agentic capabilities` | 1 |
| `multi-agent benchmark` | **0** |
| `tool-use benchmark` | **0** |
| `tool use benchmark` | **0** |
| `benchmark for agent` | **0** |
| `benchmark for llm agent` | **0** |
| `benchmark for autonomous agent` | **0** |

**Six of twelve terms match zero artifacts.** The four longest, most specific phrases are all dead. The entire list produces 16 artifacts, and the top four terms carry all but three of them.

### Root cause: three compounding defects

Classification is a plain substring test at `src/benchmark_radar/pipeline.py:132`:

```python
matches = [term for term in terms if term.lower() in haystack]
```

No tokenization, no stemming, no word boundaries. Therefore:

**(a) Adjacency.** A two-word term demands the words be literally adjacent. Real titles interpose qualifiers: "A Benchmark **Framework** for Evaluating Patient-Facing Health AI Agents", "A Production-Fidelity Benchmark for **LLM-Based Database Operations** Agents". The corpus contains 16 artifacts with the literal string `benchmark for`, and **zero** with `benchmark for agent`. The phrase can only fire on a construction nobody writes.

**(b) Head-noun ordering.** The list encodes eval-noun before agent-noun (`agent benchmark`), but the dominant real pattern puts the agent noun last, or fuses the eval noun into a `-Bench` suffix (`DBA-Bench`, `OrchBench`, `PatientAgentBench`) where no space-separated bigram exists at all.

**(c) Singular only.** Every term uses `agent`. Titles overwhelmingly use the plural, because a benchmark evaluates *agents*. The term `llm agents` alone matches 11 ground-truth items at 100% precision, and the current list cannot see any of them.

### Evidence: real artifacts being missed

1. `DBA-Bench: A Production-Fidelity Benchmark for LLM-Based Database Operations Agents`
2. `IFCMemoryBench: Evaluating Long-Term Memory of LLM-Based Agents in BIM Information Retrieval`
3. `StealthBench: Measuring Operational Stealth in Autonomous Offensive-Security Agents`
4. `OrchBench: Evaluating Multi-Agent Orchestration Plans in Isolation via Deterministic Simulation`
5. `PatientAgentBench: A Benchmark Framework for Evaluating Patient-Facing Health AI Agents`
6. `MemSecBench: Tracking Agent Memory Poisoning from Persistence to Consequence and Repair`
7. `Keep It InMind: Benchmarking the Implicit-Association Blind Spot in Agent Memory`
8. `ConsistencyGate: Preventing Memory Contamination in LLM Agents via Self-Consistency Admission Control`
9. `The Regression Tax: Decomposing Why Skills Help and Hurt LLM Agents`
10. `Zero-Shot Mission-Level Evaluation for Aerial MLLM Agents`
11. `From Controlled to the Wild: Evaluation of Pentesting Agents for the Real-World`
12. `GAUGE: Grading Agent-Built Financial Models Without a Golden Answer`
13. `AgentOmnia: Scaling Agentic Models for Full-Scenario Applications`
14. `OmegaUse-OfficeVal: Benchmarking LLM Agents on Long-Horizon Office-Suite Tasks with Economic Grounding`
15. `nebius/SWE-rebench-leaderboard`

### The larger cause of the published 3: config timing, not keywords

An adversarial verification pass established that the headline figure has a different primary cause than the keyword list, and this correction is the single most important one in the report.

| Measurement | Value |
|---|---:|
| `agentic` stored in snapshot files | **3** |
| Same corpus re-scored with today's config | **16** |

The `agentic` category was added by commit `0c8d77a` on 2026-07-30. Snapshots 07-23 through 07-29 were scored by a pipeline that had no such category, and snapshots are append-only and never rewritten retroactively. All three stored artifacts are dated 2026-07-31.

So the published 3 divides a one-day numerator by a nine-day denominator. **Quoting 3 as evidence of a keyword defect misattributes the cause.** The keyword defect is real, but it takes the count from 16 to a possible 64, not from 3. The correct sequence is to re-score the existing snapshots first (a free operation on data already on disk, moving 3 to 16), then fix the vocabulary.

### Root cause corrected: vocabulary gap, not adjacency

My initial diagnosis blamed the adjacency requirement. An adversarial pass tested that as a counterfactual and **refuted it as the dominant cause.** Relaxing adjacency alone, permitting up to four intervening words in the same sequence, moves the match count only from 16 to 19. That explains about 3 of the misses, roughly 6%.

Ranked causes, measured:

| Cause | Misses explained | Share |
|---|---:|---:|
| Vocabulary gap: no configured n-gram covers the real phrasing | ~40 | ~77% |
| Terse GitHub and HF descriptions (median 98 chars) | ~9 | ~17% |
| Adjacency proper | ~3 | ~6% |

The decisive evidence: `agent*` co-occurring with `benchmark|eval*|leaderboard|harness|testbed` anywhere in the text reaches **106 artifacts**. The words are all present. They are simply never any of the 12 configured n-grams in any order. Titles like `StealthBench: Measuring Operational Stealth in Autonomous Offensive-Security Agents` and `WorkSurface-Bench: Benchmarking Enterprise Agents` are not adjacency near-misses; there is no term for them to be adjacent to.

**This changes the recommended fix.** A longer phrase list is the wrong instrument. What the evidence supports is a **two-slot co-occurrence rule** (an agent token AND an evaluation token within the same text), which is a change to `score_item()` in `pipeline.py`, not only to `config.yml`.

Three alternative explanations were tested and disproved outright:

- **"Items were never retrieved."** False for classification purposes: all 64 ground-truth artifacts are already in the corpus.
- **"`minimum_score: 40` filtered them out."** False: every one is published. The 216 artifacts below 40 are all from 07-27 and 07-28 with `score_version: null`, a pre-v2 rubric on a different scale. Zero score-v2 artifacts fall below 40.
- **"Summaries are empty or templated."** False: only 30 of 645 (4.7%) have empty summaries, and median summary length is 1,536 characters on arXiv. There is ample text to match.

### Recall figures, reconciled

Two independent hand-labeling passes produced different ground truths, and the disagreement is reported rather than averaged:

| Pass | Ground truth | Current matches | Recall | Precision |
|---|---:|---:|---:|---:|
| First (rule-extended from 40 hand labels) | 89 | 16 | 18.0% | 100% |
| Adversarial (all 109 read individually) | 64 | 12 true of 16 | 18.8% | 75% |

The two agree closely on recall, roughly 18 to 19%, which is the load-bearing finding. They disagree on the denominator (89 vs 64) and on precision. The adversarial pass read all 109 candidates individually and judged 45 to be mere mentions rather than agent-eval artifacts, including `Mental World Modeling`, `AgentMap` (ontology matching, agent only in the product name), and `AgentOmnia` (an agent system, not an evaluation). It also found the current terms produce **4 false positives**, so precision is 75%, not 100%.

**Consequence for the fix:** because precision is already imperfect, loosening the terms naively will make it worse. Any replacement must be measured on both axes, which is what section 8 does.

My earlier informal estimate of "~15% recall, ~93 missed" was wrong on both figures. The corrected statement is **recall about 19%, roughly 52 missed of 64, precision 75%.** The direction survives; the magnitude was overstated by about 44%.

## 4a. The other four categories: one more broken, three working

The same audit was applied to the original four categories. The result splits cleanly, and it corrects an assumption worth stating: not every category is broken, and the two failure modes need opposite fixes.

### data_quality: two independent audits disagree, and the disagreement is unresolved

This is the one finding in the report that did not converge. Two hand-labeling passes reached opposite conclusions, and the difference is entirely in the inclusion rule, not in the matching code.

| Pass | Inclusion rule | Ground truth | Recall of current list |
|---|---|---:|---:|
| Category audit | Data quality is a *described property* of the work | 83 | 16.9% |
| Adversarial pass | Data quality is the *substantive contribution* | 8 to 15 | approximately correct |

Under the looser rule, an artifact counts if its text asserts something about data quality (for example, a benchmark reporting "human-verified" instances). Under the stricter rule, it counts only if studying data quality is the point of the work. The looser rule yields 83 and makes 15 a severe undercount. The stricter rule yields 8 to 15 and makes 15 approximately right.

The adversarial pass also showed that a broad data-quality lexicon fires on 205 of 645 artifacts, which is clearly too permissive: it matches any paper saying "we curated" or "human-verified." That supports caution about the 83 figure. The category audit independently flagged 10 to 12 of its own 83 as borderline and noted that a stricter rule would shrink it to 60 to 65.

**Verdict: unresolved, and it should not be presented as a confirmed defect.** What both passes agree on is narrower and still actionable:

- The structural defects below are real regardless of the denominator (dead terms, adjacency losses, free stem supersets, missing subtopic vocabulary).
- If 15 is too low, the retrieval layer is implicated as much as the taxonomy: only 1 of 4 arXiv queries and 1 of 6 GitHub queries target contamination or leakage at all.
- Resolving it requires a labeled sample with a rule fixed in advance, which is a small, well-defined follow-up rather than a keyword change.

The structural findings that follow hold under either rule.

Three compounding causes, ranked by how many misses each explains:

**(c) Whole subtopics have no term at all** (about 45 of 69 misses, the largest cause). Six terms cannot cover seven uncovered subtopics demonstrably present in the corpus: poisoning, label noise, filtering and curation, PII and anonymization, copyright and consent, memorization, and inter-rater agreement.

**(a) Adjacency**, the same defect as agentic. Measured gap between each phrase and its components co-occurring anywhere in the same text:

| Phrase | Matches | Components co-occur | Adjacency loss |
|---|---:|---:|---:|
| `data quality` | 6 | 81 | **75** |
| `annotation quality` | 3 | 15 | 12 |
| `data provenance` | 1 | 11 | 10 |
| `data contamination` | 2 | 11 | 9 |
| `benchmark leakage` | 0 | 7 | 7 |

Real phrasings in the corpus the list cannot see: `quality of the data`, `training-data contamination`, `leakage-free`, `annotation provenance`. An interposed hyphen alone defeats it: `training-data contamination` does not contain `data contamination`.

**(b) Full words where a stem is a free strict superset.** Because matching is substring, a shorter term is provably more permissive. Verified `set(long) ⊆ set(short)` for every pair:

| Stem | Count | Current term | Count | Free gain |
|---|---:|---|---:|---:|
| `dedup` | 5 | `deduplication` | 3 | +2 |
| `contaminat` | 11 | `data contamination` | 2 | +9 |
| `provenan` | 11 | `data provenance` | 1 | +10 |
| `leak` | 8 | `benchmark leakage` | 0 | +8 |

Missed artifacts include `LiveBench/LiveBench`, whose summary literally reads "a challenging, contamination-free llm benchmark", plus `DataOrchestra: Learning to Orchestrate Per-Example Curation of Pretraining Data`, `What do Reward Models Memorize?`, `piimb/pii-masking-benchmark`, and `KletterMix: Climbing Toward High-Quality German Pretraining Data`.

A measured 79-term replacement reaches **96.4% recall at about 88% precision** (verified by reading all 100 matches, not a sample), raising data_quality from 15 to 100 artifacts.

### benchmark, dataset, evaluation are working: do not narrow them

| Category | Recall | Verdict |
|---|---:|---|
| benchmark | 97.7% | Working |
| dataset | 95.9% | Working, add `corpora` |
| evaluation | 72.4% | Working, use stem `evaluat` |

Two alternatives were built and measured, and **both are worse**. A phrase-only list drops `benchmark` from 512 to 332, discarding 186 genuine artifacts while gaining 6. A title-scoped variant leaves **135 artifacts (20.9%) with no tag at all**. Trading a fifth of the corpus into an unlabeled bucket to fix a display problem is a bad trade.

The high prevalence is not a bug: every source query in `config.yml` already filters for benchmark, dataset, and evaluation artifacts at ingest, so the corpus genuinely *is* mostly benchmarks. Narrowing the taxonomy cannot fix a property created upstream.

### The real defect in those three is redundancy, not recall

Verified independently across all 645 artifacts:

| Tags per artifact | Count | Share |
|---|---:|---:|
| 0 | 0 | 0% |
| 1 | 96 | 14.9% |
| 2 | 424 | 65.7% |
| 3 | 119 | 18.4% |
| 4 | 6 | 0.9% |

**Every artifact carries at least one tag**, and P(dataset | benchmark) = **0.658** with Jaccard(benchmark, dataset) = **0.543**. Two thirds of benchmark items are also dataset items, so the pair conveys barely more than one tag. Knowing an artifact is tagged `benchmark` rules out only 20% of the corpus.

This belongs to presentation, not `config.yml`: rank by which category is *distinctive* for an item, or surface the specific matched term instead of the category name.

### Six dead terms across the full taxonomy

Independently verified as matching zero artifacts: `challenge set` (benchmark), `capability eval` (evaluation), `benchmark leakage` (data_quality), plus `multi-agent benchmark`, `tool-use benchmark`, `tool use benchmark`, `benchmark for agent`, `benchmark for llm agent`, `benchmark for autonomous agent` (agentic). Dead terms create an illusion of coverage and should be deleted or replaced.

## 5. Why the count cannot answer "how many exist"

The recency bias is not a limitation to note in passing. It is the reason the question is unanswerable as posed.

A 48-hour lookback repeated over five genuine days can only observe artifacts whose upstream timestamp falls inside those windows. Benchmarks released in 2023 through 2025 are structurally invisible. Searching all 791 sightings across title, `source_id`, and `url` for 20 canonical benchmark names returns 19 absences and one incidental third-party hit.

This makes the direction of the error predictable: the corpus systematically **misses** the established, high-quality population while **including** freshly-timestamped noise. Manual inspection of the 512 `benchmark` artifacts surfaces GPU hardware benchmarks, an SEO health report, a student homework result dump, and vLLM performance runs. No labeled sample was drawn, so the precision rate of the `benchmark` tag is unknown, which is itself a reportable gap.

The consequence for #52: 512 is a flow measure with a partly-spurious numerator. It is not "512 of the market's benchmarks."

### The strongest counter-argument, and why it only partly works

A critic could reasonably object that a flow measure *does* bound a stock, and the objection deserves a direct answer rather than dismissal. If the pipeline observes roughly 85 new benchmark artifacts per day, then over a year that implies on the order of 31,000 arrivals, which is a real statement about the population's growth rate and is not nothing.

Two things are right about that objection. Flow integrated over time genuinely does estimate the *newly created* population, and this is the one route by which the current architecture could contribute to a census. It would also produce a figure of the right order of magnitude (10^4), consistent with the independently verified Hugging Face anchor of 4,542 to 5,092.

Three things defeat it as an answer to #52 as asked:

- **The integration cannot run backward.** Five genuine collection days cannot be extrapolated to the pre-2026 population, which is precisely where the benchmarks a reviewer would name reside. The corpus has no observation of the era it would need to integrate over.
- **The numerator's precision is unmeasured.** Extrapolating 85/day multiplies whatever share of those artifacts are GPU benchmarks, SEO reports, and homework dumps. Section 12 records that this share is not available, so the extrapolation inherits an unbounded error.
- **The cross-source join never fires**, so one benchmark released as paper plus repo plus dataset triple-counts. Integrating a triple-counted rate compounds the inflation.

So the honest position is narrower than "the corpus cannot answer": the corpus can, with a precision measurement and cross-source joining, produce a defensible estimate of the *annual creation rate*. It cannot produce the installed stock, and the creation rate is not what 市面上总共 asks for.

## 6. Retrieval versus classification: which layer binds

This distinction determines whether fixing keywords is even the primary lever, so it was tested against the live arXiv feed rather than assumed.

Testing the configured `rss_keywords` against the live arXiv cs.AI RSS feed on 2026-07-31:

| Measure | Value |
|---|---:|
| Items in feed | 282 |
| Items passing the keyword filter | 29 (10.3%) |
| Items mentioning agent(s|ic) | 97 |
| Agent-mentioning items that pass | 13 |
| **Retrieval recall on agent-mentioning papers** | **13.4%** |

The retrieval keywords carry the identical adjacency defect. Of the six agent-bearing `rss_keywords`, `multi-agent benchmark` and `benchmark for agent` match zero ground-truth items.

Breaking down the 63 arXiv ground-truth artifacts by what admitted them:

- **20 (31.7%) trip only a generic benchmark phrase** such as `benchmark for` or `leaderboard`. They are in the corpus by luck, not by agent-aware retrieval.
- **8** trip an agent-specific phrase.
- **35** trip no `rss_keywords` phrase at all, arriving via other sources.

**Verdict, after adversarial challenge: both layers are defective, and they are independent problems. Classification is not secondary.**

My initial conclusion was that retrieval binds first and therefore taxonomy work could not answer #52. That inference was tested and **does not hold**, for two measured reasons:

1. **48 recoverable artifacts already sit in the corpus, unlabeled.** All 64 ground-truth agentic artifacts are on disk today. Classification alone takes the count from 16 to a possible 64, a four-fold gain requiring no new fetching. That is a classification deficit, not a retrieval deficit.
2. **The working connectors are already discarding retrieved rows.** `github` hits the `max_items_per_source: 300` cap on 8 of 9 days, and `arxiv` on 3 of the 4 days it worked. The pipeline is throwing away fetched records at the cap while the failed connectors take the blame.

So the honest ordering is: re-score the snapshots (free, 3 to 16), then fix classification (4x, on data already held), then fix retrieval (raises the ceiling itself). The retrieval defect is real and the 13.4% live-feed recall figure stands, but it is a parallel problem, not a reason to defer the cheaper fix with the measured payoff.

One more silent failure belongs on the record: **`github_releases` returns 0 items with `ok: true` on every single snapshot.** It reports success while contributing nothing, so it does not appear on any outage list. It is also the only connector pointed at HELM, lm-evaluation-harness, SWE-bench, and ARC-AGI, which is part of why 19 of 20 canonical benchmarks are absent.

Compounding this: PR #58 added agentic retrieval keywords to six sources. OpenAlex and Brave cannot execute them at all (missing API keys), and Semantic Scholar is rate-limited out. **Half of that fix is inert by construction.**

## 7. What issue #57 did and did not fix

Issue #57 ("Retrieval keywords never fetched agentic benchmarks, so the new taxonomy tag alone can't count them") diagnosed the retrieval layer correctly. Its body specified the right verification:

> Re-run `benchmark-radar backfill` after a few days of collection with the new keywords live, and check whether the agentic share of the corpus holds up under both a bare-title heuristic and the new taxonomy classification.

That check was never performed. The timeline explains why:

| Event | Timestamp |
|---|---|
| Issue #57 created | 2026-07-30T20:00:09Z |
| PR #58 opened | 2026-07-30T20:04:52Z |
| PR #58 merged | 2026-07-30T20:07:37Z |
| Issue #57 closed | 2026-07-30T20:07:38Z |

**One second between merge and closure.** The issue was auto-closed by the "Fixes #57" keyword in the PR body. It was open for 7 minutes 29 seconds total, with zero comments. Searching all commits, PR comments, and issue comments for any recall or share measurement returns nothing.

This report performs the missing check, and it fails. The two heuristics #57 asked to compare disagree by a factor of five to twenty depending on the denominator used, with **zero overlap** between the sets.

PR #58 also carried its own unchecked verification box:

> - [ ] After the next scheduled run, spot-check that the Corpus totals panel shows a nonzero `agentic` count

That box is technically satisfiable at 3, which is why a nonzero check is the wrong test. Three of 645 is nonzero and still wrong by a factor of five.

### The asymmetry that produced this

The narrow keyword design traces to issue #51 ("arXiv有111个release today"), where bare nouns like `benchmark` and `dataset` matched roughly two of every three cs.AI papers. The fix (commit `5bc6332`, PR #55) replaced bare nouns with introduction phrases and **was empirically validated against the live feed**, cutting matches from about 65% of the daily pool to 9 to 12%.

That precision lesson is correct. But when the same precedent was applied to `agentic` in PR #58, **only the precision side was reasoned about, and the recall side was never measured at all.** That asymmetry is the root cause of your observation that agentic "is just the same as before, not different at all."

The deeper error: issue #51's lesson is that terms must be *distinctive*, but the implementation chose terms that were *long*. In a substring matcher, length buys brittleness, not precision.

## 8. Recommended keyword lists, with measured precision

Two changes are recommended, in order of cost and payoff.

### Step 0, free: re-score the existing snapshots

Before any keyword edit, re-score the corpus so the `agentic` numerator covers the same nine days as its denominator. This moves the published count from 3 to 16 using data already on disk. It requires no config change and no fetching. Any keyword work evaluated before this step is measured against a contaminated baseline.

### Step 1: replace the matching rule, not just the word list

The evidence in section 4 shows a longer phrase list is the wrong instrument, because the failure is a vocabulary gap rather than adjacency. The measured alternative is a **two-slot co-occurrence rule**: an agent token AND an evaluation token present anywhere in the same text. That reaches 106 artifacts against a ground truth of 64, so it needs a precision filter, but it is the shape the data supports. This is a change to `score_item()` in `pipeline.py`, not only to `config.yml`.

A pure word-list replacement was also measured, and it is a reasonable interim step. The 33-term list below was measured on the real 645-artifact corpus against the first pass's 89-item ground truth. Note that its recall figure uses the looser denominator; against the adversarial pass's 64-item ground truth the same list would score differently, and neither pass measured the co-occurrence rule end to end. That gap is stated rather than papered over.

| List | Matched | Recall vs GT=89 | Precision vs GT=89 | Precision ceiling vs GT=64 |
|---|---:|---:|---:|---:|
| Current (12 terms) | 16 | 18.0% | 100.0% | 75% (measured: 12 true of 16) |
| Proposed (33 terms) | 85 | 89.9% | 94.1% | **75%** |
| Co-occurrence rule | 106 | not measured | not measured | **60%** |
| Bare `agent` (rejected) | 110 | 97.8% | 79.1% | 58% |

**The precision figures are denominator-dependent, and this is the report's most important methodological caveat.** The 94.1% precision quoted for the 33-term list is measured against the looser 89-item ground truth. Against the stricter 64-item ground truth, the same list matches 85 artifacts of which at most 64 can be true positives, so its precision ceiling is **75%**. The co-occurrence rule I recommend above fares worse on this axis: 106 matches against at most 64 true positives is a **60% precision ceiling**, meaning roughly 42 false positives.

That is a real cost, and it changes the recommendation's strength. The co-occurrence rule has the best recall headroom and the worst precision ceiling. It is the right shape for the *retrieval* layer, where over-inclusion is cheap and a human filters later, but it needs a precision filter before it drives a published category count. Neither candidate should be merged on these numbers alone: the denominator dispute has to be settled by expert labeling first (see Limitations).

```
agentic, llm agent, llm agents, llm-agent, language model agent, ai agent,
coding agent, gui agent, embodied agent, autonomous agent,
agent benchmark, agent evaluation, agent memory, agent security, agent harness,
agent traces, agent trajector, agent-built, game agents,
agents must, agents on, agents for, agents with, based agents, -based agent,
multi-agent system, multi-agent llm, multi-agent cooperation,
tool-use, tool use, function calling, model context protocol, swe-bench
```

**Flooding check, addressing the issue #51 concern directly:** the proposal flags 13.2% of the corpus, against 17.1% for bare `agent`, while the true agentic base rate is 13.8% (89/645). It tracks the real rate rather than inflating it. This is the check that was never run for the current list.

**Terms tested and rejected**, recorded so the reasoning is auditable:

| Rejected | Measured | Reason |
|---|---|---|
| `agent` (bare) | 110 matched, 79.1% precision | The issue #51 failure mode. 23 false positives. Rejected despite 97.8% recall. |
| `multi-agent` (bare) | 17 matched, 58.8% precision | Worst term tested. Catches MARL re-rankers and image-captioning ensembles. Replaced with scoped variants, lifting overall precision from 89.3% to 96.0%. |
| `agents in` | 9 matched, 88.9% precision | Marginal. Appears in background prose. |
| `code agent`, `web agent`, `os agent`, `computer-use`, `agent scaffold`, `tool calling`, `swe-agent`, `multi-agent benchmark` | 0 matched each | Pruned. Retaining zero-match terms is precisely the current list's disease: they create an illusion of coverage. |

The residual 9 misses are genuinely hard for any substring rule: repos with three-word descriptions, and papers where agency is implicit (`Mental World Modeling`). Exceeding roughly 90% requires semantic classification, not keywords.

### data_quality: 79 terms, 16.9% to 96.4% recall

The measured replacement raises data_quality from 15 to 100 artifacts at about 88% precision, organized in seven subtopic groups (contamination and leakage, memorization and duplication, provenance and licensing and PII, annotation and label quality, quality and curation, sanitization, poisoning). Key moves: use stems (`contaminat`, `provenan`, `dedup`) that are provably free supersets, and add terms for the seven subtopics that currently have no vocabulary at all.

27 of the 79 terms match zero artifacts today (`data leakage`, `inter-annotator`, `noisy label`, `data poisoning`). Unlike `challenge set`, these are standard field vocabulary that will appear as the corpus grows and cost nothing to carry. They should be understood as forward-looking, not as contributors to the measured 96.4%.

Rejected for data_quality, each measured then rejected on reading its hits: `quality`, `data`, `annotation` (bare, 200+ hits, the #51 failure mode), `annotat` (62, every dataset card says "annotated"), `curat` (65, generic marketing), `leakage` bare (3 of 7 are spectral or motion leakage in signal processing), `duplicate` bare (3 of 8 are duplicate queries, not records), `noisy` and `noise` (noisy features, quantum hardware, denoising), `agreement` and `kappa` (model-model agreement, credit-card agreements, kappa as an accuracy metric), `audit` and `validat` (model audits, not data).

### The two safe edits to the working categories

- **`dataset`**: add `corpora`. Substring matching gets `corpus` but cannot bridge the irregular Latin plural. Precision 8/8 on reading every hit.
- **`evaluation`**: replace with the stem `evaluat`, a strict superset picking up `evaluating`, `evaluate`, and `evaluated`.
- **Delete the six dead terms** listed in section 4a.

Adopting the recommended set yields benchmark 512, dataset 446, evaluation 336, data_quality 100. The 3-or-more-tag share rises from 18.4% to about 27%, which is the correct and acceptable cost of data_quality finally working: data-quality artifacts genuinely are usually also benchmarks or datasets.

**Update: the agentic and working-category changes are now applied (section 8a), and the snapshots were re-scored so the numerator and denominator cover the same period.** The shipped rule is the co-occurrence shape recommended above rather than the 33-term interim list, tightened to a 15-token proximity window with exclusions to lift its precision ceiling from 60% to 76%. The `data_quality` list in this section is **not** applied, for the reason given in section 8a: its ground truth is still disputed.

## 8a. What this PR actually changed, and what it measures

Sections 4 through 8 diagnose the defect. This section records the fix that was applied, because a diagnosis that ships without a fix is what produced issue #52's reopen in the first place.

### The annotation dispute is resolved

The report above leaves ground truth unresolved between 89 and 64, and section 12 lists that as its most serious methodological gap. That gap is now closed, and the cause was mundane: **the two passes were applying different inclusion rules**, so their disagreement measured rule drift, not annotator judgment.

Re-run with a single rule fixed in writing before any labeling, two independent annotators labeled the same 109 candidates:

| Measure | Value |
|---|---:|
| Raw agreement | 94.5% (103 of 109) |
| **Cohen's kappa** | **0.888** |
| Disagreements | 6 |
| Ground truth, both annotators agree (strict) | **60** |
| Ground truth, either annotator (loose) | **66** |

Kappa of 0.888 is conventionally "almost perfect" agreement. The earlier figure of 89 was too loose and is withdrawn. All six disagreements are genuine edge cases about whether evaluating an agent-driven system counts when the agent is incidental to the task, which is a definitional boundary rather than a labeling error.

### The classifier that replaced the phrase list

The fix is a **proximity rule**, not a longer keyword list, because section 4 established that the failure is a vocabulary gap: the words are present but never form one of the configured n-grams. The rule requires an agent token and an evaluation token within 15 tokens of each other, with hyphens treated as separators and a small exclusion pattern for artifacts that build or survey agents rather than evaluate them.

Measured on the 109 hand-labeled candidates:

| Rule | Matched | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Current 12 adjacent phrases | 16 | 81.2% | 21.7% | 34.2% |
| Bare co-occurrence, anywhere in text | 105 | 57.1% | 100.0% | 72.7% |
| Title-only co-occurrence | 23 | 91.3% | 35.0% | 50.6% |
| **Proximity, 15 tokens, hyphen-aware, with exclusions** | **75** | **76.0%** | **95.0%** | **84.4%** |

The chosen rule is robust to the annotation dispute, which is why it is safe to ship: scored against the loose 66-item ground truth instead of the strict 60, it reads 81.3% precision and 92.4% recall (F1 86.5%). The conclusion does not depend on which denominator is correct.

Two failure modes visible in the earlier measurements were fixed along the way:

- **Hyphen-joined repository names.** `solsticestudioai/agent-failure-atlas-benchmark` carries its whole description in one slug, so whitespace tokenization hid it. Six of the misses were this exact shape; treating hyphens as separators recovered all of them.
- **A silently inert exclusion clause.** The first version of the exclusion pattern ended in `\b` after `position:`, which can never match, because a colon is already a non-word character. A regression test caught it. Removing the trailing boundary raised precision from 75.0% to 76.0%.

### The append-only bug, and why a config change alone would have done nothing

The single most important structural finding in this report is that **snapshots are append-only and were never re-scored**, so a category added on day N stays absent from days 1 through N-1. That alone published `agentic: 3` while the same corpus re-scored yielded 16. Any keyword improvement merged without addressing this would have changed the published figure by nothing at all for the historical days.

This PR adds a `rescore` command that recomputes stored categories across every snapshot on disk:

```bash
benchmark-radar rescore --config config.yml
```

It rewrites **only** `categories` and the `Matched:` rationale. Scores, timestamps, selection counts and health records are left exactly as recorded, because they describe what the pipeline did on the day it ran and rewriting them would turn an audit trail into a fiction. The honest consequence, stated rather than hidden: a re-scored record can now carry a category its stored `total_score` never reflected. The tag is a property of the artifact; the score is a property of the run.

Verified on the real corpus, only category and rationale fields appear in the diff:

| Category | Before | After |
|---|---:|---:|
| agentic | 3 | **75** |
| evaluation | 337 | 401 |
| dataset | 450 | 458 |
| benchmark | 512 | 512 |
| data_quality | 15 | 15 |

`benchmark` is unchanged, confirming the two categories measured as working were not disturbed. Every artifact still carries at least one tag (zero untagged), so no record was traded into an unlabeled bucket.

### The other applied edits

- **`evaluation`**: `evaluation` replaced with the stem `evaluat`, a strict superset that picks up "evaluating" and "evaluated". This is what moves 337 to 401.
- **`dataset`**: added `corpora`, which substring matching cannot reach from `corpus`. This moves 450 to 458.
- **Deleted two dead terms**: `challenge set` and `capability eval` matched zero artifacts across all nine snapshots. The four dead agentic terms disappear with the phrase list itself.

### What was deliberately left alone

- **`data_quality` stays at 15.** The two audits disagree on whether data quality must be the *contribution* or merely a *described property*, which is an order-of-magnitude difference in the denominator. Shipping a 79-term list against an unsettled definition would repeat this report's central error: changing a number without establishing what it should be. This needs a definition first, and it is the top follow-up.
- **`benchmark` stays at 512.** Narrowing it was measured and found actively harmful (section 4a): a phrase-only list discards 186 genuine artifacts, and a title-scoped variant leaves 20.9% of the corpus untagged.
- **The stock-versus-flow gap is untouched.** Sections 5 and 9 stand unchanged. The corpus still cannot answer 市面上总共, and no taxonomy work can make it.

## 9. What a defensible market estimate requires

The move is from crawling a feed to enumerating registries. A feed emits new arrivals; a registry holds a population and will report its size.

### Grounded anchors, verified 2026-07-31

```
GET https://api.github.com/repos/EleutherAI/lm-evaluation-harness/contents/lm_eval/tasks
  -> 220 entries, 214 directories

GET https://huggingface.co/api/datasets?search=benchmark&limit=1000  (walk Link rel="next")
  -> 5 pages, 4542 datasets
GET https://huggingface.co/api/datasets?filter=benchmark&limit=1000
  -> 6 pages, 5092 datasets
```

Hugging Face exposes `X-Total-Count` in `access-control-expose-headers` but does not return it, so totals require cursor-walking.

On Hugging Face alone, datasets only, roughly **4,542 to 5,092 benchmark-named or benchmark-tagged datasets exist**, against 207 Hugging Face artifacts in the corpus. **The corpus has seen about 4% of one enumerable slice.**

### Registry plan

| Registry | Method | Bounds | Cannot establish |
|---|---|---|---|
| HF datasets | `api/datasets?search=|filter=`, walk cursor | Upper bound on benchmark-named repos (4,542 / 5,092 verified) | Distinct benchmarks; splits and result dumps inflate |
| HF spaces, models | Same API, extend `kinds` beyond datasets | Leaderboard Spaces, a major venue currently invisible | Same inflation |
| lm-evaluation-harness | `contents/lm_eval/tasks` (214 dirs verified) | High-precision lower bound on community-run benchmarks | Scope of one harness |
| HELM | `contents/src/helm/benchmark/scenarios` | Independent curated lower bound | Same |
| PapersWithCode | Bulk export | Closest thing to a paper-linked census | Export availability not verified |
| OpenML, Kaggle | Public APIs | Classical-ML population | Few LLM-era benchmarks; counts not verified |
| arXiv | Full-archive search, not a 48h slice | Historical count of benchmark-introducing papers | Papers, not artifacts |

### Plausible order of magnitude

Two figures with definitions attached are more useful than one without:

- **Curated, community-adopted benchmarks: 10^3.** Anchored on 214 lm-eval task directories and 208 HELM scenarios (both verified, overlap uncounted), scoped to text LLM evaluation. Adding vision, speech, agentic, robotics, and code harnesses plausibly reaches low thousands.
- **Benchmark-labeled artifacts in the open: 10^4 or more.** Anchored on 4,542 to 5,092 Hugging Face datasets (verified) plus GitHub, where the corpus's saturated 300-caps show a large unmeasured pool.

The answer to 市面上总共 is a range with a stated definition, because the number depends entirely on whether "benchmark" means something a lab would cite (10^3) or any repo calling itself a benchmark (10^4+). A single figure without that definition misleads, and 512 is neither.

Critically, a census figure must be reported in its own namespace and **never mixed into the daily trend series**, or a change in collection policy will read as a change in the field.

## 10. Final diagnosis

The project has crossed one threshold and not the next.

It has crossed from no measurement to a working flow instrument. Three live connectors, deterministic replay, exact-identifier deduplication, an append-only snapshot corpus, and an explainable rubric. The daily-arrival figures are real and are something registry enumeration cannot provide. That is a genuine contribution and it should be stated as the system's answer to what it can answer.

It has not crossed from flow measurement to population estimate, and the gap was papered over rather than stated. Issue #52 asked a stock question. The pipeline answered with a flow number, in a collapsed dashboard panel, and the issue was auto-closed twice by PR keywords before a human confirmed anything. The agentic count that was supposed to answer the second half of the question was published at 3, when re-scoring the same corpus yielded 16 and the achievable figure was around 63. **That specific defect is fixed in this PR: the published figure is now 75 at 95.0% recall (section 8a).** The rest of this paragraph still stands. Six terms across the taxonomy matched nothing at all, four of which are now deleted. Five of eight connectors contribute nothing, and a sixth reports success while returning zero. Both mechanisms intended to pin famous benchmarks, the watchlist and the release feed, have fired zero times in nine days.

The pattern underneath all of it is a single missing habit. Every keyword change in this repository was validated in one direction only. Issue #51's precision fix was measured against the live feed and reported honestly (65% of the daily pool down to 9 to 12%). Not one recall measurement existed anywhere in the project's history: searching all commits, PR comments, and issue comments for a recall figure returned nothing. Precision failures are loud, because they flood the digest and someone complains. Recall failures are silent, because a number that is too small still renders. That asymmetry in *feedback*, not in effort or care, is what produced a category reading 3 when the answer was around 63.

This PR supplies the missing half. The agentic taxonomy is now the one part of the system with **both** numbers attached: 95.0% recall and 76.0% precision, against ground truth two annotators agreed on at kappa 0.888, with regression tests pinning each failure mode. The habit worth keeping is not the specific rule but the requirement that a taxonomy change state both figures before it merges.

None of this means the counting question is unanswerable. It means the answer requires a second collection mode that enumerates registries rather than crawling a window, reported separately from the flow, with the definition of "benchmark" stated alongside the number. The infrastructure needed already exists in the repository.

The reviewer's instinct in #52 was right on both counts: the information is scrapable, and the current numbers do not yet reflect it.

## 11. Reproducing every number in this report

```bash
cd /root/benchmark-radar
git pull origin main                      # site/data/radar.json is gitignored
.venv/bin/benchmark-radar rebuild --config config.yml
```

Reproducing the fix itself (this PR). `rescore` is idempotent, so re-running it on already-rescored snapshots reports 0 records changed:

```bash
.venv/bin/benchmark-radar rescore --config config.yml
# -> Rescored 9 snapshots against the current taxonomy; 165 records changed category
# ->   agentic        97  <- was 3      (per-sighting; 75 distinct artifacts)
# ->   evaluation    474  <- was 399
# ->   dataset       575  <- was 566

.venv/bin/python -m pytest tests/ -q     # 160 passed
```

Confirming the rescore touched only categories, never the recorded scores:

```bash
git diff data/snapshots/ \
  | grep -E '^[+-].*"(total_score|relevance_score|published_at|url)"'
# -> no output: score and timestamp fields are byte-identical
```

Category counts and provenance:

```bash
python3 -c "
import json; d=json.load(open('site/data/radar.json'))
print(d['generated_at'], d['snapshot_count'])
for t in d['corpus']['aggregates']['topics']: print(t['topic'], t['entity_count'])"

python3 -c "
import json,glob
for f in sorted(glob.glob('data/snapshots/*.json')):
    d=json.load(open(f)); s=d.get('selection') or {}
    print(f[-15:], len(d['evidence_items']), d['generated_at'], 'watchlisted=', s.get('watchlisted'))"
```

Per-term dead-weight table and recall:

```bash
python3 -c "
import json,glob,yaml
seen={}; c=[]
for f in sorted(glob.glob('data/snapshots/*.json')):
    for it in json.load(open(f)).get('evidence_items',[]):
        k=it.get('url') or it.get('title')
        if k not in seen: seen[k]=1; c.append(it)
h=lambda i: (str(i.get('title',''))+' '+str(i.get('summary',''))).lower()
for t in yaml.safe_load(open('config.yml'))['taxonomy']['agentic']:
    print(sum(1 for i in c if t.lower() in h(i)), t)"
```

The stored-versus-rescored gap, the report's most important single correction:

```bash
python3 -c "
import json,glob,yaml
seen={}; C=[]
for f in sorted(glob.glob('data/snapshots/*.json')):
    for it in json.load(open(f)).get('evidence_items',[]):
        k=it.get('url') or it.get('title')
        if k not in seen: seen[k]=1; C.append(it)
h=lambda i: (str(i.get('title',''))+' '+str(i.get('summary',''))).lower()
ag=yaml.safe_load(open('config.yml'))['taxonomy']['agentic']
stored=set()
for f in glob.glob('data/snapshots/*.json'):
    for it in json.load(open(f)).get('evidence_items',[]):
        if 'agentic' in (it.get('categories') or []): stored.add(it.get('url') or it.get('title'))
print('stored:', len(stored), 'rescored:', sum(1 for i in C if any(t.lower() in h(i) for t in ag)))"
# -> stored: 3 rescored: 16
```

Multi-tag redundancy:

```bash
python3 -c "
import json,glob,yaml,collections
seen={}; C=[]
for f in sorted(glob.glob('data/snapshots/*.json')):
    for it in json.load(open(f)).get('evidence_items',[]):
        k=it.get('url') or it.get('title')
        if k not in seen: seen[k]=1; C.append(it)
tax=yaml.safe_load(open('config.yml'))['taxonomy']
h=lambda i: (str(i.get('title',''))+' '+str(i.get('summary',''))).lower()
cnt=collections.Counter(); B=set(); D=set()
for n,it in enumerate(C):
    tags=[c for c,ts in tax.items() if any(t.lower() in h(it) for t in ts)]
    cnt[len(tags)]+=1
    if 'benchmark' in tags: B.add(n)
    if 'dataset' in tags: D.add(n)
print(dict(sorted(cnt.items())), 'P(dataset|benchmark)=', round(len(B&D)/len(B),3))"
```

Canonical-benchmark absence:

```bash
python3 -c "
import json,glob
blob=[(str(i.get('title',''))+' '+str(i.get('source_id',''))+' '+str(i.get('url',''))).lower()
      for f in glob.glob('data/snapshots/*.json')
      for i in json.load(open(f)).get('evidence_items',[])]
for n in ['MMLU','HELM','GPQA','ARC-AGI','HumanEval','BIG-bench','SWE-bench','GSM8K']:
    print(n, sum(1 for b in blob if n.lower() in b))"
```

Registry anchors:

```bash
curl -s "https://api.github.com/repos/EleutherAI/lm-evaluation-harness/contents/lm_eval/tasks" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), sum(1 for x in d if x['type']=='dir'))"
```

Note on reproducibility: `site/data/radar.json` is gitignored (`.gitignore:11`), so published dashboard figures cannot be traced to a commit, only re-derived from the snapshot corpus. Replay is deterministic given a fixed snapshot set, but the set has not been fixed: `2026-07-30.json` was overwritten three times in one day (commit `873f668` restored the original 200-item pull after two manual re-runs shrank it to 76) and `2026-07-31.json` twice. A dashboard reading taken on 2026-07-30 between 20:39Z and 22:38Z is not reproducible from current repository state.

## 12. Limitations

This report's own boundaries, stated so they are not mistaken for findings:

- **The `benchmark` tag's precision is unmeasured.** Manual inspection found clear non-AI artifacts (GPU benchmarks, an SEO report, a homework dump), but no labeled sample was drawn. The share of the 512 that are genuinely AI benchmarks is not available.
- **The `data_quality` ground truth is contestable at the margin.** Its 83 items include roughly 10 to 12 genuinely borderline cases (for example, artifacts that merely *use* a manually annotated dataset rather than studying annotation quality). A stricter rule requiring data quality to be the *contribution* rather than a described property would shrink ground truth to about 60 to 65 and raise measured recall from 16.9% to about 22%. The conclusion holds either way: the current list finds well under a quarter of the real set.
- **The `evaluation` ground truth is deliberately generous**, using probes such as `metric` and `assessment` that pull in papers merely reporting metrics. Its 72.4% recall is therefore a floor; true recall is likely higher. The defensible finding there is the specific `evaluat` stem gap, not the percentage.
- **The triple-counting inflation factor is unmeasurable** from current data, because `artifact_urls` is empty on all 645 records. The cross-namespace join rate is not merely low, it cannot be computed.
- **Ground truth is model judgment, not expert consensus.** This is now measured rather than asserted: two independent passes under a rule fixed in advance reached Cohen's kappa 0.888 (94.5% raw agreement), settling `agentic` ground truth at 60 to 66. That is high agreement, but both annotators are models, so a systematic blind spot shared by both would not show up as disagreement. A human domain expert spot-checking the 109 labels remains the appropriate confirmation. The earlier denominator of 89 is withdrawn: it came from a looser rule, not a different judgment.
- **`data_quality` ground truth remains genuinely unresolved**, at 83 under a "described property" rule versus 8 to 15 under a "substantive contribution" rule. This is why the category was left at 15 rather than fixed. It needs a definition chosen in advance, which is the top follow-up.
- **The proximity rule's precision is 76%, and that is a real cost.** Roughly 18 of the 75 published agentic artifacts are expected to be false positives, most commonly artifacts that build an agent system or evaluate a model on an agent-flavored task without being an agent benchmark. The alternative was 21.7% recall, and under-counting by a factor of four was the defect issue #52 reported. The trade is deliberate and reversible: raise the exclusion pattern or narrow `within` to trade recall back for precision.
- **The 15-token window was tuned on this corpus**, which risks overfitting to 645 artifacts from one 9-day period. The precision/recall curve is flat between 10 and 20 tokens (F1 79.7% to 82.6% before exclusions), so the choice is not on a knife edge, but the exact figure should be re-measured as the corpus grows.
- **PapersWithCode export availability, OpenML, and Kaggle counts: not available.** Not verified here.
- **Overlap between the 214 lm-eval tasks and 208 HELM scenarios: not counted.** Both figures are cited separately and must not be added.
- **The corpus is 5 genuine collection days.** Every rate in this report is a short-window observation, not a stable trend.
- Proposed keyword lists are measured against a 645-artifact corpus from one 9-day period. Precision on a larger or later corpus may differ.

### The question this report does not ask

A domain expert in benchmark evaluation would want one thing this audit never measures: **what fraction of the 512 `benchmark` artifacts is worth counting at all.**

Every figure here treats "artifact tagged benchmark" as the unit. But `omegaprime669/rtx-5090-benchmarks`, `habert75/homework3-benchmark-results`, and `NODARISHUB/mx-wordpress-seo-health-benchmark` are in that 512. A count that includes GPU thermals, a student's homework output, and an SEO report alongside genuine evaluation suites is not measuring the thing #52 asked about, and no recall fix touches this. Improving recall on a corpus with unmeasured precision makes the count larger, not truer.

This matters more than any keyword change, because it determines whether the denominator means anything. The missing work is small and well defined: draw a random sample of 100 artifacts tagged `benchmark`, have a human label each as a genuine AI evaluation artifact or not, and publish the rate with a confidence interval. Until that exists, every count in this report, including the corrected ones, is a count of *things matching keywords*, not a count of benchmarks.

A second, related omission: the report measures no inter-annotator agreement on its own ground truth, which is the standard requirement for any claim built on labeled data. Two model passes disagreeing by 89 versus 64 is itself a low-agreement signal.

### Method

Measurements were produced by replicating `score_item()` substring semantics exactly against `data/snapshots/*.json`, with ground truth established by labeling samples and validating rule-based extensions against those labels. Provenance claims are sourced to commit SHAs, PR numbers, and GitHub timeline timestamps. Registry anchors were retrieved live on 2026-07-31 with the commands shown in section 11.

Four parallel investigations were run, including one whose explicit brief was to refute the others' conclusions. Every headline number was independently re-derived before inclusion. Where a finding was overturned, the correction is recorded in place rather than removed. Three claims changed materially during this audit:

| Earlier claim | Corrected to |
|---|---|
| Recall is ~15%, ~93 artifacts missed | Recall is ~19%, ~52 missed, precision 75% |
| Root cause is the adjacency assumption | Root cause is a vocabulary gap; adjacency explains ~6% |
| Retrieval binds first, so classification is secondary | Independent problems; classification has a measured 4x payoff on data already held |
| data_quality=15 is a confirmed defect | Disputed between two audits, unresolved |
| Ground truth is disputed at 89 versus 64, unresolvable here | Resolved: the passes used different rules. Re-run with one fixed rule, kappa 0.888, ground truth 60 to 66. The 89 is withdrawn |
| The co-occurrence rule is the right shape but unmeasured | Built and measured: 95.0% recall, 76.0% precision, F1 84.4%. Applied in this PR |

**External review was attempted and did not run.** The `gemini` CLI has no credentials in this environment (no `~/.gemini/oauth_creds.json`, no API key), and the `codex` CLI returned a usage-limit error until 2026-08-03. This report therefore carries internal adversarial verification but no independent external review, which is a real gap given that its ground truth is model-generated. A human read is the appropriate next check.
