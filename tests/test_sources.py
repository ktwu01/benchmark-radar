from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest
import yaml

from benchmark_radar.http import RequestError
from benchmark_radar.models import RadarItem
from benchmark_radar.pipeline import _score_and_select, score_item
from benchmark_radar.sources import (
    GITHUB_RELEASE_PARSER_VERSION,
    ConnectorPayloadError,
    collection_method,
    fetch_arxiv,
    fetch_brave,
    fetch_crossref,
    fetch_first_party_feeds,
    fetch_github,
    fetch_github_organizations,
    fetch_github_releases,
    fetch_huggingface,
    fetch_huggingface_papers,
    fetch_kaggle_datasets,
    fetch_openaire,
    fetch_openalex,
    fetch_openreview,
    fetch_semantic_scholar,
    fetch_zenodo_records,
    github_release_title,
)

FIRST_PARTY_RSS = """\
<rss version="2.0"><channel>
  <item>
    <title>A new agent evaluation benchmark</title>
    <link>https://lab.example/benchmark</link>
    <guid>benchmark-one</guid>
    <pubDate>Sat, 08 Aug 2026 12:00:00 GMT</pubDate>
    <description>We release a dataset and evaluation suite.</description>
  </item>
  <item>
    <title>Office update</title>
    <link>https://lab.example/office</link>
    <guid>office-one</guid>
    <pubDate>Sat, 08 Aug 2026 13:00:00 GMT</pubDate>
    <description>News about a new office.</description>
  </item>
</channel></rss>
"""


FIRST_PARTY_ATOM = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:lab.example,2026:leaderboard</id>
    <title>Leaderboard evaluation update</title>
    <link rel="alternate" href="https://lab.example/leaderboard"/>
    <published>2026-08-08T14:00:00Z</published>
    <updated>2026-08-08T15:00:00Z</updated>
    <summary>Updated benchmark results.</summary>
  </entry>
</feed>
"""


FIRST_PARTY_ATOM_RELATIVE_LINK = """\
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>/model-release</id>
    <title>Introducing a new model</title>
    <link rel="alternate" href="/model-release/"/>
    <published>2026-08-08T14:00:00Z</published>
    <updated>2026-08-08T14:00:00Z</updated>
    <summary>Evaluation results across the benchmark.</summary>
  </entry>
</feed>
"""


def test_first_party_feeds_parse_rss_and_atom_and_filter_noise(monkeypatch):
    payloads = {
        "https://lab.example/rss": FIRST_PARTY_RSS,
        "https://lab.example/atom": FIRST_PARTY_ATOM,
    }
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, attempts=3, timeout=30: payloads[url],
    )

    items = fetch_first_party_feeds(
        {
            "feeds": [
                {"name": "Lab RSS", "url": "https://lab.example/rss"},
                {"name": "Lab Atom", "url": "https://lab.example/atom"},
            ]
        },
        datetime(2026, 8, 8, 0, tzinfo=UTC),
        10,
    )

    assert [item.title for item in items] == [
        "Leaderboard evaluation update",
        "A new agent evaluation benchmark",
    ]
    assert items[0].event_kind == "updated"
    assert items[0].source == "First-party feed"
    assert items[0].source_id == "Lab Atom:tag:lab.example,2026:leaderboard"
    assert items[0].organizations == ["Lab Atom"]


def test_first_party_feeds_resolve_relative_entry_links(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, attempts=3, timeout=30: FIRST_PARTY_ATOM_RELATIVE_LINK,
    )

    items = fetch_first_party_feeds(
        {"feeds": [{"name": "Relative Lab", "url": "https://lab.example/feed.xml"}]},
        datetime(2026, 8, 8, 0, tzinfo=UTC),
        10,
    )

    assert [item.url for item in items] == ["https://lab.example/model-release/"]
    # The entry's own id still identifies the item, so resolving the link does
    # not renumber records already recorded under the relative URL.
    assert items[0].source_id == "Relative Lab:/model-release"


def test_first_party_feeds_require_any_narrows_broad_publishers(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, attempts=3, timeout=30: FIRST_PARTY_RSS,
    )

    feed = {"name": "Broad Publisher", "url": "https://lab.example/rss"}
    unfiltered = fetch_first_party_feeds({"feeds": [feed]}, datetime(2026, 8, 8, 0, tzinfo=UTC), 10)
    assert [item.title for item in unfiltered] == ["A new agent evaluation benchmark"]

    # The shared keyword gate still passes the item; require_any rejects it because
    # no AI-domain term appears, which is what keeps storage or database posts out.
    filtered = fetch_first_party_feeds(
        {"feeds": [{**feed, "require_any": ["protein folding"]}]},
        datetime(2026, 8, 8, 0, tzinfo=UTC),
        10,
    )
    assert filtered == []

    kept = fetch_first_party_feeds(
        {"feeds": [{**feed, "require_any": ["agent"]}]},
        datetime(2026, 8, 8, 0, tzinfo=UTC),
        10,
    )
    assert [item.title for item in kept] == ["A new agent evaluation benchmark"]


def test_first_party_feeds_reject_non_feed_documents(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, attempts=3, timeout=30: "<html><body>Not a feed</body></html>",
    )

    with pytest.raises(ConnectorPayloadError, match="incompatible feed document"):
        fetch_first_party_feeds(
            {"feeds": [{"name": "Broken", "url": "https://lab.example/feed"}]},
            datetime(2026, 8, 8, 0, tzinfo=UTC),
            10,
        )


def test_first_party_feeds_isolate_one_broken_feed(monkeypatch):
    def fake_get_text(url, attempts=3, timeout=30):
        if url.endswith("/broken"):
            raise RequestError("HTTP 503 from https://lab.example/broken")
        return FIRST_PARTY_RSS

    monkeypatch.setattr("benchmark_radar.sources.get_text", fake_get_text)
    config = {
        "feeds": [
            {"name": "Broken Lab", "url": "https://lab.example/broken"},
            {"name": "Healthy Lab", "url": "https://lab.example/healthy"},
        ]
    }

    items = fetch_first_party_feeds(config, datetime(2026, 8, 8, 0, tzinfo=UTC), 10)

    assert [item.title for item in items] == ["A new agent evaluation benchmark"]
    assert config["_source_warnings"] == [
        "Broken Lab: RequestError: HTTP 503 from https://lab.example/broken"
    ]


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

SWE_REFACTOR_RSS = """\
<rss xmlns:arxiv="http://arxiv.org/schemas/atom"
     xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <item>
      <title>SWE Refactor Bench: Can Coding Agents Complete a Long-Horizon Migration?</title>
      <link>https://arxiv.org/abs/2608.23564</link>
      <description>arXiv:2608.23564v1 Announce Type: new
Abstract: We introduce SWE Refactor Bench, a benchmark comprising 20 migrations.</description>
      <guid isPermaLink="false">oai:arXiv.org:2608.23564v1</guid>
      <pubDate>Wed, 26 Aug 2026 00:00:00 -0400</pubDate>
      <arxiv:announce_type>new</arxiv:announce_type>
      <dc:creator>Deyao Hong, Yizhe Chi</dc:creator>
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
    assert all("lastUpdatedDate:" in call["search_query"] for call in calls)
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


def test_arxiv_atom_rejects_missing_dates_instead_of_inventing_now(monkeypatch):
    malformed = ARXIV_XML.replace("<updated>2026-07-26T18:00:00Z</updated>", "")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, params=None: malformed,
    )

    with pytest.raises(ConnectorPayloadError, match="arXiv Atom item is missing required fields"):
        fetch_arxiv(
            {"queries": ["all:benchmark"], "rss_categories": []},
            datetime(2026, 7, 25, 12, tzinfo=UTC),
            10,
        )


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


def test_arxiv_config_keeps_named_bench_releases(monkeypatch):
    """Issue #379: `SWE Refactor Bench:` used no configured exact phrase."""
    config = yaml.safe_load(Path("config.yml").read_text(encoding="utf-8"))["sources"]["arxiv"]
    requested = []

    def fake_get_text(url, params=None):
        assert params is None
        requested.append(url)
        if url == "https://rss.arxiv.org/rss/cs.SE":
            return SWE_REFACTOR_RSS
        return "<rss version='2.0'><channel /></rss>"

    monkeypatch.setattr("benchmark_radar.sources.get_text", fake_get_text)

    items = fetch_arxiv(config, datetime(2026, 8, 26, 5, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["2608.23564"]
    assert requested == [
        "https://rss.arxiv.org/rss/cs.AI",
        "https://rss.arxiv.org/rss/cs.CL",
        "https://rss.arxiv.org/rss/cs.CV",
        "https://rss.arxiv.org/rss/cs.SE",
    ]


def test_openalex_carries_author_institutions(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "key")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "Institution-backed benchmark",
                    "publication_date": "2026-08-26",
                    "primary_location": {"landing_page_url": "https://example.com/w1"},
                    "authorships": [
                        {
                            "author": {"display_name": "Radar Author"},
                            "institutions": [
                                {"display_name": "Example University"},
                                {"display_name": "Example University"},
                                {"display_name": "Example Lab"},
                            ],
                        }
                    ],
                    "cited_by_count": 0,
                }
            ]
        },
    )

    items = fetch_openalex(
        {"searches": ["benchmark"]},
        datetime(2026, 8, 25, tzinfo=UTC),
        10,
        now=datetime(2026, 8, 26, 12, tzinfo=UTC),
    )

    assert items[0].authors == ["Radar Author"]
    assert items[0].organizations == ["Example University", "Example Lab"]


