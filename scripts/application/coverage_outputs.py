"""Serialize application-owned branch coverage artifacts."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.domain.tag_coverage_models import ApplicationInventory, Coverage

__all__ = ["write_application_inventory_tsv", "write_coverage_tsv"]


def write_coverage_tsv(path: Path, coverage: Coverage) -> None:
    """Serialize classified branch coverage rows as UTF-8 TSV; I/O errors propagate as OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "branch",
        "tag",
        "rank",
        "page_count",
        "status",
        "recognized_by_jp_policy",
        "jp_tag",
        "replacement",
        "translation_action",
        "copy_allowed",
        "display_tag",
        "sample_slugs",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for branch_entry in coverage["branches"]:
            branch = branch_entry["branch"]
            for tag_entry in branch_entry["tags"]:
                writer.writerow({
                    "branch": branch,
                    "tag": tag_entry["tag"],
                    "rank": tag_entry["rank"],
                    "page_count": tag_entry["page_count"],
                    "status": tag_entry["status"],
                    "recognized_by_jp_policy": str(
                        tag_entry["recognized_by_jp_policy"]
                    ).lower(),
                    "jp_tag": tag_entry["jp_tag"] or "",
                    "replacement": tag_entry["replacement"] or "",
                    "translation_action": tag_entry["translation_action"],
                    "copy_allowed": str(tag_entry["copy_allowed"]).lower(),
                    "display_tag": tag_entry["display_tag"] or "",
                    "sample_slugs": ",".join(tag_entry["sample_slugs"]),
                })


def write_application_inventory_tsv(
    path: Path,
    inventory: ApplicationInventory,
) -> None:
    """Serialize the tag-application inventory as UTF-8 TSV; I/O errors propagate as OSError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "site",
        "branch",
        "source_tag",
        "display_tag",
        "page_count",
        "sample_slugs",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for branch_entry in inventory["branches"]:
            for tag_entry in branch_entry["tags"]:
                writer.writerow({
                    "site": branch_entry["site"],
                    "branch": branch_entry["branch"],
                    "source_tag": tag_entry["tag"],
                    "display_tag": tag_entry["display_tag"],
                    "page_count": tag_entry["page_count"],
                    "sample_slugs": ",".join(tag_entry["sample_slugs"]),
                })
