"""Canonical local and corpus paths for synchronized source artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from scripts.domain.errors import InvalidDomainInputError

__all__ = [
    "BRANCH_GUIDE_SOURCE_KEYS",
    "PARSER_SOURCE_KEYS",
    "SOURCE_ARTIFACTS",
    "SOURCE_BY_KEY",
    "ParserRole",
    "SourceArtifact",
    "branch_guide_sources",
    "corpus_source_map",
    "parser_source_path",
    "source_directory",
    "source_path",
]

ParserRole = Literal["en_tags", "jp_unused", "int_crosswalk", "ko_crosswalk", "branch_guide"]


@dataclass(frozen=True)
class SourceArtifact:
    """Describe one checked-in source snapshot and its corpus counterpart."""

    key: str
    local_path: str
    corpus_path: str
    parser_role: ParserRole | None = None


SOURCE_ARTIFACTS = (
    SourceArtifact("en_guide", "sources/en/tag-guide.txt", "05command/pages/tech-hub-tag/source.wikidot.txt"),
    SourceArtifact("en_tags", "sources/en/tag-list.txt", "05command/pages/tech-hub-tag-list/source.wikidot.txt", "en_tags"),
    SourceArtifact("en_manifest", "sources/en/tag-list-manifest.txt", "05command/pages/tag-list-manifest/source.wikidot.txt"),
    SourceArtifact("jp_guide", "sources/jp/tag-guide.txt", "jp/pages/tag-guide/source.wikidot.txt"),
    SourceArtifact("jp_tags", "sources/jp/tag-list.txt", "jp/pages/tag-list/source.wikidot.txt"),
    SourceArtifact("jp_basic", "sources/jp/fragment-basic.txt", "jp/pages/fragment:tag-list-basic/source.wikidot.txt"),
    SourceArtifact("jp_series", "sources/jp/fragment-series.txt", "jp/pages/fragment:tag-list-series/source.wikidot.txt"),
    SourceArtifact("jp_universe", "sources/jp/fragment-universe.txt", "jp/pages/fragment:tag-list-universe/source.wikidot.txt"),
    SourceArtifact("jp_event", "sources/jp/fragment-event.txt", "jp/pages/fragment:tag-list-event/source.wikidot.txt"),
    SourceArtifact("jp_unused", "sources/jp/fragment-unused.txt", "jp/pages/fragment:tag-list-unused/source.wikidot.txt", "jp_unused"),
    SourceArtifact("jp_faq", "sources/jp/fragment-faq.txt", "jp/pages/fragment:tag-list-faq/source.wikidot.txt"),
    SourceArtifact("int_crosswalk", "sources/int/tag-guide.txt", "int/pages/tag-guide/source.wikidot.txt", "int_crosswalk"),
    SourceArtifact("ko_crosswalk", "sources/ko/translate-tags.txt", "ko/pages/translate:tags/source.wikidot.txt", "ko_crosswalk"),
    SourceArtifact("cn_guide", "sources/cn/tag-guide.txt", "cn/pages/tag-guide/source.wikidot.txt", "branch_guide"),
    SourceArtifact("de_guide", "sources/de/tag-guide.txt", "de/pages/tag-guide/source.wikidot.txt", "branch_guide"),
    SourceArtifact("es_guide", "sources/es/tag-guide.txt", "es/pages/tag-guide/source.wikidot.txt", "branch_guide"),
    SourceArtifact("fr_guide", "sources/fr/guide-des-tags.txt", "fr/pages/guide-des-tags/source.wikidot.txt", "branch_guide"),
    SourceArtifact("it_guide", "sources/it/tag-guide.txt", "it/pages/tag-guide/source.wikidot.txt", "branch_guide"),
    SourceArtifact("pl_guide", "sources/pl/tag-list.txt", "pl/pages/tag-list/source.wikidot.txt", "branch_guide"),
    SourceArtifact("pt_br_guide", "sources/pt-br/fragment-lista-mestra.txt", "pt-br/pages/fragment:lista-mestra/source.wikidot.txt", "branch_guide"),
    SourceArtifact("th_guide", "sources/th/tag-list.txt", "th/pages/tag-list/source.wikidot.txt", "branch_guide"),
    SourceArtifact("ua_guide", "sources/ua/tag-guide.txt", "ua/pages/tag-guide/source.wikidot.txt", "branch_guide"),
    SourceArtifact("vn_guide", "sources/vn/fragment-tag-guide-for-translator.txt", "vn/pages/fragment:tag-guide-for-translator/source.wikidot.txt", "branch_guide"),
    SourceArtifact("zh_tr_base", "sources/zh-tr/fragment-base-tag.txt", "zh-tr/pages/fragment:base-tag/source.wikidot.txt", "branch_guide"),
    SourceArtifact("zh_tr_characteristic", "sources/zh-tr/fragment-characteristic-tag.txt", "zh-tr/pages/fragment:characteristic-tag/source.wikidot.txt", "branch_guide"),
    SourceArtifact("zh_tr_genre", "sources/zh-tr/fragment-genre-and-theme-tag.txt", "zh-tr/pages/fragment:genre-and-theme-tag/source.wikidot.txt", "branch_guide"),
    SourceArtifact("zh_tr_other", "sources/zh-tr/fragment-other-tag.txt", "zh-tr/pages/fragment:other-tag/source.wikidot.txt", "branch_guide"),
    SourceArtifact("zh_tr_internationality", "sources/zh-tr/fragment-internationality-tag.txt", "zh-tr/pages/fragment:internationality-tag/source.wikidot.txt", "branch_guide"),
)

SOURCE_BY_KEY = MappingProxyType({artifact.key: artifact for artifact in SOURCE_ARTIFACTS})

PARSER_SOURCE_KEYS = MappingProxyType({
    "en": "en_tags",
    "jp_unused": "jp_unused",
    "int": "int_crosswalk",
    "ko": "ko_crosswalk",
})

BRANCH_GUIDE_SOURCE_KEYS = MappingProxyType({
    "cn": ("cn_guide",),
    "de": ("de_guide",),
    "es": ("es_guide",),
    "fr": ("fr_guide",),
    "it": ("it_guide",),
    "pl": ("pl_guide",),
    "pt-br": ("pt_br_guide",),
    "th": ("th_guide",),
    "ua": ("ua_guide",),
    "vn": ("vn_guide",),
    "zh-tr": (
        "zh_tr_base",
        "zh_tr_characteristic",
        "zh_tr_genre",
        "zh_tr_other",
        "zh_tr_internationality",
    ),
})


def source_path(key: str, *, root: Path) -> Path:
    """Return a manifest source path or raise InvalidDomainInputError for an unknown key."""
    try:
        artifact = SOURCE_BY_KEY[key]
    except KeyError as exc:
        raise InvalidDomainInputError(f"unknown source artifact: {key}") from exc
    return root / artifact.local_path


def source_directory(name: str, *, root: Path) -> Path:
    """Return a checked-in source directory by name."""
    return root / "sources" / name


def parser_source_path(name: str, *, root: Path) -> Path:
    """Return a parser source path or raise InvalidDomainInputError for an unknown name."""
    try:
        key = PARSER_SOURCE_KEYS[name]
    except KeyError as exc:
        raise InvalidDomainInputError(f"unknown parser source: {name}") from exc
    return source_path(key, root=root)


def branch_guide_sources(*, root: Path) -> dict[str, tuple[Path, ...]]:
    """Return parser guide paths grouped by corpus branch."""
    return {
        branch: tuple(source_path(key, root=root) for key in keys)
        for branch, keys in BRANCH_GUIDE_SOURCE_KEYS.items()
    }


def corpus_source_map() -> dict[str, str]:
    """Return local-to-corpus paths for the synchronization command."""
    return {
        artifact.local_path: artifact.corpus_path
        for artifact in SOURCE_ARTIFACTS
    }
