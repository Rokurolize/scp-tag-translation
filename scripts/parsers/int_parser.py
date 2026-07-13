"""Parse SCP-INT's branch tag crosswalk into deterministic JP mappings."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from scripts.parsers.contracts import CrosswalkMappings, TargetResolver

_TAG_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")
_HEADER_RE = re.compile(r"^\*\*([A-Z]+)\*\*$")
_EMPTY_MARKERS = {"-", "--", "—", "–", "n/a", "na", "none"}
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


def _cells(line: str) -> list[str]:
    values = line.split("||")[1:]
    if values and not values[-1].strip():
        values.pop()
    return [value.strip() for value in values]


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
            and value.casefold() not in _EMPTY_MARKERS
            and not any(character.isspace() for character in value)
        ):
            values.append(value)
    return values


def parse(
    input_path: Path,
    resolver: TargetResolver | None = None,
) -> CrosswalkMappings:
    """Parse only unambiguous source-tag -> registered-name candidates.

    Rows may repeat and some branch cells intentionally use one local tag for
    multiple EN concepts.  A source tag is emitted only when every occurrence
    points to the same JP cell.
    """

    candidates: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    header: list[str] | None = None

    with input_path.open(encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line.startswith("||"):
                continue
            cells = _cells(line)
            possible_header = [
                match.group(1) if (match := _HEADER_RE.match(cell)) else ""
                for cell in cells
            ]
            if "JP" in possible_header and "EN" in possible_header:
                header = possible_header
                continue
            if header is None or len(cells) < len(header):
                continue

            row = dict(zip(header, cells, strict=False))
            en_values = _cell_tags(row.get("EN", ""))
            jp_values = _cell_tags(row.get("JP", ""))
            if resolver is None:
                jp_tag = jp_values[0] if len(jp_values) == 1 else None
            else:
                jp_tag = resolver(en_values, jp_values)
            if jp_tag is None:
                continue

            for column, branches in _SOURCE_COLUMNS.items():
                for source_tag in _cell_tags(row.get(column, "")):
                    for branch in branches:
                        candidates[branch][source_tag].add(jp_tag)

    mappings: dict[str, dict[str, str]] = {}
    for branch, branch_candidates in candidates.items():
        mappings[branch] = {
            source_tag: next(iter(targets))
            for source_tag, targets in branch_candidates.items()
            if len(targets) == 1
        }
    return {
        branch: dict(sorted(mapping.items()))
        for branch, mapping in sorted(mappings.items())
    }
