"""Turn one committed daily snapshot into one rendered brief.

Nothing in here calls a model or reaches the network. The briefing text, the
question answers, the Chinese translation and the citations were all written
when the snapshot was produced and stored in it; this module only decides how
to lay them out. That is what makes a rebuild deterministic and what makes the
`classify` step safe to run in CI.

Three kinds of day exist in the committed history, and each gets a page that
says which kind it is:

* a snapshot with a full stored briefing, which is the normal case;
* a snapshot whose briefing reported ``no_material_insight``, which is a
  finding and is published unchanged, because "nothing moved enough to call it
  a change" is the honest report for that day and hiding it would leave a hole
  in the record;
* an early snapshot from before briefings were stored, which gets a labelled
  deterministic summary of the evidence it does hold and never pretends to be
  a synthesized briefing.

A field the snapshot does not carry is omitted, never filled in. The old build
printed "briefing model: deterministic snapshot summary" and "0 of 0" evidence
records for a day that had simply stored bullets without generator metadata,
which invents provenance for text nobody can trace.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .blog_shell import BlogPost
from .site_shell import esc

_DESCRIPTION_LIMIT = 155
_EVIDENCE_FALLBACK_LIMIT = 10
_CITATION_FALLBACK_LIMIT = 20

KIND_BRIEF = "Daily brief"
KIND_NO_CHANGE = "No material change"
KIND_EVIDENCE = "Evidence summary"

_LABELS = {
    "en": {
        "briefing": "Daily briefing",
        "evidence": "What the radar collected that day",
        "sources": "Evidence sources",
        "provenance": "Where this came from, and what it does not cover",
        "takeaway": "Takeaway",
        "counter": "Another reading",
        "insufficient": "Not enough evidence",
        "questions": "Questions",
        "confidence": "confidence",
        "empty": "No evidence observations were recorded for this day.",
    },
    "zh": {
        "briefing": "每日简报",
        "evidence": "当天雷达收集到的内容",
        "sources": "证据来源",
        "provenance": "内容来源与局限",
        "takeaway": "结论",
        "counter": "另一种解读",
        "insufficient": "证据不足",
        "questions": "问题",
        "confidence": "置信度",
        "empty": "当天没有记录到任何证据观察。",
    },
}

# The question and group headings are the fixed prompts in questions.py, stored
# in English in every snapshot because that is the text the model was asked.
# The dashboard translates them client-side against the same English keys, so a
# Chinese brief has to do the same or it publishes English headings inside a
# document declared zh-CN. Keys the table does not carry fall back to English,
# which is what the dashboard does with the same string.
# tests/test_blog.py checks every value here against the dashboard's table, so
# the two surfaces cannot drift into translating the same prompt differently.
_QUESTION_ZH = {
    "What arrived": "今日新增",
    "What is still moving": "仍在变动",
    "What it means": "这意味着什么",
    "What benchmarks, datasets, or evaluation methods did the radar first see today?": (
        "雷达今天首次看到了哪些benchmark、数据集或评估方法？"
    ),
    "Which of today's arrivals document how they score an answer?": (
        "今天的哪些新增条目记录了它们如何给答案评分？"
    ),
    "Which artifacts the radar already tracked moved measurably, and over what span?": (
        "雷达已跟踪的哪些条目出现了可测变动，跨度如何？"
    ),
    "Which of that movement is corroborated by more than one data source?": (
        "其中哪些变动得到了不止一个数据源的印证？"
    ),
    "What does today's evidence fail to show, and what would change the reading?": (
        "今天的证据未能说明什么，什么会改变这一解读？"
    ),
    "What should someone building or evaluating AI systems do differently today?": (
        "构建或评估 AI 系统的人今天应该做哪些不同的选择？"
    ),
}


def _safe_url(value: Any) -> str | None:
    """Accept only an absolute http(s) URL, so a stored value cannot inject a scheme."""
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _briefing_of(snapshot: dict[str, Any]) -> dict[str, Any]:
    briefing = snapshot.get("briefing")
    return briefing if isinstance(briefing, dict) else {}


def _answers(snapshot: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every stored answer, paired with the title of the group it belongs to."""
    groups = (snapshot.get("questions") or {}).get("groups") or []
    return [
        (str(group.get("title") or _LABELS["en"]["questions"]), answer)
        for group in groups
        for answer in group.get("answers") or []
        if isinstance(answer, dict)
    ]


