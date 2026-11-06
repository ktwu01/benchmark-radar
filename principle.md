# Benchmark Radar principles

## The product covers 1,259+ benchmark records across 4+ sources

This is the operating scale of Benchmark Radar. It is not a small collection
of benchmarks from model cards. Every benchmark-facing chart, search, table,
count, and export must start from the full population across all sources.

The benchmark catalog in `benchmark-index.json` contains the whole population,
including model reports, OpenCompass Hub, Artificial Analysis and LLM Stats.
The baseline was 1,259 records across four sources when this rule was introduced.
Include registry entries that have citations but no scores, and entries with
neither measurement. Rebuild the data and calculate the current total and source
count. Never hard-code these numbers into the interface or add report records
again after reading the unified index.

**If a main surface contains only a few dozen benchmarks, assume records are
missing and investigate. Do not present that subset as Benchmark Radar.**

### Paper analyses must use the frozen full catalog

For the paper, use the **frozen v0.11.0 release**, software commit
`8f46bbfa91f5d9900c8b08a5d552c3df5c9597b0`, and verify the released input hashes.
Do not substitute current `main`, the live website, or a newer collection.
The 1,259+ baseline is a coverage alarm, not a replacement for the record count
computed from that frozen catalog.

This requirement applies separately to every main results table and analysis,
including documentation, reported scores, headroom, and dates. Reading the full
index and then selecting only model reports does not satisfy it. Neither does
placing the full census in an appendix while the main findings describe only
a few dozen report benchmarks. Trace each reduction through the actual joins,
source predicates, and measurement requirements before accepting a result.

Every analysis must export the complete source-record ID set, preserve available
measurements, and report per-source coverage in its main table. Unknown units
can prevent a headroom calculation; they cannot remove numeric scores from the
score analysis. Unknown dates, documents, or organizations remain unknown on
their records. A narrow statistic may supplement the full-catalog analysis only
when its eligibility and missing evidence are explicit. Never invent a scale,
merge similarly named records, or inflate a count to meet the coverage baseline.

Keep the units of every count explicit. **Benchmark records, cited documents,
scored models, organizations, and score observations are different quantities.**
Only benchmark-record counts reconcile to the full catalog. A document count or
a count of eligible records must never answer the question “how many benchmarks
does the product cover?” Generate paper table cells and repeated quantitative
claims from the same audited frozen inputs; check their consistency before
building and delivering the PDF.

Every numeric value below 100 appearing in the rendered paper must emit:
`less than 100 is abnormal, ref to https://github.com/ktwu01/benchmark-radar/blob/main/principle.md`.
Check PDF text and rendered figure images, including page numbers, citations,
dates, model versions, percentages, and individual source counts; do not silently
exempt categories. Report the page, number, and surrounding text for review.
This is a warning requirement, not permission to alter the frozen evidence.
Missing PDF extraction or OCR tools must fail visibly. Regression tests must
verify warning emission and prevent the removed report-subset exporter and
`example-data.tex` from returning.

Check which sources, records, and fields disappeared at each join or filter.
A successful render, plausible Pareto frontier, or passing test does not excuse
missing most of the population. Each surface starts from the same catalog;
filters apply to the surface the reader is using, as described below.

## Leaderboard and Saturation share a cutoff; search bypasses it

Both tabs use the same score slider, initially 70. On Leaderboard it filters
only Benchmark Frontier and its coverage counts. The score ranking keeps its
numeric-score and date eligibility but does not follow the slider.

Saturation contains the benchmark browser and complete reported score histories.
With an empty search it applies the shared cutoff across all years, retaining
unscored records as unknown rather than inventing scores. With a search query it
searches the entire catalog, including every source, year and unscored record,
without applying the cutoff. Searching does not change the slider; clearing the
query restores filtered browsing. Selecting a result keeps its complete history,
even when it lies outside the current browsing cutoff.

## One corpus, one record contract, equal treatment of sources

Model reports and benchmark registries contribute to the same catalog. Normalize
their benchmarks, model identities, observations, documents and citations into
the same structures before any chart, search, count or export reads them. The
downloadable catalog and the website must cover the same benchmark IDs.

