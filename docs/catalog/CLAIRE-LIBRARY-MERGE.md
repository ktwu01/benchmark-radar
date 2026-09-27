# Claire Library → Benchmark Radar.org: merge report

## What this contribution gives org

The complete public/local Claire Library contributes **3,346 source IDs**.
The build enriches **674 existing org records** from 677 incoming IDs and adds
**2,669 records**, taking the catalog from **1,284 to 3,953 records**. All
original Claire fields and versions remain recoverable. Existing org score
observations are unchanged; this is a metadata and category import, not a score
import or an assertion that all records represent distinct, verified benchmarks.

中文摘要：不是只导入已审核的 422/477 条，也不是把 1,999 和 3,186 相加。
本次取公开与本地数据的完整并集，明确重复的条目补入 org，歧义条目单独保留；
分类对齐并去重，额外字段和原始版本不丢失，不混合测试版本或分数。

## Scope and counts

Audit date: 2026-09-27. Target baseline:
`ktwu01/benchmark-radar@895af2a46e2566b61c67a795a2533af291ffb0cc`.
Public input: `Claire1217/benchmark-radar@fd5868b3b9c983a6f25c50c274de3be1694ffa00`.

| Input or outcome | Records / IDs | Meaning |
| --- | ---: | --- |
| Public `library_index.json` | 3,186 | Broad Library, including catalog, family and variant records |
| Public `benchmarks.json` | 1,999 | All IDs already occur in the public Library; supplies richer original fields |
| Local `library_index.json` | 2,805 | Frozen working-copy data, not silently assumed identical to public |
| Local `benchmarks.json` | 1,914 | Frozen original representations |
| Union of all four inputs | 3,346 | One input entry per ID, retaining all available versions |
| Local-only IDs | 160 | Retained rather than lost by importing public `main` alone |
| Public-only IDs | 541 | Retained rather than lost by importing the local checkout alone |
| Incoming IDs mapped to existing org records | 677 | 676 exact catalog-ID matches; one name + paper + repository match |
| Distinct org records enriched | 674 | Several incoming IDs can supplement the same org record |
| Added without a proven existing identity | 2,661 | Not claimed to be globally unique benchmarks |
| Added with ambiguous exact candidates | 8 | Preserved separately for identity review |
| Resulting catalog | 3,953 | 1,284 existing + 2,669 added |

The input includes 40 explicit families, 15 variants, 15 explicitly typed
benchmarks, 1,121 catalog entries and 2,155 records without an explicit type.
An absent type is not evidence of verification. Review states and
`displayEligible` are retained, not used to discard records from the full corpus.

## Field mapping and conflict policy

| Claire fields | org representation | Safety rule |
| --- | --- | --- |
| `id`, `name`, `source` | Stable source key, name, provenance | Existing org keys, names and slugs remain unchanged; new keys use `claire-radar:<id>` |
| `catalogSources` | Exact lookup of existing LLM Stats / OpenCompass keys | Multiple targets stay ambiguous; no score transfer |
| `aliases` | `aliases` | Union across public/local representations |
| `links` | `artifacts` | Valid resource links; known paper/repository/dataset identifiers normalized; original links retained |
| Category axes | `categories` plus original axis-specific fields | Reuse org spelling for case-equivalent labels; preserve existing category order; append deduplicated additions |
| `releasedAt` and date evidence | `released` and reference on **new** records | Valid day-level dates only; existing org dates, including unknown dates, remain unchanged |
| `description`, `oneLine` | Labelled editorial text in the detail panel and original extension | Do not present potentially AI-assisted text as a quoted source description |
| Publishers, taxonomy modalities/tasks/protocols, metrics, usage, stars, heat, curation, evidence, parent/family relationships and every other field | `extensions.claire_radar.records[].versions` | Preserve exact objects; no lossy scalar conversion, invented score, publisher role, or family identity |
| Taxonomy definitions and input manifests | Index `import_metadata.claire_radar.manifests` and frozen bundle | Keep category definitions and versions, not just labels |

Common mapped values prefer public Library, public raw benchmarks, local Library,
then local raw benchmarks; missing source/link subfields are filled individually.
Aliases and category assignments use all versions. Conflicting original values
are never overwritten in the retained versions.

The flat category projection covers `libraryCategories`, `researchDirections`,
`researchTopics`, `area`, `applicationDomains`, `capabilities`, `topics`,
`capabilityGroups`, `catalogCategories`, `primaryDomain` and `industrySectors`.
It contributes 245 distinct mapped labels and 20,058 input-ID/label assignments.
The three public taxonomies retain their 38 Library directions, 29 research
directions and 20 research topics. These are separate axes, not 87 equivalent
categories. Nested `benchmarkTaxonomy` and `researchFacets` remain structured in
the extension. Synonyms across taxonomies are not guessed to be equivalent.

