"""Persisted source-record loading for the parse workflow."""

from __future__ import annotations

from pathlib import Path

from scripts.domain.errors import InvalidDomainInputError
from scripts.domain.records.tag_records import DeprecatedTag, JpTag
from scripts.domain.records.tag_validation import validate_deprecated_tags, validate_jp_tags
from scripts.infrastructure.json_io import load_json


def require_file(path: Path, label: str) -> None:
    """Require one parser input file to exist."""
    if not path.is_file():
        raise FileNotFoundError(f"{label}が見つかりません: {path}")


def load_json_array(path: Path, label: str) -> list[object]:
    """Load one required JSON array with a contextual schema error."""
    require_file(path, label)
    value = load_json(path)
    if not isinstance(value, list):
        raise InvalidDomainInputError(f"{label}はJSON配列である必要があります: {path}")
    return value


def load_persisted_jp_records(
    data_jp: Path,
    data_deprecated: Path,
) -> tuple[list[JpTag], list[DeprecatedTag]]:
    """Load and validate JP records persisted by an earlier parse phase."""
    jp_tags = validate_jp_tags(load_json_array(data_jp, "JPタグデータ"))
    deprecated_tags = validate_deprecated_tags(
        load_json_array(data_deprecated, "JP非使用タグデータ"),
        jp_tags,
    )
    return jp_tags, deprecated_tags


__all__ = ["load_json_array", "load_persisted_jp_records", "require_file"]
