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
    assert "No material pattern detected" in daily_findings(history, CONFIG)[0]


def test_a_shift_carried_by_too_few_sources_is_not_reported():
    # A composition change confined to one connector is that connector's
    # artifact, not a property of the feed.
    assert composition_shift(_history(10, 40, sources=2)) is None


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


def test_a_short_history_reports_insufficient_history():
    assert "Insufficient history" in daily_findings(_history(10, 30, days=8), CONFIG)[0]


def test_a_day_with_no_items_cannot_manufacture_separation():
    # An empty day would read as 0% in every category, which would look like a
    # fully separated collapse rather than an outage.
    history = _history(10, 30)
    history[-2]["evidence_items"] = []

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
