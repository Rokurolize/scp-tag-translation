#!/usr/bin/env python3
"""Build a self-contained HTML dashboard for branch tag coverage data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application import coverage_html as workflow


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=workflow.DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=workflow.DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        workflow.build_and_publish_html(input_path=args.input, output_path=args.output)
    except (OSError, ValueError) as err:
        print(f"エラー: HTML可視化生成に失敗しました: {err}")
        sys.exit(1)
    print(f"HTML可視化を生成しました: {args.output}")


__all__ = ["main"]


if __name__ == "__main__":
    main()
