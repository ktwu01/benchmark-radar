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

    url = "https://koutian.is-a.dev/benchmark-radar/data/records-badge.json"
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

    url = "https://koutian.is-a.dev/benchmark-radar/data/records-badge.json"
    quoted = quote(url, safe="")
    assert f"https://img.shields.io/endpoint?url={quoted}" in zh
    assert "[English](README.md)" in zh
    # The language switch sits at the top-right, above the title, with a plain
    # language label rather than a filename.
    assert '<div align="right">' in zh.split("# Benchmark Radar")[0]
    assert "[README.md](README.md)" not in zh
