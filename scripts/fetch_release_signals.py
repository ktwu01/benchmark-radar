"""Refresh data/release_institutions.yml and data/release_repos.yml (#1120).

Reads the committed snapshots, takes the widest Latest releases window, and for
each release looks up:

* the institutions behind its arXiv paper: OpenAlex first, else the paper's
  own arXiv HTML (``benchmark_radar.paper_institutions.lookup``). A paper is
  retried every few days until OpenAlex has it, because OpenAlex lags new
  papers;
* the root listing of the GitHub repository its stars come from, to mark
  README-only placeholders. Set GITHUB_TOKEN for the 5,000-request hourly
  budget.

Entries for releases that left the window are dropped. Each run is bounded by
--max-papers and --max-repos; what is left is picked up by the next run.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from benchmark_radar.http import RequestError, get_json, get_text
from benchmark_radar.paper_institutions import lookup
from benchmark_radar.release_leaderboard import release_signal_targets
from benchmark_radar.release_signals import (
    DEFAULT_RELEASE_INSTITUTIONS_PATH,
    DEFAULT_RELEASE_REPOS_PATH,
    github_repo,
    is_placeholder_root,
    load_release_signals,
    needs_institution_refresh,
    needs_repo_refresh,
    write_release_institutions,
    write_release_repos,
)
from benchmark_radar.snapshots import load_snapshots

USER_AGENT = "benchmark-radar/release-signals (+https://github.com/ktwu01/benchmark-radar)"


def _headers(github: bool = False) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github and token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def refresh_institutions(papers, rows, *, today, limit, delay):
    pending = sorted(p for p in papers if needs_institution_refresh(rows.get(p), today))
    looked_up = 0
    for paper in pending[:limit]:
        try:
            found = lookup(
                paper,
                fetch_json=lambda url: get_json(url, headers=_headers(), attempts=2),
                fetch_text=lambda url: get_text(url, headers=_headers(), attempts=2),
            )
        except (RequestError, OSError) as error:
            print(f"warning: {paper}: {error}", file=sys.stderr)
            continue
        rows[paper] = {
            "basis": (found or {}).get("basis"),
            "source_url": (found or {}).get("source_url"),
            "retrieved_at": today.isoformat(),
            "institutions": (found or {}).get("institutions") or [],
        }
        looked_up += 1
        time.sleep(delay)
    return looked_up, len(pending)


def refresh_repos(urls, rows, *, today, limit):
    repos = sorted({repo for repo in map(github_repo, urls) if repo})
    pending = [repo for repo in repos if needs_repo_refresh(rows.get(repo), today)]
    looked_up = 0
    for repo in pending[:limit]:
        try:
            listing = get_json(
                f"https://api.github.com/repos/{repo}/contents/",
                headers=_headers(github=True),
                attempts=2,
            )
        except RequestError as error:
            # A deleted, private or empty repository says nothing either way.
            print(f"warning: {repo}: {error}", file=sys.stderr)
            continue
        names = sorted(str(entry.get("name") or "") for entry in listing or [])
        rows[repo] = {
            "placeholder": is_placeholder_root(names),
            "root": names[:20],
            "retrieved_at": today.isoformat(),
        }
        looked_up += 1
    return looked_up, len(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--institutions", type=Path, default=DEFAULT_RELEASE_INSTITUTIONS_PATH)
    parser.add_argument("--repos", type=Path, default=DEFAULT_RELEASE_REPOS_PATH)
    parser.add_argument("--max-papers", type=int, default=400)
    parser.add_argument("--max-repos", type=int, default=1500)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args(argv)

    today = datetime.now(UTC).date()
    papers, star_urls = release_signal_targets(load_snapshots(args.snapshots))
    current = load_release_signals(args.institutions, args.repos)
    institutions = {p: r for p, r in current.institutions.items() if p in papers}
    live_repos = {repo for repo in map(github_repo, star_urls) if repo}
    repos = {r: row for r, row in current.repos.items() if r in live_repos}

    done, pending = refresh_institutions(
        papers, institutions, today=today, limit=args.max_papers, delay=args.delay
    )
    write_release_institutions(args.institutions, institutions)
    print(f"papers: {len(papers)} in window, {done} of {pending} pending looked up")
    done, pending = refresh_repos(star_urls, repos, today=today, limit=args.max_repos)
    write_release_repos(args.repos, repos)
    placeholders = sum(1 for row in repos.values() if row.get("placeholder"))
    print(f"repos: {len(live_repos)} in window, {done} of {pending} pending looked up")
    print(f"placeholder repositories: {placeholders}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
