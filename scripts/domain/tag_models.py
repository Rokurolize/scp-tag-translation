"""Typed records shared by tag dictionary and coverage generators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Required, TypedDict


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


class EnTag(TypedDict, total=False):
    name: Required[str]
    category: str | None
    description: str
    meta: dict[str, list[str]]


class JpTag(TypedDict, total=False):
    name: Required[str]
    description: str
    source_tags: Required[list[str]]
    use_restricted: bool
    edit_restricted: bool
    translation_exempt: bool


class DeprecatedTag(TypedDict, total=False):
    source_lang: str
    source_tag: Required[str]
    replacement: str | None
    description: str


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


class TagStats(TypedDict):
    page_count: int
    sample_slugs: list[str]


class Classification(TypedDict):
    status: ClassificationStatus
    recognized_by_jp_policy: bool
    jp_tag: str | None
    replacement: str | None
    translation_action: CoverageTranslationAction
    copy_allowed: bool
    display_tag: str | None
    target_policy: JpTagPolicy | None


class CoverageTag(Classification):
    tag: str
    rank: int
    page_count: int
    sample_slugs: list[str]


class CoverageBranch(TypedDict):
    branch: str
    site: str
    page_count: int
    tag_count: int
    status_counts: dict[ClassificationStatus, int]
    tags: list[CoverageTag]


class CoverageSource(TypedDict):
    corpus_root: str
    jp_tag_source: str
    jp_unused_source: str
    override_source: str
    deprecated_override_source: str
    crosswalk_source: str


class Coverage(TypedDict):
    schema_version: int
    source: CoverageSource
    status_descriptions: Mapping[ClassificationStatus, str]
    action_descriptions: Mapping[CoverageTranslationAction, str]
    branches: list[CoverageBranch]


class ApplicationTag(TypedDict):
    tag: str
    display_tag: str | None
    page_count: int
    sample_slugs: list[str]


class ApplicationBranch(TypedDict):
    branch: str
    site: str
    scanned_page_count: int
    tag_count: int
    tags: list[ApplicationTag]


class ApplicationInventory(TypedDict):
    schema_version: int
    rule: str
    branches: list[ApplicationBranch]
