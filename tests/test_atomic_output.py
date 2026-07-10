from pathlib import Path

import pytest

from scripts import atomic_output


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


def test_publication_preserves_existing_file_mode(tmp_path):
    destination = tmp_path / "published.txt"
    destination.write_text("old", encoding="utf-8")
    destination.chmod(0o640)

    atomic_output.publish_files_atomically({destination: _write("new")})

    assert destination.read_text(encoding="utf-8") == "new"
    assert destination.stat().st_mode & 0o777 == 0o640
