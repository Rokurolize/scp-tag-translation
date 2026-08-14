"""Shared branch dictionary construction from validated tag policy data."""

from __future__ import annotations

from scripts.domain.records.tag_records import DeprecatedTag, EnTag, JpTag
from scripts.domain.policy.tag_policy import (
    EN_ORIGIN_TAG_REPLACEMENTS,
    MappingPolicy,
    en_category_omitted_tags,
    is_deprecated_for_en_source,
    resolve_source_tag,
)

__all__ = ["build_branch_dict", "build_en_dicts"]


def build_branch_dict(
    branch: str,
    source_tags: set[str],
    policy: MappingPolicy,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Build branch dictionaries from source tags and policy; policy conflicts propagate."""
    branch_policy = policy.for_branch(branch)
    all_source_tags = (
        set(source_tags)
        | set(branch_policy.deprecated_tags)
        | set(branch_policy.overrides)
        | set(branch_policy.official_crosswalk)
    )
    dictionary = {
        source_tag: resolve_source_tag(
            source_tag,
            policy,
            branch_policy,
        ).target
        for source_tag in sorted(all_source_tags)
    }
    concrete_replacements = {
        source_tag: replacement
        for source_tag, replacement in branch_policy.replacements.items()
        if replacement is not None
    }
    return dictionary, dict(sorted(concrete_replacements.items()))


def build_en_dicts(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    deprecated_raw: list[DeprecatedTag],
    corpus_tags: set[str],
    policy: MappingPolicy,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Build EN dictionaries from records and policy; policy conflicts propagate."""
    branch_policy = policy.for_branch("en")
    deprecated_en_tags = {
        entry["source_tag"]
        for entry in deprecated_raw
        if is_deprecated_for_en_source(entry)
    }
    deprecated_en_tags.update(branch_policy.deprecated_tags)
    category_omitted_tags = en_category_omitted_tags(
        en_tags,
        jp_tags,
        set(branch_policy.overrides),
    )
    all_source_tags = (
        {entry["name"] for entry in en_tags}
        | corpus_tags
        | deprecated_en_tags
        | set(branch_policy.overrides)
        | set(branch_policy.official_crosswalk)
    )
    origin_replacements = {
        source_tag: replacement
        for source_tag, replacement in EN_ORIGIN_TAG_REPLACEMENTS.items()
        if source_tag in all_source_tags
    }
    deprecated_en_tags.update(category_omitted_tags)
    deprecated_en_tags.update(origin_replacements)
    all_source_tags.update(deprecated_en_tags)
    dictionary = {
        source_tag: resolve_source_tag(
            source_tag,
            policy,
            branch_policy,
            deprecated_tags=deprecated_en_tags,
        ).target
        for source_tag in sorted(all_source_tags)
    }
    deprecated_dict = {
        source_tag: replacement
        for source_tag, replacement in branch_policy.replacements.items()
        if replacement is not None
    }
    deprecated_dict.update(origin_replacements)
    return dict(sorted(dictionary.items())), dict(sorted(deprecated_dict.items()))
