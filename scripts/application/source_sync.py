"""Check and synchronize official tag sources from a local corpus."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from scripts.infrastructure.atomic_output import FileWriter, publish_files_atomically
from scripts.infrastructure.data_paths import ROOT
from scripts.pipeline.source_manifest import corpus_source_map

@dataclass(frozen=True)
class SourceSyncResult:
    """Outcome of checking or writing the repository's source snapshots."""

    stale_paths: tuple[str, ...]
    missing_sources: tuple[Path, ...]
    wrote_files: int


@dataclass(frozen=True)
class SourceSyncConfig:
    """Repository inputs used by one source synchronization workflow."""

    source_map: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType(corpus_source_map()),
    )
    repository_root: Path = field(default_factory=lambda: ROOT)


def _copy_writer(source: Path) -> FileWriter:
    def copy_to(temporary: Path) -> None:
        shutil.copyfile(source, temporary)

    return copy_to


def sync_tag_sources(
    corpus_root: Path,
    *,
    write: bool = False,
    config: SourceSyncConfig | None = None,
) -> SourceSyncResult:
    """Check and optionally publish snapshots, returning stale/missing paths; filesystem errors propagate."""
    config = config or SourceSyncConfig()
    stale: list[str] = []
    missing_sources: list[Path] = []
    pending: dict[Path, Path] = {}
    published_count = 0
    for destination_rel, source_rel in config.source_map.items():
        source = corpus_root / source_rel
        destination = config.repository_root / destination_rel
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
        publish_files_atomically({
            destination: _copy_writer(source)
            for destination, source in pending.items()
        })
        stale = []
        published_count = len(pending)
    return SourceSyncResult(
        stale_paths=tuple(stale),
        missing_sources=tuple(missing_sources),
        wrote_files=published_count,
    )


__all__ = [
    "SourceSyncConfig",
    "SourceSyncResult",
    "sync_tag_sources",
]
