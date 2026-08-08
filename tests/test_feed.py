from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from benchmark_radar.feed import ATOM_NAMESPACE, FEED_URL, write_feed


def snapshot(day: str, *, source: str = "arXiv") -> dict:
    return {
        "date": day,
        "generated_at": f"{day}T12:15:00+00:00",
        "evidence_items": [
            {
                "source": source,
                "categories": ["benchmark", "evaluation"],
            }
        ],
        "attention": {"observations": [{"source": "Hacker News"}]},
    }


def test_feed_is_deterministic_valid_rss_with_one_item_per_snapshot(tmp_path):
    output = tmp_path / "feed.xml"
    snapshots = [snapshot("2026-08-06"), snapshot("2026-08-07", source="Labs & Papers")]

    write_feed(snapshots, output)
    first_bytes = output.read_bytes()
    write_feed(snapshots, output)

    assert output.read_bytes() == first_bytes
    root = ET.parse(output).getroot()
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    channel = root.find("channel")
    assert channel is not None
    atom_link = channel.find(f"{{{ATOM_NAMESPACE}}}link")
    assert atom_link is not None
    assert atom_link.attrib == {
        "href": FEED_URL,
        "rel": "self",
        "type": "application/rss+xml",
    }

    items = channel.findall("item")
    assert [item.findtext("title") for item in items] == [
        "Benchmark Radar — 2026-08-07",
        "Benchmark Radar — 2026-08-06",
    ]
    assert items[0].findtext("link") == (
        "https://ktwu01.github.io/benchmark-radar/?date=2026-08-07"
    )
    assert items[0].find("guid").attrib["isPermaLink"] == "true"
    assert "1 evidence observation from 1 source" in items[0].findtext("description")
    assert "benchmark: 1, evaluation: 1" in items[0].findtext("description")
    assert parsedate_to_datetime(items[0].findtext("pubDate")).isoformat() == (
        "2026-08-07T00:00:00+00:00"
    )


def test_site_advertises_and_visibly_links_the_feed():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert 'rel="alternate" type="application/rss+xml"' in html
    assert 'class="repo-badge feed-badge"' in html
    assert 'href="feed.xml"' in html
    assert "Subscribe to Benchmark Radar via RSS" in html
