# Issue #533 exact-source repair

The repair path is `benchmark-radar repair-source`. It accepts one reviewed
stable identifier per invocation and writes through the existing dated snapshot
merge path. The source's publication/creation timestamp stays in
`published_at`; the later repair time is recorded in `discovered_at` and
`retrieved_at`; `event_kind: backfilled` keeps the record out of released-only
recent rankings.

The confirmed historical cases now present in the Radar snapshot are:

| Source | Stable ID | Inclusion decision |
| --- | --- | --- |
| arXiv | `2608.23564` | included as SWE Refactor Bench benchmark/evaluation |
| GitHub | `aiming-lab/RSI-Exam` | included through the named RSI-Exam watchlist |
| arXiv | `2506.18795` | included as FORGE benchmark/evaluation/dataset |
| GitHub | `shenyimings/FORGE-Artifacts` | included as the linked dataset artifact |

The command supports arXiv, GitHub, Hugging Face datasets/spaces/models, and
DOI metadata through Crossref. Re-running a repair for the same source merges
one identity into the existing snapshot rather than duplicating it. The Radar
query service and dashboard all-dates search index `source_id`, so each repair
is recoverable by its human name and stable identifier.

Example commands:

```bash
benchmark-radar repair-source --source-type arxiv --source-id 2608.23564
benchmark-radar repair-source --source-type github --source-id aiming-lab/RSI-Exam
```

The repair records remain in the Radar evidence layer. They are not inserted
into the external benchmark catalog, model-card adoption registry, or curated
score archive.
