"""Tests for JP tag parser."""

from pathlib import Path

import pytest

from src.parsers.jp_parser import parse_jp_mappings


def test_parse_jp_standard_format(tmp_path):
    """Test parsing standard format: //(tag)//"""
    test_file = tmp_path / "scp-jp_tag-list.wikidot"  # Must match glob pattern
    test_file.write_text("""
* **[[[/system:page-tags/tag/safe|safe]]]** //(safe)//
* **[[[/system:page-tags/tag/アダルト|アダルト]]]** //(adult)//
    """)

    mappings = parse_jp_mappings(tmp_path)
    assert mappings["safe"] == "safe"
    assert mappings["adult"] == "アダルト"
    assert mappings["_adult"] == "アダルト"  # Underscore variant


def test_parse_jp_reversed_format(tmp_path):
    """Test parsing reversed format: (//tag//)"""
    test_file = tmp_path / "scp-jp_tag-list.wikidot"  # Must match glob pattern
    test_file.write_text("""
* **[[[/system:page-tags/tag/_夜勤|_夜勤]]]** (//_graveyard-shift//)
* **[[[/system:page-tags/tag/_お役人|_お役人]]]** (//_the-bureaucrat//)
    """)

    mappings = parse_jp_mappings(tmp_path)
    assert mappings["_graveyard-shift"] == "_夜勤"
    assert mappings["_the-bureaucrat"] == "_お役人"


def test_parse_jp_multi_tag_line(tmp_path):
    """Test parsing lines with multiple tags."""
    test_file = tmp_path / "scp-jp_tag-list.wikidot"  # Must match glob pattern
    test_file.write_text("""
* **[[[/system:page-tags/tag/_int|_int]]]** //(_int)// / **[[[/system:page-tags/tag/_ru|_ru]]]** //(_ru)//
    """)

    mappings = parse_jp_mappings(tmp_path)
    assert mappings["_int"] == "_int"
    assert mappings["_ru"] == "_ru"


def test_parse_jp_no_english_tag(tmp_path):
    """Test tags without English equivalent."""
    test_file = tmp_path / "scp-jp_tag-list.wikidot"  # Must match glob pattern
    test_file.write_text("""
* **[[[/system:page-tags/tag/財団日本支部|財団日本支部]]]**
* **[[[/system:page-tags/tag/safe|safe]]]** //(safe)//
    """)

    mappings = parse_jp_mappings(tmp_path)
    assert "財団日本支部" not in mappings  # No EN tag, not in mappings
    assert mappings["safe"] == "safe"


def test_parse_jp_no_files_found():
    """Test when no JP files are found."""
    with pytest.raises(FileNotFoundError, match="No JP fragment files found"):
        parse_jp_mappings(Path("/nonexistent/directory"))


def test_parse_jp_underscore_variant_creation(tmp_path):
    """Test that underscore variants are created correctly."""
    test_file = tmp_path / "scp-jp_tag-list.wikidot"  # Must match glob pattern
    test_file.write_text("""
* **[[[/system:page-tags/tag/アダルト|アダルト]]]** //(adult)//
* **[[[/system:page-tags/tag/_goi-jp|_goi-jp]]]** //(_goi)//
    """)

    mappings = parse_jp_mappings(tmp_path)
    # Should create _adult variant
    assert mappings["adult"] == "アダルト"
    assert mappings["_adult"] == "アダルト"
    # Should NOT create __goi variant
    assert mappings["_goi"] == "_goi-jp"
    assert "__goi" not in mappings
