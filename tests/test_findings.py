from datetime import UTC, date, datetime, timedelta

from benchmark_radar.findings import (
    MINIMUM_DAY_ITEMS,
    Coverage,
    composition_shift,
    coverage_for,
    daily_findings,
)

CONFIG = {
    "sources": {
        "arxiv": {"required": True},
        "github": {"required": True},
        "brave": {},
        "openreview": {},
    }
}


def _day(
    index: int,
    *,
    total: int = 100,
    agentic: int = 10,
    sources: int = 4,
    failed: list[str] | None = None,
) -> dict:
    """One snapshot with `agentic` of `total` items spread across `sources`."""
    items = []
    for position in range(total):
        categories = ["benchmark"]
        if position < agentic:
            categories.append("agentic")
        items.append(
            {
                "source": f"source-{position % sources}",
                "source_id": f"item-{index}-{position}",
                "categories": categories,
            }
        )
    health = [{"source": "arxiv", "ok": True}, {"source": "github", "ok": True}]
    for name in failed or []:
        health = [entry for entry in health if entry["source"] != name]
        health.append({"source": name, "ok": False})
    return {
        "date": (date(2026, 7, 1) + timedelta(days=index)).isoformat(),
        "evidence_items": items,
        "ingest_health": health,
        # Real snapshots always stamp how they were measured. A day recording
        # none of these keys is incomparable by design.
        "selection": {
            "taxonomy_version": "v1",
            "max_items_per_source": 300,
            "report_limit": 300,
        },
    }


def _history(baseline_agentic: int, recent_agentic: int, *, days: int = 14, **kwargs) -> list[dict]:
    """Nine baseline days then five recent days, at two different shares."""
    return [
        _day(index, agentic=baseline_agentic if index < days - 5 else recent_agentic, **kwargs)
        for index in range(days)
    ]


def test_a_separated_persistent_shift_is_reported():
    findings = daily_findings(_history(10, 30), CONFIG)

    assert "Agentic artifacts rose to 30.0% of our captured feed" in findings[0]
    assert "against a 10.0% baseline" in findings[0]
    assert "+20.0 pp" in findings[0]
    assert "30 of 100 items carry it" in findings[1]


def test_a_one_day_spike_is_not_reported():
    # A single high day inside an otherwise flat window is noise. Reporting it
    # is the failure mode a point-in-time significance test invites.
    history = _history(10, 10)
    history[-1] = _day(13, agentic=60)

    assert composition_shift(history) is None
    findings = daily_findings(history, CONFIG)
    assert "No material pattern detected" in findings[0]
    # The reason must not overclaim: a candidate can clear separation and still
    # be rejected for materiality or breadth, so asserting that every share
    # stayed within its baseline would be false in exactly those cases.
    assert "stayed within" not in findings[0]


def test_a_shift_carried_by_one_source_is_not_reported():
    # A composition change confined to one connector is that connector's
    # artifact, not a property of the feed.
    assert composition_shift(_history(10, 40, sources=1)) is None


def test_a_shift_needs_a_majority_of_comparable_sources():
    # Two of four moving is not a majority, so the change is as consistent with
    # two connectors drifting as with the feed shifting.
    flat = {"a": 10.0, "b": 10.0, "c": 10.0, "d": 10.0}
    split = {"a": 40.0, "b": 40.0, "c": 10.0, "d": 10.0}
    history = [_skewed_day(index, share_by_source=flat) for index in range(9)]
    history += [_skewed_day(9 + index, share_by_source=split) for index in range(5)]

    assert composition_shift(history, CONFIG) is None


def _skewed_day(index: int, *, share_by_source: dict[str, float], per_source: int = 40) -> dict:
    """A day where each source carries its own share of the category."""
    items = []
    for source, share in share_by_source.items():
        matching = round(per_source * share / 100)
        for position in range(per_source):
            categories = ["benchmark"] + (["agentic"] if position < matching else [])
            items.append(
                {
                    "source": source,
                    "source_id": f"{source}-{index}-{position}",
                    "categories": categories,
                }
            )
    return {
        "date": (date(2026, 7, 1) + timedelta(days=index)).isoformat(),
        "evidence_items": items,
        "ingest_health": [{"source": "arxiv", "ok": True}, {"source": "github", "ok": True}],
        "selection": {
            "taxonomy_version": "v1",
            "max_items_per_source": 300,
            "report_limit": 300,
        },
    }


