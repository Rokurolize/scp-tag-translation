import csv
import json
from pathlib import Path

import pytest

from scripts.application import dictionary_build as dictionary_workflow
from scripts.application import mapping_inputs
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.pipeline import dictionary_inputs
from scripts.pipeline.corpus import discover_corpus_branches
from scripts.pipeline.dictionary_inputs import complete_hint_dictionaries_from_existing

ROOT = Path(__file__).parent.parent
DICTIONARIES = ROOT / "dictionaries"
ACCEPTANCE = ROOT / "tests" / "fixtures" / "branch_acceptance_examples.tsv"
REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_discover_branches_excludes_jp_and_internal_dirs(tmp_path):
    for branch in ("en", "jp", "_dryrun"):
        page_dir = tmp_path / branch / "pages" / "sample"
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": ["scp"]}),
            encoding="utf-8",
        )

    assert discover_corpus_branches(tmp_path) == ["en"]


def test_partial_hint_generation_reuses_other_committed_dictionaries(
    tmp_path,
):
    (tmp_path / "int_to_jp.json").write_text(
        json.dumps({"scp": "scp", "sculpture": "彫像"}),
        encoding="utf-8",
    )
    complete = complete_hint_dictionaries_from_existing(
        {"en": {"scp": "scp"}},
        dictionaries_dir=tmp_path,
        supported_branches=("en", "int"),
    )

    assert complete == {
        "en": {"scp": "scp"},
        "int": {"scp": "scp", "sculpture": "彫像"},
    }


def test_complete_mapping_inputs_report_missing_policy_files(tmp_path):
    data_en = tmp_path / "en.json"
    data_jp = tmp_path / "jp.json"
    data_en.write_text("[]", encoding="utf-8")
    data_jp.write_text("[]", encoding="utf-8")
    paths = dictionary_inputs.MappingInputPaths(
        data_en=data_en,
        data_jp=data_jp,
        data_deprecated=tmp_path / "deprecated.json",
        overrides=tmp_path / "overrides.json",
        replacement_overrides=tmp_path / "replacements.json",
        crosswalks=(tmp_path / "crosswalk.json",),
    )

    with pytest.raises(FileNotFoundError, match="Required mapping inputs missing"):
        mapping_inputs.load_mapping_inputs(
            paths,
            require_complete_inputs=True,
        )


def test_partial_mapping_inputs_use_empty_optional_policy_files(tmp_path):
    data_en = tmp_path / "en.json"
    data_jp = tmp_path / "jp.json"
    data_en.write_text(json.dumps([{"name": "scp"}]), encoding="utf-8")
    data_jp.write_text(
        json.dumps([{"name": "scp", "source_tags": ["scp"]}]),
        encoding="utf-8",
    )
    paths = dictionary_inputs.MappingInputPaths(
        data_en=data_en,
        data_jp=data_jp,
        data_deprecated=tmp_path / "deprecated.json",
        overrides=tmp_path / "overrides.json",
        replacement_overrides=tmp_path / "replacements.json",
        crosswalks=(tmp_path / "crosswalk.json",),
    )

    loaded = mapping_inputs.load_mapping_inputs(
        paths,
        include_origin_replacements=False,
    )

    assert loaded.en_tags[0]["name"] == "scp"
    assert loaded.mapping_policy.overrides == {}


def test_mapping_inputs_project_to_coverage_contract(tmp_path):
    data_en = tmp_path / "en.json"
    data_jp = tmp_path / "jp.json"
    data_en.write_text(json.dumps([{"name": "scp"}]), encoding="utf-8")
    data_jp.write_text(
        json.dumps([{"name": "scp", "source_tags": ["scp"]}]),
        encoding="utf-8",
    )
    paths = dictionary_inputs.MappingInputPaths(
        data_en=data_en,
        data_jp=data_jp,
        data_deprecated=tmp_path / "deprecated.json",
        overrides=tmp_path / "overrides.json",
        replacement_overrides=tmp_path / "replacements.json",
        crosswalks=(tmp_path / "crosswalk.json",),
    )

    loaded = mapping_inputs.load_mapping_inputs(
        paths,
        include_origin_replacements=False,
    )
    coverage = mapping_inputs.to_coverage_inputs(loaded)

    assert coverage.en_tags is loaded.en_tags
    assert coverage.jp_tags is loaded.jp_tags
    assert coverage.deprecated_tags is loaded.deprecated_tags
    assert coverage.mapping_policy is loaded.mapping_policy


def test_dictionary_command_rejects_unsupported_branch_before_loading(tmp_path):
    with pytest.raises(ValueError, match="unsupported branches"):
        dictionary_workflow.build_and_publish_dictionaries(tmp_path, ["unknown"])


def test_acceptance_fixture_mentions_every_required_branch():
    with ACCEPTANCE.open(encoding="utf-8", newline="") as f:
        branches = {row["branch"] for row in csv.DictReader(f, delimiter="\t")}

    assert branches == set(REQUIRED_BRANCHES)


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
    assert "absurdism" not in policy["source_tags"]["en"]
    assert policy["source_tags"]["en"]["more-by"]["translation_action"] == (
        "omit_jp_unused"
    )
    assert "resource" not in policy["source_tags"]["en"]
    assert policy["source_tags"]["int"]["_cc"]["translation_action"] == (
        "omit_jp_unused"
    )
    assert "_genreless" not in policy["source_tags"]["int"]
    assert set(policy["concatenated_tag_hints"]) == set(REQUIRED_BRANCHES)
    for branch, hints in policy["concatenated_tag_hints"].items():
        dictionary = _load_json(DICTIONARIES / f"{branch}_to_jp.json")
        assert set(hints).isdisjoint(dictionary)
    assert any(
        any(left == "scp" and right == "sculpture" for left, right in zip(tags, tags[1:]))
        for tags in policy["concatenated_tag_hints"]["int"].values()
    )
