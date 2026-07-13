#!/usr/bin/env python3
"""Build visualization data for branch tag coverage against the JP tag list."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_dict as en_builder
from scripts.atomic_output import publish_files_atomically
from scripts.branch_config import BRANCH_CONFIG_BY_CODE, SUPPORTED_BRANCHES
from scripts.tag_models import (
    ApplicationBranch,
    ApplicationInventory,
    ApplicationTag,
    Classification,
    Coverage,
    CoverageBranch,
    CoverageTag,
    DeprecatedTag,
    EnTag,
    JpTag,
    JpTagPolicy,
    TagStats,
)
from scripts.tag_policy import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    BranchMappingPolicy,
    JpPolicyInputs,
    MappingPolicy,
    build_jp_policy,
    build_mapping_policy,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "visualization"
SAMPLE_LIMIT = 5

STATUS_DESCRIPTIONS = {
    "jp_unused_replacement": "Listed in the JP unused-tag page for this source branch with one replacement.",
    "jp_unused_no_single_replacement": "Listed in the JP unused-tag page for this source branch without one deterministic replacement.",
    "jp_translation_policy_omit": "Not copied because the JP tag-list FAQ says to omit this source category on translations.",
    "jp_tag_name": "The source tag itself is a registered JP tag name.",
    "jp_tag_alias": "The source tag is recorded in the JP tag list as a source-language tag annotation.",
    "curated_override_only": "Not recorded in the JP tag list, but mapped by local reviewed override data.",
    "official_crosswalk": "Mapped by an official SCP-INT or branch-local tag crosswalk to a current registered JP tag.",
    "unhandled": "No current JP tag-list mapping, reviewed override, or official crosswalk.",
}


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def collect_branch_tag_stats(
    corpus_root: Path,
    branch: str,
) -> tuple[int, dict[str, TagStats]]:
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


@dataclass(frozen=True)
class ClassificationContext:
    mapping_policy: MappingPolicy
    branch_policy: BranchMappingPolicy
    target_policies: Mapping[str, JpTagPolicy] | None = None
    translation_policy_omit: frozenset[str] = frozenset()

    @classmethod
    def for_branch(
        cls,
        mapping_policy: MappingPolicy,
        branch: str,
        *,
        target_policies: Mapping[str, JpTagPolicy] | None = None,
        translation_policy_omit: set[str] | frozenset[str] = frozenset(),
    ) -> ClassificationContext:
        return cls(
            mapping_policy=mapping_policy,
            branch_policy=mapping_policy.for_branch(branch),
            target_policies=target_policies,
            translation_policy_omit=frozenset(translation_policy_omit),
        )


@dataclass(frozen=True)
class _BaseClassification:
    status: str
    jp_list_handled: bool
    translator_handled: bool
    jp_tag: str | None = None
    replacement: str | None = None


def _base_classification(
    tag: str,
    context: ClassificationContext,
) -> _BaseClassification:
    branch_policy = context.branch_policy
    if tag in branch_policy.deprecated_tags:
        replacement = branch_policy.replacements.get(tag)
        return _BaseClassification(
            status=(
                "jp_unused_replacement"
                if replacement
                else "jp_unused_no_single_replacement"
            ),
            jp_list_handled=True,
            translator_handled=bool(replacement),
            replacement=replacement,
        )
    if tag in context.mapping_policy.jp_names:
        return _BaseClassification("jp_tag_name", True, True, jp_tag=tag)
    if tag in branch_policy.overrides:
        return _BaseClassification(
            "curated_override_only",
            False,
            True,
            jp_tag=branch_policy.overrides[tag],
        )
    if tag in context.translation_policy_omit:
        return _BaseClassification(
            "jp_translation_policy_omit",
            True,
            False,
        )
    if tag in branch_policy.official_crosswalk:
        return _BaseClassification(
            "official_crosswalk",
            False,
            True,
            jp_tag=branch_policy.official_crosswalk[tag],
        )
    if tag in context.mapping_policy.jp_source_map:
        return _BaseClassification(
            "jp_tag_alias",
            True,
            True,
            jp_tag=context.mapping_policy.jp_source_map[tag],
        )
    return _BaseClassification("unhandled", False, False)


def classify_tag(tag: str, context: ClassificationContext) -> Classification:
    base = _base_classification(tag, context)
    target = base.replacement or base.jp_tag
    action: str
    copy_allowed = False
    display_tag: str | None = target
    target_policy: JpTagPolicy | None = None
    translator_handled = base.translator_handled

    if base.status == "unhandled":
        action = "tag_application_required"
        display_tag = f"未訳-{tag}"
    elif target is None:
        action = "omit_jp_unused"
        display_tag = None
    else:
        target_policy = (
            context.target_policies.get(target)
            if context.target_policies is not None
            else None
        )
        if target_policy is None:
            if context.target_policies is not None:
                raise ValueError(
                    f"JP policy missing for mapped target: {tag}->{target}"
                )
            target_policy = {
                "copy_allowed_for_translation": True,
                "use_restricted": False,
                "edit_restricted": False,
                "translation_exempt": False,
                "special_translation_action": None,
            }
        copy_allowed = target_policy["copy_allowed_for_translation"]
        if target_policy["special_translation_action"] == "omit":
            action = "omit_jp_policy"
            translator_handled = False
        elif not copy_allowed:
            action = "staff_permission_required"
            translator_handled = False
        elif base.status == "jp_unused_replacement":
            action = "copy_replacement"
        else:
            action = "copy"

    return {
        "status": base.status,
        "jp_list_handled": base.jp_list_handled,
        "translator_handled": translator_handled,
        "jp_tag": base.jp_tag,
        "replacement": base.replacement,
        "translation_action": action,
        "copy_allowed": copy_allowed,
        "display_tag": display_tag,
        "target_policy": target_policy,
    }


def build_coverage(
    corpus_root: Path,
    branches: list[str],
) -> Coverage:
    if not DATA_JP.exists() or not DATA_DEPRECATED.exists():
        raise FileNotFoundError("Run python scripts/parse_sources.py first.")

    jp_tags = cast(list[JpTag], load_json(DATA_JP))
    deprecated_tags = cast(list[DeprecatedTag], load_json(DATA_DEPRECATED))
    en_tags = cast(list[EnTag], load_json(DATA_EN))
    mapping_policy = build_mapping_policy(jp_tags, deprecated_tags)
    en_branch_policy = mapping_policy.for_branch("en")
    en_translation_policy_omit = en_builder.en_category_omitted_tags(
        en_tags,
        jp_tags,
        set(en_branch_policy.overrides),
    )
    jp_policy = build_jp_policy(
        JpPolicyInputs(
            jp_tags=jp_tags,
            deprecated_tags=deprecated_tags,
            en_tags=en_tags,
            mapping_policy=mapping_policy,
        )
    )["tags"]

    branch_entries: list[CoverageBranch] = []
    for branch in branches:
        page_count, tag_stats = collect_branch_tag_stats(corpus_root, branch)
        status_counts: Counter[str] = Counter()
        tags: list[CoverageTag] = []
        context = ClassificationContext.for_branch(
            mapping_policy,
            branch,
            target_policies=jp_policy,
            translation_policy_omit=(
                en_translation_policy_omit
                if branch in {"en", "int"}
                else set()
            ),
        )
        sorted_tags = sorted(
            tag_stats,
            key=lambda tag: (-tag_stats[tag]["page_count"], tag),
        )
        for rank, tag in enumerate(sorted_tags, start=1):
            classification = classify_tag(tag, context)
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
                "translation_action": classification["translation_action"],
                "copy_allowed": classification["copy_allowed"],
                "display_tag": classification["display_tag"],
                "target_policy": classification["target_policy"],
                "sample_slugs": tag_stats[tag]["sample_slugs"],
            })

        branch_entries.append({
            "branch": branch,
            "site": (
                BRANCH_CONFIG_BY_CODE[branch].site
                if branch in BRANCH_CONFIG_BY_CODE
                else branch
            ),
            "page_count": page_count,
            "tag_count": len(tags),
            "status_counts": dict(sorted(status_counts.items())),
            "tags": tags,
        })

    return {
        "schema_version": 2,
        "source": {
            "corpus_root": str(corpus_root),
            "jp_tag_source": "sources/jp/tag-list.txt + registered fragments",
            "jp_unused_source": "sources/jp/fragment-unused.txt",
            "override_source": "sources/branch_to_jp_overrides.json",
            "deprecated_override_source": "sources/deprecated_replacement_overrides.json",
            "crosswalk_source": "SCP-INT, SCP-KO, and synced branch-local official tag guides",
        },
        "status_descriptions": STATUS_DESCRIPTIONS,
        "action_descriptions": {
            "copy": "Registered JP tag; copyable for a translated page.",
            "copy_replacement": "JP unused source tag replaced by one registered copyable JP tag.",
            "omit_jp_unused": "JP explicitly does not use this source tag; omit it.",
            "omit_jp_policy": "Registered JP tag whose own definition says not to apply it to this translation.",
            "staff_permission_required": "Mapped JP restriction tag without translation exemption; do not copy without staff permission.",
            "tag_application_required": "No JP tag-list mapping; omit and request/confirm a JP tag before use.",
        },
        "branches": branch_entries,
    }


def write_tsv(path: Path, coverage: Coverage) -> None:
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
                    "jp_list_handled": str(tag_entry["jp_list_handled"]).lower(),
                    "translator_handled": str(tag_entry["translator_handled"]).lower(),
                    "jp_tag": tag_entry["jp_tag"] or "",
                    "replacement": tag_entry["replacement"] or "",
                    "translation_action": tag_entry["translation_action"],
                    "copy_allowed": str(tag_entry["copy_allowed"]).lower(),
                    "display_tag": tag_entry["display_tag"] or "",
                    "sample_slugs": ",".join(tag_entry["sample_slugs"]),
                })


def build_application_inventory(coverage: Coverage) -> ApplicationInventory:
    branches: list[ApplicationBranch] = []
    for branch_entry in coverage["branches"]:
        tags: list[ApplicationTag] = [
            {
                "tag": entry["tag"],
                "display_tag": entry["display_tag"],
                "page_count": entry["page_count"],
                "sample_slugs": entry["sample_slugs"],
            }
            for entry in branch_entry["tags"]
            if entry["translation_action"] == "tag_application_required"
        ]
        branches.append({
            "branch": branch_entry["branch"],
            "site": branch_entry["site"],
            "scanned_page_count": branch_entry["page_count"],
            "tag_count": len(tags),
            "tags": tags,
        })
    return {
        "schema_version": 1,
        "rule": "JP tag-list未掲載。付与を見合わせ、タグ専任スタッフへの申請・確認が必要。",
        "branches": branches,
    }


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
        coverage = build_coverage(corpus_root, branches)
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
