"""Runtime validation for parsed tag-record boundaries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from scripts.domain.tag_coverage_models import Coverage
from scripts.domain.tag_policy_models import (
    CLASSIFICATION_STATUSES,
    COVERAGE_TRANSLATION_ACTIONS,
    SPECIAL_TRANSLATION_ACTIONS,
)
from scripts.domain.tag_records import DeprecatedTag, EnTag, JpTag


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


def _valid_trimmed_string(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _validate_en_meta(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or any(
        not isinstance(key, str)
        or not isinstance(values, list)
        or any(not isinstance(item, str) for item in values)
        for key, values in value.items()
    ):
        raise ValueError(f"ENタグのmetaが不正です: {value!r}")


def _validate_en_tag_entry(entry: object, index: int) -> None:
    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
        raise ValueError(f"ENタグデータの項目が不正です: index={index}")
    name = entry["name"]
    if not _valid_trimmed_string(name):
        raise ValueError(f"ENタグ名が不正です: {name!r}")
    category = entry.get("category")
    if category is not None and not isinstance(category, str):
        raise ValueError(f"ENタグのcategoryが不正です: {category!r}")
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"ENタグのdescriptionが不正です: {description!r}")
    _validate_en_meta(entry.get("meta"))


def validate_en_tags(raw: object) -> list[EnTag]:
    if not isinstance(raw, list):
        raise ValueError("ENタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        _validate_en_tag_entry(entry, index)

    records = cast(list[EnTag], raw)
    _ensure_unique((entry["name"] for entry in records), "ENタグ名")
    return records


def _valid_source_tags(value: object) -> bool:
    return isinstance(value, list) and all(
        _valid_trimmed_string(item) for item in value
    )


def _validate_optional_boolean_fields(
    entry: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        value = entry.get(key)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"{context}{key}が不正です: {value!r}")


def _validate_jp_tag_entry(entry: object, index: int) -> None:
    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
        raise ValueError(f"JPタグデータの項目が不正です: index={index}")
    name = entry["name"]
    if not _valid_trimmed_string(name):
        raise ValueError(f"JPタグ名が不正です: {name!r}")
    if "en_tag" in entry:
        raise ValueError(f"JPタグデータに旧en_tagがあります: index={index}")
    source_tags = entry.get("source_tags")
    if not _valid_source_tags(source_tags):
        raise ValueError(f"JP側source_tagsが不正です: {source_tags!r}")
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"JPタグのdescriptionが不正です: {description!r}")
    _validate_optional_boolean_fields(
        entry,
        ("use_restricted", "edit_restricted", "translation_exempt"),
        "JPタグの",
    )


def validate_jp_tags(raw: object) -> list[JpTag]:
    if not isinstance(raw, list):
        raise ValueError("JPタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        _validate_jp_tag_entry(entry, index)

    records = cast(list[JpTag], raw)
    _ensure_unique((entry["name"] for entry in records), "JPタグ名")
    # A source alias may intentionally occur in multiple JP categories during
    # a tag-system migration.  build_jp_names_and_source_map() resolves those aliases using the
    # explicit mapping policy and rejects unresolved conflicts.
    return records


def _validate_deprecated_replacement(
    entry: dict[object, object],
    jp_names: set[str],
    require_registered_replacement: bool,
) -> None:
    replacement = entry.get("replacement")
    if replacement is not None and not _valid_trimmed_string(replacement):
        raise ValueError(f"非使用タグのreplacementが不正です: {replacement!r}")
    source_lang = entry.get("source_lang")
    if (
        replacement is not None
        and (source_lang or "EN") == "EN"
        and require_registered_replacement
        and replacement not in jp_names
    ):
        raise ValueError(
            f"非使用タグのreplacementがJPタグに存在しません: {replacement!r}"
        )


def _validate_deprecated_tag_entry(
    entry: object,
    index: int,
    jp_names: set[str],
    require_registered_replacement: bool,
) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"非使用タグデータの項目が不正です: index={index}")
    if "en_tag" in entry:
        raise ValueError(f"非使用タグデータに旧en_tagがあります: index={index}")
    source_tag = entry.get("source_tag")
    if not _valid_trimmed_string(source_tag):
        raise ValueError(f"非使用タグのsource_tagが不正です: {source_tag!r}")
    source_lang = entry.get("source_lang")
    if "source_lang" in entry and not _valid_trimmed_string(source_lang):
        raise ValueError(f"非使用タグのsource_langが不正です: {source_lang!r}")
    _validate_deprecated_replacement(
        entry,
        jp_names,
        require_registered_replacement,
    )
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"非使用タグのdescriptionが不正です: {description!r}")


def validate_deprecated_tags(
    raw: object,
    jp_tags: list[JpTag] | None = None,
) -> list[DeprecatedTag]:
    if not isinstance(raw, list):
        raise ValueError("非使用タグデータは配列である必要があります")
    jp_names = {entry["name"] for entry in jp_tags or []}
    for index, entry in enumerate(raw):
        _validate_deprecated_tag_entry(
            entry,
            index,
            jp_names,
            jp_tags is not None,
        )

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


def _require_keys(
    value: dict[object, object],
    required: tuple[str, ...],
    context: str,
) -> None:
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(f"{context} missing required keys: {', '.join(missing)}")


def _validate_required_string_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not isinstance(value.get(key), str):
            raise ValueError(f"{context}.{key} must be a string")


def _validate_required_boolean_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{context}.{key} must be boolean")


def _validate_nullable_string_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            raise ValueError(f"{context}.{key} must be a string or null")


def _validate_nonnegative_integer_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not _valid_nonnegative_int(value.get(key)):
            raise ValueError(f"{context}.{key} must be a non-negative integer")


def _validate_jp_policy(value: object, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{context}.target_policy must be an object or null")
    _require_keys(value, ("special_translation_action",), f"{context}.target_policy")
    _validate_required_boolean_fields(
        value,
        (
            "use_restricted",
            "edit_restricted",
            "translation_exempt",
            "copy_allowed_for_translation",
        ),
        f"{context}.target_policy",
    )
    action = value.get("special_translation_action")
    if action is not None and action not in SPECIAL_TRANSLATION_ACTIONS:
        raise ValueError(
            f"{context}.target_policy.special_translation_action is invalid"
        )


def _validate_coverage_tag(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    _require_keys(
        value,
        ("jp_tag", "replacement", "display_tag", "target_policy"),
        context,
    )
    if not isinstance(value.get("tag"), str):
        raise ValueError(f"{context}.tag must be a string")
    if value.get("status") not in CLASSIFICATION_STATUSES:
        raise ValueError(f"{context}.status is unknown")
    if value.get("translation_action") not in COVERAGE_TRANSLATION_ACTIONS:
        raise ValueError(f"{context}.translation_action is unknown")
    _validate_required_boolean_fields(
        value,
        ("recognized_by_jp_policy", "copy_allowed"),
        context,
    )
    _validate_nullable_string_fields(
        value,
        ("jp_tag", "replacement", "display_tag"),
        context,
    )
    _validate_nonnegative_integer_fields(
        value,
        ("rank", "page_count"),
        context,
    )
    sample_slugs = value.get("sample_slugs")
    if not isinstance(sample_slugs, list) or any(
        not isinstance(slug, str) for slug in sample_slugs
    ):
        raise ValueError(f"{context}.sample_slugs must be a string array")
    _validate_jp_policy(value.get("target_policy"), context)


def _validate_coverage_source(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("coverage.source must be an object")
    _validate_required_string_fields(
        value,
        (
            "corpus_root",
            "jp_tag_source",
            "jp_unused_source",
            "override_source",
            "deprecated_override_source",
            "crosswalk_source",
        ),
        "coverage.source",
    )


def _validate_status_counts(value: object, context: str) -> None:
    if not isinstance(value, dict) or any(
        key not in CLASSIFICATION_STATUSES or not _valid_nonnegative_int(count)
        for key, count in value.items()
    ):
        raise ValueError(f"{context}.status_counts is invalid")


def _validate_coverage_branch(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    _validate_required_string_fields(value, ("branch", "site"), context)
    _validate_nonnegative_integer_fields(
        value,
        ("page_count", "tag_count"),
        context,
    )
    _validate_status_counts(value.get("status_counts"), context)
    tags = value.get("tags")
    if not isinstance(tags, list):
        raise ValueError(f"{context}.tags must be an array")
    for tag_index, tag in enumerate(tags):
        _validate_coverage_tag(tag, f"{context}.tags[{tag_index}]")
    if value.get("tag_count") != len(tags):
        raise ValueError(f"{context}.tag_count does not match tags")


def validate_coverage(raw: object) -> Coverage:
    if not isinstance(raw, dict):
        raise ValueError("coverage root must be an object")
    if not _valid_nonnegative_int(raw.get("schema_version")):
        raise ValueError("coverage.schema_version must be a non-negative integer")
    _validate_coverage_source(raw.get("source"))
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
        _validate_coverage_branch(branch, f"coverage.branches[{branch_index}]")
    return cast(Coverage, raw)
