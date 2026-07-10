import re
import json
from pathlib import Path
from typing import TypeAlias

TagMeta: TypeAlias = dict[str, list[str]]
TagData: TypeAlias = dict[str, str | TagMeta]

tag_pattern = re.compile(
    r"^\s*\*\s*\*\*\[https?://[^ ]*/system:page-tags/tag/([^ \]]+)"
    r"(?:\s+[^\]]+)?\]\*\*"
)
desc_pattern = re.compile(r"--\s*(.*)")
meta_pattern = re.compile(r"^\s*\*\s*//\s*(.*?)\s*//")
quoted_value_pattern = re.compile(r"'([^']+)'")
tab_pattern = re.compile(r"^\[\[tab\s+(.+?)\]\]$")


def _normalize_meta_key(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _parse_meta_line(line: str) -> tuple[str, list[str]] | None:
    meta_match = meta_pattern.match(line)
    if not meta_match:
        return None

    meta_text = meta_match.group(1).strip()
    if not meta_text:
        return None

    if ":" in meta_text:
        meta_key_text, meta_value_text = meta_text.split(":", 1)
        meta_values = quoted_value_pattern.findall(meta_value_text)
        if not meta_values:
            meta_values = [
                v.strip().replace("'", "")
                for v in meta_value_text.split(",")
                if v.strip()
            ]
    else:
        meta_values = quoted_value_pattern.findall(meta_text)
        if not meta_values:
            return None
        meta_key_text = meta_text[: meta_text.find("'")]

    meta_key = _normalize_meta_key(meta_key_text)
    if not meta_key:
        return None
    return meta_key, meta_values


def parse(input_filepath: str, output_filepath: str) -> None:
    """
    Wikidot形式のENタグリストを解析してJSONに出力する。

    Args:
        input_filepath: 入力ファイルパス (sources/en/tag-list.txt)
        output_filepath: 出力ファイルパス (data/en_tags.json)
    """
    tags_data: list[TagData] = []
    current_tag: TagData | None = None
    current_category: str | None = None

    with open(input_filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            tab_match = tab_pattern.match(line)
            if tab_match:
                current_category = tab_match.group(1).strip()
                continue
            if line == "[[/tab]]":
                current_category = None
                continue

            tag_match = tag_pattern.match(line)
            if tag_match:
                if current_tag:
                    tags_data.append(current_tag)

                tag_name = tag_match.group(1)
                desc_match = desc_pattern.search(line)
                description = desc_match.group(1).strip() if desc_match else ""

                current_tag = {
                    "name": tag_name,
                    "description": description,
                    "category": current_category,
                    "meta": {},
                }
                continue

            if current_tag:
                meta_data = _parse_meta_line(line)
                if meta_data:
                    meta_key, meta_values = meta_data
                    if isinstance(current_tag["meta"], dict):
                        if meta_key not in current_tag["meta"]:
                            current_tag["meta"][meta_key] = []
                        current_tag["meta"][meta_key].extend(meta_values)

        if current_tag:
            tags_data.append(current_tag)

    Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)

    print(f"EN: {len(tags_data)} タグを解析 → {output_filepath}")
