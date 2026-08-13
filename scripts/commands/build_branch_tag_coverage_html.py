"""Build a self-contained HTML dashboard for branch tag coverage data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.atomic_output import publish_files_atomically
from scripts.data_paths import COVERAGE_HTML_PATH, COVERAGE_JSON_PATH, ROOT
from scripts.domain.tag_models import Coverage
from scripts.domain.tag_validation import validate_coverage
from scripts.json_io import write_text


DEFAULT_INPUT = COVERAGE_JSON_PATH
DEFAULT_OUTPUT = COVERAGE_HTML_PATH
TEMPLATE_PATH = ROOT / "scripts" / "assets" / "branch_tag_coverage.html"

def build_html(data: Coverage) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count("__DATA_JSON__") != 1:
        raise ValueError("coverage HTML template must contain one __DATA_JSON__ placeholder")
    embedded_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    embedded_json = (
        embedded_json.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return template.replace("__DATA_JSON__", embedded_json)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        data = validate_coverage(
            json.loads(args.input.read_text(encoding="utf-8"))
        )
        html = build_html(data)
        publish_files_atomically({
            args.output: lambda temporary: write_text(temporary, html),
        })
    except (OSError, ValueError) as err:
        print(f"エラー: HTML可視化生成に失敗しました: {err}")
        sys.exit(1)
    print(f"HTML可視化を生成しました: {args.output}")


if __name__ == "__main__":
    main()
