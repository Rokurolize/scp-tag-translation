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
from scripts.parsers.crosswalk_table import TAG_LINK_MARKER, split_wikidot_table_row
from scripts.parsers.errors import report_source_issue

__all__ = ["parse_ko_crosswalk"]

_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")


def _is_table_header(cells: list[str]) -> bool:
    text = " ".join(cells)
    return "English" in text and "日本語" in text and "한국어" in text


def _parse_ko_candidate(
    input_path: Path,
    line_number: int,
    line: str,
    cells: list[str],
    *,
    strict: bool,
    diagnostics: MutableSequence[str] | None,
) -> CrosswalkCandidate | None:
    if len(cells) != 3:
        if strict and TAG_LINK_MARKER in line:
            report_source_issue(
                input_path,
                line_number,
                "invalid KO crosswalk row",
                diagnostics,
            )
        return None

    en_tag, jp_tag, ko_cell = cells
    ko_tags = _KO_LINK_RE.findall(ko_cell)
    if strict and TAG_LINK_MARKER in ko_cell and len(ko_tags) != 1:
        report_source_issue(
            input_path,
            line_number,
            "invalid KO tag link",
            diagnostics,
        )
        return None
    if len(ko_tags) != 1:
        return None
    return (
        "ko",
        ko_tags[0],
        [en_tag.strip()] if en_tag.strip() else [],
        [jp_tag.strip()] if jp_tag.strip() else [],
    )


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
            if expected_width != 3:
                continue
            candidate = _parse_ko_candidate(
                input_path,
                line_number,
                line,
                cells,
                strict=strict,
                diagnostics=diagnostics,
            )
            if candidate is not None:
                yield candidate


def parse_ko_crosswalk(
    input_path: Path,
    resolver: TargetResolver,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> CrosswalkMappings:
    """Parse the official KO table into mappings resolved by ``resolver``.

    Lenient parsing ignores malformed rows. With ``strict=True``, malformed
    source records are appended to ``diagnostics`` when supplied, or raise
    ``SourceParseError`` when no diagnostics sink is supplied.
    """
    mappings = resolve_crosswalk_candidates(
        _iter_ko_crosswalk_candidates(
            input_path,
            strict=strict,
            diagnostics=diagnostics,
        ),
        resolver,
    )
    return {"ko": mappings.get("ko", {})}
