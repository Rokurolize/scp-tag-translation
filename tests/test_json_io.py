import json
import os

import pytest

from scripts import json_io
from scripts.json_io import json_text, write_json, write_text


def test_json_text_sorts_only_the_top_level_mapping():
    payload = {"b": {"z": 1, "a": 2}, "a": {"z": 3, "a": 4}}

    assert json.loads(json_text(payload, sort_top_level=True)) == {
        "a": {"z": 3, "a": 4},
        "b": {"z": 1, "a": 2},
    }
    assert '"z": 1,\n    "a": 2' in json_text(payload, sort_top_level=True)


def test_load_json_reports_the_input_path_for_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"broken": }', encoding="utf-8")

    with pytest.raises(ValueError, match=rf"invalid JSON in {path}: Expecting value") as excinfo:
        json_io.load_json(path)

    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_write_json_uses_utf8_indentation_and_trailing_newline(tmp_path):
    path = tmp_path / "nested" / "output.json"

    write_json(path, {"タグ": "値"})

    assert path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(path.read_text(encoding="utf-8")) == {"タグ": "値"}


def test_write_text_preserves_existing_output_if_publication_fails(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "output.txt"
    path.write_text("previous", encoding="utf-8")

    def fail_replace(_source, _destination):
        raise OSError("replace failed")

    monkeypatch.setattr(json_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_text(path, "next")

    assert path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [path]


def test_write_text_preserves_existing_permissions(tmp_path):
    path = tmp_path / "output.txt"
    path.write_text("previous", encoding="utf-8")
    path.chmod(0o640)

    write_text(path, "next")

    assert path.read_text(encoding="utf-8") == "next"
    assert os.stat(path).st_mode & 0o777 == 0o640
