from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from benchmark_radar.http import RequestError
from benchmark_radar.pipeline import apply_watchlist, score_item
from benchmark_radar.requested_repositories import (
    RequestedRepositoryRegistryError,
    load_requested_github_repositories,
)
from benchmark_radar.sources import fetch_github_requested_repositories

ISSUE = "https://github.com/ktwu01/benchmark-radar/issues/555"
ROOT = Path(__file__).resolve().parents[1]


def _registry(tmp_path, rows):
    path = tmp_path / "requested.yml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "repositories": rows}), encoding="utf-8")
    return path


def _repository(full_name, *, created="2026-08-10T12:00:00Z", description=""):
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "created_at": created,
        "pushed_at": "2026-08-20T12:00:00Z",
        "description": description,
        "stargazers_count": 40,
        "forks_count": 3,
        "fork": False,
        "archived": False,
        "disabled": False,
    }


def test_committed_registry_loads():
    rows = load_requested_github_repositories(ROOT / "data/requested_github_repositories.yml")
    assert {row["full_name"] for row in rows} >= {"sunblaze-ucb/vero"}


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"full_name": "no-slash", "issue": ISSUE, "requested_at": date(2026, 11, 5)}, "owner"),
        ({"full_name": "lab/repo", "issue": "", "requested_at": date(2026, 11, 5)}, "issue"),
        ({"full_name": "lab/repo", "issue": ISSUE, "requested_at": "soon"}, "requested_at"),
    ],
)
def test_registry_rejects_untraceable_rows(tmp_path, row, message):
    with pytest.raises(RequestedRepositoryRegistryError, match=message):
        load_requested_github_repositories(_registry(tmp_path, [row]))


def test_registry_rejects_duplicates(tmp_path):
    row = {"full_name": "Lab/Repo", "issue": ISSUE, "requested_at": date(2026, 11, 5)}
    duplicate = {**row, "full_name": "lab/repo"}
    with pytest.raises(RequestedRepositoryRegistryError, match="Duplicate"):
        load_requested_github_repositories(_registry(tmp_path, [row, duplicate]))


def test_fetches_a_repository_created_long_before_the_window(tmp_path, monkeypatch):
    """The #555 case: a months-old repository with a blank description."""
    registry = _registry(
        tmp_path,
        [
            {"full_name": "sunblaze-ucb/vero", "issue": ISSUE, "requested_at": date(2026, 11, 5)},
            {"full_name": "lab/old-request", "issue": ISSUE, "requested_at": date(2026, 10, 1)},
        ],
    )
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        return _repository(url.removeprefix("https://api.github.com/repos/"))

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    items = fetch_github_requested_repositories(
        {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)},
        datetime(2026, 11, 4, tzinfo=UTC),
        10,
    )

    # Only the row whose request date falls in this run's window is fetched,
    # so a fulfilled request does not repeat in every later snapshot.
    assert calls == ["https://api.github.com/repos/sunblaze-ucb/vero"]
    [item] = items
    assert item.source == "GitHub"
    assert item.source_id == "sunblaze-ucb/vero"
    assert item.published_at == datetime(2026, 8, 10, 12, tzinfo=UTC)
    assert item.event_kind == "updated"
    # A blank upstream description stays blank; the request adds no prose.
    assert item.summary == ""
    assert item.raw["request"] == {"issue": ISSUE, "requested_at": "2026-11-05"}


def test_request_grants_discovery_not_relevance(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "sunblaze-ucb/vero", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _repository("sunblaze-ucb/vero"),
    )
    [item] = fetch_github_requested_repositories(
        {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)},
        datetime(2026, 11, 4, tzinfo=UTC),
        10,
    )
    score_item(item, {"benchmark": ["benchmark"]}, datetime(2026, 11, 6, tzinfo=UTC))
    assert item.categories == []
    assert item.relevance_score == 0
    # Eligibility comes only from the committed watchlist entry naming it.
    watchlist = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["watchlist"]
    apply_watchlist([item], watchlist)
    assert item.watchlist == "Vero"


