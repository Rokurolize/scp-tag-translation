"""Supported SCP Wikidot sites and their local corpus branch codes."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.domain.tag_models import BrowserBranchRecord


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


SUPPORTED_BRANCHES = tuple(config.branch for config in SUPPORTED_BRANCH_CONFIGS)
BRANCH_CONFIG_BY_CODE = {config.branch: config for config in SUPPORTED_BRANCH_CONFIGS}


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
