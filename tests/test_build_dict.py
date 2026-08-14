"""ドメイン辞書構築と互換CLIの単体テスト。"""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.compatibility.legacy_dictionary import validate_existing_dict
from scripts.contracts.errors import InvalidDomainInputError
from scripts.domain.policy.tag_policy import is_deprecated_for_en_source
from scripts.domain.policy.policy_builder import MappingPolicyInputs, build_mapping_policy
from scripts.domain.records.tag_validation import validate_tag_records
from scripts.domain.tag_dictionary import build_en_dicts


EN = [{"name": "scp"}, {"name": "tale"}, {"name": "hub"}]
JP = [
    {"name": "scp", "source_tags": ["scp"]},
    {"name": "テイル", "source_tags": ["tale"]},
    {"name": "JP専用", "source_tags": []},
]


def build_domain_dictionary(
    en_tags,
    jp_tags,
    existing=None,
    deprecated_en_tags=None,
):
    existing = existing or {}
    validate_existing_dict(existing)
    deprecated_raw = [
        {"source_lang": "EN", "source_tag": source_tag}
        for source_tag in deprecated_en_tags or set()
    ]
    en_tags, jp_tags, deprecated_raw = validate_tag_records(
        en_tags,
        jp_tags,
        deprecated_raw,
    )
    policy = build_mapping_policy(
        jp_tags,
        deprecated_raw,
        MappingPolicyInputs(
            overrides={},
            replacement_overrides={},
            official_crosswalks=(),
        ),
        include_origin_replacements=False,
    )
    if existing:
        policy = replace(
            policy,
            overrides={
                **policy.overrides,
                "en": {
                    **policy.overrides.get("en", {}),
                    **{
                        source_tag: target
                        for source_tag, target in existing.items()
                        if target is not None
                    },
                },
            },
        )
    dictionary, _deprecated = build_en_dicts(
        en_tags,
        jp_tags,
        deprecated_raw,
        set(existing),
        policy,
    )
    return dictionary


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
    result = build_domain_dictionary(EN, JP)
    assert result["scp"] == "scp"
    assert result["tale"] == "テイル"


def test_unmapped_en_is_null():
    result = build_domain_dictionary(EN, JP)
    assert result["hub"] is None


def test_override_rejects_unknown_jp_target():
    with pytest.raises(InvalidDomainInputError, match="override target is not a JP tag"):
        build_mapping_policy(
            JP,
            [],
            MappingPolicyInputs(
                overrides={"en": {"source": "unknown"}},
                replacement_overrides={},
                official_crosswalks=(),
            ),
            include_origin_replacements=False,
        )


def test_existing_manual_preserved():
    existing = {"hub": "ハブ"}
    result = build_domain_dictionary(EN, JP, existing)
    assert result["hub"] == "ハブ"


def test_jp_overrides_null_existing():
    existing = {"scp": None}
    result = build_domain_dictionary(EN, JP, existing)
    assert result["scp"] == "scp"


def test_deprecated_overrides_jp_mapping():
    result = build_domain_dictionary(EN, JP, deprecated_en_tags={"tale"})
    assert result["tale"] is None


def test_duplicate_en_names_fail_fast():
    with pytest.raises(ValueError, match="ENタグ名"):
        build_domain_dictionary([{"name": "scp"}, {"name": "scp"}], JP)


def test_unresolved_duplicate_jp_source_tags_fail_fast():
    jp = [
        {"name": "対象A", "source_tags": ["ambiguous"]},
        {"name": "対象B", "source_tags": ["ambiguous"]},
    ]

    with pytest.raises(ValueError, match="multiple JP tags"):
        build_domain_dictionary(EN, jp)


def test_invalid_en_tag_data_fails_fast():
    with pytest.raises(ValueError, match="ENタグ名"):
        build_domain_dictionary([{"name": " scp"}], JP)


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
        build_domain_dictionary([{"name": "scp", field: value}], JP)


def test_invalid_jp_tag_data_fails_fast():
    with pytest.raises(ValueError, match="JPタグ名"):
        build_domain_dictionary(EN, [{"name": " テイル", "source_tags": ["tale"]}])


@pytest.mark.parametrize(
    "source_tags",
    ["tale", [""], [" tale"], ["tale "]],
)
def test_invalid_jp_source_tag_data_fails_fast(source_tags):
    with pytest.raises(ValueError, match="JP側source_tags"):
        build_domain_dictionary(EN, [{"name": "テイル", "source_tags": source_tags}])


def test_missing_jp_source_tags_fail_fast():
    with pytest.raises(ValueError, match="JP側source_tags"):
        build_domain_dictionary(EN, [{"name": "テイル"}])


def test_jp_source_tags_are_copied_during_validation():
    source_tags = ["tale"]
    records = validate_tag_records(
        EN,
        [{"name": "テイル", "source_tags": source_tags}],
        [],
    )[1]

    source_tags.append("mutated")

    assert records[0]["source_tags"] == ["tale"]


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
        build_domain_dictionary(EN, [entry])


def test_every_jp_source_alias_is_mapped():
    result = build_domain_dictionary(
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
    result = build_domain_dictionary(en, [])
    assert list(result.keys()) == sorted(result.keys())


def test_all_en_tags_in_output():
    result = build_domain_dictionary(EN, JP)
    for entry in EN:
        assert entry["name"] in result


def test_extra_existing_keys_preserved():
    existing = {"manual-only": "手動エントリ"}
    result = build_domain_dictionary(EN, JP, existing)
    assert result["manual-only"] == "手動エントリ"


def test_existing_dict_values_must_be_valid():
    with pytest.raises(ValueError, match="既存辞書の値"):
        validate_existing_dict({"hub": "ハブ "})


def test_existing_dict_keys_must_be_valid():
    with pytest.raises(ValueError, match="既存辞書のキー"):
        validate_existing_dict({" hub": "ハブ"})
