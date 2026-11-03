from datetime import UTC, datetime, timedelta

from benchmark_radar import rubric
from benchmark_radar.models import RadarItem
from benchmark_radar.pipeline import score_item

TAXONOMY = {
    "benchmark": ["benchmark", "leaderboard"],
    "evaluation": ["evaluation"],
}


def item(**overrides) -> RadarItem:
    published = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    defaults = {
        "source": "arXiv",
        "source_id": "2607.0001",
        "title": "A Benchmark and Leaderboard for Evaluation",
        "url": "https://arxiv.org/abs/2607.0001",
        "published_at": published,
        "summary": "",
    }
    return RadarItem(**{**defaults, **overrides})


def test_weights_are_a_normalized_mean_over_the_published_scale():
    assert set(rubric.WEIGHTS) == {"relevance", "evidence", "recency", "adoption"}
    assert sum(rubric.WEIGHTS.values()) == 1.0
    # Priority is presented as "x / 100". That only reads as a mean if a record
    # scoring the maximum on every component reaches exactly the maximum.
    assert sum(rubric.SCORE_MAX * weight for weight in rubric.WEIGHTS.values()) == rubric.SCORE_MAX


def test_published_rubric_describes_every_scored_component():
    reference = rubric.rubric_reference()
    keys = [component["key"] for component in reference["components"]]

    assert keys == list(rubric.WEIGHTS)
    assert reference["score_max"] == 100
    assert reference["scoring_version"] == rubric.SCORING_VERSION
    for component in reference["components"]:
        assert component["weight"] == rubric.WEIGHTS[component["key"]]
        assert component["summary"].strip()
        assert component["bands"], f"{component['key']} publishes no bands"
    assert reference["limits"]


def test_selection_policy_is_not_embedded_in_the_shared_scoring_rubric():
    reference = rubric.rubric_reference()

    assert "recommendation_score" not in reference
    assert "minimum_score" not in reference


def test_worked_example_reproduces_the_total_the_pipeline_published():
    """The dialog shows weight x component for each row and claims it sums to
    the total. If `score_item` ever weighted the components differently, that
    arithmetic would be a lie told next to the real number."""
    scored = score_item(
        item(authors=["Radar Author"], metrics={"citations": 12}),
        TAXONOMY,
        datetime(2026, 7, 28, 18, 0, tzinfo=UTC),
    )
    reference = rubric.rubric_reference()
    recomputed = sum(
        component["weight"] * getattr(scored, f"{component['key']}_score")
        for component in reference["components"]
    )

    assert round(recomputed, 2) == scored.total_score


def test_evidence_bands_match_the_credit_the_pipeline_grants():
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    baseline = score_item(item(source="Brave Search"), TAXONOMY, now)
    primary = score_item(item(source="arXiv"), TAXONOMY, now)
    registry = score_item(item(source="GitHub"), TAXONOMY, now)

    assert baseline.evidence_score == rubric.EVIDENCE_BASE
    assert primary.evidence_score == rubric.EVIDENCE_BASE + rubric.EVIDENCE_PRIMARY_CREDIT
    assert registry.evidence_score == rubric.EVIDENCE_BASE + rubric.EVIDENCE_ARTIFACT_CREDIT
    for source in (*rubric.EVIDENCE_PRIMARY_SOURCES, *rubric.EVIDENCE_ARTIFACT_SOURCES):
        credited = score_item(item(source=source), TAXONOMY, now)
        assert credited.evidence_score > baseline.evidence_score


def test_source_tiers_stay_disjoint():
    """score_item adds every tier that matches rather than taking the best one.
    A source in both tuples would earn both credits, so the published bands
    would understate the score they are supposed to explain."""
    overlap = set(rubric.EVIDENCE_PRIMARY_SOURCES) & set(rubric.EVIDENCE_ARTIFACT_SOURCES)

    assert not overlap, f"sources in two evidence tiers collect both credits: {overlap}"


def test_recency_reaches_zero_at_the_configured_lookback():
    published = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    at_publication = score_item(item(published_at=published), TAXONOMY, published)
    at_zero = score_item(
        item(published_at=published),
        TAXONOMY,
        published + timedelta(hours=72),
        lookback_hours=72,
    )
    halfway = score_item(
        item(published_at=published),
        TAXONOMY,
        published + timedelta(hours=36),
        lookback_hours=72,
    )

    assert at_publication.recency_score == rubric.SCORE_MAX
    assert at_zero.recency_score == 0.0
    assert halfway.recency_score == 50.0


def test_adoption_counts_every_metric_the_rubric_lists():
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    for metric in rubric.ADOPTION_METRIC_SATURATION:
        scored = score_item(item(metrics={metric: 999}), TAXONOMY, now)
        assert scored.adoption_score > 0, f"{metric} earned no adoption credit"


def test_no_component_can_exceed_the_published_maximum():
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    every_term = " ".join(TAXONOMY["benchmark"] + TAXONOMY["evaluation"])
    saturated = score_item(
        item(
            title=f"{every_term} benchmark leaderboard",
            authors=["A"],
            artifact_urls=["https://example.com/a"],
            metrics={metric: 10**9 for metric in rubric.ADOPTION_METRIC_SATURATION},
        ),
        TAXONOMY,
        now,
    )

    for component in rubric.WEIGHTS:
        assert getattr(saturated, f"{component}_score") <= rubric.SCORE_MAX
    assert saturated.total_score <= rubric.SCORE_MAX


