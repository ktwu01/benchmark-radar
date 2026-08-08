"""Who builds the popular benchmarks, and which of them work on data.

Issue #156 asks which authors behind popular benchmarks are doing data work.
This answers it from public professional signals only: the GitHub repositories
the radar already tracks, their contributor lists, and the profile fields those
contributors chose to publish (name, company, bio, blog, location).

Two deliberate limits.

**Popularity is derived, not asserted.** The issue leaves "popular" to us, so it
is defined here as a repository the radar's own corpus ranks: stars, how many
days the radar has tracked it, and how many connectors reported it. That keeps
the seed list reproducible and auditable rather than a hand-picked list of
famous names.

**Commit emails are collected but never committed.** `git log` publishes an
author email, and most contributors do not realise it. A committed file of
harvested addresses is a spam and doxxing vector whatever the intent, so emails
go to a separate gitignored artifact and the shareable profile records carry
professional signals only. `noreply` addresses are dropped entirely; they
identify nobody and are pure noise.

No email is ever sent. This reads public APIs and stops there.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .corpus import build_corpus
from .http import RequestError, get_json

AUTHORS_SCHEMA_VERSION = 1
GITHUB_API = "https://api.github.com"
DEFAULT_REPO_LIMIT = 40
DEFAULT_CONTRIBUTORS_PER_REPO = 20

# Substrings that mark a profile as data-adjacent work. Matched against the
# self-written bio and company fields, never inferred from a repository name:
# an author is credited with data work because they said so.
DATA_SIGNALS = (
    "data quality",
    "data-centric",
    "data curation",
    "dataset",
    "data engineering",
    "annotation",
    "labeling",
    "labelling",
    "evaluation",
    "eval",
    "benchmark",
    "rlhf",
    "human feedback",
    "data pipeline",
    "etl",
    "data infrastructure",
)

_GITHUB_REPO = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)", re.IGNORECASE)


class AuthorLookupError(RuntimeError):
    """A required GitHub call failed and the result would be misleading."""


def _headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def popular_repositories(
    snapshots: list[dict[str, Any]],
    *,
    limit: int = DEFAULT_REPO_LIMIT,
) -> list[dict[str, Any]]:
    """Rank the GitHub benchmark repositories the radar has actually seen.

    "Popular" is defined from the corpus rather than asserted: stars first, then
    how many days the radar tracked the artifact, then how many connectors
    reported it. A repository nobody starred that three connectors reported for
    a week is a real signal; so is a highly starred one seen once.
    """
    corpus = build_corpus(snapshots)
    ranked = []
    for entity in corpus["entities"]:
        if entity["type"] != "artifact":
            continue
        match = _GITHUB_REPO.match(str(entity.get("url") or ""))
        if not match:
            continue
        owner, name = match.group(1), match.group(2).removesuffix(".git")
        if owner.lower() in {"apps", "marketplace", "sponsors", "topics"}:
            continue
        categories = set(entity.get("categories") or [])
        # A lone `evaluation` tag is the repo-side version of the keyword false
        # positive `_evidence_records` already guards against: it admitted a
        # 63k-star careers repository as a benchmark. Require either an explicit
        # benchmark/dataset category or a second corroborating tag.
        if not (categories & {"benchmark", "dataset"}) and len(categories) < 2:
            continue
        metrics = entity.get("metrics") or {}
        ranked.append(
            {
                "full_name": f"{owner}/{name}",
                "owner": owner,
                "name": name,
                "url": entity.get("url"),
                "title": entity.get("label"),
                "stars": float(metrics.get("stars") or 0),
                "seen_days": len(entity.get("seen_days") or []),
                "sources": list(entity.get("sources") or []),
                "categories": list(entity.get("categories") or []),
            }
        )
    ranked.sort(
        key=lambda repo: (repo["stars"], repo["seen_days"], len(repo["sources"])),
        reverse=True,
    )
    # One owner should not consume the whole seed list: a single org publishing
    # thirty datasets would otherwise crowd out every other team.
    selected: list[dict[str, Any]] = []
    per_owner: dict[str, int] = {}
    for repo in ranked:
        owner = repo["owner"].casefold()
        if per_owner.get(owner, 0) >= 3:
            continue
        selected.append(repo)
        per_owner[owner] = per_owner.get(owner, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def repository_contributors(
    full_name: str,
    *,
    per_repo: int = DEFAULT_CONTRIBUTORS_PER_REPO,
) -> list[dict[str, Any]]:
    """Public contributor logins and commit counts for one repository."""
    try:
        payload = get_json(
            f"{GITHUB_API}/repos/{full_name}/contributors",
            params={"per_page": min(per_repo, 100)},
            headers=_headers(),
        )
    except RequestError as error:
        raise AuthorLookupError(f"contributors for {full_name}: {error}") from error
    if not isinstance(payload, list):
        return []
    return [
        {
            "login": str(entry.get("login") or ""),
            "contributions": int(entry.get("contributions") or 0),
            "type": str(entry.get("type") or "User"),
        }
        for entry in payload
        if isinstance(entry, dict) and entry.get("login") and entry.get("type") == "User"
    ][:per_repo]


def data_signals(profile: dict[str, Any]) -> list[str]:
    """Which data-work signals a profile's own words contain."""
    text = " ".join(
        str(profile.get(field) or "") for field in ("bio", "company", "blog")
    ).casefold()
    return sorted({signal for signal in DATA_SIGNALS if signal in text})


