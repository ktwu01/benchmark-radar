from datetime import UTC, datetime

from benchmark_radar import authors
from benchmark_radar.models import RadarItem, RadarRun
from benchmark_radar.snapshots import snapshot_for_run


def _repo(name: str, *, stars: float, categories: list[str], day: int = 4) -> RadarItem:
    return RadarItem(
        source="GitHub",
        source_id=f"{name}",
        title=name,
        url=f"https://github.com/{name}",
        published_at=datetime(2026, 8, day, tzinfo=UTC),
        categories=categories,
        summary="A repository the radar captured.",
        event_kind="released",
        metrics={"stars": stars},
    )


def _run(items, *, day: int = 4) -> RadarRun:
    return RadarRun(
        generated_at=datetime(2026, 8, day, 12, tzinfo=UTC),
        since=datetime(2026, 8, day - 1, 12, tzinfo=UTC),
        items=items,
        health=[],
        selection={"taxonomy_version": "taxonomy-v2"},
    )


def test_a_lone_evaluation_tag_does_not_make_a_repository_a_benchmark():
    # A 63k-star careers repository entered the real survey on a single
    # `evaluation` keyword match. Popularity must not launder a false positive.
    careers = _repo("santifer/career-ops", stars=63136.0, categories=["evaluation"])
    real = _repo("huggingface/datasets", stars=21821.0, categories=["dataset"])
    current = snapshot_for_run(_run([careers, real]))

    ranked = authors.popular_repositories([current])

    assert [repo["full_name"] for repo in ranked] == ["huggingface/datasets"]


def test_one_owner_cannot_crowd_out_the_seed_list():
    items = [
        _repo(f"bigorg/bench-{index}", stars=9000.0 - index, categories=["benchmark"])
        for index in range(6)
    ]
    items.append(_repo("smallorg/bench", stars=10.0, categories=["benchmark"]))
    current = snapshot_for_run(_run(items))

    ranked = authors.popular_repositories([current])
    owners = [repo["owner"] for repo in ranked]

    assert owners.count("bigorg") == 3
    assert "smallorg" in owners


def test_data_work_is_read_from_the_authors_own_words():
    # Never inferred from a repository name: an author is credited with data
    # work because they described it themselves.
    maintainer = {"bio": "Maintainer of Datasets", "company": "Hugging Face", "blog": ""}
    unrelated = {"bio": "I like bicycles", "company": "Acme", "blog": ""}

    assert authors.data_signals(maintainer) == ["dataset"]
    assert authors.data_signals(unrelated) == []


def test_data_signals_match_words_not_organization_substrings():
    profile = {"bio": "", "company": "PlanetLabs", "blog": ""}

    assert authors.data_signals(profile) == []


def test_data_signals_cover_professional_data_roles_and_products():
    profile = {
        "bio": "Senior Data Scientist building scalable data platforms",
        "company": "Acme",
        "blog": "",
    }

    assert authors.data_signals(profile) == ["data platform", "data scientist"]


def test_noreply_commit_addresses_are_never_collected(monkeypatch):
    # A noreply address identifies nobody and is pure noise in a contact file.
    monkeypatch.setattr(
        authors,
        "get_json",
        lambda *args, **kwargs: [
            {
                "author": {"login": "ghost"},
                "commit": {"author": {"email": "1234+ghost@users.noreply.github.com"}},
            },
            {
                "author": {"login": "real"},
                "commit": {"author": {"email": "real@example.test"}},
            },
        ],
    )

    assert authors.commit_emails("org/repo") == {"real": "real@example.test"}


def test_the_shareable_survey_never_carries_harvested_commit_emails(monkeypatch):
    # The report is safe to commit; the contacts are not. They must not merge.
    current = snapshot_for_run(_run([_repo("org/bench", stars=5.0, categories=["benchmark"])]))
    monkeypatch.setattr(
        authors,
        "repository_contributors",
        lambda *args, **kwargs: [{"login": "real", "contributions": 4, "type": "User"}],
    )
    monkeypatch.setattr(
        authors,
        "public_profile",
        lambda login: {
            "login": login,
            "name": "Real Person",
            "bio": "dataset work",
            "company": "Acme",
            "followers": 1,
            "profile_url": "https://github.com/real",
            "public_profile_email": "hello@example.test",
            "data_signals": ["dataset"],
            "works_on_data": True,
        },
    )
    monkeypatch.setattr(authors, "commit_emails", lambda *args, **kwargs: {"real": "r@e.test"})

    result = authors.survey([current], include_emails=True)

    assert result["contacts"] == [
        {
            "login": "real",
            "name": "Real Person",
            "company": "Acme",
            "bio": "dataset work",
            "profile_url": "https://github.com/real",
            "public_profile_email": "hello@example.test",
            "commit_email": "r@e.test",
            "data_signals": ["dataset"],
            "works_on_data": True,
            "found_in": ["org/bench"],
        }
    ]
    assert "r@e.test" not in str(result["report"])


def test_contacts_csv_contains_every_contact_and_flattens_lists():
    rendered = authors.contacts_csv(
        [
            {
                "login": "real",
                "commit_email": "r@e.test",
                "data_signals": ["data quality", "dataset"],
                "found_in": ["org/one", "org/two"],
            },
            {"login": "other", "commit_email": "o@e.test", "found_in": ["org/one"]},
        ]
    )

    assert rendered.count("\r\n") == 3
    assert "data quality; dataset" in rendered
    assert "org/one; org/two" in rendered
    assert "other" in rendered


def test_survey_keeps_observed_repository_when_corpus_prefers_linked_paper():
    repo = _repo("example/benchmark", stars=100, categories=["benchmark"])
    paper = RadarItem(
        source="arXiv",
        source_id="2608.12345",
        title="A benchmark paper",
        url="https://arxiv.org/abs/2608.12345",
        published_at=repo.published_at,
        categories=["benchmark"],
        artifact_urls=[repo.url],
        summary="A scored benchmark with an observed repository.",
    )
    current = snapshot_for_run(_run([repo, paper]))
    ranked = authors.popular_repositories([current])
    assert [row["full_name"] for row in ranked] == ["example/benchmark"]
    assert ranked[0]["stars"] == 100
    assert ranked[0]["url"] == repo.url


def test_survey_does_not_treat_unobserved_paper_links_as_repository_seeds():
    paper = RadarItem(
        source="arXiv",
        source_id="2608.12345",
        title="A benchmark paper",
        url="https://arxiv.org/abs/2608.12345",
        published_at=datetime(2026, 8, 4, tzinfo=UTC),
        categories=["benchmark"],
        artifact_urls=["https://github.com/example/unobserved"],
    )
    assert authors.popular_repositories([snapshot_for_run(_run([paper]))]) == []


def test_survey_does_not_assign_aggregate_stars_to_ambiguous_repository_aliases():
    first = _repo("one/benchmark", stars=100, categories=["benchmark"])
    second = _repo("two/benchmark", stars=50, categories=["benchmark"])
    paper = RadarItem(
        source="arXiv",
        source_id="2608.12345",
        title="A benchmark paper",
        url="https://arxiv.org/abs/2608.12345",
        published_at=first.published_at,
        categories=["benchmark"],
        artifact_urls=[first.url, second.url],
    )
    assert authors.popular_repositories([snapshot_for_run(_run([first, second, paper]))]) == []
