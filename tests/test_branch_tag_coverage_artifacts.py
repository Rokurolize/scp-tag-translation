import csv
import json

import pytest

from scripts.infrastructure.data_paths import ROOT
from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.tag_coverage import ACTION_DESCRIPTIONS, STATUS_DESCRIPTIONS
from scripts.pipeline.coverage_outputs import (
    write_application_inventory_tsv,
    write_coverage_tsv,
)

COVERAGE_JSON = ROOT / "visualization" / "branch_tag_coverage.json"
COVERAGE_TSV = ROOT / "visualization" / "branch_tag_coverage.tsv"
APPLICATION_JSON = ROOT / "visualization" / "tag_application_inventory.json"
APPLICATION_TSV = ROOT / "visualization" / "tag_application_inventory.tsv"
REQUIRED_BRANCHES = list(SUPPORTED_BRANCHES)
KNOWN_STATUSES = set(STATUS_DESCRIPTIONS)
KNOWN_ACTIONS = set(ACTION_DESCRIPTIONS)


@pytest.fixture
def coverage():
    return json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))


def test_visualization_files_exist_and_cover_required_branches(coverage):
    assert COVERAGE_JSON.exists()
    assert COVERAGE_TSV.exists()

    branches = [branch["branch"] for branch in coverage["branches"]]
    assert branches == REQUIRED_BRANCHES
    assert set(coverage["status_descriptions"]) == KNOWN_STATUSES
    assert set(coverage["action_descriptions"]) == KNOWN_ACTIONS


def test_visualization_entries_have_known_statuses_and_required_fields(coverage):
    for branch in coverage["branches"]:
        assert branch["tag_count"] == len(branch["tags"])
        for entry in branch["tags"]:
            assert entry["status"] in KNOWN_STATUSES
            assert isinstance(entry["recognized_by_jp_policy"], bool)
            assert isinstance(entry["copy_allowed"], bool)
            assert isinstance(entry["translation_action"], str)
            assert isinstance(entry["sample_slugs"], list)


def test_visualization_tsv_exactly_matches_json(coverage):
    expected_rows = []
    for branch in coverage["branches"]:
        for entry in branch["tags"]:
            expected_rows.append({
                "branch": branch["branch"],
                "tag": entry["tag"],
                "rank": str(entry["rank"]),
                "page_count": str(entry["page_count"]),
                "status": entry["status"],
                "recognized_by_jp_policy": str(
                    entry["recognized_by_jp_policy"]
                ).lower(),
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


def test_visualization_records_expected_status_examples(coverage):
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


def test_application_inventory_exactly_matches_unhandled_coverage(coverage):
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


def test_coverage_serializers_preserve_nullable_and_delimited_fields(tmp_path):
    coverage = {
        "schema_version": 3,
        "source": {},
        "status_descriptions": {},
        "action_descriptions": {},
        "branches": [{
            "branch": "en",
            "site": "site",
            "page_count": 1,
            "tag_count": 1,
            "status_counts": {},
            "tags": [{
                "tag": "tag\twith",
                "rank": 1,
                "page_count": 1,
                "sample_slugs": ["slug,one", "line\nslug"],
                "status": "unhandled",
                "recognized_by_jp_policy": False,
                "jp_tag": None,
                "replacement": None,
                "translation_action": "tag_application_required",
                "copy_allowed": True,
                "display_tag": "display\tvalue",
                "target_policy": None,
            }],
        }],
    }
    inventory = {
        "schema_version": 1,
        "rule": "unhandled",
        "branches": [{
            "branch": "en",
            "site": "site\tname",
            "scanned_page_count": 1,
            "tag_count": 1,
            "tags": [{
                "tag": "tag\twith",
                "display_tag": "display, value",
                "page_count": 1,
                "sample_slugs": ["slug,one", "line\nslug"],
            }],
        }],
    }

    coverage_path = tmp_path / "coverage.tsv"
    inventory_path = tmp_path / "inventory.tsv"
    write_coverage_tsv(coverage_path, coverage)
    write_application_inventory_tsv(inventory_path, inventory)

    with coverage_path.open(encoding="utf-8", newline="") as file:
        coverage_rows = list(csv.DictReader(file, delimiter="\t"))
    with inventory_path.open(encoding="utf-8", newline="") as file:
        inventory_rows = list(csv.DictReader(file, delimiter="\t"))

    assert coverage_rows == [{
        "branch": "en",
        "tag": "tag\twith",
        "rank": "1",
        "page_count": "1",
        "status": "unhandled",
        "recognized_by_jp_policy": "false",
        "jp_tag": "",
        "replacement": "",
        "translation_action": "tag_application_required",
        "copy_allowed": "true",
        "display_tag": "display\tvalue",
        "sample_slugs": "slug,one,line\nslug",
    }]
    assert inventory_rows == [{
        "site": "site\tname",
        "branch": "en",
        "source_tag": "tag\twith",
        "display_tag": "display, value",
        "page_count": "1",
        "sample_slugs": "slug,one,line\nslug",
    }]
