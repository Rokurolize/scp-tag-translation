import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parsers import en_parser, jp_parser

EN_SOURCE = ROOT / "sources" / "en" / "tag-list.txt"
JP_SOURCE_DIR = ROOT / "sources" / "jp"
DICT_FILE = ROOT / "dictionaries" / "en_to_jp.json"


@pytest.fixture(scope="session")
def en_tags_data(tmp_path_factory):
    out = tmp_path_factory.mktemp("data") / "en_tags.json"
    en_parser.parse(str(EN_SOURCE), str(out))
    return json.loads(out.read_text())


@pytest.fixture(scope="session")
def jp_tags_data(tmp_path_factory):
    out = tmp_path_factory.mktemp("data") / "jp_tags.json"
    jp_parser.parse(str(JP_SOURCE_DIR), str(out))
    return json.loads(out.read_text())


@pytest.fixture(scope="session")
def committed_dict():
    return json.loads(DICT_FILE.read_text())


@pytest.fixture(scope="session")
def en_tag_names(en_tags_data):
    return {e["name"] for e in en_tags_data}