def test_a_shift_driven_by_one_source_is_rejected_despite_broad_presence():
    # The category is present on four sources throughout, so a presence-based
    # breadth check would pass it, but the entire increase comes from one
    # connector. Contribution has to be measured per source against its own
    # baseline, not merely counted.
    flat = {"a": 10.0, "b": 10.0, "c": 10.0, "d": 10.0}
    spiked = {"a": 70.0, "b": 10.0, "c": 10.0, "d": 10.0}
    history = [_skewed_day(i, share_by_source=flat) for i in range(9)]
    history += [_skewed_day(9 + i, share_by_source=spiked) for i in range(5)]

    assert composition_shift(history) is None


def test_a_shift_moving_in_several_sources_is_reported():
    flat = {"a": 10.0, "b": 10.0, "c": 10.0, "d": 10.0}
    risen = {"a": 40.0, "b": 38.0, "c": 42.0, "d": 10.0}
    history = [_skewed_day(i, share_by_source=flat) for i in range(9)]
    history += [_skewed_day(9 + i, share_by_source=risen) for i in range(5)]

    finding = composition_shift(history)

    assert finding is not None
    assert finding["sources_moved"] == 3
    assert finding["sources_comparable"] == 4


def test_a_thin_day_truncates_the_window_rather_than_being_skipped():
    # A one-item day yields 0% or 100% in every category. Skipping it and
    # comparing the days either side would describe non-adjacent days as
    # consecutive, so the run ends there instead. Two usable recent days is
    # below the persistence floor, so nothing is reported.
    history = _history(10, 30)
    history[-3] = _day(11, total=1, agentic=1)

    assert composition_shift(history) is None


def test_a_thin_day_at_the_window_edge_shortens_a_still_valid_run():
    # Truncation is not rejection: an unusable day at the far edge of the
    # baseline leaves a shorter but genuinely contiguous run that still supports
    # a claim. This is what keeps the real history usable.
    history = _history(10, 30, days=15)
    history[1] = _day(1, total=1, agentic=1)

    finding = composition_shift(history, CONFIG)

    assert finding is not None
    assert finding["recent_days"] == 5
    assert finding["baseline_days"] == 8


def test_too_few_usable_recent_days_suppresses_the_claim():
    # Dropping unusable days cannot silently shrink the window below what a
    # persistence claim needs.
    history = _history(10, 30)
    for index in (-1, -2, -3):
        history[index] = _day(14 + index, total=1, agentic=1)

    assert composition_shift(history) is None


def test_an_outage_day_truncates_the_baseline_without_disqualifying_it():
    # An outage day is measuring a different feed and must not contribute a
    # share. Truncating rather than rejecting is what keeps the real history
    # usable: it opens with four days of arXiv outage, and discarding every
    # window reaching back to them would suppress findings while they stay in
    # range.
    history = _history(10, 30, days=15)
    history[1] = _day(1, agentic=99, failed=["github"])

    finding = composition_shift(history, CONFIG)

    assert finding is not None
    assert finding["baseline_days"] == 8


def test_a_taxonomy_change_inside_the_window_suppresses_the_claim():
    # A taxonomy edit reclassifies artifacts wholesale, so a share change across
    # the boundary measures the instrument rather than the feed.
    history = _history(10, 30)
    for index, day in enumerate(history):
        day["selection"]["taxonomy_version"] = "v2" if index >= 9 else "v1"

    assert composition_shift(history) is None


def test_a_changed_per_source_cap_inside_the_window_suppresses_the_claim():
    history = _history(10, 30)
    for index, day in enumerate(history):
        day["selection"]["max_items_per_source"] = 600 if index >= 9 else 300

    assert composition_shift(history) is None


def test_an_unrecorded_measurement_setting_is_unknown_not_different():
    # Early snapshots predate these fields. Treating a missing value as its own
    # signature rejected the entire real history, where every day was in fact
    # classified by the same taxonomy.
    history = _history(10, 30)
    for index, day in enumerate(history):
        # Early real snapshots stamp the taxonomy but not the caps.
        if index < 2:
            day["selection"] = {"taxonomy_version": "v1"}

    assert composition_shift(history) is not None


