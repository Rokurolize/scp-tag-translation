"""Parse official tag sources and publish generated records."""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from scripts.domain.policy.tag_policy import EN_CROSSWALK_SEMANTIC_REPLACEMENTS
from scripts.domain.crosswalk_resolution import CrosswalkResolver
from scripts.domain.records.tag_records import DeprecatedTag, EnTag, JpTag
from scripts.domain.records.tag_validation import validate_deprecated_tags, validate_jp_tags
from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import (
    DATA_BRANCH_GUIDE_CROSSWALK,
    DATA_DEPRECATED,
    DATA_EN,
    DATA_INT_CROSSWALK,
    DATA_JP,
    DATA_KO_CROSSWALK,
    ROOT,
)
from scripts.infrastructure.json_io import load_json, write_json
from scripts.parsers import branch_guide_parser, en_parser, int_parser, jp_parser, ko_parser
from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    CrosswalkMappings,
    TargetResolver,
)
from scripts.pipeline.source_manifest import (
    branch_guide_sources,
    parser_source_path,
    source_directory,
)

Language = Literal["en", "jp", "crosswalks", "all"]
LANGUAGES: tuple[Language, ...] = ("en", "jp", "crosswalks", "all")

SOURCES_EN = parser_source_path("en", root=ROOT)
SOURCES_JP = source_directory("jp", root=ROOT)
SOURCES_JP_UNUSED = parser_source_path("jp_unused", root=ROOT)
SOURCES_INT = parser_source_path("int", root=ROOT)
SOURCES_KO = parser_source_path("ko", root=ROOT)
BRANCH_GUIDE_SOURCES: Mapping[str, tuple[Path, ...]] = branch_guide_sources(root=ROOT)


