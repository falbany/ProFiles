"""Tests for escape sequence and Markdown renderer."""

from profiles.core.environment.render import render_text


def test_escape_sequences():
    result = render_text("Line1\\nLine2\\tTab")
    assert isinstance(result, list)
    plain = "".join(seg.text for seg in result)
    assert plain == "Line1\nLine2\tTab"


def test_escape_backslash():
    result = render_text("Path\\\\File", headless=True)
    assert result == "Path\\File"


def test_markdown_bold():
    result = render_text("**bold** text")
    assert isinstance(result, list)
    assert any(seg.text == "bold" and seg.style == "bold" for seg in result)
    assert any(seg.text == " text" and seg.style == "normal" for seg in result)


def test_markdown_heading():
    result = render_text("# Title")
    assert isinstance(result, list)
    assert any(seg.text == "Title" and seg.style == "heading" for seg in result)


def test_headless_mode():
    result = render_text("# **Bold**\\nText", headless=True)
    assert isinstance(result, str)
    assert result == "Bold\nText"


def test_headless_link_degrades_to_label_and_url():
    result = render_text("See [docs](https://example.com)", headless=True)
    assert result == "See docs (https://example.com)"


def test_headless_image_degrades_to_alt_and_url():
    result = render_text("![logo](https://example.com/logo.png)", headless=True)
    assert result == "logo (https://example.com/logo.png)"


def test_headless_block_syntax_stays_literal():
    # Lists, tables and blockquotes are not stripped: their raw lines stay
    # readable in a terminal (documented degradation contract).
    result = render_text("- item\\n> quoted\\n| a | b |", headless=True)
    assert result == "- item\n> quoted\n| a | b |"
