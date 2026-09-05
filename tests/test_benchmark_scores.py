from pathlib import Path

import pytest
import yaml

from benchmark_radar.benchmark_scores import (
    DEFAULT_SCORES_PATH,
    BenchmarkScoreError,
    build_score_progression,
    load_scores,
    score_progression,
)
from benchmark_radar.model_cards import DEFAULT_REGISTRY_PATH, load_registry


def write_scores(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "benchmark_scores.yml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def result(**overrides) -> dict:
    row = {
        "benchmark_id": "alpha",
        "instrument": "alpha",
        "protocol": "0-shot",
        "model": "Model One",
        "organization": "Org A",
        "source_id": "card_one",
        "reported_at": "2025-01-01",
        "value": 50.0,
        "read_from": "pdf_text",
    }
    row.update(overrides)
    return row


def minimal_scores(**overrides) -> dict:
    document = {
        "schema_version": 1,
        "benchmarks": [
            {
                "benchmark_id": "alpha",
                "metric": "accuracy",
                "direction": "higher_is_better",
                "unit": "percent",
            }
        ],
        "results": [result()],
    }
    document.update(overrides)
    return document


def external_source(**overrides) -> dict:
    source = {
        "id": "alpha_leaderboard",
        "title": "Alpha benchmark leaderboard",
        "publisher": "Alpha Research",
        "document_type": "benchmark_leaderboard",
        "url": "https://example.com/alpha/leaderboard",
        "benchmarks": ["alpha"],
        "retrieved_at": "2026-09-02",
    }
    source.update(overrides)
    return source


def test_load_scores_rejects_a_result_naming_an_undeclared_benchmark(tmp_path):
    # The benchmarks block is where metric, direction and unit live, so a row
    # without one would be plotted on an axis whose meaning nobody declared.
    path = write_scores(tmp_path, minimal_scores(results=[result(benchmark_id="ghost")]))
    with pytest.raises(BenchmarkScoreError, match="unknown benchmark_id 'ghost'"):
        load_scores(path)


def test_load_scores_rejects_an_unrecognized_direction(tmp_path):
    # An unrecognized direction defaulting to higher-is-better would silently
    # invert a chart for any metric where lower is the better score.
    document = minimal_scores()
    document["benchmarks"][0]["direction"] = "bigger_number_wins"
    path = write_scores(tmp_path, document)
    with pytest.raises(BenchmarkScoreError, match="direction must be one of"):
        load_scores(path)


def test_load_scores_rejects_a_percent_outside_its_own_range(tmp_path):
    # Caught here rather than on the axis: a 964 would rescale the whole plot
    # and make every real value look flat.
    path = write_scores(tmp_path, minimal_scores(results=[result(value=964.0)]))
    with pytest.raises(BenchmarkScoreError, match="outside 0-100"):
        load_scores(path)


def test_load_scores_rejects_a_non_finite_value(tmp_path):
    # Codex P2. YAML's `.nan` and `.inf` parse as floats, and NaN fails every
    # range comparison silently rather than tripping the percent check. Either
    # would reach json.dumps as the bare tokens NaN / Infinity, which are not
    # valid JSON: the browser's response.json() rejects the file and the
    # dashboard's init catch then hides every view. One value takes the site down.
    # Written as real float values so PyYAML emits the bare `.nan` / `.inf`
    # tokens: a quoted string would be caught by float() instead, which is a
    # different code path from the one under test.
    for value in (float("nan"), float("inf"), float("-inf")):
        document = minimal_scores(results=[result(value=value)])
        # An unbounded unit, so the percent range check cannot be what catches it.
        document["benchmarks"][0]["unit"] = "elo"
        path = write_scores(tmp_path, document)
        assert ".nan" in path.read_text() or ".inf" in path.read_text()
        with pytest.raises(BenchmarkScoreError, match="must be a finite number"):
            load_scores(path)


def test_the_published_payload_contains_no_non_finite_tokens():
    # The end-to-end consequence: radar.json has to be parseable by the browser.
    import json

    progression = build_score_progression(DEFAULT_SCORES_PATH, load_registry(DEFAULT_REGISTRY_PATH))
    encoded = json.dumps(progression)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded


def test_a_gain_endpoint_does_not_depend_on_a_model_name(tmp_path):
    # Codex P2. `points` is ordered by (date, organization, model), so when a date
    # carries several models the endpoint fell out lexically: renaming a model
    # could change `improvement` while every value and date stayed identical.
    # The policy is the best value on each endpoint date.
    def gain_for(late_model_name: str) -> float:
        path = write_scores(
            tmp_path,
            minimal_scores(
                results=[
                    result(model="Start", reported_at="2025-01-01", value=40.0),
                    # Two models share the closing date; the stronger one is the
                    # endpoint regardless of how either is named.
                    result(model="Zeta", reported_at="2025-02-01", value=90.0),
                    result(model=late_model_name, reported_at="2025-02-01", value=50.0),
                ]
            ),
        )
        record = score_progression(load_scores(path))["benchmarks"]["alpha"]
        return record["saturation"]["best_gain"]["improvement"]

    # "Alpha" sorts before "Zeta" and "Zzz" sorts after, so a name-ordered
    # endpoint would return two different gains here.
    assert gain_for("Alpha") == gain_for("Zzz") == 50.0


def test_load_scores_rejects_a_date_the_browser_cannot_format(tmp_path):
    # These strings reach Intl.DateTimeFormat, which throws on an unparseable
    # value and takes every view on the page down with it.
    path = write_scores(tmp_path, minimal_scores(results=[result(reported_at="20250101")]))
    with pytest.raises(BenchmarkScoreError, match="must be an ISO date"):
        load_scores(path)


def test_load_scores_rejects_one_model_measured_twice_in_one_document(tmp_path):
    # Two points at one x with no way to say which is the reading.
    path = write_scores(tmp_path, minimal_scores(results=[result(), result(value=51.0)]))
    with pytest.raises(BenchmarkScoreError, match="repeats 'Model One'"):
        load_scores(path)


def test_the_same_model_may_be_measured_under_two_protocols(tmp_path):
    # The counterpart to the check above: a document printing both a Pass@1 and
    # a Pass@1-COT figure for one model is normal, and the two are not one series.
    path = write_scores(
        tmp_path,
        minimal_scores(results=[result(), result(protocol="0-shot, chain of thought", value=61.0)]),
    )
    scores = load_scores(path)
    assert len(scores["results"]) == 2


def test_series_only_join_rows_sharing_an_instrument_and_protocol(tmp_path):
    # The join rule this dataset is built on. A differing protocol must break
    # the line rather than be absorbed into it.
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="A", reported_at="2025-01-01", value=50.0),
                result(model="B", reported_at="2025-02-01", value=60.0),
                result(
                    model="C",
                    reported_at="2025-03-01",
                    value=70.0,
                    protocol="8-shot",
                ),
            ]
        ),
    )
    record = score_progression(load_scores(path))["benchmarks"]["alpha"]
    joined = {(item["protocol"], item["point_count"]) for item in record["series"]}
    assert joined == {("0-shot", 2), ("8-shot", 1)}
    assert record["comparable_series_count"] == 1


