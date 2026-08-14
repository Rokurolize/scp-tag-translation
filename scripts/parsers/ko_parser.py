"""Parse SCP-KO's official EN/JP/KO translation-tag table."""

from __future__ import annotations

import re
from collections.abc import Iterable, MutableSequence
from pathlib import Path

from scripts.parsers.contracts import CrosswalkMappings, TargetResolver
from scripts.parsers.crosswalk_candidates import (
    CrosswalkCandidate,
    resolve_crosswalk_candidates,
)
from scripts.parsers.crosswalk_table import split_wikidot_table_row
from scripts.parsers.errors import report_source_issue

__all__ = ["parse_ko_crosswalk"]

_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")
_TAG_LINK_MARKER = "/system:page-tags/tag/"


def _is_table_header(cells: list[str]) -> bool:
    text = " ".join(cells)
    return "English" in text and "日本語" in text and "한국어" in text


def _iter_ko_crosswalk_candidates(
    input_path: Path,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> Iterable[CrosswalkCandidate]:
    expected_width = 3

    with input_path.open(encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, 1):
            line = raw_line.strip()
            if not line.startswith("||"):
                continue
            cells = split_wikidot_table_row(line)
            if _is_table_header(cells):
                expected_width = len(cells)
                continue
            if expected_width != 3 or len(cells) != expected_width:
                if strict and expected_width == 3 and _TAG_LINK_MARKER in line:
                    report_source_issue(
                        input_path,
                        line_number,
                        "invalid KO crosswalk row",
                        diagnostics,
                    )
                continue
            en_tag, jp_tag, ko_cell = cells
            ko_tags = _KO_LINK_RE.findall(ko_cell)
            if strict and _TAG_LINK_MARKER in ko_cell and len(ko_tags) != 1:
                report_source_issue(
                    input_path,
                    line_number,
                    "invalid KO tag link",
                    diagnostics,
                )
                continue
            jp_tag = jp_tag.strip()
            if len(ko_tags) != 1:
                continue
            yield (
                "ko",
                ko_tags[0],
                [en_tag.strip()] if en_tag.strip() else [],
                [jp_tag] if jp_tag else [],
            )


def parse_ko_crosswalk(
    input_path: Path,
    resolver: TargetResolver,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> CrosswalkMappings:
    mappings = resolve_crosswalk_candidates(
        _iter_ko_crosswalk_candidates(
            input_path,
            strict=strict,
            diagnostics=diagnostics,
        ),
        resolver,
    )
    return {"ko": mappings.get("ko", {})}
