"""Single source of truth for the project's self-citation (issue #483).

The citation is the arXiv technical report (arXiv:2609.11115), a fixed
paper rather than a versioned software release, so this no longer tracks
``__version__``. CITATION.cff and the site copy blocks in app_seeds.py
keep the same author set, so every citation surface stays in step under
this module's title and author list.

This module also owns the BibTeX entry. The READMEs, CITATION.md, the site
copy blocks, and the client-side mirror each hold their own copy of it; the
string is written once here so the query payload and those copies can be
compared instead of drifting.
"""

from __future__ import annotations

PUBLICATION_YEAR = "2026"
TITLE = "Benchmark Radar: A living database and search engine for AI benchmarks and evaluation"
TITLE_ARXIV = (
    "Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and Evaluation"
)
AUTHORS_APA = "Wu, K., Zhou, J., Shang, E., Wang, J., Han, P., Wang, J., & Xu, W."
AUTHORS_BIBTEX = (
    "Koutian Wu and Junjie Zhou and Ergan Shang and Jiayu Wang and "
    "Pengqian Han and Junkai Wang and Wanghan Xu"
)
BIBTEX_KEY = "wu2026benchmarkradarlivingdatabase"
ARXIV_ID = "2609.11115"
ARXIV_URL = f"https://arxiv.org/abs/{ARXIV_ID}"
DOI = f"10.48550/arXiv.{ARXIV_ID}"
CITE_URL = "https://benchmark-radar.org/#cite"


def apa_citation() -> str:
    return f"{AUTHORS_APA} ({PUBLICATION_YEAR}). {TITLE}. arXiv:{ARXIV_ID}. {ARXIV_URL}"


def bibtex_citation() -> str:
    """arXiv's own export format for this paper, line for line."""
    return "\n".join(
        (
            f"@misc{{{BIBTEX_KEY},",
            f"      title={{{TITLE_ARXIV}}},",
            f"      author={{{AUTHORS_BIBTEX}}},",
            f"      year={{{PUBLICATION_YEAR}}},",
            f"      eprint={{{ARXIV_ID}}},",
            "      archivePrefix={arXiv},",
            "      primaryClass={cs.AI},",
            f"      url={{{ARXIV_URL}}},",
            "}",
        )
    )


def latex_citation() -> str:
    """The command to paste into a manuscript that already has the BibTeX entry."""
    return f"\\cite{{{BIBTEX_KEY}}}"


def citation_block() -> dict[str, str]:
    """Machine-readable citation carried by every query payload.

    An agent that reads only stdout gets the paper here, in a form it can put
    straight into a related-work table, instead of losing the stderr footer.
    """
    return {
        "apa": apa_citation(),
        "bibtex": bibtex_citation(),
        "latex": latex_citation(),
        "arxiv_id": ARXIV_ID,
        "url": ARXIV_URL,
        "formats_url": CITE_URL,
    }


def cite_reminder() -> str:
    """Footer text for a finished CLI command (issue #483).

    No leading or trailing blank lines: callers decide the spacing.
    """
    return (
        "If Benchmark Radar helped your work, please cite it:\n"
        f"  {apa_citation()}\n"
        f"  More citation formats: {CITE_URL}"
    )
