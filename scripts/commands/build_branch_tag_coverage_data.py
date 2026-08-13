#!/usr/bin/env python3
"""Build visualization data for branch tag coverage against the JP tag list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application.coverage_build import (
    CoverageBuildConfig,
    CoverageInputs,
    DEFAULT_OUTPUT_DIR,
    build_and_publish_coverage,
    default_coverage_build_config,
    load_coverage_inputs,
)
from scripts.application import coverage_build as _workflow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build visualization data for branch tag coverage against JP tags",
    )
    parser.add_argument(
        "--corpus-root",
        required=True,
        type=Path,
        help="Path to scp-wiki-translation/corpus",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for branch_tag_coverage.{json,tsv}",
    )
    parser.add_argument(
        "--branches",
        nargs="*",
        help="Optional source branches. Defaults to the 15 supported sites.",
    )
    args = parser.parse_args()

    corpus_root = args.corpus_root
    if not corpus_root.is_dir():
        print(f"エラー: corpus rootが見つかりません: {corpus_root}")
        sys.exit(1)

    branches = [
        branch
        for branch in (args.branches or _workflow.SUPPORTED_BRANCHES)
        if branch != "jp" and not branch.startswith("_")
    ]
    if not branches:
        print("エラー: 可視化対象の支部が見つかりません。")
        sys.exit(1)

    output_dir = args.output_dir or _workflow.DEFAULT_OUTPUT_DIR
    config = default_coverage_build_config(output_dir=output_dir)
    try:
        coverage, output_paths = build_and_publish_coverage(
            corpus_root,
            branches,
            config=config,
        )
    except (OSError, ValueError) as err:
        print(f"エラー: 可視化データ生成に失敗しました: {err}")
        sys.exit(1)
    json_path, tsv_path, inventory_json_path, inventory_tsv_path = output_paths
    total_tags = sum(branch["tag_count"] for branch in coverage["branches"])
    print(
        f"可視化データ生成完了: {len(coverage['branches'])}支部, "
        f"{total_tags}タグ -> {json_path}, {tsv_path}, "
        f"{inventory_json_path}, {inventory_tsv_path}"
    )


__all__ = [
    "CoverageBuildConfig",
    "CoverageInputs",
    "DEFAULT_OUTPUT_DIR",
    "build_and_publish_coverage",
    "default_coverage_build_config",
    "load_coverage_inputs",
    "main",
]


if __name__ == "__main__":
    main()
