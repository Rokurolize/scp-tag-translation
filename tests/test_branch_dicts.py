import csv
import json
from pathlib import Path

import pytest

from scripts.corpus import (
    collect_corpus_branch_data,
    discover_corpus_branches,
)
from scripts import dictionary_inputs
from scripts.dictionary_inputs import LoadedMappingInputs, load_existing_hint_dictionaries
from scripts.commands import build_branch_dicts_from_corpus as branch_builder
from scripts.domain import tag_policy
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.jp_policy import JpPolicyInputs, build_jp_policy
from scripts.domain.tag_policy import EN_ORIGIN_TAG_REPLACEMENTS
from scripts.domain.tag_validation import validate_tag_records

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


@pytest.fixture
def controlled_branch_artifacts(tmp_path):
    corpus_root = tmp_path / "corpus"
    page_dir = corpus_root / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe", "scp", "horror"]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "dictionaries"
    policy_path = output_dir / "jp_tag_policy.json"
    en_tags = [
        {"name": "safe"},
        {"name": "scp"},
        {"name": "horror", "category": "Genre"},
    ]
    jp_tags = [
        {"name": "safe", "source_tags": []},
        {"name": "scp", "source_tags": []},
        {"name": "ホラー", "source_tags": ["horror"]},
    ]
    jp_names, jp_source_map = tag_policy.build_jp_names_and_source_map(jp_tags)
    policy = tag_policy.MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags={},
        replacements={},
        overrides={},
        official_crosswalk={},
    )
    en_tags, jp_tags, deprecated_tags = validate_tag_records(
        en_tags,
        jp_tags,
        [],
    )

    artifacts = branch_builder.build_artifacts(
        {"en": collect_corpus_branch_data(corpus_root, "en")},
        ["en"],
        LoadedMappingInputs(
            en_tags=en_tags,
            jp_tags=jp_tags,
            deprecated_tags=deprecated_tags,
            mapping_policy=policy,
        ),
        config=branch_builder.BranchBuildConfig(
            dictionaries_dir=output_dir,
            jp_policy_path=policy_path,
            supported_branches=("en",),
        ),
    )
    return corpus_root, artifacts, output_dir, policy_path


def test_build_artifacts_owns_complete_publication_set(
    controlled_branch_artifacts,
):
    _corpus_root, artifacts, output_dir, policy_path = controlled_branch_artifacts

    assert set(artifacts.outputs) == {
        output_dir / "en_to_jp.json",
        output_dir / "deprecated_en_to_jp.json",
        policy_path,
    }
    assert artifacts.outputs[output_dir / "en_to_jp.json"] == {
        "horror": "ホラー",
        "safe": "safe",
        "scp": "scp",
    }
    assert artifacts.outputs[policy_path]["concatenated_tag_hints"] == {
        "en": {}
    }
    assert artifacts.hint_count == 0


