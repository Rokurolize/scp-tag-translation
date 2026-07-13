"""Typed records shared by tag dictionary and coverage generators."""

from __future__ import annotations

from typing import Required, TypedDict


class EnTag(TypedDict, total=False):
    name: Required[str]
    category: str | None
    description: str
    meta: dict[str, object]


class JpTag(TypedDict, total=False):
    name: Required[str]
    description: str
    source_tags: list[str]
    en_tag: str | None
    use_restricted: bool
    edit_restricted: bool
    translation_exempt: bool


class DeprecatedTag(TypedDict, total=False):
    source_lang: str
    en_tag: Required[str]
    replacement: str | None
    description: str


class JpTagPolicy(TypedDict):
    use_restricted: bool
    edit_restricted: bool
    translation_exempt: bool
    special_translation_action: str | None
    copy_allowed_for_translation: bool


class SourceTagPolicy(TypedDict):
    translation_action: str
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
    status: str
    jp_list_handled: bool
    translator_handled: bool
    jp_tag: str | None
    replacement: str | None
    translation_action: str
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
    status_counts: dict[str, int]
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
    status_descriptions: dict[str, str]
    action_descriptions: dict[str, str]
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
