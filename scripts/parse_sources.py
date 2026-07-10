"""
parse_sources.py - sources/ 以下のWikidotソースを解析して data/ に出力する

使い方:
  python scripts/parse_sources.py [--lang en|jp|crosswalks|all]

オプション:
  --lang en   ENタグリストのみ解析
  --lang jp   JPフラグメントのみ解析
  --lang all  両方解析（デフォルト）
"""
import argparse
import sys
from pathlib import Path

# リポジトリルートをパスに追加（scripts/ から実行した場合も動作するよう）
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from scripts import build_dict
from scripts.parsers import (
    branch_guide_parser,
    en_parser,
    int_parser,
    jp_parser,
    ko_parser,
)
from scripts.parsers.crosswalk_resolver import load_resolver

_SOURCES_EN = _ROOT / "sources" / "en" / "tag-list.txt"
_SOURCES_JP = _ROOT / "sources" / "jp"
_SOURCES_JP_UNUSED = _SOURCES_JP / "fragment-unused.txt"
_SOURCES_INT = _ROOT / "sources" / "int" / "tag-guide.txt"
_SOURCES_KO = _ROOT / "sources" / "ko" / "translate-tags.txt"
_DATA_EN = _ROOT / "data" / "en_tags.json"
_DATA_JP = _ROOT / "data" / "jp_tags.json"
_DATA_DEPRECATED = _ROOT / "data" / "deprecated_tags.json"
_DATA_INT_CROSSWALK = _ROOT / "data" / "int_tag_crosswalk.json"
_DATA_KO_CROSSWALK = _ROOT / "data" / "ko_tag_crosswalk.json"
_DATA_BRANCH_GUIDE_CROSSWALK = _ROOT / "data" / "branch_guide_crosswalk.json"

_BRANCH_GUIDE_SOURCES = {
    "cn": [_ROOT / "sources" / "cn" / "tag-guide.txt"],
    "de": [_ROOT / "sources" / "de" / "tag-guide.txt"],
    "es": [_ROOT / "sources" / "es" / "tag-guide.txt"],
    "fr": [_ROOT / "sources" / "fr" / "guide-des-tags.txt"],
    "it": [_ROOT / "sources" / "it" / "tag-guide.txt"],
    "pl": [_ROOT / "sources" / "pl" / "tag-list.txt"],
    "pt-br": [_ROOT / "sources" / "pt-br" / "fragment-lista-mestra.txt"],
    "th": [_ROOT / "sources" / "th" / "tag-list.txt"],
    "ua": [_ROOT / "sources" / "ua" / "tag-guide.txt"],
    "vn": [_ROOT / "sources" / "vn" / "fragment-tag-guide-for-translator.txt"],
    "zh-tr": [
        _ROOT / "sources" / "zh-tr" / "fragment-base-tag.txt",
        _ROOT / "sources" / "zh-tr" / "fragment-characteristic-tag.txt",
        _ROOT / "sources" / "zh-tr" / "fragment-genre-and-theme-tag.txt",
        _ROOT / "sources" / "zh-tr" / "fragment-other-tag.txt",
        _ROOT / "sources" / "zh-tr" / "fragment-internationality-tag.txt",
    ],
}


def run_en() -> None:
    if not _SOURCES_EN.exists():
        print(f"エラー: ENソースファイルが見つかりません: {_SOURCES_EN}")
        sys.exit(1)
    en_parser.parse(str(_SOURCES_EN), str(_DATA_EN))


def run_jp() -> None:
    if not _SOURCES_JP.exists():
        print(f"エラー: JPソースディレクトリが見つかりません: {_SOURCES_JP}")
        sys.exit(1)
    jp_parser.parse(str(_SOURCES_JP), str(_DATA_JP))
    if _SOURCES_JP_UNUSED.exists():
        jp_parser.parse_unused(str(_SOURCES_JP_UNUSED), str(_DATA_DEPRECATED))
    else:
        _DATA_DEPRECATED.parent.mkdir(parents=True, exist_ok=True)
        _DATA_DEPRECATED.write_text("[]\n", encoding="utf-8")
        print(f"JP(未使用): 0 タグを解析 → {_DATA_DEPRECATED}")


def run_crosswalks() -> None:
    if not _DATA_JP.exists() or not _DATA_DEPRECATED.exists():
        print("エラー: crosswalk解析の前にJPタグデータを生成してください。")
        sys.exit(1)
    resolver = load_resolver(
        _DATA_JP,
        _DATA_DEPRECATED,
        build_dict.EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    )
    if not _SOURCES_INT.exists():
        print(f"エラー: INTタグクロスウォークが見つかりません: {_SOURCES_INT}")
        sys.exit(1)
    int_parser.parse(
        str(_SOURCES_INT),
        str(_DATA_INT_CROSSWALK),
        resolver.resolve,
    )
    if not _SOURCES_KO.exists():
        print(f"エラー: KOタグクロスウォークが見つかりません: {_SOURCES_KO}")
        sys.exit(1)
    ko_parser.parse(
        str(_SOURCES_KO),
        str(_DATA_KO_CROSSWALK),
        resolver.resolve,
    )
    missing_guides = [
        str(path)
        for paths in _BRANCH_GUIDE_SOURCES.values()
        for path in paths
        if not path.is_file()
    ]
    if missing_guides:
        print("エラー: 支部公式タグガイドが見つかりません:")
        for path in missing_guides:
            print(f"  {path}")
        sys.exit(1)
    branch_guide_parser.parse(
        _BRANCH_GUIDE_SOURCES,
        _DATA_BRANCH_GUIDE_CROSSWALK,
        resolver,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Wikidotソースを解析してdata/に出力する")
    parser.add_argument(
        "--lang",
        choices=["en", "jp", "crosswalks", "all"],
        default="all",
        help="解析対象の言語 (デフォルト: all)",
    )
    args = parser.parse_args()

    if args.lang in ("en", "all"):
        run_en()
    if args.lang in ("jp", "all"):
        run_jp()
    if args.lang in ("crosswalks", "all"):
        run_crosswalks()


if __name__ == "__main__":
    main()
