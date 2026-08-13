"""Publish browser branch metadata rendered by the domain configuration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application import browser_config as _workflow
from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import BROWSER_CONFIG_PATH

DEFAULT_OUTPUT = BROWSER_CONFIG_PATH


def render_browser_config() -> str:
    """Render browser configuration through the application workflow."""
    return _workflow.render_browser_config()


def publish_browser_config(output: Path = DEFAULT_OUTPUT) -> None:
    """Delegate browser configuration publication to the application workflow."""
    _workflow.publish_browser_config(output, publish=publish_files_atomically)


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


__all__ = ["DEFAULT_OUTPUT", "main", "publish_browser_config", "render_browser_config"]


if __name__ == "__main__":
    main()