def test_openalex_accepts_explicitly_null_authorships(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "key")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "Benchmark without authorship metadata",
                    "publication_date": "2026-08-26",
                    "primary_location": {"landing_page_url": "https://example.com/w1"},
                    "authorships": None,
                    "cited_by_count": 0,
                }
            ]
        },
    )

    items = fetch_openalex(
        {"searches": ["benchmark"]},
        datetime(2026, 8, 25, tzinfo=UTC),
        10,
        now=datetime(2026, 8, 26, 12, tzinfo=UTC),
    )

    assert items[0].authors == []
    assert items[0].organizations == []


def test_arxiv_rejects_incompatible_empty_rss_document(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_text",
        lambda url, params=None: "<html><body>maintenance</body></html>",
    )

    with pytest.raises(ConnectorPayloadError, match="arXiv RSS returned an incompatible document"):
        fetch_arxiv(
            {
                "atom_enabled": False,
                "rss_categories": ["cs.AI"],
            },
            datetime(2026, 8, 1, 12, tzinfo=UTC),
            10,
        )


def test_arxiv_rejects_malformed_present_rss_item(monkeypatch):
    malformed = """\
<rss version="2.0">
  <channel>
    <item>
      <title>New benchmark</title>
      <link>https://arxiv.org/abs/2608.00001</link>
      <description>A benchmark announcement without a publication date.</description>
    </item>
  </channel>
</rss>
"""
    monkeypatch.setattr("benchmark_radar.sources.get_text", lambda url, params=None: malformed)

    with pytest.raises(ConnectorPayloadError, match="arXiv RSS item is missing required fields"):
        fetch_arxiv(
            {
                "atom_enabled": False,
                "rss_categories": ["cs.AI"],
            },
            datetime(2026, 8, 1, 12, tzinfo=UTC),
            10,
        )


def _github_row(index: int) -> dict:
    return {
        "full_name": f"org/repo{index}",
        "html_url": f"https://github.com/org/repo{index}",
        "pushed_at": "2026-07-27T00:00:00Z",
        "created_at": "2026-07-27T00:00:00Z",
        "description": f"Benchmark suite {index}",
        "stargazers_count": index,
        "forks_count": 0,
    }


def test_github_pages_past_the_hundred_row_search_limit(monkeypatch):
    # The search API caps a response at 100 rows, so a single request silently
    # dropped everything beyond it whenever a query matched more.
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", lambda seconds: None)
    requested_pages = []

    def fake_get_json(url, params=None, headers=None):
        requested_pages.append(params["page"])
        start = (params["page"] - 1) * 100
        if start >= 150:
            return {"items": []}
        return {"items": [_github_row(start + offset) for offset in range(min(100, 150 - start))]}

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    items = fetch_github(
        {"queries": ["benchmark"]},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        300,
    )

    assert requested_pages == [1, 2]
    assert len(items) == 150


def test_github_stops_paging_once_a_page_is_short(monkeypatch):
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", lambda seconds: None)
    calls = []

    def fake_get_json(url, params=None, headers=None):
        calls.append(params["page"])
        return {"items": [_github_row(0)]}

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    items = fetch_github(
        {"queries": ["benchmark"]},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        300,
    )

    assert calls == [1]
    assert len(items) == 1


def test_github_bounds_total_requests_when_unauthenticated(monkeypatch):
    # Search allows ~10 requests/minute without a token. Paging every query to
    # exhaustion tripped a 403, which fails a required source and aborts the run.
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", lambda seconds: None)
    calls = []

    def fake_get_json(url, params=None, headers=None):
        calls.append(params["page"])
        # Rows repeat across queries, so the per-source limit is never reached
        # and only the request budget can stop the walk.
        return {"items": [_github_row(offset) for offset in range(100)]}

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    fetch_github(
        {"queries": ["a", "b", "c", "d"], "max_requests": 8},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        1000,
    )

    assert len(calls) == 8


def test_github_spaces_unauthenticated_requests(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    delays = []
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", delays.append)
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params=None, headers=None: {
            "items": [_github_row(offset) for offset in range(100)]
        },
    )

    fetch_github(
        {"queries": ["a"], "max_requests": 3},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        300,
    )

    assert delays and all(delay > 0 for delay in delays)


def test_github_pages_round_robin_so_no_query_is_skipped(monkeypatch):
    # Draining the first query to the source limit spent the whole budget on
    # it and never issued the other configured searches, dropping whole topics.
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", lambda seconds: None)
    queried = []

    def fake_get_json(url, params=None, headers=None):
        queried.append(params["q"].split(" pushed")[0])
        return {"items": [_github_row(offset) for offset in range(100)]}

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    fetch_github(
        {"queries": ["alpha", "beta", "gamma"], "max_requests": 3},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        300,
    )

    assert sorted(queried) == ["alpha", "beta", "gamma"]


def test_github_respects_the_per_source_limit_after_round_robin(monkeypatch):
    # Every query contributes before the running total is known, so the final
    # sweep can overshoot; the cap must still hold for the returned records.
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", lambda seconds: None)
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params=None, headers=None: {
            "items": [
                # Unique across query and page so nothing dedupes away.
                _github_row(ord(params["q"][0]) * 100_000 + params["page"] * 1000 + offset)
                for offset in range(100)
            ]
        },
    )

    items = fetch_github(
        {"queries": ["alpha", "beta", "gamma"], "max_requests": 9},
        datetime(2026, 7, 25, 12, tzinfo=UTC),
        150,
    )

    assert len(items) == 150


