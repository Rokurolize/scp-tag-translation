"""辞書構築ロジック（build_dict.build）の単体テスト"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.commands import build_dict
from scripts.commands.build_dict import build
from scripts.domain.tag_policy import is_deprecated_for_en_source
from scripts.domain.tag_validation import validate_tag_records


EN = [{"name": "scp"}, {"name": "tale"}, {"name": "hub"}]
JP = [
    {"name": "scp", "source_tags": ["scp"]},
    {"name": "テイル", "source_tags": ["tale"]},
    {"name": "JP専用", "source_tags": []},
]


def test_direct_script_help_works_from_repository_root():
    root = Path(__file__).parent.parent
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.commands.build_dict", "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--overwrite" in completed.stdout


def test_basic_mapping():
    result = build(EN, JP)
    assert result["scp"] == "scp"
    assert result["tale"] == "テイル"


def test_unmapped_en_is_null():
    result = build(EN, JP)
    assert result["hub"] is None


def test_existing_manual_preserved():
    existing = {"hub": "ハブ"}
    result = build(EN, JP, existing)
    assert result["hub"] == "ハブ"


def test_jp_overrides_null_existing():
    existing = {"scp": None}
    result = build(EN, JP, existing)
    assert result["scp"] == "scp"


def test_deprecated_overrides_jp_mapping():
    result = build(EN, JP, deprecated_en_tags={"tale"})
    assert result["tale"] is None


def test_duplicate_en_names_fail_fast():
    with pytest.raises(ValueError, match="ENタグ名"):
        build([{"name": "scp"}, {"name": "scp"}], JP)


def test_duplicate_jp_source_tags_fail_fast():
    jp = [
        {"name": "scp", "source_tags": ["scp"]},
        {"name": "別名scp", "source_tags": ["scp"]},
    ]

    with pytest.raises(ValueError, match="JP側source_tags"):
        build(EN, jp)


def test_invalid_en_tag_data_fails_fast():
    with pytest.raises(ValueError, match="ENタグ名"):
        build([{"name": " scp"}], JP)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category", 3),
        ("description", ["not text"]),
        ("meta", {"requires": "scp"}),
        ("meta", {"requires": [1]}),
    ],
)
def test_invalid_optional_en_fields_fail_fast(field, value):
    with pytest.raises(ValueError, match=field):
        build([{"name": "scp", field: value}], JP)


def test_invalid_jp_tag_data_fails_fast():
    with pytest.raises(ValueError, match="JPタグ名"):
        build(EN, [{"name": " テイル", "source_tags": ["tale"]}])


def test_invalid_jp_source_tag_data_fails_fast():
    with pytest.raises(ValueError, match="JP側source_tags"):
        build(EN, [{"name": "テイル", "source_tags": [" tale"]}])


def test_missing_jp_source_tags_fail_fast():
    with pytest.raises(ValueError, match="JP側source_tags"):
        build(EN, [{"name": "テイル"}])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("description", ["not text"]),
        ("use_restricted", "false"),
        ("edit_restricted", 1),
        ("translation_exempt", "true"),
    ],
)
def test_invalid_optional_jp_fields_fail_fast(key, value):
    entry = {"name": "テイル", "source_tags": ["tale"], key: value}

    with pytest.raises(ValueError, match=key):
        build(EN, [entry])


def test_every_jp_source_alias_is_mapped():
    result = build(
        [{"name": "primary"}, {"name": "secondary"}],
        [{"name": "対象", "source_tags": ["primary", "secondary"]}],
    )

    assert result == {"primary": "対象", "secondary": "対象"}


def test_invalid_deprecated_data_fails_fast():
    with pytest.raises(ValueError, match="replacement"):
        validate_tag_records(
            EN,
            JP,
            [
                {
                    "source_lang": "EN",
                    "source_tag": "artist",
                    "replacement": " アート",
                }
            ],
        )


def test_invalid_deprecated_description_fails_fast():
    with pytest.raises(ValueError, match="description"):
        validate_tag_records(
            EN,
            JP,
            [{"source_tag": "artist", "description": ["not text"]}],
        )


def test_explicit_null_deprecated_source_language_fails_fast():
    with pytest.raises(ValueError, match="source_lang"):
        validate_tag_records(
            EN,
            JP,
            [{"source_lang": None, "source_tag": "artist"}],
        )


def test_deprecated_replacement_must_name_a_registered_jp_tag():
    with pytest.raises(ValueError, match="JPタグに存在しません"):
        validate_tag_records(
            EN,
            JP,
            [
                {
                    "source_lang": "EN",
                    "source_tag": "artist",
                    "replacement": "未登録",
                }
            ],
        )


def test_is_deprecated_for_en_source_uses_source_tag():
    assert is_deprecated_for_en_source({"source_tag": "artist"})
    assert is_deprecated_for_en_source(
        {
            "source_lang": None,
            "source_tag": "artist",
        }
    )
    assert not is_deprecated_for_en_source(
        {
            "source_lang": "PL",
            "source_tag": "film",
        }
    )


def test_output_is_sorted():
    en = [{"name": "z-tag"}, {"name": "a-tag"}, {"name": "m-tag"}]
    result = build(en, [])
    assert list(result.keys()) == sorted(result.keys())


def test_all_en_tags_in_output():
    result = build(EN, JP)
    for entry in EN:
        assert entry["name"] in result


def test_extra_existing_keys_preserved():
    existing = {"manual-only": "手動エントリ"}
    result = build(EN, JP, existing)
    assert result["manual-only"] == "手動エントリ"


def test_existing_dict_values_must_be_valid():
    with pytest.raises(ValueError, match="既存辞書の値"):
        build(EN, JP, {"hub": "ハブ "})


def test_existing_dict_keys_must_be_valid():
    with pytest.raises(ValueError, match="既存辞書のキー"):
        build(EN, JP, {" hub": "ハブ"})


def test_existing_dict_case_variant_of_source_key_fails_fast():
    en = [{"name": "amoni-ram"}]

    with pytest.raises(ValueError, match="大小文字違い"):
        build(en, [], {"Amoni-Ram": None})


def test_main_writes_empty_deprecated_dict_when_source_missing(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_deprecated = data_dir / "deprecated_tags.json"
    dict_out = dict_dir / "en_to_jp.json"
    dict_deprecated = dict_dir / "deprecated_en_to_jp.json"

    data_en.write_text(json.dumps(EN), encoding="utf-8")
    data_jp.write_text(json.dumps(JP), encoding="utf-8")
    dict_deprecated.write_text(
        json.dumps({"stale": "古い置換"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_deprecated)
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_out)
    monkeypatch.setattr(build_dict, "DEPRECATED_EN_DICTIONARY_PATH", dict_deprecated)
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    build_dict.main()

    assert json.loads(dict_out.read_text(encoding="utf-8"))["scp"] == "scp"
    assert json.loads(dict_deprecated.read_text(encoding="utf-8")) == {}


def test_main_ignores_non_en_deprecated_source_collisions(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_deprecated = data_dir / "deprecated_tags.json"
    dict_out = dict_dir / "en_to_jp.json"
    dict_deprecated = dict_dir / "deprecated_en_to_jp.json"

    data_en.write_text(
        json.dumps([{"name": "film"}, {"name": "artist"}]),
        encoding="utf-8",
    )
    data_jp.write_text(
        json.dumps(
            [
                {"name": "映画", "source_tags": ["film"]},
                {"name": "アーティスト", "source_tags": ["artist"]},
                {"name": "アートワーク", "source_tags": []},
                {"name": "映像添付", "source_tags": []},
            ]
        ),
        encoding="utf-8",
    )
    data_deprecated.write_text(
        json.dumps(
            [
                {"source_lang": "PL", "source_tag": "film", "replacement": "映像添付"},
                {
                    "source_lang": "EN",
                    "source_tag": "artist",
                    "replacement": "アートワーク",
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_deprecated)
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_out)
    monkeypatch.setattr(build_dict, "DEPRECATED_EN_DICTIONARY_PATH", dict_deprecated)
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    build_dict.main()

    assert json.loads(dict_out.read_text(encoding="utf-8")) == {
        "artist": None,
        "film": "映画",
    }
    assert json.loads(dict_deprecated.read_text(encoding="utf-8")) == {
        "artist": "アートワーク",
    }


def test_main_rejects_duplicate_en_deprecated_entries(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_deprecated = data_dir / "deprecated_tags.json"

    data_en.write_text(json.dumps([{"name": "artist"}]), encoding="utf-8")
    data_jp.write_text(json.dumps([]), encoding="utf-8")
    data_deprecated.write_text(
        json.dumps(
            [
                {
                    "source_lang": "EN",
                    "source_tag": "artist",
                    "replacement": "アートワーク",
                },
                {"source_lang": "EN", "source_tag": "artist", "replacement": "芸術"},
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_deprecated)
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_dir / "en_to_jp.json")
    monkeypatch.setattr(
        build_dict,
        "DEPRECATED_EN_DICTIONARY_PATH",
        dict_dir / "deprecated_en_to_jp.json",
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not (dict_dir / "en_to_jp.json").exists()
    assert not (dict_dir / "deprecated_en_to_jp.json").exists()


def test_main_rejects_non_list_deprecated_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_deprecated = data_dir / "deprecated_tags.json"

    data_en.write_text(json.dumps([{"name": "artist"}]), encoding="utf-8")
    data_jp.write_text(json.dumps([]), encoding="utf-8")
    data_deprecated.write_text(
        json.dumps({"source_tag": "artist"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_deprecated)
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_dir / "en_to_jp.json")
    monkeypatch.setattr(
        build_dict,
        "DEPRECATED_EN_DICTIONARY_PATH",
        dict_dir / "deprecated_en_to_jp.json",
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not (dict_dir / "en_to_jp.json").exists()
    assert not (dict_dir / "deprecated_en_to_jp.json").exists()


def test_main_rejects_malformed_deprecated_entry(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_deprecated = data_dir / "deprecated_tags.json"

    data_en.write_text(json.dumps([{"name": "artist"}]), encoding="utf-8")
    data_jp.write_text(json.dumps([]), encoding="utf-8")
    data_deprecated.write_text(json.dumps(["artist"]), encoding="utf-8")

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_deprecated)
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_dir / "en_to_jp.json")
    monkeypatch.setattr(
        build_dict,
        "DEPRECATED_EN_DICTIONARY_PATH",
        dict_dir / "deprecated_en_to_jp.json",
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert not (dict_dir / "en_to_jp.json").exists()
    assert not (dict_dir / "deprecated_en_to_jp.json").exists()


def test_main_rejects_malformed_existing_dict(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    dict_dir.mkdir()

    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    dict_out = dict_dir / "en_to_jp.json"
    dict_deprecated = dict_dir / "deprecated_en_to_jp.json"

    data_en.write_text(json.dumps(EN), encoding="utf-8")
    data_jp.write_text(json.dumps(JP), encoding="utf-8")
    dict_out.write_text(json.dumps({"hub": "ハブ "}), encoding="utf-8")

    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_dir / "missing.json")
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_out)
    monkeypatch.setattr(build_dict, "DEPRECATED_EN_DICTIONARY_PATH", dict_deprecated)
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert json.loads(dict_out.read_text(encoding="utf-8")) == {"hub": "ハブ "}
    assert not dict_deprecated.exists()


def test_main_reports_malformed_json_without_traceback(
    tmp_path,
    monkeypatch,
    capsys,
):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_en.write_text("{", encoding="utf-8")
    data_jp.write_text(json.dumps(JP), encoding="utf-8")
    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_dir / "missing.json")
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_dir / "en_to_jp.json")
    monkeypatch.setattr(
        build_dict,
        "DEPRECATED_EN_DICTIONARY_PATH",
        dict_dir / "deprecated_en_to_jp.json",
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out.startswith("エラー: 辞書生成に失敗しました: ")
    assert not dict_dir.exists()


def test_main_reports_publication_failure_without_partial_outputs(
    tmp_path,
    monkeypatch,
    capsys,
):
    data_dir = tmp_path / "data"
    dict_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    data_en = data_dir / "en_tags.json"
    data_jp = data_dir / "jp_tags.json"
    data_en.write_text(json.dumps(EN), encoding="utf-8")
    data_jp.write_text(json.dumps(JP), encoding="utf-8")
    monkeypatch.setattr(build_dict, "DATA_EN", data_en)
    monkeypatch.setattr(build_dict, "DATA_JP", data_jp)
    monkeypatch.setattr(build_dict, "DATA_DEPRECATED", data_dir / "missing.json")
    monkeypatch.setattr(build_dict, "EN_DICTIONARY_PATH", dict_dir / "en_to_jp.json")
    monkeypatch.setattr(
        build_dict,
        "DEPRECATED_EN_DICTIONARY_PATH",
        dict_dir / "deprecated_en_to_jp.json",
    )
    monkeypatch.setattr(sys, "argv", ["build_dict.py"])

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(build_dict, "publish_files_atomically", fail_publication)

    with pytest.raises(SystemExit) as excinfo:
        build_dict.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == ("エラー: 辞書生成に失敗しました: disk full\n")
    assert not dict_dir.exists()
