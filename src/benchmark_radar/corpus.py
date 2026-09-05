"""Deterministic cumulative entity graph built from validated daily snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import rubric

CORPUS_SCHEMA_VERSION = 1
AGGREGATE_WINDOW_DAYS = 7
PRIMARY_SOURCE_RANK = {
    "arXiv": 1,
    "First-party feed": 1,
    "OpenReview": 1,
    "GitHub Release": 1,
    "GitHub": 1,
    "GitHub Organization": 1,
    "Hugging Face": 1,
    "Kaggle Dataset": 1,
    "Zenodo": 1,
    "Semantic Scholar": 2,
    "OpenAlex": 2,
    "Crossref": 2,
    "Brave Search": 3,
}
# Derived from the rubric rather than restated, which had let the two lists
# drift: the rubric credits OpenAlex and Semantic Scholar as primary scholarly
# records while this set omitted both, so an observation could be primary for
# scoring and not primary for provenance reporting.
PRIMARY_OR_STRUCTURED_SOURCES = {
    *rubric.EVIDENCE_PRIMARY_SOURCES,
    *rubric.EVIDENCE_ARTIFACT_SOURCES,
}


class CorpusError(ValueError):
    """Raised when generated cumulative data violates the public schema."""


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _arxiv_id(path: str) -> str | None:
    match = re.search(r"/(?:abs|pdf)/([^/?#]+)", path, flags=re.IGNORECASE)
    if not match:
        return None
    identifier = re.sub(r"\.pdf$", "", match.group(1), flags=re.IGNORECASE)
    return re.sub(r"v\d+$", "", identifier, flags=re.IGNORECASE).lower()


def _exact_candidates(item: dict[str, Any]) -> list[tuple[int, str]]:
    """Return every exact identifier this record carries with its priority."""
    urls = [str(item.get("url") or ""), *map(str, item.get("artifact_urls") or [])]
    candidates: set[tuple[int, str]] = set()
    for url in urls:
        parsed = urlsplit(url)
        host = parsed.netloc.casefold().removeprefix("www.")
        segments = [segment for segment in parsed.path.split("/") if segment]
        if host in {"doi.org", "dx.doi.org"} and segments:
            candidates.add((1, f"artifact:doi:{'/'.join(segments).casefold()}"))
        arxiv = _arxiv_id(parsed.path) if host.endswith("arxiv.org") else None
        if arxiv:
            candidates.add((2, f"artifact:arxiv:{arxiv}"))
        if host == "openreview.net":
            forum = (parse_qs(parsed.query).get("id") or [None])[0]
            if forum:
                candidates.add((3, f"artifact:openreview:{str(forum).casefold()}"))
        if host == "github.com" and len(segments) >= 2:
            candidates.add(
                (4, f"artifact:github:{segments[0].casefold()}/{segments[1].casefold()}")
            )
        if host == "huggingface.co" and len(segments) >= 2:
            kind = segments[0].casefold()
            if kind in {"datasets", "spaces", "models"} and len(segments) >= 3:
                candidates.add(
                    (
                        5,
                        f"artifact:huggingface:{kind}:"
                        f"{segments[1].casefold()}/{segments[2].casefold()}",
                    )
                )
            elif kind not in {"datasets", "spaces"}:
                candidates.add(
                    (
                        5,
                        f"artifact:huggingface:models:"
                        f"{segments[0].casefold()}/{segments[1].casefold()}",
                    )
                )
    if candidates:
        return sorted(candidates)

    # No recognizable URL identifier, so fall back to the source's own id.
    source = str(item.get("source") or "").casefold()
    source_id = str(item.get("source_id") or "").strip().casefold()
    if source == "arxiv":
        base_id = re.sub(r"v\d+$", "", source_id)
        return [(2, f"artifact:arxiv:{base_id}")]
    if source == "openreview":
        return [(3, f"artifact:openreview:{source_id}")]
    if source in {"github", "github release"}:
        return [(4, f"artifact:github:{source_id.split('@', 1)[0]}")]
    if source == "hugging face":
        return [(5, f"artifact:huggingface:datasets:{source_id}")]
    return [(9, _stable_id("artifact:url", str(item.get("url") or source_id).casefold()))]


def exact_artifact_keys(item: dict[str, Any]) -> list[str]:
    """Every exact public identifier this record carries, strongest first.

    :func:`exact_artifact_key` collapses these to one so a corpus entity has a
    single identity. Deduplication needs all of them: a paper that links its own
    repository shares no identity with that repository when only the strongest
    identifier is compared, because the paper resolves to its arXiv id and the
    repository to its owner/repo.
    """
    return [key for _, key in _exact_candidates(item)]


def exact_artifact_key(item: dict[str, Any]) -> str:
    """Resolve an artifact using exact public identifiers only.

    URL identifiers take priority so a Semantic Scholar/OpenReview observation
    carrying an arXiv, DOI, GitHub, or Hugging Face link joins that primary
    entity. Ambiguous title similarity is deliberately not used.
    """
    return _exact_candidates(item)[0][1]


def artifact_alias_map(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Resolve transitively linked exact identifiers to one stable identity.

    A single record can carry several identifiers for the same artifact, such
    as a DOI and an arXiv URL. Another source may expose only one of them. The
    shared identifier joins both observations, and transitive links join later
    observations too. This is the same additive identity rule daily dedup uses,
    applied across the full snapshot history.
    """
    parents: dict[str, str] = {}
    priorities: dict[str, int] = {}

    def find(key: str) -> str:
        root = key
        while parents[root] != root:
            root = parents[root]
        while parents[key] != key:
            parent = parents[key]
            parents[key] = root
            key = parent
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        # The parent choice is deterministic; canonical priority is applied
        # after every connected component has been assembled.
        first, second = sorted((left_root, right_root))
        parents[second] = first

    for item in items:
        candidates = _exact_candidates(item)
        keys = [key for _, key in candidates]
        for priority, key in candidates:
            parents.setdefault(key, key)
            priorities[key] = min(priority, priorities.get(key, priority))
        for key in keys[1:]:
            union(keys[0], key)

    components: dict[str, list[str]] = defaultdict(list)
    for key in parents:
        components[find(key)].append(key)

    aliases: dict[str, str] = {}
    for keys in components.values():
        canonical = min(keys, key=lambda key: (priorities[key], key))
        aliases.update({key: canonical for key in keys})
    return aliases


