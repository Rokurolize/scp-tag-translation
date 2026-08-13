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
import sys
from collections.abc import Iterable
from dataclasses import replace
from typing import cast

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.pipeline.dictionary_inputs import (
    default_mapping_input_paths,
    load_mapping_inputs,
    load_mapping_policy_inputs,
)
from scripts.infrastructure.json_io import load_json, write_json
from scripts.infrastructure.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_EN_DICTIONARY_PATH,
    EN_DICTIONARY_PATH,
)
from scripts.domain.tag_dictionary import build_en_dicts
from scripts.domain.tag_records import EnTag, JpTag
from scripts.domain.policy_builder import MappingPolicyInputs, build_mapping_policy
from scripts.domain.tag_validation import validate_tag_records

__all__ = ["build_en_dictionary", "main"]


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


def build_en_dictionary(
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
    deprecated_raw = [
        {"source_lang": "EN", "source_tag": source_tag}
        for source_tag in deprecated_en_tags
    ]
    en_tags, jp_tags, deprecated_raw = validate_tag_records(
        en_tags,
        jp_tags,
        deprecated_raw,
    )
    validate_existing_dict(existing)
    _ensure_no_case_variant_keys(
        existing.keys(),
        (entry["name"] for entry in en_tags),
        "既存辞書キー",
    )

    compatibility_overrides = {
        source_tag: target
        for source_tag, target in existing.items()
        if target is not None
    }
    policy = build_mapping_policy(
        jp_tags,
        deprecated_raw,
        MappingPolicyInputs(
            overrides={},
            replacement_overrides={},
            official_crosswalks=(),
            compatibility_overrides={"en": compatibility_overrides},
        ),
        include_origin_replacements=False,
    )
    dictionary, _replacements = build_en_dicts(
        en_tags,
        jp_tags,
        deprecated_raw,
        set(existing),
        policy,
    )
    return dictionary


def _build_outputs(
    overwrite: bool,
) -> tuple[dict[str, str | None], dict[str, str]]:
    for path in (DATA_EN, DATA_JP):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} が見つかりません。先に parse_sources.py を実行してください。"
            )

    mapping_paths = replace(
        default_mapping_input_paths(),
        data_en=DATA_EN,
        data_jp=DATA_JP,
        data_deprecated=DATA_DEPRECATED,
    )
    loaded = load_mapping_inputs(
        mapping_paths,
        policy_inputs=load_mapping_policy_inputs(),
        include_origin_replacements=False,
    )
    en_tags = loaded.en_tags
    jp_tags = loaded.jp_tags
    deprecated_raw = loaded.deprecated_tags

    existing: dict[str, str | None] = {}
    if not overwrite and EN_DICTIONARY_PATH.exists():
        existing = validate_existing_dict(load_json(EN_DICTIONARY_PATH))

    policy = loaded.mapping_policy
    if existing:
        policy = replace(
            policy,
            overrides={
                **policy.overrides,
                "en": {
                    **policy.overrides.get("en", {}),
                    **{
                        source_tag: target
                        for source_tag, target in existing.items()
                        if target is not None
                    },
                },
            },
        )

    sorted_dict, deprecated_dict = build_en_dicts(
        en_tags,
        jp_tags,
        deprecated_raw,
        set(existing),
        policy,
    )
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
        publish_files_atomically(
            {
                EN_DICTIONARY_PATH: (
                    lambda temporary: write_json(temporary, sorted_dict)
                ),
                DEPRECATED_EN_DICTIONARY_PATH: (
                    lambda temporary: write_json(temporary, deprecated_dict)
                ),
            }
        )
    except (OSError, ValueError) as err:
        print(f"エラー: 辞書生成に失敗しました: {err}")
        sys.exit(1)

    mapped = sum(1 for value in sorted_dict.values() if value is not None)
    print(
        f"辞書生成完了: {mapped}/{len(sorted_dict)} "
        f"エントリがマッピング済み → {EN_DICTIONARY_PATH}"
    )
    print(
        f"非使用タグ置換辞書: {len(deprecated_dict)} "
        f"エントリ → {DEPRECATED_EN_DICTIONARY_PATH}"
    )


if __name__ == "__main__":
    main()
