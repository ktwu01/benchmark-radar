"""Clean the author and institution names a share card shows (issue #1162).

Daily cards merge creators from several sources (arXiv, OpenAlex, DataCite,
arXiv HTML), and each leaves its own debris: one person written two ways
("Yi-Zhen Jiang", "Yizhen Jiang"), LaTeX escapes (``R\\'e``), a truncated
"Anonymous Author(s", two institutions run together ("Stanford University
Cornell University"). The card image, its caption and the X post all read
these lists, so they are cleaned once where the share block is built.

Every rule here only rewrites or merges values that are already present.
None of them guesses a name, so a value no rule recognises is kept as is.
"""

from __future__ import annotations

import re
import unicodedata

from .paper_institutions import _INSTITUTION_HINT

# LaTeX accent commands and the combining mark each stands for.
_ACCENTS = {
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    '"': "\u0308",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030c",
    "H": "\u030b",
    "c": "\u0327",
    "k": "\u0328",
}
_ACCENT = re.compile(r"\\([`'^\"~=.]|[uvHck](?![A-Za-z]))\s*\{?\s*(\\[ij]|[A-Za-z])(?:\s*\})?")
_LETTER_COMMANDS = {
    "ss": "ß",
    "o": "ø",
    "O": "Ø",
    "ae": "æ",
    "AE": "Æ",
    "oe": "œ",
    "OE": "Œ",
    "aa": "å",
    "AA": "Å",
    "l": "ł",
    "L": "Ł",
    "i": "ı",
    "j": "ȷ",
}
_GREEK = {
    name: chr(code)
    for name, code in {
        "alpha": 0x3B1,
        "beta": 0x3B2,
        "gamma": 0x3B3,
        "delta": 0x3B4,
        "epsilon": 0x3B5,
        "zeta": 0x3B6,
        "eta": 0x3B7,
        "theta": 0x3B8,
        "iota": 0x3B9,
        "kappa": 0x3BA,
        "lambda": 0x3BB,
        "mu": 0x3BC,
        "nu": 0x3BD,
        "xi": 0x3BE,
        "pi": 0x3C0,
        "rho": 0x3C1,
        "sigma": 0x3C3,
        "tau": 0x3C4,
        "upsilon": 0x3C5,
        "phi": 0x3C6,
        "chi": 0x3C7,
        "psi": 0x3C8,
        "omega": 0x3C9,
        "Gamma": 0x393,
        "Delta": 0x394,
        "Theta": 0x398,
        "Lambda": 0x39B,
        "Pi": 0x3A0,
        "Sigma": 0x3A3,
        "Phi": 0x3A6,
        "Psi": 0x3A8,
        "Omega": 0x3A9,
    }.items()
}
_COMMAND = re.compile(r"\\([A-Za-z]+)\s*")
# "{zhangshao,hushuyue}@pjlab.org.cn" and plain addresses beside a name.
_EMAIL = re.compile(r"\s*(?:\{[^{}]*\}|[\w.+-]+)@[\w-]+(?:\.[\w-]+)+")
# A street address that arXiv HTML lists as its own affiliation row
# ("Nashville, TN 37235, USA"). A row that also names a department or
# hospital is an affiliation with its address and is kept.
_ADDRESS = re.compile(r",\s*[A-Z]{2}\s+\d{5}(?:-\d{3,4})?\b")
# Contact lines that templates run into the affiliation text.
_CONTACT_TAIL = re.compile(
    r"\s*(?:Correspondence|Corresponding author|E-?mails?|Contact)\b.*$|\s*\*\s*Corresponding.*$",
    re.IGNORECASE,
)