def _attention(snapshot: dict[str, Any]) -> list[Any]:
    raw = snapshot.get("attention")
    if isinstance(raw, dict):
        return list(raw.get("observations") or [])
    return list(raw or [])


def has_translation(snapshot: dict[str, Any]) -> bool:
    """True when the snapshot stored reviewed Chinese text for this day."""
    if _briefing_of(snapshot).get("bullets_zh"):
        return True
    return any(
        answer.get("signal_zh") or answer.get("plain_chinese") for _, answer in _answers(snapshot)
    )


def _clip(text: str, *, trailing: str = ".,;:") -> str:
    text = " ".join(str(text).split())
    if len(text) <= _DESCRIPTION_LIMIT:
        return text
    return text[:_DESCRIPTION_LIMIT].rsplit(" ", 1)[0].rstrip(trailing) + "…"


def _description(snapshot: dict[str, Any]) -> str:
    bullets = _briefing_of(snapshot).get("bullets") or []
    if bullets:
        return _clip(str(bullets[0]).split(" Why it matters:", 1)[0])
    evidence = snapshot.get("evidence_items") or []
    sources = {str(item.get("source") or "") for item in evidence if item.get("source")}
    return (
        f"Benchmark Radar collected {len(evidence)} evidence observations from "
        f"{len(sources)} sources on {snapshot.get('date')}."
    )


def _citations(
    snapshot: dict[str, Any], *, allow_fallback: bool
) -> tuple[tuple[str, str, str], ...]:
    """The documents this day's text actually cited, each with its stored ID.

    The briefing prose cites evidence by ID ("Evidence: E011"), and the IDs are
    not contiguous, so the list position is not the ID. Carrying the stored
    identifier through is what lets a reader resolve a cited ID to its link;
    without it a page can say E011 and show that document as item 3.

    A ``no_material_insight`` briefing cites nothing by design, but its question
    answers still cite the records they read, so those days are not left with an
    empty source list.

    ``allow_fallback`` backfills the day's own evidence when a stored briefing
    cited nothing at all, so its claims still lead somewhere. It is off for a
    day with no briefing, because that page already lists its evidence records
    and would otherwise print the same links twice under two headings. Those
    backfilled records were not cited by ID, so they carry no identifier.
    """
    citations: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def collect(entries: Any) -> None:
        for citation in entries or []:
            if not isinstance(citation, dict):
                continue
            url = _safe_url(citation.get("url"))
            if url is None or url in seen:
                continue
            seen.add(url)
            title = str(citation.get("title") or citation.get("source") or url).strip()
            citations.append((str(citation.get("id") or "").strip(), title, url))

    collect(_briefing_of(snapshot).get("citations"))
    for _, answer in _answers(snapshot):
        collect(answer.get("cited_evidence"))
    if citations or not allow_fallback:
        return tuple(citations)
    for item in snapshot.get("evidence_items") or []:
        url = _safe_url(item.get("url"))
        if url is None or url in seen:
            continue
        seen.add(url)
        citations.append(("", str(item.get("title") or item.get("source") or url), url))
        if len(citations) == _CITATION_FALLBACK_LIMIT:
            break
    return tuple(citations)


def _stats(snapshot: dict[str, Any]) -> str:
    evidence = snapshot.get("evidence_items") or []
    sources = {str(item.get("source") or "") for item in evidence if item.get("source")}
    sources.discard("")
    cells = (
        (len(evidence), "evidence observations"),
        (len(sources), "sources represented"),
        (len(_attention(snapshot)), "public-attention signals"),
    )
    return "".join(
        f'<div class="blog-stat"><strong>{value:,}</strong><span>{label}</span></div>'
        for value, label in cells
    )


def _section(heading: str, body: str) -> str:
    return (
        '<section class="blog-section">'
        f'<div class="blog-section-heading"><h2>{esc(heading)}</h2></div>'
        f"{body}</section>"
    )


