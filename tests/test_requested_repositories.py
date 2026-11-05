from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from benchmark_radar.http import RequestError
from benchmark_radar.pipeline import apply_watchlist, run_pipeline, score_item
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
            {"full_name": "lab/answered", "issue": ISSUE, "requested_at": date(2026, 10, 1)},
        ],
    )
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        return _repository(url.removeprefix("https://api.github.com/repos/"))

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    config = {
        "registry_path": str(registry),
        "_collection_now": datetime(2026, 11, 6, tzinfo=UTC),
        # A row an earlier run already answered is not fetched again.
        "_seen_state": {"lab/answered": {"resolved_at": "2026-10-02T05:00:00+00:00"}},
    }
    items = fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10)

    assert calls == ["https://api.github.com/repos/sunblaze-ucb/vero"]
    assert config["_requested_resolved"] == ["sunblaze-ucb/vero"]
    [item] = items
    assert item.source == "GitHub"
    assert item.source_id == "sunblaze-ucb/vero"
    assert item.published_at == datetime(2026, 8, 10, 12, tzinfo=UTC)
    assert item.event_kind == "updated"
    # A blank upstream description stays blank; the request adds no prose.
    assert item.summary == ""
    assert item.raw["request"] == {
        "full_name": "sunblaze-ucb/vero",
        "issue": ISSUE,
        "requested_at": "2026-11-05",
    }


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


def test_no_pending_request_makes_no_call(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "Lab/Old", "issue": ISSUE, "requested_at": date(2026, 9, 1)}],
    )

    def fail(*args, **kwargs):
        raise AssertionError("no request is pending")

    monkeypatch.setattr("benchmark_radar.sources.get_json", fail)
    config = {"registry_path": str(registry), "_seen_state": {"lab/old": {}}}
    assert fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10) == []


def _pipeline_config(registry):
    return {
        "radar": {
            "lookback_hours": 48,
            "max_items_per_source": 10,
            "report_limit": 10,
            "minimum_score": 0,
        },
        "taxonomy": {"benchmark": ["benchmark"]},
        "sources": {
            "github_requested_repositories": {"enabled": True, "registry_path": str(registry)}
        },
    }


def test_a_request_is_published_once_even_when_merged_late(tmp_path, monkeypatch):
    """Pending until a run answers it, then recorded so it never repeats."""
    registry = _registry(
        tmp_path,
        # Dated well before the first run that sees it, as for a late merge.
        [{"full_name": "lab/repo", "issue": ISSUE, "requested_at": date(2026, 10, 1)}],
    )
    responses = iter(
        [
            RequestError("HTTP 502 from https://api.github.com/repos/lab/repo"),
            _repository("lab/repo", description="A reasoning benchmark."),
        ]
    )

    def fake_get_json(url, **kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("benchmark_radar.sources.get_json", fake_get_json)
    previous = None
    published = []
    for day in (6, 7, 8):
        run = run_pipeline(
            _pipeline_config(registry),
            datetime(2026, 11, day, 5, tzinfo=UTC),
            previous_snapshot=previous,
        )
        published.append([item.source_id for item in run.items])
        previous = {"discovery_state": run.discovery_state}
    # Day 6 fails and stays pending, day 7 publishes it, day 8 makes no call.
    assert published == [[], ["lab/repo"], []]
    assert set(previous["discovery_state"]["github_requested_repositories"]) == {"lab/repo"}


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
    # Resolved under both names, so renaming the row does not requeue it.
    assert config["_requested_resolved"] == ["old-lab/repo", "new-lab/repo"]
    assert config["_source_warnings"] == [
        "old-lab/repo: GitHub now names it new-lab/repo; update the registry row and its "
        "watchlist alias"
    ]


def test_every_pending_request_is_fetched_even_past_the_item_limit(tmp_path, monkeypatch):
    """The hand-reviewed registry is the bound; no cap leaves rows behind."""
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


def test_future_dated_answer_stays_pending(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [{"full_name": "lab/repo", "issue": ISSUE, "requested_at": date(2026, 11, 5)}],
    )
    future = {**_repository("lab/repo"), "pushed_at": "2027-01-01T00:00:00Z"}
    monkeypatch.setattr("benchmark_radar.sources.get_json", lambda url, **kwargs: future)
    config = {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)}
    assert fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10) == []
    assert config.get("_requested_resolved") == []


def test_requested_fork_is_kept_and_disabled_repository_is_reported(tmp_path, monkeypatch):
    registry = _registry(
        tmp_path,
        [
            {"full_name": "lab/fork", "issue": ISSUE, "requested_at": date(2026, 11, 5)},
            {"full_name": "lab/disabled", "issue": ISSUE, "requested_at": date(2026, 11, 5)},
        ],
    )
    rows = {
        "lab/fork": {**_repository("lab/fork"), "fork": True},
        "lab/disabled": {**_repository("lab/disabled"), "disabled": True},
    }
    monkeypatch.setattr(
        "benchmark_radar.sources.get_json",
        lambda url, **kwargs: rows[url.removeprefix("https://api.github.com/repos/")],
    )
    config = {"registry_path": str(registry), "_collection_now": datetime(2026, 11, 6, tzinfo=UTC)}
    items = fetch_github_requested_repositories(config, datetime(2026, 11, 4, tzinfo=UTC), 10)
    assert [item.source_id for item in items] == ["lab/fork"]
    assert config["_source_warnings"] == [
        "lab/disabled: GitHub reports the repository disabled; nothing published"
    ]
