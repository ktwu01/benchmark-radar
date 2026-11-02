"""Exercise consent transitions through the actual browser loader."""

import json
import shutil
import subprocess
from pathlib import Path

from benchmark_radar.blog_shell import extract_site_chrome, render_page
from benchmark_radar.site_pages import write_benchmark_pages


def test_clarity_consent_behavior():
    node = shutil.which("node")
    assert node is not None, "Node.js is required for site behavior tests"
    result = subprocess.run(
        [node, "--test", "tests/clarity_consent_harness.mjs"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_analytics_entry_point_has_a_place_to_change_consent():
    for name in ("index.html", "404.html", "logos.html"):
        html = Path("site", name).read_text(encoding="utf-8")
        assert 'class="privacy-note"' in html, name


def test_generated_reading_pages_share_consent_and_withdrawal(tmp_path):
    chrome = extract_site_chrome(Path("site/index.html").read_text())
    article = render_page(
        title="Daily brief",
        description="Evidence",
        canonical="https://benchmark-radar.org/blog/",
        body="<h1>Daily brief</h1>",
        chrome=chrome,
    )
    shards = tmp_path / "shards"
    shards.mkdir()
    (shards / "alpha.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "record": {"slug": "alpha", "name": "Alpha", "source": "test"},
                "scores_by_source": {},
            }
        )
    )
    output = tmp_path / "benchmarks"
    write_benchmark_pages(shards, output)
    pages = [article, *(p.read_text() for p in output.rglob("index.html"))]
    for page in pages:
        assert page.count('src="/assets/clarity.js"') == 1
        assert 'class="privacy-note"' in page
        assert "data-analytics-consent-reset" in page
        assert "Nothing loads until you accept" in " ".join(page.split())
