"""Parse SCP-KO's official EN/JP/KO translation-tag table."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from scripts.parsers.contracts import CrosswalkMappings, TargetResolver

_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")
_EMPTY_MARKERS = {"-", "--", "—", "–", "n/a", "na", "none"}


def _cells(line: str) -> list[str]:
    values = line.split("||")[1:]
    if values and not values[-1].strip():
        values.pop()
    return [value.strip() for value in values]


def parse(
    input_path: Path,
    resolver: TargetResolver | None = None,
) -> CrosswalkMappings:
    candidates: dict[str, set[str]] = defaultdict(set)
    with input_path.open(encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line.startswith("||"):
                continue
            cells = _cells(line)
            if len(cells) != 3:
                continue
            en_tag, jp_tag, ko_cell = cells
            ko_tags = _KO_LINK_RE.findall(ko_cell)
            jp_tag = jp_tag.strip()
            if len(ko_tags) != 1 or not jp_tag:
                if len(ko_tags) != 1 or resolver is None:
                    continue
            if resolver is None and (
                jp_tag.casefold() in _EMPTY_MARKERS
                or any(character.isspace() for character in jp_tag)
            ):
                continue
            if resolver is None:
                target = jp_tag
            else:
                target = resolver(
                    [en_tag.strip()] if en_tag.strip() else [],
                    [jp_tag] if jp_tag else [],
                )
            if target is not None:
                candidates[ko_tags[0]].add(target)

    mapping = {
        source_tag: next(iter(targets))
        for source_tag, targets in candidates.items()
        if len(targets) == 1
    }
    return {"ko": dict(sorted(mapping.items()))}
