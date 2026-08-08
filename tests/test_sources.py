from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

from benchmark_radar.http import RequestError
from benchmark_radar.sources import (
    ConnectorPayloadError,
    fetch_arxiv,
    fetch_brave,
    fetch_github,
    fetch_github_releases,
    fetch_huggingface,
    fetch_openalex,
    fetch_openreview,
    fetch_semantic_scholar,
)

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


def test_openreview_success_uses_only_upstream_abstract(monkeypatch):
    timestamp = int(datetime(2026, 7, 27, 12, tzinfo=UTC).timestamp() * 1000)
    payload = {
        "notes": [
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
        ]
    }
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: payload,
    )

    items = fetch_openreview(
        {"venues": ["ICLR.cc/2026/Conference"], "max_requests": 1},
        datetime(2026, 7, 26, tzinfo=UTC),
        10,
    )

    assert [item.source_id for item in items] == ["stable-forum"]
    assert items[0].summary == "The upstream abstract."
    assert items[0].authors == ["Ada Radar"]
    assert items[0].parser_version == "openreview-api-v2/1"
    assert items[0].raw is payload["notes"][0]


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
    assert items[0].summary == "The upstream release notes."
    assert items[0].metrics["downloads"] == 7
    assert items[0].parser_version == "github-releases/1"


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
        (fetch_openreview, {"venues": ["venue"]}, {"notes": []}),
        (fetch_semantic_scholar, {"searches": ["benchmark"]}, {"data": []}),
        (fetch_github_releases, {"repositories": ["example/benchmark"]}, []),
    ],
)
def test_new_connectors_accept_empty_upstream_results(monkeypatch, fetcher, config, empty_payload):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: empty_payload,
    )

    assert fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10) == []


@pytest.mark.parametrize(
    ("fetcher", "config", "malformed_payload"),
    [
        (fetch_openreview, {"venues": ["venue"]}, {"notes": "wrong"}),
        (fetch_semantic_scholar, {"searches": ["benchmark"]}, {"data": "wrong"}),
        (fetch_github_releases, {"repositories": ["example/benchmark"]}, {}),
    ],
)
def test_new_connectors_reject_malformed_payloads(monkeypatch, fetcher, config, malformed_payload):
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
    ],
)
def test_new_connectors_surface_http_failures(monkeypatch, fetcher, config):
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
                "notes": [
                    {
                        "id": "note",
                        "forum": "forum",
                        "cdate": 1785153600000,
                        "mdate": 1785153600000,
                        "content": {"title": {"value": "No abstract"}},
                    }
                ]
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
    ],
)
def test_new_connectors_never_synthesize_missing_summary(monkeypatch, fetcher, config, payload):
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: payload,
    )

    items = fetcher(config, datetime(2026, 7, 26, tzinfo=UTC), 10)

    assert items and items[0].summary == ""


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
