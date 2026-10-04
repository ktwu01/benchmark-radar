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
- phrases such as "blood-brain barrier" are masked out before matching,
  so one incidental mention cannot add or remove a tag; only genre
  markers (PathMap hypothesis records, species descriptions) veto a record.

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
from typing import Any, Final, NamedTuple

# One entry per domain: ``match`` patterns, any one of which tags the
# record, and ``exclude`` patterns, any one of which vetoes the domain
# for that record. Patterns are lowercase regex fragments anchored at a
# word start; embed ``\\b`` in a fragment to close its right edge.
_RULES: Final[dict[str, dict[str, tuple[Any, ...]]]] = {
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
            # fire. Hyphenated, spaced, and en-dashed compounds -- brain-
            # wide, mouse brain, brain-computer/machine interface,
            # brain-to-text -- all still match, because any separator
            # after "brain" is a word boundary; only digit compounds
            # (brain2text) close the boundary, and those have their own
            # pattern below. The closed-compound benchmark name is listed
            # separately.
            r"brain\b",
            r"brainbench\b",
            # The brain-to-X neural-decoding naming family: Brain2Text,
            # Brain2Voice, Brain2Qwerty (fMRI-to-keyboard), and any later
            # brain2X variant. "brain\b" can never reach these: digits are
            # word characters, so no boundary exists between "brain" and
            # "2". The separator spelling ("brain-to-text") needs no
            # pattern of its own -- see the brain\b note above.
            r"brain2\w+",
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
            # Bare "MEG" is not safe as an acronym: the corpus carries an
            # AI-evaluation initiative whose name is also MEG ("meg-
            # initiative/meg-inspect-eval", Codex round 2). The abbreviation
            # only counts next to a recording/data word; the full technique
            # name below carries the rest.
            r"meg[-/ ](?:eeg|data|recording|recordings|signals?|sources?|stud(?:y|ies)|"
            r"systems?|sensors?)",
            # ECoG has the same collision: "ECOG performance status" is the
            # oncology score (owner review, current-corpus audit). The
            # abbreviation requires an electrophysiology collocate; the full
            # name below carries the rest.
            r"ecog[-/ ]?(?:eeg|signals?|recordings?|electrodes?|data|based)",
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
            # Plural only: neuroscience writes "decoding neural signals",
            # while the metaphorical estimator sense ("the model's neural
            # signal is volatility filtering in disguise", a GARCH finance
            # record, Codex round 2) is singular.
            r"neural signals\b",
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
            # neuro records put the word -- minus corticosteroids, the
            # drug class (owner review: RISANCROHN, Hidradenitis).
            r"cortic(?!oster)",
            # Brain-region stems that no product or other anatomy shares.
            r"hippocamp",
            r"prefrontal",
            r"intracranial",
            r"calcium imaging",
            r"optogenetic",
        ),
        # Terms that count only when the record carries no context from
        # ``unless``. Cardiac electrophysiology is the other big user of
        # this stem (ECGQuest, the Bulgarian EP registry, an epicardial
        # atrial-fibrillation mesh), so cardiac words disarm this one term
        # and leave every other match standing: an EEG record that mentions
        # ECG screening keeps its tag.
        "conditional": (
            (
                r"electrophysiolog",
                r"cardi|\batri(?:al|um)\b|ablation|interventional electrophysiolog",
            ),
        ),
        # Phrases blanked out before matching: each one is a non-neuro
        # sense of a matched word, so removing the phrase leaves the rest
        # of the record to speak for itself (owner review: a single
        # incidental "blood-brain barrier" must not untag an EEG paper).
        # "as the brain of" / "brain-inspired" / "brain-like" / "share one
        # brain" / "brain accomplishes": computing metaphors. "no new
        # neuroscience": FluctlightDB's explicit disclaimer. "brain
        # natriuretic peptide": the cardiac hormone (NT-proBNP). "brain
        # targeting" / "brain delivery": pharma drug-delivery framing.
        # "cortical bone/porosity/thickness": orthopedic cortex.
        "mask": (
            r"blood[- ]brain barrier",
            r"as the brain of",
            r"brain[- ]inspired",
            r"brain[- ]like",
            r"share (?:one|a) brain",
            r"brain accomplishes",
            r"no new neuroscien\w*",
            r"brain natriuretic peptide",
            r"brain targeting",
            r"brain delivery",
            r"cortical (?:bone|porosity|thickness)",
        ),
        # Genre markers that veto the whole record: the genre itself is
        # not neuroscience whatever vocabulary it borrows. "pathmap
        # experiment": auto-generated hypothesis datasets naming gut/lung-
        # brain axes. "sp. nov." / "gen. nov.": species descriptions (a
        # fungus with "cortical cells of roots"). "analytical method
        # development": pharma QC reviews naming neuro indications.
        "veto": (
            r"pathmap experiment",
            r"(?:sp|spp|gen)\. nov",
            r"analytical method development",
        ),
    },
}

# Order here is the published tag order; keep it stable.
SCIENCE_DOMAINS: Final[tuple[str, ...]] = tuple(_RULES)

_WORD_START: Final[str] = r"(?<![a-z0-9])"


def _alternation(patterns: tuple[str, ...]) -> re.Pattern[str] | None:
    # The word-start lookbehind must sit in front of the whole
    # alternation, not just its first branch, or later branches such as
    # "eeg\b" lose their left anchor.
    if not patterns:
        return None
    return re.compile(_WORD_START + "(?:" + "|".join(f"(?:{p})" for p in patterns) + ")")


class _Domain(NamedTuple):
    name: str
    match: re.Pattern[str] | None
    conditional: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...]
    mask: re.Pattern[str] | None
    veto: re.Pattern[str] | None


_COMPILED: Final[tuple[_Domain, ...]] = tuple(
    _Domain(
        domain,
        _alternation(rules["match"]),
        tuple((_alternation((term,)), re.compile(unless)) for term, unless in rules["conditional"]),
        _alternation(rules["mask"]),
        _alternation(rules["veto"]),
    )
    for domain, rules in _RULES.items()
)


def _declares(domain: _Domain, haystack: str) -> bool:
    if domain.veto and domain.veto.search(haystack):
        return False
    text = domain.mask.sub(" ", haystack) if domain.mask else haystack
    if domain.match and domain.match.search(text):
        return True
    return any(term.search(text) and not unless.search(text) for term, unless in domain.conditional)


def derive_science_domains(title: str, summary: str = "") -> list[str]:
    """Return the science domains a record's own text declares.

    Matching is deterministic over the lowercased ``title + summary``
    only -- the same discipline as ``score_item``, which refuses to
    score text a connector generated. Records that declare no domain
    get ``[]``, which stays distinct from "not yet derived".
    """
    haystack = f"{title} {summary}".casefold()
    return [domain.name for domain in _COMPILED if _declares(domain, haystack)]


def science_domains_for_record(record: Mapping[str, object]) -> list[str]:
    """Derive the tag list straight from a stored evidence-item dict."""
    return derive_science_domains(
        str(record.get("title") or ""),
        str(record.get("summary") or ""),
    )