def public_profile(login: str) -> dict[str, Any]:
    """Fetch the professional fields a GitHub user chose to publish."""
    try:
        payload = get_json(f"{GITHUB_API}/users/{login}", headers=_headers())
    except RequestError as error:
        raise AuthorLookupError(f"profile for {login}: {error}") from error
    profile = {
        "login": str(payload.get("login") or login),
        "name": payload.get("name"),
        "company": payload.get("company"),
        "blog": payload.get("blog"),
        "bio": payload.get("bio"),
        "location": payload.get("location"),
        "public_repos": int(payload.get("public_repos") or 0),
        "followers": int(payload.get("followers") or 0),
        "profile_url": f"https://github.com/{payload.get('login') or login}",
    }
    profile["data_signals"] = data_signals(profile)
    profile["works_on_data"] = bool(profile["data_signals"])
    # Self-published on the profile, which is a different act from a commit
    # email the author may not know is public. Kept separate for that reason.
    profile["public_profile_email"] = payload.get("email")
    return profile


def commit_emails(full_name: str, *, per_page: int = 100) -> dict[str, str]:
    """Map contributor login to the commit email visible in that repository.

    Collected because the issue asks for it, and written only to the untracked
    contact artifact. `noreply` addresses are dropped: they identify nobody.
    """
    try:
        payload = get_json(
            f"{GITHUB_API}/repos/{full_name}/commits",
            params={"per_page": min(per_page, 100)},
            headers=_headers(),
        )
    except RequestError as error:
        raise AuthorLookupError(f"commits for {full_name}: {error}") from error
    if not isinstance(payload, list):
        return {}
    emails: dict[str, str] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        author = entry.get("author") or {}
        login = str(author.get("login") or "").strip()
        email = str(((entry.get("commit") or {}).get("author") or {}).get("email") or "").strip()
        if not login or not email or "noreply" in email.casefold():
            continue
        emails.setdefault(login, email)
    return emails


def survey(
    snapshots: list[dict[str, Any]],
    *,
    repo_limit: int = DEFAULT_REPO_LIMIT,
    per_repo: int = DEFAULT_CONTRIBUTORS_PER_REPO,
    include_emails: bool = False,
) -> dict[str, Any]:
    """Build the author survey issue #156 asks for.

    Returns the shareable report plus, when `include_emails` is set, a separate
    `contacts` block the caller must write to the untracked artifact. Keeping
    them apart is the point: the report is safe to commit, the contacts are not.
    """
    repos = popular_repositories(snapshots, limit=repo_limit)
    profiles: dict[str, dict[str, Any]] = {}
    contacts: dict[str, dict[str, str]] = {}
    failures: list[str] = []

    for repo in repos:
        try:
            contributors = repository_contributors(repo["full_name"], per_repo=per_repo)
        except AuthorLookupError as error:
            failures.append(str(error))
            continue
        repo["contributor_count"] = len(contributors)
        emails = {}
        if include_emails:
            try:
                emails = commit_emails(repo["full_name"])
            except AuthorLookupError as error:
                failures.append(str(error))
        for contributor in contributors:
            login = contributor["login"]
            profile = profiles.get(login)
            if profile is None:
                try:
                    profile = public_profile(login)
                except AuthorLookupError as error:
                    failures.append(str(error))
                    continue
                profile["repositories"] = []
                profiles[login] = profile
            profile["repositories"].append(
                {
                    "full_name": repo["full_name"],
                    "url": repo["url"],
                    "contributions": contributor["contributions"],
                }
            )
            if login in emails:
                contacts[login] = {
                    "login": login,
                    "commit_email": emails[login],
                    "found_in": repo["full_name"],
                }

    people = sorted(
        profiles.values(),
        key=lambda profile: (
            profile["works_on_data"],
            len(profile["repositories"]),
            profile["followers"],
        ),
        reverse=True,
    )
    data_people = [profile for profile in people if profile["works_on_data"]]
    report = {
        "schema_version": AUTHORS_SCHEMA_VERSION,
        "popularity_definition": (
            "GitHub repositories in the radar corpus ranked by stars, then days "
            "tracked, then connector breadth, capped at three per owner."
        ),
        "method": (
            "Public GitHub APIs only: contributor lists and the profile fields each "
            "author chose to publish. Data-work classification reads the author's own "
            "bio and company text and is never inferred from a repository name. No "
            "email is ever sent."
        ),
        "repository_count": len(repos),
        "author_count": len(people),
        "data_author_count": len(data_people),
        "repositories": repos,
        "authors": people,
        "failures": failures,
    }
    if include_emails:
        # Never merged into `report`: the caller writes this to the untracked
        # contact artifact so a harvested address cannot reach a public commit.
        report_contacts = sorted(contacts.values(), key=lambda entry: entry["login"])
        return {"report": report, "contacts": report_contacts}
    return {"report": report, "contacts": []}
