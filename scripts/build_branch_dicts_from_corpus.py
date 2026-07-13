#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_dict as en_builder
from scripts.atomic_output import publish_files_atomically
from scripts.branch_config import SUPPORTED_BRANCHES
from scripts.concatenated_tags import (
    build_concatenated_tag_hints,
    collect_corpus_tags_and_visible_sequences,
    complete_hint_dictionaries,
)
from scripts.tag_models import DeprecatedTag, EnTag, JpTag
from scripts.tag_policy import (
    DATA_BRANCH_GUIDE_CROSSWALK,
    DATA_DEPRECATED,
    DATA_EN,
    DATA_INT_CROSSWALK,
    DATA_JP,
    DATA_KO_CROSSWALK,
    JpPolicyInputs,
    MappingPolicy,
    build_jp_policy,
    build_mapping_policy,
)

ROOT = Path(__file__).resolve().parent.parent
DICTIONARIES_DIR = ROOT / "dictionaries"
JP_POLICY_PATH = DICTIONARIES_DIR / "jp_tag_policy.json"


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_branch_dict(
    branch: str,
    source_tags: set[str],
    policy: MappingPolicy,
) -> tuple[dict[str, str | None], dict[str, str]]:
    branch_policy = policy.for_branch(branch)

    dictionary: dict[str, str | None] = {}
    all_source_tags = (
        set(source_tags)
        | set(branch_policy.deprecated_tags)
        | set(branch_policy.overrides)
        | set(branch_policy.official_crosswalk)
    )
    for source_tag in sorted(all_source_tags):
        if source_tag in branch_policy.deprecated_tags:
            dictionary[source_tag] = None
        elif source_tag in policy.jp_names:
            dictionary[source_tag] = source_tag
        elif source_tag in branch_policy.overrides:
            dictionary[source_tag] = branch_policy.overrides[source_tag]
        elif source_tag in branch_policy.official_crosswalk:
            dictionary[source_tag] = branch_policy.official_crosswalk[source_tag]
        elif source_tag in policy.jp_source_map:
            dictionary[source_tag] = policy.jp_source_map[source_tag]
        else:
            dictionary[source_tag] = None

    concrete_replacements = {
        source_tag: replacement
        for source_tag, replacement in branch_policy.replacements.items()
        if replacement is not None
    }
    return dictionary, dict(sorted(concrete_replacements.items()))


def build_en_dicts(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    deprecated_raw: list[DeprecatedTag],
    corpus_tags: set[str],
    policy: MappingPolicy,
) -> tuple[dict[str, str | None], dict[str, str]]:
    branch_policy = policy.for_branch("en")
    deprecated_en_tags = {
        entry["en_tag"]
        for entry in deprecated_raw
        if en_builder.is_deprecated_for_en_source(entry)
    }
    deprecated_en_tags.update(branch_policy.deprecated_tags)
    category_omitted_tags = en_builder.en_category_omitted_tags(
        en_tags,
        jp_tags,
        set(branch_policy.overrides),
    )
    all_source_tags = (
        {entry["name"] for entry in en_tags}
        | corpus_tags
        | deprecated_en_tags
        | set(branch_policy.overrides)
        | set(branch_policy.official_crosswalk)
    )
    origin_replacements = {
        source_tag: replacement
        for source_tag, replacement in en_builder.EN_ORIGIN_TAG_REPLACEMENTS.items()
        if source_tag in all_source_tags
    }
    deprecated_en_tags.update(category_omitted_tags)
    deprecated_en_tags.update(origin_replacements)
    all_source_tags.update(deprecated_en_tags)
    dictionary: dict[str, str | None] = {}
    for source_tag in sorted(all_source_tags):
        if source_tag in deprecated_en_tags:
            dictionary[source_tag] = None
        elif source_tag in policy.jp_names:
            dictionary[source_tag] = source_tag
        elif source_tag in branch_policy.overrides:
            dictionary[source_tag] = branch_policy.overrides[source_tag]
        elif source_tag in branch_policy.official_crosswalk:
            dictionary[source_tag] = branch_policy.official_crosswalk[source_tag]
        elif source_tag in policy.jp_source_map:
            dictionary[source_tag] = policy.jp_source_map[source_tag]
        else:
            dictionary[source_tag] = None
    deprecated_dict = {
        source_tag: replacement
        for source_tag, replacement in branch_policy.replacements.items()
        if replacement is not None
    }
    deprecated_dict.update(origin_replacements)
    return dict(sorted(dictionary.items())), dict(sorted(deprecated_dict.items()))


@dataclass(frozen=True)
class BranchBuildSummary:
    branch: str
    mapped_count: int
    tag_count: int
    replacement_count: int
    dictionary_path: Path


@dataclass(frozen=True)
class BuildArtifacts:
    outputs: Mapping[Path, Mapping[str, object]]
    branch_summaries: tuple[BranchBuildSummary, ...]
    jp_tag_count: int
    hint_count: int


