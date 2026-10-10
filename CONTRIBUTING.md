# Contributing / 参与贡献

Thanks for considering a contribution. This page is the single starting point:
what we merge, what we don't merge, and the problems that most often hold a pull
request back. Read it before you open a PR. It takes five minutes and can save
you a week of review rounds.

感谢参与。本页是唯一的入口：我们合并什么、不合并什么，以及最常卡住 PR 的问题。开 PR 前请先读完，
五分钟可以省下一周的来回修改。

| You want to… / 你想… | Read / 阅读 |
| --- | --- |
| Add a model card, benchmark or score / 添加模型卡、benchmark 或分数 | [`docs/sop-add-model-cards.md`](docs/sop-add-model-cards.md) |
| Change a chart, search, table, count or export / 改图表、搜索、表格、计数或导出 | [`principle.md`](principle.md) |
| Touch a source, generator or generated file / 改数据源、生成器或生成文件 | [`docs/pipeline-and-data-map.md`](docs/pipeline-and-data-map.md) |
| Earn points / 赚积分 | [`docs/contributor-points.md`](docs/contributor-points.md) |
| Work as an AI agent / 以 AI agent 身份工作 | [`AGENTS.md`](AGENTS.md) |

## 1. What we merge / 我们合并什么

### The most useful thing you can add: a model card

