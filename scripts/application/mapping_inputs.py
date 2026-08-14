"""Compose validated persisted records into workflow mapping contexts."""

from __future__ import annotations

from scripts.domain.policy.policy_builder import MappingPolicyInputs, build_mapping_policy
from scripts.domain.tag_coverage import CoverageInputs
from scripts.pipeline import dictionary_inputs as pipeline_inputs

MappingInputPaths = pipeline_inputs.MappingInputPaths
LoadedMappingInputs = pipeline_inputs.LoadedMappingInputs
default_mapping_input_paths = pipeline_inputs.default_mapping_input_paths
complete_hint_dictionaries_from_existing = (
    pipeline_inputs.complete_hint_dictionaries_from_existing
)


def load_mapping_inputs(
    paths: MappingInputPaths | None = None,
    *,
    policy_inputs: MappingPolicyInputs | None = None,
    include_origin_replacements: bool = True,
    require_complete_inputs: bool = False,
) -> LoadedMappingInputs:
    """Load records and compose policy, raising file or domain input errors on failure."""
    paths = paths or default_mapping_input_paths()
    records = pipeline_inputs.load_tag_records(
        paths,
        require_complete_inputs=require_complete_inputs,
    )
    policy = policy_inputs or pipeline_inputs.load_mapping_policy_inputs(paths)
    return LoadedMappingInputs(
        en_tags=records.en_tags,
        jp_tags=records.jp_tags,
        deprecated_tags=records.deprecated_tags,
        mapping_policy=build_mapping_policy(
            records.jp_tags,
            records.deprecated_tags,
            policy,
            include_origin_replacements=include_origin_replacements,
        ),
    )


def to_coverage_inputs(loaded: LoadedMappingInputs) -> CoverageInputs:
    """Project a shared mapping context into the coverage domain contract."""
    return CoverageInputs(
        en_tags=loaded.en_tags,
        jp_tags=loaded.jp_tags,
        deprecated_tags=loaded.deprecated_tags,
        mapping_policy=loaded.mapping_policy,
    )


__all__ = [
    "LoadedMappingInputs",
    "MappingInputPaths",
    "default_mapping_input_paths",
    "complete_hint_dictionaries_from_existing",
    "load_mapping_inputs",
    "to_coverage_inputs",
]