def test_github_preserves_creation_and_update_times(monkeypatch):
    row = _github_row(1)
    row["created_at"] = "2026-06-01T00:00:00Z"
    row["pushed_at"] = "2026-07-27T12:00:00Z"
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params=None, headers=None: {"items": [row]},
    )

    items = fetch_github(
        {"queries": ["benchmark"], "request_delay_seconds": 0},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert items[0].published_at == datetime(2026, 6, 1, tzinfo=UTC)
    assert items[0].updated_at == datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert items[0].event_kind == "updated"


def test_github_config_discovers_and_routes_rsi_exam(monkeypatch):
    """Issue #408: the named benchmark matched no configured GitHub query."""
    config = yaml.safe_load(Path("config.yml").read_text(encoding="utf-8"))
    github_config = {**config["sources"]["github"], "request_delay_seconds": 0}
    queries = []

    def fake_get_json(url, params=None, headers=None):
        query = params["q"].split(" pushed:", 1)[0]
        queries.append(query)
        if query != '"RSI-Exam" in:name,description,readme':
            return {"items": []}
        return {
            "items": [
                {
                    "full_name": "aiming-lab/RSI-Exam",
                    "html_url": "https://github.com/aiming-lab/RSI-Exam",
                    "created_at": "2026-08-26T06:58:55Z",
                    "pushed_at": "2026-08-29T05:24:25Z",
                    "description": (
                        "RSI-Exam: Measuring Recursive Self-Improvement on Long-Horizon, "
                        "Executable Research Tasks"
                    ),
                    "stargazers_count": 75,
                    "forks_count": 3,
                },
                {
                    "full_name": "example/AgentQuant",
                    "html_url": "https://github.com/example/AgentQuant",
                    "created_at": "2026-08-26T06:58:55Z",
                    "pushed_at": "2026-08-29T05:24:25Z",
                    "description": "A quantitative trading platform",
                    "stargazers_count": 75,
                    "forks_count": 3,
                },
            ]
        }

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    items = fetch_github(github_config, datetime(2026, 8, 27, tzinfo=UTC), 300)
    published, _selection = _score_and_select(
        items,
        config,
        now=datetime(2026, 8, 29, 12, tzinfo=UTC),
        fetched_count=len(items),
        suppressed_count=0,
    )

    assert '"RSI-Exam" in:name,description,readme' in queries
    assert [item.source_id for item in items] == [
        "aiming-lab/RSI-Exam",
        "example/AgentQuant",
    ]
    assert [item.source_id for item in published] == ["aiming-lab/RSI-Exam"]
    assert published[0].watchlist == "RSI-Exam"


def _github_organization_row(index, *, created="2026-07-27T12:00:00Z"):
    return {
        "id": index,
        "full_name": f"lab/repository-{index}",
        "html_url": f"https://github.com/lab/repository-{index}",
        "created_at": created,
        "pushed_at": "2026-07-27T13:00:00Z",
        "description": "A benchmark evaluation dataset.",
        "stargazers_count": 5,
        "forks_count": 1,
        "fork": False,
        "archived": False,
        "disabled": False,
    }


def test_github_organizations_collect_only_recent_non_fork_repositories(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.load_priority_github_organizations",
        lambda path: [{"login": "first-lab", "tier": "priority", "display_name": "First Lab"}],
    )
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append((url, kwargs["params"]))
        row = _github_organization_row(1)
        fork = _github_organization_row(2)
        fork["fork"] = True
        historical = _github_organization_row(3, created="2026-07-25T12:00:00Z")
        return [row, fork, historical]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_github_organizations(
        {"registry_path": "ignored.yml", "max_requests": 2, "page_size": 30},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert len(calls) == 1
    assert calls[0][0] == "https://api.github.com/orgs/first-lab/repos"
    assert calls[0][1]["sort"] == "created"
    assert [item.source_id for item in items] == ["lab/repository-1"]
    assert items[0].source == "GitHub Organization"
    assert items[0].organizations == ["First Lab"]
    assert items[0].event_kind == "released"


def test_github_organizations_isolate_one_failed_organization(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.load_priority_github_organizations",
        lambda path: [
            {"login": "broken-lab", "tier": "priority", "display_name": "Broken Lab"},
            {"login": "healthy-lab", "tier": "standard", "display_name": "Healthy Lab"},
        ],
    )

    def fake_get_json(url, **kwargs):
        if "broken-lab" in url:
            raise RequestError("HTTP 503 from https://api.github.com/orgs/broken-lab/repos")
        return [_github_organization_row(4)]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {"registry_path": "ignored.yml", "max_requests": 2}
    items = fetch_github_organizations(config, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["lab/repository-4"]
    assert config["_source_warnings"][0].startswith("broken-lab: RequestError:")


def test_huggingface_papers_preserves_arxiv_and_project_identifiers(monkeypatch):
    payload = [
        {
            "paper": {
                "id": "2607.99999",
                "title": "A New Agent Benchmark",
                "publishedAt": "2026-07-27T00:00:00Z",
                "submittedOnDailyAt": "2026-07-27T12:00:00Z",
                "summary": "An upstream evaluation suite.",
                "upvotes": 9,
                "authors": [{"name": "Paper Author"}],
                "githubRepo": "https://github.com/lab/benchmark",
                "projectPage": "https://lab.example/benchmark",
            }
        }
    ]
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, **kwargs: payload)

    items = fetch_huggingface_papers({}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["2607.99999"]
    assert items[0].source == "Hugging Face Papers"
    assert items[0].published_at == datetime(2026, 7, 27, tzinfo=UTC)
    assert items[0].artifact_urls == [
        "https://arxiv.org/abs/2607.99999",
        "https://github.com/lab/benchmark",
        "https://lab.example/benchmark",
    ]
    assert items[0].summary == "An upstream evaluation suite."


def test_kaggle_datasets_preserves_source_text_and_tags(monkeypatch):
    payload = [
        {
            "ref": "lab/agent-benchmark",
            "url": "https://www.kaggle.com/datasets/lab/agent-benchmark",
            "title": "Agent Benchmark Dataset",
            "subtitle": "A public evaluation dataset.",
            "lastUpdated": "2026-07-27T12:00:00Z",
            "creatorName": "Dataset Author",
            "downloadCount": 11,
            "voteCount": 2,
            "viewCount": 31,
            "tags": [{"name": "benchmark"}, {"name": "llm"}],
        }
    ]
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, **kwargs: payload)

    items = fetch_kaggle_datasets(
        {"searches": ["agent benchmark"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["lab/agent-benchmark"]
    assert items[0].source == "Kaggle Dataset"
    assert items[0].summary == "A public evaluation dataset. | benchmark | llm"
    assert items[0].metrics == {"downloads": 11.0, "votes": 2.0, "views": 31.0}


def test_zenodo_records_preserve_doi_and_upstream_metadata(monkeypatch):
    payload = {
        "hits": {
            "hits": [
                {
                    "recid": "12345",
                    "doi_url": "https://doi.org/10.5281/zenodo.12345",
                    "updated": "2026-07-27T12:00:00Z",
                    "stats": {"downloads": 13, "views": 21},
                    "links": {"self_html": "https://zenodo.org/records/12345"},
                    "metadata": {
                        "title": "A Multimodal Benchmark Dataset",
                        "publication_date": "2026-07-27",
                        "description": "<p>Public upstream evaluation data.</p>",
                        "creators": [{"name": "Zenodo Author"}],
                    },
                }
            ]
        }
    }
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, **kwargs: payload)

    items = fetch_zenodo_records(
        {"searches": ["benchmark"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["12345"]
    assert items[0].source == "Zenodo"
    assert items[0].summary == "Public upstream evaluation data."
    assert items[0].authors == ["Zenodo Author"]
    assert items[0].artifact_urls == ["https://doi.org/10.5281/zenodo.12345"]
    assert items[0].metrics == {"downloads": 13.0, "views": 21.0}


def test_crossref_preserves_doi_metadata_and_bounds_the_query(monkeypatch):
    calls = []
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/Radar",
                    "title": ["A Publisher Benchmark"],
                    "abstract": "<jats:p>The upstream abstract.</jats:p>",
                    "published": {"date-parts": [[2026, 7, 27]]},
                    "URL": "https://doi.org/10.1000/Radar",
                    "author": [
                        {
                            "given": "Grace",
                            "family": "Evidence",
                            "affiliation": [{"name": "Radar Lab"}],
                        }
                    ],
                    "is-referenced-by-count": 3,
                }
            ]
        }
    }

    def fake_get_json(url, **kwargs):
        calls.append((url, kwargs))
        return payload

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_crossref(
        {
            "searches": ["agent benchmark"],
            "max_requests": 1,
            "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
        },
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["10.1000/radar"]
    assert items[0].source == "Crossref"
    assert items[0].url == "https://doi.org/10.1000/radar"
    assert items[0].summary == "The upstream abstract."
    assert items[0].authors == ["Grace Evidence"]
    assert items[0].organizations == ["Radar Lab"]
    assert items[0].artifact_urls == ["https://doi.org/10.1000/radar"]
    assert items[0].metrics == {"citations": 3.0}
    assert items[0].parser_version == "crossref-works/1"
    assert calls[0][0] == "https://api.crossref.org/works"
    assert calls[0][1]["params"]["query.title"] == "agent benchmark"
    assert calls[0][1]["params"]["filter"] == ("from-pub-date:2026-07-26,until-pub-date:2026-07-28")


def test_crossref_skips_dates_without_day_precision(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/year-only",
                        "title": ["An imprecisely dated benchmark"],
                        "published": {"date-parts": [[2026]]},
                    }
                ]
            }
        },
    )

    assert (
        fetch_crossref(
            {"searches": ["benchmark"]},
            datetime(2026, 7, 26, tzinfo=UTC),
            10,
        )
        == []
    )


def _openaire_row(product_id="openaire____::radar99001", **fields):
    """One OpenAIRE Graph v3 research product as `/research-products` returns it."""
    row = {
        "id": product_id,
        "type": "dataset",
        "mainTitle": "A Federated Benchmark Dataset",
        "description": "<p>The upstream abstract.</p>",
        "publicationDate": "2026-07-27",
        "publisher": "Radar Repository",
        "dateOfCollection": "2026-08-30T00:00:00Z",
        "authors": [
            {"fullName": "Grace Evidence", "rank": 1},
            {"name": "Ada", "surname": "Radar", "rank": 2},
        ],
        "pids": [
            {"scheme": "handle", "value": "11245/1.99001"},
            {"scheme": "doi", "value": "10.5281/ZENODO.99001"},
        ],
        "instances": [{"type": "fulltext", "urls": ["https://repository.example/records/99001"]}],
        "codeRepositoryUrl": "https://github.com/example/benchmark",
        "organizations": [{"legalName": "Radar Lab", "acronym": "RL"}],
        "indicators": {
            "citationImpact": {"citationCount": 3},
            "usageCounts": {"downloads": 13, "views": 21},
        },
    }
    row.update(fields)
    return row


