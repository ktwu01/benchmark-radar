# SOP: adding a model card

Use this when a vendor publishes a model card, system card, technical report or
release post and you want it in the registry. It covers the whole change: the
document, any benchmark it introduces, and the scores it reports.

`CONTRIBUTING.md` has the short version for a first contribution. This file is
the complete procedure, including the parts the short version leaves out.

Two files move together:

| File | What it stores |
| --- | --- |
| `data/model_cards.yml` | The document, and which benchmarks it mentions. Never a number. |
| `data/benchmark_scores.yml` | The numbers that document reports, one row each. |

A card added without its scores is not a finished change. It leaves a model in
the registry that the score progression and paired comparison readout cannot
see, and nothing reports the gap afterwards.

## Before you start

You need the document itself, open in front of you. Every value below is read
out of it. If you are working from a summary, a screenshot of a table someone
posted, or memory of what the model scores, stop here: this dataset's only claim
is that any row can be checked against its source.

Confirm the URL loads, and that it points at the document you actually read
rather than a landing page that links to it.

## Step 1: register the document

Append to the `model_cards:` block in `data/model_cards.yml`.

```yaml
  - id: acme_frontier_1_model_card
    organization: Acme
    model: Frontier-1
    document_type: model_card
    published: 2026-05-14
    url: https://acme.example/frontier-1-model-card
    retrieved_at: 2026-09-11
    benchmarks:
      - gpqa_diamond
      - swe_bench_verified
      - aime
```

Required: `id`, `organization`, `model`, `url`, `benchmarks`. The loader rejects
an entry missing any of them.

| Field | Notes |
| --- | --- |
| `id` | Unique. Score rows cite it, so treat it as a stable key. |
| `document_type` | One of `model_card`, `system_card`, `technical_report`, `release_post`, `benchmark_leaderboard`. |
| `published` | The document's own date, not the model's release date. ISO `YYYY-MM-DD`. |
| `retrieved_at` | When you read it. It is not refreshed automatically. |
| `url` | Must be HTTP(S), and one URL per document. |
| `revised` | Optional. Only for a document that genuinely gained a benchmark after publication, such as an arXiv report at v2 or a living card the vendor edits in place. |
| `benchmarks` | Canonical ids, each resolving against the `benchmarks:` block. |

The counted unit is the document. A card reporting AIME at pass@1, at
consensus@64, and again with a Python tool contributes exactly one adoption, so
a long appendix cannot outvote a different vendor.

A leaderboard published by the benchmark's own authors goes in
`source_documents:` instead, which additionally requires `name` and `publisher`.

## Step 2: add any benchmark the registry is missing

Every id used in step 1 must already exist in the `benchmarks:` block. An
unknown id is a hard error, because a typo would otherwise invent a phantom
benchmark with exactly one adopter, indistinguishable from a real benchmark
nobody adopted.

```yaml
  - id: acme_reasoning_eval
    name: Acme Reasoning Eval
    aliases: ["ARE", "Acme Reasoning Eval"]
    domain: reasoning
    url: https://arxiv.org/abs/2604.01234
    released: 2026-03-02
    caveat: >-
      140 items, so run-to-run variance is wide and a single reported number
      hides it.
```

Required: `id`, `name`, `domain`, `caveat`.

`caveat` is required rather than optional. The ranking's headline risk is being
read as a quality ordering, and the per-row caveat is what stops a saturated or
contaminated benchmark from sitting near the top with no qualification. Write
what would mislead someone comparing two reported numbers, for example a small
split with wide variance, or a score that depends on scaffold and tool access.
Do not write a generic gloss inferred from the benchmark's name.

`url` must point at the benchmark's real homepage or paper, and you must open it
to confirm. A plausible-looking guess at a GitHub path is worse than no link: it
looks checkable and is not. When you cannot find a real one, omit `url`.

`released` is the benchmark's own publication date. It lets a reader separate a
newly adopted benchmark from a newly published one. Omit it rather than guess.

## Step 3: add the scores

Append to `data/benchmark_scores.yml`. Two blocks usually need an edit.

**Metric identity**, once per benchmark, in the `benchmarks:` block. A benchmark
absent here has no metric, direction or unit for its rows to render against.

```yaml
  - benchmark_id: acme_reasoning_eval
    metric: accuracy
    direction: higher_is_better
    unit: percent
```

