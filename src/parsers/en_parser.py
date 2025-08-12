"""Parser for English SCP Wiki tags."""

import re
from pathlib import Path

# Pattern compiled at module level for performance
EN_TAG_PATTERN = re.compile(r"\*\s*\*\*\[https://[^/]+/system:page-tags/tag/([\w-]+)\s+[^]]+\]\*\*")


def parse_en_tags(filepath: Path | None = None) -> set[str]:
    """
    Extract EN tags from tech hub list.

    Args:
        filepath: Path to the EN tags file. If None, uses default.

    Returns:
        Set of English tag names.

    Raises:
        FileNotFoundError: If the specified file doesn't exist.
        ValueError: If no tags are found in the file.
    """
    if filepath is None:
        filepath = Path("05command_tech-hub-tag-list.wikidot")

    if not filepath.exists():
        raise FileNotFoundError(f"EN tags file not found: {filepath}")

    tags = set()
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if match := EN_TAG_PATTERN.search(line):
                tags.add(match.group(1))

    if not tags:
        raise ValueError(f"No EN tags found in {filepath}")

    return tags