def _openaire_rows_payload(*rows):
    return {
        "header": {"numFound": len(rows), "pageSize": 50, "nextCursor": None},
        "results": list(rows),
    }


def _openaire_payload(**fields):
    return _openaire_rows_payload(_openaire_row(**fields))


def test_openaire_preserves_upstream_metadata_and_bounds_the_query(monkeypatch):
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append((url, kwargs))
        return _openaire_payload()

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_openaire(
        {
            "searches": ["agent benchmark"],
            "max_requests": 1,
            "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
        },
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["openaire____::radar99001"]
    item = items[0]
    assert item.source == "OpenAIRE"
    # The DOI is the record's address, so the same artifact collected from
    # Crossref or Zenodo merges with it instead of being published a second
    # time.
    assert item.url == "https://doi.org/10.5281/zenodo.99001"
    assert item.title == "A Federated Benchmark Dataset"
    assert item.summary == "The upstream abstract."
    assert item.authors == ["Grace Evidence", "Ada Radar"]
    assert item.organizations == ["Radar Lab"]
    assert item.artifact_urls == [
        "https://doi.org/10.5281/zenodo.99001",
        "https://repository.example/records/99001",
        "https://github.com/example/benchmark",
    ]
    assert item.metrics == {"citations": 3.0, "downloads": 13.0, "views": 21.0}
    assert item.published_at == datetime(2026, 7, 27, tzinfo=UTC)
    # The window key and the activity key are the same field. `dateOfCollection`
    # sits in the row a month later and must not become the record's date, or a
    # simulated backfill would place the product on a day the window rejects.
    assert item.updated_at == datetime(2026, 7, 27, tzinfo=UTC)
    assert item.raw["dateOfCollection"] == "2026-08-30T00:00:00Z"
    assert item.event_kind == "released"
    assert item.parser_version == "openaire-graph-v3/1"
    assert calls[0][0] == "https://api.openaire.eu/graph/v3/research-products"
    assert calls[0][1]["params"] == {
        "mainTitle": '"agent benchmark"',
        "fromPublicationDate": "2026-07-26",
        "toPublicationDate": "2026-07-28",
        "sortBy": "publicationDate DESC",
        "pageSize": 10,
    }


def test_openaire_skips_products_without_a_publication_date(monkeypatch):
    # `dateOfCollection` says when OpenAIRE indexed the product, not when it
    # appeared, so it cannot stand in for a missing publication date.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(publicationDate=None),
    )

    assert fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


def test_openaire_enforces_the_window_on_the_parsed_record(monkeypatch):
    # The server-side range is a request, not a guarantee: a row published
    # before `since` that the API returns anyway must not enter the feed.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(publicationDate="2026-07-25"),
    )

    assert fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


def test_openaire_rejects_future_dated_products_and_counts_them(monkeypatch):
    # Counting the rejection matters as much as dropping it: run_pipeline adds
    # `_future_rejections` back into the fetched total, so a silent drop makes
    # the day's selection funnel stop adding up.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(publicationDate="2026-07-30"),
    )
    config = {"searches": ["benchmark"], "_collection_now": datetime(2026, 7, 28, tzinfo=UTC)}

    assert fetch_openaire(config, datetime(2026, 7, 26, tzinfo=UTC), 10) == []
    assert config["_future_rejections"] == 1


def test_openaire_skips_a_product_that_names_no_openable_location(monkeypatch):
    # An OpenAIRE id does not resolve anywhere a reader can check the claim, so
    # a product with neither a DOI nor an instance URL has no citable address
    # and is dropped rather than published pointing at nothing.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_rows_payload(
            _openaire_row(
                product_id="openaire____::unlocatable",
                pids=[{"scheme": "handle", "value": "11245/1.1"}],
                instances=[],
                codeRepositoryUrl=None,
            ),
            _openaire_row(product_id="openaire____::locatable"),
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["openaire____::locatable"]


def test_openaire_falls_back_to_an_instance_url_when_no_doi_is_recorded(monkeypatch):
    # Institutional-repository deposits are the products this source exists to
    # reach and many carry no DOI, so requiring one would drop exactly the
    # records the other DOI connectors already cover.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(
            pids=[{"scheme": "handle", "value": "11245/1.99001"}]
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].url == "https://repository.example/records/99001"
    assert items[0].artifact_urls == [
        "https://repository.example/records/99001",
        "https://github.com/example/benchmark",
    ]


def test_openaire_reads_author_names_without_reordering_them(monkeypatch):
    # OpenAIRE aggregates sources that disagree about whether `fullName` reads
    # "Family, Given" or "Given Family", so a rule that reordered it would
    # rewrite one of them into a name that appears in no source document.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(
            authors=[
                {"fullName": "Evidence, Grace"},
                {"name": "Ada", "surname": "Radar"},
                {"surname": "Mononym"},
                {"rank": 4},
            ]
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].authors == ["Evidence, Grace", "Ada Radar", "Mononym"]


def test_openaire_reads_organizations_only_where_one_is_named(monkeypatch):
    # A v3 relation is a flat object carrying `legalName` and `acronym`; the
    # short name is not `legalShortName`, which belongs to the organizations
    # entity. An entry naming neither field contributes nothing rather than a
    # name assembled out of whatever other keys it carries.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(
            organizations=[
                {
                    "legalName": "Radar Lab",
                    "acronym": "RL",
                    "id": "openorgs____::radar",
                    "pids": [{"scheme": "ROR", "value": "https://ror.org/example"}],
                },
                {"acronym": "OnlyAcronym"},
                {"id": "openorgs____::unnamed", "relationType": "hasAuthorInstitution"},
            ]
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].organizations == ["Radar Lab", "OnlyAcronym"]


def test_openaire_keeps_a_product_that_carries_no_organization_relation(monkeypatch):
    # The relation is absent from most products. Reading it as a hard field
    # would fail the whole source on the ordinary case.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(organizations=None),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].organizations == []


def test_openaire_skips_rows_that_carry_no_id_or_no_title(monkeypatch):
    # A connector that let an untitled row through once aborted an entire daily
    # collection, losing every other source's evidence with it. A row with no
    # id has nothing stable to dedupe or cite it by.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_rows_payload(
            _openaire_row(product_id="", pids=[{"scheme": "doi", "value": "10.1000/no-id"}]),
            _openaire_row(product_id="openaire____::untitled", mainTitle=None, title=None),
            _openaire_row(product_id="openaire____::blank", mainTitle="   ", title=None),
            _openaire_row(product_id="openaire____::kept"),
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["openaire____::kept"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"authors": "wrong"}, "authors"),
        ({"description": ["not", "text"]}, "description"),
        ({"mainTitle": ["not", "text"]}, "mainTitle"),
        ({"mainTitle": None, "title": {"value": "not text"}}, "mainTitle"),
        ({"authors": ["a bare string"]}, "authors"),
        ({"pids": {"scheme": "doi"}}, "pids"),
        ({"instances": "wrong"}, "instances"),
        ({"instances": [{"urls": "not-an-array"}]}, "instance urls"),
        ({"organizations": "wrong"}, "organizations"),
        ({"indicators": "wrong"}, "indicators"),
        ({"indicators": {"citationImpact": "wrong"}}, "indicator groups"),
    ],
)
def test_openaire_rejects_a_malformed_row_shape(monkeypatch, fields, message):
    # These raise rather than skip, so one malformed row marks the whole source
    # failed for the day. That is deliberate: a shape this connector cannot
    # read is a parsing gap the dashboard must show, not a quietly thinner
    # record that reads exactly like a product with no authors.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(**fields),
    )

    with pytest.raises(ConnectorPayloadError, match=message):
        fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)


def test_openaire_merges_one_product_across_searches_and_returns_the_newest(monkeypatch):
    # The shipped searches overlap, so the same product arrives from several of
    # them. Keying on the OpenAIRE id is what keeps one product from being
    # published twice, and the limit applies after that merge rather than per
    # request.
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(kwargs["params"])
        if len(calls) == 1:
            return _openaire_rows_payload(
                _openaire_row(product_id="openaire____::older", publicationDate="2026-07-26"),
                _openaire_row(product_id="openaire____::newer", publicationDate="2026-07-27"),
            )
        return _openaire_rows_payload(
            _openaire_row(product_id="openaire____::older", publicationDate="2026-07-26")
        )

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_openaire(
        {"searches": ["first search", "second search"], "max_requests": 2},
        datetime(2026, 7, 26, tzinfo=UTC),
        3,
    )

    # Three rows arrive naming two products. The limit is deliberately larger
    # than the answer: at two, a connector that never merged would truncate to
    # the same list and this assertion would hold without checking anything.
    assert [item.source_id for item in items] == [
        "openaire____::newer",
        "openaire____::older",
    ]
    assert [params["mainTitle"] for params in calls] == ['"first search"', '"second search"']


