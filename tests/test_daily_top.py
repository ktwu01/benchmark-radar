import http.client
import json
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

from benchmark_radar import cli
from benchmark_radar.daily_top import (
    briefing_items,
    budgeted_fetchers,
    build_share_block,
    resolve_creators,
    select_top_items,
    write_share_block,
)
from benchmark_radar.http import RequestError
from benchmark_radar.social import render_social_section

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import render_share_images as share  # noqa: E402


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


def test_selection_ranks_by_radar_score_and_stops_at_three():
    items = [_item(f"Bench {n}", n) for n in range(10)]
    selected = select_top_items(_days(*items), "2026-10-23")
    assert [item["title"] for item in selected] == ["Bench 9", "Bench 8", "Bench 7"]


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


def test_owner_comes_from_source_id_in_a_raw_snapshot():
    # Raw snapshots leave `organizations` empty for Hugging Face items.
    fetch = _fetcher(
        {"https://huggingface.co/api/organizations/utahnlp/overview": {"fullname": "Utah NLP"}}
    )
    item = _item(
        "k", 1, source="Hugging Face", organizations=[], authors=[], source_id="utahnlp/knows"
    )
    assert resolve_creators(item, fetch=fetch)["affiliations"] == ["Utah NLP"]


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


def _briefed_day(*items, bullets, generator="openai-responses"):
    days = _days(*items)
    days[-1]["briefing"] = {
        "generator": generator,
        "bullets": bullets,
        "citations": [
            {"id": f"E{index:03d}", "url": item["url"], "title": item["title"]}
            for index, item in enumerate(items, start=1)
        ],
    }
    return days


def test_briefing_bullets_choose_the_cards_in_briefing_order():
    # The LLM briefing ranks the day; the radar score does not override it.
    low, high = _item("Low Score", 10), _item("High Score", 90)
    days = _briefed_day(
        high,
        low,
        bullets=[
            "Low Score tests reading. Why it matters: x. Evidence: E002. High confidence.",
            "High Score tests math. Why it matters: y. Evidence: E001, E002. High confidence.",
        ],
    )
    picked = briefing_items(days[-1])
    assert [(item["title"], blurb) for item, blurb in picked] == [
        ("Low Score", "Low Score tests reading."),
        ("High Score", "High Score tests math."),
    ]


def test_a_day_without_a_model_briefing_falls_back_to_the_radar_score():
    days = _briefed_day(
        _item("A", 30),
        _item("B", 90),
        bullets=["Deterministic finding. Evidence: E001."],
        generator="deterministic-fallback",
    )
    block = build_share_block(days, "2026-10-23", fetch=_fetcher({}), fetch_text=lambda u, **_: "")
    assert block["basis"] == "radar_score"
    assert [card["title"] for card in block["cards"]] == ["B", "A"]


def test_top_three_are_the_first_three_cards():
    items = [_item(f"Bench {n}", n) for n in range(5)]
    bullets = [f"Bench {n} tests x. Evidence: E{n + 1:03d}." for n in range(5)]
    block = build_share_block(
        _briefed_day(*items, bullets=bullets),
        "2026-10-23",
        fetch=_fetcher({}),
        fetch_text=lambda u, **_: "",
    )
    assert block["basis"] == "briefing"
    assert len(block["cards"]) == 5
    assert block["top"] == [card["url"] for card in block["cards"][:3]]


def test_a_later_pass_keeps_posted_cards_and_only_appends_new_ones():
    # card-01.png may already be posted; a reordered briefing must not make it
    # a different benchmark, and its creators are not looked up again.
    first, second = _item("First", 1), _item("Second", 2)
    days = _briefed_day(
        first,
        second,
        bullets=["Second tests y. Evidence: E002.", "First tests x. Evidence: E001."],
    )
    previous = {
        "basis": "briefing",
        "cards": [{"url": first["url"], "title": "First", "authors": ["Ada"], "affiliations": []}],
    }
    fetch = _fetcher({})
    block = build_share_block(
        days, "2026-10-23", previous=previous, fetch=fetch, fetch_text=lambda u, **_: ""
    )
    assert [card["title"] for card in block["cards"]] == ["First", "Second"]
    assert block["cards"][0]["authors"] == ["Ada"]
    assert block["top"] == [first["url"], second["url"]]


def test_share_block_is_written_into_the_snapshot_and_survives_a_merge(tmp_path, monkeypatch):
    from benchmark_radar.snapshots import merge_snapshots

    path = tmp_path / "2026-10-23.json"
    path.write_text(json.dumps({"date": "2026-10-23"}), encoding="utf-8")
    days = _briefed_day(_item("k", 1), bullets=["k tests x. Evidence: E001."])
    monkeypatch.setattr("benchmark_radar.daily_top.load_snapshots", lambda _dir: days)
    monkeypatch.setattr("benchmark_radar.daily_top.validate_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(
        "benchmark_radar.daily_top.budgeted_fetchers",
        lambda: (_fetcher({}), lambda u, **_: ""),
    )
    block = write_share_block(tmp_path, "2026-10-23")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["share"] == block
    existing = {**stored, "evidence_items": [], "since": "2026-10-22T00:00:00+00:00"}
    incoming = {
        "evidence_items": [],
        "since": "2026-10-22T00:00:00+00:00",
        "generated_at": "2026-10-23T12:00:00+00:00",
    }
    existing["generated_at"] = "2026-10-23T09:00:00+00:00"
    assert merge_snapshots(existing, incoming)["share"] == block


