"""Branch-to-JP dictionary generation and integrity tests."""

import csv
import json
from pathlib import Path

import pytest

from scripts import build_branch_dicts_from_corpus as branch_builder
from scripts import concatenated_tags, tag_policy
from scripts.branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).parent.parent
DICTIONARIES = ROOT / "dictionaries"
OVERRIDES = ROOT / "sources" / "branch_to_jp_overrides.json"
ACCEPTANCE = ROOT / "tests" / "fixtures" / "branch_acceptance_examples.tsv"

REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_required_branch_dictionaries_exist_and_values_are_valid(jp_tags_data):
    jp_names = {entry["name"] for entry in jp_tags_data}

    for branch in REQUIRED_BRANCHES:
        dictionary_path = DICTIONARIES / f"{branch}_to_jp.json"
        deprecated_path = DICTIONARIES / f"deprecated_{branch}_to_jp.json"
        assert dictionary_path.exists(), f"missing dictionary: {dictionary_path}"
        assert deprecated_path.exists(), f"missing deprecated dictionary: {deprecated_path}"

        dictionary = _load_json(dictionary_path)
        deprecated = _load_json(deprecated_path)
        assert isinstance(dictionary, dict)
        assert isinstance(deprecated, dict)

        bad_values = {
            source: target
            for source, target in dictionary.items()
            if target is not None and target not in jp_names
        }
        bad_replacements = {
            source: target
            for source, target in deprecated.items()
            if target is not None and target not in jp_names
        }
        assert not bad_values
        assert not bad_replacements


def test_override_targets_are_valid_jp_tags(jp_tags_data):
    jp_names = {entry["name"] for entry in jp_tags_data}
    overrides = _load_json(OVERRIDES)

    failures = []
    for branch, branch_values in overrides.items():
        for source_tag, value in branch_values.items():
            target = value["jp_tag"] if isinstance(value, dict) else value
            if target not in jp_names:
                failures.append(f"{branch}:{source_tag}->{target}")

    assert not failures


def test_branch_builder_applies_expected_precedence(jp_tags_data):
    jp_names, jp_source_map = tag_policy.jp_maps(jp_tags_data)
    jp_source_map["international"] = "インターナショナル"
    policy = tag_policy.MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags={"CN": {"wanderers"}},
        replacements={"CN": {"wanderers": "外部ウィキアーカイブ"}},
        overrides={"cn": {"原创": "cn", "故事": "tale"}},
        official_crosswalk={"cn": {"international": "int"}},
    )
    dictionary, deprecated = branch_builder.build_branch_dict(
        "cn",
        {
            "原创",
            "故事",
            "euclid",
            "wanderers",
            "international",
            "unknown",
        },
        policy,
    )

    assert dictionary["原创"] == "cn"
    assert dictionary["故事"] == "tale"
    assert dictionary["euclid"] == "euclid"
    assert dictionary["wanderers"] is None
    assert dictionary["international"] == "int"
    assert dictionary["unknown"] is None
    assert deprecated == {"wanderers": "外部ウィキアーカイブ"}


