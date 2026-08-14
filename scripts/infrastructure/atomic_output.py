"""Stage related generated files and roll back the set if publication fails."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

from scripts.infrastructure.file_modes import DEFAULT_NEW_FILE_MODE

__all__ = ["AtomicPublicationError", "FileWriter", "publish_files_atomically"]


FileWriter = Callable[[Path], None]


class AtomicPublicationError(OSError):
    """Report a secondary rollback or cleanup failure with its cause."""


def _operation_error(
    operation: str,
    failures: list[tuple[Path, OSError]],
) -> AtomicPublicationError:
    error = AtomicPublicationError(
        f"atomic publication {operation} failed for {len(failures)} path(s)"
    )
    for path, failure in failures:
        error.add_note(f"{path}: {failure}")
    return error


def _rollback_replaced(
    replaced: list[Path],
    backups: Mapping[Path, Path | None],
) -> tuple[list[tuple[Path, OSError]], set[Path]]:
    failures: list[tuple[Path, OSError]] = []
    retained_backups: set[Path] = set()
    for destination in reversed(replaced):
        backup = backups[destination]
        try:
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                os.replace(backup, destination)
        except OSError as error:
            failures.append((destination, error))
            if backup is not None:
                retained_backups.add(backup)
    return failures, retained_backups


def _cleanup_paths(paths: list[Path]) -> list[tuple[Path, OSError]]:
    failures: list[tuple[Path, OSError]] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            failures.append((path, error))
    return failures


def _stage_outputs(
    writers: Mapping[Path, FileWriter],
    staged: dict[Path, Path],
) -> None:
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
            else DEFAULT_NEW_FILE_MODE
        )
        temporary.chmod(mode)


def _prepare_backups(
    destinations: Mapping[Path, Path],
    backups: dict[Path, Path | None],
) -> None:
    for destination in destinations:
        if destination.exists():
            descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".bak",
                dir=destination.parent,
            )
            os.close(descriptor)
            backup = Path(backup_name)
            backups[destination] = backup
            shutil.copyfile(destination, backup)
            shutil.copymode(destination, backup)
        else:
            backups[destination] = None


def _replace_staged(
    staged: Mapping[Path, Path],
    backups: Mapping[Path, Path | None],
    retained_backups: set[Path],
) -> None:
    replaced: list[Path] = []
    for destination, temporary in staged.items():
        try:
            os.replace(temporary, destination)
        except BaseException as publication_error:
            rollback_failures, retained = _rollback_replaced(
                replaced,
                backups,
            )
            retained_backups.update(retained)
            if rollback_failures:
                raise _operation_error(
                    "rollback",
                    rollback_failures,
                ) from publication_error
            raise
        replaced.append(destination)


def publish_files_atomically(writers: Mapping[Path, FileWriter]) -> None:
    """Fully write every output before replacing any published file.

    Individual replacements are atomic. If a later replacement fails, files
    already replaced in this batch are restored from same-directory backups.
    Existing permissions are preserved; new generated files use mode 0644.
    """

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    retained_backups: set[Path] = set()
    active_error: BaseException | None = None
    try:
        _stage_outputs(writers, staged)
        _prepare_backups(staged, backups)
        _replace_staged(staged, backups, retained_backups)
    except BaseException as error:
        active_error = error
        raise
    finally:
        cleanup_paths = list(staged.values())
        cleanup_paths.extend(
            backup
            for backup in backups.values()
            if backup is not None and backup not in retained_backups
        )
        cleanup_failures = _cleanup_paths(cleanup_paths)
        if cleanup_failures:
            cleanup_error = _operation_error("cleanup", cleanup_failures)
            if active_error is not None:
                active_error.add_note(str(cleanup_error))
                for note in cleanup_error.__notes__:
                    active_error.add_note(note)
            else:
                raise cleanup_error
