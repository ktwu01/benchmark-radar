import json
from pathlib import Path

from benchmark_radar import cli
from benchmark_radar.social import (
    SECTION_HEADING,
    GitChange,
    build_insight_sentence,
    extract_checked,
    load_channels,
    load_post_sample,
    merge_checked,
    parse_git_log,
    render_social_section,
    summarize_repo_changes,
)


def test_insight_sentence_names_the_top_signal():
    items = [
        {
            "title": "A/Bench",
            "source": "GitHub",
            "total_score": 40.0,
            "score_max": 100.0,
        },
        {
            "title": "Top | Signal",
            "source": "Hugging Face",
            "total_score": 72.4,
            "score_max": 100.0,
        },
    ]
    sentence = build_insight_sentence(items)
    assert "2 items across GitHub, Hugging Face" in sentence
    assert "Top | Signal" in sentence
    assert "Hugging Face, 72/100" in sentence


def test_insight_sentence_empty():
    assert "no new" in build_insight_sentence([])


def test_repo_sentence_empty():
    sentence, highlights = summarize_repo_changes([])
    assert sentence == "No code changes in the last 24 hours."
    assert highlights == []


def test_repo_sentence_names_areas_by_human_labels():
    changes = [
        GitChange("Fix classifier", ("src/benchmark_radar/cli.py", "tests/test_cli.py")),
        GitChange("Add feeds", ("data/model_cards.yml", "site/data/radar.json")),
    ]
    sentence, _ = summarize_repo_changes(changes)
    assert sentence.startswith("2 commits in the last 24 hours")
    assert "radar code" in sentence
    assert "registry data" in sentence
    assert "tests" in sentence


def test_repo_sentence_hides_automated_and_merge_subjects_from_highlights():
    changes = [
        GitChange("Record daily radar snapshot", ("data/snapshots/2026-08-10.json",)),
        GitChange("Merge pull request #177", ()),
        GitChange("Fix source labeling", ("src/benchmark_radar/sources.py",)),
    ]
    sentence, highlights = summarize_repo_changes(changes)
    assert sentence.startswith("3 commits")
    assert highlights == ["Fix source labeling"]


def test_parse_git_log_handles_commit_blocks():
    text = (
        "abc123\0Record daily radar snapshot\n"
        "data/snapshots/2026-08-10.json\n"
        "\n"
        "def456\0Fix the classifier\n"
        "src/benchmark_radar/cli.py\n"
        "tests/test_cli.py\n"
        "\n"
    )
    changes = parse_git_log(text)
    assert changes == [
        GitChange("Record daily radar snapshot", ("data/snapshots/2026-08-10.json",)),
        GitChange("Fix the classifier", ("src/benchmark_radar/cli.py", "tests/test_cli.py")),
    ]


def test_parse_git_log_ties_files_to_the_right_commit_when_blank_precedes_files():
    # Real `git log --name-only` output places the blank separator before the
    # file list and emits nothing but the header for a no-diff merge commit.
    # Files must land on the commit whose header they follow, not the previous
    # one, or the repo-change sentence loses every area.
    text = (
        "abc123\0Merge pull request #1\n"
        "def456\0Fix the classifier\n"
        "\n"
        "src/benchmark_radar/cli.py\n"
        "ghi789\0Record daily radar snapshot\n"
        "\n"
        "data/snapshots/2026-08-10.json\n"
    )
    assert parse_git_log(text) == [
        GitChange("Merge pull request #1", ()),
        GitChange("Fix the classifier", ("src/benchmark_radar/cli.py",)),
        GitChange("Record daily radar snapshot", ("data/snapshots/2026-08-10.json",)),
    ]


def test_load_channels_daily_only_filters_launch_channels(tmp_path: Path):
    path = tmp_path / "social.yml"
    path.write_text(
        "social:\n"
        "  channels:\n"
        "    - name: X / Twitter\n"
        "      daily: true\n"
        "    - name: DEV Community\n"
        "      daily: false\n",
        encoding="utf-8",
    )
    assert [c["name"] for c in load_channels(path, daily_only=True)] == ["X / Twitter"]
    assert [c["name"] for c in load_channels(path)] == ["X / Twitter", "DEV Community"]


def test_load_channels_daily_only_keeps_everything_when_no_channel_sets_daily(tmp_path: Path):
    path = tmp_path / "social.yml"
    path.write_text(
        "social:\n  channels:\n    - name: X / Twitter\n    - name: 知乎\n",
        encoding="utf-8",
    )
    assert [c["name"] for c in load_channels(path, daily_only=True)] == [
        "X / Twitter",
        "知乎",
    ]