def _briefing_section(snapshot: dict[str, Any], language: str) -> str:
    """The stored briefing bullets, or a labelled evidence list for a legacy day."""
    labels = _LABELS[language]
    briefing = _briefing_of(snapshot)
    bullets = briefing.get("bullets_zh" if language == "zh" else "bullets") or briefing.get(
        "bullets"
    )
    if bullets:
        items = "".join(f'<li class="blog-card">{esc(bullet)}</li>' for bullet in bullets)
        return _section(labels["briefing"], f'<ol class="blog-index">{items}</ol>')
    rendered: list[str] = []
    for item in (snapshot.get("evidence_items") or [])[:_EVIDENCE_FALLBACK_LIMIT]:
        title = esc(item.get("title") or "Untitled")
        url = _safe_url(item.get("url"))
        heading = f'<a href="{esc(url)}">{title}</a>' if url else title
        source = esc(item.get("source") or "Unknown source")
        rendered.append(f'<li class="blog-card">{heading}<p>{source}</p></li>')
    items = "".join(rendered) or f'<li class="blog-card">{esc(labels["empty"])}</li>'
    return _section(labels["evidence"], f'<ol class="blog-index">{items}</ol>')


def _stat_line(stat: dict[str, Any]) -> str:
    """One cited figure, shown with the S### ID the answer text refers to.

    The answers cite figures by registry ID rather than by name, so a line that
    prints only the label leaves the reader unable to match "S020" in the prose
    to the number underneath it.
    """
    value = stat.get("value")
    rendered = f"{value:,}" if isinstance(value, (int, float)) else str(value or "—")
    unit = str(stat.get("unit") or "").strip()
    suffix = f" {unit}" if unit and unit != "count" else ""
    identifier = str(stat.get("id") or "").strip()
    label = str(stat.get("label") or identifier or "Statistic")
    prefix = _cite_id(identifier) if identifier and label != identifier else ""
    return f"{prefix}{esc(label)}: <strong>{esc(rendered)}{esc(suffix)}</strong>"


def _prompt(text: str, language: str) -> str:
    """A fixed question or group heading in the reading language."""
    if language != "zh":
        return text
    return _QUESTION_ZH.get(text, text)


def _answer_html(answer: dict[str, Any], language: str) -> str:
    labels = _LABELS[language]
    zh = language == "zh"

    def pick(base: str, translated_key: str) -> str:
        value = answer.get(translated_key) if zh else None
        return str(value or answer.get(base) or "").strip()

    question = _prompt(pick("question", "question_zh"), language) or labels["questions"]
    signal = pick("signal", "signal_zh")
    plain = pick("plain_english", "plain_chinese")
    takeaway = pick("takeaway", "takeaway_zh")
    counter = pick("counter_view", "counter_view_zh")
    confidence = str(answer.get("confidence") or "unrated")
    stats = "".join(f"<li>{_stat_line(stat)}</li>" for stat in answer.get("cited_stats") or [])
    stats_html = f'<ul class="blog-list">{stats}</ul>' if stats else ""
    status_html = (
        f'<span class="blog-chip">{esc(labels["insufficient"])}</span>'
        if not answer.get("sufficient_evidence", True)
        else ""
    )
    body = "".join(f"<p>{esc(text)}</p>" for text in (signal, plain) if text)
    if takeaway:
        body += f"<p><strong>{esc(labels['takeaway'])}:</strong> {esc(takeaway)}</p>"
    if counter:
        body += (
            f'<p class="blog-caveat"><strong>{esc(labels["counter"])}:</strong> {esc(counter)}</p>'
        )
    return (
        '<article class="blog-panel">'
        f"<h3>{esc(question)}</h3>"
        f'<div class="blog-tags"><span class="blog-chip">'
        f"{esc(confidence)} {esc(labels['confidence'])}</span>{status_html}</div>"
        f"{body}{stats_html}</article>"
    )


def _questions_section(snapshot: dict[str, Any], language: str) -> str:
    grouped: dict[str, list[str]] = {}
    for title, answer in _answers(snapshot):
        grouped.setdefault(title, []).append(_answer_html(answer, language))
    return "".join(
        _section(_prompt(title, language), "".join(items)) for title, items in grouped.items()
    )


