"""Compatibility service for the pre-corpus EN dictionary workflow."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path

from scripts.domain.policy.policy_builder import MappingPolicyInputs, build_mapping_policy
from scripts.domain.records.tag_records import EnTag, JpTag
from scripts.domain.records.tag_validation import validate_tag_records
from scripts.domain.tag_dictionary import build_en_dicts
from scripts.infrastructure.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    EN_DICTIONARY_PATH,
)
from scripts.infrastructure.json_io import load_json
from scripts.pipeline.dictionary_inputs import (
    default_mapping_input_paths,
    load_mapping_inputs,
)

__all__ = [
    "LegacyDictionaryConfig",
    "build_legacy_en_dictionary",
    "build_legacy_outputs",
    "validate_existing_dict",
]


@dataclass(frozen=True)
class LegacyDictionaryConfig:
    """Locations used by the legacy EN dictionary compatibility workflow."""

    data_en: Path = DATA_EN
    data_jp: Path = DATA_JP
    data_deprecated: Path = DATA_DEPRECATED
    dictionary_path: Path = EN_DICTIONARY_PATH


def _ensure_no_case_variant_keys(
    existing_keys: Iterable[str],
    source_keys: Iterable[str],
    label: str,
) -> None:
    lower_to_source = {key.lower(): key for key in source_keys}
    collisions = []
    for key in existing_keys:
        source_key = lower_to_source.get(key.lower())
        if source_key is not None and key != source_key:
            collisions.append(f"{key} -> {source_key}")

    if collisions:
        sample = ", ".join(sorted(collisions)[:10])
        raise ValueError(f"{label} に大小文字違いの重複があります: {sample}")


def validate_existing_dict(raw: object) -> dict[str, str | None]:
    if not isinstance(raw, dict):
        raise ValueError("既存辞書はオブジェクトである必要があります")
    for en_name, jp_name in raw.items():
        if not isinstance(en_name, str) or not en_name or en_name != en_name.strip():
            raise ValueError(f"既存辞書のキーが不正です: {en_name!r}")
        if jp_name is not None and (
            not isinstance(jp_name, str) or not jp_name or jp_name != jp_name.strip()
        ):
            raise ValueError(f"既存辞書の値が不正です: {en_name!r} -> {jp_name!r}")
    return {
        en_name: jp_name
        for en_name, jp_name in raw.items()
    }


def build_legacy_en_dictionary(
    en_tags: list[EnTag],
    jp_tags: list[JpTag],
    existing: dict[str, str | None] | None = None,
    deprecated_en_tags: set[str] | None = None,
) -> dict[str, str | None]:
    """Build one EN dictionary for callers of the legacy compatibility API."""
    existing = existing or {}
    deprecated_en_tags = deprecated_en_tags or set()
    deprecated_raw = [
        {"source_lang": "EN", "source_tag": source_tag}
        for source_tag in deprecated_en_tags
    ]
    en_tags, jp_tags, deprecated_raw = validate_tag_records(
        en_tags,
        jp_tags,
        deprecated_raw,
    )
    validate_existing_dict(existing)
    _ensure_no_case_variant_keys(
        existing.keys(),
        (entry["name"] for entry in en_tags),
        "既存辞書キー",
    )
    policy = build_mapping_policy(
        jp_tags,
        deprecated_raw,
        MappingPolicyInputs(
            overrides={},
            replacement_overrides={},
            official_crosswalks=(),
            compatibility_overrides={
                "en": {
                    source_tag: target
                    for source_tag, target in existing.items()
                    if target is not None
                }
            },
        ),
        include_origin_replacements=False,
    )
    dictionary, _replacements = build_en_dicts(
        en_tags,
        jp_tags,
        deprecated_raw,
        set(existing),
        policy,
    )
    return dictionary


def build_legacy_outputs(
    *,
    overwrite: bool,
    config: LegacyDictionaryConfig = LegacyDictionaryConfig(),
    policy_inputs: MappingPolicyInputs,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Build legacy EN outputs while keeping loading and policy assembly centralized."""
    for path in (config.data_en, config.data_jp):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} が見つかりません。先に parse_sources.py を実行してください。"
            )

    mapping_paths = replace(
        default_mapping_input_paths(),
        data_en=config.data_en,
        data_jp=config.data_jp,
        data_deprecated=config.data_deprecated,
    )
    loaded = load_mapping_inputs(
        mapping_paths,
        policy_inputs=policy_inputs,
        include_origin_replacements=False,
    )
    existing: dict[str, str | None] = {}
    if not overwrite and config.dictionary_path.exists():
        existing = validate_existing_dict(load_json(config.dictionary_path))

    policy = loaded.mapping_policy
    if existing:
        policy = replace(
            policy,
            overrides={
                **policy.overrides,
                "en": {
                    **policy.overrides.get("en", {}),
                    **{
                        source_tag: target
                        for source_tag, target in existing.items()
                        if target is not None
                    },
                },
            },
        )

    sorted_dict, deprecated_dict = build_en_dicts(
        loaded.en_tags,
        loaded.jp_tags,
        loaded.deprecated_tags,
        set(existing),
        policy,
    )
    return sorted_dict, dict(sorted(deprecated_dict.items()))
