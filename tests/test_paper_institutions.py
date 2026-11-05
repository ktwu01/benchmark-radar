"""Institutions read from OpenAlex or an arXiv paper's own HTML (#1120)."""

from __future__ import annotations

from benchmark_radar.http import RequestError
from benchmark_radar.paper_institutions import (
    arxiv_html_affiliations,
    arxiv_id,
    clean_affiliation,
    lookup,
)


def test_arxiv_id_from_every_shape_the_radar_sees():
    assert arxiv_id("https://arxiv.org/abs/2610.37166v1") == "2610.37166"
    assert arxiv_id("https://doi.org/10.48550/arxiv.2610.34535") == "2610.34535"
    assert arxiv_id("artifact:arxiv:2610.22131") == "2610.22131"
    assert arxiv_id("artifact:doi:10.48550/arxiv.2610.28522") == "2610.28522"
    assert arxiv_id("https://huggingface.co/datasets/a/b") is None


def test_cleaning_drops_conversion_debris():
    assert clean_affiliation("[") is None
    assert clean_affiliation("Duke University;") == "Duke University"
    assert clean_affiliation("Keep , Beijing , China") == "Keep, Beijing, China"
    assert clean_affiliation("someone@uni.edu") is None


# arXiv:2611.04228 (DualWorldBench): affiliations as numbered table rows, with
# the authors' own markers in the cells above them.
NUMBERED = """
<div class="ltx_authors">
<span class="ltx_creator ltx_role_author"><span class="ltx_personname">
<span class="ltx_tabular"><span class="ltx_thead"><span class="ltx_tr">
<span class="ltx_td">Yang Chen<sup class="ltx_sup">1,2</sup>
Bin Wen<sup class="ltx_sup">1</sup></span>
</span></span><span class="ltx_tbody">
<span class="ltx_tr"><span class="ltx_td"><sup class="ltx_sup">1</sup>
National Key Laboratory for Novel Software Technology,
Nanjing University</span></span>
<span class="ltx_tr"><span class="ltx_td"><sup class="ltx_sup">2</sup>
Shanghai Innovation Institute</span></span>
</span></span></span>
<span class="ltx_note ltx_role_thanks"><sup class="ltx_note_mark">1</sup> Equal contribution.</span>
</span>
</div>
"""


def test_numbered_affiliations_skip_author_names():
    assert arxiv_html_affiliations(NUMBERED) == [
        "National Key Laboratory for Novel Software Technology, Nanjing University",
        "Shanghai Innovation Institute",
    ]


def test_contact_affiliations_still_lead():
    page = (
        '<span class="ltx_contact ltx_role_affiliation">'
        '<span class="ltx_contact_name">Affiliation: </span>Carnegie Mellon University</span>'
    )
    assert arxiv_html_affiliations(page) == ["Carnegie Mellon University"]


def test_lookup_prefers_openalex_then_the_paper():
    def missing(url):
        raise RequestError(f"HTTP 404 from {url}")

    found = lookup(
        "2610.33966",
        fetch_json=lambda url: {
            "id": "https://openalex.org/W1",
            "authorships": [{"institutions": [{"display_name": "Duke University"}]}],
        },
        fetch_text=missing,
    )
    assert found == {
        "basis": "openalex_linked_institutions",
        "source_url": "https://openalex.org/W1",
        "institutions": ["Duke University"],
    }
    found = lookup("2611.04228", fetch_json=missing, fetch_text=lambda url: NUMBERED)
    assert found["basis"] == "arxiv_html_affiliations"
    assert found["source_url"] == "https://arxiv.org/html/2611.04228"
    assert lookup("2611.00000", fetch_json=missing, fetch_text=missing) is None