def test_one_failed_request_does_not_drop_the_others(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [
            {"full_name": "lab/missing", "issue": ISSUE, "requested_at": date(2026, 11, 5)},
            {"full_name": "lab/present", "issue": ISSUE, "requested_at": date(2026, 11, 5)},
        ],
    )

    def fake_get_json(url, **kwargs):
        if url.endswith("lab/missing"):
            raise RequestError("HTTP 404 from https://api.github.com/repos/lab/missing")
        return _repository("lab/present")

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)}
    items = fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10)

    assert [item.source_id for item in items] == ["lab/present"]
    assert config["_source_warnings"][0].startswith("lab/missing: RequestError:")


def test_all_requests_failing_reports_the_source_unhealthy(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "lab/missing", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )

    def fake_get_json(url, **kwargs):
        raise RequestError("HTTP 404 from https://api.github.com/repos/lab/missing")

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    with pytest.raises(RequestError):
        fetch_github_requested_repositories(
            {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)},
            datetime(2026, 11, 4, tzinfo=UTC),
            10,
        )


def test_no_due_request_makes_no_call(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "lab/old", "issue": ISSUE, "requested_at": date(2026, 9, 1)}],
    )

    def fail(*args, **kwargs):
        raise AssertionError("no request is due")

    monkeypatch.setattr("benchmark_radar.sources.get_json", fail)
    assert (
        fetch_github_requested_repositories(
            {"registry_path": str(registry)}, datetime(2026, 11, 4, tzinfo=UTC), 10
        )
        == []
    )


def test_a_request_is_published_in_one_daily_run_only(tmp_path, monkeypatch):
    """The 48 h window spans two daily runs; only the first may fetch the row."""
    registry = _registry(
        tmp_path,
        [{"full_name": "lab/repo", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json", lambda url, **kwargs: _repository("lab/repo")
    )
    fetched = []
    for run in (
        datetime(2026, 11, 5, 5, tzinfo=UTC),
        datetime(2026, 11, 6, 5, tzinfo=UTC),
        datetime(2026, 11, 7, 5, tzinfo=UTC),
    ):
        items = fetch_github_requested_repositories(
            {"registry_path": str(registry), "_collection_now": run},
            run - timedelta(hours=48),
            10,
        )
        fetched.append(len(items))
    assert fetched == [0, 1, 0]


def test_archived_requested_repository_is_kept(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "lab/repo", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )
    archived = {**_repository("lab/repo"), "archived": True}
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, **kwargs: archived)
    items = fetch_github_requested_repositories(
        {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)},
        datetime(2026, 11, 4, tzinfo=UTC),
        10,
    )
    assert [item.source_id for item in items] == ["lab/repo"]


def test_renamed_repository_warns_that_the_alias_is_stale(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "old-lab/repo", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json", lambda url, **kwargs: _repository("new-lab/repo")
    )
    config = {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)}
    [item] = fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10)
    assert item.source_id == "new-lab/repo"
    assert config["_source_warnings"] == [
        "old-lab/repo: GitHub now names it new-lab/repo; update the registry row and its "
        "watchlist alias"
    ]


def test_every_due_request_is_fetched_even_past_the_item_limit(tmp_path, monkeypatch):
    """A row is due on one day only, so a cap would expire the rows past it."""
    rows = [
        {"full_name": f"lab/repo-{index}", "issue": ISSUE, "requested_at": date(2026, 11, 5)}
        for index in range(25)
    ]
    registry = _registry(tmp_path, rows)
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: _repository(url.removeprefix("https://api.github.com/repos/")),
    )
    items = fetch_github_requested_repositories(
        {
            "registry_path": str(registry),
            "max_requests": 1,
            "_collection_now": datetime(2026, 11, 6, tzinfo=UTC),
        },
        datetime(2026, 11, 4, tzinfo=UTC),
        10,
    )
    assert len(items) == 25
