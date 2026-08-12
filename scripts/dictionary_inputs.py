"""Load policy inputs and complete generated branch dictionaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.data_paths import (
    CROSSWALK_PATHS,
    DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
    DICTIONARIES_DIR,
    OVERRIDES_PATH,
)
from scripts.domain.tag_policy import MappingPolicyInputs
from scripts.json_io import load_json


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
