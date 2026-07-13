"""Publish browser branch metadata rendered by the domain configuration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.atomic_output import publish_files_atomically
from scripts.data_paths import BROWSER_CONFIG_PATH
from scripts.domain.branch_config import render_browser_config

DEFAULT_OUTPUT = BROWSER_CONFIG_PATH


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def publish_browser_config(output: Path = DEFAULT_OUTPUT) -> None:
    content = render_browser_config()
    publish_files_atomically(
        {
            output: lambda temporary: _write_text(temporary, content),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ブラウザ用の支部設定JavaScriptを生成する",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"出力先（デフォルト: {DEFAULT_OUTPUT}）",
    )
    args = parser.parse_args()

    try:
        publish_browser_config(args.output)
    except (OSError, ValueError) as error:
        print(f"エラー: ブラウザ設定の生成に失敗しました: {error}")
        sys.exit(1)
    print(f"browser config: {args.output}")


if __name__ == "__main__":
    main()