def build_artifacts(
    corpus_root: Path,
    branches: Sequence[str],
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    deprecated_tags: list[DeprecatedTag],
    policy: MappingPolicy,
    *,
    dictionaries_dir: Path = DICTIONARIES_DIR,
    jp_policy_path: Path = JP_POLICY_PATH,
    supported_branches: Sequence[str] = SUPPORTED_BRANCHES,
) -> BuildArtifacts:
    en_builder.validate_build_inputs(en_tags, jp_tags, deprecated_tags)
    outputs: dict[Path, Mapping[str, object]] = {}
    summaries = []
    branch_dictionaries: dict[str, dict[str, str | None]] = {}
    visible_sequences_by_branch: dict[
        str,
        list[tuple[str, tuple[str, ...]]],
    ] = {}

    for branch in sorted(branches):
        source_tags, visible_sequences = collect_corpus_tags_and_visible_sequences(
            corpus_root,
            branch,
        )
        if branch == "en":
            dictionary, deprecated_dict = build_en_dicts(
                en_tags,
                jp_tags,
                deprecated_tags,
                source_tags,
                policy,
            )
        else:
            dictionary, deprecated_dict = build_branch_dict(
                branch,
                source_tags,
                policy,
            )

        dictionary_path = dictionaries_dir / f"{branch}_to_jp.json"
        deprecated_path = dictionaries_dir / f"deprecated_{branch}_to_jp.json"
        outputs[dictionary_path] = dictionary
        outputs[deprecated_path] = deprecated_dict
        branch_dictionaries[branch] = dictionary
        visible_sequences_by_branch[branch] = visible_sequences
        summaries.append(
            BranchBuildSummary(
                branch=branch,
                mapped_count=sum(
                    value is not None for value in dictionary.values()
                ),
                tag_count=len(dictionary),
                replacement_count=len(deprecated_dict),
                dictionary_path=dictionary_path,
            )
        )

    hint_dictionaries = complete_hint_dictionaries(
        branch_dictionaries,
        dictionaries_dir=dictionaries_dir,
        supported_branches=supported_branches,
    )
    for branch in supported_branches:
        if branch not in visible_sequences_by_branch:
            _source_tags, visible_sequences_by_branch[branch] = (
                collect_corpus_tags_and_visible_sequences(corpus_root, branch)
            )
    concatenated_tag_hints = {
        branch: build_concatenated_tag_hints(
            corpus_root,
            branch,
            hint_dictionaries[branch],
            visible_sequences_by_branch[branch],
        )
        for branch in supported_branches
    }
    outputs[jp_policy_path] = build_jp_policy(
        JpPolicyInputs(
            jp_tags=jp_tags,
            deprecated_tags=deprecated_tags,
            en_tags=en_tags,
            mapping_policy=policy,
            concatenated_tag_hints=concatenated_tag_hints,
        )
    )
    return BuildArtifacts(
        outputs=outputs,
        branch_summaries=tuple(summaries),
        jp_tag_count=len(jp_tags),
        hint_count=sum(
            len(entries) for entries in concatenated_tag_hints.values()
        ),
    )


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
    required_data = (
        DATA_EN,
        DATA_JP,
        DATA_DEPRECATED,
        DATA_INT_CROSSWALK,
        DATA_KO_CROSSWALK,
        DATA_BRANCH_GUIDE_CROSSWALK,
    )
    if any(not path.exists() for path in required_data):
        print("エラー: 先に python scripts/parse_sources.py を実行してください。")
        sys.exit(1)

    branches = [
        branch
        for branch in (args.branches or SUPPORTED_BRANCHES)
        if branch != "jp" and not branch.startswith("_")
    ]
    if not branches:
        print("エラー: 生成対象の支部が見つかりません。")
        sys.exit(1)

    try:
        en_tags = cast(list[EnTag], load_json(DATA_EN))
        jp_tags = cast(list[JpTag], load_json(DATA_JP))
        deprecated_tags = cast(
            list[DeprecatedTag],
            load_json(DATA_DEPRECATED),
        )
        policy = build_mapping_policy(jp_tags, deprecated_tags)
        artifacts = build_artifacts(
            corpus_root,
            branches,
            en_tags,
            jp_tags,
            deprecated_tags,
            policy,
        )
        publish_files_atomically({
            path: (lambda temporary, data=data: write_json(temporary, data))
            for path, data in artifacts.outputs.items()
        })
    except (OSError, ValueError) as err:
        print(f"エラー: 辞書生成に失敗しました: {err}")
        sys.exit(1)

    for summary in artifacts.branch_summaries:
        print(
            f"{summary.branch}: {summary.mapped_count}/{summary.tag_count} mapped, "
            f"{summary.replacement_count} replacements -> "
            f"{summary.dictionary_path}"
        )
    print(f"jp policy: {artifacts.jp_tag_count} tags -> {JP_POLICY_PATH}")
    print(f"concatenated tag hints: {artifacts.hint_count}")


if __name__ == "__main__":
    main()
