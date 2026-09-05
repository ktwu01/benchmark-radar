import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from benchmark_radar.export import write_exports
from benchmark_radar.models import RadarItem, RadarRun
from benchmark_radar.snapshots import rebuild_dashboard, records_badge, write_snapshot

README = Path("README.md")
README_ZH = Path("README.zh-CN.md")
SKILL = Path("skills/benchmark-radar/SKILL.md")
TECHNICAL_REPORT = "https://zenodo.org/records/22167102"


def _run(day: int) -> RadarRun:
    generated = datetime(2026, 8, day, 12, 15, tzinfo=UTC)
    return RadarRun(
        generated_at=generated,
        since=datetime(2026, 8, day - 1, 12, 15, tzinfo=UTC),
        items=[
            RadarItem(
                source="Hugging Face",
                source_id=f"org/dataset-{day}",
                title=f"Benchmark dataset {day}",
                url=f"https://huggingface.co/datasets/org/dataset-{day}",
                published_at=generated,
                categories=["benchmark"],
                summary="A scored evaluation dataset with documented verifier behaviour.",
                event_kind="released",
            )
        ],
        health=[],
        selection={"taxonomy_version": "taxonomy-v2", "lookback_hours": 48},
    )


def test_readme_embeds_the_data_driven_records_badge():
    # The record-count badge is the one README artifact whose whole purpose is
    # to be copied, so its URL is quoted twice: once rendered, once as a
    # copyable snippet. Both point at the published endpoint rather than at a
    # number typed into the prose, so the count cannot drift from the corpus
    # (issue #197).
    if not README.exists():  # pragma: no cover
        return
    text = README.read_text(encoding="utf-8")

    url = "https://benchmark-radar.org/data/records-badge.json"
    quoted = quote(url, safe="")
    assert f"https://img.shields.io/endpoint?url={quoted}" in text


def test_readme_badge_endpoint_filename_matches_the_dashboard_builder(tmp_path):
    # Ties the README's embedded badge URL to the writer, so renaming the
    # artifact breaks a test here rather than silently breaking the badge.
    snapshot_dir = tmp_path / "snapshots"
    write_snapshot(_run(2), snapshot_dir)
    output = tmp_path / "site" / "data" / "radar.json"

    rebuild_dashboard(snapshot_dir, output)

    assert (tmp_path / "site" / "data" / "records-badge.json").exists()


def test_leaderboard_badge_endpoint_filename_matches_the_exporter():
    # The leaderboard badge is a separate artifact produced by the export
    # layer; the README does not embed it, but the exporter contract must not
    # silently change under it.
    written = write_exports(Path(tempfile.mkdtemp()), source_url=None)
    assert written["badge"].name == "leaderboard-badge.json"


def test_records_badge_reports_the_corpus_not_a_hardcoded_number():
    # The badge derives its message from the dashboard bundle, so it can only
    # state what the corpus actually holds rather than a hand-edited count.
    dashboard = {"snapshot_count": 23, "corpus": {"observation_count": 4334}}
    document = json.loads(records_badge(dashboard))
    assert document["schemaVersion"] == 1
    assert document["label"] == "benchmark records collected"
    assert document["message"] == "4334 records · 23 days"


def test_chinese_readme_mirrors_the_english_one():
    # The owner asked for a multiple-language README; the Chinese page must
    # exist, carry the same data-driven badge, and link back to the English one
    # (issue #197).
    if not README_ZH.exists():  # pragma: no cover
        return
    zh = README_ZH.read_text(encoding="utf-8")

    url = "https://benchmark-radar.org/data/records-badge.json"
    quoted = quote(url, safe="")
    assert f"https://img.shields.io/endpoint?url={quoted}" in zh
    assert "[English](README.md)" in zh
    # The language switch sits at the top-left, above the title, with a plain
    # language label rather than a filename.
    assert '<div align="left">' in zh.split("# Benchmark Radar")[0]
    assert "[README.md](README.md)" not in zh


def test_readmes_link_the_citable_technical_report():
    for readme in (README, README_ZH):
        text = readme.read_text(encoding="utf-8")
        assert f'<a href="{TECHNICAL_REPORT}">' in text
        assert "TECH%20REPORT" in text


def test_citation_metadata_prefers_the_technical_report():
    text = Path("CITATION.cff").read_text(encoding="utf-8")
    assert "preferred-citation:" in text
    assert 'doi: "10.5281/zenodo.22167102"' in text
    assert f'url: "{TECHNICAL_REPORT}"' in text


def test_public_bibtex_names_both_report_authors():
    author = "author       = {Wu, Koutian and Zhou, Junjie}"
    for readme in (README, README_ZH):
        assert author in readme.read_text(encoding="utf-8")


def test_readmes_offer_a_short_agent_setup_prompt():
    # Regression: local-query setup should be one copy-paste command, not a second
    # maintainer manual (issue #436).
    english = README.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")
    assert "Then ask your coding agent about benchmarks." in english
    assert "之后直接问你的 coding agent benchmark 就行。" in chinese
    english_section = english.split("## Query it locally", 1)[1].split("## More", 1)[0]
    chinese_section = chinese.split("## 在本地查询", 1)[1].split("## 更多", 1)[0]
    for section in (english_section, chinese_section):
        assert "npx skills add ktwu01/benchmark-radar" in section
        assert "skills/benchmark-radar/SKILL.md" in section
        assert "normalize-external" not in section
        assert "build-data-release" not in section


def test_readmes_expose_the_consumer_skill():
    # The setup prompt routes agents to the public, purpose-neutral consumer guide.
    assert SKILL.exists()
    skill_path = "skills/benchmark-radar/SKILL.md"
    assert skill_path in README.read_text(encoding="utf-8")
    assert skill_path in README_ZH.read_text(encoding="utf-8")


def test_consumer_skill_recovers_a_broken_cli() -> None:
    # Setup is the Skill's job, not a checklist the reader has to run: the two
    # published lines only work if the Skill installs and repairs on its own.
    text = SKILL.read_text(encoding="utf-8")
    assert "missing or broken" in text
    assert "--force-reinstall" in text
    assert "say you are installing the CLI from the official repository" in text
    assert "report what you ran" in text


def test_consumer_skill_offers_starter_example_on_setup() -> None:
    # When setup completes without a specific query, the Skill showcases a starter
    # example (e.g. popular agent benchmarks) so the user sees immediate results.
    text = SKILL.read_text(encoding="utf-8")
    assert "starter use case" in text
    assert "agent" in text
    assert "present a concise summary" in text


def test_consumer_skill_keeps_acceptance_with_the_agent() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "retrieval_score" in text
    assert "idf_coverage" in text
    assert "remove conversational wrapper text" in text
    assert "no confident match" in text
    assert "call `show`" in text
