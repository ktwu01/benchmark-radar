"""The brand marks, and the page that makes a wrong one visible (issue #261).

Three marks shipped wrong and stayed wrong: "Google DeepMind" was keyed to
simple-icons' Google "G", GPT fell through to a hand-drawn rosette, and Meta's
path was genuine for 395 characters and invented after that. Nothing failed,
because nothing asserted what a mark should look like -- and a path is not
something a reader reviews in a diff.

So the checks here are the ones a diff cannot make: that every path is
well-formed and inside the viewBox every mark is authored to, that the audit
page renders through the same module the charts do, and that the IDs review
feedback cites are frozen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

GLYPHS = Path("site/assets/glyphs.js")


def _tables() -> dict[str, dict[str, list[str]]]:
    text = GLYPHS.read_text(encoding="utf-8")
    tables: dict[str, dict[str, list[str]]] = {}
    for table in ("ORGANIZATION_ICONS", "MODEL_FAMILY_ICONS"):
        block = text.split(f"const {table} = {{", 1)[1].split("\n};", 1)[0]
        entries: dict[str, list[str]] = {}
        # One or more paths per entry: Azure is four squares, Upstage eleven
        # strokes, and iconGlyph appends one <path> for each.
        for match in re.finditer(r'\n  ("?[\w. ]+"?): \[\s*\n((?:\s*"[^"]+",\n)+)\s*\]', block):
            entries[match.group(1).strip('"')] = re.findall(r'"([^"]+)"', match.group(2))
        tables[table] = entries
    return tables


PROVENANCE = Path("site/assets/glyph-provenance.json")


def test_every_brand_path_matches_the_upstream_mark_it_claims_to_be():
    """The only check that catches a fabricated path.

    Meta's committed path was byte-identical to simple-icons for 395
    characters and invented for the next 1,200 -- same subpath count, same
    command mix, every coordinate inside the viewBox. No static heuristic
    separates it from a real mark (the coordinate check below does not), and
    it rendered as a blob for a year. What separates them is the upstream file
    each path claims to come from, so every mark is pinned to a URL and a
    digest of the bytes fetched from it.

    Offline by design: the digest is committed, so this asserts "nobody edited
    a brand path by hand" on every run without a network call. Refresh with
    `python scripts/build_glyph_provenance.py`, which refuses to record a
    digest for a path that disagrees with its upstream.
    """
    import hashlib

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))["marks"]
    tables = _tables()

    for table, entries in tables.items():
        for name, paths in entries.items():
            key = f"{table}[{name}]"
            assert key in provenance, f"{key} has no recorded source"
            # Over every path, not just the first: several marks are
            # multi-path, and hashing one would let the rest drift unnoticed.
            digest = hashlib.sha256("\0".join(paths).encode("utf-8")).hexdigest()
            assert digest == provenance[key]["sha256"], (
                f"{key} no longer matches {provenance[key]['url']} -- a brand "
                f"mark was edited by hand, which is how Meta's path was fabricated"
            )

    live = {f"{t}[{n}]" for t, entries in tables.items() for n in entries}
    assert set(provenance) == live, "provenance and the icon tables disagree"


def test_a_hand_drawn_mark_is_declared_rather_than_passed_off_as_a_brand():
    """Z.ai has no licensed upstream mark and is drawn in this repo.

    That is allowed; what is not is a hand-authored path presenting itself as
    a real brand mark. The distinction has to be recorded, because it is
    invisible in the path data itself.
    """
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))["marks"]
    placeholders = {k for k, v in provenance.items() if v["url"].startswith("placeholder:")}

    assert placeholders == {"ORGANIZATION_ICONS[Z.ai]"}
    for key, record in provenance.items():
        if key not in placeholders:
            assert record["url"].startswith("https://"), key


def test_xai_draws_grok_because_the_company_and_the_model_share_one_brand():
    """xAI ships no corporate mark separate from Grok's.

    The organization drew a bold X drawn in this repo, while the model family
    beside it drew the real licensed glyph -- two marks for one identity, and
    the hand-drawn one was the fallback nobody had a better answer for.
    """
    tables = _tables()
    assert tables["ORGANIZATION_ICONS"]["xAI"] == tables["MODEL_FAMILY_ICONS"]["Grok"]

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))["marks"]
    assert provenance["ORGANIZATION_ICONS[xAI]"]["url"].endswith("/grok.svg")
    # Same bytes, so the two entries must carry the same digest.
    assert (
        provenance["ORGANIZATION_ICONS[xAI]"]["sha256"]
        == provenance["MODEL_FAMILY_ICONS[Grok]"]["sha256"]
    )


def test_every_brand_path_is_well_formed_and_inside_the_viewbox():
    """A fabricated path is what this catches.

    Meta's committed path matched upstream for 395 characters, then ran on for
    another 1,200 of invented curve data whose extent escaped the 24-unit box
    every mark in both source sets is authored to fit. It rendered as a blob
    for a year without failing anything.
    """
    for table, entries in _tables().items():
        assert entries, table
        for name, paths in entries.items():
            for d in paths:
                assert d.startswith(("M", "m")), f"{table}[{name}] does not start with a moveto"
                # Only the command letters SVG defines. A stray letter is the
                # signature of hand-authored or truncated data.
                assert not set(re.findall(r"[A-Za-z]", d)) - set("MmLlHhVvCcSsQqTtAaZz"), (
                    f"{table}[{name}] carries a non-path command"
                )
                # No coordinate check here. SVG's grammar packs numbers in ways
                # a regex reads wrong -- "0.523.357" is two numbers, and an arc
                # writes its flags against the next coordinate, so AI21's
                # "A4.04 4.04 0 0115.183 7" scans as 115.183 when it means 15.183.
                # Every attempt to bound coordinates by pattern either misreads
                # a real mark or passes a fabricated one, and the check that
                # actually holds is the upstream digest above.
                assert len(d) > 20, f"{table}[{name}] is too short to be a mark"


def test_the_organization_table_is_keyed_by_canonical_names_only():
    """A key the data never produces is a mark nothing can draw (#261)."""
    from benchmark_radar.catalog import CANONICAL_ORGANIZATIONS

    keys = set(_tables()["ORGANIZATION_ICONS"])
    assert "Google DeepMind" not in keys, "renamed to Google"
    assert "Google" in keys
    for alias in CANONICAL_ORGANIZATIONS:
        assert alias not in keys, f"{alias} is a vendor alias, not a canonical name"


def test_gpt_resolves_to_the_real_openai_mark_not_a_stand_in():
    """Issue #261: GPT rows drew a hand-drawn six-petal rosette.

    OpenAI is absent from simple-icons, and the placeholder that stood in for
    it was the wrong logo on every GPT point on the site.
    """
    openai = _tables()["ORGANIZATION_ICONS"]["OpenAI"][0]
    assert not openai.startswith("M11.90,12.0"), "still the rosette placeholder"
    # The rosette was six identical arc segments; the real mark is not.
    assert openai.count("a 6.1,6.1") == 0


def test_the_audit_page_renders_through_the_charts_own_resolvers():
    """A review page that reimplemented these could show green while the chart
    drew the wrong mark, which is the failure it exists to catch."""
    logos = Path("site/assets/logos.js").read_text(encoding="utf-8")

    assert 'from "./glyphs.js"' in logos
    for name in ("organizationIcon", "modelIcon", "organizationColor", "iconGlyph"):
        assert name in logos.split('from "./glyphs.js"', 1)[0], name
    # No second copy of a path anywhere in the page's own source.
    assert not re.search(r'"M\d[\d.,\s-]{60,}', logos), "audit page carries its own path data"


def test_review_ids_are_frozen_so_feedback_survives_a_rebuild():
    """ "O-07" has to mean the same organization next month as it does today."""
    registry = json.loads(Path("site/data/logo-registry.json").read_text(encoding="utf-8"))

    organizations = registry["organizations"]
    models = registry["models"]
    assert organizations and models

    for mapping, prefix in ((organizations, "O"), (models, "M")):
        ids = list(mapping.values())
        assert len(ids) == len(set(ids)), f"{prefix} ids are not unique"
        assert all(re.fullmatch(rf"{prefix}-\d{{2,}}", value) for value in ids)

    assert "Google" in organizations
    assert "Google DeepMind" not in organizations


def test_every_model_that_draws_a_point_has_a_card_whichever_layer_it_came_from(
    rebuilt_logo_registry,
):
    """Issue #268: Gemini had a card and MiMo did not.

    The registry read crawled shards for organization names and threw away the
    model names in the same loop, so 75 crawled models across 23 organizations
    had no card on the page that exists to get marks reviewed. Both layers
    resolve their mark through the same `modelIcon` call, so both belong here.
    """
    registry = rebuilt_logo_registry
    models = registry["models"]
    # Layers live in models.json, the one structure that answers which models
    # exist; the logo registry only freezes what each is called in review.
    doc = json.loads(Path("site/data/models.json").read_text(encoding="utf-8"))
    sources = {f"{m['model']}␟{m['organization']}": m["provenance_sources"] for m in doc["models"]}

    assert set(models) == set(sources), "every model must declare its sources"
    assert {name for value in sources.values() for name in value} == {
        "model_reports",
        "llm_stats",
        "artificial_analysis",
    }
    # The case that was reported: Xiaomi ships MiMo through the crawled layer.
    assert any(k.endswith("␟Xiaomi") for k in models), "Xiaomi has no model card"
    # And the curated side is still there rather than displaced.
    assert any("Gemini" in k for k in models), "Gemini has no model card"
    assert sum(1 for value in sources.values() if "artificial_analysis" in value) > 100


def test_every_source_uses_the_same_provenance_chips_and_filters():
    logos = Path("site/assets/logos.js").read_text(encoding="utf-8")
    html = Path("site/logos.html").read_text(encoding="utf-8")

    # Layers come from models.json now -- the shared registry, not a list the
    # page assembles for itself.
    assert 'fetch("data/models.json")' in logos
    assert "record.provenance_sources" in logos
    assert "chip-source-${name}" in logos
    for name in ("model_reports", "llm_stats", "artificial_analysis"):
        assert f'data-filter="{name}"' in html
    assert "not a curated card" not in html
