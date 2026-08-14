"""Build and publish dictionaries for the legacy compatibility CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import (
    DEPRECATED_EN_DICTIONARY_PATH,
    EN_DICTIONARY_PATH,
)
from scripts.infrastructure.json_io import write_json
from scripts.pipeline.dictionary_inputs import (
    MappingInputPaths,
    default_mapping_input_paths,
)
from scripts.application.mapping_inputs import (
    load_mapping_inputs,
)
from scripts.compatibility.legacy_dictionary import (
    LegacyDictionaryConfig,
    build_legacy_outputs,
)


@dataclass(frozen=True)
class LegacyDictionaryBuildConfig:
    """Repository paths and policy inputs for one compatibility build."""

    mapping_inputs: MappingInputPaths = field(
        default_factory=lambda: default_mapping_input_paths(),
    )
    dictionary_path: Path = field(default_factory=lambda: EN_DICTIONARY_PATH)
    deprecated_dictionary_path: Path = field(
        default_factory=lambda: DEPRECATED_EN_DICTIONARY_PATH,
    )


@dataclass(frozen=True)
class LegacyDictionaryBuildResult:
    dictionary: dict[str, str | None]
    deprecated_dictionary: dict[str, str]
    dictionary_path: Path
    deprecated_dictionary_path: Path


def build_and_publish_legacy_dictionary(
    *,
    overwrite: bool,
    config: LegacyDictionaryBuildConfig | None = None,
) -> LegacyDictionaryBuildResult:
    """Build and publish legacy outputs, raising input, filesystem, or publication errors on failure."""
    config = config or LegacyDictionaryBuildConfig()
    loaded_inputs = load_mapping_inputs(
        config.mapping_inputs,
        include_origin_replacements=False,
    )
    dictionary, deprecated_dictionary = build_legacy_outputs(
        overwrite=overwrite,
        config=LegacyDictionaryConfig(dictionary_path=config.dictionary_path),
        loaded_inputs=loaded_inputs,
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
]