## What deduplication does—and deliberately does not do

1. Coalesce identical source IDs across the four input files, preserving every
   original version. The 1,999 raw records are not added a second time.
2. Use explicit catalog source IDs to supplement org records already representing
   that source. The one additional confirmed resource match is ELBench →
   `opencompass:2571`, with the same normalized name, paper and repository.
3. Within new records, require the same source ID, name and record type, or the
   same name plus two independent resource types. Keep family/variant records
   out of the resource-based join.
4. Never merge by name alone, strip meaningful `+` signs/version numbers, or
   treat a repository subdirectory as its parent repository.

213 incoming decisions have additional name-only candidates in the ledger.
This is a review signal, **not 213 proven duplicates**. Existing org cross-source
records and reviewed identity groups are not collapsed by this contribution.

### Eight ambiguous inputs retained separately

| Incoming name | Conflicting org IDs / distinction |
| --- | --- |
| MBPP | `mbpp` versus `mbpp+` |
| Graphwalks Parents 128K | `<128k` versus `>128k` |
| MMMU (val) | `mmmu-(val)`, `mmmu-(validation)`, `mmmuval` |
| MBPP Plus | `mbpp+` versus `mbpp-plus` |
| Graphwalks BFS 128K | `<128k` versus `>128k` |
| HumanEval Plus | `humaneval+` versus `humaneval-plus` |
| HumanEval | `humaneval` versus `humaneval+` |
| Terminal-Bench | `terminal-bench` versus `terminal-bench-2` |

The decision ledger gives the complete input IDs and candidate keys. A later
review may link genuine equivalents; it should not erase version differences.

Eight incoming release values disagree with populated org release dates; org
values win. Another 131 incoming dates are unknown/sentinel or month/year-level
values and stay out of the common day-level date field. In particular,
`0001-01-01` is not a benchmark release date. Raw values remain available.
Incoming dates also do not fill unknown dates on existing org records: doing so
would alter score-chart date eligibility without a separate date review.

## Where reviewers can inspect the data

- Frozen input: [`data/imports/claire_library/manifest.json`](../../data/imports/claire_library/manifest.json)
  and the adjacent `library.json.gz` (about 3.7 MiB).
- Every original record field: generated `site/data/benchmarks/<slug>.json`,
  under `record.extensions.claire_radar.records[].versions`.
- Every decision, candidate, date conflict and original taxonomy:
  generated `site/data/claire-library-merge.json`.
- Website detail panel: “Library categories / 分类”, review status, labelled
  editorial description, and expandable original fields and versions.
- Offline data release: the same full index and shards, including extensions.
  The compact search index is intentionally not a copy of all original fields.

The frozen gzip SHA-256 is
`7eeec72744dcfa41622a62312419658b64be2778b71aabf4b96988b95b44eb60`.
The manifest records SHA-256 receipts for each original input file. It explicitly
labels local snapshots as working-tree inputs rather than assigning them the
public commit. Building does not require access to the contributor's checkout.

## Reproduction and acceptance checks

Use a clean checkout, initialize recursive submodules, install `.[dev]`, then run:

```sh
ruff check .
ruff format --check .
benchmark-radar normalize-catalog
benchmark-radar classify
benchmark-radar build-data-release
pytest -q
```

The new tests compare every original record object with the published shard
extension, reconcile all source IDs, check category coverage and stable org
identities, and compare every existing score observation with its normalized
source object. The existing corpus/export tests reconcile the website and
offline release. Expected score observations remain LLM Stats 5,544, Artificial
Analysis 7,050 and model reports 335: **12,929 unchanged observations**.

The larger corpus changes lexical-search IDF and top results. Updated relevance
examples are backed by the records' names/descriptions; former examples retain
exact-name tests. “Weather forecasting” now has forecasting-only candidates,
which remain labelled partial matches. The ranking algorithm was not changed.

No daily collection behavior, model-card scores, upstream report, paper's frozen
release or submodule pointer is changed. This is a frozen import, not a new live
sync service. Future updates should replace the frozen input deliberately,
review the regenerated ledger and repeat the same acceptance checks.

Rollback is a revert of the contribution followed by the normal build. Org's
original input snapshots are not rewritten. No direct edit to generated output
is necessary.