def test_openaire_truncates_to_the_per_source_limit(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_rows_payload(
            _openaire_row(product_id="openaire____::older", publicationDate="2026-07-26"),
            _openaire_row(product_id="openaire____::newer", publicationDate="2026-07-27"),
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 1)

    assert [item.source_id for item in items] == ["openaire____::newer"]


def test_openaire_never_asks_for_a_page_the_api_would_reject(monkeypatch):
    # Graph v3 rejects a pageSize above 100 outright rather than truncating it,
    # so a generous per-source limit must not turn every request into a 400.
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(kwargs["params"])
        return _openaire_rows_payload()

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    fetch_openaire(
        {"searches": ["benchmark"], "page_size": 500}, datetime(2026, 7, 26, tzinfo=UTC), 300
    )
    # A zero per-source limit must not ask for a page of zero, which v3 also
    # rejects as out of range.
    fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 0)

    assert [params["pageSize"] for params in calls] == [100, 1]


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("LLM benchmark", '"LLM benchmark"'),
        ("benchmark", "benchmark"),
        ("evaluation (agents)", '"evaluation (agents)"'),
        ('"a" OR "b"', '"a" OR "b"'),
        ("(x OR y)", "(x OR y)"),
        ('bench "gold" set', '"bench \\"gold\\" set"'),
    ],
)
def test_openaire_quotes_a_filter_value_the_api_would_otherwise_reject(
    monkeypatch, search, expected
):
    # Graph v3 answers a filter value holding a space, parentheses or a bare
    # logical operator with HTTP 400 unless it is double-quoted. Every phrase
    # this project ships contains a space, so an unquoted value would fail the
    # source on every request rather than search for anything. A value that is
    # already quoted or parenthesised is left alone so an inline expression
    # survives intact.
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(kwargs["params"])
        return _openaire_rows_payload()

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    fetch_openaire({"searches": [search]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert calls[0]["mainTitle"] == expected
    # The sort is a field expression, not a filter value; quoting it is itself
    # rejected, so it must stay bare even though it contains a space.
    assert calls[0]["sortBy"] == "publicationDate DESC"


def test_openaire_treats_a_null_result_page_as_empty(monkeypatch):
    # v3 sends `results: null` for a page that matched nothing. Failing the
    # payload would report the source as broken for the day on the strength of
    # an ordinary empty result, which is the one thing source health must be
    # able to tell apart from a real outage.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {"header": {"numFound": 0}, "results": None},
    )

    assert fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


def test_openaire_rejects_a_results_page_that_is_not_a_list_of_objects(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {"header": {}, "results": ["a bare string"]},
    )

    with pytest.raises(ConnectorPayloadError, match="results"):
        fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)


@pytest.mark.parametrize(
    "deposited",
    [
        "10.5281/zenodo.99001",
        "https://doi.org/10.5281/zenodo.99001",
        "http://dx.doi.org/10.5281/zenodo.99001",
        "doi:10.5281/zenodo.99001",
        "10.5281/ZENODO.99001",
    ],
)
def test_openaire_reduces_a_deposited_doi_to_its_bare_name(monkeypatch, deposited):
    # Repositories deposit the identifier bare, as a link and as a `doi:` URI.
    # Passing a link through would build `https://doi.org/https://doi.org/...`,
    # which resolves nowhere and shares no identity with the Crossref or Zenodo
    # copy of the same artifact, so the record would be counted twice.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(pids=[{"scheme": "doi", "value": deposited}]),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].url == "https://doi.org/10.5281/zenodo.99001"


def test_openaire_ignores_an_identifier_that_does_not_name_a_doi(monkeypatch):
    # Every DOI begins `10.`. Building doi.org/<anything else> would invent an
    # address for a record rather than report the one it was given.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(pids=[{"scheme": "doi", "value": "not-a-doi"}]),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].url == "https://repository.example/records/99001"


def test_openaire_keeps_a_product_whose_only_location_is_its_repository(monkeypatch):
    # Software is one of the four product types this source exists to reach and
    # a repository link is something a reader can open, so requiring a DOI or a
    # repository-hosted instance would drop exactly those records.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(type="software", pids=[], instances=[]),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].url == "https://github.com/example/benchmark"
    assert items[0].artifact_urls == ["https://github.com/example/benchmark"]


@pytest.mark.parametrize("deposited", ["N/A", "git@github.com:example/benchmark.git", "  "])
def test_openaire_drops_a_repository_value_that_is_not_an_openable_link(monkeypatch, deposited):
    # The daily digest renders every entry in `artifact_urls` as a link, so a
    # placeholder or an ssh remote would ship a link that goes nowhere.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(codeRepositoryUrl=deposited),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].artifact_urls == [
        "https://doi.org/10.5281/zenodo.99001",
        "https://repository.example/records/99001",
    ]


def test_openaire_skips_an_instance_location_that_cannot_be_opened(monkeypatch):
    # A handle or ftp locator is not something a reader can follow, and taking
    # one as the record's URL would also cost the record its DOI identity in
    # dedupe, so the artifact would be counted twice.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(
            pids=[],
            instances=[{"urls": ["hdl:11245/1.99001", "ftp://repository.example/99001"]}],
            codeRepositoryUrl=None,
        ),
    )

    assert fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


def test_openaire_names_each_organization_once(monkeypatch):
    # A product commonly carries one relation per author, so a lab with three
    # authors on the paper would otherwise be attributed three times.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_payload(
            organizations=[
                {"legalName": "Radar Lab"},
                {"legalName": "Radar Lab"},
                {"acronym": "RL"},
            ]
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items[0].organizations == ["Radar Lab", "RL"]


