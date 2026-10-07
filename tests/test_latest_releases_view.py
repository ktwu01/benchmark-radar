"""The leaderboard opens on the latest releases (issue #530).

The ranking engine and its payload landed for #530 before the page read them,
so `/leaderboard/` kept opening on the cumulative model-card adoption view.
Each test names the failure it protects against.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from benchmark_radar.app_pages import load_view_seo
from benchmark_radar.app_seeds import _latest_releases_seed

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FIXTURE = ROOT / "tests" / "fixtures" / "latest_releases.json"
LIST_ANCHOR = (
    '<ol class="leaderboard-top-list latest-releases-list" id="latest-releases-list"></ol>'
)
WINDOW_ANCHOR = '<span class="latest-releases-window" id="latest-releases-window">· 30 days</span>'
INFO_ANCHOR = '<span id="latest-releases-info"></span>'
EMPTY_ANCHOR = (
    '<p class="empty-state latest-releases-empty" id="latest-releases-empty" '
    'aria-live="polite" hidden></p>'
)
NOTE_ANCHOR = '<p class="section-note" id="latest-releases-note" aria-live="polite"></p>'


def _inner(markup: str) -> str:
    """The content between a seeded container's opening and closing tags."""
    return markup[markup.index(">") + 1 : markup.rindex("</")]


