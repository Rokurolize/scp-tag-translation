"""Shared parser contracts for crosswalk data and audit results."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, TypeAlias, TypedDict

__all__ = [
    "BranchGuideAnalysis",
    "BranchGuideAudit",
    "BranchGuideStats",
    "CrosswalkMappings",
    "TargetResolver",
]


CrosswalkMappings: TypeAlias = dict[str, dict[str, str]]


class TargetResolver(Protocol):
    def __call__(
        self,
        en_values: Iterable[str],
        jp_values: Iterable[str],
    ) -> str | None: ...


class BranchGuideAudit(TypedDict):
    parsed_rows: int
    resolved_rows: int
    accepted_tags: int
    conflicting_tags: int
    unresolved_source_tags: int


BranchGuideStats: TypeAlias = dict[str, BranchGuideAudit]


@dataclass(frozen=True)
class BranchGuideAnalysis:
    mappings: CrosswalkMappings
    stats: BranchGuideStats
