"""The published stylesheet minifier (SEO issue).

The Pages build strips comments and blank runs from the source CSS in place.
These tests pin what the minifier may and may not change: comments and trailing
whitespace go, everything else stays byte-identical.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import minify_css as mc  # noqa: E402


def minify_css(source: str) -> str:
    return mc.minify_css(source)


def test_comments_are_removed_but_rules_survive():
    source = "/* a comment */\na { color: red; }\n/* another */\n.b { color: blue; }\n"
    result = minify_css(source)
    assert "/*" not in result
    assert "a { color: red; }" in result
    assert ".b { color: blue; }" in result


def test_url_with_comment_like_text_is_preserved():
    # The dashboard stylesheet uses no url() at all (icons are inline SVG), so
    # a naive comment stripper is safe for it. Pin the invariant a stricter
    # minifier would need anyway: a comment-looking substring inside a string
    # stays intact, so the minifier cannot corrupt a future background image.
    source = 'x { background: url("a/*b*/c.png"); }\n'
    result = minify_css(source)
    assert 'url("a/*b*/c.png")' in result


def test_blank_runs_and_trailing_whitespace_are_collapsed():
    source = ".a { color: red; }\n\n\n\n\n.b { color: blue; }\n"
    result = minify_css(source)
    assert "\n\n\n" not in result
    assert ".a { color: red; }" in result
    assert result.endswith("\n")


def test_selectors_and_declarations_are_never_rewritten():
    source = (
        "@media (max-width: 700px) { .grid { grid-template-columns: repeat(3, 1fr); } }\n"
        ".a,.b { color: rgb(1 2 3 / 50%); margin: 0 auto; }\n"
    )
    result = minify_css(source)
    assert "@media (max-width: 700px)" in result
    assert ".a,.b { color: rgb(1 2 3 / 50%); margin: 0 auto; }" in result


def test_cli_preserves_single_quoted_and_escaped_literals(tmp_path):
    source = 'x { background: url(\'a/*b*/c.png\'); content: "say \\"/*literal*/\\""; }\n'
    path = tmp_path / "styles.css"
    path.write_text(source + "/* removable comment */\n")
    assert mc.main([str(path)]) == 0
    assert path.read_text() == source


def test_quotes_inside_comments_do_not_hide_following_rules():
    source = '/* a " quote */\nx { color: red; }\n/* another " quote */\n'
    assert minify_css(source) == "x { color: red; }\n"
