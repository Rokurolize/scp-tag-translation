import json
from pathlib import Path

import pytest

from scripts.parsers import en_parser, jp_parser

ROOT = Path(__file__).parent.parent
EN_SOURCE = ROOT / "sources" / "en" / "tag-list.txt"
JP_SOURCE_DIR = ROOT / "sources" / "jp"
DICT_FILE = ROOT / "dictionaries" / "en_to_jp.json"
DEPRECATED_DICT_FILE = ROOT / "dictionaries" / "deprecated_en_to_jp.json"


@pytest.fixture(scope="session")
def en_tags_data():
    return en_parser.parse_en_tags(EN_SOURCE)


@pytest.fixture(scope="session")
def jp_tags_data():
    return jp_parser.parse_jp_tags(JP_SOURCE_DIR)


@pytest.fixture(scope="session")
def deprecated_tags_data():
    return jp_parser.parse_unused(JP_SOURCE_DIR / "fragment-unused.txt")


@pytest.fixture(scope="session")
def committed_dict():
    return json.loads(DICT_FILE.read_text())


@pytest.fixture(scope="session")
def committed_deprecated_dict():
    return json.loads(DEPRECATED_DICT_FILE.read_text())


@pytest.fixture(scope="session")
def en_tag_names(en_tags_data):
    return {e["name"] for e in en_tags_data}
