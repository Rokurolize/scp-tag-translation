import sys

import pytest

from scripts.commands import build_branch_tag_coverage_data as coverage_builder
from scripts.domain import tag_policy


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
