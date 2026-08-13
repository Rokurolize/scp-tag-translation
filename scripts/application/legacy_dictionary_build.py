"""Build and publish dictionaries for the legacy compatibility CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import (
    DATA_DEPRECATED,
    DATA_EN,
    DATA_JP,
    DEPRECATED_EN_DICTIONARY_PATH,
    EN_DICTIONARY_PATH,
)
from scripts.infrastructure.json_io import write_json
from scripts.pipeline.dictionary_inputs import load_mapping_policy_inputs
from scripts.pipeline.legacy_dictionary import (
    LegacyDictionaryConfig,
    build_legacy_en_dictionary,
    build_legacy_outputs,
)
from scripts.domain.policy.policy_builder import MappingPolicyInputs


@dataclass(frozen=True)
class LegacyDictionaryBuildConfig:
    """Repository paths and policy inputs for one compatibility build."""

    data_en: Path = DATA_EN
    data_jp: Path = DATA_JP
    data_deprecated: Path = DATA_DEPRECATED
    dictionary_path: Path = EN_DICTIONARY_PATH
    deprecated_dictionary_path: Path = DEPRECATED_EN_DICTIONARY_PATH
    policy_inputs: MappingPolicyInputs | None = None


@dataclass(frozen=True)
class LegacyDictionaryBuildResult:
    dictionary: dict[str, str | None]
    deprecated_dictionary: dict[str, str]
    dictionary_path: Path
    deprecated_dictionary_path: Path


def default_legacy_dictionary_build_config() -> LegacyDictionaryBuildConfig:
    """Return the current repository defaults for the compatibility workflow."""
    return LegacyDictionaryBuildConfig(
        data_en=DATA_EN,
        data_jp=DATA_JP,
        data_deprecated=DATA_DEPRECATED,
        dictionary_path=EN_DICTIONARY_PATH,
        deprecated_dictionary_path=DEPRECATED_EN_DICTIONARY_PATH,
        policy_inputs=load_mapping_policy_inputs(),
    )


def build_and_publish_legacy_dictionary(
    overwrite: bool,
    *,
    config: LegacyDictionaryBuildConfig | None = None,
) -> LegacyDictionaryBuildResult:
    """Build legacy outputs and publish both files atomically."""
    config = config or default_legacy_dictionary_build_config()
    dictionary, deprecated_dictionary = build_legacy_outputs(
        overwrite,
        config=LegacyDictionaryConfig(
            data_en=config.data_en,
            data_jp=config.data_jp,
            data_deprecated=config.data_deprecated,
            dictionary_path=config.dictionary_path,
        ),
        policy_inputs=config.policy_inputs,
    )
    publish_files_atomically({
        config.dictionary_path: (
            lambda temporary: write_json(temporary, dictionary)
        ),
        config.deprecated_dictionary_path: (
            lambda temporary: write_json(temporary, deprecated_dictionary)
        ),
    })
    return LegacyDictionaryBuildResult(
        dictionary=dictionary,
        deprecated_dictionary=deprecated_dictionary,
        dictionary_path=config.dictionary_path,
        deprecated_dictionary_path=config.deprecated_dictionary_path,
    )


__all__ = [
    "LegacyDictionaryBuildConfig",
    "LegacyDictionaryBuildResult",
    "build_and_publish_legacy_dictionary",
    "build_legacy_en_dictionary",
    "default_legacy_dictionary_build_config",
]
