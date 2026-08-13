"""Typed coverage and browser-facing artifact records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from scripts.domain.policy.tag_policy_models import (
    ClassificationStatus,
    CoverageTranslationAction,
    JpTagPolicy,
)


class TagStats(TypedDict):
    page_count: int
    sample_slugs: list[str]


class BranchTagStats(TypedDict):
    page_count: int
    tags: dict[str, TagStats]


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
