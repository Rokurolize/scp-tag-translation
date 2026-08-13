"""Validate generated branch-coverage artifacts at the publication boundary."""

from __future__ import annotations

from typing import cast

from scripts.domain.tag_coverage_models import Coverage
from scripts.domain.policy.tag_policy_models import (
    CLASSIFICATION_STATUSES,
    COVERAGE_TRANSLATION_ACTIONS,
    SPECIAL_TRANSLATION_ACTIONS,
)


def _validate_description_map(
    value: object,
    expected_keys: frozenset[str],
    context: str,
) -> None:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError(f"{context} must map strings to strings")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        raise ValueError(f"{context} keys do not match the protocol")


def _valid_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_keys(
    value: dict[object, object],
    required: tuple[str, ...],
    context: str,
) -> None:
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(f"{context} missing required keys: {', '.join(missing)}")


def _validate_required_string_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not isinstance(value.get(key), str):
            raise ValueError(f"{context}.{key} must be a string")


def _validate_required_boolean_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{context}.{key} must be boolean")


def _validate_nullable_string_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            raise ValueError(f"{context}.{key} must be a string or null")


def _validate_nonnegative_integer_fields(
    value: dict[object, object],
    keys: tuple[str, ...],
    context: str,
) -> None:
    for key in keys:
        if not _valid_nonnegative_int(value.get(key)):
            raise ValueError(f"{context}.{key} must be a non-negative integer")


def _validate_jp_policy(value: object, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{context}.target_policy must be an object or null")
    _require_keys(value, ("special_translation_action",), f"{context}.target_policy")
    _validate_required_boolean_fields(
        value,
        (
            "use_restricted",
            "edit_restricted",
            "translation_exempt",
            "copy_allowed_for_translation",
        ),
        f"{context}.target_policy",
    )
    action = value.get("special_translation_action")
    if action is not None and action not in SPECIAL_TRANSLATION_ACTIONS:
        raise ValueError(
            f"{context}.target_policy.special_translation_action is invalid"
        )


def _validate_coverage_tag(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    _require_keys(
        value,
        ("jp_tag", "replacement", "display_tag", "target_policy"),
        context,
    )
    if not isinstance(value.get("tag"), str):
        raise ValueError(f"{context}.tag must be a string")
    if value.get("status") not in CLASSIFICATION_STATUSES:
        raise ValueError(f"{context}.status is unknown")
    if value.get("translation_action") not in COVERAGE_TRANSLATION_ACTIONS:
        raise ValueError(f"{context}.translation_action is unknown")
    _validate_required_boolean_fields(
        value,
        ("recognized_by_jp_policy", "copy_allowed"),
        context,
    )
    _validate_nullable_string_fields(
        value,
        ("jp_tag", "replacement", "display_tag"),
        context,
    )
    _validate_nonnegative_integer_fields(
        value,
        ("rank", "page_count"),
        context,
    )
    sample_slugs = value.get("sample_slugs")
    if not isinstance(sample_slugs, list) or any(
        not isinstance(slug, str) for slug in sample_slugs
    ):
        raise ValueError(f"{context}.sample_slugs must be a string array")
    _validate_jp_policy(value.get("target_policy"), context)


def _validate_coverage_source(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("coverage.source must be an object")
    _validate_required_string_fields(
        value,
        (
            "corpus_root",
            "jp_tag_source",
            "jp_unused_source",
            "override_source",
            "deprecated_override_source",
            "crosswalk_source",
        ),
        "coverage.source",
    )


def _validate_status_counts(value: object, context: str) -> None:
    if not isinstance(value, dict) or any(
        key not in CLASSIFICATION_STATUSES or not _valid_nonnegative_int(count)
        for key, count in value.items()
    ):
        raise ValueError(f"{context}.status_counts is invalid")


def _validate_coverage_branch(value: object, context: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    _validate_required_string_fields(value, ("branch", "site"), context)
    _validate_nonnegative_integer_fields(
        value,
        ("page_count", "tag_count"),
        context,
    )
    _validate_status_counts(value.get("status_counts"), context)
    tags = value.get("tags")
    if not isinstance(tags, list):
        raise ValueError(f"{context}.tags must be an array")
    for tag_index, tag in enumerate(tags):
        _validate_coverage_tag(tag, f"{context}.tags[{tag_index}]")
    if value.get("tag_count") != len(tags):
        raise ValueError(f"{context}.tag_count does not match tags")


def validate_coverage(raw: object) -> Coverage:
    """Validate one generated coverage document before HTML publication."""
    if not isinstance(raw, dict):
        raise ValueError("coverage root must be an object")
    if not _valid_nonnegative_int(raw.get("schema_version")):
        raise ValueError("coverage.schema_version must be a non-negative integer")
    _validate_coverage_source(raw.get("source"))
    _validate_description_map(
        raw.get("status_descriptions"),
        CLASSIFICATION_STATUSES,
        "coverage.status_descriptions",
    )
    _validate_description_map(
        raw.get("action_descriptions"),
        COVERAGE_TRANSLATION_ACTIONS,
        "coverage.action_descriptions",
    )
    branches = raw.get("branches")
    if not isinstance(branches, list):
        raise ValueError("coverage.branches must be an array")
    for branch_index, branch in enumerate(branches):
        _validate_coverage_branch(branch, f"coverage.branches[{branch_index}]")
    return cast(Coverage, raw)


__all__ = ["validate_coverage"]
