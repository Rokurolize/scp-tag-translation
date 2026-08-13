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

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.pipeline.dictionary_inputs import (
    load_mapping_policy_inputs,
)
from scripts.infrastructure.json_io import write_json
from scripts.infrastructure.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_EN_DICTIONARY_PATH,
    EN_DICTIONARY_PATH,
)
from scripts.pipeline.legacy_dictionary import (
    LegacyDictionaryConfig,
    build_legacy_en_dictionary as build_en_dictionary,
    build_legacy_outputs,
)

__all__ = ["build_en_dictionary", "main"]


def _build_outputs(
    overwrite: bool,
) -> tuple[dict[str, str | None], dict[str, str]]:
    return build_legacy_outputs(
        overwrite,
        config=LegacyDictionaryConfig(
            data_en=DATA_EN,
            data_jp=DATA_JP,
            data_deprecated=DATA_DEPRECATED,
            dictionary_path=EN_DICTIONARY_PATH,
        ),
        policy_inputs=load_mapping_policy_inputs(),
    )


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
