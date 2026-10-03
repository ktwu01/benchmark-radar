"""Related-work drafting over the local query contract (issues #549, #650).

A paper's related-work section is the job users most often open this tool for
(#522 R2). This module turns a handful of topic queries into a citable draft:
one entry per retained work, each carrying a BibTeX record, the comparison axes
from #650 (paper, repository, dataset, openness), and which topics retrieved it.

Everything here reads the same local artifacts as ``search`` and ``show``. No
network is touched, so an author the snapshots never recorded stays missing and
is reported under ``verification`` instead of being guessed. Retrieval stays
lexical: a topic keeps only candidates that cover every query token unless the
caller opts into partial matches, and the draft says plainly that absence from
this corpus is not evidence of absence from the literature (#522 R3).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .citation import BIBTEX_KEY, bibtex_citation, bibtex_citation_notice, required_citations
from .related_work_render import latex_escape, render_latex, render_markdown

if TYPE_CHECKING:
    from .query import QueryService

MAX_TOPICS = 12
MAX_PER_TOPIC = 30
_SEARCH_WINDOW = 200
_ARXIV_ID = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d])")
_ARXIV_SOURCES = {"arxiv", "hugging face papers"}
_CONTRIBUTION = re.compile(
    r"\b(we (introduce|propose|present|release|build|construct|develop)|"
    r"this (paper|work) (introduces|proposes|presents)|"
    r"is an? (new |large-scale |comprehensive )?(benchmark|dataset|suite|framework))\b",
    re.IGNORECASE,
)
_TITLE_STOPWORDS = frozenset(
    "a an the on of for in to and with via from towards toward when do does can is are "
    "what how why beyond rethinking".split()
)
_MAX_SUMMARY_WORDS = 55
# Radar also records repositories, datasets, and model uploads. A related-work
# draft cites papers, so only these sources become entries by default.
SCHOLARLY_RADAR_SOURCES = frozenset(
    {"arxiv", "hugging face papers", "semantic scholar", "openalex", "crossref"}
)
_LEAD_IN = re.compile(
    r"^(to (address|bridge|fill|close|tackle|overcome|solve)[^,]{0,80}|to this end|"
    r"in this (paper|work|study)|here|therefore|thus|accordingly),\s*",
    re.IGNORECASE,
)
_LATEX_COMMAND = re.compile(r"\\[a-zA-Z]+\{([^{}]*)\}")


@dataclass(frozen=True, slots=True)
class Topic:
    label: str
    query: str


def parse_topic(value: str) -> Topic:
    """Accept ``query`` or ``Label=query``; the label names the paragraph."""
    label, separator, query = str(value).partition("=")
    if not separator:
        query, label = label, label
    label, query = " ".join(label.split()), " ".join(query.split())
    if not query:
        from .query import QueryError

        raise QueryError(f"topic {value!r} has an empty query", code="invalid_query", status=400)
    return Topic(label=label or query, query=query)


def _ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _key_part(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii(value).casefold())


def _arxiv_id(record: dict[str, Any], extra_urls: list[str]) -> str | None:
    if str(record.get("source") or "").casefold() in _ARXIV_SOURCES:
        match = _ARXIV_ID.fullmatch(str(record.get("source_id") or ""))
        if match:
            return match.group(1)
    for url in [str(record.get("url") or ""), *extra_urls]:
        if "arxiv.org/" in url or "huggingface.co/papers/" in url:
            match = _ARXIV_ID.search(url)
            if match:
                return match.group(1)
    return None


def _year(record: dict[str, Any], arxiv_id: str | None) -> str | None:
    if arxiv_id:
        return f"20{arxiv_id[:2]}"
    for field in ("published_at", "released"):
        match = re.match(r"(\d{4})", str(record.get(field) or ""))
        if match:
            return match.group(1)
    return None


def _summary(description: Any) -> str:
    if isinstance(description, dict):
        description = description.get("en") or next(iter(description.values()), "")
    text = " ".join(str(description or "").split())
    text = re.sub(r"\s*See the full description on the dataset page:.*$", "", text)
    letters = [char for char in text if char.isalpha()]
    if letters and sum(ord(char) > 0x24F for char in letters) > len(letters) / 3:
        return ""  # Not Latin-script prose; an English draft cannot restate it.
    text = _LATEX_COMMAND.sub(r"\1", text)
    text = re.sub(r"\s*[\u2014\u2013]\s*", ", ", text).rstrip("\u2026 ").strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    chosen = next((s for s in sentences if _CONTRIBUTION.search(s)), sentences[0])
    stripped = _LEAD_IN.sub("", chosen)
    if stripped != chosen:
        chosen = stripped[:1].upper() + stripped[1:]
    words = chosen.split()
    if len(words) > _MAX_SUMMARY_WORDS:
        chosen = " ".join(words[:_MAX_SUMMARY_WORDS]).rstrip(",;:") + " ..."
    return chosen


def _base_key(entry: dict[str, Any]) -> str:
    year = entry.get("year") or ""
    title_word = next(
        (
            _key_part(word)
            for word in re.split(r"[\s:/-]+", entry["name"])
            if _key_part(word) and _key_part(word) not in _TITLE_STOPWORDS
        ),
        "work",
    )
    if entry["authors"]:
        surname = _key_part(entry["authors"][0].split()[-1]) or "anon"
        return f"{surname}{year}{title_word}"
    return f"{_key_part(entry['name'])[:24] or 'benchmark'}{year}"


def _catalog_entry(service: QueryService, result: dict[str, Any]) -> dict[str, Any]:
    record = service.show(result["key"])["benchmark"]["record"]
    artifacts = record.get("artifacts") or []
    urls = [str(artifact.get("url") or "") for artifact in artifacts]
    arxiv_id = _arxiv_id(result, urls)
    paper_url = next(
        (u for a, u in zip(artifacts, urls, strict=True) if a.get("kind") == "paper"), None
    )
    openness = result.get("openness")
    if isinstance(openness, dict):
        openness = openness.get("status")
    return {
        "kind": "catalog",
        "key": result["key"],
        "name": result["name"],
        "authors": [],
        "url": paper_url or (urls[0] if urls else result.get("source_url")),
        "arxiv_id": arxiv_id,
        "year": _year(result, arxiv_id),
        "summary": _summary(record.get("description") or result.get("description")),
        "axes": {
            "has_paper": bool(result.get("has_paper")),
            "has_repo": bool(result.get("has_repo")),
            "has_dataset": bool(result.get("has_dataset")),
            "openness": openness or "unknown",
        },
    }


def _radar_entry(result: dict[str, Any]) -> dict[str, Any]:
    arxiv_id = _arxiv_id(result, [])
    return {
        "kind": "radar",
        "key": result["key"],
        "name": result["name"],
        "authors": [str(name) for name in result.get("authors") or [] if str(name).strip()],
        "url": result.get("url"),
        "arxiv_id": arxiv_id,
        "year": _year(result, arxiv_id),
        "summary": _summary(result.get("description")),
        "axes": {
            "has_paper": bool(result.get("has_paper")),
            "has_repo": bool(result.get("has_repo")),
            "has_dataset": bool(result.get("has_dataset")),
            "openness": "unknown",
        },
    }


def _merge(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    """Fold a second record of the same paper into the first one kept."""
    existing["merged_keys"].append(incoming["key"])
    if not existing["authors"] and incoming["authors"]:
        existing["authors"] = incoming["authors"]
    for field in ("url", "arxiv_id", "year", "summary"):
        existing[field] = existing[field] or incoming[field]
    for flag in ("has_paper", "has_repo", "has_dataset"):
        existing["axes"][flag] = existing["axes"][flag] or incoming["axes"][flag]
    if existing["axes"]["openness"] == "unknown":
        existing["axes"]["openness"] = incoming["axes"]["openness"]


def _bibtex(entry: dict[str, Any]) -> str:
    lines = []
    if not entry["authors"]:
        lines.append("% Benchmark Radar has no author list for this record; add it before citing.")
    lines.append(f"@misc{{{entry['cite_key']},")
    lines.append(f"  title        = {{{{{latex_escape(entry['name'])}}}}},")
    if entry["authors"]:
        authors = " and ".join(latex_escape(name) for name in entry["authors"])
        lines.append(f"  author       = {{{authors}}},")
    else:
        # BibTeX's standard stand-in: styles sort and label by `key` when no
        # author exists, so the citation renders without an invented author.
        lines.append(f"  key          = {{{latex_escape(entry['name'])}}},")
    if entry["year"]:
        lines.append(f"  year         = {{{entry['year']}}},")
    if entry["arxiv_id"]:
        lines.append(f"  eprint       = {{{entry['arxiv_id']}}},")
        lines.append("  archivePrefix = {arXiv},")
        lines.append(f"  url          = {{https://arxiv.org/abs/{entry['arxiv_id']}}},")
    elif entry["url"]:
        lines.append(f"  howpublished = {{\\url{{{entry['url']}}}}},")
    lines.append("}")
    return "\n".join(lines)


def _verification(entry: dict[str, Any]) -> list[str]:
    issues = []
    if not entry["authors"]:
        issues.append("authors_missing")
    if not entry["year"]:
        issues.append("year_missing")
    if not entry["arxiv_id"] and not entry["url"]:
        issues.append("locator_missing")
    if entry["kind"] == "radar":
        issues.append("radar_lead_unverified")
    return issues


def _assign_keys(entries: list[dict[str, Any]]) -> None:
    used = {BIBTEX_KEY}
    for entry in entries:
        base = _base_key(entry)
        key, suffix = base, ord("a")
        while key in used:
            key = f"{base}{chr(suffix)}"
            suffix += 1
        used.add(key)
        entry["cite_key"] = key


def _coverage(service: QueryService, *, include_radar: bool) -> dict[str, Any]:
    catalog_count = service.validated_catalog_index()["count"]
    value: dict[str, Any] = {"catalog_count": catalog_count}
    if include_radar:
        snapshots = service._load_snapshots()
        value.update(
            {
                "radar_first_date": snapshots[0]["date"],
                "radar_latest_date": snapshots[-1]["date"],
                "snapshot_count": len(snapshots),
            }
        )
    window = (
        f"Radar observations from {value['radar_first_date']} to {value['radar_latest_date']}"
        if include_radar
        else "no Radar observations"
    )
    value["statement"] = (
        f"Candidates come from {catalog_count} catalog records and {window}. Retrieval is "
        "lexical, and a work missing here is evidence about this corpus, not about the "
        "literature; older prior art in particular may be absent."
    )
    return value


def _without_comments(value: str) -> str:
    lines = []
    for line in value.splitlines():
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                line = line[:index]
                break
        lines.append(line)
    return "\n".join(lines)


def _citation_keys(latex: str) -> set[str]:
    keys: set[str] = set()
    pattern = r"(?<!\\)(?:\\\\)*\\cite(?:p|t)?\s*\{([^{}]*)\}"
    for match in re.finditer(pattern, _without_comments(latex)):
        keys.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return keys


def _split_bibtex_fields(body: str) -> list[str]:
    fields = []
    start = 0
    depth = 0
    for index, char in enumerate(body):
        if char == "{" and (index == 0 or body[index - 1] != "\\"):
            depth += 1
        elif char == "}" and (index == 0 or body[index - 1] != "\\"):
            depth -= 1
        elif char == "," and depth == 0:
            fields.append(body[start:index])
            start = index + 1
    fields.append(body[start:])
    return fields


def _bibtex_entries(bibtex: str) -> dict[str, tuple[str, dict[str, str]]]:
    value = _without_comments(bibtex)
    entries: dict[str, tuple[str, dict[str, str]]] = {}
    header = re.compile(r"@(\w+)\s*\{")
    cursor = 0
    while match := header.search(value, cursor):
        depth = 1
        index = match.end()
        while index < len(value) and depth:
            char = value[index]
            if char == "{" and value[index - 1] != "\\":
                depth += 1
            elif char == "}" and value[index - 1] != "\\":
                depth -= 1
            index += 1
        if depth:
            break
        parts = _split_bibtex_fields(value[match.end() : index - 1])
        key = parts[0].strip()
        fields: dict[str, str] = {}
        for part in parts[1:]:
            if "=" not in part:
                continue
            name, field_value = part.split("=", 1)
            field_value = field_value.strip()
            if field_value.startswith("{") and field_value.endswith("}"):
                field_value = field_value[1:-1]
            fields[name.strip().casefold()] = " ".join(field_value.split())
        if key:
            entries[key] = (match.group(1).casefold(), fields)
        cursor = index
    return entries


def verify_citation_complete(
    latex: str, bibtex: str, requirements: list[dict[str, str]] | None = None
) -> None:
    """Reject a related-work artifact that drops a required citation dependency."""
    from .query import QueryError

    if requirements is None:
        requirements = required_citations()
    cited_keys = _citation_keys(latex)
    actual_entries = _bibtex_entries(bibtex)
    for requirement in requirements:
        key = requirement["key"]
        if key not in cited_keys:
            raise QueryError(
                "related-work LaTeX is missing the required Benchmark Radar in-text citation",
                code="citation_contract_failed",
            )
        required_entry = _bibtex_entries(requirement["bibtex"]).get(key)
        actual_entry = actual_entries.get(key)
        if required_entry is None or actual_entry is None:
            raise QueryError(
                "related-work BibTeX is missing the required Benchmark Radar BibTeX entry",
                code="citation_contract_failed",
            )
        required_type, required_fields = required_entry
        actual_type, actual_fields = actual_entry
        if actual_type != required_type or any(
            actual_fields.get(name) != value for name, value in required_fields.items()
        ):
            raise QueryError(
                "related-work BibTeX is missing the required Benchmark Radar BibTeX entry",
                code="citation_contract_failed",
            )


def build_related_work(
    service: QueryService,
    topics: list[str],
    *,
    per_topic: int = 6,
    include_partial: bool = False,
    include_radar: bool = True,
) -> dict[str, Any]:
    from .query import QUERY_SCHEMA_VERSION, QueryError

    parsed = [parse_topic(value) for value in topics]
    if not parsed or len(parsed) > MAX_TOPICS:
        raise QueryError(
            f"pass between 1 and {MAX_TOPICS} topics", code="invalid_query", status=400
        )
    if per_topic < 1 or per_topic > MAX_PER_TOPIC:
        raise QueryError(
            f"per_topic must be between 1 and {MAX_PER_TOPIC}", code="invalid_limit", status=400
        )

    entries: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}
    topic_rows = []
    scopes = ("catalog", "radar") if include_radar else ("catalog",)
    for topic in parsed:
        row: dict[str, Any] = {"label": topic.label, "query": topic.query, "search_status": {}}
        kept: list[dict[str, Any]] = []
        for scope in scopes:
            payload = service.search(topic.query, scope=scope, limit=_SEARCH_WINDOW)
            row["search_status"][scope] = payload["search_status"]
            taken = 0
            for result in payload["results"]:
                if taken >= per_topic:
                    break
                if result["match"]["missing_tokens"] and not include_partial:
                    continue
                if (
                    scope == "radar"
                    and str(result.get("source") or "").casefold() not in SCHOLARLY_RADAR_SOURCES
                ):
                    continue
                entry = (
                    _catalog_entry(service, result) if scope == "catalog" else _radar_entry(result)
                )
                identity = f"arxiv:{entry['arxiv_id']}" if entry["arxiv_id"] else entry["key"]
                if identity in by_identity:
                    target = by_identity[identity]
                    if entry["key"] not in {target["key"], *target["merged_keys"]}:
                        _merge(target, entry)
                else:
                    entry.update({"merged_keys": [], "topics": []})
                    by_identity[identity] = entry
                    entries.append(entry)
                    target = entry
                if topic.label not in target["topics"]:
                    target["topics"].append(topic.label)
                if not any(item is target for item in kept):
                    kept.append(target)
                    taken += 1
        row["entries"] = kept
        topic_rows.append(row)

    _assign_keys(entries)
    for entry in entries:
        entry["bibtex"] = _bibtex(entry)
        entry["verification"] = _verification(entry)
    for row in topic_rows:
        row["cite_keys"] = [entry["cite_key"] for entry in row.pop("entries")]

    coverage = _coverage(service, include_radar=include_radar)
    requirements = required_citations()
    by_key = {entry["cite_key"]: entry for entry in entries}
    latex = render_latex(
        topic_rows,
        by_key,
        coverage=coverage,
        required_citation_key=requirements[0]["key"],
    )
    bibtex = (
        "\n\n".join(
            [
                bibtex_citation_notice(),
                *(entry["bibtex"] for entry in entries),
                bibtex_citation(),
            ]
        )
        + "\n"
    )
    verify_citation_complete(latex, bibtex, requirements)
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "retrieval_mode": "related_work",
        "options": {
            "per_topic": per_topic,
            "include_partial": include_partial,
            "include_radar": include_radar,
        },
        "topics": topic_rows,
        "count": len(entries),
        "entries": entries,
        "coverage": coverage,
        "latex": latex,
        "bibtex": bibtex,
        "markdown": render_markdown(topic_rows, by_key, coverage=coverage),
        "data": service._data_summary(scope="all" if include_radar else "catalog"),
        "required_citations": requirements,
    }
