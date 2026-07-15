import sys

import pytest

from scripts.commands import build_branch_tag_coverage_data as coverage_builder
from scripts.domain import tag_policy
from scripts.domain.tag_validation import validate_coverage


def test_classify_tag_distinguishes_jp_list_and_override_states():
    jp_names = {"scp", "cn", "euclid", "tale", "外部ウィキアーカイブ"}
    jp_source_map = {"euclidean": "euclid", "international": "euclid"}
    deprecated_tags = {"CN": {"wanderers"}}
    replacements = {"CN": {"wanderers": "外部ウィキアーカイブ"}}
    overrides = {"cn": {"原创": "cn"}}
    policy = {
        tag: {
            "copy_allowed_for_translation": True,
            "use_restricted": False,
            "edit_restricted": False,
            "translation_exempt": False,
            "special_translation_action": None,
        }
        for tag in jp_names
    }
    mapping_policy = tag_policy.MappingPolicy(
        jp_names=frozenset(jp_names),
        jp_source_map=jp_source_map,
        deprecated_tags=deprecated_tags,
        replacements=replacements,
        overrides=overrides,
        official_crosswalk={
            "cn": {"official": "tale", "international": "tale"}
        },
    )
    context = coverage_builder.ClassificationContext.for_branch(
        mapping_policy,
        "cn",
        target_policies=policy,
    )

    def classify(tag):
        return coverage_builder.classify_tag(tag, context)["status"]

    assert classify("scp") == "jp_tag_name"
    assert classify("euclidean") == "jp_tag_alias"
    assert classify("wanderers") == "jp_unused_replacement"
    assert classify("原创") == "curated_override_only"
    assert classify("official") == "official_crosswalk"
    assert classify("international") == "official_crosswalk"
    assert classify("unknown") == "unhandled"


def test_classify_tag_applies_copy_and_omission_policy():
    mapping_policy = tag_policy.MappingPolicy(
        jp_names=frozenset({"copy", "restricted", "omit", "replacement"}),
        jp_source_map={},
        deprecated_tags={"EN": {"legacy"}},
        replacements={"EN": {"legacy": "replacement"}},
        overrides={},
        official_crosswalk={},
    )
    target_policies = {
        tag: {
            "copy_allowed_for_translation": tag in {"copy", "replacement"},
            "use_restricted": tag == "restricted",
            "edit_restricted": False,
            "translation_exempt": False,
            "special_translation_action": "omit" if tag == "omit" else None,
        }
        for tag in mapping_policy.jp_names
    }
    context = coverage_builder.ClassificationContext.for_branch(
        mapping_policy,
        "en",
        target_policies=target_policies,
        translation_policy_omit={"genre"},
    )

    assert coverage_builder.classify_tag("copy", context)["translation_action"] == (
        "copy"
    )
    assert coverage_builder.classify_tag("legacy", context)[
        "translation_action"
    ] == "copy_replacement"
    restricted = coverage_builder.classify_tag("restricted", context)
    assert restricted["translation_action"] == "staff_permission_required"
    assert restricted["copy_allowed"] is False
    assert coverage_builder.classify_tag("omit", context)["translation_action"] == (
        "omit_jp_policy"
    )
    genre = coverage_builder.classify_tag("genre", context)
    assert genre["status"] == "jp_translation_policy_omit"
    assert genre["translation_action"] == "omit_translation_policy"
    assert genre["display_tag"] is None
    assert coverage_builder.classify_tag("unknown", context)["display_tag"] == (
        "未訳-unknown"
    )


def test_classify_tag_rejects_missing_mapped_target_policy():
    mapping_policy = tag_policy.MappingPolicy(
        jp_names=frozenset({"mapped"}),
        jp_source_map={},
        deprecated_tags={},
        replacements={},
        overrides={},
        official_crosswalk={},
    )
    context = coverage_builder.ClassificationContext.for_branch(
        mapping_policy,
        "en",
        target_policies={},
    )

    with pytest.raises(ValueError, match="JP policy missing"):
        coverage_builder.classify_tag("mapped", context)


def test_collect_branch_tag_stats_rejects_non_object_metadata(tmp_path):
    meta_path = tmp_path / "corpus" / "en" / "pages" / "sample" / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="metadata root must be an object"):
        coverage_builder.collect_branch_tag_stats(tmp_path / "corpus", "en")


def test_coverage_main_reports_publication_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    coverage = {
        "schema_version": 1,
        "source": {},
        "status_descriptions": {},
        "branches": [],
    }
    monkeypatch.setattr(
        coverage_builder,
        "build_coverage",
        lambda _corpus_root, _branches: coverage,
    )
    monkeypatch.setattr(
        coverage_builder,
        "build_application_inventory",
        lambda _coverage: {"branches": []},
    )

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(
        coverage_builder,
        "publish_files_atomically",
        fail_publication,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_data.py",
            "--corpus-root",
            str(corpus_root),
            "--output-dir",
            str(tmp_path / "output"),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_builder.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "エラー: 可視化データ生成に失敗しました: disk full\n"
    )
    assert not (tmp_path / "output").exists()


def _minimal_coverage_tag():
    return {
        "tag": "scp",
        "status": "jp_tag_name",
        "recognized_by_jp_policy": True,
        "jp_tag": "scp",
        "replacement": None,
        "translation_action": "copy",
        "copy_allowed": True,
        "display_tag": "scp",
        "rank": 1,
        "page_count": 1,
        "sample_slugs": ["sample"],
        "target_policy": {
            "use_restricted": False,
            "edit_restricted": False,
            "translation_exempt": False,
            "copy_allowed_for_translation": True,
            "special_translation_action": None,
        },
    }


def _minimal_coverage_document(tag):
    return {
        "schema_version": 1,
        "source": {
            "corpus_root": "corpus",
            "jp_tag_source": "jp",
            "jp_unused_source": "unused",
            "override_source": "override",
            "deprecated_override_source": "deprecated",
            "crosswalk_source": "crosswalk",
        },
        "status_descriptions": {
            "jp_unused_replacement": "",
            "jp_unused_no_single_replacement": "",
            "jp_translation_policy_omit": "",
            "jp_tag_name": "",
            "jp_tag_alias": "",
            "curated_override_only": "",
            "official_crosswalk": "",
            "unhandled": "",
        },
        "action_descriptions": {
            "copy": "",
            "copy_replacement": "",
            "omit_jp_policy": "",
            "omit_jp_unused": "",
            "omit_translation_policy": "",
            "staff_permission_required": "",
            "tag_application_required": "",
        },
        "branches": [{
            "branch": "en",
            "site": "EN",
            "page_count": 1,
            "tag_count": 1,
            "status_counts": {
                "jp_unused_replacement": 0,
                "jp_unused_no_single_replacement": 0,
                "jp_translation_policy_omit": 0,
                "jp_tag_name": 1,
                "jp_tag_alias": 0,
                "curated_override_only": 0,
                "official_crosswalk": 0,
                "unhandled": 0,
            },
            "tags": [tag],
        }],
    }


@pytest.mark.parametrize(
    ("field_path", "message"),
    [
        (("status",), "status must be a string"),
        (("translation_action",), "translation_action must be a string"),
        (
            ("target_policy", "special_translation_action"),
            "special_translation_action must be a string or null",
        ),
    ],
)
def test_validate_coverage_rejects_unhashable_protocol_fields(field_path, message):
    tag = _minimal_coverage_tag()
    target = tag
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = []

    with pytest.raises(ValueError, match=message):
        validate_coverage(_minimal_coverage_document(tag))
