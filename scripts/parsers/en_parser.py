import re
import json
from pathlib import Path
from typing import TypeAlias

TagMeta: TypeAlias = dict[str, list[str]]
TagData: TypeAlias = dict[str, str | TagMeta]

tag_pattern = re.compile(r"^\s*\*\s*\*\*\[https?://[^ ]+\s+([^\]]+)\]\*\*")
desc_pattern = re.compile(r"--\s*(.*)")
meta_pattern = re.compile(r"^\s*\*\s*//\s*([^:]+):\s*(.*)\s*//")


def parse(input_filepath: str, output_filepath: str) -> None:
    """
    Wikidot形式のENタグリストを解析してJSONに出力する。

    Args:
        input_filepath: 入力ファイルパス (sources/en/tag-list.txt)
        output_filepath: 出力ファイルパス (data/en_tags.json)
    """
    tags_data: list[TagData] = []
    current_tag: TagData | None = None

    with open(input_filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

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
                    "meta": {},
                }
                continue

            if current_tag:
                meta_match = meta_pattern.match(line)
                if meta_match:
                    meta_key = meta_match.group(1).strip().lower().replace(" ", "-")
                    meta_value_str = meta_match.group(2).strip()
                    meta_values = [
                        v.strip().replace("'", "")
                        for v in meta_value_str.split(",")
                        if v.strip()
                    ]
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
