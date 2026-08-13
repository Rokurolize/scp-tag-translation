"""Build and publish the self-contained branch coverage dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.domain.coverage_validation import validate_coverage
from scripts.domain.tag_coverage_models import Coverage
from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import (
    COVERAGE_HTML_PATH,
    COVERAGE_JSON_PATH,
    ROOT,
)
from scripts.infrastructure.json_io import load_json, write_text

DEFAULT_INPUT = COVERAGE_JSON_PATH
DEFAULT_OUTPUT = COVERAGE_HTML_PATH
TEMPLATE_PATH = ROOT / "scripts" / "assets" / "branch_tag_coverage.html"


def build_html(coverage: Coverage, *, template_path: Path = TEMPLATE_PATH) -> str:
    """Render validated coverage data into the dashboard template."""
    template = template_path.read_text(encoding="utf-8")
    if template.count("__DATA_JSON__") != 1:
        raise ValueError(
            "coverage HTML template must contain one __DATA_JSON__ placeholder"
        )
    embedded_json = json.dumps(coverage, ensure_ascii=False, separators=(",", ":"))
    embedded_json = (
        embedded_json.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return template.replace("__DATA_JSON__", embedded_json)


def build_and_publish_html(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    """Load, validate, render, and atomically publish the coverage dashboard."""
    coverage = validate_coverage(load_json(input_path))
    html = build_html(coverage)
    publish_files_atomically({
        output_path: lambda temporary: write_text(temporary, html),
    })
    return output_path


__all__ = [
    "DEFAULT_INPUT",
    "DEFAULT_OUTPUT",
    "TEMPLATE_PATH",
    "build_and_publish_html",
    "build_html",
]
