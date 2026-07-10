"""Parse SCP-KO's official EN/JP/KO translation-tag table."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path


_KO_LINK_RE = re.compile(r"/system:page-tags/tag/([^\s\]]+)")
_EMPTY_MARKERS = {"-", "--", "—", "–", "n/a", "na", "none"}


def _cells(line: str) -> list[str]:
    values = line.split("||")[1:]
    if values and not values[-1].strip():
        values.pop()
    return [value.strip() for value in values]


TargetResolver = Callable[[list[str], list[str]], str | None]


def parse_crosswalk(
    input_filepath: str,
    resolver: TargetResolver | None = None,
) -> dict[str, dict[str, str]]:
    candidates: dict[str, set[str]] = defaultdict(set)
    with open(input_filepath, encoding="utf-8") as source:
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
                target = resolver([en_tag.strip()] if en_tag.strip() else [], [jp_tag] if jp_tag else [])
            if target is not None:
                candidates[ko_tags[0]].add(target)

    mapping = {
        source_tag: next(iter(targets))
        for source_tag, targets in candidates.items()
        if len(targets) == 1
    }
    return {"ko": dict(sorted(mapping.items()))}


def parse(
    input_filepath: str,
    output_filepath: str,
    resolver: TargetResolver | None = None,
) -> None:
    mappings = parse_crosswalk(input_filepath, resolver)
    output = Path(output_filepath)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(mappings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"KO crosswalk: {len(mappings['ko'])} mappings -> {output_filepath}"
    )
