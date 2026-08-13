"""Generate the legacy EN dictionary through the compatibility workflow."""

from __future__ import annotations

import argparse
import sys

from scripts.application.legacy_dictionary_build import (
    LegacyDictionaryBuildConfig,
    build_and_publish_legacy_dictionary,
    build_legacy_en_dictionary as build_en_dictionary,
    default_legacy_dictionary_build_config,
)

__all__ = [
    "LegacyDictionaryBuildConfig",
    "build_en_dictionary",
    "default_legacy_dictionary_build_config",
    "main",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="data/ からEN辞書を生成する")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存の辞書を無視して強制上書きする",
    )
    args = parser.parse_args()

    try:
        config = default_legacy_dictionary_build_config()
        result = build_and_publish_legacy_dictionary(
            args.overwrite,
            config=config,
        )
    except (OSError, ValueError) as err:
        print(f"エラー: 辞書生成に失敗しました: {err}")
        sys.exit(1)

    mapped = sum(1 for value in result.dictionary.values() if value is not None)
    print(
        f"辞書生成完了: {mapped}/{len(result.dictionary)} "
        f"エントリがマッピング済み → {result.dictionary_path}"
    )
    print(
        f"非使用タグ置換辞書: {len(result.deprecated_dictionary)} "
        f"エントリ → {result.deprecated_dictionary_path}"
    )


if __name__ == "__main__":
    main()
