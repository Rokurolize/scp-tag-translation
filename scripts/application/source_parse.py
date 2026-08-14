"""Parse official tag sources and publish generated records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from scripts.domain.policy.tag_policy import EN_CROSSWALK_SEMANTIC_REPLACEMENTS
from scripts.domain.crosswalk_resolution import CrosswalkResolver
from scripts.contracts.errors import InvalidDomainInputError
from scripts.domain.records.tag_records import DeprecatedTag, JpTag
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
from scripts.infrastructure.json_io import write_json
from scripts.parsers import en_parser, jp_parser
from scripts.pipeline.source_manifest import (
    branch_guide_sources,
    parser_source_path,
    source_directory,
)
from scripts.application.source_parsing.crosswalks import (
    CrosswalkParseInputs,
    collect_crosswalk_parses,
)
from scripts.application.source_parsing.models import ParseBatch, ParserOutput
from scripts.application.source_parsing.records import (
    require_file,
)
from scripts.application.source_parsing.reporting import (
    SourceParseDiagnosticsError,
    merge_batches,
)

Language = Literal["en", "jp", "crosswalks", "all"]
LANGUAGES: tuple[Language, ...] = ("en", "jp", "crosswalks", "all")

@dataclass(frozen=True)
class ParseSourcePaths:
    """Official source locations consumed by one parse workflow."""

    en: Path = field(default_factory=lambda: parser_source_path("en", root=ROOT))
    jp: Path = field(default_factory=lambda: source_directory("jp", root=ROOT))
    jp_unused: Path | None = field(
        default_factory=lambda: parser_source_path("jp_unused", root=ROOT),
    )
    int: Path = field(default_factory=lambda: parser_source_path("int", root=ROOT))
    ko: Path = field(default_factory=lambda: parser_source_path("ko", root=ROOT))
    branch_guides: Mapping[str, tuple[Path, ...]] = field(
        default_factory=lambda: dict(branch_guide_sources(root=ROOT)),
    )


@dataclass(frozen=True)
class ParseOutputPaths:
    """Generated JSON destinations for one parse workflow."""

    en: Path = field(default_factory=lambda: DATA_EN)
    jp: Path = field(default_factory=lambda: DATA_JP)
    deprecated: Path = field(default_factory=lambda: DATA_DEPRECATED)
    int_crosswalk: Path = field(default_factory=lambda: DATA_INT_CROSSWALK)
    ko_crosswalk: Path = field(default_factory=lambda: DATA_KO_CROSSWALK)
    branch_guide_crosswalk: Path = field(
        default_factory=lambda: DATA_BRANCH_GUIDE_CROSSWALK,
    )


@dataclass(frozen=True)
class ParseWorkflowConfig:
    """Compose source and output paths for one parse workflow."""

    sources: ParseSourcePaths = field(default_factory=ParseSourcePaths)
    outputs: ParseOutputPaths = field(default_factory=ParseOutputPaths)


def _collect_en_outputs(config: ParseWorkflowConfig) -> ParseBatch:
    require_file(config.sources.en, "ENソースファイル")
    diagnostics: list[str] = []
    en_tags = en_parser.parse_en_tags(
        config.sources.en,
        strict=True,
        diagnostics=diagnostics,
    )
    return ParseBatch(
        outputs={config.outputs.en: en_tags},
        messages=(f"EN: {len(en_tags)} タグを解析 → {config.outputs.en}",),
        diagnostics=tuple(diagnostics),
    )


def _collect_jp_outputs(
    config: ParseWorkflowConfig,
) -> tuple[ParseBatch, list[JpTag], list[DeprecatedTag]]:
    if not config.sources.jp.is_dir():
        raise FileNotFoundError(
            f"JPソースディレクトリが見つかりません: {config.sources.jp}"
        )
    diagnostics: list[str] = []
    jp_tags = jp_parser.parse_jp_tags(
        config.sources.jp,
        strict=True,
        diagnostics=diagnostics,
    )
    deprecated_tags = (
        jp_parser.parse_unused_tag_records(
            config.sources.jp_unused,
            strict=True,
            diagnostics=diagnostics,
        )
        if config.sources.jp_unused is not None
        and config.sources.jp_unused.is_file()
        else []
    )
    return (
        ParseBatch(
            outputs={
                config.outputs.jp: jp_tags,
                config.outputs.deprecated: deprecated_tags,
            },
            messages=(
                f"JP: {len(jp_tags)} タグを解析 → {config.outputs.jp}",
                f"JP(未使用): {len(deprecated_tags)} タグを解析 → {config.outputs.deprecated}",
            ),
            diagnostics=tuple(diagnostics),
        ),
        jp_tags,
        deprecated_tags,
    )


def _collect_crosswalk_outputs(
    config: ParseWorkflowConfig,
    jp_tags: list[JpTag],
    deprecated_tags: list[DeprecatedTag],
) -> ParseBatch:
    parsed = collect_crosswalk_parses(
        inputs=CrosswalkParseInputs(
            int_source=config.sources.int,
            ko_source=config.sources.ko,
            branch_guide_sources=config.sources.branch_guides,
        ),
        resolver=CrosswalkResolver(
            jp_tags,
            deprecated_tags,
            EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
        ),
    )
    int_mappings = parsed.int_mappings
    ko_mappings = parsed.ko_mappings
    branch_analysis = parsed.branch_analysis
    diagnostics = parsed.diagnostics
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
        config.outputs.int_crosswalk: int_mappings,
        config.outputs.ko_crosswalk: ko_mappings,
        config.outputs.branch_guide_crosswalk: branch_mappings,
    }
    messages = (
        (
            "INT crosswalk: "
            f"{sum(len(values) for values in int_mappings.values())} "
            f"mappings -> {config.outputs.int_crosswalk}"
        ),
        (
            f"KO crosswalk: {len(ko_mappings.get('ko', {}))} mappings -> "
            f"{config.outputs.ko_crosswalk}"
        ),
        (
            "branch guide crosswalk: "
            f"{sum(len(values) for values in branch_mappings.values())} mappings "
            f"(accepted={accepted_count}, conflicting={conflict_count}, "
            f"unresolved={unresolved_count}) -> {config.outputs.branch_guide_crosswalk}"
        ),
    )
    return ParseBatch(
        outputs=outputs,
        messages=messages,
        diagnostics=tuple(diagnostics),
    )


def collect_parsed_source_outputs(
    language: Language,
    *,
    config: ParseWorkflowConfig | None = None,
) -> ParseBatch:
    """Collect records for one language, raising input, source, or file errors."""
    config = config or ParseWorkflowConfig()
    if language not in LANGUAGES:
        raise InvalidDomainInputError(f"未対応の解析対象です: {language}")

    if language == "en":
        return merge_batches([_collect_en_outputs(config)])
    jp_batch, jp_tags, deprecated_tags = _collect_jp_outputs(config)
    if language == "jp":
        return merge_batches([jp_batch])
    if language == "crosswalks":
        return merge_batches([_collect_crosswalk_outputs(config, jp_tags, deprecated_tags)])

    return merge_batches([
        _collect_en_outputs(config),
        jp_batch,
        _collect_crosswalk_outputs(config, jp_tags, deprecated_tags),
    ])


def publish_parsed_source_outputs(
    outputs: Mapping[Path, ParserOutput],
) -> None:
    """Publish parsed source records in one atomic batch.

    Raises:
        TypeError: If a parsed output cannot be JSON serialized.
        OSError: If a filesystem operation fails.
        AtomicPublicationError: If rollback or cleanup also fails.
        BaseException: Other exceptions raised by a writer propagate unchanged.
    """
    publish_files_atomically({
        destination: lambda temporary, data=data: write_json(temporary, data)
        for destination, data in outputs.items()
    })


def parse_and_publish_sources(
    language: Language,
    *,
    config: ParseWorkflowConfig | None = None,
) -> ParseBatch:
    """Collect and publish one workflow; raises diagnostics or I/O errors on failure."""
    batch = collect_parsed_source_outputs(language, config=config)
    if batch.diagnostics:
        raise SourceParseDiagnosticsError(batch.diagnostics)
    publish_parsed_source_outputs(batch.outputs)
    return batch


__all__ = [
    "LANGUAGES",
    "Language",
    "ParseBatch",
    "ParseOutputPaths",
    "ParseSourcePaths",
    "ParseWorkflowConfig",
    "collect_parsed_source_outputs",
    "parse_and_publish_sources",
    "publish_parsed_source_outputs",
]