def test_a_series_confined_to_one_date_is_not_connectable(tmp_path):
    # Five rows sharing one date are a comparison table from one document.
    # Drawing them as a progression would invent a trend from one publication.
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="A", organization="Org A", value=50.0),
                result(model="B", organization="Org B", value=60.0),
            ]
        ),
    )
    record = score_progression(load_scores(path))["benchmarks"]["alpha"]
    series = record["series"][0]
    assert series["point_count"] == 2
    assert series["dated_points"] == 1
    assert series["connectable"] is False
    assert record["comparable_series_count"] == 0


def test_best_value_respects_a_lower_is_better_direction(tmp_path):
    document = minimal_scores(
        results=[
            result(model="A", value=30.0),
            result(model="B", reported_at="2025-02-01", value=10.0),
        ]
    )
    document["benchmarks"][0]["direction"] = "lower_is_better"
    record = score_progression(load_scores(write_scores(tmp_path, document)))
    saturation = record["benchmarks"]["alpha"]["saturation"]
    assert saturation["best_value"] == 10.0
    # Headroom on an inverted metric is distance to zero, not to the bound.
    assert saturation["headroom"] == 10.0


def test_historical_best_frontier_uses_every_rendered_protocol(tmp_path):
    """Issue #312: the chart-wide frontier cannot pick one protocol subgroup."""
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="A", reported_at="2025-01-01", value=50.0),
                result(
                    model="B",
                    reported_at="2025-02-01",
                    value=90.0,
                    protocol="8-shot",
                ),
                result(model="C", reported_at="2025-03-01", value=60.0),
            ]
        ),
    )

    record = score_progression(load_scores(path))["benchmarks"]["alpha"]
    frontier = record["historical_best_frontier"]

    assert frontier["definition"] == "running_best_of_all_rendered_observations"
    assert frontier["tie_policy"] == "strict_improvement"
    assert [(point["reported_at"], point["value"]) for point in frontier["points"]] == [
        ("2025-01-01", 50.0),
        ("2025-02-01", 90.0),
    ]
    assert frontier["points"][-1]["value"] == record["saturation"]["best_value"]


