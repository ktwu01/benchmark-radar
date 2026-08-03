import csv
import io
import json
from pathlib import Path

import yaml

from benchmark_radar.export import (
    leaderboard_badge,
    leaderboard_csv,
    leaderboard_markdown,
    write_exports,
)
from benchmark_radar.model_cards import adoption_rank, build_adoption_rank


def write_registry(tmp_path: Path, document: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "model_cards.yml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def minimal_registry() -> dict:
    """Two benchmarks, two cards, one shared: enough to exercise ordering.

    Alpha is reported by both cards and Beta by one, so the ranking has a
    non-trivial order that a bug in any format would visibly disturb.
    """
    return {
        "schema_version": 1,
        "benchmarks": [
            {
                "id": "alpha",
                "name": "Alpha",
                "domain": "math",
                "url": "https://example.com/a",
                "caveat": "Alpha caveat.",
            },
            {
                "id": "beta",
                "name": "Beta",
                "domain": "coding",
                "url": "https://example.com/b",
                "caveat": "Beta caveat.",
            },
        ],
        "model_cards": [
            {
                "id": "org_one_card",
                "organization": "Org One",
                "model": "One",
                "document_type": "model_card",
                "published": "2025-01-01",
                "url": "https://example.com/one",
                "benchmarks": ["alpha", "beta"],
            },
            {
                "id": "org_two_card",
                "organization": "Org Two",
                "model": "Two",
                "document_type": "system_card",
                "published": "2025-02-01",
                "url": "https://example.com/two",
                "benchmarks": ["alpha"],
            },
        ],
    }


def _leaderboard(tmp_path: Path):
    return build_adoption_rank(write_registry(tmp_path, minimal_registry()))


def test_exports_are_derived_from_the_same_ranking(tmp_path):
    # The dashboard and the exports must not be able to publish two different
    # rankings of the same registry (issue #88). Every format is built from
    # `adoption_rank`, so the order and counts in the CSV are the order and
    # counts a dashboard reader sees, not a parallel computation that happens
    # to agree today.
    registry_path = write_registry(tmp_path, minimal_registry())
    leaderboard = build_adoption_rank(registry_path)

    written = write_exports(tmp_path / "out", registry_path=registry_path)
    exported = json.loads(written["json"].read_text(encoding="utf-8"))

    assert [entry["benchmark_id"] for entry in exported["entries"]] == [
        entry["benchmark_id"] for entry in leaderboard["entries"]
    ]
    assert exported["model_card_count"] == leaderboard["model_card_count"]

    rows = list(csv.DictReader(io.StringIO(written["csv"].read_text(encoding="utf-8"))))
    assert [row["benchmark_id"] for row in rows] == [
        entry["benchmark_id"] for entry in leaderboard["entries"]
    ]
    assert [int(row["card_count"]) for row in rows] == [
        entry["card_count"] for entry in leaderboard["entries"]
    ]


def test_every_export_carries_the_measures_caveat(tmp_path):
    # These files are built to travel: a CSV lands in a spreadsheet and a
    # Markdown table lands in someone else's README, both without the repo
    # beside them. A ranking separated from its disclaimer reads as a quality
    # ordering, which is the one misreading the registry exists to prevent, so
    # the caveat ships inside each artifact rather than next to it.
    registry_path = write_registry(tmp_path, minimal_registry())
    leaderboard = build_adoption_rank(registry_path)

    written = write_exports(tmp_path / "out", registry_path=registry_path)
    exported = json.loads(written["json"].read_text(encoding="utf-8"))
    assert exported["measures"] == leaderboard["measures"]
    assert "not benchmark quality" in exported["measures"]

    assert leaderboard["measures"] in leaderboard_markdown(leaderboard)

    rows = list(csv.DictReader(io.StringIO(leaderboard_csv(leaderboard))))
    # Carried per row, because a spreadsheet user filters and re-sorts: a
    # document-level note would be separated from the row it qualifies.
    assert all(row["caveat"] for row in rows)


def test_markdown_states_its_truncation(tmp_path):
    # A table that stops at N with no note reads as a complete ranking of N
    # benchmarks, which is a false claim about the registry rather than a
    # shorter true one.
    leaderboard = _leaderboard(tmp_path)
    table = leaderboard_markdown(leaderboard, limit=1)

    assert "Alpha" in table
    assert f"top 1 of {leaderboard['benchmark_count']} tracked benchmarks" in table
    # No note when nothing was cut: an unconditional line would claim a
    # truncation that did not happen.
    assert "Showing the top" not in leaderboard_markdown(leaderboard, limit=None)


def test_markdown_escapes_pipes_in_registry_prose(tmp_path):
    # Caveats and names are contributor-written prose. An unescaped pipe ends
    # its cell early and shifts every column after it, so the table silently
    # renders wrong rather than failing.
    registry = minimal_registry()
    registry["benchmarks"][0]["name"] = "Alpha | Bravo"
    leaderboard = adoption_rank(
        {
            "benchmarks": registry["benchmarks"],
            "model_cards": registry["model_cards"],
        }
    )
    table = leaderboard_markdown(leaderboard)

    row = next(line for line in table.splitlines() if "Alpha" in line)
    assert "Alpha \\| Bravo" in row
    # Five columns means five separators plus the two bounding pipes.
    assert row.count("|") - row.count("\\|") == 6


def test_csv_uses_rfc4180_line_endings(tmp_path):
    # Published as a release asset and read by tools on every platform, so the
    # terminator is fixed by the format rather than by whichever runner
    # generated the file.
    text = leaderboard_csv(_leaderboard(tmp_path))

    assert text.endswith("\r\n")
    assert "\r\r\n" not in text


def test_write_exports_preserves_csv_line_endings(tmp_path):
    # Regression: `write_text` without newline="" applies newline translation,
    # which turns the explicit \r\n into \r\r\n on Windows runners. The
    # in-memory string being correct is not evidence the written file is.
    written = write_exports(
        tmp_path / "out", registry_path=write_registry(tmp_path, minimal_registry())
    )
    raw = written["csv"].read_bytes()

    assert b"\r\r\n" not in raw
    assert raw.endswith(b"\r\n")


def test_badge_reports_coverage_not_rank(tmp_path):
    # A badge is a single number seen with no context. "GPQA Diamond is #1"
    # shown that way is exactly the quality claim this ranking does not make,
    # so the badge reports what the registry contains instead.
    leaderboard = _leaderboard(tmp_path)
    badge = json.loads(leaderboard_badge(leaderboard))

    assert badge["schemaVersion"] == 1
    assert str(leaderboard["model_card_count"]) in badge["message"]
    assert str(leaderboard["benchmark_count"]) in badge["message"]
    top = leaderboard["entries"][0]["name"]
    assert top not in badge["message"]


def test_export_json_omits_the_daily_corpus(tmp_path):
    # The whole point of the export is that citing the ranking should not
    # require downloading the corpus, its entity graph, and every observation
    # that the dashboard bundle also carries.
    written = write_exports(
        tmp_path / "out", registry_path=write_registry(tmp_path, minimal_registry())
    )
    exported = json.loads(written["json"].read_text(encoding="utf-8"))

    assert "corpus" not in exported
    assert "days" not in exported
    # The denominator travels with the counts: a card_count is not
    # interpretable without knowing how many documents it was counted against.
    assert exported["model_card_count"] == 2
    assert exported["counting_unit"].startswith("One document")


def test_export_records_its_source_url(tmp_path):
    written = write_exports(
        tmp_path / "out",
        registry_path=write_registry(tmp_path, minimal_registry()),
        source_url="https://example.com/?view=leaderboard",
    )

    exported = json.loads(written["json"].read_text(encoding="utf-8"))
    assert exported["source_url"] == "https://example.com/?view=leaderboard"
    assert "https://example.com/?view=leaderboard" in written["markdown"].read_text(
        encoding="utf-8"
    )


def test_shipped_registry_exports_cleanly(tmp_path):
    # The curated registry on disk is what actually gets published, and it
    # exercises real prose, real URLs, and benchmarks no card reports.
    registry_path = Path("data/model_cards.yml")
    if not registry_path.exists():  # pragma: no cover - depends on checkout
        return

    written = write_exports(tmp_path / "out", registry_path=registry_path)
    exported = json.loads(written["json"].read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(written["csv"].read_text(encoding="utf-8"))))

    assert len(rows) == exported["benchmark_count"]
    assert [int(row["rank"]) for row in rows] == list(range(1, len(rows) + 1))
    # Zero-adoption benchmarks are kept and ranked last: "in the registry,
    # adopted by nobody" is a finding, not a row to drop from the export.
    assert int(rows[-1]["card_count"]) <= int(rows[0]["card_count"])
