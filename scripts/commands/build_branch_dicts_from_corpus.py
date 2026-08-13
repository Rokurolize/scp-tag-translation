#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.atomic_output import publish_files_atomically
from scripts.corpus import (
    CorpusBranchData,
    collect_corpus_branch_data,
)
from scripts.dictionary_inputs import (
    complete_hint_dictionaries,
    load_mapping_policy_inputs,
)
from scripts.json_io import load_json, write_json
from scripts.data_paths import (
    DATA_BRANCH_GUIDE_CROSSWALK,
    DATA_DEPRECATED,
    DATA_EN,
    DATA_INT_CROSSWALK,
    DATA_JP,
    DATA_KO_CROSSWALK,
    DICTIONARIES_DIR,
    JP_POLICY_PATH,
)
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.concatenated_tags import (
    build_concatenated_tag_hints,
)
from scripts.domain.jp_policy import JpPolicyInputs, build_jp_policy
from scripts.domain.policy_builder import build_mapping_policy
from scripts.domain.tag_dictionary import build_branch_dict, build_en_dicts
from scripts.domain.tag_records import DeprecatedTag, EnTag, JpTag
from scripts.domain.tag_policy import (
    MappingPolicy,
)
from scripts.domain.tag_validation import validate_tag_records

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


@dataclass(frozen=True)
class BranchBuildInputs:
    en_tags: list[EnTag]
    jp_tags: list[JpTag]
    deprecated_tags: list[DeprecatedTag]
    policy: MappingPolicy


@dataclass(frozen=True)
class BranchBuildConfig:
    """Output and branch settings for one dictionary build."""

    dictionaries_dir: Path = DICTIONARIES_DIR
    jp_policy_path: Path = JP_POLICY_PATH
    supported_branches: tuple[str, ...] = SUPPORTED_BRANCHES


def build_artifacts(
    corpus_data: Mapping[str, CorpusBranchData],
    branches: Sequence[str],
    inputs: BranchBuildInputs,
    *,
    config: BranchBuildConfig = BranchBuildConfig(),
) -> BuildArtifacts:
    required_branches = set(branches) | set(config.supported_branches)
    missing_branches = sorted(required_branches - set(corpus_data))
    if missing_branches:
        raise ValueError(
            "corpus data missing required branches: "
            + ", ".join(missing_branches)
        )
    validate_tag_records(
        inputs.en_tags,
        inputs.jp_tags,
        inputs.deprecated_tags,
    )
    outputs: dict[Path, Mapping[str, object]] = {}
    summaries = []
    branch_dictionaries: dict[str, dict[str, str | None]] = {}
    visible_sequences_by_branch: dict[
        str,
        list[tuple[str, tuple[str, ...]]],
    ] = {}

    for branch in sorted(branches):
        branch_data = corpus_data[branch]
        source_tags = branch_data.source_tags
        visible_sequences = branch_data.visible_sequences
        if branch == "en":
            dictionary, deprecated_dict = build_en_dicts(
                inputs.en_tags,
                inputs.jp_tags,
                inputs.deprecated_tags,
                source_tags,
                inputs.policy,
            )
        else:
            dictionary, deprecated_dict = build_branch_dict(
                branch,
                source_tags,
                inputs.policy,
            )

        dictionary_path = config.dictionaries_dir / f"{branch}_to_jp.json"
        deprecated_path = (
            config.dictionaries_dir / f"deprecated_{branch}_to_jp.json"
        )
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
        dictionaries_dir=config.dictionaries_dir,
        supported_branches=config.supported_branches,
    )
    for branch in config.supported_branches:
        if branch not in visible_sequences_by_branch:
            visible_sequences_by_branch[branch] = corpus_data[branch].visible_sequences
    concatenated_tag_hints = {
        branch: build_concatenated_tag_hints(
            branch,
            hint_dictionaries[branch],
            visible_sequences_by_branch[branch],
        )
        for branch in config.supported_branches
    }
    outputs[config.jp_policy_path] = build_jp_policy(
        JpPolicyInputs(
            jp_tags=inputs.jp_tags,
            deprecated_tags=inputs.deprecated_tags,
            en_tags=inputs.en_tags,
            mapping_policy=inputs.policy,
            concatenated_tag_hints=concatenated_tag_hints,
        )
    )
    return BuildArtifacts(
        outputs=outputs,
        branch_summaries=tuple(summaries),
        jp_tag_count=len(inputs.jp_tags),
        hint_count=sum(
            len(entries) for entries in concatenated_tag_hints.values()
        ),
    )


def build_and_publish(
    corpus_root: Path,
    branches: Sequence[str],
    *,
    config: BranchBuildConfig = BranchBuildConfig(),
) -> BuildArtifacts:
    """Load validated inputs, build dictionaries, and publish them atomically."""
    required_data = (
        DATA_EN,
        DATA_JP,
        DATA_DEPRECATED,
        DATA_INT_CROSSWALK,
        DATA_KO_CROSSWALK,
        DATA_BRANCH_GUIDE_CROSSWALK,
    )
    if any(not path.exists() for path in required_data):
        raise FileNotFoundError(
            "先に python -m scripts.commands.parse_sources を実行してください。"
        )

    en_tags, jp_tags, deprecated_tags = validate_tag_records(
        load_json(DATA_EN),
        load_json(DATA_JP),
        load_json(DATA_DEPRECATED),
    )
    policy = build_mapping_policy(
        jp_tags,
        deprecated_tags,
        load_mapping_policy_inputs(),
    )
    required_branches = set(branches) | set(config.supported_branches)
    corpus_data = {
        branch: collect_corpus_branch_data(corpus_root, branch)
        for branch in sorted(required_branches)
    }
    artifacts = build_artifacts(
        corpus_data,
        branches,
        BranchBuildInputs(
            en_tags=en_tags,
            jp_tags=jp_tags,
            deprecated_tags=deprecated_tags,
            policy=policy,
        ),
        config=config,
    )
    publish_files_atomically({
        path: (
            lambda temporary, data=data: write_json(
                temporary,
                data,
                sort_top_level=True,
            )
        )
        for path, data in artifacts.outputs.items()
    })
    return artifacts


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
    branches = [
        branch
        for branch in (args.branches or SUPPORTED_BRANCHES)
        if branch != "jp" and not branch.startswith("_")
    ]
    if not branches:
        print("エラー: 生成対象の支部が見つかりません。")
        sys.exit(1)

    try:
        artifacts = build_and_publish(corpus_root, branches)
    except (FileNotFoundError, OSError, ValueError) as err:
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
