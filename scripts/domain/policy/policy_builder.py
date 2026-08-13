"""Parse repository policy inputs and assemble a mapping policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from scripts.domain.records.tag_records import (
    BranchOverrideFile,
    DeprecatedTag,
    JpTag,
    OfficialCrosswalkFile,
    ReplacementOverrideFile,
)
from scripts.domain.policy.tag_policy import (
    EN_ORIGIN_TAG_REPLACEMENTS,
    MappingPolicy,
    build_jp_names_and_source_map,
)


@dataclass(frozen=True)
class MappingPolicyInputs:
    """Validated JSON policy documents used to assemble one mapping policy."""

    overrides: BranchOverrideFile
    replacement_overrides: ReplacementOverrideFile
    official_crosswalks: tuple[OfficialCrosswalkFile, ...]
    compatibility_overrides: Mapping[str, Mapping[str, str]] = field(
        default_factory=dict,
    )


def _validated_override_target(
    branch: str,
    source_tag: str,
    value: object,
    jp_names: frozenset[str] | set[str],
) -> str:
    if isinstance(value, str):
        jp_tag = value
    elif isinstance(value, dict) and isinstance(value.get("jp_tag"), str):
        jp_tag = value["jp_tag"]
    else:
        raise ValueError(f"invalid override value for {branch}:{source_tag}")
    if jp_tag not in jp_names:
        raise ValueError(
            "override target is not a JP tag: "
            f"{branch}:{source_tag}->{jp_tag}"
        )
    return jp_tag


def parse_overrides(
    raw: object,
    jp_names: frozenset[str] | set[str],
) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        raise ValueError("branch override file must be a JSON object")

    overrides: dict[str, dict[str, str]] = {}
    for branch, branch_values in raw.items():
        if not isinstance(branch, str) or not branch:
            raise ValueError(f"invalid override branch: {branch!r}")
        if not isinstance(branch_values, dict):
            raise ValueError(f"override branch must map tags: {branch!r}")
        overrides[branch] = {}
        for source_tag, value in branch_values.items():
            if not isinstance(source_tag, str) or not source_tag:
                raise ValueError(f"invalid override source tag for {branch!r}")
            overrides[branch][source_tag] = _validated_override_target(
                branch,
                source_tag,
                value,
                jp_names,
            )
    return overrides


def parse_official_crosswalk(
    raw: object,
    jp_names: frozenset[str] | set[str],
) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        raise ValueError("official crosswalk must be a JSON object")
    result: dict[str, dict[str, str]] = {}
    for branch, mappings in raw.items():
        if not isinstance(branch, str) or not isinstance(mappings, dict):
            raise ValueError(f"invalid official crosswalk branch: {branch!r}")
        result[branch] = {}
        for source_tag, jp_tag in mappings.items():
            if not isinstance(source_tag, str) or not source_tag:
                raise ValueError(
                    f"invalid crosswalk source tag: {branch}:{source_tag!r}"
                )
            if not isinstance(jp_tag, str):
                raise ValueError(
                    f"invalid crosswalk target: {branch}:{source_tag}->{jp_tag!r}"
                )
            if jp_tag in jp_names:
                result[branch][source_tag] = jp_tag
    return result


def _validate_loaded_overrides(
    inputs: BranchOverrideFile,
    jp_names: frozenset[str] | set[str],
) -> dict[str, dict[str, str]]:
    """Normalize already-decoded branch overrides at the policy boundary."""
    return {
        branch: {
            source_tag: _validated_override_target(
                branch,
                source_tag,
                value,
                jp_names,
            )
            for source_tag, value in branch_values.items()
        }
        for branch, branch_values in inputs.items()
    }


def _merge_loaded_crosswalks(
    inputs: Sequence[OfficialCrosswalkFile],
    jp_names: frozenset[str] | set[str],
) -> dict[str, dict[str, str]]:
    """Merge validated crosswalk maps while retaining only current JP tags."""
    merged: dict[str, dict[str, str]] = {}
    for current in inputs:
        for branch, mappings in current.items():
            for source_tag, jp_tag in mappings.items():
                if jp_tag in jp_names:
                    merged.setdefault(branch, {})[source_tag] = jp_tag
    return merged


def merge_official_crosswalks(
    raw_crosswalks: Sequence[object],
    jp_names: frozenset[str] | set[str],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for raw in raw_crosswalks:
        current = parse_official_crosswalk(raw, jp_names)
        for branch, mappings in current.items():
            merged.setdefault(branch, {}).update(mappings)
    return merged


def _add_origin_replacements(
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str | None]],
    jp_names: frozenset[str] | set[str],
) -> None:
    for source_tag, replacement in EN_ORIGIN_TAG_REPLACEMENTS.items():
        if replacement not in jp_names:
            raise ValueError(
                f"EN origin replacement is not a JP tag: {source_tag}->{replacement}"
            )
        deprecated_tags.setdefault("EN", set()).add(source_tag)
        replacements.setdefault("EN", {})[source_tag] = replacement


def _add_replacement_overrides(
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str | None]],
    replacement_overrides: Mapping[str, Mapping[str, str]],
    jp_names: frozenset[str] | set[str],
) -> None:
    for source_lang, mappings in replacement_overrides.items():
        for source_tag, replacement in mappings.items():
            if replacement not in jp_names:
                raise ValueError(
                    "deprecated override target is not a JP tag: "
                    f"{source_lang}:{source_tag}->{replacement}"
                )
            deprecated_tags.setdefault(source_lang, set()).add(source_tag)
            replacements.setdefault(source_lang, {})[source_tag] = replacement


def deprecated_by_source_lang(
    deprecated_raw: list[DeprecatedTag],
    jp_names: frozenset[str] | set[str],
    replacement_overrides: Mapping[str, Mapping[str, str]] | None = None,
    *,
    include_origin_replacements: bool = True,
) -> tuple[dict[str, set[str]], dict[str, dict[str, str | None]]]:
    deprecated_tags: dict[str, set[str]] = {}
    replacements: dict[str, dict[str, str | None]] = {}
    seen: set[tuple[str, str]] = set()
    for entry in deprecated_raw:
        source_lang = entry.get("source_lang") or "EN"
        source_tag = entry["source_tag"]
        key = (source_lang, source_tag)
        if key in seen:
            raise ValueError(f"duplicate deprecated entry: {source_lang}:{source_tag}")
        seen.add(key)
        deprecated_tags.setdefault(source_lang, set()).add(source_tag)
        replacement = entry.get("replacement")
        if replacement is not None and replacement not in jp_names:
            raise ValueError(
                "deprecated replacement is not a JP tag: "
                f"{source_lang}:{source_tag}->{replacement}"
            )
        replacements.setdefault(source_lang, {})[source_tag] = replacement

    if include_origin_replacements:
        _add_origin_replacements(deprecated_tags, replacements, jp_names)
    _add_replacement_overrides(
        deprecated_tags,
        replacements,
        replacement_overrides or {},
        jp_names,
    )
    return deprecated_tags, replacements


def build_mapping_policy(
    jp_tags: list[JpTag],
    deprecated_raw: list[DeprecatedTag],
    inputs: MappingPolicyInputs,
    *,
    include_origin_replacements: bool = True,
) -> MappingPolicy:
    """Assemble parsed source policies into the runtime mapping contract."""
    jp_names, jp_source_map = build_jp_names_and_source_map(jp_tags)
    overrides = _validate_loaded_overrides(inputs.overrides, jp_names)
    official_crosswalk = _merge_loaded_crosswalks(
        inputs.official_crosswalks,
        jp_names,
    )
    for branch, mappings in inputs.compatibility_overrides.items():
        overrides.setdefault(branch, {}).update(mappings)
    deprecated_tags, replacements = deprecated_by_source_lang(
        deprecated_raw,
        jp_names,
        inputs.replacement_overrides,
        include_origin_replacements=include_origin_replacements,
    )
    return MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags=deprecated_tags,
        replacements=replacements,
        overrides=overrides,
        official_crosswalk=official_crosswalk,
    )
