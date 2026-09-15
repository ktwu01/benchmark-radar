"""Deterministic science-domain tags for radar evidence records.

A science-domain tag is a routing signal, not a quality claim: like the
watchlist, it decides where a record is surfaced (the future "AI for
Science" view and its domain filters) and never changes any score. The
rules therefore stay out of ``taxonomy:``, where every category both
grants publication eligibility and adds +20 relevance (see
``pipeline.score_item``).

The same derivation runs in two places on purpose (issue #511 review,
BLOCKER fix): ``snapshots.dashboard_data`` for the published
``radar.json`` and ``query.QueryService`` for the local search/CLI/HTTP
surfaces. QueryService must not depend on ``config.yml`` because
installed offline clients ship only the package and its data files, so
the rule set lives here as reviewed constants -- the same precedent as
the scoring weights in ``rubric.py`` -- and both surfaces call this one
function. Snapshots are never rewritten: historical records light up
because derivation replays over their stored ``title``/``summary``.

Precision red lines, locked by ``tests/test_science_domains.py``:

- bare "neural" is never a trigger, so ordinary neural-network papers
  stay untagged; only compounds such as "neural decoding" appear;
- acronym terms (EEG, MEG, ECoG, fMRI, BCI, SSVEP, P300) are word
  anchored on both sides so "megabyte" cannot match "meg";
- "blood-brain barrier" and friends are excluded for neuroscience
  because the corpus contains auto-generated hypothesis "datasets"
  whose only neuro word is that phrase (PathMap records).

The rule set is deliberately a first slice -- one merged "neuroscience"
domain that includes BCI (brain-computer interfaces are a subfield, and a
single facet keeps the future filter from splitting an already small set
of records). The vocabulary came from a domain review (issue #511):
prosthetics and hardware terms (neuroprosthesis, Utah array), recording
modalities (sEEG, fNIRS, calcium imaging, optogenetics), full technique
names (electroencephalography, electrocorticography), and unambiguous
brain-region stems (hippocampal, prefrontal). Deliberately still absent:
"neuromorphic" (bio-inspired chips, not brain science), bare "electrode"
and "ERP" (ambiguous outside neuroscience). New domains (climate,
materials, ...) extend ``_RULES`` and gain their own measured precision
pass before shipping.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

# One entry per domain: ``match`` patterns, any one of which tags the
# record, and ``exclude`` patterns, any one of which vetoes the domain
# for that record. Patterns are lowercase regex fragments anchored at a
# word start; embed ``\\b`` in a fragment to close its right edge.
_RULES: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    # One merged domain: BCI vocabulary lives here rather than in its own
    # facet because "bci"-only records were a handful per month -- too few
    # to power a separate filter, but exactly the records a merged
    # neuroscience facet most wants to catch.
    "neuroscience": {
        "match": (
            # Word stems: "neuroscien" covers neuroscience/scientist/
            # scientific, "neuroimag" neuroimaging, and so on. Bare
            # "neural" and bare "neuron" are intentionally absent: both
            # appear inside architecture prose ("neural networks", "neuron
            # counts" for layer sizes) and inside Romance-language neural-
            # network names ("red neuronal"), which are the corpus's
            # highest-volume false positives. Records whose subject really
            # is neurons say brain/cortex/EEG/decoding somewhere too.
            r"neuroscien",
            r"neuroimag",
            r"neurophysiolog",
            r"neurobiolog",
            # Neuroprosthetics (speech neuroprosthesis et al.); hyphen
            # optional for "neuro-prosthesis".
            r"neuro[- ]?prosthe",
            # Right edge closed so "brainstorm"/"brainstorming" cannot
            # fire; hyphenated and spaced compounds (brain-wide, mouse
            # brain) still match, and the closed compound benchmark name
            # is listed separately.
            r"brain\b",
            r"brainbench\b",
            # Both interface spellings, hyphen/space/en-dash separated.
            r"brain[-–— ](?:computer|machine) interface",
            # The brain-to-X neural-decoding naming family: Brain2Text,
            # Brain2Voice, Brain2Qwerty (fMRI-to-keyboard), and any later
            # brain2X variant, plus the "brain-to-text" spelling. "brain\b"
            # can never reach these: digits are word characters, so no
            # boundary exists between "brain" and "2".
            r"brain2\w+",
            r"brain[-–— ]to[-–— ]\w+",
            r"bci\b",
            r"motor imagery",
            r"neural interface",
            # Recording modalities and hardware (sEEG is stereotactic EEG;
            # the Utah array is the classic intracortical electrode).
            r"ssvep\b",
            r"p300\b",
            r"fnirs\b",
            r"seeg\b",
            r"utah array",
            r"eeg\b",
            r"meg\b",
            r"ecog\b",
            r"fmri\b",
            # Full technique names behind the acronyms above. The bare stem
            # "encephalograph" cannot reach the two real technique names --
            # the word-start lookbehind stops it matching inside
            # "electroencephalography" -- so both full forms are explicit
            # (Codex review, PR #647).
            r"electroencephalograph",
            r"magnetoencephalograph",
            r"electrocorticograph",
            r"encephalograph",
            r"neural decoding",
            r"neural encoding",
            r"neural signal",
            r"neural activity",
            # Spiking in biological tissue, not the SNN/neuromorphic
            # architecture sense: "spiking neural networks" and
            # "spiking-inspired" describe artificial models (Codex review,
            # PR #647), so the bare stem is gone and only tissue-level
            # phrases remain.
            r"spiking neurons?\b",
            r"neural spiking",
            r"spike trains?\b",
            r"spike sorting",
            r"connectome",
            # Bare "cortex" is deliberately absent: in the live corpus its
            # every hit was a product name (Snowflake Cortex) or anatomy
            # (adrenal cortex), never brain cortex. The "cortic" stem still
            # reaches cortical / cortico- compounds, which is where real
            # neuro records put the word.
            r"cortic",
            # Brain-region stems that no product or other anatomy shares.
            r"hippocamp",
            r"prefrontal",
            r"intracranial",
            r"calcium imaging",
            r"optogenetic",
            r"electrophysiolog",
        ),
        # "blood-brain barrier": auto-generated PathMap hypothesis records
        # talk about the barrier without being neuroscience artifacts. The
        # veto is whole-domain for now; a real record whose only neuro
        # evidence is this phrase is a chemoinformatics candidate, so losing
        # the tag is the safer error until measured otherwise.
        # "as the brain of": the agent-as-brain metaphor ("the LLM acts as
        # the brain of a simulated humanoid"), a live-corpus false positive
        # where "brain" describes computation, not tissue.
        # "brain-inspired" / "brain-like": neuromorphic-computing framing,
        # the same metaphor class (Codex review, PR #647: "Pathway's
        # brain-inspired architecture development").
        # "sp. nov." / "gen. nov.": species-description genre markers. A
        # fungal taxonomy record can mention "cortical cells of roots"
        # without being neuroscience; genus/species novelty is the paper-
        # genre marker that separates it, the same genre-marker pattern the
        # main taxonomy uses for surveys (Codex review, PR #647).
        "exclude": (
            r"blood[- ]brain barrier",
            r"as the brain of",
            r"brain[- ]inspired",
            r"brain[- ]like",
            r"(?:sp|spp|gen)\. nov",
        ),
    },
}

# Order here is the published tag order; keep it stable.
SCIENCE_DOMAINS: Final[tuple[str, ...]] = tuple(_RULES)

_WORD_START: Final[str] = r"(?<![a-z0-9])"
_COMPILED: Final[tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...]] = tuple(
    (
        domain,
        # The word-start lookbehind must sit in front of the whole
        # alternation, not just its first branch, or later branches
        # such as "eeg\b" lose their left anchor.
        re.compile(
            _WORD_START + "(?:" + "|".join(f"(?:{pattern})" for pattern in rules["match"]) + ")"
        ),
        re.compile("|".join(f"(?:{pattern})" for pattern in rules["exclude"]))
        if rules["exclude"]
        else None,
    )
    for domain, rules in _RULES.items()
)


def derive_science_domains(title: str, summary: str = "") -> list[str]:
    """Return the science domains a record's own text declares.

    Matching is deterministic over the lowercased ``title + summary``
    only -- the same discipline as ``score_item``, which refuses to
    score text a connector generated. Records that declare no domain
    get ``[]``, which stays distinct from "not yet derived".
    """
    haystack = f"{title} {summary}".casefold()
    return [
        domain
        for domain, match, exclude in _COMPILED
        if match.search(haystack) and not (exclude and exclude.search(haystack))
    ]


def science_domains_for_record(record: Mapping[str, object]) -> list[str]:
    """Derive the tag list straight from a stored evidence-item dict."""
    return derive_science_domains(
        str(record.get("title") or ""),
        str(record.get("summary") or ""),
    )
