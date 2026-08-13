#!/usr/bin/env python3
"""Build visualization data for branch tag coverage against the JP tag list."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from scripts.atomic_output import publish_files_atomically
from scripts.corpus import collect_branch_tag_stats
from scripts.dictionary_inputs import load_mapping_policy_inputs
from scripts.json_io import load_json, write_json
from scripts.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    VISUALIZATION_DIR,
)
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.tag_coverage import (
    CoverageInputs,
    build_application_inventory,
    build_coverage,
)
from scripts.domain.tag_models import (
    ApplicationInventory,
    Coverage,
)
from scripts.domain.tag_policy import build_mapping_policy
from scripts.domain.tag_validation import validate_tag_records

DEFAULT_OUTPUT_DIR = VISUALIZATION_DIR


def load_coverage_inputs() -> CoverageInputs:
    if not DATA_JP.exists() or not DATA_DEPRECATED.exists():
        raise FileNotFoundError("Run python -m scripts.commands.parse_sources first.")

    en_tags, jp_tags, deprecated_tags = validate_tag_records(
        load_json(DATA_EN),
        load_json(DATA_JP),
        load_json(DATA_DEPRECATED),
    )
    mapping_policy = build_mapping_policy(
        jp_tags,
        deprecated_tags,
        load_mapping_policy_inputs(),
    )
    return CoverageInputs(
        en_tags=en_tags,
        jp_tags=jp_tags,
        deprecated_tags=deprecated_tags,
        mapping_policy=mapping_policy,
    )


def write_tsv(path: Path, coverage: Coverage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "branch",
        "tag",
        "rank",
        "page_count",
        "status",
        "recognized_by_jp_policy",
        "jp_tag",
        "replacement",
        "translation_action",
        "copy_allowed",
        "display_tag",
        "sample_slugs",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for branch_entry in coverage["branches"]:
            branch = branch_entry["branch"]
            for tag_entry in branch_entry["tags"]:
                writer.writerow({
                    "branch": branch,
                    "tag": tag_entry["tag"],
                    "rank": tag_entry["rank"],
                    "page_count": tag_entry["page_count"],
                    "status": tag_entry["status"],
                    "recognized_by_jp_policy": str(
                        tag_entry["recognized_by_jp_policy"]
                    ).lower(),
                    "jp_tag": tag_entry["jp_tag"] or "",
                    "replacement": tag_entry["replacement"] or "",
                    "translation_action": tag_entry["translation_action"],
                    "copy_allowed": str(tag_entry["copy_allowed"]).lower(),
                    "display_tag": tag_entry["display_tag"] or "",
                    "sample_slugs": ",".join(tag_entry["sample_slugs"]),
                })


def write_application_tsv(path: Path, inventory: ApplicationInventory) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "site",
        "branch",
        "source_tag",
        "display_tag",
        "page_count",
        "sample_slugs",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for branch_entry in inventory["branches"]:
            for tag_entry in branch_entry["tags"]:
                writer.writerow({
                    "site": branch_entry["site"],
                    "branch": branch_entry["branch"],
                    "source_tag": tag_entry["tag"],
                    "display_tag": tag_entry["display_tag"],
                    "page_count": tag_entry["page_count"],
                    "sample_slugs": ",".join(tag_entry["sample_slugs"]),
                })


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

    try:
        inputs = load_coverage_inputs()
        branch_tag_stats = {
            branch: collect_branch_tag_stats(corpus_root, branch)
            for branch in branches
        }
        coverage = build_coverage(
            str(corpus_root),
            branches,
            inputs,
            branch_tag_stats,
        )
        json_path = args.output_dir / "branch_tag_coverage.json"
        tsv_path = args.output_dir / "branch_tag_coverage.tsv"
        inventory = build_application_inventory(coverage)
        inventory_json_path = args.output_dir / "tag_application_inventory.json"
        inventory_tsv_path = args.output_dir / "tag_application_inventory.tsv"
        publish_files_atomically({
            json_path: lambda temporary: write_json(temporary, coverage),
            tsv_path: lambda temporary: write_tsv(temporary, coverage),
            inventory_json_path: (
                lambda temporary: write_json(temporary, inventory)
            ),
            inventory_tsv_path: (
                lambda temporary: write_application_tsv(temporary, inventory)
            ),
        })
    except (OSError, ValueError) as err:
        print(f"エラー: 可視化データ生成に失敗しました: {err}")
        sys.exit(1)
    total_tags = sum(branch["tag_count"] for branch in coverage["branches"])
    print(
        f"可視化データ生成完了: {len(coverage['branches'])}支部, "
        f"{total_tags}タグ -> {json_path}, {tsv_path}, "
        f"{inventory_json_path}, {inventory_tsv_path}"
    )


if __name__ == "__main__":
    main()
