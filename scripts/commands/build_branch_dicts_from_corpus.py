#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application.branch_selection import normalize_branch_selection
from scripts.application import dictionary_build as _workflow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build branch-to-JP tag dictionaries from local corpus metadata",
    )
    parser.add_argument(
        "--corpus-root",
        required=True,
        type=Path,
        help="Path to scp-wiki-translation/corpus",
    )
    parser.add_argument(
        "--branches",
        nargs="*",
        help=(
            "Optional dictionary output branches. Defaults to the 15 supported "
            "sites. The corpus must contain all supported branches so the global "
            "concatenated-tag policy remains complete."
        ),
    )
    args = parser.parse_args()

    corpus_root = args.corpus_root
    if not corpus_root.is_dir():
        print(f"エラー: corpus rootが見つかりません: {corpus_root}")
        sys.exit(1)
    try:
        branches = normalize_branch_selection(args.branches)
        config = _workflow.BranchBuildConfig()
        artifacts = _workflow.build_and_publish_dictionaries(
            corpus_root,
            branches,
            config=config,
        )
    except (FileNotFoundError, OSError, ValueError) as err:
        print(f"エラー: 辞書生成に失敗しました: {err}")
        sys.exit(1)

    for summary in artifacts.branch_summaries:
        print(
            f"{summary.branch}: {summary.mapped_count}/{summary.tag_count} mapped, "
            f"{summary.replacement_count} replacements -> "
            f"{summary.dictionary_path}"
        )
    print(f"jp policy: {artifacts.jp_tag_count} tags -> {config.jp_policy_path}")
    print(f"concatenated tag hints: {artifacts.hint_count}")


__all__ = ["main"]


if __name__ == "__main__":
    main()