def test_openaire_stops_at_the_configured_request_budget(monkeypatch):
    # An anonymous caller gets 60 requests an hour. Without this bound, adding
    # search phrases silently multiplies the daily run's request count until
    # the source starts being rate-limited part-way through a run.
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(kwargs["params"]["mainTitle"])
        return _openaire_rows_payload()

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    fetch_openaire(
        {"searches": ["one", "two", "three", "four"], "max_requests": 2},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert calls == ["one", "two"]


def test_openaire_preserves_a_product_that_carries_almost_nothing(monkeypatch):
    # An absent public counter is a real zero rather than a missing metric.
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _openaire_rows_payload(
            {
                "id": "openaire____::sparse",
                "mainTitle": "A Sparse Research Product",
                "publicationDate": "2026-07-27",
                "pids": [{"scheme": "doi", "value": "10.1000/sparse"}],
            }
        ),
    )

    items = fetch_openaire({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    item = items[0]
    assert item.url == "https://doi.org/10.1000/sparse"
    assert item.artifact_urls == ["https://doi.org/10.1000/sparse"]
    assert item.metrics == {"citations": 0.0, "downloads": 0.0, "views": 0.0}
    assert item.authors == []
    assert item.organizations == []
    assert item.summary == ""


def test_openreview_success_uses_only_upstream_abstract(monkeypatch):
    timestamp = int(datetime(2026, 7, 27, 12, tzinfo=UTC).timestamp() * 1000)

    class MockNote:
        def __init__(self, data):
            self.id = data["id"]
            self.forum = data["forum"]
            self.cdate = data["cdate"]
            self.mdate = data["mdate"]
            self.content = data["content"]

    mock_notes = [
        MockNote(
            {
                "id": "note-revision",
                "forum": "stable-forum",
                "cdate": timestamp,
                "mdate": timestamp + 1000,
                "content": {
                    "title": {"value": "A Conference Benchmark"},
                    "abstract": {"value": "The upstream abstract."},
                    "authors": {"value": ["Ada Radar"]},
                    "code": {"value": "https://github.com/example/benchmark"},
                },
            }
        )
    ]

    class MockClient:
        def get_notes(self, invitation, limit):
            assert invitation == "ICLR.cc/2026/Conference/-/Submission"
            return mock_notes

    import openreview.api

    monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
    monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")

    items = fetch_openreview(
        {"venues": ["ICLR.cc/2026/Conference"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["stable-forum"]
    assert items[0].summary == "The upstream abstract."
    assert items[0].authors == ["Ada Radar"]
    assert items[0].parser_version == "openreview-api-v2/1"
    assert items[0].raw["forum"] == "stable-forum"


def test_openreview_isolates_one_failed_venue(monkeypatch):
    timestamp = int(datetime(2026, 7, 27, 12, tzinfo=UTC).timestamp() * 1000)

    class MockNote:
        id = "healthy-note"
        forum = "healthy-forum"
        cdate = timestamp
        mdate = timestamp
        content = {
            "title": {"value": "A Healthy Venue Benchmark"},
            "abstract": {"value": "A real benchmark abstract."},
        }

    import openreview.api

    class MockClient:
        def get_notes(self, invitation, limit):
            if invitation.startswith("Broken.cc"):
                raise openreview.openreview.OpenReviewException(
                    {"name": "Error", "message": "HTTP 500", "status": 500}
                )
            return [MockNote()]

    monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
    monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")
    config = {"venues": ["Broken.cc/2026/Conference", "Healthy.cc/2026/Conference"]}

    items = fetch_openreview(config, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["healthy-forum"]
    assert len(config["_source_warnings"]) == 1
    assert config["_source_warnings"][0].startswith("Broken.cc/2026/Conference:")


def test_semantic_scholar_success_preserves_external_ids(monkeypatch):
    payload = {
        "data": [
            {
                "paperId": "s2-paper",
                "externalIds": {"DOI": "10.1000/radar", "ArXiv": "2607.12345"},
                "url": "https://www.semanticscholar.org/paper/s2-paper",
                "title": "A Structured Benchmark",
                "abstract": "The upstream scholarly abstract.",
                "publicationDate": "2026-07-27",
                "authors": [{"name": "Grace Evidence"}],
                "citationCount": 2,
                "influentialCitationCount": 1,
                "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            }
        ],
        "next": None,
    }
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: payload,
    )

    items = fetch_semantic_scholar(
        {"searches": ["benchmark"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["s2-paper"]
    assert items[0].summary == "The upstream scholarly abstract."
    assert "https://doi.org/10.1000/radar" in items[0].artifact_urls
    assert "https://arxiv.org/abs/2607.12345" in items[0].artifact_urls
    assert items[0].parser_version == "semantic-scholar-graph/1"


def test_semantic_scholar_paces_an_individual_api_key(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "  key-with-newline\n")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: calls.append(kwargs) or {"data": [], "next": None},
    )
    monkeypatch.setattr("benchmark_radar.sources.time.sleep", delays.append)

    fetch_semantic_scholar(
        {"searches": ["one", "two"], "max_requests": 2},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [call["headers"] for call in calls] == [
        {"x-api-key": "key-with-newline"},
        {"x-api-key": "key-with-newline"},
    ]
    assert delays == [1.1]


def test_github_releases_success_uses_release_notes(monkeypatch):
    payload = [
        {
            "tag_name": "v2.0.0",
            "name": "Benchmark 2.0",
            "html_url": "https://github.com/example/benchmark/releases/tag/v2.0.0",
            "published_at": "2026-07-27T12:00:00Z",
            "created_at": "2026-07-27T11:00:00Z",
            "body": "The upstream release notes.",
            "draft": False,
            "prerelease": False,
            "author": {"login": "maintainer"},
            "assets": [{"download_count": 7}],
        }
    ]
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: payload,
    )

    items = fetch_github_releases(
        {"repositories": ["example/benchmark"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["example/benchmark@v2.0.0"]
    assert items[0].title == "Benchmark 2.0"
    assert items[0].summary == "The upstream release notes."
    assert items[0].metrics["downloads"] == 7
    assert items[0].parser_version == GITHUB_RELEASE_PARSER_VERSION


def test_github_release_popularity_comes_from_repository_metadata(monkeypatch):
    release = {
        "tag_name": "v2.0.0",
        "name": "Benchmark 2.0",
        "html_url": "https://github.com/example/benchmark/releases/tag/v2.0.0",
        "published_at": "2026-07-27T12:00:00Z",
        "body": "A benchmark evaluation release.",
        "draft": False,
        "prerelease": False,
        "assets": [],
    }
    repository = {"stargazers_count": 7_000, "forks_count": 420}
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        return [release] if url.endswith("/releases") else repository

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "repositories": ["example/benchmark"],
        "max_requests": 1,
        "repository_metadata_requests": 1,
    }
    radar_item = fetch_github_releases(
        config,
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )[0]

    assert calls == [
        "https://api.github.com/repos/example/benchmark/releases",
        "https://api.github.com/repos/example/benchmark",
    ]
    assert radar_item.metrics == {"downloads": 0.0, "stars": 7_000.0, "forks": 420.0}
    assert radar_item.raw == {"release": release, "repository": repository}
    score_item(
        radar_item,
        {"benchmark": ["benchmark"], "evaluation": ["evaluation"]},
        radar_item.published_at,
    )
    assert radar_item.adoption_score > 0


def test_github_release_repository_counters_are_covered_by_raw_hash(monkeypatch):
    stars = 7_000

    def fake_get_json(url, **kwargs):
        if url.endswith("/releases"):
            return [
                {
                    "tag_name": "v2.0.0",
                    "html_url": "https://github.com/example/benchmark/releases/tag/v2.0.0",
                    "published_at": "2026-07-27T12:00:00Z",
                    "assets": [],
                }
            ]
        return {"stargazers_count": stars, "forks_count": 420}

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "repositories": ["example/benchmark"],
        "max_requests": 1,
        "repository_metadata_requests": 1,
    }
    first = fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 10)[0]
    first_hash = first.to_dict()["raw_payload_hash"]

    stars += 1
    second = fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 10)[0]
    second_hash = second.to_dict()["raw_payload_hash"]

    assert first_hash != second_hash


def test_github_release_metadata_budget_cannot_reduce_release_coverage(monkeypatch):
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        repository = url.split("/repos/", 1)[1].split("/releases", 1)[0]
        if url.endswith("/releases"):
            return [
                {
                    "tag_name": "v1",
                    "html_url": f"https://github.com/{repository}/releases/tag/v1",
                    "published_at": "2026-07-27T12:00:00Z",
                    "assets": [],
                }
            ]
        raise RequestError("metadata unavailable")

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "repositories": ["org/first", "org/second"],
        "max_requests": 2,
        "repository_metadata_requests": 1,
    }

    items = fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["org/first@v1", "org/second@v1"]
    assert calls[:2] == [
        "https://api.github.com/repos/org/first/releases",
        "https://api.github.com/repos/org/second/releases",
    ]
    assert calls[2:] == ["https://api.github.com/repos/org/first"]


def test_github_releases_issue_362_title_never_degrades_to_the_bare_tag(
    monkeypatch,
):
    """A release named after its own tag must not become the record title.

    modelscope/evalscope names every release with the bare tag, so records
    read as "v1.11.0" and the reader cannot tell which project released.
    See https://github.com/ktwu01/benchmark-radar/issues/362.
    """

    def fake_get_json(url, **kwargs):
        return [
            {
                "tag_name": "v1.11.0",
                "name": "v1.11.0",
                "html_url": "https://github.com/modelscope/evalscope/releases/tag/v1.11.0",
                "published_at": "2026-07-27T12:00:00Z",
                "created_at": "2026-07-27T11:00:00Z",
                "body": None,
                "draft": False,
                "prerelease": False,
                "author": {"login": "maintainer"},
                "assets": [],
            }
        ]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_github_releases(
        {"repositories": ["modelscope/evalscope"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )
    assert [item.title for item in items] == ["modelscope/evalscope v1.11.0"]

    # The same guard covers an empty name and a v-prefix mismatch.
    assert github_release_title("modelscope/evalscope", "v1.11.0", "") == (
        "modelscope/evalscope v1.11.0"
    )
    assert github_release_title("modelscope/evalscope", "1.11.0", "v1.11.0") == (
        "modelscope/evalscope 1.11.0"
    )
    # A real release name still wins.
    assert github_release_title("example/benchmark", "v2.0.0", "Benchmark 2.0") == "Benchmark 2.0"


def test_github_releases_isolates_one_repository_failure(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "/repos/broken/benchmark/" in url:
            raise RequestError("HTTP 404 from https://api.github.com/repos/broken/benchmark")
        return []

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "repositories": ["broken/benchmark", "healthy/benchmark"],
        "max_requests": 2,
    }

    assert fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 10) == []
    assert config["_source_warnings"] == [
        "broken/benchmark: RequestError: HTTP 404 from "
        "https://api.github.com/repos/broken/benchmark"
    ]


def test_github_releases_replaces_a_page_consumed_by_future_rows(monkeypatch):
    pages = []

    def fake_get_json(url, params, **kwargs):
        pages.append(params["page"])
        published = "2050-01-01T00:00:00Z" if params["page"] == 1 else "2026-07-27T12:00:00Z"
        tag = "future" if params["page"] == 1 else "current"
        return [
            {
                "tag_name": tag,
                "html_url": f"https://github.com/example/benchmark/releases/tag/{tag}",
                "published_at": published,
            }
        ]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "repositories": ["example/benchmark"],
        "page_size": 1,
        "max_pages_per_repository": 1,
        "max_requests": 2,
        "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
    }

    items = fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 1)

    assert pages == [1, 2]
    assert [item.source_id for item in items] == ["example/benchmark@current"]
    assert config["_future_rejections"] == 1


def test_release_replacement_budget_preserves_later_repository_coverage(monkeypatch):
    calls = []

    def fake_get_json(url, params, **kwargs):
        repository = url.split("/repos/", 1)[1].split("/releases", 1)[0]
        calls.append((repository, params["page"]))
        if repository == "org/repo0" and params["page"] == 1:
            return [
                {
                    "tag_name": "future",
                    "html_url": "https://example.test/future",
                    "published_at": "2050-01-01T00:00:00Z",
                }
            ]
        if repository == "org/repo0" and params["page"] == 2:
            return [
                {
                    "tag_name": "current",
                    "html_url": "https://example.test/current",
                    "published_at": "2026-07-27T00:00:00Z",
                }
            ]
        return []

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    repositories = [f"org/repo{index}" for index in range(8)]
    config = {
        "repositories": repositories,
        "page_size": 1,
        "max_pages_per_repository": 1,
        "max_requests": 8,
        "future_replacement_requests": 1,
        "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
    }

    fetch_github_releases(config, datetime(2026, 7, 26, tzinfo=UTC), 300)

    assert ("org/repo0", 2) in calls
    assert ("org/repo7", 1) in calls
    assert len(calls) == 9


@pytest.mark.parametrize(
    ("fetcher", "config", "empty_payload"),
    [
        (fetch_openreview, {"venues": ["venue"]}, []),
        (fetch_semantic_scholar, {"searches": ["benchmark"]}, {"data": []}),
        (fetch_github_releases, {"repositories": ["example/benchmark"]}, []),
        (fetch_crossref, {"searches": ["benchmark"]}, {"message": {"items": []}}),
        (fetch_openaire, {"searches": ["benchmark"]}, {"header": {}, "results": []}),
    ],
)
def test_new_connectors_accept_empty_upstream_results(monkeypatch, fetcher, config, empty_payload):
    if fetcher is fetch_openreview:
        import openreview.api

        class MockClient:
            def get_notes(self, invitation, limit):
                return []

        monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
        monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
        monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")
    else:
        monkeypatch.setattr(
            "benchmark_radar.sources.get_json",
            lambda url, **kwargs: empty_payload,
        )

    assert fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


@pytest.mark.parametrize(
    ("fetcher", "config", "malformed_payload"),
    [
        (fetch_openreview, {"venues": ["venue"]}, "wrong"),
        (fetch_semantic_scholar, {"searches": ["benchmark"]}, {"data": "wrong"}),
        (fetch_github_releases, {"repositories": ["example/benchmark"]}, {}),
        (fetch_crossref, {"searches": ["benchmark"]}, {"message": {}}),
        (fetch_openaire, {"searches": ["benchmark"]}, {"header": {}, "results": "wrong"}),
    ],
)
def test_new_connectors_reject_malformed_payloads(monkeypatch, fetcher, config, malformed_payload):
    if fetcher is fetch_openreview:
        import openreview.api

        class MockClient:
            def get_notes(self, invitation, limit):
                raise openreview.openreview.OpenReviewException(
                    {"name": "Error", "message": "Invalid payload"}
                )

        monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
        monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
        monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")
        with pytest.raises(openreview.openreview.OpenReviewException):
            fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)
    else:
        monkeypatch.setattr(
            "benchmark_radar.sources.get_json",
            lambda url, **kwargs: malformed_payload,
        )

        with pytest.raises(ConnectorPayloadError):
            fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)


@pytest.mark.parametrize(
    ("fetcher", "config"),
    [
        (fetch_openreview, {"venues": ["venue"]}),
        (fetch_semantic_scholar, {"searches": ["benchmark"]}),
        (fetch_github_releases, {"repositories": ["example/benchmark"]}),
        (fetch_crossref, {"searches": ["benchmark"]}),
        (fetch_openaire, {"searches": ["benchmark"]}),
    ],
)
def test_new_connectors_surface_http_failures(monkeypatch, fetcher, config):
    if fetcher is fetch_openreview:
        import openreview.api

        class MockClient:
            def get_notes(self, invitation, limit):
                raise openreview.openreview.OpenReviewException(
                    {"name": "Error", "message": "HTTP 500", "status": 500}
                )

        monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
        monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
        monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")
        with pytest.raises(openreview.openreview.OpenReviewException):
            fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)
    else:

        def fail(url, **kwargs):
            raise RequestError("HTTP 500 from source after 3 attempts")

        monkeypatch.setattr("benchmark_radar.sources.get_json", fail)

        with pytest.raises(RequestError, match="HTTP 500"):
            fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)


@pytest.mark.parametrize(
    ("fetcher", "config", "payload"),
    [
        (
            fetch_openreview,
            {"venues": ["venue"]},
            {
                "id": "note",
                "forum": "forum",
                "cdate": 1785153600000,
                "mdate": 1785153600000,
                "content": {"title": {"value": "No abstract"}},
            },
        ),
        (
            fetch_semantic_scholar,
            {"searches": ["benchmark"]},
            {
                "data": [
                    {
                        "paperId": "paper",
                        "title": "No abstract",
                        "publicationDate": "2026-07-27",
                        "authors": [],
                    }
                ]
            },
        ),
        (
            fetch_github_releases,
            {"repositories": ["example/benchmark"]},
            [
                {
                    "tag_name": "v1",
                    "html_url": "https://github.com/example/benchmark/releases/tag/v1",
                    "published_at": "2026-07-27T12:00:00Z",
                    "draft": False,
                    "assets": [],
                }
            ],
        ),
        (
            fetch_crossref,
            {"searches": ["benchmark"]},
            {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/no-abstract",
                            "title": ["No abstract"],
                            "published": {"date-parts": [[2026, 7, 27]]},
                        }
                    ]
                }
            },
        ),
        (
            fetch_openaire,
            {"searches": ["benchmark"]},
            {
                "header": {"numFound": 1},
                "results": [
                    {
                        "id": "openaire____::no-abstract",
                        "mainTitle": "No abstract",
                        "publicationDate": "2026-07-27",
                        "pids": [{"scheme": "doi", "value": "10.1000/no-abstract"}],
                    }
                ],
            },
        ),
    ],
)
def test_new_connectors_never_synthesize_missing_summary(monkeypatch, fetcher, config, payload):
    if fetcher is fetch_openreview:
        import openreview.api

        class MockNote:
            def __init__(self, data):
                self.id = data["id"]
                self.forum = data["forum"]
                self.cdate = data["cdate"]
                self.mdate = data["mdate"]
                self.content = data["content"]

        class MockClient:
            def get_notes(self, invitation, limit):
                return [MockNote(payload)]

        monkeypatch.setattr(openreview.api, "OpenReviewClient", lambda **kwargs: MockClient())
        monkeypatch.setenv("OPENREVIEW_USERNAME", "test@example.com")
        monkeypatch.setenv("OPENREVIEW_PASSWORD", "testpass")
    else:
        monkeypatch.setattr(
            "benchmark_radar.sources.get_json",
            lambda url, **kwargs: payload,
        )

    items = fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items and items[0].summary == ""


