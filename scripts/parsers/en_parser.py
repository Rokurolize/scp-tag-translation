"""Parse the English SCP tag-list source into validated tag records."""

from __future__ import annotations

import re
from collections.abc import MutableSequence
from pathlib import Path

from scripts.domain.records.tag_records import EnTag
from scripts.parsers.errors import report_source_issue

__all__ = ["parse_en_tags"]

_TAG_PATTERN = re.compile(
    r"^\s*\*\s*\*\*\[https?://[^ ]*/system:page-tags/tag/([^ \]]+)"
    r"(?:\s+[^\]]+)?\]\*\*"
)
_DESC_PATTERN = re.compile(r"\s+--\s*(.*)")
_META_PATTERN = re.compile(r"^\s*\*\s*//\s*(.*?)\s*//")
_QUOTED_VALUE_PATTERN = re.compile(r"'([^']+)'")
_TAB_PATTERN = re.compile(r"^\[\[tab\s+(.+?)\]\]$")


def _normalize_meta_key(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _parse_meta_line(line: str) -> tuple[str, list[str]] | None:
    meta_match = _META_PATTERN.match(line)
    if not meta_match:
        return None

    meta_text = meta_match.group(1).strip()
    if not meta_text:
        return None

    if ":" in meta_text:
        meta_key_text, meta_value_text = meta_text.split(":", 1)
        meta_values = _QUOTED_VALUE_PATTERN.findall(meta_value_text)
        if not meta_values:
            meta_values = [
                v.strip().replace("'", "")
                for v in meta_value_text.split(",")
                if v.strip()
            ]
    else:
        meta_values = _QUOTED_VALUE_PATTERN.findall(meta_text)
        if not meta_values:
            return None
        meta_key_text = meta_text[: meta_text.find("'")]

    meta_key = _normalize_meta_key(meta_key_text)
    if not meta_key:
        return None
    return meta_key, meta_values


def _report_malformed_line(
    input_path: Path,
    line_number: int,
    line: str,
    *,
    current_tag: EnTag | None,
    strict: bool,
    diagnostics: MutableSequence[str] | None,
) -> None:
    if not strict:
        return
    if line.startswith("* **[") and "system:page-tags/tag/" in line:
        report_source_issue(
            input_path,
            line_number,
            "invalid EN tag link",
            diagnostics,
        )
    elif (
        current_tag is not None
        and line.startswith("* //")
        and _parse_meta_line(line) is None
    ):
        report_source_issue(
            input_path,
            line_number,
            "invalid EN metadata",
            diagnostics,
        )


def parse_en_tags(
    input_path: Path,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> list[EnTag]:
    """Parse the Wikidot EN tag list into typed records.

    Strict mode reports tag-shaped lines that cannot be parsed, preserving the
    source location instead of silently publishing an incomplete artifact.
    """

    tags_data: list[EnTag] = []
    current_tag: EnTag | None = None
    current_category: str | None = None

    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            line = line.strip()

            tab_match = _TAB_PATTERN.match(line)
            if tab_match:
                current_category = tab_match.group(1).strip()
                continue
            if line == "[[/tab]]":
                current_category = None
                continue

            tag_match = _TAG_PATTERN.match(line)
            if tag_match:
                if current_tag:
                    tags_data.append(current_tag)

                tag_name = tag_match.group(1)
                desc_match = _DESC_PATTERN.search(line, tag_match.end())
                description = desc_match.group(1).strip() if desc_match else ""

                current_tag = {
                    "name": tag_name,
                    "description": description,
                    "category": current_category,
                    "meta": {},
                }
                continue

            _report_malformed_line(
                input_path,
                line_number,
                line,
                current_tag=current_tag,
                strict=strict,
                diagnostics=diagnostics,
            )

            if current_tag:
                meta_data = _parse_meta_line(line)
                if meta_data:
                    meta_key, meta_values = meta_data
                    metadata = current_tag["meta"]
                    metadata.setdefault(meta_key, []).extend(meta_values)

        if current_tag:
            tags_data.append(current_tag)

    return tags_data
