import pytest

from scripts.domain.policy import tag_policy
from scripts.domain.records import tag_validation
from scripts.domain.policy.policy_builder import deprecated_by_source_lang
from scripts.domain.tag_dictionary import build_en_dicts
from scripts.domain.tag_dictionary import build_branch_dict


def test_shared_domain_modules_declare_exact_public_exports():
    assert tag_policy.__all__ == [
        "BranchMappingPolicy",
        "EN_CATEGORIES_OMITTED_ON_JP",
        "EN_CROSSWALK_SEMANTIC_REPLACEMENTS",
        "EN_ORIGIN_TAG_REPLACEMENTS",
        "JP_SOURCE_TAG_MAPPING_OVERRIDES",
        "MappingOrigin",
        "MappingPolicy",
        "SourceTagResolution",
        "branch_to_source_lang",
        "build_jp_names_and_source_map",
        "en_category_omitted_tags",
        "is_deprecated_for_en_source",
        "resolve_source_tag",
        "source_languages_for_branch",
    ]
    assert tag_validation.__all__ == [
        "validate_deprecated_tags",
        "validate_en_tags",
        "validate_jp_tags",
        "validate_tag_records",
    ]

def test_branch_builder_applies_expected_precedence(jp_tags_data):
    jp_names, jp_source_map = tag_policy.build_jp_names_and_source_map(jp_tags_data)
    jp_source_map["international"] = "インターナショナル"
    jp_source_map["alias-only"] = "tale"
    policy = tag_policy.MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags={"CN": {"wanderers"}},
        replacements={"CN": {"wanderers": "外部ウィキアーカイブ"}},
        overrides={"cn": {"原创": "cn", "故事": "tale"}},
        official_crosswalk={"cn": {"international": "int"}},
    )
    dictionary, deprecated = build_branch_dict(
        "cn",
        {
            "原创",
            "故事",
            "euclid",
            "wanderers",
            "international",
            "alias-only",
            "unknown",
        },
        policy,
    )

    assert dictionary["原创"] == "cn"
    assert dictionary["故事"] == "tale"
    assert dictionary["euclid"] == "euclid"
    assert dictionary["wanderers"] is None
    assert dictionary["international"] == "int"
    assert dictionary["alias-only"] == "tale"
    assert dictionary["unknown"] is None
    assert deprecated == {"wanderers": "外部ウィキアーカイブ"}

    branch_policy = policy.for_branch("cn")
    resolutions = {
        tag: tag_policy.resolve_source_tag(tag, policy, branch_policy)
        for tag in (
            "wanderers",
            "euclid",
            "故事",
            "international",
            "alias-only",
            "unknown",
        )
    }
    assert resolutions["wanderers"].origin == "jp_unused"
    assert resolutions["wanderers"].replacement == "外部ウィキアーカイブ"
    assert resolutions["euclid"].origin == "jp_tag_name"
    assert resolutions["故事"].origin == "curated_override"
    assert resolutions["international"].origin == "official_crosswalk"
    assert resolutions["alias-only"].origin == "jp_tag_alias"
    assert resolutions["unknown"].origin == "unhandled"


def test_int_inherits_en_unused_tags_and_origin_replacements(jp_tags_data):
    jp_names, jp_source_map = tag_policy.build_jp_names_and_source_map(jp_tags_data)
    policy = tag_policy.MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags={
            "EN": {"_cc", "_vn", "resource"},
            "INT": {"translator"},
        },
        replacements={
            "EN": {"_cc": None, "_vn": "vn", "resource": "世界観"},
            "INT": {"translator": "著者ページ"},
        },
        overrides={},
        official_crosswalk={},
    )
    dictionary, deprecated = build_branch_dict(
        "int",
        {"scp", "_cc", "_vn", "resource", "translator"},
        policy,
    )

    assert dictionary["scp"] == "scp"
    assert dictionary["_cc"] is None
    assert dictionary["_vn"] is None
    assert dictionary["resource"] is None
    assert dictionary["translator"] is None
    assert deprecated == {
        "_vn": "vn",
        "resource": "世界観",
        "translator": "著者ページ",
    }


def test_deprecated_entries_reject_duplicate_source_keys():
    entries = [
        {"source_lang": "EN", "source_tag": "old", "replacement": "対象A"},
        {"source_lang": "EN", "source_tag": "old", "replacement": "対象B"},
    ]

    with pytest.raises(ValueError, match="duplicate deprecated entry"):
        deprecated_by_source_lang(entries, {"対象A", "対象B"})


def test_en_builder_includes_effective_replacement_overrides():
    jp_tags = [{"name": "現在", "source_tags": ["current"]}]
    deprecated_tags = [
        {
            "source_lang": "EN",
            "source_tag": "legacy-tag",
            "replacement": "現在",
        }
    ]
    policy = tag_policy.MappingPolicy(
        jp_names=frozenset({"現在"}),
        jp_source_map={"current": "現在"},
        deprecated_tags={"EN": {"legacy-tag"}},
        replacements={"EN": {"legacy-tag": "現在"}},
        overrides={},
        official_crosswalk={},
    )
    dictionary, deprecated = build_en_dicts(
        [{"name": "current", "category": None}],
        jp_tags,
        deprecated_tags,
        {"current", "legacy-tag"},
        policy,
    )

    assert dictionary["legacy-tag"] is None
    assert deprecated["legacy-tag"] == "現在"


def test_en_builder_applies_shared_mapping_precedence():
    jp_tags = [
        {"name": "same", "source_tags": []},
        {"name": "override-target", "source_tags": []},
        {"name": "official-target", "source_tags": []},
        {"name": "alias-target", "source_tags": ["alias"]},
    ]
    policy = tag_policy.MappingPolicy(
        jp_names=frozenset(entry["name"] for entry in jp_tags),
        jp_source_map={
            "override": "alias-target",
            "official": "alias-target",
            "alias": "alias-target",
        },
        deprecated_tags={"EN": {"deprecated"}},
        replacements={"EN": {"deprecated": "same"}},
        overrides={"en": {"override": "override-target"}},
        official_crosswalk={"en": {"official": "official-target"}},
    )

    dictionary, _deprecated = build_en_dicts(
        [
            {"name": "same", "category": None},
            {"name": "override", "category": None},
            {"name": "official", "category": None},
            {"name": "alias", "category": None},
            {"name": "deprecated", "category": None},
            {"name": "unknown", "category": None},
        ],
        jp_tags,
        [],
        set(),
        policy,
    )

    assert dictionary == {
        "alias": "alias-target",
        "deprecated": None,
        "official": "official-target",
        "override": "override-target",
        "same": "same",
        "unknown": None,
    }
