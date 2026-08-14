"""Typed policy records and vocabulary for source-to-JP translation."""

from __future__ import annotations

from typing import Literal, TypedDict

__all__ = [
    "CLASSIFICATION_STATUSES",
    "COVERAGE_TRANSLATION_ACTIONS",
    "ClassificationStatus",
    "CoverageTranslationAction",
    "JpPolicyDocument",
    "JpTagPolicy",
    "SOURCE_TRANSLATION_ACTIONS",
    "SPECIAL_TRANSLATION_ACTIONS",
    "SourceTagPolicy",
    "SourceTranslationAction",
    "SpecialTranslationAction",
]


ClassificationStatus = Literal[
    "jp_unused_replacement",
    "jp_unused_no_single_replacement",
    "jp_translation_policy_omit",
    "jp_tag_name",
    "jp_tag_alias",
    "curated_override_only",
    "official_crosswalk",
    "unhandled",
]
SourceTranslationAction = Literal[
    "omit_jp_unused",
    "omit_translation_policy",
]
CoverageTranslationAction = Literal[
    "copy",
    "copy_replacement",
    "omit_jp_policy",
    "omit_jp_unused",
    "omit_translation_policy",
    "staff_permission_required",
    "tag_application_required",
]
SpecialTranslationAction = Literal["staff_permission_required", "omit"]

CLASSIFICATION_STATUSES: frozenset[ClassificationStatus] = frozenset({
    "jp_unused_replacement",
    "jp_unused_no_single_replacement",
    "jp_translation_policy_omit",
    "jp_tag_name",
    "jp_tag_alias",
    "curated_override_only",
    "official_crosswalk",
    "unhandled",
})
SOURCE_TRANSLATION_ACTIONS: frozenset[SourceTranslationAction] = frozenset({
    "omit_jp_unused",
    "omit_translation_policy",
})
COVERAGE_TRANSLATION_ACTIONS: frozenset[CoverageTranslationAction] = frozenset({
    "copy",
    "copy_replacement",
    "omit_jp_policy",
    "omit_jp_unused",
    "omit_translation_policy",
    "staff_permission_required",
    "tag_application_required",
})
SPECIAL_TRANSLATION_ACTIONS: frozenset[SpecialTranslationAction] = frozenset({
    "staff_permission_required",
    "omit",
})


class JpTagPolicy(TypedDict):
    use_restricted: bool
    edit_restricted: bool
    translation_exempt: bool
    special_translation_action: SpecialTranslationAction | None
    copy_allowed_for_translation: bool


class SourceTagPolicy(TypedDict):
    translation_action: SourceTranslationAction
    reason: str


class JpPolicyDocument(TypedDict):
    schema_version: int
    source: str
    tags: dict[str, JpTagPolicy]
    source_tags: dict[str, dict[str, SourceTagPolicy]]
    concatenated_tag_hints: dict[str, dict[str, list[str]]]
