"""Load policy inputs and complete generated branch dictionaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from scripts.data_paths import (
    CROSSWALK_PATHS,
    DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
    DICTIONARIES_DIR,
    OVERRIDES_PATH,
)
from scripts.domain.tag_records import (
    BranchOverrideFile,
    OfficialCrosswalkFile,
    ReplacementOverrideFile,
)
from scripts.domain.policy_builder import MappingPolicyInputs
from scripts.json_io import load_json


def _load_optional_json(path: Path) -> object:
    return load_json(path) if path.exists() else {}


def _load_json_object(path: Path, label: str) -> dict[object, object]:
    raw = _load_optional_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return raw


def _load_override_file(path: Path) -> BranchOverrideFile:
    raw = _load_json_object(path, "branch override file")
    for branch, branch_values in raw.items():
        if not isinstance(branch, str) or not isinstance(branch_values, dict):
            raise ValueError(f"invalid override branch in {path}: {branch!r}")
        for source_tag, value in branch_values.items():
            if not isinstance(source_tag, str) or not source_tag:
                raise ValueError(
                    f"invalid override source tag in {path}: {source_tag!r}"
                )
            if isinstance(value, str):
                continue
            if not isinstance(value, dict) or not isinstance(
                value.get("jp_tag"),
                str,
            ):
                raise ValueError(
                    f"invalid override value in {path}: {branch}:{source_tag}"
                )
            if "note" in value and not isinstance(value["note"], str):
                raise ValueError(
                    f"invalid override note in {path}: {branch}:{source_tag}"
                )
    return cast(BranchOverrideFile, raw)


def _load_replacement_overrides(path: Path) -> ReplacementOverrideFile:
    raw = _load_json_object(path, "replacement override file")
    for source_lang, mappings in raw.items():
        if not isinstance(source_lang, str) or not isinstance(mappings, dict):
            raise ValueError(
                f"invalid replacement override language in {path}: {source_lang!r}"
            )
        for source_tag, replacement in mappings.items():
            if not isinstance(source_tag, str) or not isinstance(replacement, str):
                raise ValueError(
                    f"invalid replacement override in {path}: {source_lang}:{source_tag}"
                )
    return cast(ReplacementOverrideFile, raw)


def _load_crosswalk(path: Path) -> OfficialCrosswalkFile:
    raw = _load_json_object(path, "official crosswalk")
    for branch, mappings in raw.items():
        if not isinstance(branch, str) or not isinstance(mappings, dict):
            raise ValueError(f"invalid crosswalk branch in {path}: {branch!r}")
        for source_tag, jp_tag in mappings.items():
            if not isinstance(source_tag, str) or not isinstance(jp_tag, str):
                raise ValueError(
                    f"invalid crosswalk mapping in {path}: {branch}:{source_tag}"
                )
    return cast(OfficialCrosswalkFile, raw)


def load_mapping_policy_inputs() -> MappingPolicyInputs:
    return MappingPolicyInputs(
        overrides=_load_override_file(OVERRIDES_PATH),
        replacement_overrides=_load_replacement_overrides(
            DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
        ),
        official_crosswalks=tuple(
            _load_crosswalk(path) for path in CROSSWALK_PATHS
        ),
    )


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
