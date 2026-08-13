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
from scripts.parsers.crosswalk_table import split_wikidot_table_row

_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")


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


def parse_ko_crosswalk(
    input_path: Path,
    resolver: TargetResolver,
) -> CrosswalkMappings:
    mappings = resolve_crosswalk_candidates(
        _iter_ko_crosswalk_candidates(input_path),
        resolver,
    )
    return {"ko": mappings.get("ko", {})}
