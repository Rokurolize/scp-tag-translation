"""Publish browser branch metadata rendered by the application workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application import browser_config as workflow


def main() -> None:
    """Run the CLI from ``sys.argv``; invalid inputs exit with status 1."""
    parser = argparse.ArgumentParser(
        description="ブラウザ用の支部設定JavaScriptを生成する",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=workflow.DEFAULT_OUTPUT,
        help=f"出力先（デフォルト: {workflow.DEFAULT_OUTPUT}）",
    )
    args = parser.parse_args()

    try:
        workflow.publish_browser_config(args.output)
    except (OSError, ValueError) as error:
        print(f"エラー: ブラウザ設定の生成に失敗しました: {error}")
        sys.exit(1)
    print(f"browser config: {args.output}")


__all__ = ["main"]


if __name__ == "__main__":
    main()