def _snapshot_with_cards(count):
    cards = [
        {
            "title": f"Bench {n}: " + "a long benchmark title " * 4,
            "url": f"u{n}",
            "source": "arXiv",
            "published_at": "2026-10-23T00:00:00Z",
            "categories": ["benchmark", "data_quality"],
            "blurb": "&lt;p&gt;Tests agents.&lt;/p&gt;",
            "authors": ["Vivien Jiaqian Zhu 朱佳谦", "B", "C", "D"],
            "affiliations": ["Carnegie Mellon University"],
        }
        for n in range(count)
    ]
    return {"date": "2026-10-23", "share": {"date": "2026-10-23", "cards": cards}}


def test_render_writes_the_top_three_and_one_card_per_benchmark(tmp_path):
    written = share.render_day(_snapshot_with_cards(5), tmp_path)
    assert [path.name for path in written] == [
        "top3.png",
        "card-01.png",
        "card-02.png",
        "card-03.png",
        "card-04.png",
        "card-05.png",
    ]
    with Image.open(written[0]) as image:
        assert image.size == (1080, 1350)
    with Image.open(written[1]) as image:
        assert image.size == (1200, 630)


def test_render_is_deterministic(tmp_path):
    first = share.render_day(_snapshot_with_cards(2), tmp_path / "a")
    second = share.render_day(_snapshot_with_cards(2), tmp_path / "b")
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_a_snapshot_without_cards_renders_nothing(tmp_path):
    assert share.render_day({"date": "2026-10-23"}, tmp_path) == []


def _index_record(slug, **extra):
    return {"slug": slug, "key": f"llm-stats:{slug}", "name": slug.upper(), **extra}


def test_catalog_render_writes_one_card_per_benchmark_named_by_slug(tmp_path):
    index = {
        "benchmarks": [
            _index_record(
                "mmlu-pro",
                source="llm_stats",
                publisher="University of Waterloo",
                released="2024-06-03",
                description="Ten options per question.",
                has_paper=True,
                score_count=134,
            ),
            # No date, publisher, description or score: still gets a card.
            _index_record("bare"),
        ]
    }
    written = share.render_catalog(index, tmp_path, workers=1)
    assert [path.name for path in written] == ["mmlu-pro.png", "bare.png"]
    for path in written:
        with Image.open(path) as image:
            assert image.size == (1200, 630)


def test_catalog_render_is_deterministic(tmp_path):
    index = {"benchmarks": [_index_record("gpqa", description="Graduate-level questions.")]}
    first = share.render_catalog(index, tmp_path / "a", workers=1)
    second = share.render_catalog(index, tmp_path / "b", workers=1)
    assert first[0].read_bytes() == second[0].read_bytes()


def test_catalog_render_refuses_a_slug_that_is_not_a_file_name(tmp_path):
    index = {"benchmarks": [_index_record("../escape")]}
    with pytest.raises(ValueError, match="unsafe slug"):
        share.render_catalog(index, tmp_path, workers=1)


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


def test_social_checklist_embeds_the_days_images():
    block = _snapshot_with_cards(2)["share"]
    section = render_social_section("insight", "repo", [], [{"name": "X"}], share=block)
    base = "https://cards.benchmark-radar.org/daily/2026-10-23"
    assert f"[![Top benchmarks on 2026-10-23]({base}/top3.png)]({base}/top3.png)" in section
    # Every card is shown inline, so a card cannot be forgotten.
    for index in (1, 2):
        assert f"]({base}/card-0{index}.png)\n\n[![" in section
        assert f"]({base}/card-0{index}.png)]({base}/card-0{index}.png)" in section


def test_checklist_title_cut_never_splits_an_escape():
    block = _snapshot_with_cards(1)["share"]
    block["cards"][0]["title"] = "a" * 59 + "|tail"
    section = render_social_section("insight", "repo", [], [{"name": "X"}], share=block)
    assert "[1. " not in section and "\\]" not in section.split("1. ")[1].split("\n")[0]


def test_checklist_title_cut_on_a_backslash_keeps_its_brackets_closed():
    block = _snapshot_with_cards(1)["share"]
    block["cards"][0]["title"] = "a" * 59 + "\\tail"
    section = render_social_section("insight", "repo", [], [{"name": "X"}], share=block)
    assert "\\](" not in section


def test_spent_lookup_budget_fails_fast_without_calling_the_api(monkeypatch):
    # A rate-limited API must not hold the daily run for minutes.
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


def _run_social(monkeypatch, tmp_path, snapshot, *extra):
    items = tmp_path / "items.json"
    items.write_text(
        json.dumps({"generated_at": "2026-10-23T09:39:52Z", "evidence_items": []}),
        encoding="utf-8",
    )
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "2026-10-23.json").write_text(json.dumps(snapshot), encoding="utf-8")
    channels = tmp_path / "social.yml"
    channels.write_text("social:\n  channels:\n    - name: X\n", encoding="utf-8")
    output = tmp_path / "social.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark-radar",
            "social",
            "--items",
            str(items),
            "--snapshot-dir",
            str(snapshots),
            "--channels",
            str(channels),
            "--social-output",
            str(output),
            *extra,
        ],
    )
    cli.main()
    return output.read_text(encoding="utf-8")


def test_social_command_embeds_the_images_recorded_in_the_snapshot(monkeypatch, tmp_path):
    body = _run_social(monkeypatch, tmp_path, _snapshot_with_cards(1))
    assert "daily/2026-10-23/top3.png" in body


def test_social_command_embeds_nothing_without_recorded_cards(monkeypatch, tmp_path):
    # No cards means the publish job pushes no images; a link would 404.
    assert "benchmark-radar-cards" not in _run_social(monkeypatch, tmp_path, {"date": "x"})


def test_social_command_omits_images_that_were_not_published(monkeypatch, tmp_path):
    body = _run_social(monkeypatch, tmp_path, _snapshot_with_cards(1), "--skip-share-images")
    assert "benchmark-radar-cards" not in body
