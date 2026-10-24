import http.client
import json
import sys
import time
from pathlib import Path

from PIL import Image

from benchmark_radar import cli
from benchmark_radar.daily_top import budgeted_fetchers, resolve_creators, select_top_items
from benchmark_radar.http import RequestError
from benchmark_radar.social import render_social_section

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_daily_share_image as share  # noqa: E402


def _item(title, score, **extra):
    return {
        "title": title,
        "total_score": score,
        "source": "arXiv",
        "event_kind": "released",
        "recommended": True,
        "suppression_reasons": [],
        "authors": [f"{title} Author"],
        "organizations": [],
        "url": f"https://doi.org/10.1/{title}",
        **extra,
    }


def _days(*items, earlier=()):
    return [
        {"date": "2026-10-22", "evidence_items": list(earlier)},
        {"date": "2026-10-23", "evidence_items": list(items)},
    ]


def test_selection_ranks_by_radar_score_and_stops_at_four():
    items = [_item(f"Bench {n}", n) for n in range(10)]
    selected = select_top_items(_days(*items), "2026-10-23")
    assert [item["title"] for item in selected] == ["Bench 9", "Bench 8", "Bench 7", "Bench 6"]


def test_selection_keeps_only_new_benchmarks():
    # A tool's version tag, an update, and a paper the radar already showed
    # yesterday are not news on today's image.
    selected = select_top_items(
        _days(
            _item("mteb 2.26.15", 90, source="GitHub Release"),
            _item("Updated Bench", 80, event_kind="updated"),
            _item("Yesterday  bench", 70),
            _item("Same Link", 68, url="https://arxiv.org/abs/2610.1"),
            _item("Hidden Bench", 65, recommended=False),
            _item("Fresh Bench", 60),
            earlier=[
                _item("yesterday bench", 50),
                _item("Other Title", 50, url="https://arxiv.org/abs/2610.1"),
            ],
        ),
        "2026-10-23",
    )
    assert [item["title"] for item in selected] == ["Fresh Bench"]


def test_titles_without_latin_letters_are_not_all_one_title():
    selected = select_top_items(
        _days(_item("评测数据集", 60, url="u2"), earlier=[_item("Тест", 50, url="u1")]),
        "2026-10-23",
    )
    assert [item["title"] for item in selected] == ["评测数据集"]


def test_selection_takes_one_item_per_owner():
    # Three near-identical CT datasets from one uploader once filled the list.
    selected = select_top_items(
        _days(
            _item("ct-a", 90, source="Hugging Face", organizations=["chn123"], authors=[]),
            _item("ct-b", 89, source="Hugging Face", organizations=["chn123"], authors=[]),
            _item("Other", 50),
        ),
        "2026-10-23",
    )
    assert [item["title"] for item in selected] == ["ct-a", "Other"]


def _fetcher(responses):
    calls = []

    def fetch(url, **_kwargs):
        calls.append(url)
        if url not in responses:
            raise RequestError(f"HTTP 404 from {url}")
        return responses[url]

    fetch.calls = calls
    return fetch


def test_huggingface_org_handle_becomes_the_institution():
    fetch = _fetcher(
        {
            "https://huggingface.co/api/organizations/utahnlp/overview": {
                "fullname": "NLP at University of Utah"
            }
        }
    )
    item = _item("k", 1, source="Hugging Face", organizations=["utahnlp"], authors=[])
    assert resolve_creators(item, fetch=fetch) == {
        "authors": [],
        "affiliations": ["NLP at University of Utah"],
    }


def test_huggingface_user_gets_a_name_and_no_affiliation():
    # A user profile has no affiliation field, so none is shown.
    fetch = _fetcher({"https://huggingface.co/api/users/chn123/overview": {"fullname": "clsr"}})
    item = _item("k", 1, source="Hugging Face", organizations=["chn123"], authors=[])
    assert resolve_creators(item, fetch=fetch) == {"authors": ["clsr"], "affiliations": []}


def test_github_user_company_is_the_affiliation():
    fetch = _fetcher(
        {
            "https://api.github.com/users/ada": {
                "type": "User",
                "name": "Ada Lovelace",
                "company": "@analytical",
            }
        }
    )
    item = _item("k", 1, source="GitHub", organizations=["ada"], authors=[])
    assert resolve_creators(item, fetch=fetch) == {
        "authors": ["Ada Lovelace"],
        "affiliations": ["analytical"],
    }


def test_truncated_response_costs_a_fact_not_the_build():
    def fetch(url, **_kwargs):
        raise http.client.IncompleteRead(b"")

    item = _item("k", 1, url="https://arxiv.org/abs/2610.31494")
    creators = resolve_creators(item, fetch=fetch, fetch_text=lambda url, **_: "")
    assert creators == {"authors": ["k Author"], "affiliations": []}


def test_failed_owner_lookup_never_shows_the_handle_as_an_institution():
    item = _item("k", 1, source="GitHub", organizations=["ada"], authors=[])
    assert resolve_creators(item, fetch=_fetcher({})) == {"authors": [], "affiliations": []}


def test_arxiv_institutions_come_from_openalex():
    fetch = _fetcher(
        {
            "https://api.openalex.org/works/doi:10.48550/arXiv.2610.27548": {
                "authorships": [
                    {"institutions": [{"display_name": "Northeastern University"}]},
                    {"institutions": [{"display_name": "Northeastern University"}]},
                    {"institutions": [{"display_name": "Carnegie Mellon University"}]},
                ]
            }
        }
    )
    item = _item("k", 1, url="https://arxiv.org/abs/2610.27548")
    assert resolve_creators(item, fetch=fetch)["affiliations"] == [
        "Northeastern University",
        "Carnegie Mellon University",
    ]


