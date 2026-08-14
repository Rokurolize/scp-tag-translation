import json
import sys

import pytest

from scripts.compatibility import legacy_dictionary_build as legacy_workflow
from scripts.commands import build_dict
from scripts.pipeline import dictionary_inputs

EN = [{"name": "scp"}, {"name": "tale"}, {"name": "hub"}]
JP = [
    {"name": "scp", "source_tags": ["scp"]},
    {"name": "テイル", "source_tags": ["tale"]},
    {"name": "JP専用", "source_tags": []},
]


@pytest.fixture
def redirected_build_dict_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    paths = {
        "data_en": data_dir / "en_tags.json",
        "data_jp": data_dir / "jp_tags.json",
        "data_deprecated": data_dir / "deprecated_tags.json",
        "dict_out": tmp_path / "dictionaries" / "en_to_jp.json",
        "dict_deprecated": tmp_path / "dictionaries" / "deprecated_en_to_jp.json",
    }
    for attribute, key in (
        ("EN_DICTIONARY_PATH", "dict_out"),
        ("DEPRECATED_EN_DICTIONARY_PATH", "dict_deprecated"),
    ):
        monkeypatch.setattr(legacy_workflow, attribute, paths[key])
    mapping_paths = dictionary_inputs.MappingInputPaths(
        data_en=paths["data_en"],
        data_jp=paths["data_jp"],
        data_deprecated=paths["data_deprecated"],
        overrides=data_dir / "overrides.json",
        replacement_overrides=data_dir / "replacement-overrides.json",
        crosswalks=(data_dir / "crosswalk.json",),
    )
    monkeypatch.setattr(
        legacy_workflow,
        "default_mapping_input_paths",
        lambda: mapping_paths,
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])
    return paths


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_main_writes_empty_deprecated_dict_when_source_missing(
    redirected_build_dict_paths,
):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], EN)
    _write_json(paths["data_jp"], JP)
    paths["dict_deprecated"].parent.mkdir()
    _write_json(paths["dict_deprecated"], {"stale": "古い置換"})

    build_dict.main()

    assert json.loads(paths["dict_out"].read_text(encoding="utf-8"))["scp"] == "scp"
    assert json.loads(paths["dict_deprecated"].read_text(encoding="utf-8")) == {}


def test_main_publishes_with_real_policy_file_loader(
    redirected_build_dict_paths,
    monkeypatch,
):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], EN)
    _write_json(paths["data_jp"], JP)
    _write_json(paths["data_deprecated"], [])
    override_path = paths["data_en"].parent / "overrides.json"
    replacement_path = paths["data_en"].parent / "replacement-overrides.json"
    crosswalk_path = paths["data_en"].parent / "crosswalk.json"
    for path in (override_path, replacement_path, crosswalk_path):
        _write_json(path, {})
    build_dict.main()

    assert json.loads(paths["dict_out"].read_text(encoding="utf-8"))["scp"] == "scp"
    assert json.loads(paths["dict_deprecated"].read_text(encoding="utf-8")) == {}


def test_main_ignores_non_en_deprecated_source_collisions(
    redirected_build_dict_paths,
):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], [{"name": "film"}, {"name": "artist"}])
    _write_json(
        paths["data_jp"],
        [
            {"name": "映画", "source_tags": ["film"]},
            {"name": "アーティスト", "source_tags": ["artist"]},
            {"name": "アートワーク", "source_tags": []},
            {"name": "映像添付", "source_tags": []},
        ],
    )
    _write_json(
        paths["data_deprecated"],
        [
            {"source_lang": "PL", "source_tag": "film", "replacement": "映像添付"},
            {
                "source_lang": "EN",
                "source_tag": "artist",
                "replacement": "アートワーク",
            },
        ],
    )

    build_dict.main()

    assert json.loads(paths["dict_out"].read_text(encoding="utf-8")) == {
        "artist": None,
        "film": "映画",
    }
    assert json.loads(paths["dict_deprecated"].read_text(encoding="utf-8")) == {
        "artist": "アートワーク",
    }


def test_main_rejects_duplicate_en_deprecated_entries(redirected_build_dict_paths):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], [{"name": "artist"}])
    _write_json(paths["data_jp"], [])
    _write_json(
        paths["data_deprecated"],
        [
            {
                "source_lang": "EN",
                "source_tag": "artist",
                "replacement": "アートワーク",
            },
            {"source_lang": "EN", "source_tag": "artist", "replacement": "芸術"},
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not paths["dict_out"].exists()
    assert not paths["dict_deprecated"].exists()


def test_main_rejects_non_list_deprecated_data(redirected_build_dict_paths):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], [{"name": "artist"}])
    _write_json(paths["data_jp"], [])
    _write_json(paths["data_deprecated"], {"source_tag": "artist"})

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not paths["dict_out"].exists()
    assert not paths["dict_deprecated"].exists()


def test_main_rejects_malformed_deprecated_entry(redirected_build_dict_paths):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], [{"name": "artist"}])
    _write_json(paths["data_jp"], [])
    _write_json(paths["data_deprecated"], ["artist"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not paths["dict_out"].exists()
    assert not paths["dict_deprecated"].exists()


def test_main_rejects_malformed_existing_dict(redirected_build_dict_paths):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], EN)
    _write_json(paths["data_jp"], JP)
    paths["dict_out"].parent.mkdir()
    _write_json(paths["dict_out"], {"hub": "ハブ "})

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert json.loads(paths["dict_out"].read_text(encoding="utf-8")) == {"hub": "ハブ "}
    assert not paths["dict_deprecated"].exists()


def test_main_reports_malformed_json_without_traceback(
    redirected_build_dict_paths,
    capsys,
):
    paths = redirected_build_dict_paths
    paths["data_en"].write_text("{", encoding="utf-8")
    _write_json(paths["data_jp"], JP)

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out.startswith("エラー: 辞書生成に失敗しました: ")
    assert not paths["dict_out"].parent.exists()


def test_main_reports_publication_failure_without_partial_outputs(
    redirected_build_dict_paths,
    monkeypatch,
    capsys,
):
    paths = redirected_build_dict_paths
    _write_json(paths["data_en"], EN)
    _write_json(paths["data_jp"], JP)

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(
        legacy_workflow,
        "publish_files_atomically",
        fail_publication,
    )

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == "エラー: 辞書生成に失敗しました: disk full\n"
    assert not paths["dict_out"].parent.exists()
