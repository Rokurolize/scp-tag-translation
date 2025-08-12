"""Dictionary generator for EN to JP tag mappings."""

import json
from pathlib import Path

from .parsers import parse_en_tags, parse_jp_mappings


def generate_dictionary(
    en_file: Path | None = None, jp_directory: Path | None = None, output_path: Path | None = None
) -> tuple[dict[str, str | None], dict[str, int]]:
    """
    Generate EN to JP tag dictionary from source files.

    Args:
        en_file: Path to EN tags file. If None, uses default.
        jp_directory: Directory containing JP fragment files. If None, uses current directory.
        output_path: Output path for the JSON dictionary. If None, uses default.

    Returns:
        Tuple of (dictionary, statistics)
        - dictionary: Mapping of EN tags to JP tags (or None if unmapped)
        - statistics: Dictionary with 'total', 'mapped', 'unmapped', 'coverage' keys

    Raises:
        FileNotFoundError: If source files are not found.
        ValueError: If no tags are found.
    """
    if output_path is None:
        output_path = Path("dictionaries/en_to_jp.json")

    # Parse source files
    en_tags = parse_en_tags(en_file)
    jp_mappings = parse_jp_mappings(jp_directory)

    # Create dictionary with all EN tags
    dictionary = {}
    for tag in sorted(en_tags):
        dictionary[tag] = jp_mappings.get(tag, None)

    # Calculate statistics
    total = len(dictionary)
    mapped = sum(1 for v in dictionary.values() if v is not None)
    unmapped = total - mapped
    coverage = round(mapped * 100 / total) if total > 0 else 0

    stats = {"total": total, "mapped": mapped, "unmapped": unmapped, "coverage": coverage}

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write dictionary
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)

    return dictionary, stats
