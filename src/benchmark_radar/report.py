from __future__ import annotations

from collections import Counter
from datetime import UTC

from . import __version__
from .briefing import markdown_bullet
from .models import RadarItem, RadarRun


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _item_block(index: int, item: RadarItem) -> str:
    category = ", ".join(value.replace("_", " ") for value in item.categories)
    signals = ", ".join(f"{key}={value:g}" for key, value in item.metrics.items() if value)
    authors = ", ".join(item.authors[:4])
    if len(item.authors) > 4:
        authors += " et al."
    marker = f"⭐ {_escape(item.watchlist)} · " if item.watchlist else ""
    lines = [
        f"### {index}. [{_escape(item.title)}]({item.url})",
        "",
        f"**{marker}{item.source} · {item.event_kind} · {category} · "
        f"priority {item.total_score:.1f}/{item.score_max:.0f}**",
        "",
    ]
    if item.watchlist and item.watchlist_note:
        lines.extend([f"> {_escape(item.watchlist_note)}", ""])
    if item.summary:
        summary = _escape(item.summary)
        lines.extend([summary[:700] + ("…" if len(summary) > 700 else ""), ""])
    else:
        # Stated as an absence. A generated stand-in sentence would only
        # restate the source and event line directly above.
        lines.extend(["_No description published at the source._", ""])
    details = [
        f"Published/updated: `{item.published_at.date().isoformat()}`",
        f"Evidence: `{item.evidence_score:.2f}`",
        f"Relevance: `{item.relevance_score:.2f}`",
        f"Recency: `{item.recency_score:.2f}`",
    ]
    if authors:
        details.append(f"Authors: {_escape(authors)}")
    if signals:
        details.append(f"Signals: `{_escape(signals)}`")
    lines.extend([f"- {detail}" for detail in details])
    if item.rationale:
        lines.append(f"- Why surfaced: {_escape('; '.join(item.rationale))}")
    if item.artifact_urls:
        links = " · ".join(f"[related source]({url})" for url in item.artifact_urls[:4])
        lines.append(f"- Cross-source evidence: {links}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(
    run: RadarRun,
    dashboard_url: str | None = None,
    *,
    issue_item_limit: int | None = None,
    daily_briefing: list[str] | None = None,
) -> str:
    date = run.generated_at.astimezone(UTC).date().isoformat()
    category_counts = Counter(category for item in run.items for category in item.categories)
    source_counts = Counter(item.source for item in run.items)
    failed = [health for health in run.health if not health.ok]
    empty = [health for health in run.health if health.ok and health.item_count == 0]
    nonempty = [health for health in run.health if health.ok and health.item_count > 0]
    lines = [
        f"<!-- benchmark-radar:daily:{date} -->",
        f"<!-- generator: benchmark-radar/{__version__} -->",
        "",
        f"# 📡 AI Benchmark & Data Radar — {date}",
        "",
        f"Evidence-first daily scan from `{run.since.isoformat()}` to "
        f"`{run.generated_at.isoformat()}`.",
        "",
        "> Automated discovery and triage, not an endorsement. Open the primary source before "
        "using any claim.",
        "",
    ]
    if dashboard_url:
        separator = "&" if "?" in dashboard_url else "?"
        lines.extend(
            [
                f"**[Explore this day on the dashboard]({dashboard_url}{separator}date={date})**",
                "",
            ]
        )
    if daily_briefing:
        # Bullets are persisted as canonical plain text, so the Markdown and
        # HTML escaping happens here rather than in the stored value.
        lines.extend(
            [
                "## Daily briefing",
                "",
                *[f"- {_escape(markdown_bullet(bullet))}" for bullet in daily_briefing],
                "",
            ]
        )
    lines.extend(
        [
            "## At a glance",
            "",
            f"- **{len(run.items)}** ranked evidence items",
            f"- **{len(run.attention)}** unranked attention observations",
            "- Categories: "
            + (
                ", ".join(
                    f"{key.replace('_', ' ')} ({value})" for key, value in category_counts.items()
                )
                or "none"
            ),
            "- Sources represented: "
            + (", ".join(f"{key} ({value})" for key, value in source_counts.items()) or "none"),
            f"- Evidence ingest: **{len(nonempty)} nonempty · {len(empty)} empty · "
            f"{len(failed)} failed**",
            "",
        ]
    )
    if run.selection:
        selection = run.selection
        daily_total = selection.get("published_total")
        watchlisted = int(selection.get("watchlisted") or 0)
        # Watchlist hits bypass the threshold on purpose and are already inside
        # `qualified`, so subtract them before claiming how many cleared the
        # bar. Otherwise a lone bypass reads as "1 qualified (at or above 99)".
        by_threshold = int(selection.get("qualified", 0)) - watchlisted
        qualified = (
            f"**{selection.get('qualified', 0)}** qualified "
            f"({by_threshold} at or above {selection.get('minimum_score', 0):g}"
            + (f", {watchlisted} by watchlist" if watchlisted else "")
            + ")"
        )
        suppressed = int(selection.get("suppressed_as_seen") or 0)
        suppressed_future = int(selection.get("suppressed_future_dated") or 0)
        suppressed_low_value = int(selection.get("suppressed_low_value") or 0)
        lines.extend(
            [
                ("- Latest-pass selection: " if daily_total is not None else "- Selection: ")
                + f"**{selection.get('fetched', 0)}** fetched → "
                + (f"**{suppressed}** already seen → " if suppressed else "")
                + (
                    f"**{suppressed_future}** future-dated records quarantined → "
                    if suppressed_future
                    else ""
                )
                + f"**{selection.get('deduplicated', 0)}** after dedupe → "
                + (
                    f"**{suppressed_low_value}** low-value artifacts suppressed → "
                    if suppressed_low_value
                    else ""
                )
                + qualified
                + f" → **{selection.get('published', 0)}** published"
                + (
                    f"; **{daily_total}** across today's collection passes"
                    if daily_total is not None
                    else ""
                ),
                "",
            ]
        )
    tracked = [item for item in run.items if item.watchlist]
    if tracked:
        lines.extend(["## Watchlist", ""])
        for item in tracked:
            note = f" {_escape(item.watchlist_note)}" if item.watchlist_note else ""
            lines.append(
                f"- **{_escape(item.watchlist)}** — [{_escape(item.title)}]({item.url}) "
                f"({item.source} · {item.event_kind}).{note}"
            )
        lines.append("")
    if run.items:
        # GitHub Issue bodies have a hard size limit, so the digest is
        # truncated while the snapshot and dashboard keep every record.
        shown = run.items[:issue_item_limit] if issue_item_limit else run.items
        heading = "## Today's signals"
        if len(shown) < len(run.items):
            heading += f" (top {len(shown)} of {len(run.items)})"
        lines.extend([heading, ""])
        for index, item in enumerate(shown, start=1):
            lines.append(_item_block(index, item))
        if len(shown) < len(run.items):
            remaining = len(run.items) - len(shown)
            link = f"[the dashboard]({dashboard_url})" if dashboard_url else "the dashboard"
            lines.extend(
                [
                    f"_{remaining} further ranked records are published to {link}._",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "## No qualifying signals",
                "",
                "The scan completed but no records met the configured relevance threshold.",
                "",
            ]
        )
    lines.extend(
        [
            "## Source health",
            "",
            "| Source | Status | Records | Detail |",
            "|---|---:|---:|---|",
        ]
    )
    for health in run.health:
        detail = _escape(health.error or "")
        lines.append(
            f"| {health.source} | {'✅' if health.ok else '⚠️'} | {health.item_count} | {detail} |"
        )
    if run.attention_ingest_health or run.producer_health:
        lines.extend(
            [
                "",
                "## Attention-feed health",
                "",
                "| Layer | Source | Status | Records | Detail |",
                "|---|---|---:|---:|---|",
            ]
        )
        for health in run.attention_ingest_health:
            detail = _escape(health.error or "")
            lines.append(
                f"| Radar ingest | {health.source} | {'✅' if health.ok else '⚠️'} | "
                f"{health.item_count} | {detail} |"
            )
        for health in run.producer_health:
            detail = _escape(health.error or "")
            lines.append(
                f"| Producer report | {health.source} | {'✅' if health.ok else '⚠️'} | "
                f"{health.item_count} | {detail} |"
            )
    lines.extend(
        [
            "",
            "---",
            "",
            "Generated by [benchmark-radar](https://github.com/ktwu01/benchmark-radar). "
            "Scores combine topical relevance, primary-source evidence, recency, and transparent "
            "adoption signals. Missing optional API keys appear as source-health warnings.",
            "",
        ]
    )
    return "\n".join(lines)
