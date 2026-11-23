"""Hand-written blog posts, committed as files instead of generated from a snapshot.

Every other page under /blog/ is derived from one collection day, and the blog
tree is rebuilt wholesale on each run, so a page dropped into site/blog/ would
be deleted by the next build. A written post therefore lives in its own folder
under data/blog_posts/<slug>/ and is published through the same write_blog run:
same chrome, same index, same feed, same sitemap.

A folder is a post when it holds:

- post.json: title, description, published (YYYY-MM-DD), and optionally
  updated, tags, sources (a list of {"title", "url"}), and title_zh.
- body.html: the English body, already HTML.
- body.zh.html (optional): the Chinese body. Without it the page is English only.

Any other file in the folder (an image, a PDF) is copied beside the page, so
the body can reference it by a relative path.

A malformed post fails the build instead of being skipped: a post that
silently vanished from the blog would look like a deliberate removal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .blog_shell import BlogPost

KIND_ARTICLE = "article"

_POST_FILES = {"post.json", "body.html", "body.zh.html"}
# A daily brief's slug is its date, so a written post must not look like one.
_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class Article:
    post: BlogPost
    assets: tuple[Path, ...]


def _iso_day(meta: dict[str, Any], key: str, folder: Path) -> str:
    value = str(meta.get(key) or "")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{folder}/post.json: {key} must be YYYY-MM-DD, got {value!r}") from error
    return value


def _sources(meta: dict[str, Any], folder: Path) -> tuple[tuple[str, str, str], ...]:
    sources: list[tuple[str, str, str]] = []
    for entry in meta.get("sources") or []:
        url = str(entry.get("url") or "") if isinstance(entry, dict) else ""
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"{folder}/post.json: every source needs an http(s) url")
        sources.append(("", str(entry.get("title") or url), url))
    return tuple(sources)


def load_article(folder: Path) -> Article:
    slug = folder.name
    if not _SLUG.match(slug):
        raise ValueError(
            f"{folder}: a post slug is lowercase words and hyphens, starting with a letter"
        )
    meta = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    for key in ("title", "description"):
        if not str(meta.get(key) or "").strip():
            raise ValueError(f"{folder}/post.json: {key} is required")
    published = _iso_day(meta, "published", folder)
    updated = _iso_day(meta, "updated", folder) if meta.get("updated") else published
    zh_body = folder / "body.zh.html"
    has_zh = zh_body.is_file()
    post = BlogPost(
        slug=slug,
        title=str(meta["title"]).strip(),
        description=str(meta["description"]).strip(),
        published=published,
        updated=updated,
        kind=KIND_ARTICLE,
        tags=tuple(str(tag) for tag in meta.get("tags") or ()),
        sources=_sources(meta, folder),
        body_en=(folder / "body.html").read_text(encoding="utf-8"),
        body_zh=zh_body.read_text(encoding="utf-8") if has_zh else None,
        title_zh=(str(meta.get("title_zh") or "").strip() or None) if has_zh else None,
    )
    assets = tuple(
        sorted(path for path in folder.iterdir() if path.is_file() and path.name not in _POST_FILES)
    )
    return Article(post=post, assets=assets)


def load_articles(articles_dir: Path | None) -> list[Article]:
    """Every post folder under ``articles_dir``, in slug order; none when it is absent."""
    if articles_dir is None or not articles_dir.is_dir():
        return []
    folders = sorted(
        path for path in articles_dir.iterdir() if path.is_dir() and (path / "post.json").is_file()
    )
    return [load_article(folder) for folder in folders]
