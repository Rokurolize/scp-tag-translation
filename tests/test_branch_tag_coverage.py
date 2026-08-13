import json
import sys

import pytest

from scripts.commands import build_branch_tag_coverage_data as coverage_builder
from scripts.corpus import collect_branch_tag_stats
from scripts import dictionary_inputs
from scripts.domain import tag_coverage
from scripts.domain import tag_policy
from scripts.domain.tag_policy import MappingPolicy


def _write_page(corpus_root, branch, slug, tags):
    meta_path = corpus_root / branch / "pages" / slug / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(
        json.dumps({"tags": tags}, ensure_ascii=False),
        encoding="utf-8",
    )


def _coverage_inputs():
    jp_tags = [
        {"name": "scp", "source_tags": []},
        {"name": "cn", "source_tags": []},
        {"name": "euclid", "source_tags": ["euclidean", "international"]},
        {"name": "tale", "source_tags": []},
        {"name": "copy", "source_tags": []},
        {
            "name": "restricted",
            "source_tags": [],
            "use_restricted": True,
        },
        {
            "name": "omit",
            "source_tags": [],
            "description": "他言語やSCP-INTに翻訳された記事には付与しないでください",
        },
        {"name": "replacement", "source_tags": []},
        {"name": "外部ウィキアーカイブ", "source_tags": []},
        {"name": "ホラー", "source_tags": ["horror"]},
    ]
    mapping_policy = MappingPolicy(
        jp_names=frozenset(entry["name"] for entry in jp_tags),
        jp_source_map={
            "euclidean": "euclid",
            "international": "euclid",
            "horror": "ホラー",
        },
        deprecated_tags={
            "CN": {"wanderers"},
            "EN": {"legacy", "unused"},
        },
        replacements={
            "CN": {"wanderers": "外部ウィキアーカイブ"},
            "EN": {"legacy": "replacement", "unused": None},
        },
        overrides={"cn": {"原创": "cn"}},
        official_crosswalk={
            "cn": {"official": "tale", "international": "tale"}
        },
    )
    return tag_coverage.CoverageInputs(
        en_tags=[
            {"name": "genre", "category": "Genre"},
            {"name": "horror", "category": "Genre"},
        ],
        jp_tags=jp_tags,
        deprecated_tags=[
            {
                "source_lang": "CN",
                "source_tag": "wanderers",
                "replacement": "外部ウィキアーカイブ",
            },
            {
                "source_lang": "EN",
                "source_tag": "legacy",
                "replacement": "replacement",
            },
            {"source_lang": "EN", "source_tag": "unused"},
        ],
        mapping_policy=mapping_policy,
    )


def test_build_coverage_classifies_corpus_tags_and_preserves_ordering(tmp_path):
    corpus_root = tmp_path / "corpus"
    _write_page(
        corpus_root,
        "cn",
        "sample",
        [
            "scp",
            "euclidean",
            "wanderers",
            "原创",
            "official",
            "international",
            "unknown",
        ],
    )
    _write_page(
        corpus_root,
        "en",
        "a",
        [
            "copy",
            "legacy",
            "restricted",
            "omit",
            "genre",
            "unknown",
            "horror",
            "unused",
        ],
    )
    _write_page(corpus_root, "en", "b", ["copy"])

    coverage = tag_coverage.build_coverage(
        str(corpus_root),
        ["cn", "en"],
        _coverage_inputs(),
        {
            branch: collect_branch_tag_stats(corpus_root, branch)
            for branch in ("cn", "en")
        },
    )

    assert coverage["schema_version"] == 3
    assert coverage["source"]["corpus_root"] == str(corpus_root)
    assert coverage["status_descriptions"] == tag_coverage.STATUS_DESCRIPTIONS
    assert coverage["action_descriptions"] == tag_coverage.ACTION_DESCRIPTIONS
    assert [branch["branch"] for branch in coverage["branches"]] == ["cn", "en"]

    cn_entries = {
        entry["tag"]: entry for entry in coverage["branches"][0]["tags"]
    }
    assert cn_entries["scp"]["status"] == "jp_tag_name"
    assert cn_entries["euclidean"]["status"] == "jp_tag_alias"
    assert cn_entries["wanderers"]["status"] == "jp_unused_replacement"
    assert cn_entries["原创"]["status"] == "curated_override_only"
    assert cn_entries["official"]["status"] == "official_crosswalk"
    assert cn_entries["international"]["status"] == "official_crosswalk"
    assert cn_entries["unknown"]["status"] == "unhandled"

    en_branch = coverage["branches"][1]
    en_entries = {entry["tag"]: entry for entry in en_branch["tags"]}
    assert en_branch["page_count"] == 2
    assert en_branch["tags"][0]["tag"] == "copy"
    assert en_entries["copy"]["rank"] == 1
    assert en_entries["copy"]["page_count"] == 2
    assert en_entries["copy"]["sample_slugs"] == ["a", "b"]
    assert en_entries["legacy"]["translation_action"] == "copy_replacement"
    assert en_entries["restricted"]["translation_action"] == (
        "staff_permission_required"
    )
    assert en_entries["restricted"]["copy_allowed"] is False
    assert en_entries["omit"]["translation_action"] == "omit_jp_policy"
    assert en_entries["genre"]["status"] == "jp_translation_policy_omit"
    assert en_entries["genre"]["translation_action"] == (
        "omit_translation_policy"
    )
    assert en_entries["genre"]["display_tag"] is None
    assert en_entries["unused"]["translation_action"] == "omit_jp_unused"
    assert en_entries["unknown"]["display_tag"] == "未訳-unknown"

    # Explicit JP mappings take precedence over the EN genre omission policy.
    assert en_entries["horror"]["status"] == "jp_tag_alias"
    assert en_entries["horror"]["translation_action"] == "copy"
    assert en_entries["horror"]["display_tag"] == "ホラー"

    inventory = tag_coverage.build_application_inventory(coverage)
    assert inventory["schema_version"] == 1
    assert [branch["branch"] for branch in inventory["branches"]] == ["cn", "en"]
    assert [
        entry["tag"]
        for branch in inventory["branches"]
        for entry in branch["tags"]
    ] == ["unknown", "unknown"]


