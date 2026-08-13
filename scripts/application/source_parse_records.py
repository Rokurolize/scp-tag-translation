"""Compatibility imports for persisted source-record loading."""

from scripts.application.source_parsing.records import (
    load_json_array,
    load_persisted_jp_records,
    require_file,
)

__all__ = ["load_json_array", "load_persisted_jp_records", "require_file"]
