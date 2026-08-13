"""Supported SCP Wikidot sites and their local corpus branch codes."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from types import MappingProxyType
from typing import TypedDict
from collections.abc import Mapping

from scripts.domain.policy.branch_scope import SUPPORTED_BRANCHES

__all__ = [
    "BRANCH_CONFIG_BY_CODE",
    "SUPPORTED_BRANCHES",
    "SUPPORTED_BRANCH_CONFIGS",
    "BrowserBranchRecord",
    "BranchConfig",
    "browser_config_records",
    "jp_branch_tag_for_branch",
    "source_site_for_branch",
    "validate_requested_branches",
]


class BrowserBranchRecord(TypedDict):
    branch: str
    site: str
    label: str
    jp_branch_tag: str


@dataclass(frozen=True)
class BranchConfig:
    branch: str
    site: str
    label: str
    jp_branch_tag: str


SUPPORTED_BRANCH_CONFIGS = (
    BranchConfig("cn", "scp-wiki-cn", "中文", "cn"),
    BranchConfig("cs", "scp-cs", "Čeština", "cs"),
    BranchConfig("de", "scp-wiki-de", "Deutsch", "de"),
    BranchConfig("en", "scp-wiki", "English", "en"),
    BranchConfig("es", "lafundacionscp", "Español", "es"),
    BranchConfig("fr", "fondationscp", "Français", "fr"),
    BranchConfig("int", "scp-int", "International", "int"),
    BranchConfig("it", "fondazionescp", "Italiano", "it"),
    BranchConfig("ko", "scpko", "한국어", "ko"),
    BranchConfig("pl", "scp-pl", "Polski", "pl"),
    BranchConfig("pt-br", "scp-pt-br", "Português", "pt"),
    BranchConfig("th", "scp-th", "ภาษาไทย", "th"),
    BranchConfig("ua", "scp-ukrainian", "Українська", "ua"),
    BranchConfig("vn", "scp-vn", "Tiếng Việt", "vn"),
    BranchConfig("zh-tr", "scp-zh-tr", "繁體中文", "zh"),
)


def validate_requested_branches(
    branches: Sequence[str],
    *,
    supported_branches: Sequence[str] = SUPPORTED_BRANCHES,
) -> tuple[str, ...]:
    """Validate a non-empty, duplicate-free subset of supported branches."""
    requested = tuple(branches)
    if not requested:
        raise ValueError("at least one branch is required")
    if any(not isinstance(branch, str) or not branch for branch in requested):
        raise ValueError("branch names must be non-empty strings")
    duplicates = sorted({
        branch
        for branch in requested
        if requested.count(branch) > 1
    })
    if duplicates:
        raise ValueError("duplicate branches: " + ", ".join(duplicates))
    unsupported = sorted(set(requested) - set(supported_branches))
    if unsupported:
        raise ValueError("unsupported branches: " + ", ".join(unsupported))
    return requested
BRANCH_CONFIG_BY_CODE: Mapping[str, BranchConfig] = MappingProxyType({
    config.branch: config for config in SUPPORTED_BRANCH_CONFIGS
})


def browser_config_records() -> list[BrowserBranchRecord]:
    """Return the supported-branch fields consumed by the static browser app."""

    return [
        {
            "branch": config.branch,
            "site": config.site,
            "label": config.label,
            "jp_branch_tag": config.jp_branch_tag,
        }
        for config in SUPPORTED_BRANCH_CONFIGS
    ]


def source_site_for_branch(branch: str) -> str:
    try:
        return BRANCH_CONFIG_BY_CODE[branch].site
    except KeyError as exc:
        raise ValueError(f"unsupported corpus branch: {branch}") from exc


def jp_branch_tag_for_branch(branch: str) -> str:
    try:
        return BRANCH_CONFIG_BY_CODE[branch].jp_branch_tag
    except KeyError as exc:
        raise ValueError(f"unsupported corpus branch: {branch}") from exc
