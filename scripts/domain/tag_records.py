"""Typed source and parser records used by dictionary generation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Required, TypeAlias, TypedDict


class EnTag(TypedDict, total=False):
    name: Required[str]
    category: str | None
    description: str
    meta: dict[str, list[str]]


class JpTag(TypedDict, total=False):
    name: Required[str]
    description: str
    source_tags: Required[list[str]]
    use_restricted: bool
    edit_restricted: bool
    translation_exempt: bool


class BranchOverrideRecord(TypedDict, total=False):
    jp_tag: Required[str]
    note: str


BranchOverrideValue: TypeAlias = str | BranchOverrideRecord
BranchOverrideFile: TypeAlias = Mapping[str, Mapping[str, BranchOverrideValue]]
ReplacementOverrideFile: TypeAlias = Mapping[str, Mapping[str, str]]
OfficialCrosswalkFile: TypeAlias = Mapping[str, Mapping[str, str]]


class DeprecatedTag(TypedDict, total=False):
    source_lang: str
    source_tag: Required[str]
    replacement: str | None
    description: str
