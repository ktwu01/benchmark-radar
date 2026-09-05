"""Daily social post material for each day's radar run (issue #88 follow-up).

Every day the radar workflow opens one GitHub Issue whose body is this short
"Daily social post" section (issue #88): a benchmark insight read off the day's
evidence, a repo-change summary read off the day's git history, a ready-to-copy
发布文案 sample from config/social.yml, plus a per-channel posting checklist.
The dashboard and site/feed.xml remain the reading surface (issue #37), so the
Issue carries only this section, not the full report. When a previous render is
supplied with ``--existing-body``, ticks already made are re-applied so a re-run
never resets posting progress.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

SECTION_HEADING = "## 🗣 Daily social post"

# Issue #206: the record-count badge (same Shields endpoint the README embeds)
# sits at the top of every day's checklist so the corpus size is visible at a
# glance on the posting issue. It is data-driven (snapshots.records_badge), so
# it can only state what the corpus actually holds.
_RECORDS_BADGE = (
    "[![benchmark records collected]"
    "(https://img.shields.io/endpoint?url=https%3A%2F%2Fbenchmark-radar.org"
    "%2Fdata%2Frecords-badge.json)]"
    "(https://benchmark-radar.org/)"
)

_CHECKBOX_RE = re.compile(r"^-\s+\[([ xX])\]\s+(.+)$")

# Path prefixes that would otherwise read as "src", "data" etc. in a social
# post. The sentence is for humans who do not know the repository layout.
_AREA_ALIASES = {
    ".github": "workflows",
    "src": "radar code",
    "scripts": "scripts",
    "data": "registry data",
    "site": "dashboard",
    "docs": "docs",
    "tests": "tests",
    "config.yml": "config",
}

# Automated and integration commits add no information to a social post; the
# count still includes them, but the highlighted commit subjects do not.
_NOISE_SUBJECT_PREFIXES = (
    "Record daily radar snapshot",
    "Merge ",
)


@dataclass(frozen=True)
class GitChange:
    subject: str
    files: tuple[str, ...]


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def load_post_sample(path: Path) -> str | None:
    """Read the ready-to-copy 发布文案 from config/social.yml, if any."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sample = (data.get("social") or {}).get("post_sample")
    return str(sample).strip() if sample else None


def load_channels(path: Path, *, daily_only: bool = False) -> list[dict]:
    """Read the channel checklist from config/social.yml.

    With daily_only, only channels marked ``daily: true`` are returned. The
    launch-only channels (Discord communities, DEV/Hashnode articles, and the
    like) are single-shot: listing them on every day's checklist would read as
    an instruction to post there daily. When the config marks no channel at
    all, every channel is treated as daily rather than silently dropping the
    whole checklist.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    channels = (data.get("social") or {}).get("channels") or []
    if daily_only and any(channel.get("daily") is not None for channel in channels):
        channels = [
            channel
            for channel in channels
            if channel.get("daily") and channel.get("monthly") is not True
        ]
    return [channel for channel in channels if str(channel.get("name") or "").strip()]


def build_insight_sentence(items: list[dict]) -> str:
    """One factual sentence describing today's captured evidence.

    Deterministic by design: the sentence is computed from the day's ranked
    evidence, never drafted by a model, so it always exists even when a GPT
    briefing fails.
    """
    if not items:
        return "The radar captured no new benchmark items today."
    source_counts = Counter(str(item.get("source") or "unknown") for item in items)
    sources = ", ".join(source for source, _ in source_counts.most_common())
    top = max(items, key=lambda item: float(item.get("total_score") or 0.0))
    title = str(top.get("title") or "untitled").strip()
    source = str(top.get("source") or "unknown")
    score = float(top.get("total_score") or 0.0)
    score_max = float(top.get("score_max") or 100.0)
    noun = "item" if len(items) == 1 else "items"
    return (
        f"Today's radar surfaced {len(items)} {noun} across {sources}; "
        f"top signal: {title} ({source}, {score:.0f}/{score_max:.0f})."
    )


def _area_for(path: str) -> str:
    if path in _AREA_ALIASES:
        return _AREA_ALIASES[path]
    if "/" in path:
        return _AREA_ALIASES.get(path.split("/", 1)[0], path.split("/", 1)[0])
    return path


def summarize_repo_changes(changes: list[GitChange]) -> tuple[str, list[str]]:
    """Reduce a day of commits to one sentence plus a few subject highlights."""
    if not changes:
        return "No code changes in the last 24 hours.", []
    area_counts: Counter[str] = Counter()
    for change in changes:
        for area in {_area_for(path) for path in change.files}:
            area_counts[area] += 1
    areas = ", ".join(area for area, _ in area_counts.most_common())
    noun = "commit" if len(changes) == 1 else "commits"
    sentence = f"{len(changes)} {noun} in the last 24 hours"
    if areas:
        sentence += f" across {areas}"
    sentence += "."
    highlights = [
        change.subject
        for change in changes
        if not change.subject.startswith(_NOISE_SUBJECT_PREFIXES)
    ][:3]
    return sentence, highlights


def parse_git_log(text: str) -> list[GitChange]:
    """Parse `git log --format=%H%x00%s --name-only` output.

    Blank lines are separators and carry no meaning, so a commit ends only at
    the next header line. This stays correct whether git places the blank
    before or after the file list, and whether a merge commit lists no files.
    """
    changes: list[GitChange] = []
    subject: str | None = None
    files: list[str] = []
    for line in text.splitlines():
        if "\0" in line:
            if subject is not None:
                changes.append(GitChange(subject, tuple(files)))
            _, subject = line.split("\0", 1)
            files = []
        elif line.strip():
            files.append(line.strip())
    if subject is not None:
        changes.append(GitChange(subject, tuple(files)))
    return changes


def collect_git_changes(repo: Path, since: str, until: str) -> list[GitChange]:
    """Run git log over the repository for the given ISO window."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            f"--since={since}",
            f"--until={until}",
            "--format=%H%x00%s",
            "--name-only",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return parse_git_log(result.stdout)