Required: `benchmark_id`, `metric`, `direction`, `unit`. `direction` is
`higher_is_better` or `lower_is_better`, and it exists because not every metric
improves upward. An edit-distance metric inverts the axis, and a chart that
assumed higher-is-better would draw the progression upside down.

**One row per reported number**, in the `results:` block.

```yaml
  - benchmark_id: acme_reasoning_eval
    instrument: acme_reasoning_eval
    protocol: thinking on, pass@1
    model: Frontier-1
    organization: Acme
    source_id: acme_frontier_1_model_card
    reported_at: 2026-05-14
    value: 71.4
    read_from: pdf_text
```

All nine fields are required. Three of them carry the comparability contract:

- **`instrument`** is version identity, kept separate from `benchmark_id`.
  Terminal-Bench 2.0 and 2.1 share an id and are different instruments, because
  2.1 changed 28 of 89 tasks. Same for HumanEval against HumanEval-Mul, or GPQA
  full against Diamond. This is what stops a task-set change from reading as
  model progress.
- **`protocol`** is the comparability class. Record what the source said moves
  the number: thinking budget, tool access, pass@1 against consensus@k. Silence
  is not agreement, so two documents that both omit tool access are not evidence
  that their setups matched. Do not leave it generic to make rows look joinable.
- **`source_id`** must name a document registered in `data/model_cards.yml`, and
  that document must actually report the benchmark being scored. The loader
  checks the pair, because an id mistyped to a different real card would
  otherwise publish a number with false provenance.

`read_from` is how you read the value: `pdf_text`, `html_text` or
`table_image`. The interface grades evidence on this field, so it is not a
formality.

Optional:

- `measurement_kind` defaults to `reported_self_score`. Use
  `benchmark_publisher_run` only when the benchmark's own publisher ran the
  measurement, which additionally requires the cited document to be a
  `benchmark_leaderboard` with a named `publisher`.
- `reported_by` marks a third-party citation, where the publisher repeated a
  competitor's self-reported figure. That is weaker evidence, and weaker still
  when the publisher had a stake in the comparison. The interface marks these
  rather than mixing them in.

Score rows are per model, not per document. A card covering a Pro, Lite and Mini
release gets one row per variant. Collapsing three systems into one label makes
the series meaningless.

### Recording the value

Record the number exactly as printed. Do not round it, convert it, or reconcile
it with a figure from elsewhere.

If a document publishes its table as an image and a value cannot be read with
certainty, add nothing. An absent row is honest, a guessed row is not.

A note on precision: GPQA Diamond has 198 items, so a single-run accuracy can
only land on multiples of about 0.505 points. A reported 92.1% therefore cannot
be a plain single-run accuracy over the full split, which is why `protocol`
carries the run treatment when the source states it.

## Step 4: rebuild and verify

```bash
benchmark-radar rebuild
pytest -q
```

Before opening the pull request, run the full CI sequence from `AGENTS.md`
against a clean checkout.

## What the loader rejects

These fail the build loudly, which is the point. A mistake should not silently
shift the ranking.

- A card or benchmark entry missing a required field.
- A benchmark id used by a card but absent from the `benchmarks:` block.
- A new benchmark with no `caveat`.
- A `url` that is not HTTP(S).
- A date that is not a real ISO calendar date.
- A card reporting a benchmark released after the card, with no `revised` date.
- A score row citing a `source_id` that no card or source document declares.
- A score row citing a document that does not report that benchmark.
- A score row for a benchmark with no metric identity entry.
- A percent value outside 0 to 100.
- A `read_from`, `direction` or `measurement_kind` outside its allowed set.
- Two rows for the same model on the same instrument, under the same protocol,
  from the same document. That is a contradiction: the chart would draw two
  points at one position with no way to say which is the reading.
- A `benchmark_publisher_run` row whose document is not a registered leaderboard
  with a named publisher.

## What the loader cannot catch

Each of these passes validation and is still wrong, so they are on you:

- A number transcribed from the wrong row or column of a table.
- A `protocol` string that omits a condition the document stated.
- A `caveat` that describes what the benchmark sounds like rather than what it
  measures.
- A `url` that resolves but points at an unrelated project with a similar name.
- A benchmark recorded as mentioned when the document only cites it in related
  work rather than reporting a result.
