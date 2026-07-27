import json
from html.parser import HTMLParser
from pathlib import Path


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()
        self.html_lang = ""
        self.viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append(tag)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "html":
            self.html_lang = str(values.get("lang", ""))
        if tag == "meta" and values.get("name") == "viewport":
            self.viewport = True


def test_site_has_accessible_landmarks_and_views():
    parser = SiteParser()
    parser.feed(Path("site/index.html").read_text(encoding="utf-8"))

    assert parser.html_lang == "en"
    assert parser.viewport
    assert {"header", "nav", "main", "footer", "dialog"} <= set(parser.tags)
    assert {"today-view", "trends-view", "explorer-view", "main-content"} <= parser.ids


def test_site_does_not_render_source_content_as_html():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert ".innerHTML" not in script
    assert ".outerHTML" not in script
    assert "document.write" not in script
    assert " eval(" not in script


def test_public_feed_configuration_is_versioned_and_https():
    config = json.loads(Path("site/data/feeds.json").read_text(encoding="utf-8"))

    assert config["schema_version"] == 1
    assert config["feeds"]
    assert all(feed["url"].startswith("https://") for feed in config["feeds"])


def test_attention_signals_use_activity_metrics_not_quality_scores():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert 'text: "Not quality-scored"' in script
    assert '["Submissions", Number(item.metrics?.submissions || 1).toLocaleString()]' in script
    assert '["Published", formatDate(item.published_at' in script
    assert "supporting_observations" in script
    assert 'total_score: 0' not in script
    assert 'evidence_score: 0' not in script


def test_explorer_clusters_attention_by_normalized_title():
    script = Path("site/assets/app.js").read_text(encoding="utf-8")

    assert "function clusterAttentionRecords(items)" in script
    assert "normalizedRecordTitle(item.title)" in script
    assert "state.external = clusterAttentionRecords(" in script