The [Model Card Adoption Rank](README.md#model-card-adoption-rank) answers a
question nobody else is tracking: which benchmarks do frontier vendors actually
report when they ship a model? Its value grows with every document it has read,
and it is curated by hand because no reliable parser for vendor PDFs and release
posts exists. The registry is schema-validated, so a mistake fails the build
loudly rather than silently shifting the ranking.

Append an entry to `model_cards:` in [`data/model_cards.yml`](data/model_cards.yml):

```yaml
  - id: acme_frontier_1
    organization: Acme
    model: Frontier-1
    document_type: model_card       # or system_card, technical_report, release_post
    published: 2026-05-14           # the document's date, not the model's
    retrieved_at: 2026-08-02        # when you read it
    url: https://acme.example/frontier-1-model-card
    benchmarks: [gpqa_diamond, swe_bench_verified, aime]
```

The loader enforces these rules:

- **Record what the document reports, not what the model can do.** The counted
  unit is the document. A card reporting AIME three ways contributes one
  adoption, so a long appendix cannot outvote a different vendor.
- **Every benchmark id must already exist** in the `benchmarks:` block. A typo
  would otherwise invent a phantom benchmark with exactly one adopter.
- **One URL per document.** The same report under two ids would count twice.
- **A card cannot report a benchmark released after it.** If a living document
  really gained a benchmark later, record the real `revised` date.
- **A new benchmark needs a `caveat`:** what would mislead someone comparing two
  reported numbers, such as a small split or a score that depends on tool access.
- **Scores move with the card.** Every number you can read with certainty from
  the document goes in [`data/benchmark_scores.yml`](data/benchmark_scores.yml),
  with the document cited. Read every value out of the document, never from memory.

### Every PR we merge does these things

- **Starts from the full corpus.** Every benchmark-facing chart, search, table,
  count and export covers all records across all sources (1,259+ records across
  4+ sources at minimum). Missing measurements never remove a record. If your
  surface shows a few dozen benchmarks, records are missing. See
  [`principle.md`](principle.md).
- **Makes one change.** One logical change per PR. A connector, a page and a
  restyle are three PRs. Stacked PRs say so and land in order.
- **Is current and green.** Rebased on the latest `main`, with the full CI
  sequence passing from a clean checkout (`git worktree add`, then
  `git submodule update --init --recursive`):

  ```bash
  ruff check .
  ruff format --check .
  benchmark-radar normalize-catalog
  benchmark-radar classify
  benchmark-radar build-data-release
  pytest -q
  ```

- **Shows UI changes.** Before/after screenshots at desktop and phone width,
  light and dark. Keep the existing header, logo, colors and layout. UI changes
  are merged on design quality, so keep the first screen simple.
- **Cites primary evidence.** Every entry links to the official paper, card,
  dataset or leaderboard it came from. Nothing asks a reader to take our word.
- **Fixes a real bug with a regression test.** Name the failure, show the test
  failing before the fix and passing after. Comments explain what the design
  prevents, not what the code does.
- **Discloses authorship.** You may add a benchmark you wrote. Say so in the PR.

### 中文

- **最有价值的贡献：模型卡。** 在 `data/model_cards.yml` 的 `model_cards:` 下追加条目；benchmark id
  必须已存在；每个文档只用一个 URL；新增 benchmark 必须写 `caveat`；文档中能确定读出的分数一并写入
  `data/benchmark_scores.yml`，数值只从引用文档中读取，不凭记忆。详见 `docs/sop-add-model-cards.md`。
- **从完整语料出发。** 所有面向 benchmark 的图表、搜索、表格、计数和导出都覆盖全部来源的全部记录；
  缺少测量值不能删掉记录。只显示几十条 benchmark 就说明有记录丢失。见 `principle.md`。
- **一个 PR 只做一件事。** 连接器、页面、改样式是三个 PR；有依赖的 PR 要写明并按顺序合并。
- **基于最新 main，CI 全绿。** 在干净的 worktree 中按上面顺序跑完六步。
- **UI 改动附截图。** 桌面和手机宽度、浅色和深色的前后对比；保留现有页头、logo、配色和布局。
- **引用一手证据。** 每条记录都链接到官方论文、模型卡、数据集或排行榜。
- **修 bug 要带回归测试。** 写明故障，测试在修复前失败、修复后通过。
- **披露作者身份。** 可以添加自己写的 benchmark，但要在 PR 中说明。

## 2. What we don't merge / 我们不合并什么

Stated up front so nobody writes work that has to be turned down.

- **Scores in the adoption registry.** Vendors differ on prompt, scaffold, tool
  access, reasoning budget, pass@k and evaluator. A mention survives all of
  those caveats, which is why it is the unit the ranking publishes.
- **Any ranking presented as a quality judgement.** Adoption measures vendor
  attention, not benchmark quality.
- **Fuzzy matching that silently merges records.** Entities resolve on exact
  identifiers (DOI, arXiv, OpenReview, GitHub, Hugging Face).
- **Synthesized summaries.** A missing upstream description stays empty.
- **Scraping behind authentication.** No cookies, logged-in sessions, private
  posts, or LinkedIn and X scraping.
- **Hand-edited generated files.** `site/data/models.json`,
  `site/data/logo-registry.json`, `site/data/radar.json` and the catalog index
  and shards are regenerated by the build. Fix the source data and rerun the
  generator; never patch the output.
- **Self-cited source documents without official data.** Your own system
  report, solution repository or participant paper registered as a benchmark's
  leaderboard or evidence. Cite the organizers' official leaderboard or paper.
- **Stale or unrelated history.** A branch that no longer shares history with
  `main`, or that brings back old commits, snapshots or files. Replay your own
  commits onto a fresh branch from `main`.
- **Paper material.** Report drafts, figures and analysis folders for the
  technical report go to
  [`benchmark-radar-paper`](https://github.com/ktwu01/benchmark-radar-paper),
  not this code repository.
- **Useless bug fixes.** Changes without a reproducible failure a user could
  hit: cosmetic churn, defensive code for impossible inputs, rewording, or
  tests that pin source text or today's data counts instead of behavior.
- **Floods of AI-generated PRs.** AI-assisted work is welcome when a person has
  read and checked it and it states the model (`330226 <model-id>` in a PR
  comment, see `AGENTS.md`). Many near-identical or unverified agent PRs are
  closed without review.

### A real example of a flood / 真实案例：刷屏式提交

Between 2026-09-29 and 2026-10-09, one account opened **58 pull requests and
11 issues**. At the peak, 56 PRs and 11 issues were open at the same time.

- **Bursts faster than anyone can review.** 15 PRs in 37 minutes on
  2026-09-30 ([#716](https://github.com/ktwu01/benchmark-radar/pull/716) to
  [#730](https://github.com/ktwu01/benchmark-radar/pull/730)). On 2026-10-06,
  29 PRs in one day, including 8 in 27 seconds
  ([#768](https://github.com/ktwu01/benchmark-radar/pull/768) to
  [#775](https://github.com/ktwu01/benchmark-radar/pull/775)).
- **Self-issue, self-PR.** On the afternoon of 2026-10-06 the account filed 11
  issues ([#782](https://github.com/ktwu01/benchmark-radar/issues/782) to
  [#798](https://github.com/ktwu01/benchmark-radar/issues/798)), then opened a
  PR "fixing" each one minutes later. For example, issue
  [#788](https://github.com/ktwu01/benchmark-radar/issues/788) at 14:01 became
  PR [#799](https://github.com/ktwu01/benchmark-radar/pull/799) at 14:15. An
  issue written by the PR's own author, to justify that PR, is not evidence
  that anyone needs the change.
- **Hypothetical edge cases.** Most reproductions were inputs no user or source
  had produced: a JSON number `1e400` turning into Infinity, a single-quoted
  `url('a/*b*/c.png')` in the CSS minifier, an HTTP-date `Retry-After` header,
  `xml:base` in Atom feeds, a source title crafted as `MemoryBench](https://wrong.test)`.
  Each came with long, polished, AI-generated verification text.
- **Outcome.** Five PRs were merged, the ones that fixed silent data loss in
  the corpus or a real report bug
  ([#706](https://github.com/ktwu01/benchmark-radar/pull/706),
  [#723](https://github.com/ktwu01/benchmark-radar/pull/723),
  [#773](https://github.com/ktwu01/benchmark-radar/pull/773),
  [#774](https://github.com/ktwu01/benchmark-radar/pull/774),
  [#815](https://github.com/ktwu01/benchmark-radar/pull/815)). The other 53
  PRs and all 11 issues were closed as not planned on 2026-10-07, so the queue
  could be reviewed again.

The lesson is not "never send fixes". It is: **send the few that a real user or
caller would hit, one at a time, and wait for review before sending the next.**
Five merged fixes from 58 PRs means 53 reviews nobody needed.

2026-09-29 至 2026-10-09，一个账号共开了 **58 个 PR 和 11 个 issue**，高峰时 56 个 PR 和 11 个 issue
同时未关闭。2026-09-30 在 37 分钟内开了 15 个 PR；2026-10-06 一天开了 29 个 PR，其中 8 个在 27 秒内提交。
同一天下午先自己开 11 个 issue，几分钟后再开 PR "修复"自己的 issue（例如 issue #788 于 14:01 开、
PR #799 于 14:15 开）——作者为自己的 PR 写的 issue 不能证明有人需要这个改动。大多数复现是没有用户或数据源
产生过的假想输入（`1e400` 变成 Infinity、CSS 单引号 `url()`、HTTP 日期格式的 `Retry-After`、Atom 的
`xml:base`、刻意构造的标题），并附有大段 AI 生成的验证文字。最终合并了 5 个修复语料静默丢失或报告真实缺陷的 PR，
其余 53 个 PR 和全部 11 个 issue 于 2026-10-07 以 not planned 关闭。教训：只提交真实用户或调用方会遇到的修复，
一次一个，等审阅后再提交下一个。

### Open item limit / 未关闭数量上限

One author can have at most **10 open issues and pull requests combined**. A new
one past that is closed automatically with a note, and can be reopened once
earlier ones are merged or closed. Maintainers are exempt. Pick the few changes
that matter most and finish them.

### 中文

- **采用登记表里不放分数。** 不同厂商的提示词、脚手架、工具、推理预算、pass@k 和评测器不同。
- **不把任何排名包装成质量评价。** 采用度衡量的是厂商关注度。
- **不做静默合并记录的模糊匹配。** 实体只按精确标识符（DOI、arXiv、OpenReview、GitHub、Hugging Face）对应。
- **不生成摘要。** 上游没有描述就留空。
- **不抓取需要登录的内容。** 不用 cookie、登录会话、私密帖子，不抓 LinkedIn 和 X。
- **不手改生成文件。** `site/data/models.json`、`logo-registry.json`、`radar.json` 及目录索引和分片由构建生成；
  请修源数据并重新运行生成器。
- **不接受无官方数据的自引来源。** 不要把自己的参赛系统报告、方案仓库或参赛论文登记为某个 benchmark
  的排行榜或证据；请引用主办方的官方排行榜或论文。
- **不接受过期或无关的历史。** 与 `main` 没有共同历史、或带回旧提交、旧快照、旧文件的分支；
  请把自己的提交重放到基于 `main` 的新分支上。
- **论文材料放到论文仓库。** 技术报告的草稿、图和分析文件夹请提交到 `benchmark-radar-paper`。
- **不接受无用的 bug 修复。** 没有可复现、用户会遇到的故障的改动：纯外观改动、防御不可能输入的代码、
  改措辞，或锁定源码文本、当日数据计数而非行为的测试。
- **不接受批量 AI 生成的 PR。** 欢迎 AI 辅助，但需要有人读过并核对，并注明模型（在 PR 评论中写
  `330226 <model-id>`，见 `AGENTS.md`）。大量雷同或未经核对的 agent PR 会不经审阅直接关闭。
- **未关闭数量上限：** 同一位作者同时最多保留 **10 个未关闭的 issue 和 PR（合计）**，超出的会被自动关闭，
  之前的合并或关闭后可重新打开。维护者不受限制。请优先完成最重要的几个。

## 3. How points work / 积分规则

Points, scored issues, collaborator seats and the public ledger are described in
[`docs/contributor-points.md`](docs/contributor-points.md).

积分、计分 issue、协作者席位和公开账本见 [`docs/contributor-points.md`](docs/contributor-points.md)。

## 4. Other problems / 其他常见问题

- **CI has not run on your PR.** Workflows from forks wait for a maintainer to
  approve them. Say in the PR that you ran the six steps from a clean checkout,
  and with what result. "Relying on CI" is not a verification.
- **Your branch conflicts.** Rebase on `main`. When both sides append to a YAML
  file or a test file, keep both blocks. When a generated file conflicts, take
  `main`'s copy and regenerate it.
- **Your local run passes but CI fails.** Gitignored generated files on disk can
  hide failures. Run from a clean worktree with its own venv; see
  [`docs/agent-gotchas.md`](docs/agent-gotchas.md).
- **Review asks go unanswered.** A PR that has had no reply to review comments
  for two weeks may be closed. Reopen it, or open a fresh one, when you return.
- **Who merges.** Only maintainers merge, with a merge commit.
- **A wrong row in the ranking.** That is a real bug, not a nitpick. Open an
  issue with the document URL and what it actually reports, and the benchmark
  id if you know it.

### 中文

- **PR 上没有跑 CI。** 来自 fork 的 workflow 需要维护者批准。请在 PR 中说明你在干净的 checkout
  上跑了六步及结果；"依赖 CI" 不算验证。
- **分支有冲突。** rebase 到 `main`；两边都在 YAML 或测试文件末尾追加时保留双方；生成文件冲突时取
  `main` 的版本再重新生成。
- **本地通过、CI 失败。** 磁盘上被 gitignore 的生成文件会掩盖问题；请在带独立 venv 的干净 worktree
  中运行，见 `docs/agent-gotchas.md`。
- **审阅意见长期无回复。** 两周没有回复审阅意见的 PR 可能被关闭；回来后可重新打开或新开 PR。
- **谁来合并。** 只有维护者合并，并使用 merge commit。
- **排行榜中的错误数据。** 这是真 bug。请开 issue，附上文档 URL、文档实际报告的内容，以及 benchmark id（如知道）。
