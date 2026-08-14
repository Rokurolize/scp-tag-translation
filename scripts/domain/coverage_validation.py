"""Validate generated branch-coverage artifacts at the publication boundary."""

from __future__ import annotations

from typing import TypeGuard

from scripts.contracts.errors import InvalidDomainInputError
from scripts.domain.policy.tag_policy_models import (
    CLASSIFICATION_STATUSES,
    COVERAGE_TRANSLATION_ACTIONS,
    SPECIAL_TRANSLATION_ACTIONS,
    ClassificationStatus,
    CoverageTranslationAction,
    JpTagPolicy,
    SpecialTranslationAction,
)
from scripts.domain.tag_coverage_models import (
    Coverage,
    CoverageBranch,
    CoverageSource,
    CoverageTag,
)


def _is_classification_status(value: object) -> TypeGuard[ClassificationStatus]:
    return isinstance(value, str) and value in CLASSIFICATION_STATUSES


def _is_coverage_translation_action(
    value: object,
) -> TypeGuard[CoverageTranslationAction]:
    return isinstance(value, str) and value in COVERAGE_TRANSLATION_ACTIONS


def _is_special_translation_action(
    value: object,
) -> TypeGuard[SpecialTranslationAction]:
    return isinstance(value, str) and value in SPECIAL_TRANSLATION_ACTIONS


def _validate_description_map(
    value: object,
    expected_keys: frozenset[str],
    context: str,
) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise InvalidDomainInputError(f"{context} must map strings to strings")
    actual_keys = set(value)
    if actual_keys != expected_keys:
        raise InvalidDomainInputError(f"{context} keys do not match the protocol")
    return dict(value)


def _is_nonnegative_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _require_keys(
    value: dict[object, object],
    required: tuple[str, ...],
    context: str,
) -> None:
    missing = [key for key in required if key not in value]
    if missing:
        raise InvalidDomainInputError(f"{context} missing required keys: {', '.join(missing)}")


