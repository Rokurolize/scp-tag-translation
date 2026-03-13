"""
parse_sources.py - sources/ 以下のWikidotソースを解析して data/ に出力する

使い方:
  python scripts/parse_sources.py [--lang en|jp|all]

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

from scripts.parsers import en_parser, jp_parser

_SOURCES_EN = _ROOT / "sources" / "en" / "tag-list.txt"
_SOURCES_JP = _ROOT / "sources" / "jp"
_DATA_EN = _ROOT / "data" / "en_tags.json"
_DATA_JP = _ROOT / "data" / "jp_tags.json"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Wikidotソースを解析してdata/に出力する")
    parser.add_argument(
        "--lang",
        choices=["en", "jp", "all"],
        default="all",
        help="解析対象の言語 (デフォルト: all)",
    )
    args = parser.parse_args()

    if args.lang in ("en", "all"):
        run_en()
    if args.lang in ("jp", "all"):
        run_jp()


if __name__ == "__main__":
    main()
