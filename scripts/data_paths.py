"""Repository artifact locations and command-facing JSON loading."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.domain.tag_policy import MappingPolicyInputs

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_DIR = ROOT / "sources"

DATA_EN = DATA_DIR / "en_tags.json"
DATA_JP = DATA_DIR / "jp_tags.json"
DATA_DEPRECATED = DATA_DIR / "deprecated_tags.json"
DATA_INT_CROSSWALK = DATA_DIR / "int_tag_crosswalk.json"
DATA_KO_CROSSWALK = DATA_DIR / "ko_tag_crosswalk.json"
DATA_BRANCH_GUIDE_CROSSWALK = DATA_DIR / "branch_guide_crosswalk.json"
OVERRIDES_PATH = SOURCES_DIR / "branch_to_jp_overrides.json"
DEPRECATED_REPLACEMENT_OVERRIDES_PATH = (
    SOURCES_DIR / "deprecated_replacement_overrides.json"
)
CROSSWALK_PATHS = (
    DATA_INT_CROSSWALK,
    DATA_KO_CROSSWALK,
    DATA_BRANCH_GUIDE_CROSSWALK,
)


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_optional_json(path: Path) -> object:
    return load_json(path) if path.exists() else {}


def load_mapping_policy_inputs() -> MappingPolicyInputs:
    return MappingPolicyInputs(
        overrides=_load_optional_json(OVERRIDES_PATH),
        replacement_overrides=_load_optional_json(
            DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
        ),
        official_crosswalks=tuple(load_json(path) for path in CROSSWALK_PATHS),
    )
