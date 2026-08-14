"""Parser interfaces shared by the source-parse application stages."""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence, Sequence
from pathlib import Path
from typing import Protocol

from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    CrosswalkMappings,
    TargetResolver,
)


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
    "IntParser",
    "KoParser",
]
