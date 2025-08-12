"""Tests for dictionary generator."""

import json
from pathlib import Path

import pytest

from src.generator import generate_dictionary


def test_generate_dictionary_success(tmp_path):
    """Test successful dictionary generation."""
    # Create test EN file
    en_file = tmp_path / "en_tags.wikidot"
    en_file.write_text("""
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/safe safe]** -- Object class
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/scp scp]** -- Main tag
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/tale tale]** -- Tales
    """)

    # Create test JP file
    jp_file = tmp_path / "scp-jp_tag-list.wikidot"
    jp_file.write_text("""
* **[[[/system:page-tags/tag/safe|safe]]]** //(safe)//
* **[[[/system:page-tags/tag/scp|scp]]]** //(scp)//
    """)

    output_file = tmp_path / "output.json"

    dictionary, stats = generate_dictionary(en_file, tmp_path, output_file)

    # Check dictionary contents
    assert dictionary["safe"] == "safe"
    assert dictionary["scp"] == "scp"
    assert dictionary["tale"] is None  # Not in JP file

    # Check statistics
    assert stats["total"] == 3
    assert stats["mapped"] == 2
    assert stats["unmapped"] == 1
    assert stats["coverage"] == 67

    # Check output file was created
    assert output_file.exists()
    with open(output_file) as f:
        saved_dict = json.load(f)
    assert saved_dict == dictionary


def test_generate_dictionary_missing_en_file(tmp_path):
    """Test with missing EN file."""
    with pytest.raises(FileNotFoundError):
        generate_dictionary(Path("nonexistent.wikidot"), tmp_path, tmp_path / "out.json")


def test_generate_dictionary_no_jp_files(tmp_path):
    """Test with no JP files."""
    en_file = tmp_path / "en_tags.wikidot"
    en_file.write_text("""
* **[https://scp-wiki.wikidot.com/system:page-tags/tag/safe safe]**
    """)

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        generate_dictionary(en_file, empty_dir, tmp_path / "out.json")


def test_generate_dictionary_empty_en_file(tmp_path):
    """Test with empty EN file."""
    en_file = tmp_path / "en_tags.wikidot"
    en_file.write_text("")

    jp_file = tmp_path / "scp-jp_test.wikidot"
    jp_file.write_text("* **[[[/system:page-tags/tag/test|test]]]** //(test)//")

    with pytest.raises(ValueError, match="No EN tags found"):
        generate_dictionary(en_file, tmp_path, tmp_path / "out.json")