def test_int_inherits_en_unused_tags_and_origin_replacements(jp_tags_data):
    jp_names, jp_source_map = tag_policy.jp_maps(jp_tags_data)
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
    dictionary, deprecated = branch_builder.build_branch_dict(
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
        tag_policy.deprecated_by_source_lang(entries, {"対象A", "対象B"})


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
    dictionary, deprecated = branch_builder.build_en_dicts(
        [{"name": "current"}],
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

    dictionary, _deprecated = branch_builder.build_en_dicts(
        [
            {"name": "same"},
            {"name": "override"},
            {"name": "official"},
            {"name": "alias"},
            {"name": "deprecated"},
            {"name": "unknown"},
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


def test_build_artifacts_owns_complete_publication_set(tmp_path):
    page_dir = tmp_path / "corpus" / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe", "scp"]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "dictionaries"
    policy_path = output_dir / "jp_tag_policy.json"
    en_tags = [{"name": "safe"}, {"name": "scp"}]
    jp_tags = [
        {"name": "safe", "source_tags": []},
        {"name": "scp", "source_tags": []},
    ]
    policy = tag_policy.MappingPolicy(
        jp_names=frozenset({"safe", "scp"}),
        jp_source_map={},
        deprecated_tags={},
        replacements={},
        overrides={},
        official_crosswalk={},
    )

    artifacts = branch_builder.build_artifacts(
        tmp_path / "corpus",
        ["en"],
        en_tags,
        jp_tags,
        [],
        policy,
        dictionaries_dir=output_dir,
        jp_policy_path=policy_path,
        supported_branches=("en",),
    )

    assert set(artifacts.outputs) == {
        output_dir / "en_to_jp.json",
        output_dir / "deprecated_en_to_jp.json",
        policy_path,
    }
    assert artifacts.outputs[output_dir / "en_to_jp.json"] == {
        "safe": "safe",
        "scp": "scp",
    }
    assert artifacts.outputs[policy_path]["concatenated_tag_hints"] == {
        "en": {}
    }
    assert artifacts.hint_count == 0


def test_discover_branches_excludes_jp_and_internal_dirs(tmp_path):
    for branch in ("en", "jp", "_dryrun"):
        page_dir = tmp_path / branch / "pages" / "sample"
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": ["scp"]}),
            encoding="utf-8",
        )

    assert concatenated_tags.discover_branches(tmp_path) == ["en"]


def test_concatenated_tag_hints_restore_ambiguous_boundaries(tmp_path):
    pages = tmp_path / "int" / "pages"
    page_dir = pages / "separate"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe", "scp", "sculpture"]}),
        encoding="utf-8",
    )
    dictionary = {
        "safe": "safe",
        "scp": "scp",
        "sculpture": "彫像",
        "scpsculpture": None,
    }

    hints = concatenated_tags.build_concatenated_tag_hints(
        tmp_path,
        "int",
        dictionary,
    )

    assert hints == {
        "safescpsculpture": ["safe", "scp", "sculpture"]
    }


def test_concatenated_tag_hints_reject_intrinsic_collisions(tmp_path):
    pages = tmp_path / "en" / "pages"
    for slug, tags in {
        "first": ["a", "bc"],
        "second": ["ab", "c"],
    }.items():
        page_dir = pages / slug
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": tags}),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="multiple corpus boundaries"):
        concatenated_tags.build_concatenated_tag_hints(
            tmp_path,
            "en",
            {"a": None, "ab": None, "bc": None, "c": None},
        )


def test_concatenated_tag_hints_reject_exact_dictionary_collision(tmp_path):
    page_dir = tmp_path / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["scp", "sculpture"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exact dictionary key"):
        concatenated_tags.build_concatenated_tag_hints(
            tmp_path,
            "en",
            {"scp": "scp", "sculpture": "彫像", "scpsculpture": None},
        )


def test_concatenated_tag_hints_reject_tags_missing_from_dictionary(tmp_path):
    page_dir = tmp_path / "int" / "pages" / "new-tag"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["known", "newtag"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="corpus tags missing from dictionary"):
        concatenated_tags.build_concatenated_tag_hints(
            tmp_path,
            "int",
            {"known": "known"},
        )


def test_partial_hint_generation_reuses_other_committed_dictionaries(
    tmp_path,
):
    (tmp_path / "int_to_jp.json").write_text(
        json.dumps({"scp": "scp", "sculpture": "彫像"}),
        encoding="utf-8",
    )
    complete = concatenated_tags.complete_hint_dictionaries(
        {"en": {"scp": "scp"}},
        dictionaries_dir=tmp_path,
        supported_branches=("en", "int"),
    )

    assert complete == {
        "en": {"scp": "scp"},
        "int": {"scp": "scp", "sculpture": "彫像"},
    }


def test_acceptance_fixture_mentions_every_required_branch():
    with ACCEPTANCE.open(encoding="utf-8", newline="") as f:
        branches = {row["branch"] for row in csv.DictReader(f, delimiter="\t")}

    assert branches == set(REQUIRED_BRANCHES)


def test_every_current_corpus_tag_is_present_in_its_dictionary():
    corpus_root = Path("/home/roku/src/Rokurolize/scp-wiki-translation/corpus")
    if not corpus_root.is_dir():
        return

    for branch in REQUIRED_BRANCHES:
        corpus_tags = concatenated_tags.corpus_tags_for_branch(corpus_root, branch)
        dictionary = _load_json(DICTIONARIES / f"{branch}_to_jp.json")
        assert corpus_tags <= set(dictionary), branch


def test_official_crosswalk_and_faq_overrides_are_applied():
    vectors = {
        "cn": {"认知危害": "認識災害", "段落": "フラグメント", "指导": "他支部公式"},
        "de": {"lebendig": "生命", "amphibisch": "両生類"},
        "es": {"adulto": "アダルト"},
        "fr": {"adulte": "アダルト"},
        "int": {"cognitohazard": "認識災害", "guide": "他支部公式"},
        "it": {"caino": "カイン"},
        "ko": {"생물": "生命", "정신조작": "精神影響", "안내": "他支部公式"},
        "pl": {"poradnik": "他支部公式", "_inne-pl": "_その他団体-他支部"},
        "pt-br": {"guia": "他支部公式"},
        "th": {"การทหาร": "軍事"},
        "ua": {"телекінез": "念力"},
        "vn": {"hướng-dẫn": "他支部公式"},
        "zh-tr": {"指導": "他支部公式"},
    }
    for branch, expected in vectors.items():
        dictionary = _load_json(DICTIONARIES / f"{branch}_to_jp.json")
        for source_tag, jp_tag in expected.items():
            assert dictionary[source_tag] == jp_tag


def test_jp_policy_covers_every_registered_tag(jp_tags_data):
    policy = _load_json(DICTIONARIES / "jp_tag_policy.json")
    assert policy["schema_version"] == 2
    assert set(policy["tags"]) == {entry["name"] for entry in jp_tags_data}
    assert policy["tags"]["テーマ"]["copy_allowed_for_translation"] is False
    assert policy["tags"]["エッセイ"]["copy_allowed_for_translation"] is True
    assert policy["tags"]["インターナショナル"]["special_translation_action"] == "omit"
    assert policy["source_tags"]["en"]["absurdism"]["translation_action"] == (
        "omit_translation_policy"
    )
    assert policy["source_tags"]["en"]["more-by"]["translation_action"] == (
        "omit_jp_unused"
    )
    assert "resource" not in policy["source_tags"]["en"]
    assert policy["source_tags"]["int"]["_cc"]["translation_action"] == (
        "omit_jp_unused"
    )
    assert policy["source_tags"]["int"]["_genreless"]["translation_action"] == (
        "omit_translation_policy"
    )
    assert set(policy["concatenated_tag_hints"]) == set(REQUIRED_BRANCHES)
    for branch, hints in policy["concatenated_tag_hints"].items():
        dictionary = _load_json(DICTIONARIES / f"{branch}_to_jp.json")
        assert set(hints).isdisjoint(dictionary)
    assert any(
        any(left == "scp" and right == "sculpture" for left, right in zip(tags, tags[1:]))
        for tags in policy["concatenated_tag_hints"]["int"].values()
    )
