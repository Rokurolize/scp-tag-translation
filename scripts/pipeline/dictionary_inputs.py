"""Load policy inputs and complete generated branch dictionaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from scripts.infrastructure.data_paths import (
    CROSSWALK_PATHS,
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
    DICTIONARIES_DIR,
    OVERRIDES_PATH,
)
from scripts.domain.policy_builder import MappingPolicyInputs, build_mapping_policy
from scripts.domain.tag_records import (
    BranchOverrideFile,
    DeprecatedTag,
    EnTag,
    OfficialCrosswalkFile,
    JpTag,
    ReplacementOverrideFile,
)
from scripts.domain.tag_policy import MappingPolicy
from scripts.domain.tag_validation import validate_tag_records
from scripts.infrastructure.json_io import load_json


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


@dataclass(frozen=True)
class MappingInputPaths:
    """All source artifacts needed to assemble one mapping policy."""

    data_en: Path
    data_jp: Path
    data_deprecated: Path
    overrides: Path
    replacement_overrides: Path
    crosswalks: tuple[Path, ...]


def default_mapping_input_paths() -> MappingInputPaths:
    """Return the repository's default mapping input locations."""
    return MappingInputPaths(
        data_en=DATA_EN,
        data_jp=DATA_JP,
        data_deprecated=DATA_DEPRECATED,
        overrides=OVERRIDES_PATH,
        replacement_overrides=DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
        crosswalks=CROSSWALK_PATHS,
    )


def load_mapping_policy_inputs(
    paths: MappingInputPaths | None = None,
) -> MappingPolicyInputs:
    paths = paths or default_mapping_input_paths()
    return MappingPolicyInputs(
        overrides=_load_override_file(paths.overrides),
        replacement_overrides=_load_replacement_overrides(
            paths.replacement_overrides,
        ),
        official_crosswalks=tuple(
            _load_crosswalk(path) for path in paths.crosswalks
        ),
    )


@dataclass(frozen=True)
class LoadedMappingInputs:
    """Validated tag records and their assembled mapping policy."""

    en_tags: list[EnTag]
    jp_tags: list[JpTag]
    deprecated_tags: list[DeprecatedTag]
    mapping_policy: MappingPolicy


def load_mapping_inputs(
    paths: MappingInputPaths | None = None,
    *,
    policy_inputs: MappingPolicyInputs | None = None,
    include_origin_replacements: bool = True,
    require_complete_inputs: bool = False,
) -> LoadedMappingInputs:
    """Load and validate tag records, then assemble one mapping policy."""
    paths = paths or default_mapping_input_paths()
    required_paths = [paths.data_en, paths.data_jp]
    if require_complete_inputs:
        required_paths.extend(
            [
                paths.data_deprecated,
                paths.overrides,
                paths.replacement_overrides,
                *paths.crosswalks,
            ]
        )
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Required mapping inputs missing: {missing}")
    en_tags, jp_tags, deprecated_tags = validate_tag_records(
        load_json(paths.data_en),
        load_json(paths.data_jp),
        (load_json(paths.data_deprecated) if paths.data_deprecated.exists() else []),
    )
    return LoadedMappingInputs(
        en_tags=en_tags,
        jp_tags=jp_tags,
        deprecated_tags=deprecated_tags,
        mapping_policy=build_mapping_policy(
            jp_tags,
            deprecated_tags,
            policy_inputs or load_mapping_policy_inputs(paths),
            include_origin_replacements=include_origin_replacements,
        ),
    )


def load_existing_hint_dictionaries(
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
