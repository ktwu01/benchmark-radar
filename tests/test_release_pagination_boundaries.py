from datetime import UTC, datetime

from benchmark_radar.sources import fetch_github_releases


def test_release_pages_keep_their_boundaries_as_the_global_limit_fills(monkeypatch):
    # GitHub's numbered pages are relative to per_page. Shrinking it after
    # page one repeats older rows and consumes the request cap before v5.
    rows = [
        {
            "tag_name": f"v{i}",
            "html_url": f"https://github.com/example/benchmark/releases/tag/v{i}",
            "published_at": "2026-09-29T12:00:00Z",
        }
        for i in range(1, 7)
    ]
    requests = []

    def numbered_pages(url, *, params, **kwargs):
        requests.append(params.copy())
        size = params["per_page"]
        start = (params["page"] - 1) * size
        return rows[start : start + size]

    monkeypatch.setattr("benchmark_radar.sources.get_json", numbered_pages)
    items = fetch_github_releases(
        {
            "repositories": ["example/benchmark"],
            "page_size": 3,
            "max_pages_per_repository": 2,
            "max_requests": 2,
            "repository_metadata_requests": 0,
        },
        datetime(2026, 9, 28, tzinfo=UTC),
        5,
    )
    assert {item.source_id for item in items} == {f"example/benchmark@v{i}" for i in range(1, 6)}
    assert requests == [{"per_page": 3, "page": 1}, {"per_page": 3, "page": 2}]
