"""Build and publish branch dictionaries from corpus metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.domain.branch_config import (
    SUPPORTED_BRANCHES,
    validate_requested_branches,
)
from scripts.domain.concatenated_tags import build_concatenated_tag_hints
from scripts.domain.errors import InvalidDomainInputError
from scripts.domain.policy.jp_policy import JpPolicyInputs, build_jp_policy
from scripts.domain.policy.tag_policy_models import JpPolicyDocument
from scripts.domain.tag_dictionary import build_branch_dict, build_en_dicts
from scripts.infrastructure.atomic_output import FileWriter, publish_files_atomically
from scripts.infrastructure.data_paths import DICTIONARIES_DIR
from scripts.infrastructure.json_io import write_json
from scripts.pipeline.corpus import CorpusBranchData, collect_corpus_branch_data
from scripts.application.mapping_inputs import (
    LoadedMappingInputs,
    MappingInputPaths,
    default_mapping_input_paths,
    complete_hint_dictionaries_from_existing,
    load_mapping_inputs,
)


@dataclass(frozen=True)
class BranchBuildSummary:
    branch: str
    mapped_count: int
    tag_count: int
    replacement_count: int
    dictionary_path: Path


@dataclass(frozen=True)
class BuildArtifacts:
    dictionary_outputs: Mapping[Path, Mapping[str, str | None]]
    policy_path: Path
    policy: JpPolicyDocument
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


def _resolve_build_branch_scope(
    branches: Sequence[str] | None,
    config: BranchBuildConfig,
) -> tuple[tuple[str, ...], set[str]]:
    requested = tuple(config.supported_branches if branches is None else branches)
    selected = validate_requested_branches(
        requested,
        supported_branches=config.supported_branches,
    )
    return selected, set(selected) | set(config.supported_branches)


def _build_branch_artifacts(
    corpus_data: Mapping[str, CorpusBranchData],
    branches: Sequence[str],
    inputs: LoadedMappingInputs,
    config: BranchBuildConfig,
) -> tuple[
    dict[Path, Mapping[str, str | None]],
    tuple[BranchBuildSummary, ...],
    dict[str, dict[str, str | None]],
]:
    outputs: dict[Path, Mapping[str, str | None]] = {}
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
    return outputs, tuple(summaries), branch_dictionaries


def _merge_hint_dictionaries_and_sequences(
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
            raise InvalidDomainInputError(
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
    config: BranchBuildConfig | None = None,
    existing_dictionaries: Mapping[str, Mapping[str, str | None]] | None = None,
) -> BuildArtifacts:
    """Assemble dictionary and policy artifacts without publishing them."""
    config = config or BranchBuildConfig()
    branches, required_branches = _resolve_build_branch_scope(branches, config)
    return _build_artifacts_for_scope(
        corpus_data,
        branches,
        required_branches,
        inputs,
        config,
        existing_dictionaries,
    )


def _build_artifacts_for_scope(
    corpus_data: Mapping[str, CorpusBranchData],
    branches: Sequence[str],
    required_branches: set[str],
    inputs: LoadedMappingInputs,
    config: BranchBuildConfig,
    existing_dictionaries: Mapping[str, Mapping[str, str | None]] | None,
) -> BuildArtifacts:
    """Assemble artifacts after the outer workflow resolved branch scope."""
    missing_branches = sorted(required_branches - set(corpus_data))
    if missing_branches:
        raise InvalidDomainInputError(
            "corpus data missing required branches: "
            + ", ".join(missing_branches)
        )
    outputs, summaries, branch_dictionaries = _build_branch_artifacts(
        corpus_data,
        branches,
        inputs,
        config,
    )
    hint_dictionaries, visible_sequences_by_branch = _merge_hint_dictionaries_and_sequences(
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
    policy = build_jp_policy(
        JpPolicyInputs(
            jp_tags=inputs.jp_tags,
            deprecated_tags=inputs.deprecated_tags,
            en_tags=inputs.en_tags,
            mapping_policy=inputs.mapping_policy,
            concatenated_tag_hints=concatenated_tag_hints,
        )
    )
    return BuildArtifacts(
        dictionary_outputs=outputs,
        policy_path=config.jp_policy_path,
        policy=policy,
        branch_summaries=summaries,
        jp_tag_count=len(inputs.jp_tags),
        hint_count=sum(len(entries) for entries in concatenated_tag_hints.values()),
    )


def build_and_publish_dictionaries(
    corpus_root: Path,
    branches: Sequence[str] | None,
    *,
    config: BranchBuildConfig | None = None,
) -> BuildArtifacts:
    """Load validated inputs, build dictionaries, and publish them atomically."""
    config = config or BranchBuildConfig()
    branches, required_branches = _resolve_build_branch_scope(branches, config)
    loaded = load_mapping_inputs(
        config.mapping_inputs,
        require_complete_inputs=True,
    )
    corpus_data = {
        branch: collect_corpus_branch_data(corpus_root, branch)
        for branch in sorted(required_branches)
    }
    omitted_branches = tuple(
        branch
        for branch in config.supported_branches
        if branch not in branches
    )
    existing_dictionaries = complete_hint_dictionaries_from_existing(
        {},
        dictionaries_dir=config.dictionaries_dir,
        supported_branches=omitted_branches,
    )
    artifacts = _build_artifacts_for_scope(
        corpus_data,
        branches,
        required_branches,
        loaded,
        config,
        existing_dictionaries=existing_dictionaries,
    )
    writers: dict[Path, FileWriter] = {}
    for path, data in artifacts.dictionary_outputs.items():
        writers[path] = lambda temporary, data=data: write_json(
            temporary,
            data,
            sort_top_level=True,
        )
    writers[artifacts.policy_path] = lambda temporary: write_json(
        temporary,
        artifacts.policy,
        sort_top_level=True,
    )
    publish_files_atomically(writers)
    return artifacts


__all__ = [
    "BranchBuildConfig",
    "BranchBuildSummary",
    "BuildArtifacts",
    "build_and_publish_dictionaries",
    "build_artifacts",
]
