"""Tests for the canonical synchronized-source manifest."""

from __future__ import annotations

from scripts.domain.source_manifest import (
    BRANCH_GUIDE_SOURCE_KEYS,
    SOURCE_ARTIFACTS,
    branch_guide_sources,
    corpus_source_map,
    parser_source_path,
)


def test_manifest_exposes_parser_and_corpus_paths() -> None:
    assert parser_source_path("en").as_posix().endswith("sources/en/tag-list.txt")
    assert parser_source_path("jp_unused").as_posix().endswith(
        "sources/jp/fragment-unused.txt"
    )
    assert len(corpus_source_map()) == len(SOURCE_ARTIFACTS) == 28


def test_manifest_groups_all_branch_guide_inputs() -> None:
    guides = branch_guide_sources()

    assert set(guides) == set(BRANCH_GUIDE_SOURCE_KEYS)
    assert sum(len(paths) for paths in guides.values()) == 15
    assert guides["zh-tr"][-1].name == "fragment-internationality-tag.txt"
