"""Repository artifact locations and command-facing JSON loading."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_DIR = ROOT / "sources"
DICTIONARIES_DIR = ROOT / "dictionaries"
VISUALIZATION_DIR = ROOT / "visualization"

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
JP_POLICY_PATH = DICTIONARIES_DIR / "jp_tag_policy.json"
EN_DICTIONARY_PATH = DICTIONARIES_DIR / "en_to_jp.json"
DEPRECATED_EN_DICTIONARY_PATH = DICTIONARIES_DIR / "deprecated_en_to_jp.json"
BROWSER_CONFIG_PATH = ROOT / "branch_config.js"
COVERAGE_JSON_PATH = VISUALIZATION_DIR / "branch_tag_coverage.json"
COVERAGE_HTML_PATH = VISUALIZATION_DIR / "branch_tag_coverage.html"