def test_semantic_scholar_skips_malformed_dates(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {
            "data": [
                {
                    "paperId": "paper",
                    "title": "Malformed date benchmark",
                    "publicationDate": "not-a-date",
                    "authors": [],
                }
            ]
        },
    )

    assert (
        fetch_semantic_scholar({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)
        == []
    )


def test_semantic_scholar_date_only_values_are_utc_on_every_machine(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {
            "data": [
                {
                    "paperId": "paper",
                    "title": "Date-only benchmark",
                    "publicationDate": "2026-07-27",
                    "authors": [],
                }
            ]
        },
    )

    items = fetch_semantic_scholar(
        {"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10
    )

    assert items[0].published_at == datetime(2026, 7, 27, tzinfo=UTC)


def test_semantic_scholar_keeps_the_date_granular_lookback_boundary(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: {
            "data": [
                {
                    "paperId": "boundary-paper",
                    "title": "Boundary-day benchmark",
                    "publicationDate": "2026-07-26",
                    "authors": [],
                }
            ]
        },
    )

    items = fetch_semantic_scholar(
        {"searches": ["benchmark"]}, datetime(2026, 7, 26, 12, tzinfo=UTC), 10
    )

    assert [item.source_id for item in items] == ["boundary-paper"]


def test_github_releases_skip_malformed_dates(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: [
            {
                "tag_name": "v1",
                "html_url": "https://github.com/example/benchmark/releases/tag/v1",
                "published_at": "not-a-date",
            }
        ],
    )

    assert (
        fetch_github_releases(
            {"repositories": ["example/benchmark"]},
            datetime(2026, 7, 26, tzinfo=UTC),
            10,
        )
        == []
    )


def test_openalex_rejects_a_shapeless_payload(monkeypatch):
    # `payload.get("results", [])` made a `{}` reply indistinguishable from a
    # genuine zero-result day, so a broken response reported as healthy.
    monkeypatch.setenv("OPENALEX_API_KEY", "key")
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, params: {})

    with pytest.raises(ConnectorPayloadError):
        fetch_openalex({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)


@pytest.mark.parametrize("blank", ["", "   ", "\n", " \t\n"])
def test_openalex_requires_a_nonblank_free_api_key(monkeypatch, blank):
    monkeypatch.setenv("OPENALEX_API_KEY", blank)

    with pytest.raises(RuntimeError, match="OPENALEX_API_KEY is not configured"):
        fetch_openalex(
            {"searches": ["benchmark"]},
            datetime(2026, 7, 26, tzinfo=UTC),
            10,
        )


def test_openalex_bounds_results_to_the_run_date(monkeypatch):
    seen = []
    monkeypatch.setenv("OPENALEX_API_KEY", "  free-key\n")

    def fake_get_json(url, params):
        seen.append(params)
        return {
            "results": [
                {
                    "id": "https://openalex.org/W2050",
                    "display_name": "Erroneously future benchmark",
                    "publication_date": "2050-01-01",
                    "primary_location": {"landing_page_url": "https://example.com/future"},
                },
                {
                    "id": "https://openalex.org/WNOW",
                    "display_name": "Current benchmark",
                    "publication_date": "2026-07-28",
                    "primary_location": {"landing_page_url": "https://example.com/current"},
                },
            ]
        }

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_openalex(
        {"searches": ["benchmark"]},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
        now=datetime(2026, 7, 28, 12, tzinfo=UTC),
    )

    assert [item.title for item in items] == ["Current benchmark"]
    assert seen[0]["api_key"] == "free-key"
    assert seen[0]["filter"] == ("from_publication_date:2026-07-26,to_publication_date:2026-07-28")


def test_openalex_skips_undated_works(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "key")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "Undated benchmark",
                    "publication_date": None,
                    "primary_location": {"landing_page_url": "https://example.com/w1"},
                },
                {
                    "id": "https://openalex.org/W2",
                    "display_name": "Dated benchmark",
                    "publication_date": "2026-07-27",
                    "primary_location": {"landing_page_url": "https://example.com/w2"},
                },
            ]
        },
    )

    items = fetch_openalex({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.title for item in items] == ["Dated benchmark"]


def test_openalex_skips_untitled_works(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "key")
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: {
            "results": [
                {
                    # OpenAlex serves this for withdrawn or metadata-incomplete
                    # works. It reached the shared scorer as title=None and
                    # aborted the whole daily run in normalized_title().
                    "id": "https://openalex.org/W1",
                    "display_name": None,
                    "publication_date": "2026-07-27",
                    "primary_location": {"landing_page_url": "https://example.com/w1"},
                },
                {
                    "id": "https://openalex.org/W2",
                    "display_name": "   ",
                    "publication_date": "2026-07-27",
                    "primary_location": {"landing_page_url": "https://example.com/w2"},
                },
                {
                    "id": "https://openalex.org/W3",
                    "display_name": "Titled benchmark",
                    "publication_date": "2026-07-27",
                    "primary_location": {"landing_page_url": "https://example.com/w3"},
                },
            ]
        },
    )

    items = fetch_openalex({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert [item.title for item in items] == ["Titled benchmark"]


def test_brave_rejects_a_shapeless_payload(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "key")
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, params, headers: {})

    with pytest.raises(ConnectorPayloadError):
        fetch_brave({"searches": ["benchmark"]}, datetime(2026, 7, 26, tzinfo=UTC), 10)


def test_brave_skips_undated_results_and_does_not_read_the_clock(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "key")
    seen: list[dict] = []

    def fake_get_json(url, params, headers):
        seen.append(params)
        return {
            "web": {
                "results": [
                    {"url": "https://example.com/a", "title": "No age", "page_age": None},
                    {
                        "url": "https://example.com/b",
                        "title": "Has age",
                        "page_age": "2026-07-27T00:00:00Z",
                    },
                ]
            }
        }

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    since = datetime(2026, 7, 26, tzinfo=UTC)

    items = fetch_brave({"searches": ["benchmark"]}, since, 10)

    assert [item.title for item in items] == ["Has age"]
    # Anchored to `since`, so replaying the run rebuilds the same query.
    assert seen[0]["freshness"].startswith("2026-07-26to")


def test_huggingface_trims_the_union_to_the_limit(monkeypatch):
    # `limit` is applied per request and this fetcher issues one per kind per
    # search, so the union could reach kinds x searches x limit.
    def fake_get_json(url, params):
        return [
            {
                "id": f"{params['search']}/set-{index}",
                "lastModified": "2026-07-27T12:00:00Z",
                "createdAt": "2026-07-27T12:00:00Z",
            }
            for index in range(5)
        ]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    items = fetch_huggingface(
        {"kinds": ["datasets"], "searches": ["a", "b", "c"]},
        datetime(2026, 7, 26, tzinfo=UTC),
        4,
    )

    assert len(items) == 4


def test_huggingface_skips_undated_repositories(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: [
            {"id": "org/undated", "lastModified": None, "createdAt": None},
            {"id": "org/dated", "lastModified": "2026-07-27T12:00:00Z"},
        ],
    )

    items = fetch_huggingface(
        {"kinds": ["datasets"], "searches": ["a"]},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["org/dated"]


def test_huggingface_preserves_creation_and_update_times(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: [
            {
                "id": "org/benchmark",
                "createdAt": "2026-06-01T00:00:00Z",
                "lastModified": "2026-07-27T12:00:00Z",
            }
        ],
    )

    items = fetch_huggingface(
        {"kinds": ["datasets"], "searches": ["benchmark"]},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert items[0].published_at == datetime(2026, 6, 1, tzinfo=UTC)
    assert items[0].updated_at == datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert items[0].event_kind == "updated"


def test_huggingface_filters_future_rows_before_the_local_cap(monkeypatch):
    seen_limit = []

    def fake_get_json(url, params):
        seen_limit.append(params["limit"])
        return [
            {"id": "org/future", "lastModified": "2050-01-01T00:00:00Z"},
            {"id": "org/current", "lastModified": "2026-07-27T12:00:00Z"},
        ]

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)

    config = {
        "kinds": ["datasets"],
        "searches": ["benchmark", "evaluation"],
        "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
    }
    items = fetch_huggingface(
        config,
        datetime(2026, 7, 26, tzinfo=UTC),
        1,
    )

    assert seen_limit == [51, 51]
    assert [item.source_id for item in items] == ["org/current"]
    assert config["_future_rejections"] == 1


def test_huggingface_rejects_a_future_creation_date_even_when_modified_now(monkeypatch):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, params: [
            {
                "id": "org/future-created",
                "createdAt": "2050-01-01T00:00:00Z",
                "lastModified": "2026-07-27T12:00:00Z",
            }
        ],
    )
    config = {
        "kinds": ["datasets"],
        "searches": ["benchmark"],
        "_collection_now": datetime(2026, 7, 28, tzinfo=UTC),
    }

    assert fetch_huggingface(config, datetime(2026, 7, 26, tzinfo=UTC), 10) == []
    assert config["_future_rejections"] == 1


def _item(parser_version: str) -> RadarItem:
    return RadarItem(
        source="arXiv",
        source_id="abs/1",
        title="t",
        url="https://example.test/1",
        published_at=datetime(2026, 7, 27, tzinfo=UTC),
        parser_version=parser_version,
    )


def test_collection_method_reflects_what_actually_ran_not_a_static_guess():
    # Issue #174 follow-up: arXiv tries its Atom API and falls back to RSS
    # mid-run, so a static "arxiv -> RSS" label would misreport a run that
    # succeeded over Atom. The method must come from what the run did.
    assert collection_method("arxiv", [_item("arxiv-atom/1")]) == "API"
    assert collection_method("arxiv", [_item("arxiv-rss/1")]) == "RSS"


def test_collection_method_falls_back_to_a_static_default_without_items():
    # An empty-but-healthy fetch, or a failure before any item was parsed,
    # leaves nothing to inspect; fall back to the connector's usual method.
    assert collection_method("arxiv", []) == "RSS"
    assert collection_method("brave", []) == "API"
    assert collection_method("openaire", []) == "API"
