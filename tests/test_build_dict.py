"""辞書構築ロジック（build_dict.build）の単体テスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from build_dict import build


EN = [{"name": "scp"}, {"name": "tale"}, {"name": "hub"}]
JP = [
    {"name": "scp", "en_tag": "scp"},
    {"name": "テイル", "en_tag": "tale"},
    {"name": "JP専用", "en_tag": None},
]


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
