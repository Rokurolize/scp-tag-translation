"""Branch tag coverage visualization data tests."""

import csv
import json
import re
import sys
from pathlib import Path

import pytest

from scripts.commands import build_branch_tag_coverage_html as coverage_html_builder
from scripts.commands import build_branch_tag_coverage_data as coverage_builder
from scripts.domain import tag_policy
from scripts.domain.branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).parent.parent
COVERAGE_JSON = ROOT / "visualization" / "branch_tag_coverage.json"
COVERAGE_TSV = ROOT / "visualization" / "branch_tag_coverage.tsv"
COVERAGE_HTML = ROOT / "visualization" / "branch_tag_coverage.html"
APPLICATION_JSON = ROOT / "visualization" / "tag_application_inventory.json"
APPLICATION_TSV = ROOT / "visualization" / "tag_application_inventory.tsv"
TEMPLATE_HTML = ROOT / "scripts" / "assets" / "branch_tag_coverage.html"

REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)

KNOWN_STATUSES = set(coverage_builder.STATUS_DESCRIPTIONS)
KNOWN_ACTIONS = set(coverage_builder.ACTION_DESCRIPTIONS)


def _load_coverage():
    return json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))


def _load_embedded_html_coverage():
    html = COVERAGE_HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="coverage-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match
    return json.loads(match.group(1)), html


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
    assert restricted["translator_handled"] is False
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


def test_visualization_files_exist_and_cover_required_branches():
    assert COVERAGE_JSON.exists()
    assert COVERAGE_TSV.exists()

    coverage = _load_coverage()
    branches = [branch["branch"] for branch in coverage["branches"]]
    assert branches == REQUIRED_BRANCHES
    assert set(coverage["status_descriptions"]) == KNOWN_STATUSES
    assert set(coverage["action_descriptions"]) == KNOWN_ACTIONS


def test_visualization_entries_have_known_statuses_and_required_fields():
    coverage = _load_coverage()
    for branch in coverage["branches"]:
        assert branch["tag_count"] == len(branch["tags"])
        for entry in branch["tags"]:
            assert entry["status"] in KNOWN_STATUSES
            assert isinstance(entry["jp_list_handled"], bool)
            assert isinstance(entry["translator_handled"], bool)
            assert isinstance(entry["copy_allowed"], bool)
            assert isinstance(entry["translation_action"], str)
            assert isinstance(entry["sample_slugs"], list)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "misspelled", "status is unknown"),
        ("translation_action", "misspelled", "translation_action is unknown"),
    ],
)
def test_coverage_validator_rejects_unknown_protocol_values(
    field,
    value,
    message,
):
    coverage = _load_coverage()
    coverage["branches"][0]["tags"][0][field] = value

    with pytest.raises(ValueError, match=message):
        coverage_html_builder.validate_coverage(coverage)


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ("status_descriptions", "status_descriptions keys"),
        ("action_descriptions", "action_descriptions keys"),
    ],
)
def test_coverage_validator_rejects_unknown_description_keys(mapping, message):
    coverage = _load_coverage()
    coverage[mapping]["misspelled"] = "invalid"

    with pytest.raises(ValueError, match=message):
        coverage_html_builder.validate_coverage(coverage)


def test_coverage_validator_rejects_unknown_status_count_key():
    coverage = _load_coverage()
    coverage["branches"][0]["status_counts"]["misspelled"] = 1

    with pytest.raises(ValueError, match="status_counts is invalid"):
        coverage_html_builder.validate_coverage(coverage)


def test_coverage_validator_rejects_unknown_special_action():
    coverage = _load_coverage()
    coverage["branches"][0]["tags"][0]["target_policy"] = {
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "copy_allowed_for_translation": True,
        "special_translation_action": "misspelled",
    }

    with pytest.raises(ValueError, match="special_translation_action"):
        coverage_html_builder.validate_coverage(coverage)


def test_visualization_tsv_exactly_matches_json():
    coverage = _load_coverage()
    expected_rows = []
    for branch in coverage["branches"]:
        for entry in branch["tags"]:
            expected_rows.append({
                "branch": branch["branch"],
                "tag": entry["tag"],
                "rank": str(entry["rank"]),
                "page_count": str(entry["page_count"]),
                "status": entry["status"],
                "jp_list_handled": str(entry["jp_list_handled"]).lower(),
                "translator_handled": str(entry["translator_handled"]).lower(),
                "jp_tag": entry["jp_tag"] or "",
                "replacement": entry["replacement"] or "",
                "translation_action": entry["translation_action"],
                "copy_allowed": str(entry["copy_allowed"]).lower(),
                "display_tag": entry["display_tag"] or "",
                "sample_slugs": ",".join(entry["sample_slugs"]),
            })

    with COVERAGE_TSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    assert rows == expected_rows


