"""Compact resource links sharing the homepage's source marks."""

from urllib.parse import urlsplit

from .site_shell import esc

_PROVIDERS = {
    "github.com": ("GitHub", "github"),
    "huggingface.co": ("Hugging Face", "huggingface"),
    "arxiv.org": ("arXiv", "arxiv"),
    "news.ycombinator.com": ("Hacker News", "hackernews"),
    "semanticscholar.org": ("Semantic Scholar", "semanticscholar"),
}


def resource_link(url: str, label: str, *, distinguish: bool = False) -> str:
    """Render an already validated HTTP link; unknown hosts retain a text label."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").removeprefix("www.")
    if distinguish:
        label = f"{label} · {url}"
    provider, brand = _PROVIDERS.get(host, (host, None))
    mark = (
        '<svg class="brand-icon" viewBox="0 0 24 24" aria-hidden="true">'
        f'<use href="/assets/source-icons.svg#{brand}"></use></svg>'
        if brand
        else f"<span>{esc(provider)}</span>"
    )
    return (
        f'<a class="radar-source benchmark-resource-link" href="{esc(url)}" '
        f'aria-label="{esc(label)} · {esc(provider)}" title="{esc(url)}" '
        'rel="nofollow noopener">'
        f'<span>{esc(label)}</span>{mark}<span aria-hidden="true">↗</span></a>'
    )
