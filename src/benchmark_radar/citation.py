"""Single source of truth for the project's self-citation (issue #483).

The version comes from the ``__version__`` constant in
``benchmark_radar/__init__.py`` (not importlib metadata), so a release
bumps the citation without a separate edit; the year and DOI are stable
because the technical report is deposited once. CITATION.cff and the
site copy blocks in app_seeds.py keep the same author set, so every
citation surface stays in step under this module's author list.
"""

from __future__ import annotations

from . import __version__

PUBLICATION_YEAR = "2026"
AUTHORS_APA = "Wu, K., & Zhou, J."
DOI = "10.5281/zenodo.22167102"
CITE_URL = "https://benchmark-radar.org/#cite"


def apa_citation() -> str:
    return (
        f"{AUTHORS_APA} ({PUBLICATION_YEAR}). Benchmark Radar v{__version__}: Technical Report "
        f"(Version {__version__}). https://doi.org/{DOI}"
    )


def cite_reminder() -> str:
    """Footer text for a finished CLI command (issue #483).

    No leading or trailing blank lines: callers decide the spacing.
    """
    return (
        "If Benchmark Radar helped your work, please cite it:\n"
        f"  {apa_citation()}\n"
        f"  More citation formats: {CITE_URL}"
    )
