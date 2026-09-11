"""Single source of truth for the project's self-citation (issue #483).

The citation is the arXiv technical report (arXiv:2609.11115), a fixed
paper rather than a versioned software release, so this no longer tracks
``__version__``. CITATION.cff and the site copy blocks in app_seeds.py
keep the same author set, so every citation surface stays in step under
this module's title and author list.
"""

from __future__ import annotations

PUBLICATION_YEAR = "2026"
TITLE = "Benchmark Radar: A living database and search engine for AI benchmarks and evaluation"
AUTHORS_APA = "Wu, K., Zhou, J., Shang, E., Wang, J., Han, P., Wang, J., & Xu, W."
ARXIV_ID = "2609.11115"
ARXIV_URL = f"https://arxiv.org/abs/{ARXIV_ID}"
DOI = f"10.48550/arXiv.{ARXIV_ID}"
CITE_URL = "https://benchmark-radar.org/#cite"


def apa_citation() -> str:
    return f"{AUTHORS_APA} ({PUBLICATION_YEAR}). {TITLE}. arXiv:{ARXIV_ID}. {ARXIV_URL}"


def cite_reminder() -> str:
    """Footer text for a finished CLI command (issue #483).

    No leading or trailing blank lines: callers decide the spacing.
    """
    return (
        "If Benchmark Radar helped your work, please cite it:\n"
        f"  {apa_citation()}\n"
        f"  More citation formats: {CITE_URL}"
    )
