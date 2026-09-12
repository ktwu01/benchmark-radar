"""Shared HTML escaping and schema helpers for generated app pages."""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from typing import Any

from .feed import SITE_URL

# The reader-facing name of every score source. Shared because the dashboard
# seeds and the static benchmark pages both label the same partitions, and a
# page that calls a source `opencompass_hub` while the dashboard calls it
# OpenCompass Hub reads as two different catalogs.
SOURCE_LABELS = {
    "model_reports": "Model reports",
    "llm_stats": "LLM Stats",
    "artificial_analysis": "Artificial Analysis",
    "opencompass_hub": "OpenCompass Hub",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def json_ld(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")


def website_reference() -> dict[str, Any]:
    """Self-describing `WebSite` node for `isPartOf`.

    A bare `{"@id": ...}` only resolves where that node is defined. Only the
    homepage and its route copies define `#website`, so Search Console reports
    `Invalid object type for field "isPartOf"` on every generated page that
    links to it. Carrying the type inline makes the reference valid anywhere.
    """
    return {
        "@type": "WebSite",
        "@id": f"{SITE_URL}/#website",
        "name": "Benchmark Radar",
        "url": f"{SITE_URL}/",
    }


def organization_reference() -> dict[str, Any]:
    """Self-describing `Organization` node, for the same reason as above."""
    return {
        "@type": "Organization",
        "@id": f"{SITE_URL}/#organization",
        "name": "Benchmark Radar",
        "url": f"{SITE_URL}/",
    }


def breadcrumb_schema(*items: tuple[str, str], canonical: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": url,
            }
            for position, (name, url) in enumerate(items, start=1)
        ],
    }


def webpage_schema(
    *, title: str, description: str, canonical: str, languages: Iterable[str] = ("en",)
) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": canonical,
        "name": title,
        "url": canonical,
        "description": description,
        "inLanguage": list(languages),
        "isPartOf": website_reference(),
    }