def _canonical_name(raw: str) -> str:
    """Undo the rendering-time escaping so ticks match configured names."""
    return raw.strip().replace("\\|", "|")


def extract_checked(body: str) -> set[str]:
    """Channel names already ticked in an existing issue body."""
    checked: set[str] = set()
    in_section = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_section = line.rstrip() == SECTION_HEADING
            continue
        if not in_section:
            continue
        match = _CHECKBOX_RE.match(line)
        if match and match.group(1).strip().lower() == "x":
            checked.add(_canonical_name(match.group(2)))
    return checked


def merge_checked(section: str, existing_body: str) -> str:
    """Re-apply ticks from a previous render of the same day's section.

    The checklist is the only state a re-run must not destroy: insight and
    repo-change lines may legitimately change, but a channel the user already
    marked as posted must stay marked.
    """
    checked = extract_checked(existing_body)
    if not checked:
        return section
    lines = []
    for line in section.splitlines():
        match = _CHECKBOX_RE.match(line)
        if match and _canonical_name(match.group(2)) in checked:
            lines.append(f"- [x] {match.group(2).strip()}")
        else:
            lines.append(line)
    return "\n".join(lines)


def render_social_section(
    insight: str,
    repo_sentence: str,
    commit_subjects: list[str],
    channels: list[dict],
    post_sample: str | None = None,
    today: date | None = None,
) -> str:
    """Render the "Daily social post" section for today's radar run."""
    lines = [
        SECTION_HEADING,
        "",
        _RECORDS_BADGE,
        "",
        "Ready-to-post material for today. Rephrase per platform; the two "
        "sentences below are the factual core.",
        "",
        f"**Benchmark update:** {_escape(insight)}",
        "",
        f"**Repo change:** {_escape(repo_sentence)}",
        "",
    ]
    if commit_subjects:
        lines.extend(["_Latest commits:_", ""])
        lines.extend(f"- {_escape(subject)}" for subject in commit_subjects)
        lines.append("")
    if post_sample:
        lines.extend(
            [
                "**发布文案示例** (copy-paste for today's post):",
                "",
                post_sample,
                "",
            ]
        )
    lines.extend(
        [
            "**Posting checklist** - tick a channel after today's post is sent there:",
            "",
        ]
    )
    # Every cadence remains visible in every issue so the issue is a complete
    # checklist. The headings tell the maintainer how often to use a destination;
    # they no longer hide options on dates that do not match the cadence.
    monthly_channels = [channel for channel in channels if channel.get("monthly") is True]
    weekly_channels = [
        channel
        for channel in channels
        if channel.get("monthly") is not True and channel.get("daily") is False
    ]
    daily_channels = [
        channel
        for channel in channels
        if channel.get("monthly") is not True
        and channel.get("daily") is not False
        and str(channel.get("name") or "").strip()
    ]
    has_daily_flag = any(channel.get("daily") is True for channel in channels)
    if daily_channels:
        if weekly_channels or monthly_channels or has_daily_flag:
            lines.append("**Daily targets:**")
            lines.append("")
        for channel in daily_channels:
            lines.append(f"- [ ] {_escape(str(channel.get('name')).strip())}")
        lines.append("")
    if weekly_channels:
        lines.append("**Weekly (every 7 days):**")
        lines.append("")
        for channel in weekly_channels:
            name = str(channel.get("name") or "").strip()
            if name:
                lines.append(f"- [ ] {_escape(name)}")
        lines.append("")
    if monthly_channels:
        lines.append("**Monthly:**")
        lines.append("")
        for channel in monthly_channels:
            name = str(channel.get("name") or "").strip()
            if name:
                lines.append(f"- [ ] {_escape(name)}")
    lines.append("")
    return "\n".join(lines)
