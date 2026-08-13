"""Tests for the canonical synchronized-source manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.source_manifest import (
    BRANCH_GUIDE_SOURCE_KEYS,
    SOURCE_ARTIFACTS,
    branch_guide_sources,
    corpus_source_map,
    parser_source_path,
    source_path,
)


def test_manifest_lookup_errors_are_domain_errors() -> None:
    root = Path("/repo")
    with pytest.raises(ValueError, match="unknown source artifact"):
        source_path("missing", root=root)
    with pytest.raises(ValueError, match="unknown parser source"):
        parser_source_path("missing", root=root)


def test_manifest_exposes_parser_and_corpus_paths() -> None:
    root = Path("/repo")
    assert parser_source_path("en", root=root).as_posix().endswith("sources/en/tag-list.txt")
    assert parser_source_path("jp_unused", root=root).as_posix().endswith(
        "sources/jp/fragment-unused.txt"
    )
    assert len(corpus_source_map()) == len(SOURCE_ARTIFACTS) == 28


def test_manifest_groups_all_branch_guide_inputs() -> None:
    guides = branch_guide_sources(root=Path("/repo"))

    assert set(guides) == set(BRANCH_GUIDE_SOURCE_KEYS)
    assert sum(len(paths) for paths in guides.values()) == 15
    assert guides["zh-tr"][-1].name == "fragment-internationality-tag.txt"