Use source names as provenance: **Model reports**, **OpenCompass Hub**,
**Artificial Analysis**, **LLM Stats**. Do not introduce "internal", "external",
"curated" or "crawled" tiers that change inclusion, ranking, visual prominence,
or access to a measurement. Name modules for their job or source, such as
`catalog_opencompass`, and use `data/catalog/` for shared normalization products.
Keep old public commands as aliases when a rename would break existing clients.

Keep model-card citations in the same evidence collection as registry citations.
A document type describes evidence; it does not create another benchmark corpus.
Source adapters may parse different inputs, but consumers must not reconstruct
the population by concatenating a preferred registry with an optional supplement.
If the catalog cannot load, show the failure instead of a plausible shortlist.

Equal treatment means applying the same rules to the same kinds of evidence.
Keep score values, units, protocols, dates and citations attached to their source
record. A score and a citation are different measurements. Count distinct models
by model identity and documents by document identity; repeated observations do
not create extra models or documents. Unknown values stay unknown. Apply scale
and protocol requirements by available evidence, never by source membership.

Preserve one record per source benchmark and its stable links. Link records only
through reviewed identity evidence; a similar name cannot justify combining
models, adding counts, averaging scores or assuming matching test protocols.

## Put the figure first; collect explanations in one information note

Place **all legends below the main figure** they explain, including domain
colors, organization colors and mark shapes. Keep only the keys needed to read
the visible marks expanded. Axis names, units, ticks and essential missing-data
labels belong on the plot; paragraphs about the method do not.

Collect coverage, source totals, exclusions, count definitions, date caveats,
projection explanations and Pareto rules in **one collapsed `(i)` note below
the figure**, beside its legend. For example, "342 of 1,259 benchmarks shown",
"Height recorded for 342 of 342", and "Same scores and selected counts; time
omitted" all belong in that note. Update its counts when filters change.

The note must work with keyboard and touch, have an accessible name, and keep
its contents out of the layout while closed. Do not scatter the same caveat
across the heading, plot, legend and footer. A loading failure or empty result
needs a visible status; an information note must not hide a broken surface.

## Frontier and its score ranking require a reported score

The user explicitly requested this filter: **exclude benchmarks with no numeric
reported score from Benchmark Frontier and its linked score ranking**, including
when the score slider is set to All. Remove the "No score reported" bands and
marks. A genuine score of zero is still a reported score and must remain.

Start from the full corpus, apply this filter, and account for the excluded
records in the counts. Keep the records in the underlying catalog, general
search and dataset exports. A source with no scored records may have zero
visible marks in this view; do not invent scores to preserve source counts.

This exception only concerns missing scores. Missing adoption, an unknown date
or an unverified score scale must not hide a record that has a numeric score.
Keep scored records on other scales inspectable and outside Pareto calculations.
The rules below apply after this explicit filter on the Frontier surface.

## Missing measurements do not delete corpus records

Having a score, release date, reviewed identity, or source-document count
is not a requirement for belonging to the corpus. Do not use an inner join
against the model-report registry to define the main chart's population.

Keep records with missing measurements visible and individually inspectable,
using a clearly labelled missing-data area or another suitable representation
within the same surface. A footnote saying that hundreds of records were
excluded does not replace showing them. Do not invent dates, treat unknown
counts as zero, or rename score observations as unique model cards.

**The main visualization must draw every benchmark that survives the user's
explicit filters, one mark per source record, by default.** Counting a record
in the header, retaining it in search, or putting it in a collapsed list does
not count as drawing it. A 28- or 29-point skyline above a hidden catalog still
fails this rule even when the header says 1,259. Missing dates, adoption or score
units must choose a visible representation, never remove a scored mark.

Preserve the dimensions that are known. A benchmark with a reported score and
date belongs on the time × score plane even when adoption is unrecorded; use
an explicit unknown-count mark. Keep unverified source scales visually
distinct from normalized scores and out of Pareto calculations. Benchmarks
whose numeric score cannot use the main scale retain dated, individual marks.
A generic holding area below a tiny report-only chart is not sufficient when it
discards known dimensions.

A numeric score cutoff may hide records whose known scores are at or above it.
Records without scores cannot be classified as above or below the cutoff;
Frontier excludes them with its separate reported-score requirement. Show the
full population and account for the visible records, pre-2024 records, records
excluded for missing scores, and records hidden by score. Count each
record once so the categories reconcile.

## A filtered benchmark is worse than a flagged non-benchmark