def decode_latex(text: str) -> str:
    """Turn the LaTeX that conversions leave in names into plain text."""
    if "\\" not in text and "$" not in text and "{" not in text:
        return text

    def accent(match: re.Match[str]) -> str:
        base = match.group(2)
        base = {"\\i": "i", "\\j": "j"}.get(base, base)
        return unicodedata.normalize("NFC", base + _ACCENTS[match.group(1)])

    value = _ACCENT.sub(accent, text)

    def command(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _GREEK:
            return _GREEK[name]
        if name in _LETTER_COMMANDS:
            return _LETTER_COMMANDS[name]
        # Layout commands such as \addr or \textbf carry no text of their own.
        return ""

    value = _COMMAND.sub(command, value)
    value = value.replace("$", "").replace("{", "").replace("}", "")
    return " ".join(value.split())


def _close_brackets(text: str) -> str:
    # "Anonymous Author(s" lost its closing bracket where a field was cut.
    missing = text.count("(") - text.count(")")
    return text + ")" * missing if missing > 0 else text


def _letters(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if char.isalpha()).casefold()


def name_key(name: str) -> str:
    """Spelling-insensitive key: "Yi-Zhen Jiang" and "Yizhen Jiang" match."""
    return _letters(name)


def _parts(name: str) -> tuple[str, str]:
    words = name.replace(".", ". ").split()
    return (_letters(words[0]), _letters(words[-1])) if len(words) > 1 else ("", "")


def _is_initial(word: str) -> bool:
    return len(word) == 1


def _same_person(short: str, full: str) -> bool:
    """True when ``short`` abbreviates ``full``: "A. Gustafson" and "Aaron
    Gustafson", or "Jennifer Mankoff" and "Jennifer C. Mankoff"."""
    first_a, last_a = _parts(short)
    first_b, last_b = _parts(full)
    if not last_a or last_a != last_b or not first_a or not first_b:
        return False
    if first_a == first_b:
        return True
    return (_is_initial(first_a) or _is_initial(first_b)) and first_a[0] == first_b[0]


def clean_authors(names: list[str]) -> tuple[list[str], list[str]]:
    """Return (authors, affiliations found inside author values).

    "Yangze Liu (Shandong University)" yields the author "Yangze Liu" and the
    affiliation "Shandong University". Duplicates merge into the fullest
    spelling, in the position the person first appeared.
    """
    people: list[str] = []
    found_affiliations: list[str] = []
    for raw in names:
        name = _close_brackets(decode_latex(" ".join(str(raw).split())))
        trailing = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", name)
        if trailing and not re.search(r"\bauthors?\b", trailing.group(1), re.IGNORECASE):
            name, affiliation = trailing.group(1).strip(), trailing.group(2).strip()
            found_affiliations.append(affiliation)
        if not name:
            continue
        key = name_key(name)
        match = next(
            (index for index, kept in enumerate(people) if name_key(kept) == key),
            None,
        )
        if match is None:
            candidates = [index for index, kept in enumerate(people) if _same_person(kept, name)]
            # Two different people can share a surname and an initial, so an
            # abbreviation merges only when it fits exactly one listed name.
            match = candidates[0] if len(candidates) == 1 else None
        if match is None:
            people.append(name)
        elif len(name_key(name)) > len(name_key(people[match])):
            people[match] = name
    return people, found_affiliations


_INSTITUTION_END = r"(?:University|Institute|Academy|Laboratory|College)"
_INSTITUTION_WORD = re.compile(r"\b(?:University|Institute|Academy|Laboratory|College|School)\b")
# Words that continue the same institution after "University": "University
# College London", "Stanford University School of Medicine".
_CONTINUES = {
    "of",
    "for",
    "and",
    "at",
    "in",
    "the",
    "&",
    "College",
    "School",
    "Hospital",
    "Medical",
    "Press",
    "Library",
    "Health",
    "Center",
    "Centre",
    "Graduate",
    "Business",
    "Law",
    "Medicine",
    "System",
    "Systems",
}
_STOPWORDS = {"of", "for", "and", "at", "in", "the", "&"}


def _split_one(value: str) -> list[str]:
    words = value.split()
    for cut in range(2, len(words) - 1):
        left, right = words[:cut], words[cut:]
        if right[0] in _CONTINUES or not right[0][:1].isupper():
            continue
        if left[-1] in _STOPWORDS:
            continue
        left_text, right_text = " ".join(left), " ".join(right)
        right_is_institution = bool(
            re.search(rf"\b{_INSTITUTION_END}$", right_text)
            or re.match(rf"^{_INSTITUTION_END} of\b", right_text)
            or (
                _INSTITUTION_WORD.search(right_text)
                and re.search(rf"{_INSTITUTION_END}$", left_text)
            )
        )
        left_is_institution = bool(
            re.search(rf"\b{_INSTITUTION_END}$", left_text)
            or re.match(rf"^{_INSTITUTION_END} of\b", left_text)
        )
        if left_is_institution and right_is_institution and len(right) >= 2:
            return [left_text, *_split_one(right_text)]
    return [value]


def split_institutions(value: str) -> list[str]:
    """Split names run together without a separator.

    "Stanford University Cornell University" becomes two institutions;
    "University College London" and "Massachusetts Institute of Technology"
    stay whole. A value with a comma or semicolon is already separated.
    """
    if "," in value or ";" in value:
        return [value]
    return _split_one(value)


def clean_affiliations(values: list[str], authors: list[str]) -> list[str]:
    author_keys = {name_key(name) for name in authors}
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = decode_latex(_EMAIL.sub("", " ".join(str(raw).split())))
        value = _close_brackets(_CONTACT_TAIL.sub("", value).strip(" ,;:"))
        if not value or (_ADDRESS.search(value) and not _INSTITUTION_HINT.search(value)):
            continue
        # "Chia-Jung Lee, Vanessa Murdock": the author list again, not a place.
        names = [name for name in re.split(r",\s*|\s+and\s+", value) if name.strip()]
        if author_keys and all(name_key(name) in author_keys for name in names):
            continue
        for part in split_institutions(value):
            key = name_key(part)
            # A person's name in the institution list is already an author.
            if not key or key in seen or key in author_keys:
                continue
            seen.add(key)
            cleaned.append(part)
    return cleaned


def clean_creators(authors: list[str], affiliations: list[str]) -> dict[str, list[str]]:
    people, from_authors = clean_authors(authors)
    return {
        "authors": people,
        "affiliations": clean_affiliations([*affiliations, *from_authors], people),
    }
