"""Build and publish the self-contained branch coverage dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.contracts.errors import InvalidDomainInputError
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


def render_coverage_html(
    coverage: Coverage,
    *,
    template_path: Path = TEMPLATE_PATH,
) -> str:
    """Render validated coverage data into the dashboard template.

    Raises:
        OSError: If the template cannot be read.
        InvalidDomainInputError: If the template does not contain exactly one
            ``__DATA_JSON__`` placeholder.
    """
    template = template_path.read_text(encoding="utf-8")
    if template.count("__DATA_JSON__") != 1:
        raise InvalidDomainInputError(
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


def build_and_publish_coverage_html(
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Publish the coverage dashboard.

    Raises:
        InvalidDomainInputError: If the input coverage or HTML template is invalid.
        FileNotFoundError: If the coverage JSON or template is missing.
        OSError: If input reads or publication filesystem operations fail.
        AtomicPublicationError: If publication rollback or cleanup fails.
    """
    input_path = input_path or DEFAULT_INPUT
    output_path = output_path or DEFAULT_OUTPUT
    coverage = validate_coverage(load_json(input_path))
    html = render_coverage_html(coverage)
    publish_files_atomically({
        output_path: lambda temporary: write_text(temporary, html),
    })
    return output_path


__all__ = [
    "DEFAULT_INPUT",
    "DEFAULT_OUTPUT",
    "TEMPLATE_PATH",
    "build_and_publish_coverage_html",
    "render_coverage_html",
]