def _provenance_section(snapshot: dict[str, Any], language: str) -> str:
    """State exactly what produced this page, using only fields the snapshot has."""
    labels = _LABELS[language]
    zh = language == "zh"
    briefing = _briefing_of(snapshot)
    corpus = len(snapshot.get("evidence_items") or [])
    lines: list[str] = []
    if not briefing:
        lines.append(
            f"这一天的快照没有存储简报，本页是对其 {corpus:,} 条证据记录的确定性汇总，"
            "而非综合分析。"
            if zh
            else "No briefing was stored for this day, so this page is a deterministic "
            f"summary of the {corpus:,} evidence records the snapshot holds, not a "
            "synthesized briefing."
        )
    else:
        lines.append(
            f"内容来自已验证的每日快照，共 {corpus:,} 条证据记录。"
            if zh
            else f"Built from the validated daily snapshot and its {corpus:,} evidence records."
        )
        model = str(briefing.get("model") or "").strip()
        coverage = (briefing.get("input") or {}).get("coverage") or {}
        injected = coverage.get("evidence_injected")
        total = coverage.get("corpus_evidence_records")
        if model:
            lines.append(f"简报模型：{model}。" if zh else f"Briefing model: {model}.")
        if isinstance(injected, int) and isinstance(total, int):
            lines.append(
                f"实际读取了 {total:,} 条记录中的 {injected:,} 条。"
                if zh
                else f"It read {injected:,} of {total:,} records."
            )
        if not model and injected is None:
            lines.append(
                "该快照保存了简报文本，但没有保存生成它的模型或覆盖范围信息。"
                if zh
                else "The snapshot stored the briefing text without recording the model "
                "that produced it or how much of the corpus it read."
            )
    caveat = str(
        briefing.get("caveat_zh" if zh else "caveat") or briefing.get("caveat") or ""
    ).strip()
    caveat_html = f'<p class="blog-caveat">{esc(caveat)}</p>' if caveat else ""
    body = "".join(f"<p>{esc(line)}</p>" for line in lines)
    return (
        '<section class="blog-section blog-panel">'
        f"<h2>{esc(labels['provenance'])}</h2>{body}{caveat_html}</section>"
    )


def _sources_section(sources: tuple[tuple[str, str, str], ...], language: str) -> str:
    if not sources:
        return ""
    links = "".join(
        f'<li>{_cite_id(identifier)}<a href="{esc(url)}">{esc(title)}</a></li>'
        for identifier, title, url in sources
    )
    # Unnumbered on purpose: the stored ID is how the prose refers to a source,
    # and a list counter beside it reads as a second, contradictory number.
    return _section(_LABELS[language]["sources"], f'<ul class="blog-evidence">{links}</ul>')


def _cite_id(identifier: str) -> str:
    """The stored citation ID, shown so prose that says E011 can be followed."""
    return f'<span class="blog-cite-id">{esc(identifier)}</span> ' if identifier else ""


def _kind(snapshot: dict[str, Any]) -> str:
    briefing = _briefing_of(snapshot)
    if not briefing:
        return KIND_EVIDENCE
    if str(briefing.get("status") or "") == "no_material_insight":
        return KIND_NO_CHANGE
    return KIND_BRIEF


def build_post(snapshot: dict[str, Any]) -> BlogPost:
    """Render one snapshot into a publishable brief."""
    day = str(snapshot["date"])
    kind = _kind(snapshot)
    sources = _citations(snapshot, allow_fallback=kind != KIND_EVIDENCE)

    def body(language: str) -> str:
        return (
            f'<div class="blog-stats">{_stats(snapshot)}</div>'
            + _briefing_section(snapshot, language)
            + _questions_section(snapshot, language)
            + _sources_section(sources, language)
            + _provenance_section(snapshot, language)
        )

    translated = has_translation(snapshot)
    if kind == KIND_EVIDENCE:
        title = f"Benchmark evidence summary: {day}"
        title_zh = f"Benchmark 证据汇总：{day}"
    else:
        title = f"Daily AI benchmark brief: {day}"
        title_zh = f"AI Benchmark 每日简报：{day}"
    generated = str(snapshot.get("generated_at") or day)
    return BlogPost(
        slug=day,
        title=title,
        description=_description(snapshot),
        published=day,
        updated=generated[:10] if len(generated) >= 10 else day,
        kind=kind,
        tags=("daily brief", "AI benchmarks", "evaluation"),
        sources=sources,
        body_en=body("en"),
        body_zh=body("zh") if translated else None,
        title_zh=title_zh if translated else None,
    )
