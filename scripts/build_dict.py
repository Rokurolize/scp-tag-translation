"""
build_dict.py - data/ の解析済みタグ情報から辞書ファイルを生成する

使い方:
  python scripts/build_dict.py [--overwrite]

動作:
  1. data/jp_tags.json の source_tags を {source_tag: jp_name} にマッピング
  2. data/en_tags.json のうちマッピングが存在しないものを {en_name: null} として追加
  3. 既存の dictionaries/en_to_jp.json があればマージして手動追記を保護

オプション:
  --overwrite  既存の辞書を無視して強制上書き
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atomic_output import publish_files_atomically
from scripts.tag_models import DeprecatedTag, EnTag, JpTag
from scripts.tag_validation import validate_deprecated_tags, validate_jp_tags

_ROOT = Path(__file__).parent.parent
_DATA_EN = _ROOT / "data" / "en_tags.json"
_DATA_JP = _ROOT / "data" / "jp_tags.json"
_DATA_DEPRECATED = _ROOT / "data" / "deprecated_tags.json"
_DICT_OUT = _ROOT / "dictionaries" / "en_to_jp.json"
_DICT_DEPRECATED = _ROOT / "dictionaries" / "deprecated_en_to_jp.json"
EN_CATEGORIES_OMITTED_ON_JP = {"Genre", "Genre and Themes"}
EN_ORIGIN_TAG_REPLACEMENTS = {
    "_int": "int",
    "_ru": "ru",
    "_ko": "ko",
    "_cn": "cn",
    "_fr": "fr",
    "_pl": "pl",
    "_es": "es",
    "_th": "th",
    "_jp": "jp",
    "_de": "de",
    "_it": "it",
    "_ua": "ua",
    "_pt": "pt",
    "_zh": "zh",
    "_vn": "vn",
    "_el": "el",
    "_id": "id",
    "_hu": "hu",
    "_nd": "nd",
}
EN_CROSSWALK_SEMANTIC_REPLACEMENTS = {
    **EN_ORIGIN_TAG_REPLACEMENTS,
    # JP tag-list FAQ: foreign-branch guide tags become 他支部公式 on JP.
    "guide": "他支部公式",
}


def load_json(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        f"{json.dumps(data, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def is_deprecated_for_en_source(entry: DeprecatedTag) -> bool:
    source_lang = entry.get("source_lang") or "EN"
    return source_lang == "EN" and bool(entry.get("source_tag"))


def jp_source_tags(entry: JpTag) -> list[str]:
    """Return every source-language alias recorded for a JP tag."""
    return entry.get("source_tags", [])


def en_category_omitted_tags(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    extra_mapped_tags: set[str] | None = None,
) -> set[str]:
    """EN Genre tags omitted by JP policy unless JP explicitly maps them."""
    mapped = {
        source_tag
        for entry in jp_tags
        for source_tag in jp_source_tags(entry)
    }
    mapped.update(extra_mapped_tags or set())
    return {
        entry["name"]
        for entry in en_tags
        if entry.get("category") in EN_CATEGORIES_OMITTED_ON_JP
        and entry["name"] not in mapped
    }


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


def _ensure_no_case_variant_keys(
    existing_keys: Iterable[str],
    source_keys: Iterable[str],
    label: str,
) -> None:
    lower_to_source = {key.lower(): key for key in source_keys}
    collisions = []
    for key in existing_keys:
        source_key = lower_to_source.get(key.lower())
        if source_key is not None and key != source_key:
            collisions.append(f"{key} -> {source_key}")

    if collisions:
        sample = ", ".join(sorted(collisions)[:10])
        raise ValueError(f"{label} に大小文字違いの重複があります: {sample}")


def validate_build_inputs(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    deprecated_raw: list[DeprecatedTag] | None = None,
) -> None:
    if not isinstance(en_tags, list):
        raise ValueError("ENタグデータは配列である必要があります")
    for index, entry in enumerate(en_tags):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"ENタグデータの項目が不正です: index={index}")
        if not entry["name"] or entry["name"] != entry["name"].strip():
            raise ValueError(f"ENタグ名が不正です: {entry['name']!r}")
    validated_jp_tags = validate_jp_tags(jp_tags)
    if deprecated_raw is not None:
        validate_deprecated_tags(deprecated_raw, validated_jp_tags)

    _ensure_unique((entry["name"] for entry in en_tags), "ENタグ名")


def validate_existing_dict(existing: dict[str, str | None]) -> None:
    if not isinstance(existing, dict):
        raise ValueError("既存辞書はオブジェクトである必要があります")
    for en_name, jp_name in existing.items():
        if not isinstance(en_name, str) or not en_name or en_name != en_name.strip():
            raise ValueError(f"既存辞書のキーが不正です: {en_name!r}")
        if jp_name is not None and (
            not isinstance(jp_name, str) or not jp_name or jp_name != jp_name.strip()
        ):
            raise ValueError(f"既存辞書の値が不正です: {en_name!r} -> {jp_name!r}")


def build(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    existing: dict[str, str | None] | None = None,
    deprecated_en_tags: set[str] | None = None,
) -> dict[str, str | None]:
    """
    ENタグリストとJPタグリストから辞書を構築する。

    Args:
        en_tags: ENタグのリスト（各エントリに "name" キーを持つ）
        jp_tags: JPタグのリスト（各エントリに "name", "source_tags" キーを持つ）
        existing: 既存辞書（手動追記を保護するため）
        deprecated_en_tags: 非使用ENタグのセット（これらは既存値があってもnullにする）

    Returns:
        ソート済みの {en_name: jp_name | None} 辞書
    """
    if existing is None:
        existing = {}
    if deprecated_en_tags is None:
        deprecated_en_tags = set()
    validate_build_inputs(en_tags, jp_tags)
    validate_existing_dict(existing)
    _ensure_no_case_variant_keys(
        existing.keys(),
        (entry["name"] for entry in en_tags),
        "既存辞書キー",
    )

    jp_map: dict[str, str] = {}
    for entry in jp_tags:
        for source_tag in jp_source_tags(entry):
            jp_map[source_tag] = entry["name"]

    new_dict: dict[str, str | None] = {}

    for entry in en_tags:
        en_name: str = entry["name"]

        if en_name in deprecated_en_tags:
            new_dict[en_name] = None
        elif en_name in jp_map:
            new_dict[en_name] = jp_map[en_name]
        elif en_name in existing and existing[en_name] is not None:
            new_dict[en_name] = existing[en_name]
        else:
            new_dict[en_name] = None

    # ENソース外の手動エントリは、非使用タグでない限り保持する。
    for en_name, jp_name in existing.items():
        if en_name not in new_dict:
            new_dict[en_name] = None if en_name in deprecated_en_tags else jp_name

    return dict(sorted(new_dict.items()))


def _build_outputs(
    overwrite: bool,
) -> tuple[dict[str, str | None], dict[str, str]]:
    for path in (_DATA_EN, _DATA_JP):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} が見つかりません。"
                "先に parse_sources.py を実行してください。"
            )

    en_tags = cast(list[EnTag], load_json(_DATA_EN))
    jp_tags = cast(list[JpTag], load_json(_DATA_JP))
    deprecated_raw = (
        cast(list[DeprecatedTag], load_json(_DATA_DEPRECATED))
        if _DATA_DEPRECATED.exists()
        else []
    )
    validate_build_inputs(en_tags, jp_tags, deprecated_raw)

    deprecated_en_tags = {
        entry["source_tag"]
        for entry in deprecated_raw
        if is_deprecated_for_en_source(entry)
    }
    category_omitted_tags = en_category_omitted_tags(en_tags, jp_tags)
    en_tag_names = {entry["name"] for entry in en_tags}
    origin_replacements = {
        source_tag: replacement
        for source_tag, replacement in EN_ORIGIN_TAG_REPLACEMENTS.items()
        if source_tag in en_tag_names
    }
    deprecated_en_tags.update(category_omitted_tags)
    deprecated_en_tags.update(origin_replacements)

    existing: dict[str, str | None] = {}
    if not overwrite and _DICT_OUT.exists():
        existing = cast(dict[str, str | None], load_json(_DICT_OUT))
        validate_existing_dict(existing)

    sorted_dict = build(en_tags, jp_tags, existing, deprecated_en_tags)
    deprecated_dict = {
        entry["source_tag"]: replacement
        for entry in deprecated_raw
        if is_deprecated_for_en_source(entry)
        and isinstance(replacement := entry.get("replacement"), str)
    }
    deprecated_dict.update(origin_replacements)
    return sorted_dict, dict(sorted(deprecated_dict.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="data/ から辞書ファイルを生成する")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存の辞書を無視して強制上書きする",
    )
    args = parser.parse_args()

    try:
        sorted_dict, deprecated_dict = _build_outputs(args.overwrite)
        publish_files_atomically({
            _DICT_OUT: (
                lambda temporary: _write_json(temporary, sorted_dict)
            ),
            _DICT_DEPRECATED: (
                lambda temporary: _write_json(temporary, deprecated_dict)
            ),
        })
    except (OSError, ValueError) as err:
        print(f"エラー: 辞書生成に失敗しました: {err}")
        sys.exit(1)

    mapped = sum(1 for value in sorted_dict.values() if value is not None)
    print(
        f"辞書生成完了: {mapped}/{len(sorted_dict)} "
        f"エントリがマッピング済み → {_DICT_OUT}"
    )
    print(
        f"非使用タグ置換辞書: {len(deprecated_dict)} "
        f"エントリ → {_DICT_DEPRECATED}"
    )


if __name__ == "__main__":
    main()
