"""Parse SCP-INT's branch tag crosswalk into deterministic JP mappings."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from scripts.parsers.contracts import CrosswalkMappings, TargetResolver
from scripts.parsers.crosswalk_candidates import (
    CrosswalkCandidate,
    resolve_crosswalk_candidates,
)
from scripts.parsers.crosswalk_table import (
    EMPTY_CELL_MARKERS,
    split_wikidot_table_row,
)

_TAG_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")
_HEADER_RE = re.compile(r"^\*\*([A-Z]+)\*\*$")
_SOURCE_COLUMNS = {
    "EN": ("en", "int"),
    "CN": ("cn",),
    "DE": ("de",),
    "ES": ("es",),
    "FR": ("fr",),
    "IT": ("it",),
    "KO": ("ko",),
    "PL": ("pl",),
    "PT": ("pt-br",),
    "TH": ("th",),
    "UA": ("ua",),
    "VN": ("vn",),
    "ZH": ("zh-tr",),
}


def _cell_tags(cell: str) -> list[str]:
    """Return concrete tag values from one crosswalk cell."""
    linked = _TAG_LINK_RE.findall(cell)
    if linked:
        return linked

    values = []
    for value in re.split(r"\s+or\s+", cell.strip()):
        value = value.strip().strip("|*")
        # Wikidot tags cannot contain spaces.  Skipping prose/ambiguous cells is
        # safer than inventing a mapping.
        if (
            value
            and value.casefold() not in EMPTY_CELL_MARKERS
            and not any(character.isspace() for character in value)
        ):
            values.append(value)
    return values


def _cell_for_column(cells: list[str], header: list[str], column: str) -> str:
    """Return a header-selected cell while tolerating short rows."""
    index = header.index(column)
    return cells[index] if index < len(cells) else ""


def _raw_target(
    en_values: Iterable[str],
    jp_values: Iterable[str],
) -> str | None:
    del en_values
    values = list(jp_values)
    return values[0] if len(values) == 1 else None


def _iter_int_crosswalk_candidates(
    input_path: Path,
) -> Iterable[CrosswalkCandidate]:
    """Parse only unambiguous source-tag -> registered-name candidates.

    Rows may repeat and some branch cells intentionally use one local tag for
    multiple EN concepts.  A source tag is emitted only when every occurrence
    points to the same JP cell.
    """

    header: list[str] | None = None

    with input_path.open(encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line.startswith("||"):
                continue
            cells = split_wikidot_table_row(line)
            possible_header = [
                match.group(1) if (match := _HEADER_RE.match(cell)) else ""
                for cell in cells
            ]
            if "JP" in possible_header and "EN" in possible_header:
                header = possible_header
                continue
            if header is None or len(cells) < len(header):
                continue

            en_values = _cell_tags(_cell_for_column(cells, header, "EN"))
            jp_values = _cell_tags(_cell_for_column(cells, header, "JP"))
            for column, branches in _SOURCE_COLUMNS.items():
                for source_tag in _cell_tags(
                    _cell_for_column(cells, header, column)
                    if column in header
                    else ""
                ):
                    for branch in branches:
                        yield branch, source_tag, en_values, jp_values


def parse_int_crosswalk_raw(input_path: Path) -> CrosswalkMappings:
    return resolve_crosswalk_candidates(
        _iter_int_crosswalk_candidates(input_path),
        _raw_target,
    )


def parse_int_crosswalk(
    input_path: Path,
    resolver: TargetResolver,
) -> CrosswalkMappings:
    return resolve_crosswalk_candidates(
        _iter_int_crosswalk_candidates(input_path),
        resolver,
    )
