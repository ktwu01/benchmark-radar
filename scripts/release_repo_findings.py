"""Reproduce the release-repository findings from committed data only.

Reads data/snapshots/, data/release_repos.yml and data/release_institutions.yml
(no network) and prints the numbers behind the insights issues: how stars
concentrate, how many new repositories never get one, how a linked paper and
the institutions behind it relate to stars, how many repositories go quiet or
disappear, and how far the two attention signals agree.

Every figure is a description of the Latest releases cohort on the date the
repository facts were retrieved, not a quality judgement of any benchmark.
Counts are of distinct repositories unless a line says otherwise.

    python scripts/release_repo_findings.py [--window 90d]
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

from benchmark_radar.affiliation_rank import institution_counts, paper_institutions
from benchmark_radar.release_leaderboard import build_latest_releases_leaderboard
from benchmark_radar.release_signals import github_repo, load_release_signals
from benchmark_radar.snapshots import load_snapshots

TOP_INSTITUTIONS = 25


def _summary(stars: list[int]) -> str:
    if not stars:
        return "n=0"
    zero = sum(s == 0 for s in stars) / len(stars)
    return (
        f"n={len(stars)}, median {statistics.median(stars):g}★, "
        f"{zero:.0%} with zero stars, {sum(s >= 100 for s in stars)} with 100★ or more"
    )


def _pearson_log(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs = [math.log1p(a) for a, _ in pairs]
    ys = [math.log1p(b) for _, b in pairs]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    var = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return cov / var if var else None


def findings(window: str, snapshot_dir: Path) -> list[str]:
    signals = load_release_signals()
    counts = institution_counts(paper_institutions(signals))
    top = {name for name, _ in counts.most_common(TOP_INSTITUTIONS)}
    board = build_latest_releases_leaderboard(
        load_snapshots(snapshot_dir), top_limit=None, signals=signals, institution_counts=counts
    )
    entries = board["windows"][window]["entries"]

    repos: dict[str, dict] = {}
    for entry in entries:
        repo = github_repo((entry["components"].get("github_stars") or {}).get("source_url"))
        if repo and repo not in repos:
            repos[repo] = entry
    rows = {repo: signals.repos.get(repo) or {} for repo in repos}
    checked = {r: row for r, row in rows.items() if row.get("stars_at_check") is not None}
    # unavailable is True only after the repository endpoint, which follows renames,
    # returned 404; None means the daily check has not reached that repo yet.
    gone = [r for r, row in rows.items() if row.get("unavailable") is True]
    unchecked = [r for r, row in rows.items() if row.get("unavailable") is None]
    retrieved = sorted({row.get("retrieved_at") for row in rows.values() if row})

    stars = sorted((row["stars_at_check"] for row in checked.values()), reverse=True)
    total = sum(stars) or 1

    def share(fraction: float) -> float:
        return sum(stars[: max(1, round(len(stars) * fraction))]) / total

    paper, no_paper, top_inst, other_inst, pairs = [], [], [], [], []
    for repo, row in checked.items():
        entry, value = repos[repo], row["stars_at_check"]
        has_paper = bool(entry.get("institutions")) or "arxiv" in entry["canonical_artifact_id"]
        (paper if has_paper else no_paper).append(value)
        if entry.get("institutions"):
            in_top = any(name in top for name in entry["institutions"])
            (top_inst if in_top else other_inst).append(value)
        upvotes = (entry["components"].get("hf_paper_upvotes") or {}).get("value")
        if upvotes is not None:
            pairs.append((upvotes, value))

    sizes = sorted(row["size_kb"] for row in checked.values())
    one_day = sum(row.get("pushed_at") == row.get("created_at") for row in checked.values())
    r = _pearson_log(pairs)
    hundred = sum(s >= 100 for s in stars)
    return [
        f"Window {window}: {len(entries)} releases, {len(repos)} distinct GitHub repositories, "
        f"facts retrieved {', '.join(str(d) for d in retrieved if d)}.",
        f"Repositories with facts: {len(checked)}; gone (404 on the repository endpoint, "
        f"deleted or made private): {len(gone)} ({len(gone) / len(repos):.1%}); "
        f"not yet checked: {len(unchecked)}.",
        f"Stars: {_summary(stars)}; top 1% hold {share(0.01):.0%} of all stars, "
        f"top 10% hold {share(0.10):.0%}.",
        f"Repository size: median {statistics.median(sizes):g} KB, "
        f"quartiles {sizes[len(sizes) // 4]} / {sizes[3 * len(sizes) // 4]} KB.",
        f"Never pushed after the day they were created: {one_day} ({one_day / len(checked):.0%}).",
        f"Linked to an arXiv paper: {_summary(paper)}.",
        f"No paper: {_summary(no_paper)}.",
        f"Paper repositories hold {sum(s >= 100 for s in paper)} of the {hundred} "
        f"repositories with 100★ or more, while being {len(paper) / len(checked):.0%} "
        "of the cohort.",
        f"Paper with a top-{TOP_INSTITUTIONS} institution: {_summary(top_inst)}.",
        f"Paper with other institutions: {_summary(other_inst)}.",
        "Hugging Face paper upvotes vs GitHub stars, log-log Pearson r: "
        + (f"{r:.2f} (n={len(pairs)})." if r is not None else "not enough pairs."),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default="90d", choices=["7d", "30d", "90d"])
    parser.add_argument("--snapshots", type=Path, default=Path("data/snapshots"))
    args = parser.parse_args(argv)
    for line in findings(args.window, args.snapshots):
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
