"""Parse SCP-KO's official EN/JP/KO translation-tag table."""

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

_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")


def _single_valid_jp_target(
    en_values: Iterable[str],
    jp_values: Iterable[str],
) -> str | None:
    del en_values
    values = list(jp_values)
    if len(values) != 1:
        return None
    jp_tag = values[0]
    if jp_tag.casefold() in EMPTY_CELL_MARKERS or any(
        character.isspace() for character in jp_tag
    ):
        return None
    return jp_tag


def _iter_ko_crosswalk_candidates(
    input_path: Path,
) -> Iterable[CrosswalkCandidate]:
    with input_path.open(encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line.startswith("||"):
                continue
            cells = split_wikidot_table_row(line)
            if len(cells) != 3:
                continue
            en_tag, jp_tag, ko_cell = cells
            ko_tags = _KO_LINK_RE.findall(ko_cell)
            jp_tag = jp_tag.strip()
            if len(ko_tags) != 1:
                continue
            yield (
                "ko",
                ko_tags[0],
                [en_tag.strip()] if en_tag.strip() else [],
                [jp_tag] if jp_tag else [],
            )


def parse_ko_crosswalk_raw(input_path: Path) -> CrosswalkMappings:
    mappings = resolve_crosswalk_candidates(
        _iter_ko_crosswalk_candidates(input_path),
        _single_valid_jp_target,
    )
    return {"ko": mappings.get("ko", {})}


def parse_ko_crosswalk(
    input_path: Path,
    resolver: TargetResolver,
) -> CrosswalkMappings:
    mappings = resolve_crosswalk_candidates(
        _iter_ko_crosswalk_candidates(input_path),
        resolver,
    )
    return {"ko": mappings.get("ko", {})}
