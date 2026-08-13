"""Normalize branch selections at the command-to-application boundary."""

from __future__ import annotations

from collections.abc import Sequence

from scripts.domain.branch_config import SUPPORTED_BRANCHES, validate_requested_branches
from scripts.domain.errors import InvalidDomainInputError


def normalize_branch_selection(
    branches: Sequence[str] | None,
) -> tuple[str, ...]:
    """Return user-selectable source branches for branch-oriented commands."""
    requested = SUPPORTED_BRANCHES if branches is None else tuple(branches)
    normalized = tuple(
        branch
        for branch in requested
        if branch != "jp" and not branch.startswith("_")
    )
    if not normalized:
        raise InvalidDomainInputError("可視化または辞書生成の対象支部が見つかりません")
    return validate_requested_branches(normalized)


__all__ = ["normalize_branch_selection"]
