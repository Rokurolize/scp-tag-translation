"""Branch-to-JP dictionary generation and integrity tests."""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_branch_dicts_from_corpus as branch_builder
from branch_config import SUPPORTED_BRANCHES

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
    jp_names, jp_source_map = branch_builder.jp_maps(jp_tags_data)
    dictionary, deprecated = branch_builder.build_branch_dict(
        "cn",
        {"原创", "故事", "euclid", "wanderers", "unknown"},
        jp_names,
        jp_source_map,
        {"CN": {"wanderers"}},
        {"CN": {"wanderers": "外部ウィキアーカイブ"}},
        {"cn": {"原创": "cn", "故事": "tale"}},
    )

    assert dictionary["原创"] == "cn"
    assert dictionary["故事"] == "tale"
    assert dictionary["euclid"] == "euclid"
    assert dictionary["wanderers"] is None
    assert dictionary["unknown"] is None
    assert deprecated == {"wanderers": "外部ウィキアーカイブ"}


def test_int_inherits_en_unused_tags_and_origin_replacements(jp_tags_data):
    jp_names, jp_source_map = branch_builder.jp_maps(jp_tags_data)
    dictionary, deprecated = branch_builder.build_branch_dict(
        "int",
        {"scp", "_cc", "_vn", "resource", "translator"},
        jp_names,
        jp_source_map,
        {
            "EN": {"_cc", "_vn", "resource"},
            "INT": {"translator"},
        },
        {
            "EN": {"_cc": None, "_vn": "vn", "resource": "世界観"},
            "INT": {"translator": "著者ページ"},
        },
        {},
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


def test_discover_branches_excludes_jp_and_internal_dirs(tmp_path):
    for branch in ("en", "jp", "_dryrun"):
        page_dir = tmp_path / branch / "pages" / "sample"
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": ["scp"]}),
            encoding="utf-8",
        )

    assert branch_builder.discover_branches(tmp_path) == ["en"]


def test_acceptance_fixture_mentions_every_required_branch():
    with ACCEPTANCE.open(encoding="utf-8", newline="") as f:
        branches = {row["branch"] for row in csv.DictReader(f, delimiter="\t")}

    assert branches == set(REQUIRED_BRANCHES)


def test_every_current_corpus_tag_is_present_in_its_dictionary():
    corpus_root = Path("/home/roku/src/Rokurolize/scp-wiki-translation/corpus")
    if not corpus_root.is_dir():
        return

    for branch in REQUIRED_BRANCHES:
        corpus_tags = branch_builder.corpus_tags_for_branch(corpus_root, branch)
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