class EnParser(Protocol):
    def parse_en_tags(
        self,
        path: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[EnTag]: ...


class JpParser(Protocol):
    def parse_jp_tags(
        self,
        path: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[JpTag]: ...

    def parse_unused_tag_records(
        self,
        path: Path,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> list[DeprecatedTag]: ...


class IntParser(Protocol):
    def parse_int_crosswalk(
        self,
        path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class KoParser(Protocol):
    def parse_ko_crosswalk(
        self,
        path: Path,
        resolver: TargetResolver,
    ) -> CrosswalkMappings: ...


class BranchGuideParser(Protocol):
    def analyze_branch_guides(
        self,
        sources: Mapping[str, tuple[Path, ...]],
        resolver: TargetResolver,
        *,
        strict: bool = False,
        diagnostics: MutableSequence[str] | None = None,
    ) -> BranchGuideAnalysis: ...


@dataclass(frozen=True)
class ParseBatch:
    outputs: Mapping[Path, object]
    messages: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseWorkflowConfig:
    """Paths and parser implementations used by one parse workflow."""

    sources_en: Path = field(default_factory=lambda: SOURCES_EN)
    sources_jp: Path = field(default_factory=lambda: SOURCES_JP)
    sources_jp_unused: Path = field(default_factory=lambda: SOURCES_JP_UNUSED)
    sources_int: Path = field(default_factory=lambda: SOURCES_INT)
    sources_ko: Path = field(default_factory=lambda: SOURCES_KO)
    branch_guide_sources: Mapping[str, tuple[Path, ...]] = field(
        default_factory=lambda: BRANCH_GUIDE_SOURCES,
    )
    data_en: Path = field(default_factory=lambda: DATA_EN)
    data_jp: Path = field(default_factory=lambda: DATA_JP)
    data_deprecated: Path = field(default_factory=lambda: DATA_DEPRECATED)
    data_int_crosswalk: Path = field(default_factory=lambda: DATA_INT_CROSSWALK)
    data_ko_crosswalk: Path = field(default_factory=lambda: DATA_KO_CROSSWALK)
    data_branch_guide_crosswalk: Path = field(
        default_factory=lambda: DATA_BRANCH_GUIDE_CROSSWALK,
    )
    en_parser: EnParser = field(default_factory=lambda: en_parser)
    jp_parser: JpParser = field(default_factory=lambda: jp_parser)
    int_parser: IntParser = field(default_factory=lambda: int_parser)
    ko_parser: KoParser = field(default_factory=lambda: ko_parser)
    branch_guide_parser: BranchGuideParser = field(
        default_factory=lambda: branch_guide_parser,
    )


def default_parse_workflow_config() -> ParseWorkflowConfig:
    """Return the repository-default source parsing configuration."""
    return ParseWorkflowConfig()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label}が見つかりません: {path}")


def _require_branch_guides(config: ParseWorkflowConfig) -> None:
    missing = [
        path
        for paths in config.branch_guide_sources.values()
        for path in paths
        if not path.is_file()
    ]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"支部公式タグガイドが見つかりません:\n{formatted}")


def _load_json_array(path: Path, label: str) -> list[object]:
    _require_file(path, label)
    value = load_json(path)
    if not isinstance(value, list):
        raise ValueError(f"{label}はJSON配列である必要があります: {path}")
    return value


def _build_crosswalk_resolver(
    jp_tags: list[JpTag],
    deprecated_tags: list[DeprecatedTag],
) -> CrosswalkResolver:
    return CrosswalkResolver(
        jp_tags,
        deprecated_tags,
        EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    )


def _collect_en_outputs(config: ParseWorkflowConfig) -> ParseBatch:
    _require_file(config.sources_en, "ENソースファイル")
    diagnostics: list[str] = []
    en_tags = config.en_parser.parse_en_tags(
        config.sources_en,
        strict=True,
        diagnostics=diagnostics,
    )
    return ParseBatch(
        outputs={config.data_en: en_tags},
        messages=(f"EN: {len(en_tags)} タグを解析 → {config.data_en}",),
        diagnostics=tuple(diagnostics),
    )


def _collect_jp_outputs(
    config: ParseWorkflowConfig,
) -> tuple[ParseBatch, list[JpTag], list[DeprecatedTag]]:
    if not config.sources_jp.is_dir():
        raise FileNotFoundError(
            f"JPソースディレクトリが見つかりません: {config.sources_jp}"
        )
    diagnostics: list[str] = []
    jp_tags = config.jp_parser.parse_jp_tags(
        config.sources_jp,
        strict=True,
        diagnostics=diagnostics,
    )
    deprecated_tags = (
        config.jp_parser.parse_unused_tag_records(
            config.sources_jp_unused,
            strict=True,
            diagnostics=diagnostics,
        )
        if config.sources_jp_unused.is_file()
        else []
    )
    batch = ParseBatch(
        outputs={
            config.data_jp: jp_tags,
            config.data_deprecated: deprecated_tags,
        },
        messages=(
            f"JP: {len(jp_tags)} タグを解析 → {config.data_jp}",
            f"JP(未使用): {len(deprecated_tags)} タグを解析 → {config.data_deprecated}",
        ),
    )
    return (
        ParseBatch(
            outputs=batch.outputs,
            messages=batch.messages,
            diagnostics=tuple(diagnostics),
        ),
        jp_tags,
        deprecated_tags,
    )


def _load_persisted_jp_records(
    config: ParseWorkflowConfig,
) -> tuple[list[JpTag], list[DeprecatedTag]]:
    jp_tags = validate_jp_tags(_load_json_array(config.data_jp, "JPタグデータ"))
    deprecated_tags = validate_deprecated_tags(
        _load_json_array(config.data_deprecated, "JP非使用タグデータ"),
        jp_tags,
    )
    return jp_tags, deprecated_tags


def _collect_crosswalk_outputs(
    config: ParseWorkflowConfig,
    jp_tags: list[JpTag],
    deprecated_tags: list[DeprecatedTag],
) -> ParseBatch:
    resolver = _build_crosswalk_resolver(jp_tags, deprecated_tags)
    _require_file(config.sources_int, "INTタグクロスウォーク")
    _require_file(config.sources_ko, "KOタグクロスウォーク")
    _require_branch_guides(config)
    int_mappings = config.int_parser.parse_int_crosswalk(
        config.sources_int,
        resolver.resolve,
    )
    ko_mappings = config.ko_parser.parse_ko_crosswalk(
        config.sources_ko,
        resolver.resolve,
    )
    diagnostics: list[str] = []
    branch_analysis = config.branch_guide_parser.analyze_branch_guides(
        config.branch_guide_sources,
        resolver.resolve,
        strict=True,
        diagnostics=diagnostics,
    )
    branch_mappings = branch_analysis.mappings
    accepted_count = sum(
        stats["accepted_tags"] for stats in branch_analysis.stats.values()
    )
    conflict_count = sum(
        stats["conflicting_tags"] for stats in branch_analysis.stats.values()
    )
    unresolved_count = sum(
        stats["unresolved_source_tags"] for stats in branch_analysis.stats.values()
    )
    outputs = {
        config.data_int_crosswalk: int_mappings,
        config.data_ko_crosswalk: ko_mappings,
        config.data_branch_guide_crosswalk: branch_mappings,
    }
    messages = (
        (
            "INT crosswalk: "
            f"{sum(len(values) for values in int_mappings.values())} "
            f"mappings -> {config.data_int_crosswalk}"
        ),
        (
            f"KO crosswalk: {len(ko_mappings.get('ko', {}))} mappings -> "
            f"{config.data_ko_crosswalk}"
        ),
        (
            "branch guide crosswalk: "
            f"{sum(len(values) for values in branch_mappings.values())} mappings "
            f"(accepted={accepted_count}, conflicting={conflict_count}, "
            f"unresolved={unresolved_count}) -> {config.data_branch_guide_crosswalk}"
        ),
    )
    return ParseBatch(
        outputs=outputs,
        messages=messages,
        diagnostics=tuple(diagnostics),
    )


def _collect_crosswalk_outputs_from_persisted_records(
    config: ParseWorkflowConfig,
) -> ParseBatch:
    jp_tags, deprecated_tags = _load_persisted_jp_records(config)
    return _collect_crosswalk_outputs(config, jp_tags, deprecated_tags)


def _merge_batches(batches: list[ParseBatch]) -> ParseBatch:
    outputs: dict[Path, object] = {}
    messages: list[str] = []
    diagnostics: list[str] = []
    for batch in batches:
        outputs.update(batch.outputs)
        messages.extend(batch.messages)
        diagnostics.extend(batch.diagnostics)
    return ParseBatch(
        outputs=outputs,
        messages=tuple(messages),
        diagnostics=tuple(diagnostics),
    )


def collect_outputs(
    language: Language,
    *,
    config: ParseWorkflowConfig | None = None,
) -> ParseBatch:
    """Collect parsed records for one supported language selection."""
    config = config or default_parse_workflow_config()
    if language not in LANGUAGES:
        raise ValueError(f"未対応の解析対象です: {language}")

    batches: list[ParseBatch] = []
    jp_tags: list[JpTag] | None = None
    deprecated_tags: list[DeprecatedTag] | None = None
    if language in {"en", "all"}:
        batches.append(_collect_en_outputs(config))
    if language in {"jp", "all"}:
        jp_batch, jp_tags, deprecated_tags = _collect_jp_outputs(config)
        batches.append(jp_batch)
    if language in {"crosswalks", "all"}:
        if language == "all":
            if jp_tags is None or deprecated_tags is None:
                raise ValueError("all解析にはJPタグデータが必要です")
            batches.append(_collect_crosswalk_outputs(config, jp_tags, deprecated_tags))
        else:
            batches.append(_collect_crosswalk_outputs_from_persisted_records(config))
    return _merge_batches(batches)


def publish_outputs(
    outputs: Mapping[Path, object],
) -> None:
    """Publish all collected records in one atomic batch."""
    publish_files_atomically({
        destination: lambda temporary, data=data: write_json(temporary, data)
        for destination, data in outputs.items()
    })


def parse_and_publish_sources(
    language: Language,
    *,
    config: ParseWorkflowConfig | None = None,
) -> ParseBatch:
    """Collect, atomically publish, and report one source parse workflow."""
    batch = collect_outputs(language, config=config)
    publish_outputs(batch.outputs)
    for message in batch.messages:
        print(message)
    for diagnostic in batch.diagnostics:
        print(f"警告: {diagnostic}")
    return batch


__all__ = [
    "BRANCH_GUIDE_SOURCES",
    "SOURCES_EN",
    "SOURCES_INT",
    "SOURCES_JP",
    "SOURCES_JP_UNUSED",
    "SOURCES_KO",
    "LANGUAGES",
    "Language",
    "ParseBatch",
    "ParseWorkflowConfig",
    "collect_outputs",
    "default_parse_workflow_config",
    "parse_and_publish_sources",
    "publish_outputs",
]
