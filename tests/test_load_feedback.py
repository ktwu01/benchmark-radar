"""Every large data download shows the reader that the page is working (#1128).

The first homepage search pulls the full archive (radar.json, tens of
megabytes) and the catalog views wait on benchmark-index.json. With no visual
cue the page looked dead for seconds to minutes on a slow line.
"""

import re
from pathlib import Path

APP = Path("site/assets/app.js").read_text(encoding="utf-8")
STYLES = Path("site/assets/styles.css").read_text(encoding="utf-8")


def test_every_site_data_fetch_goes_through_the_load_tracker():
    # A /data/ fetch outside trackLoad would bring back a silent wait.
    for match in re.finditer(r"fetch\((?P<arg>[^,)]+)", APP):
        arg = match.group("arg")
        if "/data/" not in arg and arg.strip() != "path":
            continue
        preceding = APP[max(0, match.start() - 400) : match.start()]
        assert "trackLoad(" in preceding, f"untracked data fetch: {arg}"


def test_the_full_archive_names_itself_while_it_downloads():
    assert '"/data/radar.json": ["Loading the full archive…"' in APP


def test_loads_keep_the_browsers_own_json_reader():
    # Streaming the body through JavaScript to count megabytes kept a second
    # copy of the 344 MB archive: Chromium's peak renderer memory rose from
    # 1.40 GB to 1.76-1.93 GB, enough to kill a phone tab (#1142 review).
    assert "getReader()" not in APP
    assert "pipeThrough(" not in APP
    assert "JSON.parse(parts" not in APP


def test_load_labels_have_chinese_translations():
    table = APP.split("const I18N = {", 1)[1].split("\nconst state = {", 1)[0]
    for key in (
        "Loading the full archive…",
        "Loading the benchmark catalog…",
        "Loading the latest scan…",
        "Loading trends…",
        "{s} s",
    ):
        assert f'"{key}":' in table, key


def test_waiting_views_mark_their_results_as_stale():
    assert '.view[aria-busy="true"]' in STYLES
    assert "#today-list" in STYLES.split('.view[aria-busy="true"] :is(', 1)[1].split("{", 1)[0]
