import pytest

from benchmark_radar.corpus import (
    CorpusError,
    build_corpus,
    exact_artifact_key,
    exact_artifact_keys,
    organizations_for_item,
    validate_corpus,
)


def item(**overrides):
    value = {
        "source": "Semantic Scholar",
        "source_id": "paper-1",
        "title": "A benchmark",
        "url": "https://www.semanticscholar.org/paper/paper-1",
        "published_at": "2026-07-28T12:00:00+00:00",
        "updated_at": None,
        "event_kind": "released",
        "categories": ["benchmark"],
        "authors": [],
        "artifact_urls": [],
        "metrics": {},
        "total_score": 50,
    }
    value.update(overrides)
    return value


def snapshot(*items):
    return {
        "date": "2026-07-28",
        "evidence_items": list(items),
    }


def test_exact_primary_identifier_wins_over_secondary_record_and_repo_links():
    record = item(
        artifact_urls=[
            "https://github.com/org/benchmark",
            "https://arxiv.org/abs/2607.12345v2",
        ]
    )

    assert exact_artifact_key(record) == "artifact:arxiv:2607.12345"


def test_arxiv_pdf_and_abstract_urls_share_one_identity():
    abstract = item(url="https://arxiv.org/abs/2608.12345")
    pdf = item(url="https://arxiv.org/pdf/2608.12345v2.pdf")

    assert exact_artifact_key(abstract) == "artifact:arxiv:2608.12345"
    assert exact_artifact_key(pdf) == exact_artifact_key(abstract)


def test_every_identifier_of_the_same_kind_is_preserved():
    record = item(
        artifact_urls=[
            "https://github.com/org/benchmark",
            "https://github.com/org/evaluator",
        ]
    )

    assert exact_artifact_keys(record) == [
        "artifact:github:org/benchmark",
        "artifact:github:org/evaluator",
    ]


def test_equal_titles_do_not_merge_without_an_exact_identifier():
    first = item(url="https://example.com/releases/one")
    second = item(source_id="paper-2", url="https://example.net/releases/two")

    assert exact_artifact_key(first) != exact_artifact_key(second)


def test_repository_owner_is_a_structured_organization():
    assert organizations_for_item(item(source="GitHub Release", source_id="OpenAI/evals@v1")) == [
        "OpenAI"
    ]


def test_cross_source_observations_cluster_under_one_entity():
    scholarly = item(
        source="Semantic Scholar",
        artifact_urls=["https://arxiv.org/abs/2607.12345"],
    )
    primary = item(
        source="arXiv",
        source_id="2607.12345",
        url="https://arxiv.org/abs/2607.12345",
    )

    corpus = build_corpus([snapshot(scholarly, primary)])
    artifacts = [entity for entity in corpus["entities"] if entity["type"] == "artifact"]

    assert len(artifacts) == 1
    assert artifacts[0]["observation_count"] == 2
    assert artifacts[0]["sources"] == ["Semantic Scholar", "arXiv"]


def test_multi_identifier_aliases_cluster_across_snapshots():
    first = item(
        artifact_urls=[
            "https://doi.org/10.1000/radar",
            "https://arxiv.org/abs/2607.12345",
        ]
    )
    second = item(
        source="OpenAlex",
        source_id="W1",
        url="https://openalex.org/W1",
        artifact_urls=["https://arxiv.org/abs/2607.12345"],
    )

    corpus = build_corpus(
        [
            {"date": "2026-07-27", "evidence_items": [first]},
            {"date": "2026-07-28", "evidence_items": [second]},
        ]
    )
    artifacts = [entity for entity in corpus["entities"] if entity["type"] == "artifact"]

    assert len(artifacts) == 1
    assert artifacts[0]["id"] == "artifact:doi:10.1000/radar"
    assert artifacts[0]["observation_count"] == 2
    assert artifacts[0]["sources"] == ["OpenAlex", "Semantic Scholar"]


def test_validation_rejects_edges_to_unknown_entities():
    corpus = build_corpus([snapshot(item())])
    corpus["edges"][0]["target"] = "artifact:missing"

    with pytest.raises(CorpusError, match="unknown entity"):
        validate_corpus(corpus)


@pytest.mark.parametrize(
    "first,second",
    [
        (
            item(
                source="OpenReview",
                source_id="AbC123",
                url="https://openreview.net/forum?id=AbC123",
            ),
            item(
                source="OpenReview",
                source_id="abc123",
                url="https://openreview.net/forum?id=abc123",
            ),
        ),
        (
            item(source="OpenReview", source_id="AbC123", url="https://openreview.net/pdf/AbC123"),
            item(source="OpenReview", source_id="abc123", url="https://openreview.net/pdf/abc123"),
        ),
        (
            item(url="https://example.com/Benchmark?version=A"),
            item(source_id="paper-2", url="https://example.com/benchmark?version=a"),
        ),
    ],
)
def test_corpus_keeps_case_sensitive_identifiers_distinct(first, second):
    corpus = build_corpus([snapshot(first, second)])
    artifacts = [entity for entity in corpus["entities"] if entity["type"] == "artifact"]
    assert len(artifacts) == 2
    assert all(entity["observation_count"] == 1 for entity in artifacts)


def test_generic_url_hostname_is_case_insensitive():
    first = item(url="https://EXAMPLE.com/Benchmark?version=A")
    second = item(source_id="paper-2", url="https://example.COM/Benchmark?version=A")
    corpus = build_corpus([snapshot(first, second)])
    artifacts = [entity for entity in corpus["entities"] if entity["type"] == "artifact"]
    assert len(artifacts) == 1
    assert artifacts[0]["observation_count"] == 2
