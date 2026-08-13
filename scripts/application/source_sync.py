"""Check and synchronize official tag sources from a local corpus."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from scripts.infrastructure.atomic_output import FileWriter, publish_files_atomically
from scripts.infrastructure.data_paths import ROOT
from scripts.pipeline.source_manifest import corpus_source_map

SOURCE_MAP = corpus_source_map()


@dataclass(frozen=True)
class SourceSyncResult:
    """Outcome of checking or writing the repository's source snapshots."""

    stale_paths: tuple[str, ...]
    missing_sources: tuple[Path, ...]
    wrote_files: int


def _copy_writer(source: Path) -> FileWriter:
    def copy_to(temporary: Path) -> None:
        shutil.copyfile(source, temporary)

    return copy_to


def sync_tag_sources(
    corpus_root: Path,
    *,
    write: bool = False,
    source_map: Mapping[str, str] = SOURCE_MAP,
    repository_root: Path = ROOT,
    publish=publish_files_atomically,
) -> SourceSyncResult:
    """Check snapshots and optionally publish current corpus sources atomically."""
    stale: list[str] = []
    missing_sources: list[Path] = []
    pending: dict[Path, Path] = {}
    for destination_rel, source_rel in source_map.items():
        source = corpus_root / source_rel
        destination = repository_root / destination_rel
        if not source.is_file():
            missing_sources.append(source)
            stale.append(destination_rel)
            continue
        if (
            not destination.is_file()
            or destination.read_bytes() != source.read_bytes()
        ):
            stale.append(destination_rel)
            if write:
                pending[destination] = source

    if write and not missing_sources:
        publish({
            destination: _copy_writer(source)
            for destination, source in pending.items()
        })
        stale = []
    return SourceSyncResult(
        stale_paths=tuple(stale),
        missing_sources=tuple(missing_sources),
        wrote_files=len(pending),
    )


__all__ = ["SOURCE_MAP", "SourceSyncResult", "sync_tag_sources"]