def test_formula_states_the_weights_it_applies():
    formula = rubric.priority_formula()

    for component, weight in rubric.WEIGHTS.items():
        assert f"{weight:.2f} {component}" in formula


def test_downloads_and_likes_cannot_reach_the_top_of_the_adoption_scale():
    """Issue #278: a dataset's automated downloads took #2 from a 3,265-star repo.

    Under v3's uncapped max-wins rule 25,238 downloads scored 88.04 against
    87.85 for 3,265 stars. The cap has to leave the starred repository ahead
    without collapsing the dataset to zero, which is what removing downloads
    outright would have done.
    """
    dataset = item(metrics={"downloads": 25_238.0, "likes": 1.0})
    starred = item(metrics={"stars": 3_265.0})

    score_item(dataset, TAXONOMY, dataset.published_at, lookback_hours=48.0)
    score_item(starred, TAXONOMY, starred.published_at, lookback_hours=48.0)

    assert dataset.adoption_score == rubric.ADOPTION_CAPPED_METRICS["downloads"]
    assert dataset.adoption_score < starred.adoption_score
    # Not removed: a widely-downloaded dataset still outranks an unnoticed repo.
    assert dataset.adoption_score > 0


def test_the_cap_applies_per_metric_so_stars_stay_unbounded():
    """A record carrying both counters is scored on the stronger, uncapped one.

    Capping the result rather than each metric would penalize a repository for
    also publishing downloads, which is the opposite of the intent.
    """
    both = item(metrics={"downloads": 25_238.0, "stars": 3_265.0})
    stars_only = item(metrics={"stars": 3_265.0})

    score_item(both, TAXONOMY, both.published_at, lookback_hours=48.0)
    score_item(stars_only, TAXONOMY, stars_only.published_at, lookback_hours=48.0)

    assert both.adoption_score == stars_only.adoption_score
    assert both.adoption_score > rubric.ADOPTION_CAPPED_METRICS["downloads"]


def test_a_small_download_count_scores_below_the_cap():
    """The cap is a ceiling, not a floor: low counters still score low."""
    quiet = item(metrics={"downloads": 10.0})

    score_item(quiet, TAXONOMY, quiet.published_at, lookback_hours=48.0)

    assert 0 < quiet.adoption_score < rubric.ADOPTION_CAPPED_METRICS["downloads"]


def test_the_published_rubric_states_the_cap_and_the_self_exclusion():
    reference = rubric.rubric_reference()
    adoption = next(c for c in reference["components"] if c["key"] == "adoption")

    assert any("capped at 60" in band for band in adoption["bands"])
    assert any(rubric.SELF_REPOSITORY in limit for limit in reference["limits"])


def test_v3_reference_is_not_relabelled_with_v4_arithmetic():
    """Issue #32's guarantee: a past score keeps the rubric that produced it."""
    v3 = rubric.v3_rubric_reference()
    adoption = next(c for c in v3["components"] if c["key"] == "adoption")

    assert v3["scoring_version"] == 3
    assert not any("capped at" in band for band in adoption["bands"])
    assert not any(rubric.SELF_REPOSITORY in limit for limit in v3["limits"])


def test_v4_reference_is_not_relabelled_with_v5_bands_or_limits():
    current = rubric.rubric_reference()
    v4 = rubric.v4_rubric_reference()
    current_relevance = next(c for c in current["components"] if c["key"] == "relevance")
    current_recency = next(c for c in current["components"] if c["key"] == "recency")
    v4_relevance = next(c for c in v4["components"] if c["key"] == "relevance")
    v4_recency = next(c for c in v4["components"] if c["key"] == "recency")

    assert v4["scoring_version"] == 4
    assert any("title-only provenance" in band for band in current_relevance["bands"])
    assert not any("title-only provenance" in band for band in v4_relevance["bands"])
    assert any("updated events retain 50%" in band for band in current_recency["bands"])
    assert not any("updated events retain 50%" in band for band in v4_recency["bands"])
    assert "100 at release or first-discovery time" in current_recency["bands"]
    assert "100 at publication or update time" in v4_recency["bands"]
    assert all(limit in current["limits"] for limit in rubric.V5_LIMITS)
    assert all(limit not in v4["limits"] for limit in rubric.V5_LIMITS)


def test_v5_reference_is_not_relabelled_with_the_v6_supplement_rule():
    """Issue #936: August to October snapshots scored under v5 keep v5's rules."""
    current = rubric.rubric_reference()
    v5 = rubric.v5_rubric_reference()
    v4 = rubric.v4_rubric_reference()

    def relevance(reference):
        return next(c for c in reference["components"] if c["key"] == "relevance")["bands"]

    assert current["scoring_version"] == rubric.SCORING_VERSION == 6
    assert v5["scoring_version"] == 5
    assert any("paper supplement" in band for band in relevance(current))
    for frozen in (v5, v4, rubric.v3_rubric_reference(), rubric.v2_rubric_reference()):
        assert not any("paper supplement" in band for band in relevance(frozen))
        assert not any("paper supplements" in limit.lower() for limit in frozen["limits"])
    assert rubric.V6_SUPPRESSION_LIMIT in current["limits"]
    assert rubric.V5_SUPPRESSION_LIMIT in v5["limits"]
    # v5 keeps every v5 rule; only the v6 addition is removed.
    assert all(limit in v5["limits"] for limit in rubric.V5_LIMITS)
    assert len(relevance(v5)) == len(relevance(current)) - len(rubric.V6_SIGNAL_LABELS)
