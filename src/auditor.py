"""Audit functionality for tag mappings."""

import csv
from pathlib import Path


def audit_mappings(
    en_tags: set[str], jp_directory: Path | None = None, output_csv: Path | None = None
) -> tuple[list[dict], dict[str, int]]:
    """
    Audit EN tags against JP source files.

    Args:
        en_tags: Set of EN tags to audit.
        jp_directory: Directory containing JP files. If None, uses current directory.
        output_csv: Path to write CSV results. If None, doesn't write CSV.

    Returns:
        Tuple of (results, statistics)
        - results: List of audit results for each tag
        - statistics: Dictionary with audit statistics
    """
    if jp_directory is None:
        jp_directory = Path(".")

    jp_files = list(jp_directory.glob("scp-jp*.wikidot"))
    if not jp_files:
        raise FileNotFoundError(f"No JP files found in {jp_directory}")

    results = []

    for tag in sorted(en_tags):
        found = False

        # Try both with and without underscore prefix
        tags_to_try = [tag]
        if tag.startswith("_"):
            tags_to_try.append(tag[1:])  # Try without underscore

        # Search all JP files
        for jp_file in jp_files:
            with open(jp_file, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    # Check each variant
                    for variant in tags_to_try:
                        # Check both parentheses formats
                        if f"//({variant})//" in line or f"(//{variant}//)" in line:
                            results.append(
                                {
                                    "en_tag": tag,
                                    "found_as": variant,
                                    "status": "FOUND",
                                    "file": jp_file.name,
                                    "line": line_no,
                                    "text": line.strip()[:100],
                                }
                            )
                            found = True
                            break

                    if found:
                        break

            if found:
                break

        if not found:
            results.append({"en_tag": tag, "found_as": "", "status": "NOT_FOUND", "file": "", "line": "", "text": ""})

    # Calculate statistics
    found_exact = sum(1 for r in results if r["status"] == "FOUND" and r["en_tag"] == r["found_as"])
    found_without_underscore = sum(1 for r in results if r["status"] == "FOUND" and r["en_tag"] != r["found_as"])
    not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")
    total = len(results)

    statistics = {
        "total": total,
        "found_exact": found_exact,
        "found_without_underscore": found_without_underscore,
        "total_found": found_exact + found_without_underscore,
        "not_found": not_found,
        "coverage": round((found_exact + found_without_underscore) * 100 / total) if total > 0 else 0,
    }

    # Write CSV if requested
    if output_csv:
        with open(output_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["en_tag", "found_as", "status", "file", "line", "text"])
            writer.writeheader()
            writer.writerows(results)

    return results, statistics
