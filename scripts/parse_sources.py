#!/usr/bin/env python3
"""Parse synchronized Wikidot tag sources into generated JSON records."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atomic_output import publish_files_atomically
from scripts.parsers import (
    branch_guide_parser,
    en_parser,
    int_parser,
    jp_parser,
    ko_parser,
)
from scripts.parsers.crosswalk_resolver import CrosswalkResolver
from scripts.tag_models import DeprecatedTag, JpTag
from scripts.tag_policy import EN_CROSSWALK_SEMANTIC_REPLACEMENTS
from scripts.tag_validation import validate_deprecated_tags, validate_jp_tags

Language = Literal["en", "jp", "crosswalks", "all"]
LANGUAGES: tuple[Language, ...] = ("en", "jp", "crosswalks", "all")

ROOT = Path(__file__).resolve().parent.parent
SOURCES_EN = ROOT / "sources" / "en" / "tag-list.txt"
SOURCES_JP = ROOT / "sources" / "jp"
SOURCES_JP_UNUSED = SOURCES_JP / "fragment-unused.txt"
SOURCES_INT = ROOT / "sources" / "int" / "tag-guide.txt"
SOURCES_KO = ROOT / "sources" / "ko" / "translate-tags.txt"
DATA_EN = ROOT / "data" / "en_tags.json"
DATA_JP = ROOT / "data" / "jp_tags.json"
DATA_DEPRECATED = ROOT / "data" / "deprecated_tags.json"
DATA_INT_CROSSWALK = ROOT / "data" / "int_tag_crosswalk.json"
DATA_KO_CROSSWALK = ROOT / "data" / "ko_tag_crosswalk.json"
DATA_BRANCH_GUIDE_CROSSWALK = ROOT / "data" / "branch_guide_crosswalk.json"

BRANCH_GUIDE_SOURCES: Mapping[str, tuple[Path, ...]] = {
    "cn": (ROOT / "sources" / "cn" / "tag-guide.txt",),
    "de": (ROOT / "sources" / "de" / "tag-guide.txt",),
    "es": (ROOT / "sources" / "es" / "tag-guide.txt",),
    "fr": (ROOT / "sources" / "fr" / "guide-des-tags.txt",),
    "it": (ROOT / "sources" / "it" / "tag-guide.txt",),
    "pl": (ROOT / "sources" / "pl" / "tag-list.txt",),
    "pt-br": (ROOT / "sources" / "pt-br" / "fragment-lista-mestra.txt",),
    "th": (ROOT / "sources" / "th" / "tag-list.txt",),
    "ua": (ROOT / "sources" / "ua" / "tag-guide.txt",),
    "vn": (
        ROOT / "sources" / "vn" / "fragment-tag-guide-for-translator.txt",
    ),
    "zh-tr": (
        ROOT / "sources" / "zh-tr" / "fragment-base-tag.txt",
        ROOT / "sources" / "zh-tr" / "fragment-characteristic-tag.txt",
        ROOT / "sources" / "zh-tr" / "fragment-genre-and-theme-tag.txt",
        ROOT / "sources" / "zh-tr" / "fragment-other-tag.txt",
        ROOT / "sources" / "zh-tr" / "fragment-internationality-tag.txt",
    ),
}


@dataclass(frozen=True)
class ParseBatch:
    outputs: Mapping[Path, object]
    messages: tuple[str, ...]


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label}が見つかりません: {path}")


def _require_branch_guides() -> None:
    missing = [
        path
        for paths in BRANCH_GUIDE_SOURCES.values()
        for path in paths
        if not path.is_file()
    ]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(
            f"支部公式タグガイドが見つかりません:\n{formatted}"
        )


def _load_json_array(path: Path, label: str) -> list[object]:
    _require_file(path, label)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{label}はJSON配列である必要があります: {path}")
    return value


def _resolver(
    jp_tags: list[JpTag],
    deprecated_tags: list[DeprecatedTag],
) -> CrosswalkResolver:
    return CrosswalkResolver(
        jp_tags,
        deprecated_tags,
        EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    )


def collect_outputs(language: Language) -> ParseBatch:
    if language not in LANGUAGES:
        raise ValueError(f"未対応の解析対象です: {language}")
    outputs: dict[Path, object] = {}
    messages = []
    jp_tags: list[JpTag] | None = None
    deprecated_tags: list[DeprecatedTag] | None = None

    if language in {"en", "all"}:
        _require_file(SOURCES_EN, "ENソースファイル")
        en_tags = en_parser.parse(SOURCES_EN)
        outputs[DATA_EN] = en_tags
        messages.append(f"EN: {len(en_tags)} タグを解析 → {DATA_EN}")

    if language in {"jp", "all"}:
        if not SOURCES_JP.is_dir():
            raise FileNotFoundError(
                f"JPソースディレクトリが見つかりません: {SOURCES_JP}"
            )
        jp_tags = jp_parser.parse(SOURCES_JP)
        deprecated_tags = (
            jp_parser.parse_unused(SOURCES_JP_UNUSED)
            if SOURCES_JP_UNUSED.is_file()
            else []
        )
        outputs[DATA_JP] = jp_tags
        outputs[DATA_DEPRECATED] = deprecated_tags
        messages.extend((
            f"JP: {len(jp_tags)} タグを解析 → {DATA_JP}",
            (
                f"JP(未使用): {len(deprecated_tags)} タグを解析 → "
                f"{DATA_DEPRECATED}"
            ),
        ))

    if language in {"crosswalks", "all"}:
        if jp_tags is None or deprecated_tags is None:
            jp_tags = validate_jp_tags(
                _load_json_array(DATA_JP, "JPタグデータ")
            )
            deprecated_tags = validate_deprecated_tags(
                _load_json_array(DATA_DEPRECATED, "JP非使用タグデータ"),
                jp_tags,
            )
        resolver = _resolver(jp_tags, deprecated_tags)
        _require_file(SOURCES_INT, "INTタグクロスウォーク")
        _require_file(SOURCES_KO, "KOタグクロスウォーク")
        _require_branch_guides()
        int_mappings = int_parser.parse(SOURCES_INT, resolver.resolve)
        ko_mappings = ko_parser.parse(SOURCES_KO, resolver.resolve)
        branch_mappings = branch_guide_parser.parse(
            BRANCH_GUIDE_SOURCES,
            resolver.resolve,
        )
        outputs[DATA_INT_CROSSWALK] = int_mappings
        outputs[DATA_KO_CROSSWALK] = ko_mappings
        outputs[DATA_BRANCH_GUIDE_CROSSWALK] = branch_mappings
        messages.extend((
            (
                "INT crosswalk: "
                f"{sum(len(values) for values in int_mappings.values())} "
                f"mappings -> {DATA_INT_CROSSWALK}"
            ),
            (
                f"KO crosswalk: {len(ko_mappings.get('ko', {}))} mappings -> "
                f"{DATA_KO_CROSSWALK}"
            ),
            (
                "branch guide crosswalk: "
                f"{sum(len(values) for values in branch_mappings.values())} "
                f"mappings -> {DATA_BRANCH_GUIDE_CROSSWALK}"
            ),
        ))

    return ParseBatch(outputs=outputs, messages=tuple(messages))


def publish_outputs(outputs: Mapping[Path, object]) -> None:
    serialized = {
        destination: json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        for destination, data in outputs.items()
    }
    publish_files_atomically({
        destination: (
            lambda temporary, payload=payload: _write_payload(temporary, payload)
        )
        for destination, payload in serialized.items()
    })


def _write_payload(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


def run(language: Language) -> ParseBatch:
    batch = collect_outputs(language)
    publish_outputs(batch.outputs)
    for message in batch.messages:
        print(message)
    return batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        default="all",
        help="解析対象の言語 (デフォルト: all)",
    )
    args = parser.parse_args()

    try:
        run(cast(Language, args.lang))
    except (OSError, ValueError) as error:
        print(f"エラー: ソース解析に失敗しました: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