def test_render_section_leads_with_the_records_badge(tmp_path: Path):
    # Issue #206: the data-driven record-count badge appears at the top of every
    # day's checklist so the corpus size is visible at a glance on the posting
    # issue. It points at the published Shields endpoint, never a hand-typed
    # count, mirroring the README's embedded badge.
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [{"name": "X / Twitter"}],
    )
    lines = section.splitlines()
    assert lines[0] == SECTION_HEADING
    assert lines[1] == ""
    assert "![benchmark records collected]" in lines[2]
    assert "img.shields.io/endpoint" in lines[2]
    assert "records-badge.json" in lines[2]


def test_merge_checked_keeps_the_records_badge(tmp_path: Path):
    # The badge sits above the checklist and carries no checkbox, so re-running
    # with an existing body must never strip it (issue #206).
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [{"name": "X / Twitter"}],
    )
    existing = SECTION_HEADING + "\n\n- [x] X / Twitter\n"
    merged = merge_checked(section, existing)
    assert "![benchmark records collected]" in merged


def test_render_section_lists_every_channel_unchecked(tmp_path: Path):
    channels_path = tmp_path / "social.yml"
    channels_path.write_text(
        "social:\n  channels:\n    - name: X / Twitter\n    - name: 知乎\n",
        encoding="utf-8",
    )
    section = render_social_section(
        "insight",
        "repo change",
        [],
        load_channels(channels_path),
    )
    assert SECTION_HEADING in section
    assert "**Benchmark update:** insight" in section
    assert "**Repo change:** repo change" in section
    assert "- [ ] X / Twitter" in section
    assert "- [ ] 知乎" in section
    assert "- [x]" not in section


def test_render_section_groups_daily_and_weekly_channels():
    # The complete checklist stays visible every day. Cadence headings tell the
    # maintainer how often to use a destination without hiding the checkbox.
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [
            {"name": "X / Twitter", "daily": True},
            {"name": "https://www.reddit.com/r/agi/", "daily": False},
        ],
    )
    assert "**Daily targets:**" in section
    assert "**Weekly (every 7 days):**" in section
    assert "- [ ] X / Twitter" in section
    assert "- [ ] https://www.reddit.com/r/agi/" in section


def test_weekly_channels_remain_visible_between_posting_days():
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [
            {"name": "X / Twitter", "daily": True},
            {"name": "https://www.reddit.com/r/agi/", "daily": False},
        ],
    )
    assert "**Daily targets:**" in section
    assert "- [ ] X / Twitter" in section
    assert "**Weekly (every 7 days):**" in section
    assert "- [ ] https://www.reddit.com/r/agi/" in section


def test_render_section_groups_monthly_channels():
    # Monthly channels remain visible but stay separate from daily and weekly
    # targets, so checking one does not change its intended cadence.
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [
            {"name": "X / Twitter", "daily": True},
            {"name": "Monthly outreach", "monthly": True},
        ],
    )
    assert "**Daily targets:**" in section
    assert "**Monthly:**" in section
    assert "- [ ] X / Twitter" in section
    assert "- [ ] Monthly outreach" in section
    assert "**Weekly" not in section


def test_monthly_channels_remain_visible_between_posting_days():
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [
            {"name": "X / Twitter", "daily": True},
            {"name": "Monthly outreach", "monthly": True},
        ],
    )
    assert "**Daily targets:**" in section
    assert "- [ ] X / Twitter" in section
    assert "**Monthly:**" in section
    assert "- [ ] Monthly outreach" in section


def test_load_channels_daily_only_excludes_monthly_channels(tmp_path: Path):
    path = tmp_path / "social.yml"
    path.write_text(
        "social:\n"
        "  channels:\n"
        "    - name: X / Twitter\n"
        "      daily: true\n"
        "    - name: Monthly outreach\n"
        "      monthly: true\n",
        encoding="utf-8",
    )
    assert [c["name"] for c in load_channels(path, daily_only=True)] == ["X / Twitter"]
    assert [c["name"] for c in load_channels(path)] == [
        "X / Twitter",
        "Monthly outreach",
    ]


def test_render_section_includes_the_copy_paste_post_sample():
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [{"name": "LinkedIn"}],
        post_sample=(
            "一个反常识的发现：样本。\n"
            "源码和分析详见：https://github.com/ktwu01/benchmark-radar/issues/150"
        ),
    )
    assert "**发布文案示例** (copy-paste for today's post):" in section
    assert "一个反常识的发现：样本。" in section
    assert "issues/150" in section