def test_the_baseline_window_is_bounded():
    # An unbounded baseline lets one old extreme share block separation forever.
    # A long flat archive preceding a real shift must not suppress it.
    history = [_day(index, agentic=90) for index in range(20)]
    history += [_day(20 + index, agentic=10) for index in range(9)]
    history += [_day(29 + index, agentic=30) for index in range(5)]

    finding = composition_shift(history)

    assert finding is not None
    assert finding["baseline_days"] == 9


def test_a_small_but_separated_shift_is_not_reported():
    # Real and separated but not worth a reader's attention.
    assert composition_shift(_history(10, 13)) is None


def test_volume_growth_alone_is_not_a_finding():
    # The corpus went from 20 to 259 items a day during connector onboarding.
    # A count-based detector would call that a twelvefold change in the field.
    # Holding the share fixed while volume triples must report nothing.
    history = [_day(index, total=30, agentic=6) for index in range(9)]
    history += [_day(9 + index, total=300, agentic=60) for index in range(5)]

    assert composition_shift(history) is None


def test_a_failed_required_source_suppresses_every_claim():
    history = _history(10, 30)
    history[-1] = _day(13, agentic=30, failed=["github"])

    findings = daily_findings(history, CONFIG)

    assert "No pattern assessed" in findings[0]
    assert "required source(s) github unavailable" in findings[1]


def test_failed_optional_sources_do_not_suppress_a_claim():
    # `brave` has no API key and `openreview` has returned 403 for nine
    # consecutive runs. Gating on them would mean never publishing a finding.
    history = _history(10, 30)
    history[-1] = _day(13, agentic=30, failed=["brave", "openreview"])

    findings = daily_findings(history, CONFIG)

    assert "Agentic artifacts rose" in findings[0]
    # The claim survives, but confidence is capped and the gap is disclosed.
    assert "Moderate confidence" in findings[2]
    assert "brave, openreview unavailable" in findings[2]


def test_a_thin_day_reports_insufficient_volume():
    history = _history(10, 30)
    history[-1] = _day(13, total=MINIMUM_DAY_ITEMS - 1, agentic=10)

    assert "Insufficient volume" in daily_findings(history, CONFIG)[0]


def test_a_short_history_reports_insufficient_comparable_history():
    assert "Insufficient comparable history" in daily_findings(_history(10, 30, days=8), CONFIG)[0]


def test_a_day_with_no_items_cannot_manufacture_separation():
    # An empty day would read as 0% in every category, which would look like a
    # fully separated collapse rather than an outage. It is excluded.
    history = _history(10, 30)
    history[-2]["evidence_items"] = []

    # An empty day reads as 0% in every category, so it must never contribute a
    # share. Inside the recent window it truncates the run below the floor.
    assert composition_shift(history) is None


def test_the_reported_day_itself_is_never_dropped():
    # If today cannot be compared there is nothing to report, and the caller
    # renders the reason rather than a finding built from other days.
    history = _history(10, 30)
    history[-1] = _day(13, total=1, agentic=1)

    assert composition_shift(history) is None


def test_only_the_largest_shift_is_published():
    # Categories are multi-label and move together. Publishing every one that
    # cleared the bar would let a reader pick the most flattering.
    findings = daily_findings(_history(10, 40), CONFIG)

    assert len([line for line in findings if "of our captured feed" in line]) == 1


def test_claims_are_scoped_to_the_captured_feed():
    # The crawler is a keyword-filtered scrape of a handful of sources, not a
    # sample of the field, so no claim may generalize beyond it.
    findings = daily_findings(_history(10, 30), CONFIG)

    assert "our captured feed" in findings[0]
    assert "AI evaluation" not in " ".join(findings)


def test_coverage_separates_required_from_optional_failures():
    coverage = coverage_for(_day(1, failed=["github", "brave"]), CONFIG)

    assert coverage.failed_required == ["github"]
    assert coverage.failed_optional == ["brave"]
    assert not coverage.complete


def test_coverage_caption_states_a_complete_feed_plainly():
    assert Coverage(8, 8, [], []).caption() == "Coverage: 8/8 connectors healthy."


