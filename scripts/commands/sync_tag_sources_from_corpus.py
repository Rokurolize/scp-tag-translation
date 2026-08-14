#!/usr/bin/env python3
"""Check or sync tag-rule sources from the local SCP corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.application import source_sync as _workflow


def main() -> None:
    """Run the CLI from ``sys.argv``; invalid inputs exit with status 1."""
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
        result = _workflow.sync_tag_sources(args.corpus_root, write=args.write)
    except (OSError, ValueError) as err:
        print(f"エラー: タグソース同期に失敗しました: {err}")
        sys.exit(1)

    for source in result.missing_sources:
        print(f"missing corpus source: {source}")
    if result.stale_paths:
        print("tag sources are stale or missing:")
        for path in result.stale_paths:
            print(f"  {path}")
        sys.exit(1)

    action = "synced" if args.write else "current"
    print(
        f"tag sources {action}: "
        f"{len(_workflow.SourceSyncConfig().source_map)} files"
    )


__all__ = ["main"]


if __name__ == "__main__":
    main()
