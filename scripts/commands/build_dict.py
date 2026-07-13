"""
build_dict.py - data/ の解析済みタグ情報からEN辞書を生成する互換CLI

使い方:
  python -m scripts.commands.build_dict [--overwrite]

動作:
  正規パイプラインと同じ共有辞書ビルダーを使用し、既存の辞書キーと値を互換入力として渡す。

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

from scripts.atomic_output import publish_files_atomically
from scripts.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_EN_DICTIONARY_PATH,
    EN_DICTIONARY_PATH,
)
from scripts.domain.tag_dictionary import build_en_dicts
from scripts.domain.tag_models import EnTag, JpTag
from scripts.domain.tag_policy import (
    EN_ORIGIN_TAG_REPLACEMENTS,
    en_category_omitted_tags,
    is_deprecated_for_en_source,
    jp_maps,
    MappingPolicy,
)
from scripts.domain.tag_validation import validate_tag_records

_DATA_EN = DATA_EN
_DATA_JP = DATA_JP
_DATA_DEPRECATED = DATA_DEPRECATED
_DICT_OUT = EN_DICTIONARY_PATH
_DICT_DEPRECATED = DEPRECATED_EN_DICTIONARY_PATH


def load_json(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        f"{json.dumps(data, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


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


def validate_existing_dict(raw: object) -> dict[str, str | None]:
    existing = cast(dict[object, object], raw) if isinstance(raw, dict) else None
    if not isinstance(existing, dict):
        raise ValueError("既存辞書はオブジェクトである必要があります")
    for en_name, jp_name in existing.items():
        if not isinstance(en_name, str) or not en_name or en_name != en_name.strip():
            raise ValueError(f"既存辞書のキーが不正です: {en_name!r}")
        if jp_name is not None and (
            not isinstance(jp_name, str) or not jp_name or jp_name != jp_name.strip()
        ):
            raise ValueError(f"既存辞書の値が不正です: {en_name!r} -> {jp_name!r}")
    return cast(dict[str, str | None], existing)


def build(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    existing: dict[str, str | None] | None = None,
    deprecated_en_tags: set[str] | None = None,
) -> dict[str, str | None]:
    """Treat existing mappings as compatibility overrides; deprecation still wins."""
    if existing is None:
        existing = {}
    if deprecated_en_tags is None:
        deprecated_en_tags = set()
    validate_tag_records(en_tags, jp_tags)
    validate_existing_dict(existing)
    _ensure_no_case_variant_keys(
        existing.keys(),
        (entry["name"] for entry in en_tags),
        "既存辞書キー",
    )

    jp_names, jp_source_map = jp_maps(jp_tags)
    compatibility_overrides = {
        source_tag: target
        for source_tag, target in existing.items()
        if target is not None
    }
    policy = MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags={"EN": deprecated_en_tags},
        replacements={},
        overrides={"en": compatibility_overrides},
        official_crosswalk={},
    )
    dictionary, _replacements = build_en_dicts(
        en_tags,
        jp_tags,
        [],
        set(existing),
        policy,
    )
    return dictionary


def _build_outputs(
    overwrite: bool,
) -> tuple[dict[str, str | None], dict[str, str]]:
    for path in (_DATA_EN, _DATA_JP):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} が見つかりません。"
                "先に parse_sources.py を実行してください。"
            )

    en_tags, jp_tags, deprecated_raw = validate_tag_records(
        load_json(_DATA_EN),
        load_json(_DATA_JP),
        (
            load_json(_DATA_DEPRECATED)
            if _DATA_DEPRECATED.exists()
            else []
        ),
    )

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
        existing = validate_existing_dict(load_json(_DICT_OUT))

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
