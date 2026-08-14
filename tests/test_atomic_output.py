import multiprocessing
from pathlib import Path
from threading import Event, Thread

import pytest

from scripts.infrastructure import atomic_output


def _hold_publication_lock(
    destinations: list[str],
    entered,
    release,
    started=None,
) -> None:
    if started is not None:
        started.set()
    with atomic_output._publication_lock({Path(path): None for path in destinations}):
        entered.set()
        release.wait(5)


def _write(value: str):
    return lambda path: path.write_text(value, encoding="utf-8")


def test_staging_failure_leaves_all_published_files_unchanged(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("old-first", encoding="utf-8")
    second.write_text("old-second", encoding="utf-8")

    def fail(_path: Path) -> None:
        raise OSError("injected staging failure")

    with pytest.raises(OSError, match="injected staging failure"):
        atomic_output.publish_files_atomically({
            first: _write("new-first"),
            second: fail,
        })

    assert first.read_text(encoding="utf-8") == "old-first"
    assert second.read_text(encoding="utf-8") == "old-second"
    assert {path.name for path in tmp_path.iterdir()} == {"first.txt", "second.txt"}


def test_publication_failure_rolls_back_files_already_replaced(tmp_path, monkeypatch):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("old-first", encoding="utf-8")
    second.write_text("old-second", encoding="utf-8")
    real_replace = atomic_output.os.replace
    calls = 0

    def fail_second_publication(source, destination):
        nonlocal calls
        if str(source).endswith(".tmp"):
            calls += 1
            if calls == 2:
                raise OSError("injected publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_output.os, "replace", fail_second_publication)

    with pytest.raises(OSError, match="injected publication failure"):
        atomic_output.publish_files_atomically({
            first: _write("new-first"),
            second: _write("new-second"),
        })

    assert first.read_text(encoding="utf-8") == "old-first"
    assert second.read_text(encoding="utf-8") == "old-second"


def test_publication_failure_removes_new_files_and_cleanup_artifacts(
    tmp_path,
    monkeypatch,
):
    existing_first = tmp_path / "first.txt"
    new_second = tmp_path / "second.txt"
    existing_third = tmp_path / "third.txt"
    existing_first.write_text("old-first", encoding="utf-8")
    existing_third.write_text("old-third", encoding="utf-8")
    real_replace = atomic_output.os.replace
    publication_count = 0

    def fail_third_publication(source, destination):
        nonlocal publication_count
        if str(source).endswith(".tmp"):
            publication_count += 1
            if publication_count == 3:
                raise OSError("injected mixed publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_output.os, "replace", fail_third_publication)

    with pytest.raises(OSError, match="injected mixed publication failure"):
        atomic_output.publish_files_atomically({
            existing_first: _write("new-first"),
            new_second: _write("new-second"),
            existing_third: _write("new-third"),
        })

    assert existing_first.read_text(encoding="utf-8") == "old-first"
    assert not new_second.exists()
    assert existing_third.read_text(encoding="utf-8") == "old-third"
    assert {path.name for path in tmp_path.iterdir()} == {
        "first.txt",
        "third.txt",
    }


def test_publication_preserves_existing_file_mode(tmp_path):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")
    destination.chmod(0o640)

    atomic_output.publish_files_atomically({destination: _write("new")})

    assert destination.read_text(encoding="utf-8") == "new"
    assert destination.stat().st_mode & 0o777 == 0o640


def test_new_publication_uses_explicit_mode_without_reading_umask(
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "published.txt"

    def fail_umask(_mode):
        raise AssertionError("publication must not inspect the process umask")

    monkeypatch.setattr(atomic_output.os, "umask", fail_umask)

    atomic_output.publish_files_atomically({destination: _write("new")})

    assert destination.stat().st_mode & 0o777 == 0o644


def test_publication_rejects_equivalent_destination_paths(tmp_path):
    destination = tmp_path / "published.txt"
    equivalent = tmp_path / "nested" / ".." / "published.txt"

    with pytest.raises(ValueError, match="equivalent destination paths"):
        atomic_output.publish_files_atomically({
            destination: _write("first"),
            equivalent: _write("second"),
        })


def test_rollback_failure_continues_and_chains_publication_error(
    tmp_path,
    monkeypatch,
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    third = tmp_path / "third.txt"
    for path in (first, second, third):
        path.write_text(f"old-{path.stem}", encoding="utf-8")
    real_replace = atomic_output.os.replace
    publication_count = 0

    def fail_publication_and_second_rollback(source, destination):
        nonlocal publication_count
        if str(source).endswith(".tmp"):
            publication_count += 1
            if publication_count == 3:
                raise OSError("primary publication failure")
        if str(source).endswith(".bak") and Path(destination) == second:
            raise OSError("secondary rollback failure")
        return real_replace(source, destination)

    monkeypatch.setattr(
        atomic_output.os,
        "replace",
        fail_publication_and_second_rollback,
    )

    with pytest.raises(
        atomic_output.AtomicPublicationError,
        match="rollback failed",
    ) as caught:
        atomic_output.publish_files_atomically({
            first: _write("new-first"),
            second: _write("new-second"),
            third: _write("new-third"),
        })

    assert isinstance(caught.value.__cause__, OSError)
    assert "primary publication failure" in str(caught.value.__cause__)
    assert first.read_text(encoding="utf-8") == "old-first"
    assert second.read_text(encoding="utf-8") == "new-second"
    assert third.read_text(encoding="utf-8") == "old-third"
    assert len(list(tmp_path.glob(".*.bak"))) == 1


def test_cleanup_failure_is_chained_from_staging_error(tmp_path, monkeypatch):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")
    real_unlink = Path.unlink

    def fail_temporary_cleanup(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise OSError("secondary cleanup failure")
        return real_unlink(path, *args, **kwargs)

    def fail_staging(_path: Path) -> None:
        raise OSError("primary staging failure")

    monkeypatch.setattr(Path, "unlink", fail_temporary_cleanup)

    with pytest.raises(OSError, match="primary staging failure") as caught:
        atomic_output.publish_files_atomically({destination: fail_staging})

    assert any("cleanup failed" in note for note in caught.value.__notes__)
    assert any("secondary cleanup failure" in note for note in caught.value.__notes__)
    assert destination.read_text(encoding="utf-8") == "old"


def test_successful_publication_reports_cleanup_failure(tmp_path, monkeypatch):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")
    real_unlink = Path.unlink

    def fail_backup_cleanup(path, *args, **kwargs):
        if path.suffix == ".bak":
            raise OSError("backup cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_backup_cleanup)

    with pytest.raises(
        atomic_output.AtomicPublicationError,
        match="cleanup failed",
    ) as caught:
        atomic_output.publish_files_atomically({destination: _write("new")})

    assert caught.value.__cause__ is None
    assert destination.read_text(encoding="utf-8") == "new"
    assert len(list(tmp_path.glob(".*.bak"))) == 1


def test_backup_copy_failure_removes_created_backup(tmp_path, monkeypatch):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")

    def fail_copy(*_args):
        raise OSError("backup copy failure")

    monkeypatch.setattr(atomic_output.shutil, "copyfile", fail_copy)

    with pytest.raises(OSError, match="backup copy failure"):
        atomic_output.publish_files_atomically({destination: _write("new")})

    assert destination.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob(".*.bak"))


def test_concurrent_publishers_serialize_backup_and_replacement(tmp_path, monkeypatch):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")
    entered_prepare = Event()
    release_prepare = Event()
    second_done = Event()
    prepare_calls = 0
    real_prepare = atomic_output._prepare_backups

    def block_first_prepare(destinations, backups):
        nonlocal prepare_calls
        prepare_calls += 1
        if prepare_calls == 1:
            entered_prepare.set()
            assert release_prepare.wait(5)
        real_prepare(destinations, backups)

    monkeypatch.setattr(atomic_output, "_prepare_backups", block_first_prepare)
    errors: list[BaseException] = []

    def publish(value: str, done: Event | None = None):
        try:
            atomic_output.publish_files_atomically({destination: _write(value)})
        except BaseException as error:
            errors.append(error)
        finally:
            if done is not None:
                done.set()

    first = Thread(target=publish, args=("first",))
    second = Thread(target=publish, args=("second", second_done))
    first.start()
    assert entered_prepare.wait(5)
    second.start()
    assert not second_done.wait(0.1)
    release_prepare.set()
    first.join(5)
    second.join(5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert destination.read_text(encoding="utf-8") == "second"


def test_overlapping_destination_batches_lock_each_shared_path(tmp_path):
    context = multiprocessing.get_context("spawn")
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first_entered = context.Event()
    first_release = context.Event()
    second_started = context.Event()
    second_entered = context.Event()
    second_release = context.Event()
    first_process = context.Process(
        target=_hold_publication_lock,
        args=([str(first), str(second)], first_entered, first_release),
    )
    second_process = context.Process(
        target=_hold_publication_lock,
        args=([str(first)], second_entered, second_release, second_started),
    )
    first_process.start()
    try:
        assert first_entered.wait(5)
        second_process.start()
        assert second_started.wait(5)
        assert not second_entered.is_set()
        first_release.set()
        assert second_entered.wait(5)
        second_release.set()
    finally:
        first_release.set()
        second_release.set()
        for process in (first_process, second_process):
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
    assert first_process.exitcode == 0
    assert second_process.exitcode == 0
