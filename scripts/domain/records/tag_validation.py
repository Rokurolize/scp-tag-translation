"""Runtime validation for parsed tag-record boundaries."""

from __future__ import annotations

from collections.abc import Iterable
from scripts.domain.errors import InvalidDomainInputError
from scripts.domain.records.tag_records import DeprecatedTag, EnTag, JpTag


def _ensure_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        sample = ", ".join(sorted(duplicates)[:10])
        raise InvalidDomainInputError(f"{label} が重複しています: {sample}")


def _valid_trimmed_string(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _required_string(
    entry: dict[object, object],
    key: str,
    context: str,
) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise InvalidDomainInputError(f"{context}{key}が不正です: {value!r}")
    return value


def _optional_string(
    entry: dict[object, object],
    key: str,
    default: str,
    context: str,
) -> str:
    value = entry.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise InvalidDomainInputError(f"{context}{key}が不正です: {value!r}")
    return value


def _optional_boolean(
    entry: dict[object, object],
    key: str,
    context: str,
) -> bool:
    value = entry.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise InvalidDomainInputError(f"{context}{key}が不正です: {value!r}")
    return value


def _validated_meta(entry: dict[object, object]) -> dict[str, list[str]]:
    value = entry.get("meta")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise InvalidDomainInputError(f"ENタグのmetaが不正です: {value!r}")
    return {
        key: list(values)
        for key, values in value.items()
        if isinstance(key, str)
        and isinstance(values, list)
        and all(isinstance(item, str) for item in values)
    }


def _validated_source_tags(entry: dict[object, object]) -> list[str]:
    value = entry.get("source_tags")
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise InvalidDomainInputError(f"JP側source_tagsが不正です: {value!r}")
    return list(value)


def _validate_en_meta(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or any(
        not isinstance(key, str)
        or not isinstance(values, list)
        or any(not isinstance(item, str) for item in values)
        for key, values in value.items()
    ):
        raise InvalidDomainInputError(f"ENタグのmetaが不正です: {value!r}")


def _validate_en_tag_entry(entry: object, index: int) -> None:
    if (
        not isinstance(entry, dict)
        or "name" not in entry
        or not isinstance(entry["name"], str)
    ):
        raise InvalidDomainInputError(f"ENタグデータの項目が不正です: index={index}")
    name = entry["name"]
    if not _valid_trimmed_string(name):
        raise InvalidDomainInputError(f"ENタグ名が不正です: {name!r}")
    category = entry.get("category")
    if category is not None and not isinstance(category, str):
        raise InvalidDomainInputError(f"ENタグのcategoryが不正です: {category!r}")
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise InvalidDomainInputError(f"ENタグのdescriptionが不正です: {description!r}")
    _validate_en_meta(entry.get("meta"))


def validate_en_tags(raw: object) -> list[EnTag]:
    if not isinstance(raw, list):
        raise InvalidDomainInputError("ENタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        _validate_en_tag_entry(entry, index)

    records: list[EnTag] = []
    for item in raw:
        if not isinstance(item, dict):
            raise InvalidDomainInputError("ENタグデータの項目が不正です")
        category = item.get("category")
        if category is not None and not isinstance(category, str):
            raise InvalidDomainInputError(f"ENタグのcategoryが不正です: {category!r}")
        records.append({
            "name": _required_string(item, "name", "ENタグの"),
            "category": category,
            "description": _optional_string(
                item,
                "description",
                "",
                "ENタグの",
            ),
            "meta": _validated_meta(item),
        })
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
            raise InvalidDomainInputError(f"{context}{key}が不正です: {value!r}")


def _validate_jp_tag_entry(entry: object, index: int) -> None:
    if (
        not isinstance(entry, dict)
        or "name" not in entry
        or not isinstance(entry["name"], str)
    ):
        raise InvalidDomainInputError(f"JPタグデータの項目が不正です: index={index}")
    name = entry["name"]
    if not _valid_trimmed_string(name):
        raise InvalidDomainInputError(f"JPタグ名が不正です: {name!r}")
    if "en_tag" in entry:
        raise InvalidDomainInputError(f"JPタグデータに旧en_tagがあります: index={index}")
    if "source_tags" not in entry:
        raise InvalidDomainInputError("JP側source_tagsが不正です: 欠落")
    source_tags = entry["source_tags"]
    if not _valid_source_tags(source_tags):
        raise InvalidDomainInputError(f"JP側source_tagsが不正です: {source_tags!r}")
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise InvalidDomainInputError(f"JPタグのdescriptionが不正です: {description!r}")
    _validate_optional_boolean_fields(
        entry,
        ("use_restricted", "edit_restricted", "translation_exempt"),
        "JPタグの",
    )


def validate_jp_tags(raw: object) -> list[JpTag]:
    if not isinstance(raw, list):
        raise InvalidDomainInputError("JPタグデータは配列である必要があります")
    for index, entry in enumerate(raw):
        _validate_jp_tag_entry(entry, index)

    records: list[JpTag] = []
    for item in raw:
        if not isinstance(item, dict):
            raise InvalidDomainInputError("JPタグデータの項目が不正です")
        records.append({
            "name": _required_string(item, "name", "JPタグの"),
            "description": _optional_string(
                item,
                "description",
                "",
                "JPタグの",
            ),
            "source_tags": _validated_source_tags(item),
            "use_restricted": _optional_boolean(
                item,
                "use_restricted",
                "JPタグの",
            ),
            "edit_restricted": _optional_boolean(
                item,
                "edit_restricted",
                "JPタグの",
            ),
            "translation_exempt": _optional_boolean(
                item,
                "translation_exempt",
                "JPタグの",
            ),
        })
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
        raise InvalidDomainInputError(f"非使用タグのreplacementが不正です: {replacement!r}")
    source_lang = entry.get("source_lang")
    if (
        replacement is not None
        and (source_lang or "EN") == "EN"
        and require_registered_replacement
        and replacement not in jp_names
    ):
        raise InvalidDomainInputError(
            f"非使用タグのreplacementがJPタグに存在しません: {replacement!r}"
        )


def _validate_deprecated_tag_entry(
    entry: object,
    index: int,
    jp_names: set[str],
    require_registered_replacement: bool,
) -> None:
    if not isinstance(entry, dict):
        raise InvalidDomainInputError(f"非使用タグデータの項目が不正です: index={index}")
    if "en_tag" in entry:
        raise InvalidDomainInputError(f"非使用タグデータに旧en_tagがあります: index={index}")
    if "source_tag" not in entry:
        raise InvalidDomainInputError("非使用タグのsource_tagが不正です: 欠落")
    source_tag = entry["source_tag"]
    if not _valid_trimmed_string(source_tag):
        raise InvalidDomainInputError(f"非使用タグのsource_tagが不正です: {source_tag!r}")
    source_lang = entry.get("source_lang")
    if "source_lang" in entry and not _valid_trimmed_string(source_lang):
        raise InvalidDomainInputError(f"非使用タグのsource_langが不正です: {source_lang!r}")
    _validate_deprecated_replacement(
        entry,
        jp_names,
        require_registered_replacement,
    )
    description = entry.get("description")
    if description is not None and not isinstance(description, str):
        raise InvalidDomainInputError(f"非使用タグのdescriptionが不正です: {description!r}")


def validate_deprecated_tags(
    raw: object,
    jp_tags: list[JpTag] | None = None,
) -> list[DeprecatedTag]:
    if not isinstance(raw, list):
        raise InvalidDomainInputError("非使用タグデータは配列である必要があります")
    jp_names = {entry["name"] for entry in jp_tags or []}
    for index, entry in enumerate(raw):
        _validate_deprecated_tag_entry(
            entry,
            index,
            jp_names,
            jp_tags is not None,
        )

    records: list[DeprecatedTag] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise InvalidDomainInputError("非使用タグデータの項目が不正です")
        record: DeprecatedTag = {"source_tag": entry["source_tag"]}
        for key in ("source_lang", "replacement", "description"):
            if key in entry:
                record[key] = entry[key]
        records.append(record)
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
