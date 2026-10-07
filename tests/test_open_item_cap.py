"""The open-item cap closes only authors who are over it and not exempt."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(".github/scripts/enforce-open-item-cap.sh").resolve()


def run_cap(tmp_path, *, author, issues, prs, kind="pr", exempt="ktwu01 junjiezhou1122"):
    # A fake `gh` answers the two GraphQL counts and records any close command.
    log = tmp_path / "calls.log"
    fake = tmp_path / "gh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "$CALLS"\n'
        'if [[ "$1" == api ]]; then\n'
        '  case "$*" in *pullRequests*) echo "$PRS";; *) echo "$ISSUES";; esac\n'
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CALLS": str(log),
        "ISSUES": str(issues),
        "PRS": str(prs),
        "REPO": "ktwu01/benchmark-radar",
        "AUTHOR": author,
        "NUMBER": "900",
        "KIND": kind,
        "CAP": "10",
        "EXEMPT": exempt,
    }
    result = subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, [line for line in calls if " close " in f" {line} "]


def test_an_author_at_the_cap_is_left_alone(tmp_path):
    # 4 issues + 6 PRs is exactly 10: the cap is "at most 10", not "fewer than 10".
    result, closes = run_cap(tmp_path, author="someone", issues=4, prs=6)
    assert result.returncode == 0
    assert closes == []


@pytest.mark.parametrize("kind,verb", [("pr", "pr close"), ("issue", "issue close")])
def test_the_eleventh_open_item_is_closed(tmp_path, kind, verb):
    # Issues and PRs count together, so 5 + 6 trips the cap even though neither does alone.
    result, closes = run_cap(tmp_path, author="someone", issues=5, prs=6, kind=kind)
    assert result.returncode == 0
    assert len(closes) == 1 and closes[0].startswith(verb)
    assert ("--reason not planned" in closes[0]) == (kind == "issue")


@pytest.mark.parametrize("author", ["ktwu01", "KTWU01", "junjiezhou1122"])
def test_exempt_authors_are_never_closed(tmp_path, author):
    # GitHub logins are case-insensitive, so the allowlist must be too.
    result, closes = run_cap(tmp_path, author=author, issues=40, prs=40)
    assert result.returncode == 0
    assert closes == []


def test_a_login_with_shell_or_jq_syntax_is_refused(tmp_path):
    result, closes = run_cap(tmp_path, author='x") | halt_error', issues=99, prs=99)
    assert result.returncode != 0
    assert closes == []