def _render(payload: dict) -> dict:
    """What the real renderer draws for the payload, on a minimal DOM (see the harness)."""
    node = shutil.which("node")
    assert node, "Node.js is required for the site behavior tests"
    with open(FIXTURE.with_name("latest_releases_under_test.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    try:
        result = subprocess.run(
            [node, "tests/latest_releases_render_harness.mjs", fh.name],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    finally:
        Path(fh.name).unlink(missing_ok=True)
    return json.loads(result.stdout)


def _payload(entries: list[dict] | None = None, default_window: str = "30d") -> dict:
    window = {
        "window_start": "2026-08-11T09:00:00+00:00",
        "window_end": "2026-09-10T09:00:00+00:00",
        "window_days": 30,
        "ranked_count": 1,
        "total_cohort_count": 2,
        "signal_coverage": 0.5,
        "entries": entries
        if entries is not None
        else [
            {
                "canonical_artifact_id": "artifact:github:org/bench",
                "name": "Bench <Agents>",
                "purpose": "",
                "release_date": "2026-09-01T00:00:00+00:00",
                "score": 87,
                "coverage": 0.85,
                "confidence": "High",
                "status": "ranked",
                "rank": 1,
                "components": {},
            },
            {
                "canonical_artifact_id": "artifact:arxiv:2609.02222",
                "name": "Quiet",
                "purpose": "",
                "release_date": "2026-08-20T00:00:00+00:00",
                "score": None,
                "coverage": 0.0,
                "confidence": "Low",
                "status": "limited_signals",
                "rank": None,
                "components": {},
            },
        ],
    }
    return {
        "schema_version": 1,
        "method_version": "attention-ranking-v1",
        "generated_at": "2026-09-10T09:00:00+00:00",
        "default_window": default_window,
        "windows": {default_window: window},
    }


def _leaderboard_section(html: str) -> str:
    start = html.index('<section class="view" id="leaderboard-view"')
    return html[start : html.index('<section class="view" id="map-view"', start)]


def test_the_page_opens_on_latest_releases_and_keeps_the_adoption_view():
    # Acceptance: `/leaderboard/` defaults to Latest releases · 30d, and the
    # existing model-card adoption and reported-score views stay reachable
    # with their content intact.
    html = (SITE / "index.html").read_text(encoding="utf-8")
    section = _leaderboard_section(html)

    modes = section.index('<nav class="leaderboard-modes"')
    latest = section.index('id="latest-releases"')
    adoption = section.index('<div id="leaderboard-adoption" hidden>')
    assert modes < latest < adoption, "modes, then the latest ranking, then the adoption view"
    assert 'data-lmode="latest" aria-pressed="true"' in section
    assert 'data-lmode="adoption" aria-pressed="false"' in section
    assert 'href="/saturation/"' in section, "the score workbench stays a separate view"
    # One path, one reader-facing name: the nav, the heading, VIEW_LABELS and
    # the sitemap all call /saturation/ Saturation, so a mode label of its own
    # invention would land the reader somewhere that never uses the word they
    # clicked.
    assert 'href="/saturation/" data-i18n="Saturation">Saturation</a>' in section
    # The latest section is not hidden; the adoption block is, and it still
    # holds every element the adoption renderer writes into.
    opening = re.search(r'<section[^>]*id="latest-releases"[^>]*>', section)
    assert opening and 'class="leaderboard-top latest-releases"' in opening.group(0)
    assert "hidden" not in opening.group(0)
    for anchor in (
        'id="benchmark-skyline"',
        'id="leaderboard-top-list"',
        'id="leaderboard-insights"',
        'id="leaderboard-filters"',
        'id="leaderboard-cards"',
    ):
        assert anchor in section[adoption:], anchor
    # Three windows, the 30-day one pressed, in the order the payload keys them.
    assert re.findall(r'data-lwindow="(\w+)"', section) == ["7d", "30d", "90d"]
    assert 'data-lwindow="30d" aria-pressed="true"' in section
    assert 'id="latest-releases-window">· 30 days</span>' in section
    # The window switch rewrites the count and the empty state with no page
    # load, so both announce themselves the way this view's other counts do.
    assert 'id="latest-releases-empty" aria-live="polite" hidden' in section
    assert 'id="latest-releases-note" aria-live="polite"' in section


def test_browser_mode_window_signal_and_url_contracts():
    # These contracts used to run in a second harness that rebuilt each
    # function by slicing app.js between literal start and end markers, so a
    # rename or a reorder broke the test without changing any behaviour. They
    # now run against the real evaluated module in the render harness, through
    # the same readUrl/writeUrl the browser calls.
    drawn = _render(json.loads(FIXTURE.read_text(encoding="utf-8")))

    # The page opens on the latest releases. A permalink written before the
    # view had modes carries one of the adoption view's own filters, and still
    # opens the view it filtered; an explicit lmode wins either way. The
    # cohort search is not such a marker, or a shared search link would flip.
    assert drawn["modes"] == {
        "(none)": "latest",
        "lwindow=7d": "latest",
        "lrq=agent": "latest",
        "lrq=agent&lwindow=90d": "latest",
        "lscore=70": "adoption",
        "lq=agent": "adoption",
        "ldomain=code": "adoption",
        "lorg=OpenAI": "adoption",
        "lera=2025": "adoption",
        "lheight=documents": "adoption",
        "lmode=latest&lscore=70": "latest",
        "lmode=adoption": "adoption",
        "lmode=bogus": "latest",
        # Saturation writes the shared cutoff on every address, so on its own
        # it is no choice of a leaderboard mode; the adoption filters still are.
        "saturation:lscore=60": "latest",
        "saturation:lscore=60&lq=agent": "adoption",
    }

    # The payload's default window unless the reader picked a valid one.
    assert drawn["windows"] == {
        "default": "30d",
        "explicit7d": "7d",
        "unknown": "30d",
        "keyDefault": "30d",
        "key90d": "90d",
        "keyInvalid": "30d",
        "label7d": "7 days",
    }

    # Null is "no signal", never zero; a stale reading carries the day it was
    # read; a gone resource says so; a real zero stays a zero.
    assert drawn["signalText"] == {
        "stars": "1,204",
        "staleUpvotes": "33 · stale since 2026-09-08",
        "goneDataset": "unavailable",
        "staleNoDate": "5 · stale",
        "freshZero": "0",
        "unknownNull": "not observed",
        "absent": "not observed",
    }
    # And the normalized contribution names its own absence.
    assert drawn["normalizedText"] == {
        "fresh": "1.00",
        "stale": "0.90",
        "unscored": "not scored",
        "absent": "not scored",
    }

    # The cohort search matches a substring of the name or the artifact id,
    # case-insensitively, over what is already loaded. A blank query is not a
    # filter.
    assert drawn["matcher"] == {
        "emptyQuery": 2,
        "blankQuery": 2,
        "caseInsensitive": ["Quiet"],
        "byId": ['Bench <Agents> & "Tools"'],
        "miss": 0,
    }

    # An empty window points at a wider one that has entries, or at the
    # cumulative adoption view once there is no wider window left.
    assert drawn["emptyState"] == {
        "message7d": (
            "No benchmark released in the last 7 days has a measurable attention signal yet."
        ),
        "wider7d": ["30d", "90d"],
        "adoption7d": False,
        "widerWhenLoadedEmpty": [],
        "adoptionWhenLoadedEmpty": True,
        "adoption90d": True,
    }

    # Weights come from the published components, never a number restated in
    # the browser, and a payload without them names the signals plainly.
    assert drawn["weights"] == {
        "github_stars": 0.55,
        "hf_paper_upvotes": 0.3,
        "hf_dataset_downloads": 0.15,
    }
    assert drawn["methodNote"].startswith(
        "Ranking attention-ranking-v1: 55% GitHub stars, 30% Hugging Face paper upvotes, "
        "15% Hugging Face dataset downloads, last 30 days,"
    )
    assert "never a cumulative total" in drawn["methodNote"]
    # The bounds are formatted the way the page formats them, in UTC as the
    # sentence says. The retired harness stubbed formatDate and asserted the
    # raw ISO prefix, so it passed on "2026-09-10" for a window ending
    # 2026-09-10T23:30-05:00 -- the local day, one off from the UTC day the
    # reader is shown. Running the real formatter is what makes that visible.
    assert "Window Aug 11, 2026 to Sep 11, 2026, UTC." in drawn["methodNote"]
    assert drawn["methodNoteBare"].startswith(
        "Ranking v9: GitHub stars, Hugging Face paper upvotes, "
        "Hugging Face dataset downloads, last 30 days,"
    )

    # URL round trip through the real readUrl and writeUrl: the latest mode
    # writes only a non-default window and its own search, the adoption mode
    # writes its filters and so names itself, and neither carries the other's.
    routes = drawn["routes"]
    assert routes["cleanMode"] == "latest" and routes["cleanWindow"] == ""
    assert routes["clean"] == "/leaderboard/"
    assert routes["read90d"] == "90d"
    assert routes["write90d"] == "/leaderboard/?lwindow=90d"
    assert routes["defaultWindowOmitted"] == "/leaderboard/"
    assert routes["searchMode"] == "latest" and routes["searchQuery"] == "vbench"
    assert routes["searchAddress"] == "/leaderboard/?lwindow=90d&lrq=vbench"
    assert routes["searchSurvivesDefaultWindow"] == "/leaderboard/?lrq=vbench"
    assert routes["legacyMode"] == "adoption" and routes["legacyQuery"] == "agent"
    assert routes["legacyAddress"] == "/leaderboard/?lscore=70&lq=agent"
    assert routes["backToLatest"] == "/leaderboard/?lwindow=7d"
    # The adoption view writes no cohort search, so switching cannot leave a
    # latest-mode filter in an adoption address.
    assert "lrq=" not in routes["adoptionDropsSearch"]
    # Back from Saturation must not land on a mode the reader never chose.
    assert routes["saturationView"] == "saturation" and routes["saturationMode"] == "latest"
    assert routes["fromSaturation"] == "/leaderboard/"
    assert routes["legacyFrontierView"] == "saturation"
    assert routes["legacyFrontierMode"] == "latest"
    assert routes["saturationAdoptionMode"] == "adoption"
    assert routes["saturationAdoptionAddress"] == (
        "/leaderboard/?lscore=40&lheight=documents&lq=agent"
    )


def test_every_visible_latest_releases_string_is_translated():
    # Every static label the section shows and every string its renderer draws
    # through t() has a zh entry, so the Chinese interface does not fall back
    # to English on the page's default view.
    html = (SITE / "index.html").read_text(encoding="utf-8")
    script = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    section = _leaderboard_section(html)
    latest = section[: section.index('<div id="leaderboard-adoption" hidden>')]
    zh = script.split("  zh: {", 1)[1].split("\n  },\n", 1)[0]

    def has(key: str) -> bool:
        quoted = json.dumps(key, ensure_ascii=False)
        return f"{quoted}:" in zh or f"\n    {key}:" in zh

    for key in re.findall(r'data-i18n(?:-aria)?="([^"]+)"', latest):
        assert has(key), f"missing zh translation for {key!r}"
    for key in (
        "GitHub stars",
        "Hugging Face paper upvotes",
        "Hugging Face dataset downloads, last 30 days",
        "unavailable",
        "not observed",
        "{value} · stale since {date}",
        "{value} · unverified since {date}",
        "{value} · unverified",
        "source ↗",
        "Coverage {coverage}",
        "limited signals: not enough fresh durable signal to rank",
        "No benchmark released in the last {days} days has a measurable attention signal yet.",
        "Try {window}",
        "See model-card adoption instead",
        "{days} days",
        "unranked",
        "Loading this window…",
        "This window could not be loaded. Refresh to try again.",
        "The {window} window is not in this build.",
        "Data through {through} · average signal coverage {coverage}.",
        "normalized",
        "not scored",
    ):
        assert has(key), f"missing zh translation for {key!r}"
    # The feature adds no second entry for a key the table already had: a
    # repeated key silently keeps only its last value.
    for key in ("confidence", "high", "medium", "low", "unranked", "released", "weight"):
        assert zh.count(f"\n    {key}:") + zh.count(f'\n    "{key}":') == 1, key


def test_the_static_leaderboard_page_seeds_the_default_window():
    # A crawler or a reader without scripts sees the same rows the script
    # draws for the default window, in the published order, with the limited
    # entry kept and marked rather than dropped, and the inputs behind each
    # rank in the disclosure the script would otherwise draw.
    seed = _latest_releases_seed({"latest_releases_leaderboard": _payload()})
    rows = seed[LIST_ANCHOR]
    assert "data-seed" in rows
    assert rows.count('<li class="latest-release">') == 2
    assert '<span class="leaderboard-top-rank">01</span>' in rows
    assert "Bench &lt;Agents&gt;" in rows, "names are escaped"
    assert (
        '<span class="leaderboard-top-rank"><span aria-hidden="true">—</span>'
        '<span class="visually-hidden">unranked</span></span>'
    ) in rows
    assert "latest-release-bar-limited" in rows
    assert "<span>87</span>" in rows and "<span>no score</span>" in rows
    assert 'class="pill pill-confidence pill-confidence-high">high</span>' in rows
    assert 'class="latest-release-date">released Sep 1, 2026</small>' in rows
    assert rows.count('<div class="latest-release-body">') == 2
    assert rows.count("<dt>GitHub stars</dt><dd><span>not observed</span>") == 2
    assert "limited signals: not enough fresh durable signal to rank" in rows
    assert rows.index("Bench") < rows.index("Quiet"), "published order is kept"
    assert seed[WINDOW_ANCHOR].endswith("· 30 days</span>")
    assert "Ranking attention-ranking-v1:" in seed[INFO_ANCHOR]
    assert EMPTY_ANCHOR not in seed, "rows leave the empty state to the script"
    # The default window names itself, so a payload defaulting to 7 days
    # would not open under a 30-day heading.
    week = _latest_releases_seed({"latest_releases_leaderboard": _payload(default_window="7d")})
    assert week[WINDOW_ANCHOR].endswith("· 7 days</span>")
    # Nothing to rank is a real state the page must show without scripts, with
    # the same way out the script offers; nothing published is nothing seeded.
    empty = _latest_releases_seed({"latest_releases_leaderboard": _payload(entries=[])})
    assert LIST_ANCHOR not in empty
    assert empty[EMPTY_ANCHOR].startswith(
        '<p class="empty-state latest-releases-empty" id="latest-releases-empty" '
        'aria-live="polite" data-seed>'
        "No benchmark released in the last 30 days has a measurable attention signal yet. "
    )
    assert 'data-lwindow="90d">Try 90 days</button>' in empty[EMPTY_ANCHOR]
    assert 'data-lwindow="7d"' not in empty[EMPTY_ANCHOR], "only wider windows are offered"
    widest = _latest_releases_seed(
        {"latest_releases_leaderboard": _payload(entries=[], default_window="90d")}
    )
    assert 'data-lmode="adoption">See model-card adoption instead</button>' in widest[EMPTY_ANCHOR]
    # A wider window known to be empty is not offered; one not published is.
    known = _payload(entries=[], default_window="7d")
    known["windows"]["30d"] = {**known["windows"]["7d"], "entries": []}
    offered = _latest_releases_seed({"latest_releases_leaderboard": known})[EMPTY_ANCHOR]
    assert 'data-lwindow="30d"' not in offered and 'data-lwindow="90d"' in offered
    assert _latest_releases_seed({}) == {}
    unpublished = {**_payload(), "windows": {}}
    assert _latest_releases_seed({"latest_releases_leaderboard": unpublished}) == {}


def test_seeds_are_what_the_renderer_draws():
    # The rule app_seeds.py states: a seed is what the renderer would produce
    # from the same data, in the same markup. Checked against the renderer
    # itself rather than a description of it, on a fixture with a ranked row
    # carrying fresh, stale and unavailable signals, a limited row, an unsafe
    # source URL, and an empty window.
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    drawn = _render(payload)
    seed = _latest_releases_seed({"latest_releases_leaderboard": payload})
    assert _inner(seed[LIST_ANCHOR]) == drawn["default"]["list"]
    assert _inner(seed[INFO_ANCHOR]) == drawn["default"]["info"]
    # The renderer fills the ranked-count note for a non-empty window, so the
    # seed has to as well: without it a reader without scripts saw rows marked
    # "limited signals" and nothing saying how many of the cohort were ranked.
    assert _inner(seed[NOTE_ANCHOR]) == drawn["default"]["note"]
    assert drawn["default"]["window"] == "· 30 days"
    assert drawn["default"]["emptyHidden"] is True
    # The note also carries how current the data is and how much of the ranking
    # weight was observed across the cohort, both already in the payload and
    # neither previously shown: a reader could see how many rows ranked but not
    # how well, nor whether the numbers were from today or a stalled run.
    assert drawn["default"]["note"] == (
        "1 of 2 releases in this window are ranked; the rest are listed with limited signals. "
        "Data through Sep 11, 2026 · average signal coverage 50%."
    )
    assert drawn["default"]["pressedWindows"] == ["30d"]
    assert drawn["default"]["pressedModes"] == ["latest"]
    assert drawn["default"]["latestHidden"] is False and drawn["default"]["adoptionHidden"] is True
    # The unsafe URL is not linked; the safe ones are, with their weights.
    assert 'href="javascript:' not in drawn["default"]["list"]
    assert drawn["default"]["list"].count('class="latest-release-source"') == 4
    # A connector counter reaches the payload as a real number the engine marks
    # `unknown` and refuses to promote. Printed bare it read exactly like a
    # fresh observation, which is the imputation issue #530 rules out.
    assert "420 · unverified since 2026-08-30" in drawn["default"]["list"]
    assert "420<" not in drawn["default"]["list"]
    # Each component also shows the normalized contribution the rank was
    # computed from, and names the state when the engine scored nothing: a
    # component that contributed zero and one that was never scored are
    # different facts, and a blank would read as the first.
    assert "normalized 1.00" in drawn["default"]["list"]
    assert "normalized 0.90" in drawn["default"]["list"]
    assert drawn["default"]["list"].count("normalized not scored") == 4
    week = _latest_releases_seed(
        {"latest_releases_leaderboard": {**payload, "default_window": "7d"}}
    )
    assert _inner(week[EMPTY_ANCHOR]) == drawn["empty7d"]["empty"]
    assert _inner(week[INFO_ANCHOR]) == drawn["empty7d"]["info"]
    assert drawn["empty7d"]["list"] == "" and drawn["empty7d"]["window"] == "· 7 days"


def test_the_renderer_keeps_open_rows_loads_wider_windows_and_reports_failure():
    drawn = _render(json.loads(FIXTURE.read_text(encoding="utf-8")))
    # A redraw (the catalog index landing, Refresh, Back) keeps the signals a
    # reader opened.
    assert drawn["openBefore"] == ["artifact:github:org/bench"]
    assert drawn["openAfter"] == ["artifact:github:org/bench"]
    # The adoption mode hides the latest section and shows the adoption block.
    assert drawn["adoption"] == {
        "latestHidden": True,
        "adoptionHidden": False,
        "pressedModes": ["adoption"],
    }
    # A window the bootstrap did not carry is a full-data route, like a
    # historical Today URL: boot, Back and Refresh fetch the corpus for it.
    assert drawn["needsFullData"] == {
        "missingWindow": True,
        "adoption": False,
        "loadedWindow": False,
        "otherView": False,
        "fullLoaded": False,
    }
    # The renderer fetches it too, says so while waiting, and says what
    # happened when the fetch fails instead of loading forever.
    assert drawn["failed90d"]["empty"] == "Loading this window…"
    assert drawn["failed90d"]["fetchCalls"] == ["/data/radar.json"]
    assert drawn["failed90d"]["after"] == "This window could not be loaded. Refresh to try again."
    assert drawn["failed90d"]["errors"] == ["HTTP 404"]
    # A corpus that has loaded without the window is not going to bring it.
    assert drawn["missing90d"]["empty"].startswith("The 90 days window is not in this build. ")
    assert drawn["missing90d"]["empty"].count("data-lwindow=") == 2
    assert drawn["missing90d"]["fetchCalls"] == []
    assert drawn["loading90d"]["after"] == "Loading this window…"
    # Adoption mode reads no release window and stateNeedsFullData skips the
    # corpus for it, so the renderer must not fetch it either to fill a hidden
    # section. The guard and the renderer have to agree or one of them is waste.
    assert drawn["adoption90d"]["fetchCalls"] == []
    assert drawn["adoption90d"]["needsFullData"] is False
    assert drawn["adoption90d"]["latestHidden"] is True
    # The empty stub the bootstrap keeps for an unpublished window has no
    # bounds to print a method note for; the empty state still shows its way out.
    assert drawn["stub90d"]["info"] == ""
    assert drawn["stub90d"]["empty"].startswith("No benchmark released in the last 90 days")
    assert 'data-lmode="adoption"' in drawn["stub90d"]["empty"]
    # Search was only ever inside the hidden adoption view, so a reader looking
    # at the latest cohort had no way to find a row in it. The query narrows
    # what is already loaded: the window still decides which releases exist.
    assert drawn["search"]["allRows"] == 2 and drawn["search"]["rows"] == 1
    assert "Quiet" in drawn["search"]["list"] and "Bench " not in drawn["search"]["list"]
    assert drawn["search"]["inputValue"] == "quiet"
    # The note says how many of the cohort the reader is being shown, so a
    # filtered list cannot be mistaken for the whole window.
    assert "Showing 1 that match “quiet”." in drawn["search"]["note"]
    # A query that matches nothing is not an empty window, so the way out is
    # clearing the search rather than the wider-window suggestion.
    assert drawn["searchMiss"]["rows"] == 0
    assert drawn["searchMiss"]["empty"].startswith(
        "No release in this window matches “no-such-benchmark”."
    )
    assert "data-lrq-clear" in drawn["searchMiss"]["empty"]
    assert "data-lwindow=" not in drawn["searchMiss"]["empty"]
    assert drawn["searchCleared"]["rows"] == 2

    # A direct non-default-window address lands on a page the generator seeded
    # with the DEFAULT window's rows, and the concern is that those rows stay
    # put when the corpus fetch fails -- 30-day data sitting under a 90-day
    # URL. Every other failure probe here runs straight after an empty render,
    # so "the list is empty" proved nothing about clearing. This one puts the
    # 30-day rows on the page first and then fails the fetch.
    seeded = drawn["seededThenFailed90d"]
    assert seeded["seededRows"] == 2 and seeded["seededNote"]
    assert seeded["rowsAfter"] == 0 and seeded["list"] == ""
    # The note and method disclosure describe the window that is gone, so they
    # go with it rather than being left to describe rows nobody can see.
    assert seeded["note"] == "" and seeded["info"] == ""
    # And the heading names the window actually requested, not the seeded one.
    assert seeded["window"] == "· 90 days"
    assert seeded["empty"] == "This window could not be loaded. Refresh to try again."

    # The Chinese interface draws the same rows in its own words.
    assert drawn["zh"]["window"] == "· 30 天"
    assert "发布于" in drawn["zh"]["list"] and "released" not in drawn["zh"]["list"]
    assert "来源 ↗" in drawn["zh"]["list"]


def test_the_leaderboard_page_describes_its_new_default():
    seo = load_view_seo(SITE / "assets" / "app.js")["leaderboard"]
    assert "latest" in seo["title"].lower()
    assert "GitHub stars" in seo["description"]
    assert seo["canonical"] == "/leaderboard/"
    # The description is the page's meta, og and twitter description at once.
    # Every other view sits between 126 and 166 characters; a longer one is
    # cut off in a result snippet, and this page had run to 230.
    assert len(seo["description"]) <= 170


def test_written_leaderboard_page_carries_both_rankings(tmp_path):
    # tests/ has no __init__.py, so the sibling module is imported by its own
    # name: that resolves under the `pytest` script CI runs and under
    # `python -m pytest` alike.
    from test_app_pages import _dashboard, _write

    dashboard = _dashboard()
    dashboard["latest_releases_leaderboard"] = _payload()
    _write(tmp_path, dashboard)
    page = (tmp_path / "leaderboard" / "index.html").read_text(encoding="utf-8")
    assert 'id="latest-releases-list" data-seed>' in page
    assert "Bench &lt;Agents&gt;" in page
    assert 'id="leaderboard-top-list" data-seed>' in page, "the adoption rows are still seeded"
    assert page.index('id="latest-releases-list"') < page.index('id="leaderboard-top-list"')
    seo = load_view_seo(tmp_path / "assets" / "app.js")
    assert seo["leaderboard"]["canonical"] == "/leaderboard/"


@pytest.mark.parametrize("status", ["ranked", "limited_signals"])
def test_seed_bar_widths_scale_against_the_top_score(status):
    entries = [
        {"name": "Top", "score": 80, "status": "ranked", "rank": 1},
        {"name": "Half", "score": 40, "status": status, "rank": 2 if status == "ranked" else None},
    ]
    rows = _latest_releases_seed({"latest_releases_leaderboard": _payload(entries=entries)})[
        LIST_ANCHOR
    ]
    assert 'style="width:100.0%"' in rows
    assert 'style="width:50.0%"' in rows