def test_repository_social_config_leads_with_crowdsourcing_then_ranked_channels():
    path = Path("config/social.yml")
    channels = load_channels(path)
    names = [channel["name"] for channel in channels]

    assert names[:7] == [
        "众筹-social：请 benchmark 群友转发到自己的社群",
        "X / Twitter",
        "Benchmark Radar 讨论群",
        "GitHub Blog https://ktwu01.github.io/",
        "WeChat Moment",
        "Science Intelligence 实名讨论群",
        "Hacker News https://news.ycombinator.com/submit",
    ]
    assert {
        "Bilibili / B站",
        "YouTube",
        "Product Hunt",
        "DevHunt",
        "AgentHunter",
        "BetaList",
        "Peerlist",
        "AppSumo",
        "Indie Hackers",
        "GitHub Discussions",
        "Papers with Code discussions",
        "LAION Discord",
        "Cold email：arXiv / OpenReview benchmark 作者",
        "新微信群或 Discord 群",
        "KOL：逛逛 GitHub 等相关账号",
        "WhatsApp Communities",
        "Pinterest",
        "Snapchat",
        "Quora",
    } <= set(names)
    assert {
        "Sichen Tao",
        "Junwei Zhou",
        "Ziyan Chen",
        "Phys Bench",
        "LHTB 造题",
    }.isdisjoint(names)
    by_name = {channel["name"]: channel for channel in channels}
    assert by_name["Cold email：arXiv / OpenReview benchmark 作者"]["daily"] is True

    sample = load_post_sample(path)
    assert sample is not None
    assert sample.count("- [ ]") >= 11
    assert "KOL 软推广：先问一个真问题" in sample
    assert "Benchmark Radar Top 10" in sample
    assert "https://benchmark-radar.org/cli" in sample
    assert "网上在热议什么，最后沉淀成了什么" in sample
    assert "B站：每天整理 Agent benchmark" in sample
    assert "Daily Agent Benchmarks" in sample


def test_render_section_omits_post_sample_when_none_configured():
    section = render_social_section("insight", "repo change", [], [{"name": "LinkedIn"}])
    assert "**发布文案示例**" not in section


def test_merge_checked_keeps_prior_ticks_and_leaves_new_channels_unchecked():
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [
            {"name": "X / Twitter"},
            {"name": "LinkedIn"},
            {"name": "知乎"},
        ],
    )
    existing = (
        "# 📡 AI Benchmark & Data Radar\n\n"
        "## 🗣 Daily social post\n\n"
        "- [x] LinkedIn\n"
        "- [ ] X / Twitter\n"
    )
    merged = merge_checked(section, existing)
    assert "- [x] LinkedIn" in merged
    assert "- [ ] X / Twitter" in merged
    assert "- [ ] 知乎" in merged


def test_merge_checked_keeps_ticks_for_escaped_channel_names():
    # A channel named with a pipe renders escaped (\\|) in the issue body.
    # extract_checked must unescape it so the tick survives the next render.
    section = render_social_section(
        "insight",
        "repo change",
        [],
        [{"name": "Community | General"}, {"name": "LinkedIn"}],
    )
    existing = "## 🗣 Daily social post\n\n- [x] Community \\| General\n- [ ] LinkedIn\n"
    merged = merge_checked(section, existing)
    assert "- [x] Community \\| General" in merged
    assert "- [ ] LinkedIn" in merged


def test_extract_checked_only_reads_the_social_section():
    body = (
        "## At a glance\n\n- [x] Some checklist elsewhere\n\n"
        "## 🗣 Daily social post\n\n"
        "- [x] LinkedIn\n- [ ] X / Twitter\n"
    )
    assert extract_checked(body) == {"LinkedIn"}


def test_social_command_writes_section(monkeypatch, tmp_path: Path):
    items_path = tmp_path / "items.json"
    items_path.write_text(
        json.dumps(
            {
                "evidence_items": [
                    {
                        "title": "A/Bench",
                        "source": "GitHub",
                        "total_score": 55.0,
                        "score_max": 100.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    channels_path = tmp_path / "social.yml"
    channels_path.write_text(
        "social:\n"
        "  post_sample: |-\n"
        "    一个反常识的发现：样本。\n"
        "  channels:\n"
        "    - name: X / Twitter\n"
        "      daily: true\n"
        "    - name: LinkedIn\n"
        "      daily: true\n",
        encoding="utf-8",
    )
    output = tmp_path / "social.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "social",
            "--items",
            str(items_path),
            "--channels",
            str(channels_path),
            "--social-output",
            str(output),
        ],
    )
    cli.main()
    body = output.read_text(encoding="utf-8")
    assert SECTION_HEADING in body
    assert "1 item across GitHub" in body
    assert "- [ ] X / Twitter" in body
    assert "一个反常识的发现：样本。" in body
