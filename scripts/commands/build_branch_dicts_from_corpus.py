#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.pipeline.corpus import (
    CorpusBranchData,
    collect_corpus_branch_data,
)
from scripts.pipeline.dictionary_inputs import (
    LoadedMappingInputs,
    MappingInputPaths,
    default_mapping_input_paths,
    load_existing_hint_dictionaries,
    load_mapping_inputs,
)
from scripts.infrastructure.json_io import write_json
from scripts.infrastructure.data_paths import DICTIONARIES_DIR
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.concatenated_tags import (
    build_concatenated_tag_hints,
)
from scripts.domain.jp_policy import JpPolicyInputs, build_jp_policy
from scripts.domain.tag_dictionary import build_branch_dict, build_en_dicts

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
class BranchBuildConfig:
    """Input, output, and branch settings for one dictionary build."""

    dictionaries_dir: Path = DICTIONARIES_DIR
    jp_policy_path: Path = DICTIONARIES_DIR / "jp_tag_policy.json"
    supported_branches: tuple[str, ...] = SUPPORTED_BRANCHES
    mapping_inputs: MappingInputPaths = field(
        default_factory=default_mapping_input_paths,
    )


def _build_branch_artifacts(
    corpus_data: Mapping[str, CorpusBranchData],
    branches: Sequence[str],
    inputs: LoadedMappingInputs,
    config: BranchBuildConfig,
) -> tuple[
    dict[Path, Mapping[str, object]],
    tuple[BranchBuildSummary, ...],
    dict[str, dict[str, str | None]],
]:
    outputs: dict[Path, Mapping[str, object]] = {}
    summaries: list[BranchBuildSummary] = []
    branch_dictionaries: dict[str, dict[str, str | None]] = {}
    for branch in sorted(branches):
        branch_data = corpus_data[branch]
        if branch == "en":
            dictionary, deprecated_dict = build_en_dicts(
                inputs.en_tags,
                inputs.jp_tags,
                inputs.deprecated_tags,
                branch_data.source_tags,
                inputs.mapping_policy,
            )
        else:
            dictionary, deprecated_dict = build_branch_dict(
                branch,
                branch_data.source_tags,
                inputs.mapping_policy,
            )

        dictionary_path = config.dictionaries_dir / f"{branch}_to_jp.json"
        deprecated_path = config.dictionaries_dir / f"deprecated_{branch}_to_jp.json"
        outputs[dictionary_path] = dictionary
        outputs[deprecated_path] = deprecated_dict
        branch_dictionaries[branch] = dictionary
        summaries.append(
            BranchBuildSummary(
                branch=branch,
                mapped_count=sum(value is not None for value in dictionary.values()),
                tag_count=len(dictionary),
                replacement_count=len(deprecated_dict),
                dictionary_path=dictionary_path,
            )
        )
    return (
        outputs,
        tuple(summaries),
        branch_dictionaries,
    )


def _merge_existing_hint_dictionaries(
    branch_dictionaries: Mapping[str, Mapping[str, str | None]],
    corpus_data: Mapping[str, CorpusBranchData],
    config: BranchBuildConfig,
    existing_dictionaries: Mapping[str, Mapping[str, str | None]] | None,
) -> tuple[
    dict[str, dict[str, str | None]],
    dict[str, list[tuple[str, tuple[str, ...]]]],
]:
    hint_dictionaries = {
        branch: dict(dictionary)
        for branch, dictionary in branch_dictionaries.items()
    }
    for branch in config.supported_branches:
        if branch in hint_dictionaries:
            continue
        if existing_dictionaries is None or branch not in existing_dictionaries:
            raise ValueError(
                "explicit existing dictionary required for partial hint generation: "
                f"{branch}"
            )
        hint_dictionaries[branch] = dict(existing_dictionaries[branch])
    visible_sequences_by_branch = {
        branch: corpus_data[branch].visible_sequences
        for branch in config.supported_branches
    }
    return hint_dictionaries, visible_sequences_by_branch


def build_artifacts(
    corpus_data: Mapping[str, CorpusBranchData],
    branches: Sequence[str],
    inputs: LoadedMappingInputs,
    *,
    config: BranchBuildConfig = BranchBuildConfig(),
    existing_dictionaries: Mapping[str, Mapping[str, str | None]] | None = None,
) -> BuildArtifacts:
    required_branches = set(branches) | set(config.supported_branches)
    missing_branches = sorted(required_branches - set(corpus_data))
    if missing_branches:
        raise ValueError(
            "corpus data missing required branches: "
            + ", ".join(missing_branches)
        )
    (
        outputs,
        summaries,
        branch_dictionaries,
    ) = _build_branch_artifacts(corpus_data, branches, inputs, config)
    hint_dictionaries, visible_sequences_by_branch = _merge_existing_hint_dictionaries(
        branch_dictionaries,
        corpus_data,
        config,
        existing_dictionaries,
    )
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
            mapping_policy=inputs.mapping_policy,
            concatenated_tag_hints=concatenated_tag_hints,
        )
    )
    return BuildArtifacts(
        outputs=outputs,
        branch_summaries=summaries,
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
    loaded = load_mapping_inputs(
        config.mapping_inputs,
        require_complete_inputs=True,
    )
    required_branches = set(branches) | set(config.supported_branches)
    corpus_data = {
        branch: collect_corpus_branch_data(corpus_root, branch)
        for branch in sorted(required_branches)
    }
    omitted_branches = tuple(
        branch
        for branch in config.supported_branches
        if branch not in branches
    )
    existing_dictionaries = load_existing_hint_dictionaries(
        {},
        dictionaries_dir=config.dictionaries_dir,
        supported_branches=omitted_branches,
    )
    artifacts = build_artifacts(
        corpus_data,
        branches,
        loaded,
        config=config,
        existing_dictionaries=existing_dictionaries,
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

    config = BranchBuildConfig()
    try:
        artifacts = build_and_publish(corpus_root, branches, config=config)
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


if __name__ == "__main__":
    main()
