"""Keep the field browser on the canonical site shell and catalog."""

import json
import shutil
import subprocess
from pathlib import Path

from benchmark_radar.blog_shell import extract_site_chrome
from benchmark_radar.research_page import write_research_page

ROOT = Path(__file__).resolve().parents[1]


def test_research_page_uses_original_navigation(tmp_path):
    site = ROOT / "site"
    (tmp_path / "assets").mkdir()
    shutil.copy(site / "index.html", tmp_path / "index.html")
    shutil.copy(site / "assets/app.js", tmp_path / "assets/app.js")
    assert write_research_page(tmp_path) == "/research/"
    page = (tmp_path / "research/index.html").read_text()
    header = extract_site_chrome((site / "index.html").read_text(), active_path="/research/").header
    assert header in page
    assert 'class="brand-mark"' in page
    assert 'href="/assets/design-system.css"' in page
    assert 'src="/assets/research.js"' in page
    assert "{{" not in page
    assert "noindex" not in page


def test_field_mapping_preserves_unknowns_and_overlapping_tags():
    module = (ROOT / "site/assets/fields.js").read_text()
    script = (
        module
        + """
console.log(JSON.stringify([
  recordFields({tags: []}),
  recordFields({tags: ['coding_agent']}),
  recordFields({tags: ['unrecognized']}),
  matchesField({tags: ['tool_use']}, 'agents', 'Tool use'),
  matchesField({tags: ['coding_agent']}, 'agents', 'Tool use'),
  matchesField({tags: []}, 'all'),
  recordFields({tags: [], name: 'Safety coding benchmark'})
]));
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [
        ["other"],
        ["agents", "coding"],
        ["other"],
        True,
        False,
        True,
        ["other"],
    ]
