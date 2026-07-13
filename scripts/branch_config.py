"""Supported SCP Wikidot sites and their local corpus branch codes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchConfig:
    branch: str
    site: str
    label: str
    jp_branch_tag: str


SUPPORTED_BRANCH_CONFIGS = (
    BranchConfig("cn", "scp-wiki-cn", "中文 / SCP-CN", "cn"),
    BranchConfig("cs", "scp-cs", "Čeština / SCP-CS", "cs"),
    BranchConfig("de", "scp-wiki-de", "Deutsch / SCP-DE", "de"),
    BranchConfig("en", "scp-wiki", "English / SCP-EN", "en"),
    BranchConfig("es", "lafundacionscp", "Español / SCP-ES", "es"),
    BranchConfig("fr", "fondationscp", "Français / SCP-FR", "fr"),
    BranchConfig("int", "scp-int", "International / SCP-INT", "int"),
    BranchConfig("it", "fondazionescp", "Italiano / SCP-IT", "it"),
    BranchConfig("ko", "scpko", "한국어 / SCP-KO", "ko"),
    BranchConfig("pl", "scp-pl", "Polski / SCP-PL", "pl"),
    BranchConfig("pt-br", "scp-pt-br", "Português / SCP-PT-BR", "pt"),
    BranchConfig("th", "scp-th", "ภาษาไทย / SCP-TH", "th"),
    BranchConfig("ua", "scp-ukrainian", "Українська / SCP-UA", "ua"),
    BranchConfig("vn", "scp-vn", "Tiếng Việt / SCP-VN", "vn"),
    BranchConfig("zh-tr", "scp-zh-tr", "繁體中文 / SCP-ZH-TR", "zh"),
)


SUPPORTED_BRANCHES = tuple(config.branch for config in SUPPORTED_BRANCH_CONFIGS)
BRANCH_CONFIG_BY_CODE = {
    config.branch: config for config in SUPPORTED_BRANCH_CONFIGS
}


def source_site_for_branch(branch: str) -> str:
    """Return the Wikidot site unix name for a supported corpus branch."""

    try:
        return BRANCH_CONFIG_BY_CODE[branch].site
    except KeyError as exc:
        raise ValueError(f"unsupported corpus branch: {branch}") from exc


def jp_branch_tag_for_branch(branch: str) -> str:
    """Return the SCP-JP origin tag corresponding to a source branch."""

    try:
        return BRANCH_CONFIG_BY_CODE[branch].jp_branch_tag
    except KeyError as exc:
        raise ValueError(f"unsupported corpus branch: {branch}") from exc