def test_findings_never_return_an_empty_briefing():
    # An absent briefing reads as a broken pipeline. "Nothing moved" is
    # informative and must be said out loud.
    for history in (_history(10, 10), _history(10, 30, days=6)):
        assert daily_findings(history, CONFIG)


def test_a_falling_share_is_reported_with_its_direction():
    findings = daily_findings(_history(40, 10), CONFIG)

    assert "fell to 10.0%" in findings[0]
    assert "-30.0 pp" in findings[0]


def test_real_history_reports_the_verified_agentic_shift():
    """Guard against regression on the shift measured by hand in issue #127.

    The captured feed moved from a 12.3% agentic share over nine days to 25.9%
    over the following five, fully separated, across all five sources. A robust
    z-score against the trailing window scores this at 1.54 and would reject
    it, which is why separation and persistence do the gating instead.
    """
    shares = [15.0, 12.5, 15.6, 10.0, 3.3, 11.3, 10.4, 16.0, 16.7, 24.6, 25.8, 25.7, 25.9, 27.4]
    history = [
        _day(index, total=1000, agentic=round(share * 10)) for index, share in enumerate(shares)
    ]

    finding = composition_shift(history)

    assert finding is not None
    assert finding["category"] == "agentic"
    assert finding["rising"] is True
    assert finding["recent_share"] == 25.9
    assert finding["baseline_share"] == 12.3


def test_datetime_import_is_available_for_snapshot_dates():
    # Regression guard: trimming the LLM path once removed `datetime` from
    # briefing.py while `daily_report_run` still parsed snapshot timestamps.
    from benchmark_radar.briefing import daily_report_run  # noqa: F401

    assert datetime.now(UTC).tzinfo is UTC


def test_a_contradictory_day_cannot_be_dropped_to_save_a_claim():
    # The whole point of contiguity: a day that contradicts the shift must break
    # the run rather than being skipped while the survivors are still described
    # as consecutive.
    history = _history(10, 30)
    history[-2] = _day(12, agentic=10)

    assert composition_shift(history, CONFIG) is None


def test_a_day_recording_no_measurement_settings_is_incomparable():
    # A day produced under settings nobody wrote down cannot be certified as
    # measured the same way, so admitting it silently would be the stronger
    # error than declining.
    history = _history(10, 30)
    history[-4]["selection"] = {}

    assert composition_shift(history, CONFIG) is None


def test_a_changed_report_limit_inside_the_window_suppresses_the_claim():
    # report_limit truncates the ranked selection directly, so changing it moves
    # category shares without anything happening in the feed.
    history = _history(10, 30)
    for index, day in enumerate(history):
        day["selection"]["report_limit"] = 600 if index >= 9 else 300

    assert composition_shift(history, CONFIG) is None


def test_noise_in_other_sources_cannot_certify_a_one_source_change():
    # One source moves 10% -> 70% while three drift 10% -> 11%. Counting any
    # directional change would pass the breadth gate on ~95% single-source
    # movement, which is the artifact the gate exists to reject.
    flat = {"a": 10.0, "b": 10.0, "c": 10.0, "d": 10.0}
    drifted = {"a": 70.0, "b": 11.0, "c": 11.0, "d": 11.0}
    history = [_skewed_day(index, share_by_source=flat) for index in range(9)]
    history += [_skewed_day(9 + index, share_by_source=drifted) for index in range(5)]

    assert composition_shift(history, CONFIG) is None


def test_a_required_source_with_no_health_row_is_not_counted_as_healthy():
    # A required connector that never reported is not the same as one that
    # reported success. Days recorded before a source became required must not
    # be admitted as fully covered.
    day = _day(1)
    day["ingest_health"] = [{"source": "arxiv", "ok": True}]

    coverage = coverage_for(day, CONFIG)

    assert coverage.failed_required == ["github"]
    assert not coverage.complete


def test_a_category_that_collapses_to_zero_is_still_reported():
    # A category absent from today's shares would never be evaluated if the loop
    # iterated today, silently skipping the most complete falling shift there is.
    history = _history(30, 0)

    finding = composition_shift(history, CONFIG)

    assert finding is not None
    assert finding["category"] == "agentic"
    assert finding["rising"] is False
    assert finding["recent_share"] == 0.0
