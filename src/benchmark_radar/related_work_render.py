from __future__ import annotations

import re
import unicodedata
from typing import Any

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_LOWER_GREEK = dict(
    zip(
        "αβγδεζηθικλμνξπρςστυφχψω",
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho "
        "varsigma sigma tau upsilon phi chi psi omega".split(),
        strict=True,
    )
)
# Capital Greek letters that have their own LaTeX command; the rest are drawn
# identically to a Latin capital, which pdflatex can typeset.
_UPPER_GREEK = frozenset("Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega".split())
_LATIN_LOOKALIKE = {
    "Alpha": "A",
    "Beta": "B",
    "Epsilon": "E",
    "Zeta": "Z",
    "Eta": "H",
    "Iota": "I",
    "Kappa": "K",
    "Mu": "M",
    "Nu": "N",
    "Omicron": "O",
    "Rho": "P",
    "Tau": "T",
    "Chi": "X",
}
# Characters pdflatex (utf8 inputenc, T1 fonts) typesets without extra packages.
_TYPESET_PUNCTUATION = frozenset(
    "\u2018\u2019\u201c\u201d\u2013\u2014\u2022\u0218\u0219\u021a\u021b"
)
_WE_VERB = re.compile(r"^We (\w+)\s+(.*)$", re.DOTALL | re.IGNORECASE)


def _latex_char(char: str) -> str:
    if char in _LATEX_SPECIALS:
        return _LATEX_SPECIALS[char]
    # pdflatex with inputenc rejects Greek text characters, which arXiv titles
    # use for names such as tau-bench; math-mode commands work in every engine.
    name = unicodedata.name(char, "")
    if char in _LOWER_GREEK:
        return f"\\ensuremath{{\\{_LOWER_GREEK[char]}}}"
    if char == "ο":
        return "o"
    if name.startswith("GREEK CAPITAL LETTER ") and name.count(" ") == 3:
        letter = name.rsplit(" ", 1)[-1].capitalize()
        if letter in _UPPER_GREEK:
            return f"\\ensuremath{{\\{letter}}}"
        return _LATIN_LOOKALIKE.get(letter, "")
    if ord(char) <= 0x17F or char in _TYPESET_PUNCTUATION:
        return char
    # CJK text, emoji, and other scripts stop a pdflatex run outright; a
    # dropped glyph costs a character, an unknown one costs the whole paper.
    return ""


def latex_escape(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\u2026", "...")
    return re.sub(r" {2,}", " ", "".join(_latex_char(char) for char in value)).strip()


def _sentence(entry: dict[str, Any], *, natbib: bool) -> str:
    key, name, summary = entry["cite_key"], entry["name"], entry["summary"]
    cite = "citep" if natbib else "cite"
    if not summary:
        return f"{latex_escape(name)}~\\{cite}{{{key}}}."
    we_verb = _WE_VERB.match(summary)
    if we_verb and entry["authors"] and natbib:
        return f"\\citet{{{key}}} {we_verb.group(1)} {latex_escape(we_verb.group(2))}"
    if summary.casefold().startswith(name.casefold()):
        rest = summary[len(name) :].lstrip()
        if re.match(r"(a|an|the)\s", rest, re.IGNORECASE):
            rest = f"is {rest}"
        joiner = "" if rest[:1] in {",", ":", ";", "."} else " "
        return f"{latex_escape(name)}~\\{cite}{{{key}}}{joiner}{latex_escape(rest)}"
    return f"{latex_escape(name)}~\\{cite}{{{key}}}: {latex_escape(summary)}"


def render_latex(
    topics: list[dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    *,
    natbib: bool = False,
) -> str:
    lines = ["\\section{Related Work}", "\\label{sec:related-work}"]
    described: set[str] = set()
    cite = "citep" if natbib else "cite"
    for topic in topics:
        lines.extend(["", f"\\paragraph{{{latex_escape(topic['label'])}.}}"])
        fresh = [key for key in topic["cite_keys"] if key not in described]
        seen = [key for key in topic["cite_keys"] if key in described]
        body = [_sentence(entries[key], natbib=natbib) for key in fresh]
        body = [text if text.endswith((".", "...")) else f"{text}." for text in body]
        if seen:
            body.append(f"See also~\\{cite}{{{', '.join(seen)}}}.")
        described.update(fresh)
        if body:
            lines.append("\n".join(body))
    return "\n".join(lines) + "\n"


def _flag(value: bool) -> str:
    return "yes" if value else "no"


def render_markdown(
    topics: list[dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    *,
    coverage: dict[str, Any],
) -> str:
    lines = ["## Related work candidates", "", coverage["statement"], "", "### Topics", ""]
    for topic in topics:
        statuses = ", ".join(
            f"{scope}: {status}" for scope, status in topic["search_status"].items()
        )
        kept = len(topic["cite_keys"])
        lines.append(f"- **{topic['label']}** (`{topic['query']}`): {kept} kept; {statuses}")
    lines.extend(
        [
            "",
            "### Comparison",
            "",
            "| Work | Cite key | Topics | Record | Paper | Repo | Dataset | Openness | Verify |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in entries.values():
        axes = entry["axes"]
        name = entry["name"].replace("|", "\\|")
        work = f"[{name}]({entry['url']})" if entry["url"] else name
        record = "catalog" if entry["kind"] == "catalog" else "Radar lead"
        lines.append(
            f"| {work} | `{entry['cite_key']}` | {'; '.join(entry['topics'])} | {record} | "
            f"{_flag(axes['has_paper'])} | {_flag(axes['has_repo'])} | "
            f"{_flag(axes['has_dataset'])} | {axes['openness']} | "
            f"{', '.join(entry['verification']) or 'none'} |"
        )
    return "\n".join(lines) + "\n"
