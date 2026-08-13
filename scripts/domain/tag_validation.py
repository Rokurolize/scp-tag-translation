"""Runtime validation for parsed tag-record boundaries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast
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

    records = [
        {
            **entry,
            "category": entry.get("category"),
            "description": entry.get("description") or "",
            "meta": entry.get("meta") or {},
        }
        for entry in raw
    ]
    records = cast(list[EnTag], records)
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

    records = [
        {
            **entry,
            "description": entry.get("description") or "",
            "use_restricted": bool(entry.get("use_restricted")),
            "edit_restricted": bool(entry.get("edit_restricted")),
            "translation_exempt": bool(entry.get("translation_exempt")),
        }
        for entry in raw
    ]
    records = cast(list[JpTag], records)
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
