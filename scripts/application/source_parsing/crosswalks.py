"""Coordinate the crosswalk parser stage of source generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.domain.crosswalk_resolution import CrosswalkResolver
from scripts.parsers.contracts import BranchGuideAnalysis, CrosswalkMappings

from .contracts import BranchGuideParser, IntParser, KoParser
from .records import require_file


@dataclass(frozen=True)
class CrosswalkParseResult:
    int_mappings: CrosswalkMappings
    ko_mappings: CrosswalkMappings
    branch_analysis: BranchGuideAnalysis
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class CrosswalkParseInputs:
    """Source files consumed by one crosswalk parsing stage."""

    sources_int: Path
    sources_ko: Path
    branch_guide_sources: Mapping[str, Sequence[Path]]


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
    inputs: CrosswalkParseInputs,
    int_parser_impl: IntParser,
    ko_parser_impl: KoParser,
    branch_guide_parser_impl: BranchGuideParser,
    resolver: CrosswalkResolver,
) -> CrosswalkParseResult:
    """Run all crosswalk parsers and return one typed stage result."""
    require_file(inputs.sources_int, "INTタグクロスウォーク")
    require_file(inputs.sources_ko, "KOタグクロスウォーク")
    _require_branch_guides(inputs.branch_guide_sources)
    diagnostics: list[str] = []
    int_mappings = int_parser_impl.parse_int_crosswalk(
        inputs.sources_int,
        resolver.resolve,
        strict=True,
        diagnostics=diagnostics,
    )
    ko_mappings = ko_parser_impl.parse_ko_crosswalk(
        inputs.sources_ko,
        resolver.resolve,
        strict=True,
        diagnostics=diagnostics,
    )
    branch_analysis = branch_guide_parser_impl.analyze_branch_guides(
        inputs.branch_guide_sources,
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


__all__ = [
    "CrosswalkParseInputs",
    "CrosswalkParseResult",
    "collect_crosswalk_parses",
]
