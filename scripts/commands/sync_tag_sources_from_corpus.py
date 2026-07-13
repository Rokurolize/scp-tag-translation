#!/usr/bin/env python3
"""Check or sync tag-rule sources from the local SCP corpus."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from scripts.atomic_output import FileWriter, publish_files_atomically
from scripts.data_paths import ROOT

SOURCE_MAP = {
    "sources/en/tag-guide.txt": "05command/pages/tech-hub-tag/source.wikidot.txt",
    "sources/en/tag-list.txt": "05command/pages/tech-hub-tag-list/source.wikidot.txt",
    "sources/en/tag-list-manifest.txt": "05command/pages/tag-list-manifest/source.wikidot.txt",
    "sources/jp/tag-guide.txt": "jp/pages/tag-guide/source.wikidot.txt",
    "sources/jp/tag-list.txt": "jp/pages/tag-list/source.wikidot.txt",
    "sources/jp/fragment-basic.txt": "jp/pages/fragment:tag-list-basic/source.wikidot.txt",
    "sources/jp/fragment-series.txt": "jp/pages/fragment:tag-list-series/source.wikidot.txt",
    "sources/jp/fragment-universe.txt": "jp/pages/fragment:tag-list-universe/source.wikidot.txt",
    "sources/jp/fragment-event.txt": "jp/pages/fragment:tag-list-event/source.wikidot.txt",
    "sources/jp/fragment-unused.txt": "jp/pages/fragment:tag-list-unused/source.wikidot.txt",
    "sources/jp/fragment-faq.txt": "jp/pages/fragment:tag-list-faq/source.wikidot.txt",
    "sources/int/tag-guide.txt": "int/pages/tag-guide/source.wikidot.txt",
    "sources/ko/translate-tags.txt": "ko/pages/translate:tags/source.wikidot.txt",
    "sources/cn/tag-guide.txt": "cn/pages/tag-guide/source.wikidot.txt",
    "sources/de/tag-guide.txt": "de/pages/tag-guide/source.wikidot.txt",
    "sources/es/tag-guide.txt": "es/pages/tag-guide/source.wikidot.txt",
    "sources/fr/guide-des-tags.txt": "fr/pages/guide-des-tags/source.wikidot.txt",
    "sources/it/tag-guide.txt": "it/pages/tag-guide/source.wikidot.txt",
    "sources/pl/tag-list.txt": "pl/pages/tag-list/source.wikidot.txt",
    "sources/pt-br/fragment-lista-mestra.txt": "pt-br/pages/fragment:lista-mestra/source.wikidot.txt",
    "sources/th/tag-list.txt": "th/pages/tag-list/source.wikidot.txt",
    "sources/ua/tag-guide.txt": "ua/pages/tag-guide/source.wikidot.txt",
    "sources/vn/fragment-tag-guide-for-translator.txt": "vn/pages/fragment:tag-guide-for-translator/source.wikidot.txt",
    "sources/zh-tr/fragment-base-tag.txt": "zh-tr/pages/fragment:base-tag/source.wikidot.txt",
    "sources/zh-tr/fragment-characteristic-tag.txt": "zh-tr/pages/fragment:characteristic-tag/source.wikidot.txt",
    "sources/zh-tr/fragment-genre-and-theme-tag.txt": "zh-tr/pages/fragment:genre-and-theme-tag/source.wikidot.txt",
    "sources/zh-tr/fragment-other-tag.txt": "zh-tr/pages/fragment:other-tag/source.wikidot.txt",
    "sources/zh-tr/fragment-internationality-tag.txt": "zh-tr/pages/fragment:internationality-tag/source.wikidot.txt",
}


def _copy_writer(source: Path) -> FileWriter:
    def copy_to(temporary: Path) -> None:
        shutil.copyfile(source, temporary)

    return copy_to


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        required=True,
        type=Path,
        help="Path to scp-wiki-translation/corpus",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Copy current corpus sources into this repository (default: check only).",
    )
    args = parser.parse_args()

    try:
        stale: list[str] = []
        pending: dict[Path, Path] = {}
        for destination_rel, source_rel in SOURCE_MAP.items():
            source = args.corpus_root / source_rel
            destination = ROOT / destination_rel
            if not source.is_file():
                print(f"missing corpus source: {source}")
                stale.append(destination_rel)
                continue
            if (
                not destination.is_file()
                or destination.read_bytes() != source.read_bytes()
            ):
                stale.append(destination_rel)
                if args.write:
                    pending[destination] = source

        if args.write and not any(
            not (args.corpus_root / source_rel).is_file()
            for source_rel in SOURCE_MAP.values()
        ):
            publish_files_atomically({
                destination: _copy_writer(source)
                for destination, source in pending.items()
            })
            stale = []
    except (OSError, ValueError) as err:
        print(f"エラー: タグソース同期に失敗しました: {err}")
        sys.exit(1)

    if stale:
        print("tag sources are stale or missing:")
        for path in stale:
            print(f"  {path}")
        sys.exit(1)

    action = "synced" if args.write else "current"
    print(f"tag sources {action}: {len(SOURCE_MAP)} files")


if __name__ == "__main__":
    main()
