"""Parser interfaces shared by the source-parse application stages."""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence, Sequence
from pathlib import Path
from typing import Protocol

from scripts.domain.records.tag_records import DeprecatedTag, EnTag, JpTag
from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    CrosswalkMappings,
    TargetResolver,
)


class EnParser(Protocol):
    def parse_en_tags(
        self,
        input_path: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[EnTag]: ...


class JpParser(Protocol):
    def parse_jp_tags(
        self,
        source_dir: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[JpTag]: ...

    def parse_unused_tag_records(
        self,
        source_path: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[DeprecatedTag]: ...


class IntParser(Protocol):
    def parse_int_crosswalk(
        self,
        input_path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class KoParser(Protocol):
    def parse_ko_crosswalk(
        self,
        input_path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class BranchGuideParser(Protocol):
    def analyze_branch_guides(
        self,
        source_paths: Mapping[str, Sequence[Path]],
        resolver: TargetResolver,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> BranchGuideAnalysis: ...


__all__ = [
    "BranchGuideParser",
    "EnParser",
    "IntParser",
    "JpParser",
    "KoParser",
]
