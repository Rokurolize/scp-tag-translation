"""Shared source-to-JP mapping policy and typed policy artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Literal

from scripts.domain.tag_models import (
    DeprecatedTag,
    EnTag,
    JpTag,
    BranchOverrideFile,
    OfficialCrosswalkFile,
    ReplacementOverrideFile,
)

EN_CATEGORIES_OMITTED_ON_JP = {"Genre", "Genre and Themes"}
# A source tag can occur in more than one JP category while the JP tag system
# is being migrated.  The published dictionary has one context-free value, so
# these ambiguous aliases need an explicit canonical target.
JP_SOURCE_TAG_MAPPING_OVERRIDES = {
    "ghost": "幽霊",
    "orientation": "オリエンテーション",
}
EN_ORIGIN_TAG_REPLACEMENTS = {
    "_int": "int",
    "_ru": "ru",
    "_ko": "ko",
    "_cn": "cn",
    "_fr": "fr",
    "_pl": "pl",
    "_es": "es",
    "_th": "th",
    "_jp": "jp",
    "_de": "de",
    "_it": "it",
    "_ua": "ua",
    "_pt": "pt",
    "_zh": "zh",
    "_vn": "vn",
    "_el": "el",
    "_id": "id",
    "_hu": "hu",
    "_nd": "nd",
}
EN_CROSSWALK_SEMANTIC_REPLACEMENTS = {
    **EN_ORIGIN_TAG_REPLACEMENTS,
    "guide": "他支部公式",
}


def is_deprecated_for_en_source(entry: DeprecatedTag) -> bool:
    source_lang = entry.get("source_lang") or "EN"
    return source_lang == "EN" and bool(entry["source_tag"])


def jp_source_tags(entry: JpTag) -> list[str]:
    """Return every source-language alias recorded for a JP tag."""
    return entry["source_tags"]


def en_category_omitted_tags(
    en_tags: Sequence[EnTag],
    jp_tags: Sequence[JpTag],
    extra_mapped_tags: set[str] | None = None,
) -> set[str]:
    """Return EN genre tags omitted unless JP maps them explicitly."""
    mapped = {
        source_tag
        for entry in jp_tags
        for source_tag in jp_source_tags(entry)
    }
    mapped.update(extra_mapped_tags or set())
    return {
        entry["name"]
        for entry in en_tags
        if entry.get("category") in EN_CATEGORIES_OMITTED_ON_JP
        and entry["name"] not in mapped
    }


def branch_to_source_lang(branch: str) -> str:
    if branch == "pt-br":
        return "PT"
    if branch == "zh-tr":
        return "ZH"
    return branch.upper()


def source_languages_for_branch(branch: str) -> tuple[str, ...]:
    """Return JP unused-list sections inherited by a source branch."""

    if branch == "int":
        return ("EN", "INT")
    return (branch_to_source_lang(branch),)


@dataclass(frozen=True)
class BranchMappingPolicy:
    deprecated_tags: frozenset[str]
    replacements: Mapping[str, str | None]
    overrides: Mapping[str, str]
    official_crosswalk: Mapping[str, str]


@dataclass(frozen=True)
class MappingPolicy:
    jp_names: frozenset[str]
    jp_source_map: Mapping[str, str]
    deprecated_tags: Mapping[str, set[str]]
    replacements: Mapping[str, Mapping[str, str | None]]
    overrides: Mapping[str, Mapping[str, str]]
    official_crosswalk: Mapping[str, Mapping[str, str]]

    def for_branch(self, branch: str) -> BranchMappingPolicy:
        applicable: set[str] = set()
        effective_replacements: dict[str, str | None] = {}
        for source_lang in source_languages_for_branch(branch):
            applicable.update(self.deprecated_tags.get(source_lang, set()))
            for source_tag, replacement in self.replacements.get(
                source_lang,
                {},
            ).items():
                existing = effective_replacements.get(source_tag)
                if (
                    existing is not None
                    and replacement is not None
                    and existing != replacement
                ):
                    raise ValueError(
                        "conflicting inherited replacements: "
                        f"{branch}:{source_tag}->{existing}/{replacement}"
                    )
                if replacement is not None or source_tag not in effective_replacements:
                    effective_replacements[source_tag] = replacement

        return BranchMappingPolicy(
            deprecated_tags=frozenset(applicable),
            replacements=effective_replacements,
            overrides={
                **self.overrides.get("*", {}),
                **self.overrides.get(branch, {}),
            },
            official_crosswalk=self.official_crosswalk.get(branch, {}),
        )


MappingOrigin = Literal[
    "jp_unused",
    "jp_tag_name",
    "curated_override",
    "official_crosswalk",
    "jp_tag_alias",
    "unhandled",
]


@dataclass(frozen=True)
class SourceTagResolution:
    origin: MappingOrigin
    target: str | None = None
    replacement: str | None = None


def resolve_source_tag(
    source_tag: str,
    mapping_policy: MappingPolicy,
    branch_policy: BranchMappingPolicy,
    *,
    deprecated_tags: Set[str] | None = None,
) -> SourceTagResolution:
    """Resolve one source tag with the shared mapping precedence."""

    effective_deprecated = (
        branch_policy.deprecated_tags
        if deprecated_tags is None
        else deprecated_tags
    )
    if source_tag in effective_deprecated:
        return SourceTagResolution(
            "jp_unused",
            replacement=branch_policy.replacements.get(source_tag),
        )
    if source_tag in branch_policy.overrides:
        return SourceTagResolution(
            "curated_override",
            target=branch_policy.overrides[source_tag],
        )
    if source_tag in branch_policy.official_crosswalk:
        return SourceTagResolution(
            "official_crosswalk",
            target=branch_policy.official_crosswalk[source_tag],
        )
    if source_tag in mapping_policy.jp_source_map:
        mapped_target = mapping_policy.jp_source_map[source_tag]
        if source_tag not in mapping_policy.jp_names or mapped_target != source_tag:
            return SourceTagResolution(
                "jp_tag_alias",
                target=mapped_target,
            )
    if source_tag in mapping_policy.jp_names:
        return SourceTagResolution(
            "jp_tag_name",
            target=source_tag,
        )
    return SourceTagResolution("unhandled")


@dataclass(frozen=True)
class MappingPolicyInputs:
    overrides: BranchOverrideFile
    replacement_overrides: ReplacementOverrideFile
    official_crosswalks: tuple[OfficialCrosswalkFile, ...]


def jp_maps(
    jp_tags: list[JpTag],
    source_tag_overrides: Mapping[str, str] | None = None,
) -> tuple[frozenset[str], dict[str, str]]:
    jp_names: set[str] = set()
    source_candidates: dict[str, set[str]] = {}
    for entry in jp_tags:
        name = entry["name"]
        jp_names.add(name)
        for source_tag in jp_source_tags(entry):
            source_candidates.setdefault(source_tag, set()).add(name)

    overrides = {
        **JP_SOURCE_TAG_MAPPING_OVERRIDES,
        **(source_tag_overrides or {}),
    }
    source_to_jp: dict[str, str] = {}
    for source_tag, candidates in source_candidates.items():
        override = overrides.get(source_tag)
        if override is not None:
            if override not in candidates:
                raise ValueError(
                    "source tag mapping override is not a candidate: "
                    f"{source_tag!r}->{override!r}"
                )
            source_to_jp[source_tag] = override
            continue

        if len(candidates) == 1:
            source_to_jp[source_tag] = next(iter(candidates))
            continue

        translated_candidates = candidates - {source_tag}
        if len(translated_candidates) == 1:
            source_to_jp[source_tag] = next(iter(translated_candidates))
            continue

        formatted = ", ".join(sorted(candidates))
        raise ValueError(
            "source tag maps to multiple JP tags without an explicit policy: "
            f"{source_tag!r} -> {formatted}"
        )
    return frozenset(jp_names), source_to_jp


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


def deprecated_by_source_lang(
    deprecated_raw: list[DeprecatedTag],
    jp_names: frozenset[str] | set[str],
    replacement_overrides: Mapping[str, Mapping[str, str]] | None = None,
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

    for source_tag, replacement in EN_ORIGIN_TAG_REPLACEMENTS.items():
        if replacement not in jp_names:
            raise ValueError(
                f"EN origin replacement is not a JP tag: {source_tag}->{replacement}"
            )
        deprecated_tags.setdefault("EN", set()).add(source_tag)
        replacements.setdefault("EN", {})[source_tag] = replacement

    for source_lang, mappings in (replacement_overrides or {}).items():
        for source_tag, replacement in mappings.items():
            if replacement not in jp_names:
                raise ValueError(
                    "deprecated override target is not a JP tag: "
                    f"{source_lang}:{source_tag}->{replacement}"
                )
            deprecated_tags.setdefault(source_lang, set()).add(source_tag)
            replacements.setdefault(source_lang, {})[source_tag] = replacement
    return deprecated_tags, replacements


def build_mapping_policy(
    jp_tags: list[JpTag],
    deprecated_raw: list[DeprecatedTag],
    inputs: MappingPolicyInputs,
) -> MappingPolicy:
    jp_names, jp_source_map = jp_maps(jp_tags)
    overrides = parse_overrides(inputs.overrides, jp_names)
    replacement_overrides = parse_overrides(
        inputs.replacement_overrides,
        jp_names,
    )
    official_crosswalk = merge_official_crosswalks(
        inputs.official_crosswalks,
        jp_names,
    )
    deprecated_tags, replacements = deprecated_by_source_lang(
        deprecated_raw,
        jp_names,
        replacement_overrides,
    )
    return MappingPolicy(
        jp_names=jp_names,
        jp_source_map=jp_source_map,
        deprecated_tags=deprecated_tags,
        replacements=replacements,
        overrides=overrides,
        official_crosswalk=official_crosswalk,
    )
