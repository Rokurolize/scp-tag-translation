"""Compatibility service for the pre-corpus EN dictionary workflow."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from scripts.contracts.errors import InvalidDomainInputError
from scripts.domain.tag_dictionary import build_en_dicts
from scripts.infrastructure.data_paths import (
    EN_DICTIONARY_PATH,
)
from scripts.infrastructure.json_io import load_json
from scripts.pipeline.dictionary_inputs import LoadedMappingInputs

__all__ = [
    "LegacyDictionaryConfig",
    "build_legacy_en_dictionaries",
    "validate_existing_dict",
]


@dataclass(frozen=True)
class LegacyDictionaryConfig:
    """Output and existing-dictionary settings for the legacy workflow."""

    dictionary_path: Path = field(default_factory=lambda: EN_DICTIONARY_PATH)


def validate_existing_dict(raw: object) -> dict[str, str | None]:
    """Validate an existing dictionary object or raise InvalidDomainInputError."""
    if not isinstance(raw, dict):
        raise InvalidDomainInputError("既存辞書はオブジェクトである必要があります")
    for en_name, jp_name in raw.items():
        if not isinstance(en_name, str) or not en_name or en_name != en_name.strip():
            raise InvalidDomainInputError(f"既存辞書のキーが不正です: {en_name!r}")
        if jp_name is not None and (
            not isinstance(jp_name, str) or not jp_name or jp_name != jp_name.strip()
        ):
            raise InvalidDomainInputError(
                f"既存辞書の値が不正です: {en_name!r} -> {jp_name!r}"
            )
    return {
        en_name: jp_name
        for en_name, jp_name in raw.items()
    }


def build_legacy_en_dictionaries(
    *,
    overwrite: bool,
    config: LegacyDictionaryConfig | None = None,
    loaded_inputs: LoadedMappingInputs,
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Build legacy EN outputs, raising existing-file validation, policy, or filesystem errors."""
    config = config or LegacyDictionaryConfig()
    loaded = loaded_inputs
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
