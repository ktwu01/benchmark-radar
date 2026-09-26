"""Generate the research browser with the dashboard's canonical navigation."""

import json
from pathlib import Path

from .blog_shell import chrome_i18n_table, extract_site_chrome


def write_research_page(site_dir: Path) -> str:
    dashboard = (site_dir / "index.html").read_text(encoding="utf-8")
    chrome = extract_site_chrome(dashboard, active_path="/research/")
    translations = chrome_i18n_table(
        chrome, (site_dir / "assets/app.js").read_text(encoding="utf-8")
    )
    template = (Path(__file__).parent / "templates/research.html").read_text(encoding="utf-8")
    i18n = json.dumps(translations, ensure_ascii=False).replace("<", "\\u003c")
    page = template.replace("{{header}}", chrome.header).replace(
        "{{i18n}}", f'<script id="chrome-i18n" type="application/json">{i18n}</script>'
    )
    destination = site_dir / "research/index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(page, encoding="utf-8")
    return "/research/"
