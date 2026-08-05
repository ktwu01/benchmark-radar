import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from benchmark_radar.export import write_exports
from benchmark_radar.model_cards import build_adoption_rank

README = Path("README.md")
REGISTRY = Path("data/model_cards.yml")


def _leaderboard():
    return build_adoption_rank(REGISTRY)


def test_readme_headline_table_matches_the_registry():
    # The README's first screen quotes the ranking as a static table, because a
    # reader deciding whether to look further will not click through to find
    # out what the project found. That copy is the one part of the ranking that
    # is not generated, so nothing else would notice it going stale -- and a
    # README advertising counts the registry no longer supports discredits the
    # ranking far more than having no table would.
    if not README.exists() or not REGISTRY.exists():  # pragma: no cover
        return
    text = README.read_text(encoding="utf-8")
    leaderboard = _leaderboard()

    # Only the rows above the "Across N curated model cards" summary line: the
    # Markdown table syntax also appears later in the README for the source and
    # config tables, which have nothing to do with the ranking.
    headline = text.split("Across ", 1)[0]
    rows = re.findall(
        r"^\| (\d+) \| \[?([^\]|]+?)\]?\([^)]*\) \| ([^|]+?) \| (\d+) \| (\d+) \|$",
        headline,
        flags=re.MULTILINE,
    )
    assert rows, "the README headline table was not found or changed shape"

    by_rank = {entry["rank"]: entry for entry in leaderboard["entries"]}
    for rank, name, domain, card_count, organization_count in rows:
        entry = by_rank[int(rank)]
        assert name.strip() == entry["name"]
        assert domain.strip() == entry["domain"]
        assert int(card_count) == entry["card_count"]
        assert int(organization_count) == entry["organization_count"]


def test_readme_headline_totals_match_the_registry():
    # The denominator is what makes a count of 23 mean anything, and it moves
    # every time a card is added.
    if not README.exists() or not REGISTRY.exists():  # pragma: no cover
        return
    text = README.read_text(encoding="utf-8")
    leaderboard = _leaderboard()

    assert (
        f"Across {leaderboard['model_card_count']} curated model cards, system cards, "
        f"and technical reports from {leaderboard['organization_count']}\n"
        f"organizations, tracking {leaderboard['benchmark_count']} benchmarks."
    ) in text


def test_readme_badge_points_at_the_published_endpoint():
    # The badge is the one artifact whose whole purpose is to be copied by
    # someone else, so its URL is quoted twice: once rendered, once as a
    # copyable snippet. Both are hand-written, and a badge pointing at a path
    # the export layer no longer writes fails as a broken image on every README
    # that copied it -- including other people's.
    if not README.exists():  # pragma: no cover
        return
    text = README.read_text(encoding="utf-8")

    url = "https://koutian.is-a.dev/benchmark-radar/data/leaderboard-badge.json"
    quoted = quote(url, safe="")
    assert text.count(f"https://img.shields.io/endpoint?url={quoted}") == 2


def test_readme_badge_endpoint_filename_matches_the_exporter():
    # Ties the name above to the writer, so renaming the artifact breaks a test
    # here rather than silently breaking every embedded badge.
    written = write_exports(Path(tempfile.mkdtemp()), source_url=None)
    assert written["badge"].name == "leaderboard-badge.json"


def test_readme_headline_keeps_the_quality_caveat():
    # The headline table is the most quotable thing in the repository and the
    # most likely to be read as a quality ordering. The caveat is not decoration
    # on that table; it is the reason the table is publishable.
    if not README.exists():  # pragma: no cover
        return
    text = README.read_text(encoding="utf-8")

    headline = text.split("## The daily radar", 1)[0]
    assert "measures vendor attention, not benchmark quality" in headline