def test_historical_best_frontier_collapses_dates_and_ignores_later_ties(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="Weak", reported_at="2025-01-01", value=40.0),
                result(model="Strong", reported_at="2025-01-01", value=60.0),
                result(model="Tie", reported_at="2025-02-01", value=60.0),
                result(model="Lower", reported_at="2025-03-01", value=20.0),
            ]
        ),
    )

    points = score_progression(load_scores(path))["benchmarks"]["alpha"][
        "historical_best_frontier"
    ]["points"]

    assert [(point["reported_at"], point["value"], point["model"]) for point in points] == [
        ("2025-01-01", 60.0, "Strong")
    ]


def test_historical_best_frontier_respects_lower_is_better(tmp_path):
    document = minimal_scores(
        results=[
            result(model="A", reported_at="2025-01-01", value=30.0),
            result(model="B", reported_at="2025-02-01", value=40.0),
            result(model="C", reported_at="2025-03-01", value=10.0),
        ]
    )
    document["benchmarks"][0]["direction"] = "lower_is_better"

    points = score_progression(load_scores(write_scores(tmp_path, document)))["benchmarks"][
        "alpha"
    ]["historical_best_frontier"]["points"]

    assert [point["value"] for point in points] == [30.0, 10.0]


def test_gpqa_diamond_frontier_reaches_the_visible_94_3_record():
    progression = build_score_progression(DEFAULT_SCORES_PATH, load_registry(DEFAULT_REGISTRY_PATH))
    record = progression["benchmarks"]["gpqa_diamond"]

    assert [point["value"] for point in record["historical_best_frontier"]["points"]] == [
        59.1,
        71.5,
        79.6,
        86.4,
        94.3,
    ]
    assert (
        record["historical_best_frontier"]["points"][-1]["value"]
        == record["saturation"]["best_value"]
    )


def test_every_shipped_point_is_on_or_below_its_historical_best():
    progression = build_score_progression(DEFAULT_SCORES_PATH, load_registry(DEFAULT_REGISTRY_PATH))
    for record in progression["benchmarks"].values():
        frontier = record["historical_best_frontier"]
        points = frontier["points"]
        assert points
        assert points[-1]["value"] == record["saturation"]["best_value"]

        for observation in record["observations"]:
            available = [
                point for point in points if point["reported_at"] <= observation["reported_at"]
            ]
            assert available
            historical_best = available[-1]["value"]
            if record["direction"] == "higher_is_better":
                assert observation["value"] <= historical_best
            else:
                assert observation["value"] >= historical_best


def test_headroom_is_omitted_when_the_metric_has_no_defensible_bound(tmp_path):
    # An Elo or a raw F1 has no ceiling this module is entitled to invent.
    document = minimal_scores()
    document["benchmarks"][0]["unit"] = "elo"
    record = score_progression(load_scores(write_scores(tmp_path, document)))
    saturation = record["benchmarks"]["alpha"]["saturation"]
    assert saturation["bound"] is None
    assert saturation["headroom"] is None


