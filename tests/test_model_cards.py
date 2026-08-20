from pathlib import Path

import pytest
import yaml

from benchmark_radar.model_cards import (
    DEFAULT_REGISTRY_PATH,
    ModelCardRegistryError,
    adoption_rank,
    build_adoption_rank,
    load_registry,
)


def write_registry(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "model_cards.yml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def minimal_registry(**overrides) -> dict:
    document = {
        "schema_version": 1,
        "benchmarks": [
            {
                "id": "alpha",
                "name": "Alpha",
                "domain": "math",
                "url": "https://example.com/a",
                "caveat": "Alpha caveat.",
            },
            {
                "id": "beta",
                "name": "Beta",
                "domain": "coding",
                "url": "https://example.com/b",
                "caveat": "Beta caveat.",
            },
        ],
        "model_cards": [
            {
                "id": "org_one_card",
                "organization": "Org One",
                "model": "One",
                "document_type": "model_card",
                "published": "2025-01-01",
                "url": "https://example.com/one",
                "benchmarks": ["alpha", "beta"],
            },
            {
                "id": "org_two_card",
                "organization": "Org Two",
                "model": "Two",
                "document_type": "system_card",
                "published": "2025-02-01",
                "url": "https://example.com/two",
                "benchmarks": ["alpha"],
            },
        ],
    }
    document.update(overrides)
    return document


def test_shipped_registry_loads_and_ranks():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    assert board["model_card_count"] > 0
    assert board["benchmark_count"] > 0
    # Every organization named in issue #83 is represented, so the ranking is
    # not an artifact of one vendor's reporting habits.
    assert {
        "OpenAI",
        "Anthropic",
        "Google",
        "Meta",
        "Qwen",
        "DeepSeek",
        "Mistral",
        "xAI",
    } <= set(board["organizations"])


def test_rank_is_total_and_deterministic():
    board = adoption_rank(load_registry(DEFAULT_REGISTRY_PATH))
    entries = board["entries"]

    assert [entry["rank"] for entry in entries] == list(range(1, len(entries) + 1))
    # Cards descending, then organizations descending, then name ascending. No
    # entry may outrank one with a strictly higher card count.
    keys = [
        (-entry["card_count"], -entry["organization_count"], entry["name"]) for entry in entries
    ]
    assert keys == sorted(keys)


def test_repeated_configurations_do_not_inflate_a_single_card(tmp_path):
    # Issue #83's central caveat: one card reporting AIME at pass@1 and
    # consensus@64 is still one card choosing to report AIME. If duplicates
    # counted, a verbose appendix would outvote a whole other vendor.
    document = minimal_registry()
    document["model_cards"][0]["benchmarks"] = ["alpha", "alpha", "alpha", "beta"]
    board = adoption_rank(load_registry(write_registry(tmp_path, document)))

    alpha = next(entry for entry in board["entries"] if entry["benchmark_id"] == "alpha")
    assert alpha["card_count"] == 2
    assert alpha["organization_count"] == 2
    assert len(alpha["adopters"]) == 2


def test_organization_count_distinguishes_a_standard_from_a_house_style(tmp_path):
    document = minimal_registry()
    document["model_cards"].append(
        {
            "id": "org_one_second_card",
            "organization": "Org One",
            "model": "One Plus",
            "document_type": "model_card",
            "published": "2025-03-01",
            "url": "https://example.com/one-plus",
            "benchmarks": ["beta"],
        }
    )
    board = adoption_rank(load_registry(write_registry(tmp_path, document)))

    alpha = next(entry for entry in board["entries"] if entry["benchmark_id"] == "alpha")
    beta = next(entry for entry in board["entries"] if entry["benchmark_id"] == "beta")

    # Both are reported by two cards, but alpha crosses two organizations and
    # beta is one vendor twice. That is precisely the tie the second column
    # exists to break, so alpha must outrank beta.
    assert alpha["card_count"] == beta["card_count"] == 2
    assert alpha["organization_count"] == 2
    assert beta["organization_count"] == 1
    assert alpha["rank"] < beta["rank"]


def test_adoption_share_is_relative_to_the_document_count(tmp_path):
    board = adoption_rank(load_registry(write_registry(tmp_path, minimal_registry())))

    alpha = next(entry for entry in board["entries"] if entry["benchmark_id"] == "alpha")
    beta = next(entry for entry in board["entries"] if entry["benchmark_id"] == "beta")
    assert alpha["adoption_share"] == 1.0
    assert beta["adoption_share"] == 0.5


def test_unknown_benchmark_reference_is_rejected(tmp_path):
    # A typo must not silently mint a benchmark with an adoption count of one,
    # which is indistinguishable from a real benchmark nobody adopted.
    document = minimal_registry()
    document["model_cards"][0]["benchmarks"] = ["alpha", "gamma"]
    path = write_registry(tmp_path, document)

    with pytest.raises(ModelCardRegistryError, match="unknown benchmarks: gamma"):
        load_registry(path)


def test_duplicate_ids_are_rejected(tmp_path):
    document = minimal_registry()
    document["benchmarks"].append(
        {"id": "alpha", "name": "Alpha again", "domain": "math", "caveat": "Dup."}
    )
    with pytest.raises(ModelCardRegistryError, match="duplicate benchmark id"):
        load_registry(write_registry(tmp_path, document))

    document = minimal_registry()
    document["model_cards"].append(dict(document["model_cards"][0]))
    with pytest.raises(ModelCardRegistryError, match="duplicate model card id"):
        load_registry(write_registry(tmp_path, document))


def test_non_http_card_url_is_rejected(tmp_path):
    document = minimal_registry()
    document["model_cards"][0]["url"] = "file:///etc/passwd"
    with pytest.raises(ModelCardRegistryError, match="url must be HTTP"):
        load_registry(write_registry(tmp_path, document))


def test_unsupported_schema_version_is_rejected(tmp_path):
    with pytest.raises(ModelCardRegistryError, match="unsupported schema_version"):
        load_registry(write_registry(tmp_path, minimal_registry(schema_version=99)))


def test_missing_registry_file_is_reported(tmp_path):
    with pytest.raises(ModelCardRegistryError, match="registry file not found"):
        load_registry(tmp_path / "absent.yml")


def test_every_benchmark_states_what_it_does_not_settle():
    registry = load_registry(DEFAULT_REGISTRY_PATH)

    # A ranking that puts a saturated or contaminated benchmark near the top
    # without saying so invites the exact misreading issue #83 warns about, so
    # the caveat is required data rather than optional prose.
    missing = [
        benchmark["id"]
        for benchmark in registry["benchmarks"]
        if not str(benchmark.get("caveat") or "").strip()
    ]
    assert not missing


def test_a_benchmark_without_a_caveat_is_rejected(tmp_path):
    # Enforced for any registry, not spot-checked on the shipped one: a custom
    # --model-cards file could otherwise publish rows with no qualification at
    # all, which is precisely the misreading the caveat exists to prevent.
    document = minimal_registry()
    document["benchmarks"][0].pop("caveat")
    with pytest.raises(ModelCardRegistryError, match="missing fields: caveat"):
        load_registry(write_registry(tmp_path, document))

    document = minimal_registry()
    document["benchmarks"][0]["caveat"] = "   "
    with pytest.raises(ModelCardRegistryError, match="missing fields: caveat"):
        load_registry(write_registry(tmp_path, document))


def test_measures_statement_travels_with_the_data():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    # Any consumer of radar.json inherits the disclaimer instead of inferring
    # the ranking's meaning from its column headers.
    # Asserted as the claim rather than the phrasing. Issue #241 rewrote this
    # for a 16-year-old reader ("vendor attention", "saturated" and
    # "contaminated" were vocabulary a reader had to already have), and a test
    # that pins the old words would force the jargon back.
    #
    # The load-bearing part is that popularity is not quality, and that the
    # statement travels with the data rather than living only in the UI.
    assert "not the same as a good one" in board["measures"]
    assert "how many" in board["measures"].lower()


def test_adoption_rank_links_are_exact_inverses():
    """The registry is one edge set published in two directions.

    `entries[].adopters` answers "who reports this benchmark" and
    `model_cards[].reported_benchmarks` answers "what does this card report".
    Both are derived from the same validated `card["benchmarks"]`, and this test
    is what makes that a guarantee rather than a coincidence: if either
    projection is ever filtered, truncated or sorted into a lossy shape, the two
    edge sets diverge and a reader auditing a card against the table above would
    be shown a benchmark list that does not explain the counts.
    """
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    forward = {
        (entry["benchmark_id"], adopter["model_card_id"])
        for entry in board["entries"]
        for adopter in entry["adopters"]
    }
    reverse = {
        (benchmark["benchmark_id"], card["model_card_id"])
        for card in board["model_cards"]
        for benchmark in card["reported_benchmarks"]
    }

    assert forward == reverse
    assert forward, "the shipped registry must publish at least one adoption edge"
    # Every card's own count agrees with the number of edges it contributes.
    # `reported_benchmarks` is ordered by domain for display, so compare as sets
    # against the id list rather than positionally.
    for card in board["model_cards"]:
        assert card["benchmark_count"] == len(card["reported_benchmarks"])
        assert {benchmark["benchmark_id"] for benchmark in card["reported_benchmarks"]} == set(
            card["benchmarks"]
        )


def test_expanded_card_carries_enough_to_audit_against_the_source():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    # A reader opening a card checks our list against the vendor's own document.
    # That requires the source URL, when a human last read it, and for each
    # benchmark the name and caveat -- not just an id they would have to resolve
    # against another table by hand.
    for card in board["model_cards"]:
        assert card["url"].startswith("https://")
        for benchmark in card["reported_benchmarks"]:
            assert benchmark["name"]
            assert benchmark["domain"]
            assert benchmark["caveat"]


def test_benchmark_release_dates_are_published_and_validated(tmp_path):
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    # Filterable in the dashboard, so it has to survive into the published data.
    assert any(entry["released"] for entry in board["entries"])
    for entry in board["entries"]:
        if entry["released"]:
            assert len(entry["released"]) == 10

    # Validated on the same terms as a card's dates: this value reaches the same
    # browser formatter, and an unparseable one would take every view down.
    document = minimal_registry()
    document["benchmarks"][0]["released"] = "March 2025"
    with pytest.raises(ModelCardRegistryError, match="must be an ISO date"):
        load_registry(write_registry(tmp_path, document))

    document = minimal_registry()
    document["benchmarks"][0]["released"] = "2025-02-30"
    with pytest.raises(ModelCardRegistryError, match="not a real calendar date"):
        load_registry(write_registry(tmp_path, document))


def test_a_card_cannot_report_a_benchmark_that_did_not_exist_yet(tmp_path):
    """A benchmark released after a card cannot have been reported by it.

    Every date involved is individually well-formed, so no other check catches
    the contradiction, and the bad edge is invisible in the ranking: it just
    quietly adds one adoption. The first draft of the 2026 expansion contained
    three such edges, each a different underlying mistake -- one wrong `released`
    date and two benchmarks attributed to cards that reported a different
    instrument -- so this is the check that tells a data error from real data.
    """
    # `beta` is reported only by the first card, so exactly one card violates the
    # chronology and the raised message names it.
    document = minimal_registry()
    document["benchmarks"][1]["released"] = "2025-06-01"
    document["model_cards"][0]["published"] = "2025-01-01"

    with pytest.raises(ModelCardRegistryError, match="'org_one_card'.*released after it"):
        load_registry(write_registry(tmp_path, document))

    # A benchmark with no recorded release date cannot be placed on the
    # timeline, so it is not evidence of a contradiction either way.
    document = minimal_registry()
    document["benchmarks"][1].pop("released", None)
    document["model_cards"][0]["published"] = "2025-01-01"
    load_registry(write_registry(tmp_path, document))

    # Same-day is legitimate: benchmarks are routinely published alongside the
    # card that first reports them (MRCR shipped with GPT-4.1).
    document = minimal_registry()
    document["benchmarks"][1]["released"] = "2025-01-01"
    document["model_cards"][0]["published"] = "2025-01-01"
    load_registry(write_registry(tmp_path, document))


def test_a_revised_document_may_report_a_later_benchmark(tmp_path):
    """An arXiv report at v3 or a living model card is not a data error.

    For those, `published` is the original date while the contents are newer, so
    a benchmark released after publication can be a real mention. The relaxation
    is opt-in per card: the common case is still a mistake, and allowing every
    later benchmark by default would give back the three bad edges the chronology
    check was added to catch.
    """
    # `beta` is reported only by the first card, so the revision under test is
    # the only thing the later release date interacts with.
    document = minimal_registry()
    document["benchmarks"][1]["released"] = "2025-06-01"
    document["model_cards"][0]["published"] = "2025-01-01"
    document["model_cards"][0]["revised"] = "2025-07-01"
    registry = load_registry(write_registry(tmp_path, document))
    assert registry["model_cards"][0]["revised"] == "2025-07-01"

    # The revision date is a real cutoff, not a blanket exemption: a benchmark
    # released after the revision is still impossible.
    document["benchmarks"][1]["released"] = "2025-08-01"
    with pytest.raises(ModelCardRegistryError, match="reports benchmarks released after it"):
        load_registry(write_registry(tmp_path, document))

    # A revision cannot predate the publication it revises.
    document = minimal_registry()
    document["model_cards"][0]["published"] = "2025-06-01"
    document["model_cards"][0]["revised"] = "2025-01-01"
    with pytest.raises(ModelCardRegistryError, match="precedes its published date"):
        load_registry(write_registry(tmp_path, document))

    # And it must be a well-formed date, like every other date in the registry.
    document = minimal_registry()
    document["model_cards"][0]["revised"] = "last Tuesday"
    with pytest.raises(ModelCardRegistryError, match="must be an ISO date"):
        load_registry(write_registry(tmp_path, document))


def test_shipped_registry_has_no_chronologically_impossible_mention():
    registry = load_registry(DEFAULT_REGISTRY_PATH)
    released = {
        str(benchmark["id"]): str(benchmark["released"])
        for benchmark in registry["benchmarks"]
        if benchmark.get("released")
    }

    for card in registry["model_cards"]:
        # The revision date when the document has one: that is the version the
        # mentions were read from.
        cutoff = str(card.get("revised") or card.get("published") or "")
        if not cutoff:
            continue
        for ref in {str(ref) for ref in card["benchmarks"]}:
            if ref in released:
                assert released[ref] <= cutoff, (
                    f"{card['id']} ({cutoff}) cannot report {ref} released {released[ref]}"
                )


def test_reported_benchmark_order_is_total():
    """Ordering must not depend on set iteration order.

    Domain and lowercased name can tie between two distinct benchmarks, and the
    input is a set, so without the id as a final key the published order would
    vary with PYTHONHASHSEED. The inverse-property test cannot catch that -- it
    compares sets -- so the ordering is asserted directly.
    """
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    for card in board["model_cards"]:
        keys = [
            (benchmark["domain"], benchmark["name"].lower(), benchmark["benchmark_id"])
            for benchmark in card["reported_benchmarks"]
        ]
        assert keys == sorted(keys)
        # A total order has no duplicate keys to break.
        assert len(set(keys)) == len(keys)


def test_registry_covers_the_2026_frontier():
    """The ranking has to describe current reporting, not 2025's.

    Issue #83 asks which benchmarks vendors put in front of readers. A registry
    whose newest document predates the current model generation answers that
    question about a frontier that no longer exists, so coverage of recent cards
    is a correctness property of this feature rather than a nice-to-have.
    """
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    published = [card["published"] for card in board["model_cards"] if card["published"]]
    assert sum(1 for date in published if date >= "2026-01-01") >= 10

    # Each organization in the registry is represented by at least one document,
    # and the agentic evaluations that headline 2026 cards are present.
    names = {entry["benchmark_id"] for entry in board["entries"] if entry["card_count"]}
    assert {"terminal_bench", "swe_bench_pro", "tau2_bench", "gdpval", "osworld"} <= names


def test_model_cards_are_listed_newest_first(tmp_path):
    """Issue #90: the roster is ordered by date, not by publisher.

    Grouping by organization first buried the newest documents behind whichever
    vendor sorted earliest alphabetically, which is the opposite of what a
    reader scanning a registry of frontier releases wants.
    """
    document = minimal_registry()
    # A third card from the alphabetically-first organization, published last.
    # Under the old publisher-then-date order this sorted second; the date is
    # what has to decide it now.
    document["model_cards"].append(
        {
            "id": "org_one_newer",
            "organization": "Org One",
            "model": "One Point One",
            "document_type": "model_card",
            "published": "2025-06-01",
            "url": "https://example.com/one-newer",
            "benchmarks": ["beta"],
        }
    )
    board = adoption_rank(load_registry(write_registry(tmp_path, document)))

    assert [card["model_card_id"] for card in board["model_cards"]] == [
        "org_one_newer",
        "org_two_card",
        "org_one_card",
    ]


def test_card_order_does_not_depend_on_registry_file_order(tmp_path):
    """Two documents about one model on one day must still order totally.

    Z.ai published a GLM-5 model card and a GLM-5 technical report on the same
    date, tying organization, model and published. Without a unique final key
    their relative order follows their position in the YAML file, so editing an
    unrelated part of the registry could silently reorder the roster.
    """
    document = minimal_registry()
    for suffix in ("model_card", "technical_report"):
        document["model_cards"].append(
            {
                "id": f"org_one_{suffix}",
                "organization": "Org One",
                "model": "Twin",
                "document_type": suffix,
                "published": "2025-03-01",
                "url": f"https://example.com/twin-{suffix}",
                "benchmarks": ["alpha"],
            }
        )
    forward = adoption_rank(load_registry(write_registry(tmp_path, document)))

    reversed_document = minimal_registry()
    reversed_document["model_cards"].extend(reversed(document["model_cards"][2:]))
    backward = adoption_rank(load_registry(write_registry(tmp_path, reversed_document)))

    assert [card["model_card_id"] for card in forward["model_cards"]] == [
        card["model_card_id"] for card in backward["model_cards"]
    ]


def test_undated_model_cards_sort_last_not_first(tmp_path):
    """An unknown date is not evidence of recency.

    A missing `published` normalises to the empty string, which would sort
    ahead of every real date under a plain descending comparison and put the
    least-known documents at the top of a list that claims to be newest-first.
    """
    document = minimal_registry()
    document["model_cards"].append(
        {
            "id": "undated_card",
            "organization": "Org Three",
            "model": "Three",
            "document_type": "model_card",
            "url": "https://example.com/three",
            "benchmarks": ["alpha"],
        }
    )
    board = adoption_rank(load_registry(write_registry(tmp_path, document)))

    assert board["model_cards"][-1]["model_card_id"] == "undated_card"
    assert board["model_cards"][-1]["published"] is None


def test_shipped_registry_is_ordered_by_date():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    published = [card["published"] for card in board["model_cards"]]
    dated = [value for value in published if value]
    # Every dated card precedes every undated one, and the dated run descends.
    assert published[: len(dated)] == dated
    assert dated == sorted(dated, reverse=True)


def test_fable_mythos_card_records_its_full_comparison_table():
    """Issue #90: the release's benchmark table is an image.

    A text-only reading of the page saw three benchmarks named in prose and
    invented two more that appear nowhere in the release. The table itself
    carries thirteen, and they are the ones the release leads with, so their
    absence understated the adoption of every instrument in it.
    """
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    card = next(
        entry
        for entry in board["model_cards"]
        if entry["model_card_id"] == "anthropic_claude_fable_5_mythos_5"
    )
    reported = set(card["benchmarks"])

    # Transcribed from the comparison table in the release post.
    assert {
        "swe_bench_pro",
        "frontiercode",
        "gdpval",
        "gdp_pdf",
        "blueprint_bench_2",
        "automationbench",
        "osworld",
        "legal_agent_benchmark",
        "hle",
        "biomysterybench",
        "terminal_bench",
        "exploitbench",
        "healthbench_professional",
    } <= reported
    # Named in the prose but not scored in the table. The prose also names
    # Frontier-Bench, which is Terminal-Bench 3.0 under its former name and so
    # resolves to `terminal_bench` (asserted above) rather than an id of its
    # own. FrontierCode, in the table above, is Cognition's separate
    # instrument and keeps its own id despite the shared prefix.
    assert {"cursor_bench", "vibench"} <= reported
    assert "frontier_bench" not in reported
    # Recorded by an earlier pass but absent from the release entirely.
    assert not ({"browsecomp", "swe_bench_verified"} & reported)


def test_new_benchmarks_do_not_reuse_an_existing_benchmarks_alias():
    """A spelling must not resolve to two different benchmarks.

    Aliases exist so a future extractor can map vendor spellings onto one id.
    Splitting a benchmark out of a broader entry -- HealthBench Professional
    out of HealthBench -- leaves that spelling claimed by both unless it is
    removed from the entry it left, and the extractor would then have no way
    to decide which id a card meant.

    Scoped to the benchmarks touched here: three older collisions predate this
    change and resolving them means deciding what those cards actually
    reported, which is a separate piece of work.
    """
    registry = load_registry(DEFAULT_REGISTRY_PATH)

    claimed: dict[str, set[str]] = {}
    for benchmark in registry["benchmarks"]:
        spellings = {str(benchmark["name"])} | {
            str(alias) for alias in benchmark.get("aliases") or []
        }
        for spelling in spellings:
            claimed.setdefault(spelling.strip().lower(), set()).add(str(benchmark["id"]))

    for spelling in ("healthbench professional", "frontiercode", "vibench"):
        assert len(claimed.get(spelling, set())) == 1, (
            f"{spelling!r} resolves to more than one benchmark id"
        )


def test_adopters_link_back_to_the_source_document():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    for entry in board["entries"]:
        for adopter in entry["adopters"]:
            assert adopter["url"].startswith("https://")
            assert adopter["organization"]
            assert adopter["model"]


def test_benchmarks_reported_by_no_card_are_kept_and_ranked_last(tmp_path):
    document = minimal_registry()
    document["benchmarks"].append(
        {"id": "gamma", "name": "Gamma", "domain": "agent", "caveat": "Not yet adopted."}
    )
    board = adoption_rank(load_registry(write_registry(tmp_path, document)))

    gamma = next(entry for entry in board["entries"] if entry["benchmark_id"] == "gamma")
    # Kept: "tracked but reported by nobody" is a finding about vendor
    # attention. Ranked last, and excluded from the adopted-domain tally so a
    # zero cannot inflate a domain's apparent coverage.
    assert gamma["card_count"] == 0
    assert gamma["adopters"] == []
    assert gamma["rank"] == len(board["entries"])
    assert "agent" not in board["domains"]


def test_unparseable_publication_date_fails_the_build(tmp_path):
    # These values reach Intl.DateTimeFormat unmodified, which throws on an
    # unparseable one. The dashboard treats that as an unusable data file and
    # hides every view, so one typo in an optional field would take Today and
    # Trends down with the leaderboard.
    document = minimal_registry()
    document["model_cards"][0]["published"] = "Aug 7th 2025"
    with pytest.raises(ModelCardRegistryError, match="published must be an ISO date"):
        load_registry(write_registry(tmp_path, document))

    document = minimal_registry()
    document["model_cards"][0]["retrieved_at"] = "yesterday"
    with pytest.raises(ModelCardRegistryError, match="retrieved_at must be an ISO date"):
        load_registry(write_registry(tmp_path, document))


def test_dates_parsed_by_yaml_into_date_objects_are_accepted(tmp_path):
    # Unquoted YYYY-MM-DD is a date, not a string, after yaml.safe_load. The
    # shipped registry is written that way, so rejecting it would fail on the
    # file this module exists to read.
    path = tmp_path / "model_cards.yml"
    path.write_text(
        "schema_version: 1\n"
        "benchmarks:\n"
        "  - {id: alpha, name: Alpha, domain: math, caveat: Caveat.}\n"
        "model_cards:\n"
        "  - id: card\n"
        "    organization: Org\n"
        "    model: One\n"
        "    published: 2025-08-07\n"
        "    retrieved_at: 2026-08-02\n"
        "    url: https://example.com/one\n"
        "    benchmarks: [alpha]\n",
        encoding="utf-8",
    )
    board = adoption_rank(load_registry(path))

    assert board["model_cards"][0]["published"] == "2025-08-07"


def test_every_shipped_date_is_browser_formattable():
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    from datetime import date as date_type

    for card in board["model_cards"]:
        assert date_type.fromisoformat(card["published"])
        assert date_type.fromisoformat(card["retrieved_at"])


@pytest.mark.parametrize("value", ["20250807", "2025-W32-4", "2025-220"])
def test_iso_variants_the_browser_cannot_parse_are_rejected(tmp_path, value):
    # date.fromisoformat accepts all of these on Python 3.11+, and JavaScript's
    # Date turns every one into Invalid Date. Validating against the standard
    # rather than against the browser would let the build pass and the whole
    # dashboard fail at load.
    document = minimal_registry()
    document["model_cards"][0]["published"] = value
    with pytest.raises(ModelCardRegistryError, match="must be an ISO date"):
        load_registry(write_registry(tmp_path, document))


def test_a_well_formed_but_impossible_date_is_rejected(tmp_path):
    document = minimal_registry()
    document["model_cards"][0]["published"] = "2025-02-30"
    with pytest.raises(ModelCardRegistryError, match="not a real calendar date"):
        load_registry(write_registry(tmp_path, document))


def test_the_same_document_registered_twice_is_rejected(tmp_path):
    # The counting unit is the document. Two ids pointing at one URL would add
    # two adoptions to every benchmark that document lists and reorder the
    # ranking, which is exactly the inflation the per-document rule prevents.
    document = minimal_registry()
    document["model_cards"].append(
        {
            **document["model_cards"][0],
            "id": "org_one_card_again",
        }
    )
    with pytest.raises(ModelCardRegistryError, match="repeats the document URL"):
        load_registry(write_registry(tmp_path, document))


def test_a_scalar_alias_is_rejected_rather_than_split_into_characters(tmp_path):
    # `aliases: Alias` is the natural thing to write and is a YAML scalar,
    # which iterates per character into ['A', 'l', 'i', 'a', 's'].
    document = minimal_registry()
    document["benchmarks"][0]["aliases"] = "Alpha Bench"
    with pytest.raises(ModelCardRegistryError, match="aliases must be a list"):
        load_registry(write_registry(tmp_path, document))


def test_shipped_registry_has_no_repeated_documents_or_scalar_aliases():
    registry = load_registry(DEFAULT_REGISTRY_PATH)

    urls = [str(card["url"]) for card in registry["model_cards"]]
    assert len(urls) == len(set(urls))
    for benchmark in registry["benchmarks"]:
        aliases = benchmark.get("aliases")
        assert aliases is None or isinstance(aliases, list)


def test_a_yaml_timestamp_is_rejected_rather_than_shifted_a_day(tmp_path):
    # datetime subclasses date, and PyYAML returns one for any value carrying a
    # time. "2025-08-07T00:00:00+05:30" would serialize with its offset and the
    # dashboard's UTC formatter would render August 6: silently wrong rather
    # than rejected.
    path = tmp_path / "model_cards.yml"
    path.write_text(
        "schema_version: 1\n"
        "benchmarks:\n"
        "  - {id: alpha, name: Alpha, domain: math, caveat: Caveat.}\n"
        "model_cards:\n"
        "  - id: card\n"
        "    organization: Org\n"
        "    model: One\n"
        "    published: 2025-08-07T00:00:00+05:30\n"
        "    url: https://example.com/one\n"
        "    benchmarks: [alpha]\n",
        encoding="utf-8",
    )
    with pytest.raises(ModelCardRegistryError, match="published must be an ISO date"):
        load_registry(path)


def test_a_fragment_does_not_make_one_document_look_like_two(tmp_path):
    # "#results" names a location inside a document, not another document, so
    # both forms are one card and must not each add an adoption.
    document = minimal_registry()
    document["model_cards"].append(
        {
            **document["model_cards"][0],
            "id": "org_one_card_anchor",
            "url": f"{document['model_cards'][0]['url']}#results",
        }
    )
    with pytest.raises(ModelCardRegistryError, match="repeats the document URL"):
        load_registry(write_registry(tmp_path, document))


def test_merging_frontier_bench_did_not_double_count_terminal_bench():
    """Issue #94: the merge must absorb those mentions, not add them.

    Frontier-Bench was folded into `terminal_bench` as Terminal-Bench 3.0 under
    its former name. Three cards had named it, which invites the reading that
    the merge should lift Terminal-Bench's count by three. It must not: all
    three also report Terminal-Bench in the same document, and the counting
    unit is the document, so each contributes exactly one adoption either way.
    Counting the merged alias separately would put the series above instruments
    that genuinely appear in more cards.
    """
    board = build_adoption_rank(DEFAULT_REGISTRY_PATH)

    # The merged id is gone, and no card can still reference it.
    assert all("frontier_bench" not in card["benchmarks"] for card in board["model_cards"])

    by_card = {card["model_card_id"]: set(card["benchmarks"]) for card in board["model_cards"]}
    # The three cards that named Frontier-Bench, each already reporting the
    # series under its own name -- which is why the merge is absorptive.
    for card_id in (
        "anthropic_claude_opus_5_system_card",
        "anthropic_claude_fable_5_mythos_5",
        "moonshot_kimi_k3_model_card",
    ):
        assert "terminal_bench" in by_card[card_id]

    entry = next(row for row in board["entries"] if row["benchmark_id"] == "terminal_bench")
    # One adoption per citing document, not one per alias spelling it used.
    assert entry["card_count"] == len(
        [card for card in board["model_cards"] if "terminal_bench" in card["benchmarks"]]
    )
    # The merged spellings still resolve, so a future extractor can map them.
    assert {"Frontier-Bench", "Terminal-Bench 3.0"} <= set(entry["aliases"])
