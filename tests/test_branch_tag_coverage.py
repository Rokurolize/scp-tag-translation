"""Branch tag coverage visualization data tests."""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_branch_tag_coverage_html as coverage_html_builder
import build_branch_tag_coverage_data as coverage_builder
from branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).parent.parent
COVERAGE_JSON = ROOT / "visualization" / "branch_tag_coverage.json"
COVERAGE_TSV = ROOT / "visualization" / "branch_tag_coverage.tsv"
COVERAGE_HTML = ROOT / "visualization" / "branch_tag_coverage.html"
APPLICATION_JSON = ROOT / "visualization" / "tag_application_inventory.json"
APPLICATION_TSV = ROOT / "visualization" / "tag_application_inventory.tsv"

REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)

KNOWN_STATUSES = set(coverage_builder.STATUS_DESCRIPTIONS)


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

    def classify(tag):
        return coverage_builder.classify_tag(
            "cn",
            tag,
            jp_names,
            jp_source_map,
            deprecated_tags,
            replacements,
            overrides,
            policy,
            set(),
            {"cn": {"official": "tale", "international": "tale"}},
        )["status"]

    assert classify("scp") == "jp_tag_name"
    assert classify("euclidean") == "jp_tag_alias"
    assert classify("wanderers") == "jp_unused_replacement"
    assert classify("原创") == "curated_override_only"
    assert classify("official") == "official_crosswalk"
    assert classify("international") == "official_crosswalk"
    assert classify("unknown") == "unhandled"


def test_visualization_files_exist_and_cover_required_branches():
    assert COVERAGE_JSON.exists()
    assert COVERAGE_TSV.exists()

    coverage = _load_coverage()
    branches = [branch["branch"] for branch in coverage["branches"]]
    assert branches == REQUIRED_BRANCHES
    assert set(coverage["status_descriptions"]) == KNOWN_STATUSES


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
