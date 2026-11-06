"""Type a `released` evidence record before Latest releases treats it as a benchmark.

Issue #902: discovery matches keywords such as "benchmark" and "evaluat" in
abstracts, so a model paper that merely evaluates on benchmarks, a training
method, and a GitHub version tag all arrive as `event_kind == "released"` with a
`benchmark` category. The Latest releases view promises new benchmarks, so it
asks this module what the record's headline contribution is.

Only a positive finding excludes a record: a software version tag, or a paper
whose own introduction sentence names a model, a method, an agent, or a harness
before any benchmark.
A record with no clear headline stays eligible, so an unfamiliar benchmark is
never dropped for lack of a recognised phrase. This type is read at display
time only. The record stays in the corpus, in search, and in every count.
"""

from __future__ import annotations

import re
from typing import Any

BENCHMARK = "benchmark"
MODEL = "model"
METHOD = "method"
SOFTWARE_RELEASE = "software_release"
AGENT = "agent"
HARNESS = "harness"
UNCLEAR = "unclear"

NON_BENCHMARK_KINDS: frozenset[str] = frozenset({MODEL, METHOD, SOFTWARE_RELEASE, AGENT, HARNESS})

# A version tag of a followed repository (OpenClaw 2026.8.34, an mteb patch
# release) says the software shipped, not that a new benchmark exists.
_SOFTWARE_RELEASE_SOURCES = frozenset({"github release"})

_TITLE_BENCHMARK = re.compile(
    r"bench|dataset|corpus|\bgym\b|\barena\b|leaderboard|testbed|test suite|\beval\w*|assess\w*",
    re.IGNORECASE,
)

# The first contribution noun decides: "a benchmark framework" is a benchmark,
# "a general training framework" is a method, and "a unified agent" is an agent.
# Agent/harness matches are limited to the descriptor, before its elaboration.
# A benchmark noun anywhere in the coordinated descriptor still wins, so
# "an agent benchmark" stays a benchmark.
_BENCHMARK_NOUN = (
    r"evaluation (?:suite|framework|protocol|platform|harness)|benchmark\w*|dataset|corpus"
    r"|testbed|test suite|test set|leaderboard|\bgym\b|\barena\b"
)
_MODEL_NOUN = (
    r"(?:foundation |language |vision-language |multimodal |generative |reasoning )*"
    r"(?:model|models|llm|vlm|mllm)\b"
)
_METHOD_NOUN = (
    r"framework|method|approach|network|architecture|algorithm|training|pipeline|recipe"
    r"|paradigm|technique|mechanism|module|objective|optimi[sz]\w*|system"
)
_AGENT_NOUN = r"\bagents?\b"
_HARNESS_NOUN = r"\bharness(?:es)?\b"
_HEADLINE_NOUN = re.compile(
    rf"(?P<benchmark>{_BENCHMARK_NOUN})|(?P<model>{_MODEL_NOUN})|(?P<method>{_METHOD_NOUN})",
    re.IGNORECASE,
)
_AGENT_OR_HARNESS = re.compile(
    rf"(?P<agent>{_AGENT_NOUN})|(?P<harness>{_HARNESS_NOUN})",
    re.IGNORECASE,
)
_INTRODUCES = re.compile(
    r"\bwe\s+(?:\w+\s+)?(?:introduce|present|propose|release|construct|build|curate|develop"
    r"|contribute|design)\b(?P<rest>[^.]*)",
    re.IGNORECASE,
)

_ARTICLE_START = re.compile(r"\s*(?:a|an|the|new|first|our)\b", re.IGNORECASE)

# Words that end the descriptor and start its elaboration.
_HEAD_END = re.compile(
    r"\s(?:of|for|that|which|to|with|in|on|from|by|via|using|where|trained|built)\s",
    re.IGNORECASE,
)


def _headline_kind(summary: str) -> str | None:
    """The kind of the first thing the abstract says its authors introduce."""
    match = _INTRODUCES.search(summary)
    if match is None:
        return None
    rest = match.group("rest")
    # "We introduce <Name>, a <descriptor>": words inside the name ("World
    # Models' Last Exam") are not its type, so read the descriptor after the comma.
    name, comma, descriptor = rest.partition(",")
    if comma and not _ARTICLE_START.match(name):
        rest = descriptor
    # "a training source and benchmark": a benchmark noun anywhere in the
    # coordinated descriptor makes the record a benchmark.
    head = _HEAD_END.split(rest, maxsplit=1)[0]
    if re.search(_BENCHMARK_NOUN, head, re.IGNORECASE):
        return BENCHMARK
    noun = _HEADLINE_NOUN.search(rest)
    # Only the descriptor can identify an agent/harness contribution. Mentions
    # in elaboration can instead name evaluation targets (e.g. CABRA).
    introduced_agent = _AGENT_OR_HARNESS.search(head)
    if introduced_agent is not None and (noun is None or introduced_agent.start() < noun.start()):
        noun = introduced_agent
    if noun is None:
        return None
    for kind in (BENCHMARK, MODEL, METHOD, AGENT, HARNESS):
        if noun.lastgroup == kind:
            return kind
    return None


def classify_release_record(item: dict[str, Any]) -> str:
    """Return benchmark, model, method, agent, harness, software_release, or unclear."""
    source = str(item.get("source") or "").strip().casefold()
    parser = str(item.get("parser_version") or "")
    if source in _SOFTWARE_RELEASE_SOURCES or parser.startswith("github-releases/"):
        return SOFTWARE_RELEASE

    title = str(item.get("title") or "")
    if _TITLE_BENCHMARK.search(title):
        return BENCHMARK

    kind = _headline_kind(str(item.get("summary") or ""))
    return kind or UNCLEAR


def is_benchmark_release(item: dict[str, Any]) -> bool:
    """Whether a `released` record may stand for a new benchmark release."""
    return classify_release_record(item) not in NON_BENCHMARK_KINDS
