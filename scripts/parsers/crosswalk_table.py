"""Shared Wikidot table syntax used by official tag crosswalk parsers."""

from __future__ import annotations

__all__ = ["EMPTY_CELL_MARKERS", "TAG_LINK_MARKER", "split_wikidot_table_row"]


EMPTY_CELL_MARKERS = frozenset({"-", "--", "—", "–", "n/a", "na", "none"})
TAG_LINK_MARKER = "/system:page-tags/tag/"


def split_wikidot_table_row(line: str) -> list[str]:
    cells = line.split("||")[1:]
    if cells and not cells[-1].strip():
        cells.pop()
    return [cell.strip() for cell in cells]