def organizations_for_item(item: dict[str, Any]) -> list[str]:
    """Return exact publisher/owner names available in structured source IDs."""
    source = str(item.get("source") or "").casefold()
    source_id = str(item.get("source_id") or "")
    if source in {"github", "github release", "hugging face"} and "/" in source_id:
        return [source_id.split("/", 1)[0]]
    return [str(value) for value in item.get("organizations") or [] if str(value).strip()]


def _edge_id(kind: str, source: str, target: str) -> str:
    return _stable_id("edge", f"{kind}\0{source}\0{target}")


def _observation_id(date: str, entity_id: str, item: dict[str, Any]) -> str:
    return _stable_id(
        "observation",
        f"{date}\0{entity_id}\0{item.get('source')}\0{item.get('source_id')}",
    )


def _legacy_payload_hash(item: dict[str, Any]) -> str:
    """Fingerprint the persisted public projection when the raw hash predates v2."""
    encoded = json.dumps(
        item,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _entity(
    entity_id: str,
    entity_type: str,
    label: str,
    *,
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entity_id,
        "type": entity_type,
        "label": label,
        "url": url,
        "first_seen_at": None,
        "last_seen_at": None,
        "seen_days": set(),
        "sources": set(),
        "categories": set(),
        "metrics_first": {},
        "metrics_latest": {},
        "latest_score": None,
        "_primary_rank": 99,
        "_parser_versions": set(),
        "_raw_payload_hashes": set(),
    }


def build_corpus(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge snapshot observations into a deterministic public entity graph."""
    entities: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []
    aliases = artifact_alias_map(
        item for snapshot in snapshots for item in snapshot["evidence_items"]
    )

    def touch(entity: dict[str, Any], *, date: str, source: str = "") -> None:
        entity["first_seen_at"] = min(entity["first_seen_at"] or date, date)
        entity["last_seen_at"] = max(entity["last_seen_at"] or date, date)
        entity["seen_days"].add(date)
        if source:
            entity["sources"].add(source)

    def record_provenance(
        entity: dict[str, Any],
        *,
        parser_version: str,
        raw_payload_hash: str,
    ) -> None:
        entity["_parser_versions"].add(parser_version)
        entity["_raw_payload_hashes"].add(raw_payload_hash)

    def connect(kind: str, source_id: str, target_id: str, date: str) -> None:
        edge_id = _edge_id(kind, source_id, target_id)
        edge = edges.setdefault(
            edge_id,
            {
                "id": edge_id,
                "type": kind,
                "source": source_id,
                "target": target_id,
                "first_seen_at": date,
                "last_seen_at": date,
                "seen_days": set(),
            },
        )
        edge["first_seen_at"] = min(edge["first_seen_at"], date)
        edge["last_seen_at"] = max(edge["last_seen_at"], date)
        edge["seen_days"].add(date)

    for snapshot in snapshots:
        date = str(snapshot["date"])
        for item in snapshot["evidence_items"]:
            parser_version = str(item.get("parser_version") or "legacy-public-projection/1")
            raw_payload_hash = str(item.get("raw_payload_hash") or _legacy_payload_hash(item))
            retrieved_at = (
                item.get("retrieved_at") or snapshot.get("generated_at") or f"{date}T00:00:00+00:00"
            )
            entity_id = aliases[exact_artifact_key(item)]
            artifact = entities.setdefault(
                entity_id,
                _entity(entity_id, "artifact", str(item["title"]), url=str(item["url"])),
            )
            touch(artifact, date=date, source=str(item["source"]))
            record_provenance(
                artifact,
                parser_version=parser_version,
                raw_payload_hash=raw_payload_hash,
            )
            source_rank = PRIMARY_SOURCE_RANK.get(str(item["source"]), 4)
            # A secondary metadata observation must not replace an exact
            # primary artifact as the entity's public label/link.
            if source_rank <= artifact["_primary_rank"]:
                artifact["label"] = str(item["title"])
                artifact["url"] = str(item["url"])
                artifact["_primary_rank"] = source_rank
            artifact["categories"].update(map(str, item.get("categories") or []))
            metrics = {
                str(key): float(value)
                for key, value in (item.get("metrics") or {}).items()
                if isinstance(value, (int, float))
            }
            # Endpoints are tracked per metric. Connectors publish different
            # fields for the same artifact, so a metric-less sighting from one
            # connector must not erase another's history: taking the whole dict
            # wholesale let a GitHub observation blank out Hugging Face's
            # download endpoints and silently delete the delta.
            for key, value in metrics.items():
                artifact["metrics_first"].setdefault(key, value)
                artifact["metrics_latest"][key] = value
            artifact["latest_score"] = item.get("total_score")

            observation = {
                "id": _observation_id(date, entity_id, item),
                "entity_id": entity_id,
                "snapshot_date": date,
                "source": str(item["source"]),
                "source_id": str(item["source_id"]),
                "event_kind": str(item["event_kind"]),
                "url": str(item["url"]),
                "published_at": str(item["published_at"]),
                "updated_at": item.get("updated_at"),
                "discovered_at": item.get("discovered_at"),
                "retrieved_at": retrieved_at,
                "parser_version": parser_version,
                "raw_payload_hash": raw_payload_hash,
                "categories": sorted(map(str, item.get("categories") or [])),
                "organizations": sorted(organizations_for_item(item)),
                "metrics": metrics,
                "total_score": item.get("total_score"),
                "score_version": int(item.get("score_version") or 1),
                # This observation publishes `categories`, so it has to publish
                # which rules produced them (issue #72). None for a record
                # classified before the field existed: "unrecorded" and "these
                # specific rules" are different claims, and only one of them is
                # checkable.
                "taxonomy_version": item.get("taxonomy_version"),
            }
            observations.append(observation)

            source_name = str(item["source"])
            source_id = f"source:{source_name.casefold().replace(' ', '-')}"
            source_entity = entities.setdefault(
                source_id,
                _entity(source_id, "source", source_name),
            )
            touch(source_entity, date=date, source=source_name)
            record_provenance(
                source_entity,
                parser_version=parser_version,
                raw_payload_hash=raw_payload_hash,
            )
            connect("FOUND_VIA", entity_id, source_id, date)

            for category in observation["categories"]:
                topic_id = f"topic:{category}"
                topic = entities.setdefault(
                    topic_id,
                    _entity(topic_id, "topic", category.replace("_", " ")),
                )
                touch(topic, date=date, source=source_name)
                record_provenance(
                    topic,
                    parser_version=parser_version,
                    raw_payload_hash=raw_payload_hash,
                )
                connect("HAS_TOPIC", entity_id, topic_id, date)

            for organization in observation["organizations"]:
                organization_id = _stable_id("organization", organization.casefold())
                owner = entities.setdefault(
                    organization_id,
                    _entity(organization_id, "organization", organization),
                )
                touch(owner, date=date, source=source_name)
                record_provenance(
                    owner,
                    parser_version=parser_version,
                    raw_payload_hash=raw_payload_hash,
                )
                connect("RELEASED_BY", entity_id, organization_id, date)

            for author in map(str, item.get("authors") or []):
                person_id = _stable_id("person", author.casefold())
                person = entities.setdefault(
                    person_id,
                    _entity(person_id, "person", author),
                )
                touch(person, date=date, source=source_name)
                record_provenance(
                    person,
                    parser_version=parser_version,
                    raw_payload_hash=raw_payload_hash,
                )
                connect("AUTHORED_BY", entity_id, person_id, date)

    entity_observation_counts = Counter(observation["entity_id"] for observation in observations)
    public_entities = []
    for entity in entities.values():
        entity.pop("_primary_rank")
        parser_versions = sorted(entity.pop("_parser_versions"))
        raw_payload_hashes = sorted(entity.pop("_raw_payload_hashes"))
        metrics_first = entity.pop("metrics_first")
        metrics_latest = entity.pop("metrics_latest")
        # Only a metric present at BOTH endpoints has a real delta. Substituting
        # 0 for a missing endpoint reports "downloads grew from zero" when the
        # connector merely started publishing the field, which is fabricated
        # movement. Metrics seen at one endpoint only are omitted here and
        # remain visible as current values under `metrics`.
        metric_deltas = {
            key: round(metrics_latest[key] - metrics_first[key], 4)
            for key in sorted(metrics_first.keys() & metrics_latest.keys())
        }
        public_entities.append(
            {
                **entity,
                "seen_days": sorted(entity["seen_days"]),
                "sources": sorted(entity["sources"]),
                "categories": sorted(entity["categories"]),
                "metrics": metrics_latest,
                "metric_deltas": metric_deltas,
                "observation_count": (
                    entity_observation_counts[entity["id"]]
                    if entity["type"] == "artifact"
                    else len(entity["seen_days"])
                ),
                "parser_versions": parser_versions,
                "raw_payload_hashes": raw_payload_hashes,
            }
        )
    public_edges = [{**edge, "seen_days": sorted(edge["seen_days"])} for edge in edges.values()]
    observations.sort(key=lambda value: (value["snapshot_date"], value["id"]))
    public_entities.sort(key=lambda value: value["id"])
    public_edges.sort(key=lambda value: value["id"])

    aggregates = _aggregate_corpus(public_entities, observations)
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "entity_count": len(public_entities),
        "observation_count": len(observations),
        "edge_count": len(public_edges),
        "entities": public_entities,
        "observations": observations,
        "edges": public_edges,
        "aggregates": aggregates,
    }
    validate_corpus(corpus)
    return corpus


def _aggregate_corpus(
    entities: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    dates = sorted({observation["snapshot_date"] for observation in observations})
    recent_dates = set(dates[-AGGREGATE_WINDOW_DAYS:])
    baseline_dates = set(dates[-2 * AGGREGATE_WINDOW_DAYS : -AGGREGATE_WINDOW_DAYS])
    topic_entities: dict[str, set[str]] = defaultdict(set)
    topic_days: dict[str, set[str]] = defaultdict(set)
    topic_sources: dict[str, set[str]] = defaultdict(set)
    recent = Counter()
    baseline = Counter()
    for observation in observations:
        for topic in observation["categories"]:
            topic_entities[topic].add(observation["entity_id"])
            topic_days[topic].add(observation["snapshot_date"])
            topic_sources[topic].add(observation["source"])
            if observation["snapshot_date"] in recent_dates:
                recent[topic] += 1
            if observation["snapshot_date"] in baseline_dates:
                baseline[topic] += 1
    topics = []
    for topic in sorted(topic_entities):
        recent_average = recent[topic] / len(recent_dates) if recent_dates else 0
        baseline_average = baseline[topic] / len(baseline_dates) if baseline_dates else None
        topics.append(
            {
                "topic": topic,
                "entity_count": len(topic_entities[topic]),
                "persistence_days": len(topic_days[topic]),
                "source_breadth": len(topic_sources[topic]),
                "recent_daily_average": round(recent_average, 3),
                "baseline_daily_average": (
                    round(baseline_average, 3) if baseline_average is not None else None
                ),
                "velocity": (
                    round(recent_average - baseline_average, 3)
                    if baseline_average is not None
                    else None
                ),
            }
        )
    return {
        "window_days": AGGREGATE_WINDOW_DAYS,
        # The window holds at most AGGREGATE_WINDOW_DAYS of snapshots, but early
        # in the archive it holds fewer. Publishing the count actually divided by
        # lets the dashboard stop calling a 2-day average a 7-day one.
        "observed_window_days": len(recent_dates),
        "topics": topics,
        "entity_types": dict(sorted(Counter(entity["type"] for entity in entities).items())),
        "sources": dict(
            sorted(Counter(observation["source"] for observation in observations).items())
        ),
        "organizations": dict(
            sorted(
                Counter(
                    organization
                    for observation in observations
                    for organization in observation["organizations"]
                ).items()
            )
        ),
        "provenance": {
            "primary_or_structured_observations": sum(
                observation["source"] in PRIMARY_OR_STRUCTURED_SOURCES
                for observation in observations
            ),
            "primary_source_rate": round(
                (
                    sum(
                        observation["source"] in PRIMARY_OR_STRUCTURED_SOURCES
                        for observation in observations
                    )
                    / len(observations)
                ),
                4,
            )
            if observations
            else None,
        },
    }


def validate_corpus(corpus: dict[str, Any]) -> None:
    if corpus.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise CorpusError("unsupported corpus schema_version")
    for field in ("entities", "observations", "edges"):
        if not isinstance(corpus.get(field), list):
            raise CorpusError(f"{field} must be an array")
    entities = corpus["entities"]
    entity_ids = {entity.get("id") for entity in entities}
    if None in entity_ids or len(entity_ids) != len(entities):
        raise CorpusError("entity IDs must be present and unique")
    for entity in entities:
        if entity.get("url") and not str(entity["url"]).startswith(("https://", "http://")):
            raise CorpusError(f"{entity['id']}: entity URL must be HTTP(S)")
        if "raw" in entity:
            raise CorpusError(f"{entity['id']}: raw payloads are not public corpus fields")
        if not entity.get("parser_versions") or not entity.get("raw_payload_hashes"):
            raise CorpusError(f"{entity['id']}: provenance must be present")
        if any(
            not re.fullmatch(r"sha256:[0-9a-f]{64}", str(value))
            for value in entity["raw_payload_hashes"]
        ):
            raise CorpusError(f"{entity['id']}: raw payload hash must use sha256")
    observation_ids: set[str] = set()
    for observation in corpus["observations"]:
        if observation.get("id") in observation_ids:
            raise CorpusError("observation IDs must be unique")
        observation_ids.add(observation.get("id"))
        if observation.get("entity_id") not in entity_ids:
            raise CorpusError("observation references an unknown entity")
        if not str(observation.get("url") or "").startswith(("https://", "http://")):
            raise CorpusError("observation URL must be HTTP(S)")
        datetime.fromisoformat(str(observation["published_at"]).replace("Z", "+00:00")).astimezone(
            UTC
        )
        datetime.fromisoformat(str(observation["retrieved_at"]).replace("Z", "+00:00")).astimezone(
            UTC
        )
        if not observation.get("parser_version") or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", str(observation.get("raw_payload_hash") or "")
        ):
            raise CorpusError("observation provenance must be present")
    edge_ids: set[str] = set()
    for edge in corpus["edges"]:
        if edge.get("id") in edge_ids:
            raise CorpusError("edge IDs must be unique")
        edge_ids.add(edge.get("id"))
        if edge.get("source") not in entity_ids or edge.get("target") not in entity_ids:
            raise CorpusError("edge references an unknown entity")
