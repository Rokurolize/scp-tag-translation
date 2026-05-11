#!/usr/bin/env python3
"""Build visualization data for branch tag coverage against the JP tag list."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_branch_dicts_from_corpus as branch_builder

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "visualization"
SAMPLE_LIMIT = 5

STATUS_DESCRIPTIONS = {
    "jp_unused_replacement": "Listed in the JP unused-tag page for this source branch with one replacement.",
    "jp_unused_no_single_replacement": "Listed in the JP unused-tag page for this source branch without one deterministic replacement.",
    "jp_tag_name": "The source tag itself is a registered JP tag name.",
    "jp_tag_alias": "The source tag is recorded in the JP tag list as a source-language tag annotation.",
    "curated_override_only": "Not recorded in the JP tag list, but mapped by local reviewed override data.",
    "unhandled": "Not recorded in the JP tag list or local reviewed overrides.",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def collect_branch_tag_stats(
    corpus_root: Path,
    branch: str,
) -> tuple[int, dict[str, dict[str, Any]]]:
    pages_dir = corpus_root / branch / "pages"
    if not pages_dir.is_dir():
        raise ValueError(f"corpus branch pages directory not found: {pages_dir}")

    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    page_count = 0
    for meta_path in sorted(pages_dir.glob("*/meta.json")):
        meta = load_json(meta_path)
        page_count += 1
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, str):
            tags = [raw_tags]
        elif isinstance(raw_tags, list):
            tags = [tag for tag in raw_tags if isinstance(tag, str) and tag]
        else:
            raise ValueError(f"invalid tags field in {meta_path}")

        for tag in set(tags):
            counts[tag] += 1
            if len(samples[tag]) < SAMPLE_LIMIT:
                samples[tag].append(meta_path.parent.name)

    tag_stats = {
        tag: {
            "page_count": count,
            "sample_slugs": samples[tag],
        }
        for tag, count in counts.items()
    }
    return page_count, tag_stats


def classify_tag(
    branch: str,
    tag: str,
    jp_names: set[str],
    jp_source_map: dict[str, str],
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str]],
    overrides: dict[str, dict[str, str]],
) -> dict[str, Any]:
    source_lang = branch_builder.branch_to_source_lang(branch)
    branch_deprecated = deprecated_tags.get(source_lang, set())
    branch_replacements = replacements.get(source_lang, {})
    branch_overrides = overrides.get(branch, {})

    if tag in branch_deprecated:
        replacement = branch_replacements.get(tag)
        status = (
            "jp_unused_replacement"
            if replacement
            else "jp_unused_no_single_replacement"
        )
        return {
            "status": status,
            "jp_list_handled": True,
            "translator_handled": bool(replacement),
            "jp_tag": None,
            "replacement": replacement,
        }
    if tag in jp_names:
        return {
            "status": "jp_tag_name",
            "jp_list_handled": True,
            "translator_handled": True,
            "jp_tag": tag,
            "replacement": None,
        }
    if tag in jp_source_map:
        return {
            "status": "jp_tag_alias",
            "jp_list_handled": True,
            "translator_handled": True,
            "jp_tag": jp_source_map[tag],
            "replacement": None,
        }
    if tag in branch_overrides:
        return {
            "status": "curated_override_only",
            "jp_list_handled": False,
            "translator_handled": True,
            "jp_tag": branch_overrides[tag],
            "replacement": None,
        }
    return {
        "status": "unhandled",
        "jp_list_handled": False,
        "translator_handled": False,
        "jp_tag": None,
        "replacement": None,
    }


def build_coverage(
    corpus_root: Path,
    branches: list[str],
) -> dict[str, Any]:
    if not branch_builder.DATA_JP.exists() or not branch_builder.DATA_DEPRECATED.exists():
        raise FileNotFoundError("Run python scripts/parse_sources.py first.")

    jp_tags: list[dict] = load_json(branch_builder.DATA_JP)
    deprecated_raw: list[dict] = load_json(branch_builder.DATA_DEPRECATED)
    jp_names, jp_source_map = branch_builder.jp_maps(jp_tags)
    overrides = branch_builder.load_overrides(branch_builder.OVERRIDES_PATH, jp_names)
    deprecated_tags, replacements = branch_builder.deprecated_by_source_lang(
        deprecated_raw,
        jp_names,
    )

    branch_entries = []
    for branch in sorted(branches):
        page_count, tag_stats = collect_branch_tag_stats(corpus_root, branch)
        status_counts: Counter[str] = Counter()
        tags = []
        sorted_tags = sorted(
            tag_stats,
            key=lambda tag: (-tag_stats[tag]["page_count"], tag),
        )
        for rank, tag in enumerate(sorted_tags, start=1):
            classification = classify_tag(
                branch,
                tag,
                jp_names,
                jp_source_map,
                deprecated_tags,
                replacements,
                overrides,
            )
            status_counts[classification["status"]] += 1
            tags.append({
                "tag": tag,
                "rank": rank,
                "page_count": tag_stats[tag]["page_count"],
                "status": classification["status"],
                "jp_list_handled": classification["jp_list_handled"],
                "translator_handled": classification["translator_handled"],
                "jp_tag": classification["jp_tag"],
                "replacement": classification["replacement"],
                "sample_slugs": tag_stats[tag]["sample_slugs"],
            })

        branch_entries.append({
            "branch": branch,
            "page_count": page_count,
            "tag_count": len(tags),
            "status_counts": dict(sorted(status_counts.items())),
            "tags": tags,
        })

    return {
        "schema_version": 1,
        "source": {
            "corpus_root": str(corpus_root),
            "jp_tag_source": "sources/jp/fragment-*.txt",
            "jp_unused_source": "sources/jp/fragment-unused.txt",
            "override_source": "sources/branch_to_jp_overrides.json",
        },
        "status_descriptions": STATUS_DESCRIPTIONS,
        "branches": branch_entries,
    }


def write_tsv(path: Path, coverage: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "branch",
        "tag",
        "rank",
        "page_count",
        "status",
        "jp_list_handled",
        "translator_handled",
        "jp_tag",
        "replacement",
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
                    "jp_list_handled": str(tag_entry["jp_list_handled"]).lower(),
                    "translator_handled": str(tag_entry["translator_handled"]).lower(),
                    "jp_tag": tag_entry["jp_tag"] or "",
                    "replacement": tag_entry["replacement"] or "",
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
        help="Optional source branches. Defaults to all non-JP corpus branches.",
    )
    args = parser.parse_args()

    corpus_root = args.corpus_root
    if not corpus_root.is_dir():
        print(f"エラー: corpus rootが見つかりません: {corpus_root}")
        sys.exit(1)

    branches = args.branches if args.branches else branch_builder.discover_branches(
        corpus_root,
    )
    branches = [
        branch
        for branch in branches
        if branch != "jp" and not branch.startswith("_")
    ]
    if not branches:
        print("エラー: 可視化対象の支部が見つかりません。")
        sys.exit(1)

    try:
        coverage = build_coverage(corpus_root, branches)
    except (OSError, ValueError) as err:
        print(f"エラー: 可視化データ生成に失敗しました: {err}")
        sys.exit(1)

    json_path = args.output_dir / "branch_tag_coverage.json"
    tsv_path = args.output_dir / "branch_tag_coverage.tsv"
    write_json(json_path, coverage)
    write_tsv(tsv_path, coverage)
    total_tags = sum(branch["tag_count"] for branch in coverage["branches"])
    print(
        f"可視化データ生成完了: {len(coverage['branches'])}支部, "
        f"{total_tags}タグ -> {json_path}, {tsv_path}"
    )


if __name__ == "__main__":
    main()
