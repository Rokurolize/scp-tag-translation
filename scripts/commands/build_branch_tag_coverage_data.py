#!/usr/bin/env python3
"""Build visualization data for branch tag coverage against the JP tag list."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.pipeline.corpus import collect_branch_tag_stats
from scripts.pipeline.coverage_outputs import (
    write_application_inventory_tsv,
    write_coverage_tsv,
)
from scripts.pipeline.dictionary_inputs import (
    MappingInputPaths,
    default_mapping_input_paths,
    load_mapping_inputs,
)
from scripts.infrastructure.json_io import write_json
from scripts.infrastructure.data_paths import VISUALIZATION_DIR
from scripts.domain.branch_config import (
    SUPPORTED_BRANCHES,
    validate_requested_branches,
)
from scripts.domain.tag_coverage import (
    CoverageInputs,
    build_application_inventory,
    build_coverage,
)
from scripts.domain.tag_coverage_models import Coverage

DEFAULT_OUTPUT_DIR = VISUALIZATION_DIR


@dataclass(frozen=True)
class CoverageBuildConfig:
    """Input and output locations for one coverage build."""

    output_dir: Path = DEFAULT_OUTPUT_DIR
    mapping_inputs: MappingInputPaths = field(
        default_factory=default_mapping_input_paths,
    )


def default_coverage_build_config() -> CoverageBuildConfig:
    """Return the repository's default coverage build configuration."""
    return CoverageBuildConfig()


def load_coverage_inputs(paths: MappingInputPaths) -> CoverageInputs:
    loaded = load_mapping_inputs(paths)
    return CoverageInputs(
        en_tags=loaded.en_tags,
        jp_tags=loaded.jp_tags,
        deprecated_tags=loaded.deprecated_tags,
        mapping_policy=loaded.mapping_policy,
    )


def build_and_publish_coverage(
    corpus_root: Path,
    branches: Sequence[str],
    *,
    config: CoverageBuildConfig | None = None,
) -> tuple[Coverage, tuple[Path, Path, Path, Path]]:
    """Build coverage artifacts and publish all four outputs atomically."""

    branches = validate_requested_branches(branches)
    config = config or default_coverage_build_config()
    inputs = load_coverage_inputs(config.mapping_inputs)
    branch_tag_stats = {
        branch: collect_branch_tag_stats(corpus_root, branch)
        for branch in branches
    }
    coverage = build_coverage(
        corpus_root,
        branches,
        inputs,
        branch_tag_stats,
    )
    json_path = config.output_dir / "branch_tag_coverage.json"
    tsv_path = config.output_dir / "branch_tag_coverage.tsv"
    inventory = build_application_inventory(coverage)
    inventory_json_path = config.output_dir / "tag_application_inventory.json"
    inventory_tsv_path = config.output_dir / "tag_application_inventory.tsv"
    publish_files_atomically({
        json_path: lambda temporary: write_json(temporary, coverage),
        tsv_path: lambda temporary: write_coverage_tsv(temporary, coverage),
        inventory_json_path: (
            lambda temporary: write_json(temporary, inventory)
        ),
        inventory_tsv_path: (
            lambda temporary: write_application_inventory_tsv(
                temporary,
                inventory,
            )
        ),
    })
    return coverage, (
        json_path,
        tsv_path,
        inventory_json_path,
        inventory_tsv_path,
    )


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
        default=DEFAULT_OUTPUT_DIR,
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

    branches = args.branches if args.branches else list(SUPPORTED_BRANCHES)
    branches = [
        branch
        for branch in branches
        if branch != "jp" and not branch.startswith("_")
    ]
    if not branches:
        print("エラー: 可視化対象の支部が見つかりません。")
        sys.exit(1)

    config = CoverageBuildConfig(
        output_dir=args.output_dir,
        mapping_inputs=default_mapping_input_paths(),
    )
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


if __name__ == "__main__":
    main()