def test_build_coverage_rejects_missing_mapped_target_policy(tmp_path):
    corpus_root = tmp_path / "corpus"
    _write_page(corpus_root, "en", "sample", ["mapped"])
    inputs = tag_coverage.CoverageInputs(
        en_tags=[],
        jp_tags=[],
        deprecated_tags=[],
        mapping_policy=MappingPolicy(
            jp_names=frozenset({"mapped"}),
            jp_source_map={},
            deprecated_tags={},
            replacements={},
            overrides={},
            official_crosswalk={},
        ),
    )

    with pytest.raises(ValueError, match="JP policy missing"):
        tag_coverage.build_coverage(
            str(corpus_root),
            ["en"],
            inputs,
            {"en": collect_branch_tag_stats(corpus_root, "en")},
        )


def test_build_coverage_rejects_non_object_metadata(tmp_path):
    corpus_root = tmp_path / "corpus"
    meta_path = corpus_root / "en" / "pages" / "sample" / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text("[]", encoding="utf-8")
    inputs = tag_coverage.CoverageInputs(
        en_tags=[],
        jp_tags=[],
        deprecated_tags=[],
        mapping_policy=MappingPolicy(
            jp_names=frozenset(),
            jp_source_map={},
            deprecated_tags={},
            replacements={},
            overrides={},
            official_crosswalk={},
        ),
    )

    with pytest.raises(ValueError, match="metadata root must be an object"):
        tag_coverage.build_coverage(
            str(corpus_root),
            ["en"],
            inputs,
            {"en": collect_branch_tag_stats(corpus_root, "en")},
        )


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
    monkeypatch.setattr(coverage_builder, "load_coverage_inputs", lambda: object())
    monkeypatch.setattr(
        coverage_builder,
        "collect_branch_tag_stats",
        lambda _corpus_root, _branch: {"page_count": 0, "tags": {}},
    )
    monkeypatch.setattr(
        coverage_builder,
        "build_coverage",
        lambda _corpus_root, _branches, _inputs, _branch_tag_stats: coverage,
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


def test_coverage_main_publishes_all_outputs_from_real_inputs(
    tmp_path,
    monkeypatch,
    capsys,
):
    corpus_root = tmp_path / "corpus"
    _write_page(corpus_root, "en", "sample", ["scp"])
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    jp_names = {"scp", *tag_policy.EN_ORIGIN_TAG_REPLACEMENTS.values()}
    data_paths = {
        "DATA_EN": data_dir / "en_tags.json",
        "DATA_JP": data_dir / "jp_tags.json",
        "DATA_DEPRECATED": data_dir / "deprecated_tags.json",
    }
    data_paths["DATA_EN"].write_text(
        json.dumps([{"name": "scp"}]),
        encoding="utf-8",
    )
    data_paths["DATA_JP"].write_text(
        json.dumps([
            {"name": name, "source_tags": []}
            for name in sorted(jp_names)
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    data_paths["DATA_DEPRECATED"].write_text("[]", encoding="utf-8")
    for name, path in data_paths.items():
        monkeypatch.setattr(coverage_builder, name, path)

    override_path = tmp_path / "overrides.json"
    replacement_path = tmp_path / "replacement_overrides.json"
    override_path.write_text("{}", encoding="utf-8")
    replacement_path.write_text("{}", encoding="utf-8")
    crosswalk_paths = []
    for index in range(3):
        path = tmp_path / f"crosswalk-{index}.json"
        path.write_text("{}", encoding="utf-8")
        crosswalk_paths.append(path)
    monkeypatch.setattr(dictionary_inputs, "OVERRIDES_PATH", override_path)
    monkeypatch.setattr(
        dictionary_inputs,
        "DEPRECATED_REPLACEMENT_OVERRIDES_PATH",
        replacement_path,
    )
    monkeypatch.setattr(
        dictionary_inputs,
        "CROSSWALK_PATHS",
        tuple(crosswalk_paths),
    )

    output_dir = tmp_path / "visualization"
    monkeypatch.setattr(coverage_builder, "DEFAULT_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_data.py",
            "--corpus-root",
            str(corpus_root),
            "--branches",
            "en",
        ],
    )

    coverage_builder.main()

    assert "可視化データ生成完了: 1支部, 1タグ" in capsys.readouterr().out
    expected_outputs = {
        "branch_tag_coverage.json",
        "branch_tag_coverage.tsv",
        "tag_application_inventory.json",
        "tag_application_inventory.tsv",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_outputs
    coverage = json.loads(
        (output_dir / "branch_tag_coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["branches"][0]["tags"][0]["tag"] == "scp"