**We cannot tolerate a benchmark being filtered out. A non-benchmark being
flagged is tolerable.** A benchmark that an admission, taxonomy, or suppression
rule removes never reaches any surface, and nobody can see that it is missing.
A non-benchmark that gets in stays visible, so a reader can report it, as with
the OpenClaw release in #1001.

Before adding or tightening such a rule, run it against every record in the
committed snapshots and list each record it would remove. If one of them is a
benchmark, a benchmark paper, or an evaluation tool, reject the rule or narrow
it. Say which inputs the test could not cover. #1011 is an example.

## No quality judgement is not no judgement

Benchmark Radar does not grade a benchmark's merit. It never says a benchmark
is good or bad, and it leaves comparing scores to the people who use the data.

That is not permission to hand readers hundreds of unsorted releases a day. A
reader who opens the Leaderboard needs a short, defensible list. Benchmark
Radar therefore triages:

- **Rank by disclosed signals.** Attention (stars, upvotes, downloads) and the
  institutions behind the paper are signals a reader can check. Print every
  input, its weight and its source next to the rank, so the order can be
  disputed, not just trusted.
- **Demote placeholders.** A repository that holds only a README, a licence or
  images has announced a benchmark, not shipped one. Keep it listed and
  unranked, with the reason, below the releases that ship code or data.
- **Demote, never delete.** Triage moves a record down or flags it. It does
  not remove it from the corpus, search or exports (see the rule above).
- **Missing stays unknown.** A release with no institution on file gets no
  affiliation credit; it is not given an average and its weight is not
  redistributed.

The harm this prevents: an unranked firehose pushes the sorting onto every
reader, and an attention-only ranking lets an empty repository with a viral
announcement outrank a benchmark that ships its data.

## Calculate only what the evidence supports

Represent every record, but compute a statistic only from records with the
measurements that statistic requires. State measured coverage in the figure's information note or the
exported metadata. In particular, Pareto eligibility requires a declared common score
scale and a recorded value for the selected count. Unknown measurements must
never become zeros or qualify a point for the frontier.

Keep source identities and provenance. Two source records with similar names
are not permission to merge scores or transfer adoption counts. A shared
display scale does not establish equivalent test protocols.

## Chart heights must use the measurements in the full corpus

The default Frontier height is **Models with reported scores**: distinct models
with numeric scores for that source's benchmark record. Aggregate score records
already contain hundreds of model IDs for some benchmarks; a chart that only
uses the small model-report registry discards that measured coverage.
Deduplicate by the source's model ID, preserving separately evaluated
configurations. Report observations use the exact organization and model name.
Repeated scores, protocols and source documents for the same model must not
increase this count. If model identities are incomplete, mark the count unknown.

The **Source documents** height option counts distinct cited documents through
the same evidence collection for every source, including model cards and
registry pages. Models, score rows and documents are different quantities.
Never substitute or sum them, transfer a count between similarly named source
records, or label hundreds of evaluated models as hundreds of documents. Both
counts and the selected coverage must be inspectable. Switching height measures
must preserve the filtered benchmark IDs.

Use `log1p(count)` for height and raw counts for ticks, tooltips and dominance.
Derive the maximum from the entire scored 2024+ cohort for the selected measure,
before the score cutoff. Do not cap it at 20, 100 or any fixed value.
The wall projection uses the same selected count as the main chart; unverified
score scales retain hollow projections and remain outside Pareto calculations.

## Use benchmark dates and show only 2024 onward

The Benchmark Frontier timeline starts on **2024-01-01, inclusive**. Exclude
earlier benchmarks from this view; do not add an earlier segment or clamp them
to the start of the axis. Keep the original records in the underlying corpus
and account for the date filter in the displayed counts.

Use the benchmark's valid release date first. If it has no release date, use
the earliest dated numeric LLM score for that benchmark, labelled **First LLM
score reported**. Take the earliest score across the available history, before
applying the 2024 cutoff; do not pick its first score after 2024 to force it into
the view. Keep the evidence and date basis inspectable. A batch crawl timestamp
or an adoption-only mention is not a score date.

A missing date in a crawl is a gap to investigate. Check the benchmark's own
release announcement, dataset card, and introducing paper before leaving it
undated. Store recovered dates with their exact source-record key, citation,
and basis, and regenerate the chart's inputs. A README's bibliography can
contain older component methods and unrelated datasets; its earliest paper
is not automatically this benchmark's release. New dates must reach the main
timeline, with their evidence accessible from the mark.