def _string_field(value: dict[object, object], key: str, context: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise InvalidDomainInputError(f"{context}.{key} must be a string")
    return item


def _required_bool(
    value: dict[object, object],
    key: str,
    context: str,
) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise InvalidDomainInputError(f"{context}.{key} must be boolean")
    return item


def _nullable_string(
    value: dict[object, object],
    key: str,
    context: str,
) -> str | None:
    item = value.get(key)
    if item is not None and not isinstance(item, str):
        raise InvalidDomainInputError(f"{context}.{key} must be a string or null")
    return item


def _nonnegative_integer(
    value: dict[object, object],
    key: str,
    context: str,
) -> int:
    item = value.get(key)
    if not _is_nonnegative_int(item):
        raise InvalidDomainInputError(f"{context}.{key} must be a non-negative integer")
    return item


def _validate_jp_policy(value: object, context: str) -> JpTagPolicy | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InvalidDomainInputError(f"{context}.target_policy must be an object or null")
    policy_context = f"{context}.target_policy"
    _require_keys(value, ("special_translation_action",), policy_context)
    action = value.get("special_translation_action")
    if action is not None and not _is_special_translation_action(action):
        raise InvalidDomainInputError(
            f"{context}.target_policy.special_translation_action is invalid"
        )
    return {
        "use_restricted": _required_bool(value, "use_restricted", policy_context),
        "edit_restricted": _required_bool(value, "edit_restricted", policy_context),
        "translation_exempt": _required_bool(
            value,
            "translation_exempt",
            policy_context,
        ),
        "special_translation_action": action,
        "copy_allowed_for_translation": _required_bool(
            value,
            "copy_allowed_for_translation",
            policy_context,
        ),
    }


def _validate_coverage_tag(value: object, context: str) -> CoverageTag:
    if not isinstance(value, dict):
        raise InvalidDomainInputError(f"{context} must be an object")
    _require_keys(
        value,
        ("jp_tag", "replacement", "display_tag", "target_policy"),
        context,
    )
    tag = _string_field(value, "tag", context)
    status = value.get("status")
    if not _is_classification_status(status):
        raise InvalidDomainInputError(f"{context}.status is unknown")
    translation_action = value.get("translation_action")
    if not _is_coverage_translation_action(translation_action):
        raise InvalidDomainInputError(f"{context}.translation_action is unknown")
    sample_slugs = value.get("sample_slugs")
    if not isinstance(sample_slugs, list) or any(
        not isinstance(slug, str) for slug in sample_slugs
    ):
        raise InvalidDomainInputError(f"{context}.sample_slugs must be a string array")
    return {
        "tag": tag,
        "rank": _nonnegative_integer(value, "rank", context),
        "page_count": _nonnegative_integer(value, "page_count", context),
        "status": status,
        "recognized_by_jp_policy": _required_bool(
            value,
            "recognized_by_jp_policy",
            context,
        ),
        "jp_tag": _nullable_string(value, "jp_tag", context),
        "replacement": _nullable_string(value, "replacement", context),
        "translation_action": translation_action,
        "copy_allowed": _required_bool(value, "copy_allowed", context),
        "display_tag": _nullable_string(value, "display_tag", context),
        "target_policy": _validate_jp_policy(value.get("target_policy"), context),
        "sample_slugs": list(sample_slugs),
    }


def _validate_coverage_source(value: object) -> CoverageSource:
    if not isinstance(value, dict):
        raise InvalidDomainInputError("coverage.source must be an object")
    return {
        "corpus_root": _string_field(value, "corpus_root", "coverage.source"),
        "jp_tag_source": _string_field(value, "jp_tag_source", "coverage.source"),
        "jp_unused_source": _string_field(
            value,
            "jp_unused_source",
            "coverage.source",
        ),
        "override_source": _string_field(
            value,
            "override_source",
            "coverage.source",
        ),
        "deprecated_override_source": _string_field(
            value,
            "deprecated_override_source",
            "coverage.source",
        ),
        "crosswalk_source": _string_field(
            value,
            "crosswalk_source",
            "coverage.source",
        ),
    }


def _validate_status_counts(
    value: object,
    context: str,
) -> dict[ClassificationStatus, int]:
    if not isinstance(value, dict) or any(
        not _is_classification_status(key) or not _is_nonnegative_int(count)
        for key, count in value.items()
    ):
        raise InvalidDomainInputError(f"{context}.status_counts is invalid")
    return {
        key: _nonnegative_integer(value, key, f"{context}.status_counts")
        for key in value
        if _is_classification_status(key)
    }


def _validate_coverage_branch(value: object, context: str) -> CoverageBranch:
    if not isinstance(value, dict):
        raise InvalidDomainInputError(f"{context} must be an object")
    branch = _string_field(value, "branch", context)
    site = _string_field(value, "site", context)
    page_count = _nonnegative_integer(value, "page_count", context)
    tag_count = _nonnegative_integer(value, "tag_count", context)
    status_counts = _validate_status_counts(value.get("status_counts"), context)
    tags = value.get("tags")
    if not isinstance(tags, list):
        raise InvalidDomainInputError(f"{context}.tags must be an array")
    validated_tags = [
        _validate_coverage_tag(tag, f"{context}.tags[{tag_index}]")
        for tag_index, tag in enumerate(tags)
    ]
    if tag_count != len(validated_tags):
        raise InvalidDomainInputError(f"{context}.tag_count does not match tags")
    return {
        "branch": branch,
        "site": site,
        "page_count": page_count,
        "tag_count": tag_count,
        "status_counts": status_counts,
        "tags": validated_tags,
    }


def validate_coverage(raw: object) -> Coverage:
    """Validate one generated coverage document before HTML publication."""
    if not isinstance(raw, dict):
        raise InvalidDomainInputError("coverage root must be an object")
    schema_version = raw.get("schema_version")
    if not _is_nonnegative_int(schema_version):
        raise InvalidDomainInputError("coverage.schema_version must be a non-negative integer")
    source = _validate_coverage_source(raw.get("source"))
    raw_status_descriptions = _validate_description_map(
        raw.get("status_descriptions"),
        CLASSIFICATION_STATUSES,
        "coverage.status_descriptions",
    )
    raw_action_descriptions = _validate_description_map(
        raw.get("action_descriptions"),
        COVERAGE_TRANSLATION_ACTIONS,
        "coverage.action_descriptions",
    )
    branches = raw.get("branches")
    if not isinstance(branches, list):
        raise InvalidDomainInputError("coverage.branches must be an array")
    status_descriptions: dict[ClassificationStatus, str] = {
        key: raw_status_descriptions[key]
        for key in raw_status_descriptions
        if _is_classification_status(key)
    }
    action_descriptions: dict[CoverageTranslationAction, str] = {
        key: raw_action_descriptions[key]
        for key in raw_action_descriptions
        if _is_coverage_translation_action(key)
    }
    coverage: Coverage = {
        "schema_version": schema_version,
        "source": source,
        "status_descriptions": status_descriptions,
        "action_descriptions": action_descriptions,
        "branches": [
            _validate_coverage_branch(branch, f"coverage.branches[{branch_index}]")
            for branch_index, branch in enumerate(branches)
        ],
    }
    return coverage


__all__ = ["validate_coverage"]
