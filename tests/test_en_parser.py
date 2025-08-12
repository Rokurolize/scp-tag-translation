"""Tests for EN tag parser."""

from pathlib import Path

import pytest

from src.parsers.en_parser import parse_en_tags


def test_parse_en_tags_with_valid_file(tmp_path):
    """Test parsing valid EN tags file."""
    test_file = tmp_path / "test_tags.wikidot"
    test_file.write_text("""
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/safe safe]** -- Object is safe
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/euclid euclid]** -- Object is euclid
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/keter keter]** -- Object is keter
    """)

    tags = parse_en_tags(test_file)
    assert tags == {"safe", "euclid", "keter"}


def test_parse_en_tags_with_missing_file():
    """Test parsing with missing file."""
    with pytest.raises(FileNotFoundError):
        parse_en_tags(Path("nonexistent.wikidot"))


def test_parse_en_tags_with_empty_file(tmp_path):
    """Test parsing empty file."""
    test_file = tmp_path / "empty.wikidot"
    test_file.write_text("")

    with pytest.raises(ValueError, match="No EN tags found"):
        parse_en_tags(test_file)


def test_parse_en_tags_with_complex_tags(tmp_path):
    """Test parsing tags with underscores and hyphens."""
    test_file = tmp_path / "complex.wikidot"
    test_file.write_text("""
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/_cc _cc]** -- Creative Commons
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/broken-god broken-god]** -- Church of the Broken God
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/scp-001 scp-001]** -- SCP-001
    """)

    tags = parse_en_tags(test_file)
    assert tags == {"_cc", "broken-god", "scp-001"}
