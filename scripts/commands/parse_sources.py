#!/usr/bin/env python3
"""Parse synchronized Wikidot tag sources into generated JSON records."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from scripts.application import source_parse as _workflow
from scripts.application.source_parse import (
    LANGUAGES,
    Language,
    ParseBatch,
    default_parse_workflow_config,
)


def collect_outputs(language: Language) -> ParseBatch:
    """Delegate record collection to the application workflow."""
    return _workflow.collect_outputs(
        language,
        config=default_parse_workflow_config(),
    )


def publish_outputs(outputs: Mapping[Path, object]) -> None:
    """Delegate atomic publication to the application workflow."""
    _workflow.publish_outputs(outputs)


def parse_and_publish_sources(language: Language) -> ParseBatch:
    """Delegate source parsing and publication to the application workflow."""
    return _workflow.parse_and_publish_sources(
        language,
        config=default_parse_workflow_config(),
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
        parse_and_publish_sources(args.lang)
    except (OSError, ValueError) as error:
        print(f"エラー: ソース解析に失敗しました: {error}")
        sys.exit(1)


__all__ = [
    "LANGUAGES",
    "ParseBatch",
    "collect_outputs",
    "default_parse_workflow_config",
    "main",
    "parse_and_publish_sources",
    "publish_outputs",
]


if __name__ == "__main__":
    main()
