"""Runtime validation for parsed tag-record boundaries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from scripts.domain.tag_models import (
    CLASSIFICATION_STATUSES,
    COVERAGE_TRANSLATION_ACTIONS,
    SPECIAL_TRANSLATION_ACTIONS,
    Coverage,
    DeprecatedTag,
    EnTag,
    JpTag,
)


def _ensure_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        sample = ", ".join(sorted(duplicates)[:10])
        raise ValueError(f"{label} が重複しています: {sample}")


def validate_en_tags(raw: object) -> list[EnTag]:
    """Validate and narrow one canonical EN tag-record array."""
    if not isinstance(raw, list):
        raise ValueError("ENタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"ENタグデータの項目が不正です: index={index}")
        name = entry["name"]
        if not name or name != name.strip():
            raise ValueError(f"ENタグ名が不正です: {name!r}")
        category = entry.get("category")
        if category is not None and not isinstance(category, str):
            raise ValueError(f"ENタグのcategoryが不正です: {category!r}")
        description = entry.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(f"ENタグのdescriptionが不正です: {description!r}")
        meta = entry.get("meta")
        if meta is not None and (
            not isinstance(meta, dict)
            or any(
                not isinstance(key, str)
                or not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                for key, values in meta.items()
            )
        ):
            raise ValueError(f"ENタグのmetaが不正です: {meta!r}")

    records = cast(list[EnTag], raw)
    _ensure_unique((entry["name"] for entry in records), "ENタグ名")
    return records


def validate_jp_tags(raw: object) -> list[JpTag]:
    """Validate and narrow one canonical JP tag-record array."""
    if not isinstance(raw, list):
        raise ValueError("JPタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"JPタグデータの項目が不正です: index={index}")
        name = entry["name"]
        if not name or name != name.strip():
            raise ValueError(f"JPタグ名が不正です: {name!r}")
        if "en_tag" in entry:
            raise ValueError(f"JPタグデータに旧en_tagがあります: index={index}")
        source_tags = entry.get("source_tags")
        if (
            not isinstance(source_tags, list)
            or any(
                not isinstance(value, str)
                or not value
                or value != value.strip()
                for value in source_tags
            )
        ):
            raise ValueError(f"JP側source_tagsが不正です: {source_tags!r}")
        description = entry.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(f"JPタグのdescriptionが不正です: {description!r}")
        for key in (
            "use_restricted",
            "edit_restricted",
            "translation_exempt",
        ):
            value = entry.get(key)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"JPタグの{key}が不正です: {value!r}")

    records = cast(list[JpTag], raw)
    _ensure_unique((entry["name"] for entry in records), "JPタグ名")
    _ensure_unique(
        (source_tag for entry in records for source_tag in entry["source_tags"]),
        "JP側source_tags",
    )
    return records


def validate_deprecated_tags(
    raw: object,
    jp_tags: list[JpTag] | None = None,
) -> list[DeprecatedTag]:
    """Validate and narrow one canonical deprecated tag-record array."""
    if not isinstance(raw, list):
        raise ValueError("非使用タグデータは配列である必要があります")
    jp_names = {entry["name"] for entry in jp_tags or []}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"非使用タグデータの項目が不正です: index={index}")
        if "en_tag" in entry:
            raise ValueError(f"非使用タグデータに旧en_tagがあります: index={index}")
        source_tag = entry.get("source_tag")
        if (
            not isinstance(source_tag, str)
            or not source_tag
            or source_tag != source_tag.strip()
        ):
            raise ValueError(f"非使用タグのsource_tagが不正です: {source_tag!r}")
        source_lang = entry.get("source_lang")
        if "source_lang" in entry and (
            not isinstance(source_lang, str)
            or not source_lang
            or source_lang != source_lang.strip()
        ):
            raise ValueError(f"非使用タグのsource_langが不正です: {source_lang!r}")
        replacement = entry.get("replacement")
        if replacement is not None and (
            not isinstance(replacement, str)
            or not replacement
            or replacement != replacement.strip()
        ):
            raise ValueError(f"非使用タグのreplacementが不正です: {replacement!r}")
        if (
            replacement is not None
            and (source_lang or "EN") == "EN"
            and jp_tags is not None
            and replacement not in jp_names
        ):
            raise ValueError(
                f"非使用タグのreplacementがJPタグに存在しません: {replacement!r}"
            )
        description = entry.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(f"非使用タグのdescriptionが不正です: {description!r}")

    records = cast(list[DeprecatedTag], raw)
    _ensure_unique(
        (
            entry["source_tag"]
            for entry in records
            if (entry.get("source_lang") or "EN") == "EN"
        ),
        "EN非使用タグ",
    )
    return records


def validate_tag_records(
    en_raw: object,
    jp_raw: object,
    deprecated_raw: object | None = None,
) -> tuple[list[EnTag], list[JpTag], list[DeprecatedTag]]:
    """Validate the persisted record families consumed by tag builders."""
    en_tags = validate_en_tags(en_raw)
    jp_tags = validate_jp_tags(jp_raw)
    deprecated_tags = (
        validate_deprecated_tags(deprecated_raw, jp_tags)
        if deprecated_raw is not None
        else []
    )
    return en_tags, jp_tags, deprecated_tags


def _validate_description_map(
    value: object,
    expected_keys: frozenset[str],
    context: str,
) -> None:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError(f"{context} must map strings to strings")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        raise ValueError(f"{context} keys do not match the protocol")


def _valid_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_jp_policy(value: object, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{context}.target_policy must be an object or null")
    for key in (
        "use_restricted",
        "edit_restricted",
        "translation_exempt",
        "copy_allowed_for_translation",
    ):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{context}.target_policy.{key} must be boolean")
    action = value.get("special_translation_action")
    if action is not None and action not in SPECIAL_TRANSLATION_ACTIONS:
        raise ValueError(
            f"{context}.target_policy.special_translation_action is invalid"
        )


def _validate_coverage_tag(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    if not isinstance(value.get("tag"), str):
        raise ValueError(f"{context}.tag must be a string")
    if value.get("status") not in CLASSIFICATION_STATUSES:
        raise ValueError(f"{context}.status is unknown")
    if value.get("translation_action") not in COVERAGE_TRANSLATION_ACTIONS:
        raise ValueError(f"{context}.translation_action is unknown")
    for key in ("jp_list_handled", "translator_handled", "copy_allowed"):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{context}.{key} must be boolean")
    for key in ("jp_tag", "replacement", "display_tag"):
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            raise ValueError(f"{context}.{key} must be a string or null")
    for key in ("rank", "page_count"):
        if not _valid_nonnegative_int(value.get(key)):
            raise ValueError(f"{context}.{key} must be a non-negative integer")
    sample_slugs = value.get("sample_slugs")
    if not isinstance(sample_slugs, list) or any(
        not isinstance(slug, str) for slug in sample_slugs
    ):
        raise ValueError(f"{context}.sample_slugs must be a string array")
    _validate_jp_policy(value.get("target_policy"), context)


def validate_coverage(raw: object) -> Coverage:
    """Validate and narrow one generated branch-coverage document."""
    if not isinstance(raw, dict):
        raise ValueError("coverage root must be an object")
    if not _valid_nonnegative_int(raw.get("schema_version")):
        raise ValueError("coverage.schema_version must be a non-negative integer")
    source = raw.get("source")
    if not isinstance(source, dict):
        raise ValueError("coverage.source must be an object")
    for key in (
        "corpus_root",
        "jp_tag_source",
        "jp_unused_source",
        "override_source",
        "deprecated_override_source",
        "crosswalk_source",
    ):
        if not isinstance(source.get(key), str):
            raise ValueError(f"coverage.source.{key} must be a string")
    _validate_description_map(
        raw.get("status_descriptions"),
        CLASSIFICATION_STATUSES,
        "coverage.status_descriptions",
    )
    _validate_description_map(
        raw.get("action_descriptions"),
        COVERAGE_TRANSLATION_ACTIONS,
        "coverage.action_descriptions",
    )
    branches = raw.get("branches")
    if not isinstance(branches, list):
        raise ValueError("coverage.branches must be an array")
    for branch_index, branch in enumerate(branches):
        context = f"coverage.branches[{branch_index}]"
        if not isinstance(branch, dict):
            raise ValueError(f"{context} must be an object")
        for key in ("branch", "site"):
            if not isinstance(branch.get(key), str):
                raise ValueError(f"{context}.{key} must be a string")
        for key in ("page_count", "tag_count"):
            if not _valid_nonnegative_int(branch.get(key)):
                raise ValueError(f"{context}.{key} must be a non-negative integer")
        status_counts = branch.get("status_counts")
        if not isinstance(status_counts, dict) or any(
            key not in CLASSIFICATION_STATUSES or not _valid_nonnegative_int(count)
            for key, count in status_counts.items()
        ):
            raise ValueError(f"{context}.status_counts is invalid")
        tags = branch.get("tags")
        if not isinstance(tags, list):
            raise ValueError(f"{context}.tags must be an array")
        for tag_index, tag in enumerate(tags):
            _validate_coverage_tag(tag, f"{context}.tags[{tag_index}]")
        if branch["tag_count"] != len(tags):
            raise ValueError(f"{context}.tag_count does not match tags")
    return cast(Coverage, raw)
