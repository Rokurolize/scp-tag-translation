import json

from scripts.json_io import json_text, write_json


def test_json_text_sorts_only_the_top_level_mapping():
    payload = {"b": {"z": 1, "a": 2}, "a": {"z": 3, "a": 4}}

    assert json.loads(json_text(payload, sort_top_level=True)) == {
        "a": {"z": 3, "a": 4},
        "b": {"z": 1, "a": 2},
    }
    assert '"z": 1,\n    "a": 2' in json_text(payload, sort_top_level=True)


def test_write_json_uses_utf8_indentation_and_trailing_newline(tmp_path):
    path = tmp_path / "nested" / "output.json"

    write_json(path, {"タグ": "値"})

    assert path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(path.read_text(encoding="utf-8")) == {"タグ": "値"}