def test_build_and_publish_success_path_uses_real_inputs_and_outputs(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "dictionaries"
    data_dir.mkdir()
    source_dir.mkdir()

    data_paths = {
        "data_en": data_dir / "en_tags.json",
        "data_jp": data_dir / "jp_tags.json",
        "data_deprecated": data_dir / "deprecated_tags.json",
        "int_crosswalk": data_dir / "int_tag_crosswalk.json",
        "ko_crosswalk": data_dir / "ko_tag_crosswalk.json",
        "branch_guide_crosswalk": data_dir / "branch_guide_crosswalk.json",
    }

    overrides_path = source_dir / "branch_to_jp_overrides.json"
    replacement_overrides_path = (
        source_dir / "deprecated_replacement_overrides.json"
    )
    crosswalk_paths = (
        data_paths["int_crosswalk"],
        data_paths["ko_crosswalk"],
        data_paths["branch_guide_crosswalk"],
    )
    monkeypatch.setattr(dictionary_inputs, "OVERRIDES_PATH", overrides_path)
    monkeypatch.setattr(
        dictionary_inputs,
        "DEPRECATED_REPLACEMENT_OVERRIDES_PATH",
        replacement_overrides_path,
    )
    monkeypatch.setattr(dictionary_inputs, "CROSSWALK_PATHS", crosswalk_paths)

    en_tags = [
        {"name": "safe"},
        {"name": "scp"},
        {"name": "horror", "category": "Genre"},
    ]
    jp_names = {
        "safe",
        "scp",
        "ホラー",
        *EN_ORIGIN_TAG_REPLACEMENTS.values(),
    }
    jp_tags = [
        {
            "name": name,
            "source_tags": ["horror"] if name == "ホラー" else [],
        }
        for name in sorted(jp_names)
    ]
    for path, value in (
        (data_paths["data_en"], en_tags),
        (data_paths["data_jp"], jp_tags),
        (data_paths["data_deprecated"], []),
        (overrides_path, {}),
        (replacement_overrides_path, {}),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")
    for path in crosswalk_paths:
        path.write_text("{}", encoding="utf-8")

    corpus_root = tmp_path / "corpus"
    page_dir = corpus_root / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe", "scp", "horror"]}),
        encoding="utf-8",
    )
    config = branch_builder.BranchBuildConfig(
        dictionaries_dir=output_dir,
        jp_policy_path=output_dir / "jp_tag_policy.json",
        supported_branches=("en",),
        mapping_inputs=dictionary_inputs.MappingInputPaths(
            data_en=data_paths["data_en"],
            data_jp=data_paths["data_jp"],
            data_deprecated=data_paths["data_deprecated"],
            overrides=overrides_path,
            replacement_overrides=replacement_overrides_path,
            crosswalks=crosswalk_paths,
        ),
    )

    artifacts = branch_builder.build_and_publish(
        corpus_root,
        ["en"],
        config=config,
    )

    assert set(artifacts.outputs) == {
        output_dir / "en_to_jp.json",
        output_dir / "deprecated_en_to_jp.json",
        output_dir / "jp_tag_policy.json",
    }
    assert _load_json(output_dir / "en_to_jp.json")["horror"] == "ホラー"
    assert _load_json(output_dir / "jp_tag_policy.json")["schema_version"] == 2


def test_build_jp_policy_preserves_tag_and_source_policy_rules():
    policy = build_jp_policy(
        JpPolicyInputs(
            jp_tags=[
                {
                    "name": "ホラー",
                    "source_tags": ["horror"],
                    "description": "",
                },
                {
                    "name": "restricted",
                    "source_tags": [],
                    "use_restricted": True,
                },
            ],
            deprecated_tags=[],
            en_tags=[
                {"name": "horror", "category": "Genre"},
                {"name": "genreless", "category": "Genre"},
            ],
            mapping_policy=tag_policy.MappingPolicy(
                jp_names=frozenset({"ホラー", "restricted"}),
                jp_source_map={"horror": "ホラー"},
                deprecated_tags={},
                replacements={},
                overrides={},
                official_crosswalk={},
            ),
            concatenated_tag_hints={},
        )
    )

    assert policy["tags"]["ホラー"]["copy_allowed_for_translation"] is True
    assert policy["tags"]["restricted"]["copy_allowed_for_translation"] is False
    assert "horror" not in policy["source_tags"].get("en", {})
    assert policy["source_tags"]["en"]["genreless"]["translation_action"] == (
        "omit_translation_policy"
    )


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
    complete = load_existing_hint_dictionaries(
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


def test_generated_dictionary_covers_every_tag_in_controlled_corpus(
    controlled_branch_artifacts,
):
    corpus_root, artifacts, output_dir, _policy_path = controlled_branch_artifacts
    corpus_tags = collect_corpus_branch_data(corpus_root, "en").source_tags
    dictionary = artifacts.outputs[output_dir / "en_to_jp.json"]

    assert corpus_tags <= set(dictionary)
    assert dictionary["horror"] == "ホラー"


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
