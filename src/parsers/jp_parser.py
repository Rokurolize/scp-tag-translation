"""Parser for Japanese SCP Wiki tags."""

import re
from pathlib import Path

from ..logger import logger

# Pattern that handles both //(tag)// and (//tag//) formats
JP_TAG_PATTERN = re.compile(
    r"\*\*\[\[\[/system:page-tags/tag/([^|]+)\|[^]]+\]\]\]\*\*"
    r"(?:\s*(?://\(([^)]+)\)//|\(//([^/]+)//\)))?"
)


def parse_jp_mappings(directory: Path | None = None, pattern: str | None = None) -> dict[str, str]:
    """
    Extract JP tag mappings from fragment files.

    Args:
        directory: Directory containing JP fragment files. If None, uses current directory.
        pattern: Glob pattern for JP files. If None, uses default.

    Returns:
        Dictionary mapping EN tags to JP tags.

    Raises:
        FileNotFoundError: If no JP fragment files are found.
    """
    if directory is None:
        directory = Path(".")

    if pattern is None:
        pattern = "scp-jp*tag-list*.wikidot"

    fragments = list(directory.glob(pattern))
    if not fragments:
        raise FileNotFoundError(f"No JP fragment files found in {directory} matching pattern '{pattern}'")

    mappings = {}
    errors = []

    for filepath in fragments:
        try:
            with open(filepath, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    try:
                        # Use findall to get ALL matches on the line (handles multi-tag lines)
                        matches = JP_TAG_PATTERN.findall(line)
                        for jp_tag, en_standard, en_reversed in matches:
                            jp_tag = jp_tag.strip()
                            # Use whichever pattern matched
                            en_tag = en_standard or en_reversed
                            if en_tag:
                                en_tag = en_tag.strip()
                                # First occurrence wins (no overwrites)
                                if en_tag not in mappings:
                                    mappings[en_tag] = jp_tag
                                    logger.debug(f"Mapped {en_tag} -> {jp_tag}")

                                # Also create underscore variant if EN doesn't start with underscore
                                if not en_tag.startswith("_"):
                                    underscore_variant = f"_{en_tag}"
                                    if underscore_variant not in mappings:
                                        mappings[underscore_variant] = jp_tag
                                        logger.debug(f"Created variant {underscore_variant} -> {jp_tag}")
                    except Exception as e:
                        logger.warning(f"Error parsing line {line_no} in {filepath}: {e}")
                        continue
        except Exception as e:
            error_msg = f"Failed to parse {filepath}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue

    # If we got some mappings, return them even if there were errors
    if mappings:
        if errors:
            logger.warning(f"Parsed with {len(errors)} errors: {errors[:3]}...")
        return mappings

    # If no mappings at all, raise an error
    if errors:
        raise ValueError(f"Failed to parse any files successfully: {errors}")

    return mappings
