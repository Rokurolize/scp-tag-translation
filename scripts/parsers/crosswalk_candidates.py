"""Shared reduction of parsed crosswalk rows into deterministic mappings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TypeAlias

from scripts.parsers.contracts import CrosswalkMappings, TargetResolver

CrosswalkCandidate: TypeAlias = tuple[
    str,
    str,
    Iterable[str],
    Iterable[str],
]

__all__ = ["CrosswalkCandidate", "resolve_crosswalk_candidates"]


def resolve_crosswalk_candidates(
    candidates: Iterable[CrosswalkCandidate],
    resolver: TargetResolver,
) -> CrosswalkMappings:
    """Resolve candidates into mappings, omitting unresolved and conflicting targets."""
    targets: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for branch, source_tag, en_values, jp_values in candidates:
        target = resolver(en_values, jp_values)
        if target is not None:
            targets[branch][source_tag].add(target)

    return {
        branch: {
            source_tag: next(iter(source_targets))
            for source_tag, source_targets in sorted(branch_targets.items())
            if len(source_targets) == 1
        }
        for branch, branch_targets in sorted(targets.items())
    }
