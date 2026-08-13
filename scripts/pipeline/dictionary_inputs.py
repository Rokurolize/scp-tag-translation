"""Load policy inputs and complete generated branch dictionaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.infrastructure.data_paths import (
    CROSSWALK_PATHS,
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
    DICTIONARIES_DIR,
    OVERRIDES_PATH,
)
from scripts.domain.policy.policy_builder import MappingPolicyInputs
from scripts.domain.records.tag_records import (
    BranchOverrideFile,
    BranchOverrideRecord,
    BranchOverrideValue,
    DeprecatedTag,
    EnTag,
    OfficialCrosswalkFile,
    JpTag,
    ReplacementOverrideFile,
)
from scripts.domain.policy.tag_policy import MappingPolicy
from scripts.domain.records.tag_validation import validate_tag_records
from scripts.infrastructure.json_io import load_json
from scripts.domain.errors import InvalidDomainInputError


def _load_optional_json(path: Path) -> object:
    return load_json(path) if path.exists() else {}


def _load_json_object(path: Path, label: str) -> dict[object, object]:
    raw = _load_optional_json(path)
    if not isinstance(raw, dict):
        raise InvalidDomainInputError(f"{label} must be a JSON object: {path}")
    return raw


def _validate_override_entry(
    path: Path,
    branch: object,
    source_tag: object,
    value: object,
) -> tuple[str, BranchOverrideValue]:
    if not isinstance(source_tag, str) or not source_tag:
        raise ValueError(f"invalid override source tag in {path}: {source_tag!r}")
    if isinstance(value, str):
        return source_tag, value
    if not isinstance(branch, str) or not isinstance(value, dict):
        raise ValueError(f"invalid override value in {path}: {branch}:{source_tag}")
    if "jp_tag" not in value or not isinstance(value["jp_tag"], str):
        raise ValueError(f"invalid override value in {path}: {branch}:{source_tag}")
    jp_tag = value["jp_tag"]
    unknown_keys = set(value) - {"jp_tag", "note"}
    if unknown_keys:
        raise ValueError(
            f"invalid override fields in {path}: "
            f"{branch}:{source_tag}: {sorted(unknown_keys, key=repr)}"
        )
    note = value.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError(f"invalid override note in {path}: {branch}:{source_tag}")
    record: BranchOverrideRecord = {"jp_tag": jp_tag}
    if note is not None:
        record["note"] = note
    return source_tag, record


def _load_override_file(path: Path) -> BranchOverrideFile:
    raw = _load_json_object(path, "branch override file")
    validated: dict[str, dict[str, BranchOverrideValue]] = {}
    for branch, branch_values in raw.items():
        if not isinstance(branch, str) or not isinstance(branch_values, dict):
            raise ValueError(f"invalid override branch in {path}: {branch!r}")
        validated[branch] = dict(
            _validate_override_entry(path, branch, source_tag, value)
            for source_tag, value in branch_values.items()
        )
    return validated


def _load_replacement_overrides(path: Path) -> ReplacementOverrideFile:
    raw = _load_json_object(path, "replacement override file")
    validated: dict[str, dict[str, str]] = {}
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
            validated.setdefault(source_lang, {})[source_tag] = replacement
    return validated


def _load_crosswalk(path: Path) -> OfficialCrosswalkFile:
    raw = _load_json_object(path, "official crosswalk")
    validated: dict[str, dict[str, str]] = {}
    for branch, mappings in raw.items():
        if not isinstance(branch, str) or not isinstance(mappings, dict):
            raise ValueError(f"invalid crosswalk branch in {path}: {branch!r}")
        for source_tag, jp_tag in mappings.items():
            if not isinstance(source_tag, str) or not isinstance(jp_tag, str):
                raise ValueError(
                    f"invalid crosswalk mapping in {path}: {branch}:{source_tag}"
                )
            validated.setdefault(branch, {})[source_tag] = jp_tag
    return validated


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
    """Validated tag records and a composed runtime mapping policy."""

    en_tags: list[EnTag]
    jp_tags: list[JpTag]
    deprecated_tags: list[DeprecatedTag]
    mapping_policy: MappingPolicy

@dataclass(frozen=True)
class LoadedTagRecords:
    """Validated tag records loaded before policy composition."""

    en_tags: list[EnTag]
    jp_tags: list[JpTag]
    deprecated_tags: list[DeprecatedTag]


def load_tag_records(
    paths: MappingInputPaths | None = None,
    *,
    require_complete_inputs: bool = False,
) -> LoadedTagRecords:
    """Load and validate persisted tag records without composing policy."""
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
    return LoadedTagRecords(
        en_tags=en_tags,
        jp_tags=jp_tags,
        deprecated_tags=deprecated_tags,
    )


def load_mapping_inputs(
    paths: MappingInputPaths | None = None,
    *,
    policy_inputs: MappingPolicyInputs | None = None,
    include_origin_replacements: bool = True,
    require_complete_inputs: bool = False,
) -> LoadedMappingInputs:
    """Compatibility entry point for the application mapping composer."""
    from scripts.application.mapping_inputs import load_mapping_inputs as compose

    return compose(
        paths,
        policy_inputs=policy_inputs,
        include_origin_replacements=include_origin_replacements,
        require_complete_inputs=require_complete_inputs,
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
