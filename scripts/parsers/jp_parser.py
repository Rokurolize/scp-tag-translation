"""Parse SCP-JP tag-list fragments and unused-tag records."""

from __future__ import annotations

import re
from collections.abc import Iterator, MutableSequence
from dataclasses import dataclass
from pathlib import Path

from scripts.domain.errors import InvalidDomainInputError
from scripts.domain.records.tag_records import DeprecatedTag, JpTag
from scripts.parsers.errors import report_source_issue

__all__ = ["parse_jp_tags", "parse_unused_tag_records"]

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
_REPLACE_RE = re.compile(r"//([^/]+)//(?:タグ)?(?:へ|に)置(?:き)?換(?:え|し)てください")
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


@dataclass(frozen=True)
class _TagParseContext:
    path: Path
    line_number: int
    strict: bool
    diagnostics: MutableSequence[str] | None


def _extract_single_replacement(description: str) -> str | None:
    replacements = [value.strip() for value in _REPLACE_RE.findall(description)]
    tag_refs = [value.strip() for value in _TAG_REF_RE.findall(description)]
    if len(replacements) != 1:
        return None
    if len(tag_refs) != 1:
        return None
    replacement = replacements[0]
    return replacement or None


def _iter_uncommented_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Wikidotコメント [!-- ... --] を除外して行を返す。"""
    in_comment = False
    with path.open("r", encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, 1):
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
                yield line_number, uncommented


def parse_unused_tag_records(
    source_path: Path,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> list[DeprecatedTag]:
    """Parse source-language unused tags and deterministic replacements.

    In strict mode, malformed tag links are reported through ``diagnostics``
    when supplied; without a sink, the parser raises the source parse error.
    """

    results: list[DeprecatedTag] = []
    seen_source_tags: set[tuple[str, str]] = set()
    source_lang = "EN"

    for line_number, line in _iter_uncommented_lines(source_path):
        section_match = _SECTION_RE.match(line.strip())
        if section_match:
            source_lang = section_match.group(1)
            continue

        if "**[[[/system" not in line or "page-tags/tag/" not in line:
            continue
        matches = list(_PAIR_RE.finditer(line))
        if not matches:
            if strict:
                report_source_issue(
                    source_path,
                    line_number,
                    "invalid JP tag link",
                    diagnostics,
                )
            continue

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

            results.append(
                {
                    "source_lang": source_lang,
                    "source_tag": en_tag,
                    "replacement": replacement,
                    "description": description,
                }
            )

    return results


def _registered_tag_entries(
    line: str,
    context: _TagParseContext,
    matches: list[re.Match[str]],
) -> list[JpTag]:
    prefix = line[: matches[0].start()]
    edit_restricted = _EDIT_RESTRICTED_ICON in prefix
    use_restricted = edit_restricted or _USE_RESTRICTED_ICON in prefix
    translation_exempt = _TRANSLATION_EXEMPT_ICON in prefix

    remaining = line[matches[-1].end() :]
    desc_match = re.search(r"\s*-\s*(.+)", remaining)
    description = desc_match.group(1).strip() if desc_match else ""

    entries: list[JpTag] = []
    for match in matches:
        name = match.group(1).strip()
        if not name:
            if context.strict:
                report_source_issue(
                    context.path,
                    context.line_number,
                    "empty JP tag name",
                    context.diagnostics,
                )
            continue

        source_tag = match.group(3).strip() if match.group(3) else None
        entries.append(
            JpTag(
                name=name,
                source_tags=[source_tag] if source_tag else [],
                description=description,
                use_restricted=use_restricted,
                edit_restricted=edit_restricted,
                translation_exempt=translation_exempt,
            )
        )
    return entries


def _merge_jp_tag(tags_by_name: dict[str, JpTag], incoming: JpTag) -> None:
    entry = tags_by_name.get(incoming["name"])
    if entry is None:
        tags_by_name[incoming["name"]] = incoming
        return

    if not entry["description"] and incoming["description"]:
        entry["description"] = incoming["description"]
    entry["use_restricted"] = entry["use_restricted"] or incoming["use_restricted"]
    entry["edit_restricted"] = entry["edit_restricted"] or incoming["edit_restricted"]
    entry["translation_exempt"] = entry["translation_exempt"] or incoming["translation_exempt"]

    for source_tag in incoming["source_tags"]:
        if source_tag not in entry["source_tags"]:
            entry["source_tags"].append(source_tag)


def parse_jp_tags(
    source_dir: Path,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> list[JpTag]:
    """Parse registered JP tag fragments into canonical tag records.

    In strict mode, malformed links or empty names are reported through
    ``diagnostics`` when supplied; without a sink, the parser raises the source
    parse error. Missing registered fragments raise InvalidDomainInputError.
    """

    tags_by_name: dict[str, JpTag] = {}

    fragment_files = [
        source_dir / name
        for name in _REGISTERED_FRAGMENT_NAMES
        if (source_dir / name).exists()
    ]
    if not fragment_files:
        raise InvalidDomainInputError(
            f"JPフラグメントファイルが見つかりません: {source_dir}"
        )

    for filepath in fragment_files:
        for line_number, line in _iter_uncommented_lines(filepath):
            if "**[[[/system" not in line or "page-tags/tag/" not in line:
                continue
            matches = list(_PAIR_RE.finditer(line))
            if not matches:
                if strict:
                    report_source_issue(
                        filepath,
                        line_number,
                        "invalid JP tag link",
                        diagnostics,
                    )
                continue
            for entry in _registered_tag_entries(
                line,
                _TagParseContext(
                    path=filepath,
                    line_number=line_number,
                    strict=strict,
                    diagnostics=diagnostics,
                ),
                matches,
            ):
                _merge_jp_tag(tags_by_name, entry)

    return list(tags_by_name.values())
