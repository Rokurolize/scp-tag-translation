#!/usr/bin/env python3
"""Build a self-contained HTML dashboard for branch tag coverage data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application import coverage_html as _workflow

validate_coverage = _workflow.validate_coverage


def build_html(coverage: _workflow.Coverage) -> str:
    """Render coverage data through the application workflow template."""
    return _workflow.build_html(coverage)


def build_and_publish_html(
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Delegate dashboard generation to the application workflow."""
    return _workflow.build_and_publish_html(input_path, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=_workflow.DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=_workflow.DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        build_and_publish_html(args.input, args.output)
    except (OSError, ValueError) as err:
        print(f"エラー: HTML可視化生成に失敗しました: {err}")
        sys.exit(1)
    print(f"HTML可視化を生成しました: {args.output}")


__all__ = [
    "build_and_publish_html",
    "build_html",
    "main",
    "validate_coverage",
]


if __name__ == "__main__":
    main()
