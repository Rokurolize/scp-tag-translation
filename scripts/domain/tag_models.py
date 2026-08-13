"""Compatibility exports for the split domain model modules.

New code should import records from ``tag_records``, policy vocabulary from
``tag_policy_models``, and generated artifacts from ``tag_coverage_models``.
"""

from scripts.domain.tag_coverage_models import (
    ApplicationBranch,
    ApplicationInventory,
    ApplicationTag,
    BranchTagStats,
    Classification,
    Coverage,
    CoverageBranch,
    CoverageSource,
    CoverageTag,
    TagStats,
)
from scripts.domain.tag_policy_models import (
    CLASSIFICATION_STATUSES,
    COVERAGE_TRANSLATION_ACTIONS,
    SOURCE_TRANSLATION_ACTIONS,
    SPECIAL_TRANSLATION_ACTIONS,
    ClassificationStatus,
    CoverageTranslationAction,
    JpPolicyDocument,
    JpTagPolicy,
    SourceTagPolicy,
    SourceTranslationAction,
    SpecialTranslationAction,
)
from scripts.domain.tag_records import (
    BranchOverrideFile,
    BranchOverrideRecord,
    BranchOverrideValue,
    DeprecatedTag,
    EnTag,
    JpTag,
    OfficialCrosswalkFile,
    ReplacementOverrideFile,
)

__all__ = [
    "ApplicationBranch",
    "ApplicationInventory",
    "ApplicationTag",
    "BranchOverrideFile",
    "BranchOverrideRecord",
    "BranchOverrideValue",
    "BranchTagStats",
    "CLASSIFICATION_STATUSES",
    "Classification",
    "ClassificationStatus",
    "COVERAGE_TRANSLATION_ACTIONS",
    "Coverage",
    "CoverageBranch",
    "CoverageSource",
    "CoverageTag",
    "CoverageTranslationAction",
    "DeprecatedTag",
    "EnTag",
    "JpPolicyDocument",
    "JpTag",
    "JpTagPolicy",
    "OfficialCrosswalkFile",
    "ReplacementOverrideFile",
    "SOURCE_TRANSLATION_ACTIONS",
    "SPECIAL_TRANSLATION_ACTIONS",
    "SourceTagPolicy",
    "SourceTranslationAction",
    "SpecialTranslationAction",
    "TagStats",
]
