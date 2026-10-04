# Agent gotchas

Known traps in this repo. Each entry states the trap and what to do.

## Local verification

- **Stale artifacts lie both ways.** Gitignored files such as `site/data/radar.json`
  can make a working copy pass a test that CI fails. Stale files can also invent
  failures. Trust only the clean-worktree run that `AGENTS.md` describes.
- **The clean worktree needs its own venv.** Run `python3 -m venv .venv`, then
  `.venv/bin/pip install -e ".[dev]"`, and put `.venv/bin` on `PATH`. The bare
  install omits pytest and Pillow. A global `pipx` install of `benchmark-radar`
  lags the repo and produces false generator failures. Confirm that
  `which benchmark-radar` points into the worktree.
- **A shared venv can import the wrong source.** `pyproject.toml` sets
  `pythonpath = ["src"]`, so run pytest from the worktree root. If the test
  count matches `main` after you added tests, you tested the wrong tree.
- **Tracked generated files need a rebuild.** A score for a new model identity
  changes `site/data/models.json` and `site/data/logo-registry.json`. Rebuild with
  `python scripts/build_logo_registry.py` and commit both files.
- **Local pipeline runs need a token.** Export `GITHUB_TOKEN="$(gh auth token)"`.
  Without it, GitHub search returns HTTP 429 and the run aborts before the
  boilerplate guard executes.
- **Worktree removal fails because of the submodule.** Confirm
  `git status --short` is empty, then run `trash <path>` and `git worktree prune`.

## GitHub and hosting

- **`main` uses a ruleset, not branch protection.** The `main-protect` ruleset
  requires one approval, which the sole maintainer cannot give. A merge shows
  `BLOCKED` with green CI and needs `gh pr merge --admin`. Merge only when the
  user asks.
- **Pages has a 100 GB/month bandwidth cap.** `data/radar.json` is about 9 MB
  gzipped. A default visit loads `radar-bootstrap.json` (about 420 KB) instead.
  Keep that lazy-load split in `app.js`. Put bulk artifacts on GitHub Releases.
- **Do not run `npx skills add` inside this repo.** It replaces the tracked
  `skills/benchmark-radar/` with a symlink. Test the consumer install from a
  scratch directory.

## Data and literature

- **The CLI cannot find older arXiv papers.** arXiv ingest reads the RSS feed of
  new submissions. An empty CLI result is no evidence that no prior work exists.
  Search arXiv directly for related work. Example: the benchmark plateau paper,
  [arXiv:2602.16763](https://arxiv.org/abs/2602.16763), is absent from the CLI.
- **The KW-Bench L0-L5 classifier is dormant.** Regex rules cannot do the
  semantic judgment the levels need. Issue #153 was closed as not planned.
  `docs/kw-bench-rubric.md` is the rubric source of truth. Do not propose the
  L0-L5 chart again unless a semantic extractor replaces `NullExtractor`.
- **A rate limit must not select content.** A token cap in `briefing.py` once
  dropped 296 of 306 evidence records without a report. If a budget trims
  content, count and publish the trim.

## arXiv submission

- **arXiv deletes `X.pdf` when `X.tex` exists.** Do not ship the figure `.tex`
  wrappers. Before an upload, extract the tarball, delete each `X.pdf` that has
  an `X.tex`, and compile. Exit 0 means arXiv will accept it.
