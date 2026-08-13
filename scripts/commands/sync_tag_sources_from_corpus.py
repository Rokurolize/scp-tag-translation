#!/usr/bin/env python3
"""Check or sync tag-rule sources from the local SCP corpus."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from scripts.atomic_output import FileWriter, publish_files_atomically
from scripts.data_paths import ROOT
from scripts.source_manifest import corpus_source_map

SOURCE_MAP = corpus_source_map()


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
