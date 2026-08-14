"""Project validated mapping records into application-specific contexts."""

from __future__ import annotations

from scripts.domain.tag_coverage import CoverageInputs
from scripts.pipeline.dictionary_inputs import LoadedMappingInputs


def to_coverage_inputs(loaded: LoadedMappingInputs) -> CoverageInputs:
    """Project a shared mapping context into the coverage domain contract."""
    return CoverageInputs(
        en_tags=loaded.en_tags,
        jp_tags=loaded.jp_tags,
        deprecated_tags=loaded.deprecated_tags,
        mapping_policy=loaded.mapping_policy,
    )


__all__ = [
    "to_coverage_inputs",
]
