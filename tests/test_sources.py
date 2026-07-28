from datetime import UTC, datetime
from urllib.error import HTTPError

from benchmark_radar.sources import fetch_arxiv

ARXIV_XML = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2607.12345v2</id>
    <updated>2026-07-26T18:00:00Z</updated>
    <published>2026-07-23T18:00:00Z</published>
    <title>Weekend benchmark</title>
    <summary>A benchmark announced after the submission window.</summary>
    <author><name>Radar Author</name></author>
  </entry>
</feed>
"""

ARXIV_RSS = """\
<rss xmlns:arxiv="http://arxiv.org/schemas/atom"
     xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <item>
      <title>Fallback evaluation benchmark</title>
      <link>https://arxiv.org/abs/2607.54321</link>
      <description>arXiv:2607.54321v1 Announce Type: new
Abstract: A benchmark recovered from the official category feed.</description>
      <guid isPermaLink="false">oai:arXiv.org:2607.54321v1</guid>
      <pubDate>Mon, 27 Jul 2026 00:00:00 -0400</pubDate>
      <arxiv:announce_type>new</arxiv:announce_type>
      <dc:creator>Radar Author, Second Author</dc:creator>
    </item>
  </channel>
</rss>
"""


def test_arxiv_uses_overlap_and_updated_timestamp(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, params: calls.append(params) or ARXIV_XML,
    )
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", delays.append)
    since = datetime(2026, 7, 25, 12, tzinfo=UTC)

    items = fetch_arxiv(
        {
            "queries": ["one", "two", "three"],
            "overlap_hours": 120,
            "request_delay_seconds": 3,
        },
        since,
        10,
    )

    assert len(calls) == 3
    assert delays == [3, 3]
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 7, 23, 18, tzinfo=UTC)
    assert items[0].updated_at == datetime(2026, 7, 26, 18, tzinfo=UTC)
    assert items[0].event_kind == "updated"


def test_arxiv_falls_back_to_official_rss_when_atom_is_rate_limited(monkeypatch):
    def fake_get_text(url, params=None):
        if url == "https://export.arxiv.org/api/query":
            raise HTTPError(url, 429, "Too Many Requests", {}, None)
        assert url == "https://rss.arxiv.org/rss/cs.AI"
        return ARXIV_RSS

    monkeypatch.setattr("benchmark_radar.sources.get_text", fake_get_text)

    items = fetch_arxiv(
        {
            "queries": ["all:benchmark"],
            "rss_categories": ["cs.AI"],
            "rss_keywords": ["benchmark"],
        },
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        10,
    )

    assert len(items) == 1
    assert items[0].source_id == "2607.54321"
    assert items[0].published_at == datetime(2026, 7, 27, 4, tzinfo=UTC)
    assert items[0].authors == ["Radar Author", "Second Author"]
    assert items[0].event_kind == "released"


def test_arxiv_can_use_official_rss_as_primary(monkeypatch):
    def fake_get_text(url, params=None):
        assert url == "https://rss.arxiv.org/rss/cs.AI"
        assert params is None
        return ARXIV_RSS

    monkeypatch.setattr("benchmark_radar.sources.get_text", fake_get_text)

    items = fetch_arxiv(
        {
            "atom_enabled": False,
            "queries": ["must not be requested"],
            "rss_categories": ["cs.AI"],
            "rss_keywords": ["benchmark"],
        },
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["2607.54321"]
