"""Repository artifact locations and command-facing JSON loading."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from scripts.domain.tag_policy import MappingPolicyInputs

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


def discover_corpus_branches(corpus_root: Path) -> list[str]:
    branches = []
    for branch_dir in sorted(corpus_root.iterdir()):
        if not branch_dir.is_dir():
            continue
        branch = branch_dir.name
        if branch == "jp" or branch.startswith("_"):
            continue
        pages_dir = branch_dir / "pages"
        if pages_dir.is_dir() and any(pages_dir.glob("*/meta.json")):
            branches.append(branch)
    return branches


def iter_corpus_page_tags(
    corpus_root: Path,
    branch: str,
) -> Iterator[tuple[str, list[str]]]:
    pages_dir = corpus_root / branch / "pages"
    if not pages_dir.is_dir():
        raise ValueError(f"corpus branch pages directory not found: {pages_dir}")

    for meta_path in sorted(pages_dir.glob("*/meta.json")):
        meta = load_json(meta_path)
        if not isinstance(meta, dict):
            raise ValueError(f"metadata root must be an object: {meta_path}")
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, str):
            page_tags = [raw_tags]
        elif isinstance(raw_tags, list):
            if any(not isinstance(tag, str) or not tag for tag in raw_tags):
                raise ValueError(f"invalid tags field in {meta_path}")
            page_tags = list(raw_tags)
            if len(set(page_tags)) != len(page_tags):
                raise ValueError(f"duplicate tags in {meta_path}")
        else:
            raise ValueError(f"invalid tags field in {meta_path}")
        yield meta_path.parent.name, page_tags


def collect_corpus_tags_and_visible_sequences(
    corpus_root: Path,
    branch: str,
) -> tuple[set[str], list[tuple[str, tuple[str, ...]]]]:
    tags: set[str] = set()
    visible_sequences = []
    for slug, page_tags in iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
        visible = tuple(tag for tag in page_tags if not tag.startswith("_"))
        if visible:
            visible_sequences.append((slug, visible))
    return tags, visible_sequences


def corpus_tags_for_branch(corpus_root: Path, branch: str) -> set[str]:
    tags: set[str] = set()
    for _slug, page_tags in iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
    return tags


def complete_hint_dictionaries(
    generated: Mapping[str, dict[str, str | None]],
    *,
    dictionaries_dir: Path = DICTIONARIES_DIR,
    supported_branches: Sequence[str],
) -> dict[str, dict[str, str | None]]:
    complete = dict(generated)
    for branch in supported_branches:
        if branch in complete:
            continue
        path = dictionaries_dir / f"{branch}_to_jp.json"
        if not path.is_file():
            raise ValueError(
                "existing dictionary required for partial hint generation: "
                f"{path}"
            )
        dictionary = load_json(path)
        if not isinstance(dictionary, dict) or any(
            not isinstance(tag, str)
            or (target is not None and not isinstance(target, str))
            for tag, target in dictionary.items()
        ):
            raise ValueError(f"invalid existing dictionary: {path}")
        complete[branch] = dictionary
    return complete