def test_visualization_records_expected_status_examples():
    coverage = _load_coverage()
    by_branch = {
        branch["branch"]: {entry["tag"]: entry for entry in branch["tags"]}
        for branch in coverage["branches"]
    }

    assert by_branch["cn"]["原创"]["status"] == "jp_unused_replacement"
    assert by_branch["pt-br"]["conto"]["status"] == "curated_override_only"
    assert by_branch["zh-tr"]["原創"]["status"] == "jp_unused_replacement"
    assert by_branch["en"]["scp"]["status"] == "jp_tag_name"
    assert by_branch["cn"]["认知危害"]["status"] == "official_crosswalk"
    assert by_branch["de"]["amphibisch"]["status"] == "official_crosswalk"
    assert by_branch["vn"]["hướng-dẫn"]["status"] == "official_crosswalk"
    assert by_branch["ko"]["생물"]["status"] == "official_crosswalk"


def test_visualization_html_is_self_contained_and_embeds_current_data():
    assert COVERAGE_HTML.exists()

    coverage = _load_coverage()
    embedded, html = _load_embedded_html_coverage()

    assert embedded == coverage
    assert html == coverage_html_builder.build_html(coverage)
    assert "fetch(" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert 'id="branchSelect"' in html
    assert 'id="statusFilters"' in html
    assert 'id="tagRows"' in html


def test_dashboard_template_has_one_data_placeholder():
    template = TEMPLATE_HTML.read_text(encoding="utf-8")

    assert template.count("__DATA_JSON__") == 1
    assert '<script type="application/json" id="coverage-data">' in template


def test_application_inventory_exactly_matches_unhandled_coverage():
    coverage = _load_coverage()
    inventory = json.loads(APPLICATION_JSON.read_text(encoding="utf-8"))
    expected = {
        (branch["branch"], entry["tag"])
        for branch in coverage["branches"]
        for entry in branch["tags"]
        if entry["translation_action"] == "tag_application_required"
    }
    actual = {
        (branch["branch"], entry["tag"])
        for branch in inventory["branches"]
        for entry in branch["tags"]
    }
    assert actual == expected
    assert [branch["branch"] for branch in inventory["branches"]] == REQUIRED_BRANCHES
    assert sum(
        branch["scanned_page_count"] for branch in inventory["branches"]
    ) == sum(branch["page_count"] for branch in coverage["branches"])

    with APPLICATION_TSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    expected_rows = [
        {
            "site": branch["site"],
            "branch": branch["branch"],
            "source_tag": entry["tag"],
            "display_tag": entry["display_tag"],
            "page_count": str(entry["page_count"]),
            "sample_slugs": ",".join(entry["sample_slugs"]),
        }
        for branch in inventory["branches"]
        for entry in branch["tags"]
    ]
    assert rows == expected_rows


def test_visualization_html_escapes_embedded_json_script_boundaries():
    html = coverage_html_builder.build_html(
        {
            "schema_version": 1,
            "source": {},
            "status_descriptions": {},
            "branches": [],
            "probe": "</script><p>breakout</p>",
        }
    )

    assert "</script><p>breakout</p>" not in html
    match = re.search(
        r'<script type="application/json" id="coverage-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match
    assert json.loads(match.group(1))["probe"] == "</script><p>breakout</p>"


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


def test_coverage_html_main_reports_input_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    missing_input = tmp_path / "missing.json"
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(missing_input),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out.startswith(
        "エラー: HTML可視化生成に失敗しました: "
    )
    assert not output.exists()


def test_coverage_html_main_rejects_invalid_nested_schema(
    tmp_path,
    monkeypatch,
    capsys,
):
    invalid_input = tmp_path / "invalid.json"
    invalid_input.write_text(
        json.dumps({
            "schema_version": 1,
            "source": {},
            "status_descriptions": {},
            "action_descriptions": {},
            "branches": [],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(invalid_input),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert "coverage.source.corpus_root" in capsys.readouterr().out
    assert not output.exists()


def test_coverage_html_main_preserves_output_on_publication_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    input_path = tmp_path / "coverage.json"
    input_path.write_text("{}", encoding="utf-8")
    output = tmp_path / "coverage.html"
    output.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(
        coverage_html_builder,
        "validate_coverage",
        lambda raw: raw,
    )

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(
        coverage_html_builder,
        "publish_files_atomically",
        fail_publication,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(input_path),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "エラー: HTML可視化生成に失敗しました: disk full\n"
    )
    assert output.read_text(encoding="utf-8") == "previous"