def test_evidence_grade_separates_a_single_vendor_run_from_a_field_wide_one(tmp_path):
    # Three dates from one publisher shows that publisher's models moving, and
    # says nothing about the field. The grade has to carry that distinction.
    (tmp_path / "single").mkdir()
    (tmp_path / "multi").mkdir()
    single = write_scores(
        tmp_path / "single",
        minimal_scores(
            results=[
                result(model="A", reported_at="2025-01-01", value=50.0),
                result(model="B", reported_at="2025-02-01", value=60.0),
                result(model="C", reported_at="2025-03-01", value=70.0),
            ]
        ),
    )
    record = score_progression(load_scores(single))["benchmarks"]["alpha"]
    assert record["evidence"]["id"] == "single_organization_trend"
    assert "Nothing about the field" in record["evidence"]["does_not_support"]

    multi = write_scores(
        tmp_path / "multi",
        minimal_scores(
            results=[
                result(model="A", organization="Org A", reported_at="2025-01-01", value=50.0),
                result(model="B", organization="Org B", reported_at="2025-02-01", value=60.0),
                result(model="C", organization="Org C", reported_at="2025-03-01", value=70.0),
            ]
        ),
    )
    record = score_progression(load_scores(multi))["benchmarks"]["alpha"]
    assert record["evidence"]["id"] == "multi_organization_trend"


def test_evidence_grade_refuses_the_word_trend_for_a_two_point_pair(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="A", reported_at="2025-01-01", value=50.0),
                result(model="B", reported_at="2025-02-01", value=60.0),
            ]
        ),
    )
    record = score_progression(load_scores(path))["benchmarks"]["alpha"]
    assert record["evidence"]["id"] == "paired_comparison"


def test_evidence_grade_labels_same_day_multi_value_leaderboards(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(source_id="card_one", model="Model One", reported_at="2026-08-25"),
                result(source_id="card_two", model="Model Two", reported_at="2026-08-25"),
            ]
        ),
    )
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [
            {"id": "card_one", "benchmarks": ["alpha"]},
            {"id": "card_two", "benchmarks": ["alpha"]},
        ],
    }
    record = score_progression(load_scores(path), registry)["benchmarks"]["alpha"]
    assert record["evidence"]["id"] == "same_day_comparison"
    assert "leaderboard snapshot" in record["evidence"]["does_not_support"]


def test_a_gain_is_only_attributed_to_a_vendor_when_the_run_has_one(tmp_path):
    # Naming a publisher on a run that crossed vendors would misattribute the
    # gain, so the field is present only when it is true.
    crossing = write_scores(
        tmp_path,
        minimal_scores(
            results=[
                result(model="A", organization="Org A", reported_at="2025-01-01", value=50.0),
                result(model="B", organization="Org B", reported_at="2025-02-01", value=70.0),
            ]
        ),
    )
    gain = score_progression(load_scores(crossing))["benchmarks"]["alpha"]["saturation"][
        "best_gain"
    ]
    assert gain["single_organization"] is False
    assert gain["organization"] is None


def test_cross_check_rejects_a_score_cited_to_a_card_that_never_reported_it(tmp_path):
    # Codex P2. Existence of the cited card is not enough: a source_id mistyped to
    # a different real card passes an existence check while attributing the score
    # to a document that never reported that benchmark. That publishes a number
    # with false provenance, which is worse than a missing one because it looks
    # checkable.
    path = write_scores(tmp_path, minimal_scores(results=[result(source_id="card_two")]))
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [
            {"id": "card_one", "benchmarks": ["alpha"]},
            {"id": "card_two", "benchmarks": ["beta"]},
        ],
    }
    with pytest.raises(BenchmarkScoreError, match="does not report"):
        score_progression(load_scores(path), registry)