An old model can be evaluated retrospectively on a new benchmark. Audit any
pre-2024 exclusion based only on a model-release proxy, especially records with
hundreds of scored models. HLE and SciCode must not disappear merely because
their evaluated models include releases from 2023. Recover the benchmark's own
date before interpreting such a proxy as evidence of benchmark age.

When an aggregator dates its numeric LLM score records by model release, use
the earliest dated score record as a **model-release proxy**, after any known
benchmark release or actual score-publication date. Carry that date precision
into the chart and tooltip. Do not discard all such records or move hundreds
of scored benchmarks into a second chart: they belong in the main skyline.
Never label this proxy as the benchmark's release or actual score-publication
date. It is the earliest score-entry date available from that source.

If neither date is known, show an individual mark in the main visualization's
clearly labelled undated panel, visible without expanding anything. Preserve
its score position when a score is known. Do not place it at an invented point
on the dated axis or claim it belongs to the 2024+ cohort. Report dated,
undated, pre-2024, and other filtered counts so they reconcile to the full
population. Unknown dates do not satisfy the pre-2024 exclusion condition.

Position dated marks chronologically, using the exact date on a linear axis.
Do not arrange them alphabetically inside year bins. Separate overlapping marks
without changing their dates; explain any stacking or alternate layout. A mass
of benchmarks landing on one collection day is a date-provenance defect to
investigate, not evidence that they were all introduced that day.

## Diagnose from real records, not from a plausible story

Before fixing a bug or designing a feature, pull the actual records it affects
and read them. A cause that sounds right is still a guess until the data shows
it. Fixing a guessed cause can leave the real defect in place and still pass the
tests written for the guess.

Example: ingest discarded "future-dated" records. The first fix assumed time-zone
skew on Hugging Face and widened the tolerance to one day. The run snapshots
showed 53 of 56 discards since 2026-08-31 came from Zenodo. A live Zenodo record
created on 2026-10-27 carried an uploader-entered publication date of
`2026-10-31`, four days ahead, which a one-day tolerance still drops. Another
carried `2027`, which the parser could not read, so the record was skipped
without being counted. Zenodo's API documentation settles the cause:
`publication_date` is "Date of publication ... Defaults to current date", set by
the depositor with no range check, while `created` and `modified` are the
deposition's own timestamps (https://developers.zenodo.org/#deposit-metadata).
Count the cases by source, open a few, read the source's API documentation for
the field, then fix.

The fix follows from those cases. An uploader-entered date can be in the future
or unreadable; the platform's own creation timestamp (`created`, the date the
upload or repository was opened) cannot. When the source date is in the future
or unreadable, keep the record, keep the source value as given, and date it by
`created`, labelled as that basis. Quarantine with a warning only when `created`
is also in the future, as with a record dated 2050. If a source has no creation
timestamp, keep the record with an unknown date; never substitute the crawl time.

## Verify coverage before delivery

- Rebuild the inputs and compute the full population and its sources.
- Check that every input record is represented or accounted for by the explicit
  date, reported-score and cutoff filters, including records without measurements.
- Count actual individually inspectable marks in the default main chart and
  compare their IDs with the filtered full corpus. Counts or collapsed lists
  cannot substitute for missing marks. Every source with matching scored records
  must render; account for sources excluded by the reported-score requirement.
- Check that filtered, visible, and unknown counts reconcile to that population.
- Test missing fields and every source, not just a few model-report fixtures.
- Check that report records and their citations reach the index, detail shards,
  website and offline archive once each. Verify the 577 model IDs for Artificial
  Analysis HLE and SciCode and 492 for CritPt from the source observations.
- Inspect the UI at desktop and mobile widths: legends below their figures,
  secondary annotations inside one closed information note, and no lost marks.
- Verify release-date priority, earliest-score fallback, the inclusive 2024
  boundary, rejection of crawl dates, and explicit labelling of model-date
  proxies. Missing adoption must not remove dated scores from the main plot,
  and undated records must remain inspectable.
- Treat an unexplained drop from thousands of records to dozens as a defect
  that blocks delivery.

These coverage rules apply alongside the interface guidance in `design.md`.
If a narrower interpretation of that guidance would drop a source or a record
because a measurement is absent, follow this file.
