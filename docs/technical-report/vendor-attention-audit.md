# Vendor-attention sensitivity audit for issue #456

This audit tests the technical report's section 6.1 claim against the reviewed
model-report registry at commit
`98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae`, with an analysis cutoff of
2026-08-31. The definitions and decision rule were posted before the analysis
in [issue #456](https://github.com/ktwu01/benchmark-radar/issues/456#issuecomment-5496051366).
Junkai Wang / [@JunkaiWang-TheoPhy](https://github.com/JunkaiWang-TheoPhy)
contributed the analysis, code, machine-readable tables, and report revision.

## Question and counted units

The primary question is whether a fixed set of benchmarks is repeatedly
reported across organizations, and whether that set survives reasonable changes
to the counting rule. The source is the reviewed `model_cards` array in the
[commit-pinned registry](https://github.com/ktwu01/benchmark-radar/blob/98c8cf6fb5d1d69c66d438ea9f92242b2205c9ae/data/model_cards.yml). One document is one
validated model-card ID and URL. One organization observation is binary: five
documents from the same organization mentioning one benchmark still contribute
one organization. Models, documents, canonical benchmark IDs, reviewed
families, and score tracks remain separate units.

The primary rule keeps canonical benchmark IDs and defines the threshold set as
IDs mentioned by at least six distinct organization labels. Alternative rules
use thresholds of five and seven; model cards only; one latest document per
organization; trailing 365-, 180-, and 90-day windows; an explicit reviewed
family projection; and missing-report stress tests. A card's `revised` date is
used when recorded, otherwise its `published` date. Window boundaries are
inclusive.

Aliases do not merge records automatically. Five normalized collision keys span
four distinct ambiguous benchmark-pair groups in the registry, including MMMU-Pro
and Toolathlon. The reviewed
family mapping resolves those cases explicitly and records primary project or
paper URLs. Family aggregation applies only to mention edges. It never averages
or combines scores, instruments, splits, evaluators, budgets, or protocols.

## Result

The earlier sentence cannot be reproduced from its stated rule. Its eight
listed benchmarks form a strict subset of the 16 canonical IDs that actually
meet the six-organization threshold. The eight-item list is consistent with a
truncated adoption ranking, but a top-eight rule and a six-organization rule are
different selection procedures.

| Pre-registered definition | Documents | Organizations | Threshold set |
|---|---:|---:|---:|
| Full history, canonical IDs, threshold 5 | 37 | 12 | 21 |
| Full history, canonical IDs, threshold 6 | 37 | 12 | 16 |
| Full history, canonical IDs, threshold 7 | 37 | 12 | 10 |
| Model-card documents only, threshold 6 | 15 | 8 | 4 |
| Latest document per organization, threshold 6 | 12 | 12 | 3 |
| Trailing 365 days, threshold 6 | 21 | 11 | 6 |
| Trailing 180 days, threshold 6 | 15 | 9 | 4 |
| Trailing 90 days, threshold 6 | 12 | 8 | 4 |
| Reviewed family projection, threshold 6 | 37 | 12 | 13 resolved identities |
| Remove every organization's newest document, threshold 6 | 25 | 9 | 9 |

The family-projection row contains 5 explicit families + 8 singleton canonical
IDs. It does not claim that all 13 resolved identities are multi-benchmark
families.

| Counting method | Implementation | Identity rule | Selection / threshold | Result output |
|---|---|---|---|---|
| Full history, canonical IDs | `scripts/analyze_vendor_attention.py` | Canonical ID | All documents; 6 organizations | `scenario-summary.csv` → `canonical_all_t6` |
| Time-window, document, and missing-report sensitivities | `scripts/analyze_vendor_attention.py` | Canonical ID | Pre-registered 5/6/7 thresholds, 365/180/90-day windows, latest-per-organization, and drop-newest variants | `scenario-summary.csv`, `sensitivity-membership.csv` |
| Reviewed-family projection | `scripts/analyze_vendor_attention.py` | Explicit families plus canonical singletons | All documents; 6 organizations | `scenario-summary.csv` → `reviewed_families_t6` |
| Reader-facing report | `scripts/build_system_evaluation.py` | Uses the audit rows above | Draft report only | `claim-audit.json` and PDF reference [10] |

The robustness median is 0.4688 when the baseline self-comparison is included,
and 0.3750 when it is excluded; both are below the pre-registered 0.80
retention requirement. The recommendation is therefore unchanged.

The full-history threshold set contains GPQA Diamond, Humanity's Last Exam,
Terminal-Bench, SWE-bench Verified, AIME, LiveCodeBench, MMLU-Pro, SWE-bench
Pro, IFEval, MMLU, BrowseComp, MATH-500, MMMU, HumanEval, GSM8K, and MMMLU.
The trailing-year set contracts to Terminal-Bench, Humanity's Last Exam, GPQA
Diamond, SWE-bench Pro, SWE-bench Verified, and BrowseComp. Keeping one latest
document per organization leaves only Terminal-Bench, GPQA Diamond, and
Humanity's Last Exam.

The pre-registered exact-membership rule also fails. Median Jaccard similarity
across the full-scope document and identity alternatives is 0.4688, below the
0.80 retention threshold. Six of the 16 baseline members—BrowseComp, GSM8K,
HumanEval, MATH-500, MMMLU, and MMMU—do not survive every leave-one-organization
or leave-one-document stress test. MMLU-Pro and SWE-bench Pro survive those
single omissions but drop out when every organization's newest document is
removed. BrowseComp is particularly instructive: it appears in six
organizations in the trailing-year window and falls below the threshold when a
supporting organization is omitted.

## Recommendation

Replace the exact convergence sentence with the following narrower statement:

> In the reviewed sample through 2026-08-31, 16 canonical benchmark IDs were
> reported by at least 6 organizations across the full history; the trailing
> 365-day window contained 6, and retaining only each organization's latest
> document contained 3. A recurring reporting group is visible, but its
> boundary depends on the time window, document selection, identity grouping,
> and support threshold.

This wording reports the observable relation without treating the registry as a
complete vendor census or presenting one sensitivity choice as a natural law.

## Evidence and limitations

The committed outputs are designed for different audit questions:

- [`document-benchmark-edges.csv`](vendor-attention-audit/document-benchmark-edges.csv)
  links each counted mention to its document ID, URL, organization, model, date,
  and raw benchmark ID.
- [`organization-benchmark-matrix.csv`](vendor-attention-audit/organization-benchmark-matrix.csv)
  reconstructs the binary table. Empty cells are labelled `not_observed`, not
  absent.
- [`scenario-summary.csv`](vendor-attention-audit/scenario-summary.csv) records
  every pre-registered rule and threshold set.
- [`sensitivity-membership.csv`](vendor-attention-audit/sensitivity-membership.csv)
  reports per-benchmark support and leave-one-out results.
- [`claim-audit.json`](vendor-attention-audit/claim-audit.json) records the
  original claim, decision rule, result, recommendation, alias collisions,
  family evidence, and limitations.

The registry is a reviewed convenience sample. It has no complete vendor
universe or exhaustive report-inclusion frame. Some document comments identify
benchmarks that were visible in a source but not yet represented in the
canonical registry. An unobserved edge can therefore reflect an omitted report,
an unread image or table, a living document changed after retrieval, or a
benchmark outside the tracked identity set. Organization strings identify
publishers, not audited corporate parents. These limitations make the
sensitivity result useful for narrowing the claim, but they do not support an
estimate of field-wide vendor behavior.