def test_cross_check_accepts_a_score_cited_to_a_card_that_reports_it(tmp_path):
    path = write_scores(tmp_path, minimal_scores(results=[result(source_id="card_one")]))
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [{"id": "card_one", "benchmarks": ["alpha"]}],
    }
    assert score_progression(load_scores(path), registry)["observation_count"] == 1


def test_cross_check_accepts_a_score_cited_to_an_external_benchmark_source(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            sources=[external_source()],
            results=[result(source_id="alpha_leaderboard", read_from="html_text")],
        ),
    )
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [],
        "source_documents": [external_source()],
    }

    observation = score_progression(load_scores(path), registry)["benchmarks"]["alpha"][
        "observations"
    ][0]

    assert observation["source_title"] == "Alpha benchmark leaderboard"
    assert observation["source_url"] == "https://example.com/alpha/leaderboard"
    assert observation["source_document_type"] == "benchmark_leaderboard"


def test_cross_check_uses_registry_source_metadata_over_score_file_copy(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            sources=[external_source()],
            results=[result(source_id="alpha_leaderboard", read_from="html_text")],
        ),
    )
    registry_source = external_source()
    registry_source["title"] = "Reviewed title"
    registry_source["url"] = "https://reviewed.example/alpha"
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [],
        "source_documents": [registry_source],
    }

    observation = score_progression(load_scores(path), registry)["benchmarks"]["alpha"][
        "observations"
    ][0]

    assert observation["source_title"] == "Reviewed title"
    assert observation["source_url"] == "https://reviewed.example/alpha"


def test_cross_check_rejects_an_external_source_that_does_not_cover_the_score(tmp_path):
    path = write_scores(
        tmp_path,
        minimal_scores(
            sources=[external_source(benchmarks=["beta"])],
            results=[result(source_id="alpha_leaderboard")],
        ),
    )
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [],
        "source_documents": [external_source(benchmarks=["beta"])],
    }

    with pytest.raises(BenchmarkScoreError, match="does not report alpha"):
        score_progression(load_scores(path), registry)


def test_cross_check_rejects_a_score_citing_an_unknown_document(tmp_path):
    # Provenance is this layer's whole claim to be readable-out-of-a-document.
    # A source_id with no card is a citation to nothing.
    path = write_scores(tmp_path, minimal_scores(results=[result(source_id="nowhere")]))
    registry = {
        "benchmarks": [{"id": "alpha"}],
        "model_cards": [{"id": "card_one", "benchmarks": ["alpha"]}],
    }
    with pytest.raises(BenchmarkScoreError, match="absent from the model card registry"):
        score_progression(load_scores(path), registry)


def test_the_shipped_score_file_is_valid_and_cites_only_known_documents():
    # The guarantee that matters in production: the published dataset loads, and
    # every value in it points at a document the registry can link to.
    registry = load_registry(DEFAULT_REGISTRY_PATH)
    progression = build_score_progression(DEFAULT_SCORES_PATH, registry)

    assert progression["observation_count"] > 0
    card_ids = {str(card["id"]) for card in registry["model_cards"]}
    source_ids = {str(source["id"]) for source in registry.get("source_documents", [])}
    for record in progression["benchmarks"].values():
        for observation in record["observations"]:
            assert observation["source_id"] in card_ids | source_ids

    frontier = progression["benchmarks"]["frontier_challenge"]
    assert all(
        row["measurement_kind"] == "benchmark_publisher_run" for row in frontier["observations"]
    )
    assert all(row["reported_by"] is None for row in frontier["observations"])


def test_the_shipped_file_never_claims_a_trend_it_cannot_support():
    # Under the strict join rule this corpus yields no multi-date run of three
    # or more dates, so nothing in it may be graded as a trend. If a future
    # curation pass adds one, this test should be updated deliberately rather
    # than the grade appearing unnoticed.
    progression = build_score_progression(DEFAULT_SCORES_PATH, load_registry(DEFAULT_REGISTRY_PATH))
    for record in progression["benchmarks"].values():
        for series in record["series"]:
            if series["dated_points"] >= 3:
                assert record["evidence"]["id"].endswith("_trend")
