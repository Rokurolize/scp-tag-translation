"""Coordinate the crosswalk parser stage of source generation."""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scripts.domain.crosswalk_resolution import CrosswalkResolver
from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    CrosswalkMappings,
    TargetResolver,
)
from scripts.application.source_parse_records import require_file


class _IntParser(Protocol):
    def parse_int_crosswalk(
        self,
        input_path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class _KoParser(Protocol):
    def parse_ko_crosswalk(
        self,
        input_path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class _BranchGuideParser(Protocol):
    def analyze_branch_guides(
        self,
        source_paths: Mapping[str, Sequence[Path]],
        resolver: TargetResolver,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> BranchGuideAnalysis: ...


class CrosswalkParsers(Protocol):
    @property
    def int(self) -> _IntParser: ...

    @property
    def ko(self) -> _KoParser: ...

    @property
    def branch_guides(self) -> _BranchGuideParser: ...


@dataclass(frozen=True)
class CrosswalkParseResult:
    int_mappings: CrosswalkMappings
    ko_mappings: CrosswalkMappings
    branch_analysis: BranchGuideAnalysis
    diagnostics: tuple[str, ...]


def _require_branch_guides(
    sources: Mapping[str, Sequence[Path]],
) -> None:
    missing = [
        path
        for paths in sources.values()
        for path in paths
        if not path.is_file()
    ]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"支部公式タグガイドが見つかりません:\n{formatted}")


def collect_crosswalk_parses(
    *,
    sources_int: Path,
    sources_ko: Path,
    branch_guide_sources: Mapping[str, Sequence[Path]],
    parsers: CrosswalkParsers,
    resolver: CrosswalkResolver,
) -> CrosswalkParseResult:
    """Run all crosswalk parsers and return one typed stage result."""
    require_file(sources_int, "INTタグクロスウォーク")
    require_file(sources_ko, "KOタグクロスウォーク")
    _require_branch_guides(branch_guide_sources)
    int_mappings = parsers.int.parse_int_crosswalk(
        sources_int,
        resolver.resolve,
    )
    ko_mappings = parsers.ko.parse_ko_crosswalk(
        sources_ko,
        resolver.resolve,
    )
    diagnostics: list[str] = []
    branch_analysis = parsers.branch_guides.analyze_branch_guides(
        branch_guide_sources,
        resolver.resolve,
        strict=True,
        diagnostics=diagnostics,
    )
    return CrosswalkParseResult(
        int_mappings=int_mappings,
        ko_mappings=ko_mappings,
        branch_analysis=branch_analysis,
        diagnostics=tuple(diagnostics),
    )


__all__ = ["CrosswalkParseResult", "collect_crosswalk_parses"]
