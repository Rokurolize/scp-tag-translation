import re
import json
import os
from pathlib import Path

# タグリンクと任意のENタグ表記のペアにマッチ
# 形式: **[[[/system:page-tags/tag/{slug}|{display}]]]** //(en-tag)//
# 一部ソースには /system/page-tags/tag/ 形式も混在している。
_PAIR_RE = re.compile(
    r"\*\*\[\[\[/system(?::|/)page-tags/tag/([^\|]+)\|([^\]]*)\]\]\]\*\*"
    r"(?:\s*//\(([^)]+)\)//)?"
)

# 説明文中の単一置換先を抽出するパターン
# 例: "JPでは//世界観//タグに置換してください", "//scp//タグに置換してください"
_TAG_REF_RE = re.compile(r"//([^/]+)//")
_REPLACE_RE = re.compile(
    r"//([^/]+)//(?:タグ)?(?:へ|に)置(?:き)?換(?:え|し)てください"
)
_SECTION_RE = re.compile(r"^\+{3,}\s*([A-Z]{2,3})\b")

# SCP-JP's tag list uses Font Awesome glyphs as the machine-visible source of
# truth for restricted tags.  The surrounding variation selector/comma markup
# has changed over time, but these private-use code points have stayed stable.
_USE_RESTRICTED_ICON = "\uf05e"
_EDIT_RESTRICTED_ICON = "\uf023"
_TRANSLATION_EXEMPT_ICON = "\uf084"

# Only these include fragments define registered JP tags.  tag-list's FAQ and
# unused-tag fragments also contain tag links, but those links are references,
# not additional registered definitions.
_REGISTERED_FRAGMENT_NAMES = (
    "tag-list.txt",
    "fragment-basic.txt",
    "fragment-series.txt",
    "fragment-universe.txt",
    "fragment-event.txt",
)


def _extract_single_replacement(description: str) -> str | None:
    replacements = [value.strip() for value in _REPLACE_RE.findall(description)]
    tag_refs = [value.strip() for value in _TAG_REF_RE.findall(description)]
    if len(replacements) != 1:
        return None
    if len(tag_refs) != 1:
        return None
    replacement = replacements[0]
    return replacement or None


def _iter_uncommented_lines(filepath: str):
    """Wikidotコメント [!-- ... --] を除外して行を返す。"""
    in_comment = False
    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line_parts: list[str] = []
            cursor = 0

            while cursor < len(raw_line):
                if in_comment:
                    comment_end = raw_line.find("--]", cursor)
                    if comment_end == -1:
                        cursor = len(raw_line)
                    else:
                        in_comment = False
                        cursor = comment_end + len("--]")
                    continue

                comment_start = raw_line.find("[!--", cursor)
                if comment_start == -1:
                    line_parts.append(raw_line[cursor:])
                    break

                line_parts.append(raw_line[cursor:comment_start])
                comment_end = raw_line.find("--]", comment_start + len("[!--"))
                if comment_end == -1:
                    in_comment = True
                    break
                cursor = comment_end + len("--]")

            uncommented = "".join(line_parts)
            if uncommented.strip():
                yield uncommented


def parse_unused(filepath: str, output_filepath: str) -> None:
    """
    fragment-unused.txt から支部別の非使用タグと置換先（単一タグのみ）を抽出してJSONに出力する。

    Args:
        filepath: fragment-unused.txt のパス
        output_filepath: 出力ファイルパス (data/deprecated_tags.json)
    """
    results = []
    seen_source_tags: set[tuple[str, str]] = set()
    source_lang = "EN"

    for line in _iter_uncommented_lines(filepath):
        section_match = _SECTION_RE.match(line.strip())
        if section_match:
            source_lang = section_match.group(1)
            continue

        if "**[[[/system" not in line or "page-tags/tag/" not in line:
            continue
        matches = list(_PAIR_RE.finditer(line))
        if not matches:
            continue

        # 最後のマッチ終了位置以降から説明文を抽出
        last_end = matches[-1].end()
        desc_m = re.search(r"\s*-\s*(.+)", line[last_end:])
        description = desc_m.group(1).strip() if desc_m else ""

        # 単一置換先のみ抽出（複数候補や文脈依存の置換はスキップ）
        replacement = _extract_single_replacement(description)

        for m in matches:
            en_tag = m.group(3).strip() if m.group(3) else None
            if not en_tag:
                continue
            source_key = (source_lang, en_tag)
            if source_key in seen_source_tags:
                continue
            seen_source_tags.add(source_key)

            results.append({
                "source_lang": source_lang,
                "en_tag": en_tag,
                "replacement": replacement,
                "description": description,
            })

    Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"JP(未使用): {len(results)} タグを解析 → {output_filepath}")


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
    tags_by_name: dict[str, dict] = {}

    fragment_files = [
        os.path.join(sources_jp_dir, name)
        for name in _REGISTERED_FRAGMENT_NAMES
        if os.path.exists(os.path.join(sources_jp_dir, name))
    ]
    if not fragment_files:
        print(f"警告: JPフラグメントファイルが見つかりません: {sources_jp_dir}")

    for filepath in fragment_files:
        for line in _iter_uncommented_lines(filepath):
            if "**[[[/system" not in line or "page-tags/tag/" not in line:
                continue

            matches = list(_PAIR_RE.finditer(line))
            if not matches:
                continue

            # Restriction icons precede the first tag definition and apply to
            # every tag definition on that list item.
            prefix = line[: matches[0].start()]
            edit_restricted = _EDIT_RESTRICTED_ICON in prefix
            use_restricted = edit_restricted or _USE_RESTRICTED_ICON in prefix
            translation_exempt = _TRANSLATION_EXEMPT_ICON in prefix

            # 最後のマッチ終了位置以降から説明文を抽出
            last_end = matches[-1].end()
            remaining = line[last_end:]
            desc_match = re.search(r"\s*-\s*(.+)", remaining)
            description = desc_match.group(1).strip() if desc_match else ""

            for m in matches:
                slug = m.group(1).strip()   # URLスラッグ = JPタグ名
                # ENタグ名（省略時は None）
                en_tag = m.group(3).strip() if m.group(3) else None

                if not slug:
                    continue

                entry = tags_by_name.get(slug)
                if entry is None:
                    entry = {
                        "name": slug,
                        # Kept for compatibility with existing data consumers.
                        # New code should use source_tags so a JP tag can retain
                        # every foreign-language alias listed in multiple tabs.
                        "en_tag": en_tag if en_tag else None,
                        "source_tags": [],
                        "description": description,
                        "use_restricted": use_restricted,
                        "edit_restricted": edit_restricted,
                        "translation_exempt": translation_exempt,
                    }
                    tags_by_name[slug] = entry
                else:
                    if not entry["description"] and description:
                        entry["description"] = description
                    entry["use_restricted"] = (
                        entry["use_restricted"] or use_restricted
                    )
                    entry["edit_restricted"] = (
                        entry["edit_restricted"] or edit_restricted
                    )
                    entry["translation_exempt"] = (
                        entry["translation_exempt"] or translation_exempt
                    )

                if en_tag and en_tag not in entry["source_tags"]:
                    entry["source_tags"].append(en_tag)
                    if entry["en_tag"] is None:
                        entry["en_tag"] = en_tag

    tags_data = list(tags_by_name.values())

    Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)

    print(f"JP: {len(tags_data)} タグを解析 → {output_filepath}")
