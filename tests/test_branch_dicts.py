import json
import sys
from pathlib import Path

import pytest

from scripts.pipeline.corpus import collect_corpus_branch_data
from scripts.pipeline import dictionary_inputs
from scripts.pipeline.dictionary_inputs import LoadedMappingInputs
from scripts.commands import build_branch_dicts_from_corpus as branch_command
from scripts.application import dictionary_build as dictionary_workflow
from scripts.domain.policy import tag_policy
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.policy.jp_policy import JpPolicyInputs, build_jp_policy
from scripts.domain.policy.tag_policy import EN_ORIGIN_TAG_REPLACEMENTS
from scripts.domain.records.tag_validation import validate_tag_records

ROOT = Path(__file__).parent.parent
DICTIONARIES = ROOT / "dictionaries"
OVERRIDES = ROOT / "sources" / "branch_to_jp_overrides.json"
REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)


def test_branch_dictionary_command_reports_missing_corpus(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_branch_dicts_from_corpus.py", "--corpus-root", str(tmp_path / "missing")],
    )

    with pytest.raises(SystemExit) as excinfo:
        branch_command.main()

    assert excinfo.value.code == 1
    assert "corpus rootが見つかりません" in capsys.readouterr().out


def test_branch_dictionary_command_publishes_successful_build(
    tmp_path,
    monkeypatch,
    capsys,
):
    corpus_root = tmp_path / "corpus"
    page_dir = corpus_root / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe"]}),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_en = data_dir / "en.json"
    data_jp = data_dir / "jp.json"
    data_deprecated = data_dir / "deprecated.json"
    data_en.write_text(json.dumps([{"name": "safe"}]), encoding="utf-8")
    data_jp.write_text(
        json.dumps(
            [
                {"name": "safe", "source_tags": []},
                *[
                    {"name": name, "source_tags": []}
                    for name in EN_ORIGIN_TAG_REPLACEMENTS.values()
                ],
            ]
        ),
        encoding="utf-8",
    )
    data_deprecated.write_text("[]", encoding="utf-8")
    overrides = data_dir / "overrides.json"
    replacements = data_dir / "replacements.json"
    crosswalk = data_dir / "crosswalk.json"
    for path in (overrides, replacements, crosswalk):
        path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "dictionaries"
    config = dictionary_workflow.BranchBuildConfig(
        dictionaries_dir=output_dir,
        jp_policy_path=output_dir / "jp_tag_policy.json",
        supported_branches=("en",),
        mapping_inputs=dictionary_inputs.MappingInputPaths(
            data_en=data_en,
            data_jp=data_jp,
            data_deprecated=data_deprecated,
            overrides=overrides,
            replacement_overrides=replacements,
            crosswalks=(crosswalk,),
        ),
    )
    monkeypatch.setattr(dictionary_workflow, "BranchBuildConfig", lambda: config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_dicts_from_corpus.py",
            "--corpus-root",
            str(corpus_root),
            "--branches",
            "en",
        ],
    )

    branch_command.main()

    dictionary = json.loads(
        (output_dir / "en_to_jp.json").read_text(encoding="utf-8")
    )
    assert dictionary["safe"] == "safe"
    assert "en: 1/20 mapped" in capsys.readouterr().out


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

    artifacts = dictionary_workflow.build_artifacts(
        {"en": collect_corpus_branch_data(corpus_root, "en")},
        ["en"],
        LoadedMappingInputs(
            en_tags=en_tags,
            jp_tags=jp_tags,
            deprecated_tags=deprecated_tags,
            mapping_policy=policy,
        ),
        config=dictionary_workflow.BranchBuildConfig(
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

    assert set(artifacts.dictionary_outputs) | {artifacts.policy_path} == {
        output_dir / "en_to_jp.json",
        output_dir / "deprecated_en_to_jp.json",
        policy_path,
    }
    assert artifacts.dictionary_outputs[output_dir / "en_to_jp.json"] == {
        "horror": "ホラー",
        "safe": "safe",
        "scp": "scp",
    }
    assert artifacts.policy["concatenated_tag_hints"] == {
        "en": {}
    }
    assert artifacts.hint_count == 0


def test_build_and_publish_dictionaries_success_path_uses_real_inputs_and_outputs(
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
    config = dictionary_workflow.BranchBuildConfig(
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

    artifacts = dictionary_workflow.build_and_publish_dictionaries(
        corpus_root,
        ["en"],
        config=config,
    )

    assert set(artifacts.dictionary_outputs) | {artifacts.policy_path} == {
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


def test_generated_dictionary_covers_every_tag_in_controlled_corpus(
    controlled_branch_artifacts,
):
    corpus_root, artifacts, output_dir, _policy_path = controlled_branch_artifacts
    corpus_tags = collect_corpus_branch_data(corpus_root, "en").source_tags
    dictionary = artifacts.dictionary_outputs[output_dir / "en_to_jp.json"]

    assert corpus_tags <= set(dictionary)
    assert dictionary["horror"] == "ホラー"
