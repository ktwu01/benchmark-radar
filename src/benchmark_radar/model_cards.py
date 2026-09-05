"""Model Card Adoption Rank: which benchmarks frontier model cards actually report.

Issue #83 asked for a queryable registry of every benchmark result in every
model card, keyed by evaluation configuration. That is the right destination and
the wrong first step: it cannot produce a single row until a per-vendor PDF
parser exists, and every row it did produce would carry a score that is
incomparable to the score beside it.

This module implements the tractable core of that idea. It counts *mentions*,
not scores. A mention is the one fact that survives the configuration caveats
the issue itself raises: it does not matter whether a card ran AIME at pass@1 or
consensus@64 with a Python tool, the card still chose to put AIME in front of
its readers. Adoption is therefore a claim about vendor attention, and this
module is careful never to present it as a claim about benchmark quality.

The counted unit is the document, not the result row. A card reporting AIME in
four configurations adds one to AIME's adoption count, exactly like a card
reporting it once, so a verbose appendix cannot outvote a different vendor.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

# The single date format JavaScript's Date constructor parses reliably. See
# `_require_date` for why the ISO 8601 standard is too wide a target here.
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

REGISTRY_SCHEMA_VERSION = 1

DEFAULT_REGISTRY_PATH = Path("data/model_cards.yml")

# Domains carry no ordering: `math` is not above or below `coding`. They exist
# so a reader can ask "what does this field measure" without the leaderboard
# implying a hierarchy between fields.
#
# `caveat` is required, not optional. The ranking's headline risk is being read
# as a quality ordering, and the per-row caveat is what stops a saturated or
# contaminated benchmark from sitting near the top with no qualification. A
# registry that may omit it can publish exactly the misreading this feature is
# built to prevent, so the guarantee is enforced for any registry rather than
# spot-checked on the shipped one.
_REQUIRED_BENCHMARK_FIELDS = ("id", "name", "domain", "caveat")
_REQUIRED_CARD_FIELDS = ("id", "organization", "model", "url", "benchmarks")
_REQUIRED_SOURCE_DOCUMENT_FIELDS = ("id", "name", "url", "document_type", "benchmarks")


def _benchmark_summary(benchmark: dict[str, Any]) -> dict[str, Any]:
    """The benchmark fields that travel with a card in the card->benchmark link.

    Deliberately the same projection used to build the leaderboard entry, so the
    two directions of the link cannot describe one benchmark differently.
    """
    return {
        "benchmark_id": str(benchmark["id"]),
        "name": str(benchmark["name"]),
        "domain": str(benchmark["domain"]),
        "url": str(benchmark.get("url") or "") or None,
        "released": str(benchmark["released"]) if benchmark.get("released") else None,
        "caveat": (str(benchmark["caveat"]).strip() if benchmark.get("caveat") else None),
    }


class _descending:
    """Sort one key in reverse while its tie-breakers stay ascending.

    `sorted(reverse=True)` reverses the whole tuple, which would also flip
    organization and model into Z-to-A for cards sharing a date. Negating the
    key is the usual alternative and is unavailable here: these are ISO date
    strings, not numbers. Wrapping just the date inverts that one comparison
    and leaves the rest of the tuple alone.
    """

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _descending):
            return NotImplemented
        return self.value == other.value

    def __lt__(self, other: _descending) -> bool:
        return other.value < self.value


class ModelCardRegistryError(ValueError):
    """Raised when the curated registry is internally inconsistent."""


def _require(value: Any, fields: tuple[str, ...], *, label: str) -> None:
    if not isinstance(value, dict):
        raise ModelCardRegistryError(f"{label} must be a mapping")
    # A whitespace-only string is a missing field, not a present one: it
    # satisfies a truthiness check while carrying no information for a reader.
    missing = [
        field
        for field in fields
        if not value.get(field) or (isinstance(value[field], str) and not value[field].strip())
    ]
    if missing:
        raise ModelCardRegistryError(f"{label} is missing fields: {', '.join(missing)}")


def _require_date(value: Any, *, label: str) -> None:
    """Reject a date the browser cannot format.

    These values reach `Intl.DateTimeFormat` unmodified, and it throws a
    RangeError on an unparseable one. The dashboard's initialization catch
    treats that as an unusable data file and hides *every* view, so a single
    typo in one optional field would take Today and Trends down with the
    leaderboard. Failing the build here keeps that blast radius at zero.

    `date.fromisoformat` alone is too permissive to protect that: on Python
    3.11+ it also accepts `20250807` and `2025-W32-4`, both of which are valid
    ISO 8601 and both of which JavaScript's Date parses to Invalid Date. The
    check is therefore against the one format the browser accepts, not against
    the standard.
    """
    # `datetime` subclasses `date`, and PyYAML returns one for any value
    # carrying a time. It would serialize as "2025-08-07 00:00:00+05:30", which
    # the dashboard's UTC formatter renders as August 6: a silently wrong date
    # rather than a rejected one. Only a plain calendar date is accepted.
    if type(value) is date:
        return
    text = str(value)
    if not _ISO_DATE.fullmatch(text):
        raise ModelCardRegistryError(f"{label} must be an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ModelCardRegistryError(f"{label} is not a real calendar date") from error


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    """Read and validate the curated model card registry.

    Validation is strict on purpose. The leaderboard's only claim is "this many
    distinct cards reported this benchmark", and a benchmark id that appears in
    a card but not in the benchmark block would silently create a phantom entry
    with an adoption count of one. That is indistinguishable from a real
    benchmark nobody adopted, so it is rejected rather than tolerated.
    """
    if not path.exists():
        raise ModelCardRegistryError(f"{path}: registry file not found")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ModelCardRegistryError(f"{path}: registry must be a mapping")
    version = document.get("schema_version")
    if version != REGISTRY_SCHEMA_VERSION:
        raise ModelCardRegistryError(f"{path}: unsupported schema_version {version!r}")

    benchmarks = document.get("benchmarks")
    cards = document.get("model_cards")
    source_documents = document.get("source_documents", [])
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ModelCardRegistryError(f"{path}: benchmarks must be a non-empty array")
    if not isinstance(cards, list) or not cards:
        raise ModelCardRegistryError(f"{path}: model_cards must be a non-empty array")
    if not isinstance(source_documents, list):
        raise ModelCardRegistryError(f"{path}: source_documents must be an array")

    by_id: dict[str, dict[str, Any]] = {}
    for index, benchmark in enumerate(benchmarks):
        _require(benchmark, _REQUIRED_BENCHMARK_FIELDS, label=f"{path}: benchmark {index}")
        benchmark_id = str(benchmark["id"])
        if benchmark_id in by_id:
            raise ModelCardRegistryError(f"{path}: duplicate benchmark id {benchmark_id!r}")
        # `aliases: SWE-bench Verified` is the natural thing to write and is a
        # YAML scalar, which iterates per character: the published registry
        # would carry ['S', 'W', 'E', ...] and every alias search would miss,
        # silently rather than loudly.
        if benchmark.get("aliases") is not None and not isinstance(benchmark["aliases"], list):
            raise ModelCardRegistryError(
                f"{path}: benchmark {benchmark_id!r} aliases must be a list"
            )
        # Validated on the same terms as a card's dates: `released` is rendered
        # by the same browser formatter and is filterable, so an unparseable
        # value here would take the whole dashboard down exactly as one in
        # `published` would.
        if benchmark.get("released"):
            _require_date(
                benchmark["released"], label=f"{path}: benchmark {benchmark_id!r} released"
            )
        by_id[benchmark_id] = benchmark

    seen_cards: set[str] = set()
    seen_urls: dict[str, str] = {}
    for index, card in enumerate(cards):
        _require(card, _REQUIRED_CARD_FIELDS, label=f"{path}: model card {index}")
        card_id = str(card["id"])
        if card_id in seen_cards:
            raise ModelCardRegistryError(f"{path}: duplicate model card id {card_id!r}")
        seen_cards.add(card_id)
        # The counting unit is the document, so the same document entered twice
        # under two ids would add two adoptions to every benchmark it lists and
        # reorder the ranking. A distinct id is not evidence of a distinct
        # document; the URL is what identifies one.
        url = str(card["url"])
        # Compared without the fragment: `#results` names a location inside a
        # document, not a different document, so the two forms are one card
        # and must not each add an adoption.
        key = urlsplit(url)._replace(fragment="").geturl()
        if key in seen_urls:
            raise ModelCardRegistryError(
                f"{path}: model card {card_id!r} repeats the document URL already "
                f"registered by {seen_urls[key]!r}: {url}"
            )
        seen_urls[key] = card_id
        if not isinstance(card["benchmarks"], list):
            raise ModelCardRegistryError(
                f"{path}: model card {card_id!r} benchmarks must be a list"
            )
        unknown = sorted({str(ref) for ref in card["benchmarks"]} - by_id.keys())
        if unknown:
            raise ModelCardRegistryError(
                f"{path}: model card {card_id!r} references unknown benchmarks: "
                f"{', '.join(unknown)}"
            )
        if not str(card["url"]).startswith(("https://", "http://")):
            raise ModelCardRegistryError(f"{path}: model card {card_id!r} url must be HTTP(S)")
        for field in ("published", "retrieved_at"):
            if card.get(field):
                _require_date(card[field], label=f"{path}: model card {card_id!r} {field}")

        # A card cannot report a benchmark that did not exist when it was
        # published. Every date here is individually well-formed, so nothing
        # above catches the contradiction, and the resulting edge is invisible in
        # the ranking: it just quietly adds one adoption. Three such edges were
        # in the first draft of the 2026 expansion, each a different mistake --
        # a wrong `released` date, and two benchmarks attributed to cards that
        # reported a different instrument. Checking the pair is what tells those
        # apart from correct data.
        #
        # Compared as ISO strings, and only when both dates are present: a
        # benchmark with no recorded release date cannot be placed on the
        # timeline, so it is not evidence of anything either way.
        #
        # `revised` is the escape hatch for a document that legitimately gained a
        # benchmark after first publication: an arXiv report reaching v3, or a
        # living model card a vendor keeps editing in place. Those are real, and
        # for them `published` is the original date while the contents are newer.
        # It is opt-in per card rather than a blanket relaxation, because the
        # common case is still a data error and silently allowing every later
        # benchmark would give back the three edges this check just caught. A
        # card claiming a revision must name the date it was revised to, which is
        # a checkable claim about the document.
        published = str(card["published"]) if card.get("published") else ""
        if card.get("revised"):
            _require_date(card["revised"], label=f"{path}: model card {card_id!r} revised")
            if published and str(card["revised"]) < published:
                raise ModelCardRegistryError(
                    f"{path}: model card {card_id!r} revised {card['revised']} "
                    f"precedes its published date {published}"
                )
        # The revision date is the cutoff when one is recorded: the document as
        # read at that point is what the mentions were taken from.
        cutoff = str(card["revised"]) if card.get("revised") else published
        if cutoff:
            impossible = sorted(
                f"{ref} (released {by_id[ref]['released']})"
                for ref in {str(ref) for ref in card["benchmarks"]}
                if by_id[ref].get("released") and str(by_id[ref]["released"]) > cutoff
            )
            if impossible:
                raise ModelCardRegistryError(
                    f"{path}: model card {card_id!r} ({cutoff}) reports benchmarks "
                    f"released after it: {', '.join(impossible)}. If the document was "
                    f"revised after publication, record the revision date as `revised`"
                )

    seen_documents: set[str] = set(seen_cards)
    for index, source in enumerate(source_documents):
        label = f"{path}: source document {index}"
        _require(source, _REQUIRED_SOURCE_DOCUMENT_FIELDS, label=label)
        source_id = str(source["id"])
        if source_id in seen_documents:
            raise ModelCardRegistryError(f"{path}: duplicate source document id {source_id!r}")
        seen_documents.add(source_id)
        if not str(source["url"]).startswith(("https://", "http://")):
            raise ModelCardRegistryError(f"{label} url must be HTTP(S)")
        if not isinstance(source["benchmarks"], list):
            raise ModelCardRegistryError(f"{label} benchmarks must be a list")
        unknown = sorted({str(ref) for ref in source["benchmarks"]} - by_id.keys())
        if unknown:
            raise ModelCardRegistryError(
                f"{label} references unknown benchmarks: {', '.join(unknown)}"
            )
        if str(source["document_type"]) != "benchmark_leaderboard":
            raise ModelCardRegistryError(
                f"{label} must use non-adoption document_type 'benchmark_leaderboard'"
            )
        key = urlsplit(str(source["url"]))._replace(fragment="").geturl()
        if key in seen_urls:
            raise ModelCardRegistryError(f"{label} repeats a registered document URL")
        seen_urls[key] = source_id
        for field in ("published", "retrieved_at"):
            if source.get(field):
                _require_date(source[field], label=f"{label} {field}")

    return {
        "benchmarks": benchmarks,
        "model_cards": cards,
        "source_documents": source_documents,
    }


def adoption_rank(registry: dict[str, Any]) -> dict[str, Any]:
    """Rank benchmarks by how many distinct model cards report them.

    Two counts are published side by side and neither is the "real" one:

    ``card_count``
        How many documents report the benchmark. This is the headline: it is
        what "popular in model cards" literally means.
    ``organization_count``
        How many distinct publishers report it. A benchmark carried by six
        cards from one vendor is a house style; the same six cards from six
        vendors is a shared standard. Ranking on cards alone cannot tell those
        apart, so the organization count breaks ties and is shown next to the
        headline rather than folded into it.

    Ordering is total and deterministic: cards, then organizations, then name.
    No score is combined out of the two, because any weighting would be an
    invented judgement presented as a measurement.
    """
    cards = registry["model_cards"]
    benchmarks = {str(benchmark["id"]): benchmark for benchmark in registry["benchmarks"]}

    card_counts: Counter[str] = Counter()
    organizations: dict[str, set[str]] = {}
    adopters: dict[str, list[dict[str, Any]]] = {}

    for card in cards:
        organization = str(card["organization"])
        # A set: a card listing the same benchmark twice, or listing two
        # aliases that resolve to one id, still counts once.
        for benchmark_id in sorted({str(ref) for ref in card["benchmarks"]}):
            card_counts[benchmark_id] += 1
            organizations.setdefault(benchmark_id, set()).add(organization)
            adopters.setdefault(benchmark_id, []).append(
                {
                    "model_card_id": str(card["id"]),
                    "organization": organization,
                    "model": str(card["model"]),
                    "document_type": str(card.get("document_type") or "model_card"),
                    "published": str(card["published"]) if card.get("published") else None,
                    "url": str(card["url"]),
                }
            )

    total_cards = len(cards)
    entries = []
    for benchmark_id, benchmark in benchmarks.items():
        count = card_counts.get(benchmark_id, 0)
        entries.append(
            {
                "benchmark_id": benchmark_id,
                "name": str(benchmark["name"]),
                "domain": str(benchmark["domain"]),
                "url": str(benchmark.get("url") or "") or None,
                "aliases": [str(alias) for alias in benchmark.get("aliases") or []],
                # The benchmark's own release date, not any card's. Published so
                # a reader can separate a newly *adopted* benchmark from a newly
                # *published* one, and filter the ranking by instrument age.
                "released": str(benchmark["released"]) if benchmark.get("released") else None,
                # The caveat travels with the row. A ranking that shows MMLU
                # high and does not say "saturated and contaminated" invites
                # exactly the reading issue #83 warns against.
                "caveat": (str(benchmark["caveat"]).strip() if benchmark.get("caveat") else None),
                "card_count": count,
                "organization_count": len(organizations.get(benchmark_id, set())),
                "organizations": sorted(organizations.get(benchmark_id, set())),
                "adoption_share": round(count / total_cards, 4) if total_cards else 0.0,
                "adopters": sorted(
                    adopters.get(benchmark_id, []),
                    key=lambda entry: (
                        entry["organization"],
                        entry["published"] or "",
                        entry["model"],
                    ),
                ),
            }
        )

    entries.sort(
        key=lambda entry: (
            -entry["card_count"],
            -entry["organization_count"],
            entry["name"],
        )
    )
    for position, entry in enumerate(entries, start=1):
        entry["rank"] = position

    organization_totals = Counter(str(card["organization"]) for card in cards)
    domain_totals = Counter(entry["domain"] for entry in entries if entry["card_count"])

    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "model_card_count": total_cards,
        "benchmark_count": len(entries),
        "organization_count": len(organization_totals),
        "organizations": dict(sorted(organization_totals.items())),
        "domains": dict(sorted(domain_totals.items())),
        # Sorted newest first (issue #90). The previous publisher-then-date
        # order grouped a vendor's whole history together, which buried this
        # month's frontier cards under whichever organization sorted first
        # alphabetically: the newest document in the registry sat halfway down
        # the list. Date is what a reader scanning this roster is actually
        # looking for, and it is the one key that is comparable across vendors.
        #
        # A card with no published date sorts last rather than first: `None`
        # means the date was never established, and an unknown date is not
        # evidence of recency. Organization then model break ties so the order
        # stays total and deterministic for cards sharing a date.
        "model_cards": sorted(
            (
                {
                    "model_card_id": str(card["id"]),
                    "organization": str(card["organization"]),
                    "model": str(card["model"]),
                    "document_type": str(card.get("document_type") or "model_card"),
                    "published": str(card["published"]) if card.get("published") else None,
                    "url": str(card["url"]),
                    "retrieved_at": (
                        str(card["retrieved_at"]) if card.get("retrieved_at") else None
                    ),
                    # Published so a reader can see that a document reporting a
                    # benchmark newer than itself is a recorded revision rather
                    # than a mistake nobody caught.
                    "revised": str(card["revised"]) if card.get("revised") else None,
                    "benchmark_count": len({str(ref) for ref in card["benchmarks"]}),
                    "benchmarks": sorted({str(ref) for ref in card["benchmarks"]}),
                    # The reverse of `entries[].adopters`, and the reason this
                    # registry is a dual link rather than two lists that happen
                    # to agree. Both directions are derived here from the same
                    # validated `card["benchmarks"]`, so "which cards report
                    # benchmark X" and "which benchmarks does card Y report"
                    # cannot disagree: `test_adoption_rank_links_are_exact
                    # _inverses` asserts the two edge sets are identical.
                    #
                    # The full record travels, not just the id, so a reader
                    # expanding a card sees each benchmark's domain, release
                    # date and caveat without having to join against `entries`
                    # in the browser.
                    "reported_benchmarks": [
                        _benchmark_summary(benchmarks[benchmark_id])
                        # The id is the final key, not decoration: domain and
                        # lowercased name can both tie between two distinct
                        # benchmarks, and the input is a set, so without a
                        # unique tie-breaker their published order would vary
                        # with PYTHONHASHSEED. The inverse-property test would
                        # not catch it -- it compares sets -- so the ordering
                        # has to be total here.
                        for benchmark_id in sorted(
                            {str(ref) for ref in card["benchmarks"]},
                            key=lambda ref: (
                                benchmarks[ref]["domain"],
                                str(benchmarks[ref]["name"]).lower(),
                                ref,
                            ),
                        )
                    ],
                }
                for card in cards
            ),
            key=lambda card: (
                card["published"] is None,
                _descending(card["published"] or ""),
                card["organization"],
                card["model"],
                # Z.ai published a GLM-5 model card and a GLM-5 technical
                # report on the same day, which ties every key above. Without
                # a unique final key their order would follow their position in
                # the YAML file, so editing an unrelated part of the registry
                # could reorder the published roster. The id is the only field
                # guaranteed distinct.
                card["document_type"],
                card["model_card_id"],
            ),
        ),
        "entries": entries,
        # Stated in the data rather than only in the UI, so any consumer of
        # radar.json inherits the caveat instead of re-deriving the ranking's
        # meaning from its column headers.
        # Plain words on purpose (issue #241): "vendor attention", "saturated"
        # and "contaminated" all named the right ideas in vocabulary a reader
        # has to already have. The claim is unchanged -- a benchmark near the
        # top is one everybody reports, which is not the same as a good one.
        "measures": (
            "When an AI lab releases a model, it publishes a report listing the "
            "tests it ran. This counts how many of those reports mention each "
            "test. A test near the top is one almost everyone runs, which is not "
            "the same as a good one: labs keep running a popular test out of "
            "habit, even after the scores stop telling anyone much."
        ),
    }


def build_adoption_rank(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    return adoption_rank(load_registry(path))
