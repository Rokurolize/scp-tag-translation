"""Stage related generated files and roll back the set if publication fails."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path


FileWriter = Callable[[Path], None]


def _new_file_mode() -> int:
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def publish_files_atomically(writers: Mapping[Path, FileWriter]) -> None:
    """Fully write every output before replacing any published file.

    Individual replacements are atomic. If a later replacement fails, files
    already replaced in this batch are restored from same-directory backups.
    """

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    try:
        for destination, writer in writers.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            staged[destination] = temporary
            writer(temporary)
            mode = (
                stat.S_IMODE(destination.stat().st_mode)
                if destination.exists()
                else _new_file_mode()
            )
            temporary.chmod(mode)

        for destination in writers:
            if destination.exists():
                descriptor, backup_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.",
                    suffix=".bak",
                    dir=destination.parent,
                )
                os.close(descriptor)
                backup = Path(backup_name)
                shutil.copyfile(destination, backup)
                shutil.copymode(destination, backup)
                backups[destination] = backup
            else:
                backups[destination] = None

        try:
            for destination, temporary in staged.items():
                os.replace(temporary, destination)
                replaced.append(destination)
        except OSError:
            for destination in reversed(replaced):
                backup = backups[destination]
                if backup is None:
                    destination.unlink(missing_ok=True)
                else:
                    os.replace(backup, destination)
            raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None:
                backup.unlink(missing_ok=True)
