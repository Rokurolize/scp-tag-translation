"""Runtime validation for parsed tag-record boundaries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from scripts.tag_models import DeprecatedTag, JpTag


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
