import re
import json
import glob
import os
from pathlib import Path

# タグリンクと任意のENタグ表記のペアにマッチ
# 形式: **[[[/system:page-tags/tag/{slug}|{display}]]]** //(en-tag)//
_PAIR_RE = re.compile(
    r"\*\*\[\[\[/system:page-tags/tag/([^\|]+)\|([^\]]*)\]\]\]\*\*"
    r"(?:\s*//\(([^)]+)\)//)?"
)


def parse(sources_jp_dir: str, output_filepath: str) -> None:
    """
    sources/jp/ 以下のフラグメントファイルを解析してJSONに出力する。

    フラグメントファイルの形式:
      * **[[[/system:page-tags/tag/{jp-tag}|{display}]]]** //(en-tag)// - description
      （//(en-tag)// はJP固有タグの場合は省略される）
      複数タグが ` / ` で同一行に並ぶこともある。

    Args:
        sources_jp_dir: JPフラグメントファイルのディレクトリ (sources/jp/)
        output_filepath: 出力ファイルパス (data/jp_tags.json)
    """
    tags_data = []
    seen_names: set[str] = set()

    fragment_files = sorted(
        glob.glob(os.path.join(sources_jp_dir, "fragment-*.txt"))
    )
    if not fragment_files:
        print(f"警告: JPフラグメントファイルが見つかりません: {sources_jp_dir}")

    for filepath in fragment_files:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if "**[[[/system:page-tags/tag/" not in line:
                    continue

                matches = list(_PAIR_RE.finditer(line))
                if not matches:
                    continue

                # 最後のマッチ終了位置以降から説明文を抽出
                last_end = matches[-1].end()
                remaining = line[last_end:]
                desc_match = re.search(r"\s*-\s*(.+)", remaining)
                description = desc_match.group(1).strip() if desc_match else ""

                for m in matches:
                    slug = m.group(1)   # URLスラッグ = JPタグ名
                    en_tag = m.group(3) # ENタグ名（省略時は None）

                    if slug in seen_names:
                        continue
                    seen_names.add(slug)

                    tags_data.append({
                        "name": slug,
                        "en_tag": en_tag if en_tag else None,
                        "description": description,
                    })

    Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)

    print(f"JP: {len(tags_data)} タグを解析 → {output_filepath}")
