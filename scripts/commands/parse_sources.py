#!/usr/bin/env python3
"""Parse synchronized Wikidot tag sources into generated JSON records."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from scripts.application import source_parse as _workflow
from scripts.application.source_parse import (
    LANGUAGES,
    Language,
    ParseBatch,
    default_parse_workflow_config,
)
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
from scripts.parsers import branch_guide_parser, en_parser, int_parser, jp_parser, ko_parser
from scripts.pipeline.source_manifest import (
    branch_guide_sources,
    parser_source_path,
    source_directory,
)

SOURCES_EN = parser_source_path("en", root=ROOT)
SOURCES_JP = source_directory("jp", root=ROOT)
SOURCES_JP_UNUSED = parser_source_path("jp_unused", root=ROOT)
SOURCES_INT = parser_source_path("int", root=ROOT)
SOURCES_KO = parser_source_path("ko", root=ROOT)
BRANCH_GUIDE_SOURCES: Mapping[str, tuple[Path, ...]] = branch_guide_sources(root=ROOT)


def collect_outputs(language: Language) -> ParseBatch:
    """Collect records through the application workflow."""
    return _workflow.collect_outputs(
        language,
        config=default_parse_workflow_config(),
    )


def publish_outputs(outputs: Mapping[Path, object]) -> None:
    """Publish records through the shared atomic writer."""
    _workflow.publish_outputs(outputs, publish=publish_files_atomically)


def parse_and_publish_sources(language: Language) -> ParseBatch:
    """Delegate source parsing and publication to the application workflow."""
    return _workflow.parse_and_publish_sources(
        language,
        config=default_parse_workflow_config(),
        publish_outputs_fn=publish_outputs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        default="all",
        help="解析対象の言語 (デフォルト: all)",
    )
    args = parser.parse_args()

    try:
        parse_and_publish_sources(cast(Language, args.lang))
    except (OSError, ValueError) as error:
        print(f"エラー: ソース解析に失敗しました: {error}")
        sys.exit(1)


__all__ = [
    "BRANCH_GUIDE_SOURCES",
    "DATA_BRANCH_GUIDE_CROSSWALK",
    "DATA_DEPRECATED",
    "DATA_EN",
    "DATA_INT_CROSSWALK",
    "DATA_JP",
    "DATA_KO_CROSSWALK",
    "LANGUAGES",
    "ParseBatch",
    "SOURCES_EN",
    "SOURCES_INT",
    "SOURCES_JP",
    "SOURCES_JP_UNUSED",
    "SOURCES_KO",
    "branch_guide_parser",
    "collect_outputs",
    "default_parse_workflow_config",
    "en_parser",
    "int_parser",
    "jp_parser",
    "ko_parser",
    "main",
    "parse_and_publish_sources",
    "publish_files_atomically",
    "publish_outputs",
]


if __name__ == "__main__":
    main()
