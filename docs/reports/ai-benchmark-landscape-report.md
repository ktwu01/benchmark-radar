# AI Benchmark Landscape Report

## Market scope, agentic evaluation, and the limits of live discovery

> Report date: July 31, 2026  
> Evidence cutoff: 2026-07-31T14:31:49Z  
> Repository: [ktwu01/benchmark-radar](https://github.com/ktwu01/benchmark-radar)  
> Origin: [Issue #52](https://github.com/ktwu01/benchmark-radar/issues/52)  
> Author: [Koutian Wu](https://ktwu01.github.io/)

## Executive findings

Benchmark Radar currently supports two different products. The first is already useful: a live monitor of newly released or updated AI evaluation artifacts. The second is the product requested in issue #52: a census and interpretation of the benchmark market. The current pipeline does not yet support that second claim.

This distinction changes the meaning of every headline number.

The validated snapshot corpus contains 645 distinct artifacts from 791 sightings. Its current tags are 512 benchmark, 450 dataset, 401 evaluation, 78 agentic, and 15 data quality. These tags overlap. They describe the observed corpus, not the total market, and they must not be added together.

The most informative finding is not the corrected agentic count. It is the shape of the observed agentic segment. Of the 78 tagged artifacts, 53 come from arXiv, 17 from Hugging Face, and 8 from GitHub. Transparent content probes show that software engineering and computer use, tool use and planning, memory and long-horizon behavior, professional tasks, and security dominate the material. This points to a field moving from static question answering toward sustained action in technical and operational environments.

The report also identifies why a market total remains unavailable. Four of nine snapshot dates are simulated. Only three source families contribute any corpus records. Nineteen of 20 canonical benchmarks tested are absent. No artifact has a populated cross-source link, so a paper, repository, and dataset for the same benchmark may remain separate. The watchlist has not fired once. These are properties of the measurement system, not minor footnotes.

Issue #52 should therefore become a recurring landscape report with four modules:

1. a registry-based census of the installed benchmark stock;
2. a live monitor of new and updated artifacts;
3. a research interpretation of emerging evaluation themes;
4. an audit of coverage, classification quality, and uncertainty.

The present corpus can support modules 2, 3, and part of 4. A separate registry-enumeration mode is required for module 1.

## 1. The decision this report supports

An expert reader does not need a single answer to “how many benchmarks exist?” without knowing what was counted. The useful decisions are more specific:

- Which evaluation areas are expanding?
- Which artifacts appear to be gaining use?
- Where is agent evaluation moving beyond static tests?
- Which parts of the landscape are missing from the radar?
- How much confidence should a reader place in each number?
- What additional collection work would turn observed activity into a market census?

The report is designed for evaluation researchers, benchmark maintainers, research leaders, and teams deciding where to build or adopt evaluation infrastructure.

## 2. Measurement contract

### 2.1 Units that must remain separate

| Unit | Meaning | Supported now? |
|---|---|---|
| Sighting | One source record on one snapshot date | Yes |
| Artifact | A deduplicated paper, repository, dataset, or release record | Yes, within exact identifiers |
| Benchmark | An evaluation construct with tasks, data, protocol, and metrics | Not reliably resolved |
| Benchmark family | Related versions or modalities under one lineage | No |
| Market stock | The installed population at a stated date | No |
| Discovery flow | Newly released or updated artifacts inside the collection window | Yes |

The dashboard’s 512 benchmark-tagged artifacts are neither 512 distinct benchmark families nor an estimate of the market stock. They are observed artifacts whose source text matched the current benchmark taxonomy.

### 2.2 What the corpus contains

The corpus joins nine versioned daily snapshots:

| Measure | Value |
|---|---:|
| Snapshot dates | 9 |
| Genuine collection dates | 5 |
| Simulated dates | 4 |
| Sightings | 791 |
| Distinct artifacts | 645 |
| Latest sighting marked released | 444 |
| Latest sighting marked updated | 201 |

The four simulated dates are useful for testing history and presentation. They are not observed market activity. Trend work must either exclude them or label them separately.

### 2.3 Confidence language

Every future edition should attach one of three labels to each result:

- **Measured:** directly derived from validated snapshots or a fully enumerated registry.
- **Estimated:** inferred from a labeled sample, with the sample size and interval stated.
- **Directional:** a content signal that suggests a pattern but has not been validated as a field-wide trend.

The category totals below are measured properties of the corpus. The market interpretation is directional. The installed market total is unavailable.

## 3. Observed benchmark landscape

### 3.1 Source composition

| Source | Distinct artifacts | Share of corpus |
|---|---:|---:|
| arXiv | 383 | 59.4% |
| Hugging Face | 207 | 32.1% |
| GitHub | 55 | 8.5% |
| **Total** | **645** | **100%** |

This is a research-heavy view of the ecosystem. arXiv supplies nearly three fifths of the corpus, while Hugging Face supplies nearly one third. GitHub is a small share of published artifacts despite repeatedly hitting the 300-item fetch cap. OpenReview, Semantic Scholar, OpenAlex, Brave Search, and the curated GitHub release feed contribute no corpus artifacts in the stored period.

The source mix affects interpretation. arXiv exposes proposed methods and benchmark papers. Hugging Face exposes datasets and result stores. GitHub exposes implementations, harnesses, and repositories. A change in connector health can therefore look like a change in the field even when research activity is unchanged.

### 3.2 Category composition

| Category | Distinct artifacts | Share of corpus |
|---|---:|---:|
| benchmark | 512 | 79.4% |
| dataset | 450 | 69.8% |
| evaluation | 401 | 62.2% |
| agentic | 78 | 12.1% |
| data quality | 15 | 2.3% |

These categories are multi-label. Most artifacts carry two or three tags:

| Tags per artifact | Artifacts | Share |
|---|---:|---:|
| 1 | 79 | 12.2% |
| 2 | 347 | 53.8% |
| 3 | 194 | 30.1% |
| 4 | 24 | 3.7% |
| 5 | 1 | 0.2% |

The largest combinations are benchmark plus dataset (168), benchmark plus evaluation plus dataset (142), and benchmark plus evaluation (95). This overlap is substantively plausible, because a benchmark often packages a dataset and an evaluation protocol. It also shows why the existing category names are weak market segments. They describe artifact components, not buyer needs, task domains, modalities, risk levels, or deployment settings.

The next taxonomy should add analytical dimensions rather than replace the existing tags:

- modality: text, vision, audio, video, multimodal, embodied;
- task environment: coding, web, desktop, science, health, finance, robotics;
- evaluation target: model, agent, multi-agent system, judge, retrieval system, data pipeline;
- evaluation property: capability, safety, reliability, efficiency, robustness, data integrity;
- maturity: proposal, dataset release, runnable harness, leaderboard, adopted standard;
- access: open data, gated data, hosted evaluation, private benchmark.

Those dimensions would let an expert compare like with like. “Benchmark” and “dataset” alone cannot do that.

### 3.3 Activity and maturity signals

The latest sighting for each artifact marks 444 as released and 201 as updated. This split suggests that maintenance activity is a material part of the observed flow, not noise to discard. An update to a benchmark, dataset, or harness may matter more to practitioners than another first release.

Adoption fields are available for 262 of 645 artifacts: all 207 Hugging Face artifacts and all 55 GitHub artifacts. Of those 262, 224 have at least one nonzero metric and 38 have observed zero values. GitHub supplies stars and forks, and Hugging Face supplies downloads and likes. The 383 arXiv records in this corpus carry no comparable citation signal. Missing metrics and measured zero values must remain separate.

The highest observed adoption scores include an evaluation harness, leaderboard datasets, result stores, and collections. This mix is another warning against treating every artifact as one benchmark. A market report should distinguish benchmark definitions from infrastructure and result repositories before ranking adoption.

## 4. Agentic evaluation as an emerging segment

### 4.1 Corrected size inside the observed corpus

The published agentic count moved through three states:

| State | Distinct artifacts | What the number meant |
|---|---:|---|
| Stored historical tags | 3 | Only snapshots written after the category was introduced |
| Same corpus re-scored with the old phrases | 16 | Historical coverage repaired, vocabulary still narrow |
| Re-scored with the proximity rule | 78 | Current published corpus count |

The current rule requires an agent term and an evaluation term within 15 tokens. On 109 labeled candidates, two independent model annotators reached Cohen’s kappa of 0.888. Against the stricter shared-positive set, the rule measured 95.0% recall and 73.1% precision.

This is a useful classifier for discovery, but it is not an expert-validated market label. At the measured precision, about one quarter of tagged items may sit outside a strict definition of an agent benchmark. A human review of the labeled candidates remains necessary before the figure is used in an external market claim.

### 4.2 Source mix

| Source | Agentic artifacts | Share of agentic set |
|---|---:|---:|
| arXiv | 53 | 67.9% |
| Hugging Face | 17 | 21.8% |
| GitHub | 8 | 10.3% |
| **Total** | **78** | **100%** |

Agentic evaluation is even more paper-heavy than the full corpus. This may mean that proposed tasks and methods are arriving faster than reusable implementations. It may also reflect source bias: the GitHub queries are capped, and several scholarly connectors are inactive. The report should track the paper-to-runnable-artifact conversion rate over longer windows before calling this a maturity gap.

Adoption fields are present for 25 of the 78 agentic artifacts, and 23 have at least one nonzero metric. Neither figure is a usage rate because arXiv lacks a comparable metric in the current data. They show that adoption evidence is sparse and source-dependent.

### 4.3 Research themes

The following probes are transparent keyword scans over the 78 tagged artifacts. They overlap and are directional, not a second ground-truth taxonomy.

| Theme signal | Artifacts matched in title or summary | Share of agentic set |
|---|---:|---:|
| Software engineering and computer use | 56 | 71.8% |
| Tool use and planning | 39 | 50.0% |
| Memory and long-horizon behavior | 27 | 34.6% |
| Domain and professional tasks | 25 | 32.1% |
| Security and safety | 22 | 28.2% |
| Multi-agent coordination | 7 | 9.0% |

The probe text is the lowercased title plus summary. The exact Python regular expressions are versioned here so the table can be reproduced:

- Software engineering and computer use: `code|coding|software|web|browser|gui|computer|office|database|terminal|devops|repository|repo|swe`
- Tool use and planning: `tool|planning|plan\b|workflow|function.call|action|reasoning`
- Memory and long-horizon behavior: `memory|context|long.horizon|long.term|persistent|trajectory`
- Domain and professional tasks: `health|patient|medical|finance|financial|legal|science|scientific|aerial|bim|education|robot`
- Security and safety: `secur|attack|pentest|vulnerab|red.team|poison|privacy|stealth|risk|safe`
- Multi-agent coordination: `multi.agent|orchestrat|cooperat|collaborat|team|coordination`

Three interpretations follow.

First, agent evaluation is centered on environments, not isolated questions. Software repositories, browsers, office tools, databases, and operational workflows appear throughout the set. The unit being evaluated is increasingly a trajectory of actions against stateful systems.

Second, memory and long-horizon behavior are becoming evaluation objects in their own right. Several artifacts test persistence, contamination, retrieval, or downstream consequences rather than treating context as a fixed input.

Third, security is both a task domain and an evaluation property. The corpus includes offensive-security agents, stealth, memory poisoning, and safety-related behavior. A future landscape report should separate “agents performing security work” from “security evaluation of agents,” because they answer different research and procurement questions.

The small multi-agent coordination signal is also informative. Multi-agent language is common in AI papers, but relatively few observed artifacts combine it with a nearby evaluation construct under the current rule. That may indicate a gap between system-building papers and dedicated multi-agent evaluation.

## 5. What the radar cannot infer from the present corpus

### 5.1 A market total

The pipeline uses a 48-hour lookback and repeated daily collection. That measures arrivals and updates. Established benchmarks do not need to emit a new timestamp, so a short-window feed cannot reconstruct the installed stock.

The coverage test is direct and deliberately identity-scoped. The report searched the `title`, `source_id`, and `url` fields of all 791 sightings for 20 canonical names: MMLU, HELM, GPQA, ARC-AGI, HumanEval, BIG-bench, MMMU, GSM8K, HellaSwag, TruthfulQA, WebArena, tau-bench, OSWorld, MLE-bench, PaperBench, lm-evaluation-harness, MLCommons, EvalPlus, openai/evals, and SWE-bench. Nineteen have no artifact-level match in those identity fields. The only match is a third-party SWE-bench-related Hugging Face artifact, not the canonical Princeton repository. Ten names do appear as references inside summaries, but a paper mentioning MMLU or HELM does not place the MMLU or HELM artifact in the corpus.

At the same time, the corpus includes GPU hardware benchmarks, SEO health reports, homework result repositories, and site-performance records whose names contain “benchmark.” The current count therefore misses much of the known stock while including artifacts outside a strict AI-evaluation definition.

The direction of error is not uniformly low or high. Missing established benchmarks pushes the count down. False positives and cross-source duplicates push it up. Without a labeled precision sample and identity resolution, the net error is unknown.

### 5.2 Field-wide trends

Five genuine collection dates are too short for a trend claim. Three of those dates have arXiv and GitHub at their 300-item fetch cap. July 31 has only 69 arXiv inputs while GitHub remains capped. These days are not directly comparable representations of upstream activity.

The corpus can describe what arrived in the monitored channels during this period. It cannot yet establish whether a research area is accelerating across the field. Future trend claims need a longer window and a fixed connector-coverage signature.

### 5.3 Cross-source adoption and benchmark families

No one of the 645 artifacts has a populated `artifact_urls` field, and no artifact is observed across multiple source namespaces. The exact-identifier join is implemented, but it has no cross-source evidence to use.

This prevents several expert questions:

- Which papers have released runnable code and data?
- How long does paper-to-harness conversion take?
- Which benchmark families have multiple versions or language ports?
- Which artifacts are independent adoptions rather than mirrors or result dumps?

Cross-source identity is the highest-value data-engineering gap after the market census itself.

## 6. Instrument audit

### 6.1 Connector realization

The project configures eight discovery connectors, but the stored corpus contains records from only arXiv, Hugging Face, and GitHub. On July 31:

| Connector | Fetched | Result |
|---|---:|---|
| GitHub | 300 | Active, at cap |
| Hugging Face | 89 | Active |
| arXiv | 69 | Active |
| GitHub Releases | 0 | Reports success, returns nothing |
| OpenReview | 0 | HTTP 403 |
| Semantic Scholar | 0 | HTTP 429 after retries |
| OpenAlex | 0 | API key not configured |
| Brave Search | 0 | API key not configured |

Configured coverage is not realized coverage. The daily report should publish both, and market claims should be blocked when required source families are absent.

The GitHub release connector is a special case. It is the only connector aimed directly at several established benchmark repositories, yet it returned zero records on all seven dates where its health was recorded. The July 27 and July 28 snapshots contain no health row for this connector and are unobserved, not zero. A release-only feed inside a 48-hour window is an event monitor, not a stock collector.

### 6.2 Taxonomy validity

Issue #52 exposed two separate failure modes.

The first was temporal: a category introduced after older snapshots were written appeared to cover only one day. The new `rescore` command repairs category tags across stored history while preserving recorded scores and timestamps.

The second was linguistic: adjacent phrases missed common constructions such as “benchmark for LLM-based agents.” The proximity rule lifted measured recall from 21.7% to 95.0%, with precision falling from 81.2% to 73.1% under the strict labels.

The lesson is procedural. A taxonomy change should not merge until it reports:

- a written inclusion rule;
- a labeled evaluation set;
- precision, recall, and F1;
- performance by source;
- a check for time-dependent snapshot effects;
- an out-of-sample or later-window validation.

### 6.3 The unresolved data-quality category

The 15 data-quality artifacts should not be interpreted as the size of data-quality evaluation. Two audits used different definitions:

- data quality as any described property of an artifact;
- data quality as the artifact’s substantive contribution.

Those definitions produce an order-of-magnitude difference. The correct next step is a definition decision, followed by labeling. Expanding the keyword list before that would make the count move without making it more meaningful.

## 7. Registry anchors for a future census

A stock estimate requires enumerating registries, not extending a recency window. Two official endpoints provide immediate anchors as of July 31, 2026:

- The [lm-evaluation-harness task directory](https://api.github.com/repos/EleutherAI/lm-evaluation-harness/contents/lm_eval/tasks) contains 214 directories among 220 entries.
- The Hugging Face datasets API returns 4,548 datasets for [`search=benchmark`](https://huggingface.co/api/datasets?search=benchmark&limit=1000) and 5,099 for [`filter=benchmark`](https://huggingface.co/api/datasets?filter=benchmark&limit=1000), counted by following every pagination cursor.

These are not additive market totals. lm-evaluation-harness directories may contain grouped tasks. Hugging Face results include mirrors, result stores, variants, and artifacts that use “benchmark” loosely. They demonstrate scale and provide sampling frames.

A defensible census should enumerate at least:

| Registry or source | Census role | Main bias |
|---|---|---|
| Hugging Face datasets, models, and spaces | Open datasets, models, leaderboards | Mirrors, result stores, name inflation |
| GitHub code search and curated repositories | Harnesses and implementations | Repositories are not benchmark families |
| lm-evaluation-harness and HELM | Curated runnable tasks and scenarios | Framework-specific scope |
| arXiv historical search | Benchmark-introducing papers | Papers are not runnable artifacts |
| OpenReview historical search | Conference submissions | Venue and access differences |
| OpenML and Kaggle | Classical ML and hosted competitions | Different community and unit definitions |

The census output should be a range under explicit definitions, not one universal number. At minimum, publish:

- a high-precision lower bound for curated runnable benchmarks;
- a broader count of benchmark-labeled open artifacts;
- overlap and deduplication estimates;
- a sampling-based precision estimate for each registry;
- the date and query used for every count.

## 8. Proposal for issue #52

### Proposed issue title

**AI Benchmark Landscape Report: Market Scope, Agentic Evaluation, and Coverage Gaps**

### Proposed deliverable

Issue #52 should produce a versioned report, not another dashboard total. Each edition should contain:

1. **Reader brief:** five findings and their confidence labels.
2. **Market census:** registry counts, definitions, overlap, and uncertainty.
3. **Live activity:** new releases, material updates, and source-normalized rates.
4. **Landscape map:** domain, modality, evaluation target, property, maturity, and access.
5. **Agentic evaluation deep dive:** environments, horizon, tools, memory, safety, and task domains.
6. **Adoption view:** runnable artifacts, stars, downloads, citations, and hosted leaderboards, reported by source rather than forced onto one scale.
7. **Measurement audit:** connector health, caps, synthetic data, classifier metrics, and identity gaps.
8. **Research agenda:** missing benchmarks, under-evaluated capabilities, and infrastructure priorities.
9. **Reproducibility appendix:** commands, data cutoff, definitions, and known limits.

### Acceptance criteria

The issue is complete when all of the following are true:

- “benchmark,” “artifact,” “family,” “stock,” and “flow” are defined.
- Stock and flow appear in separate tables and visualizations.
- Registry enumeration covers more than one artifact ecosystem.
- A random sample of at least 100 benchmark-tagged artifacts is human-labeled for precision, with an interval.
- Agentic classification is checked by a domain expert and validated on a later window.
- Paper, repository, dataset, leaderboard, and result-store records can be linked into benchmark families where exact evidence exists.
- Every headline number carries a source, cutoff date, and confidence label.
- Simulated dates and connector-incomplete dates are excluded from trend estimates.
- The generated report can be rebuilt from committed snapshots and versioned analysis code.

### Implementation sequence

#### Phase 1: Define and validate

Write the counting ontology and labeling guide. Draw the 100-artifact precision sample. Have a human review the 109 agentic candidates and resolve the data-quality definition.

#### Phase 2: Add census collection

Create registry enumerators that run separately from daily discovery. Store registry, query, retrieval date, raw identifier, and pagination provenance. Do not mix census rows into daily trend snapshots.

#### Phase 3: Resolve identities and families

Extract paper, code, dataset, project-page, DOI, and benchmark-family links. Merge only on exact identifiers or reviewed evidence. Report unresolved possible matches instead of silently joining them.

#### Phase 4: Build the analytical taxonomy

Add domain, modality, target, property, maturity, and access labels. Validate each dimension separately. Preserve the existing operational tags for retrieval and triage.

#### Phase 5: Publish the recurring report

Generate the landscape report from versioned census and flow datasets. Use monthly or quarterly windows for interpretation, while retaining the daily radar for discovery.

## 9. Reproducibility

Rebuild the corpus from committed snapshots:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/benchmark-radar rebuild --config config.yml
```

Recompute taxonomy tags across stored history:

```bash
.venv/bin/benchmark-radar rescore --config config.yml
```

Run the verification suite:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
```

The source of record is `data/snapshots/*.json`. The generated `site/data/radar.json` is intentionally untracked. Market-census inputs do not yet exist in the repository and should be added as a separate versioned dataset.

## 10. Limits of this edition

- The report covers five genuine collection dates and four simulated dates.
- The benchmark tag’s precision has not been measured on a random human-labeled sample.
- The agentic ground truth was produced by model annotators, not a domain expert.
- The agentic theme probes overlap and use keywords rather than reviewed labels.
- Adoption metrics differ by source and are missing for arXiv records.
- No current artifact carries a cross-source link.
- The data-quality category lacks an agreed inclusion rule.
- The Hugging Face and GitHub registry anchors are live counts and will change.
- No field-wide growth rate or installed market total is claimed.

## Conclusion

Issue #52 can become the analytical center of Benchmark Radar. The daily pipeline already provides an auditable view of new activity. The corrected agentic classifier reveals a useful research segment, especially around software environments, tool use, memory, professional tasks, and security. The same audit also shows that live discovery, market enumeration, identity resolution, and research interpretation are separate jobs.

The next step is to preserve the radar’s strength as a flow instrument while adding a registry-based census beside it. The resulting report would tell an expert what is appearing, what is being maintained, where evaluation is moving, how much of the market is visible, and which conclusions remain uncertain. That is a durable answer to issue #52.