def test_arxiv_html_affiliations_cover_a_paper_openalex_has_not_indexed():
    page = (
        '<span class="ltx_contact ltx_role_affiliation">'
        '<span class="ltx_contact_name">Affiliation: </span>Carnegie Mellon University'
        "</span>"
        '<span class="ltx_contact ltx_role_affiliation">'
        '<span class="ltx_contact_name">Affiliation: </span>'
        '<span class="ltx_text">CMU &amp; UNC</span></span>'
    )
    item = _item("k", 1, url="https://arxiv.org/abs/2610.31404")
    creators = resolve_creators(item, fetch=_fetcher({}), fetch_text=lambda url, **_: page)
    assert creators["affiliations"] == ["Carnegie Mellon University", "CMU & UNC"]


def test_paper_without_any_stated_affiliation_shows_authors_only():
    item = _item("k", 1, url="https://arxiv.org/abs/2610.31494")
    creators = resolve_creators(item, fetch=_fetcher({}), fetch_text=lambda url, **_: "<p></p>")
    assert creators == {"authors": ["k Author"], "affiliations": []}


def test_reversed_duplicate_author_names_merge():
    item = _item(
        "k",
        1,
        source="DataCite",
        authors=["Toshiharu Ohnuma", "Ohnuma, Toshiharu", "Gaku Yamazaki"],
        organizations=["CRIEPI"],
    )
    assert resolve_creators(item, fetch=_fetcher({})) == {
        "authors": ["Toshiharu Ohnuma", "Gaku Yamazaki"],
        "affiliations": ["CRIEPI"],
    }


def test_build_writes_a_portrait_image_per_day_and_latest(tmp_path):
    radar = tmp_path / "radar.json"
    radar.write_text(
        json.dumps(
            {
                "days": _days(
                    _item("Fresh Bench", 60, summary="&lt;p&gt;Tests agents.&lt;/p&gt;"),
                    earlier=[_item("Old Bench", 50)],
                )
            }
        ),
        encoding="utf-8",
    )
    no_html = lambda url, **_: ""  # noqa: E731
    written = share.build(radar, tmp_path / "out", fetchers=(_fetcher({}), no_html))
    assert [path.name for path in written] == ["2026-10-22.png", "2026-10-23.png", "latest.png"]
    assert written[-1].read_bytes() == written[-2].read_bytes()
    with Image.open(written[-1]) as image:
        assert image.size == (1080, 1350)


def test_no_wrapped_line_is_wider_than_the_text_area():
    face = share.font(30, bold=True)
    title = "Pegi1727/" + "DIINA-Human-in-the-Loop-Evaluation-" * 4 + " of educational content"
    lines = share._wrap(title, face, 882, 2)
    assert lines and all(face.getlength(line) <= 882 for line in lines)


def test_summary_html_is_shown_as_text():
    assert share._plain("&lt;h3&gt;Recommended&lt;/h3&gt; &amp;amp; more") == "Recommended & more"


def test_cjk_the_image_font_cannot_draw_is_dropped_unless_nothing_remains():
    assert share._plain("Vivien Jiaqian Zhu 朱佳谦") == "Vivien Jiaqian Zhu"
    assert share._plain("朱佳谦") == "朱佳谦"


def test_social_checklist_embeds_the_days_image():
    section = render_social_section(
        "insight", "repo", [], [{"name": "X"}], share_image_date="2026-10-23"
    )
    assert "https://benchmark-radar.org/share/top4/2026-10-23.png" in section
    assert "latest.png" not in section


def test_spent_lookup_budget_fails_fast_without_calling_the_api(monkeypatch):
    # A rate-limited API must not hold the Pages build past its time limit.
    calls = []
    monkeypatch.setattr(
        "benchmark_radar.daily_top.get_json", lambda url, **kw: calls.append(kw) or {}
    )
    fetch, _ = budgeted_fetchers(seconds=60)
    fetch("https://api.github.com/users/ada")
    assert calls == [{"timeout": 10.0, "attempts": 1}]
    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 61)
    item = _item("k", 1, source="GitHub", organizations=["ada"], authors=[])
    assert resolve_creators(item, fetch=fetch) == {"authors": [], "affiliations": []}
    assert len(calls) == 1


def _run_social(monkeypatch, tmp_path, history):
    items = tmp_path / "items.json"
    items.write_text(
        json.dumps({"generated_at": "2026-10-23T09:39:52Z", "evidence_items": []}),
        encoding="utf-8",
    )
    channels = tmp_path / "social.yml"
    channels.write_text("social:\n  channels:\n    - name: X\n", encoding="utf-8")
    output = tmp_path / "social.md"
    monkeypatch.setattr(cli, "load_snapshots", lambda _path: history)
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "social",
            "--items",
            str(items),
            "--channels",
            str(channels),
            "--social-output",
            str(output),
        ],
    )
    cli.main()
    return output.read_text(encoding="utf-8")


def test_social_command_embeds_the_image_the_pages_build_writes(monkeypatch, tmp_path):
    body = _run_social(monkeypatch, tmp_path, _days(_item("Fresh Bench", 60)))
    assert "share/top4/2026-10-23.png" in body


def test_social_command_embeds_nothing_on_a_day_without_new_benchmarks(monkeypatch, tmp_path):
    # The Pages build writes no image that day; a link would 404.
    history = _days(_item("Seen Bench", 60), earlier=[_item("Seen Bench", 50)])
    assert "share/top4" not in _run_social(monkeypatch, tmp_path, history)
