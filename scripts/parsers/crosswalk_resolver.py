"""Resolve official crosswalk rows to names in the current JP tag list."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from scripts.tag_models import DeprecatedTag, JpTag
from scripts.tag_validation import validate_deprecated_tags, validate_jp_tags


def normalize_tag(value: str) -> str:
    """Normalize compatibility glyphs and discard invisible format controls."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    ).strip()


class CrosswalkResolver:
    """Resolve EN semantic anchors and JP labels to one current JP tag.

    Official tables sometimes retain old JP spellings.  EN semantic anchors
    are therefore resolved against the current JP ``source_tags`` first, while
    a current JP label remains independent corroborating evidence.  Conflicting
    current targets are rejected instead of choosing one silently.
    """

    def __init__(
        self,
        jp_tags: list[JpTag],
        deprecated_tags: list[DeprecatedTag] | None = None,
        origin_replacements: dict[str, str] | None = None,
    ) -> None:
        self.jp_names: set[str] = set()
        self.normalized_jp_names: dict[str, set[str]] = {}
        self.source_to_jp: dict[str, str] = {}
        validated_jp_tags = validate_jp_tags(jp_tags)
        validated_deprecated_tags = validate_deprecated_tags(
            deprecated_tags or [],
            validated_jp_tags,
        )
        for entry in validated_jp_tags:
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid JP tag entry: {entry!r}")
            self.jp_names.add(name)
            self.normalized_jp_names.setdefault(normalize_tag(name), set()).add(name)
            source_tags = entry["source_tags"]
            for source_tag in source_tags:
                if not isinstance(source_tag, str) or not source_tag:
                    continue
                normalized_source = normalize_tag(source_tag)
                if not normalized_source:
                    continue
                existing = self.source_to_jp.get(normalized_source)
                if existing is not None and existing != name:
                    raise ValueError(
                        "source tag maps to multiple current JP tags: "
                        f"{normalized_source!r}->{existing!r}/{name!r}"
                    )
                self.source_to_jp[normalized_source] = name

        self.en_replacements: dict[str, str] = {}
        for entry in validated_deprecated_tags:
            if (entry.get("source_lang") or "EN") != "EN":
                continue
            source_tag = entry.get("source_tag")
            replacement = entry.get("replacement")
            if isinstance(source_tag, str) and isinstance(replacement, str):
                targets = self.normalized_jp_names.get(normalize_tag(replacement), set())
                if len(targets) == 1:
                    self._add_en_replacement(source_tag, next(iter(targets)))
        for source_tag, replacement in (origin_replacements or {}).items():
            targets = self.normalized_jp_names.get(normalize_tag(replacement), set())
            if len(targets) == 1:
                self._add_en_replacement(source_tag, next(iter(targets)))

    def _add_en_replacement(self, source_tag: str, replacement: str) -> None:
        normalized_source = normalize_tag(source_tag)
        if not normalized_source:
            return
        existing = self.en_replacements.get(normalized_source)
        if existing is not None and existing != replacement:
            raise ValueError(
                "deprecated source tag maps to multiple current JP tags: "
                f"{normalized_source!r}->{existing!r}/{replacement!r}"
            )
        self.en_replacements[normalized_source] = replacement

    def _resolve_en(self, value: str) -> str | None:
        normalized = normalize_tag(value)
        if normalized in self.en_replacements:
            return self.en_replacements[normalized]
        mapped = self.source_to_jp.get(normalized)
        if mapped is not None:
            return mapped
        registered = self.normalized_jp_names.get(normalized, set())
        if len(registered) == 1:
            return next(iter(registered))
        return None

    def _resolve_jp(self, value: str) -> str | None:
        normalized = normalize_tag(value)
        targets = self.normalized_jp_names.get(normalized, set())
        if len(targets) == 1:
            return next(iter(targets))
        return self.source_to_jp.get(normalized)

    def resolve(
        self,
        en_values: Iterable[str],
        jp_values: Iterable[str],
    ) -> str | None:
        """Return the sole current target, or ``None`` for unknown/conflict."""

        normalized_en_values = [normalize_tag(value) for value in en_values]
        semantic_replacements = {
            self.en_replacements[value]
            for value in normalized_en_values
            if value in self.en_replacements
        }
        targets = {
            target
            for value in normalized_en_values
            if (target := self._resolve_en(value)) is not None
        }
        # A deprecated EN semantic replacement intentionally overrides the raw
        # JP cell because official tables often retain an obsolete JP label.
        # Other EN anchors remain independent evidence and can still conflict.
        if not semantic_replacements:
            targets.update(
                target
                for value in jp_values
                if (target := self._resolve_jp(value)) is not None
            )
        if len(targets) != 1:
            return None
        return next(iter(targets))


def load_resolver(
    jp_path: Path,
    deprecated_path: Path,
    origin_replacements: dict[str, str] | None = None,
) -> CrosswalkResolver:
    jp_tags = json.loads(jp_path.read_text(encoding="utf-8"))
    deprecated_tags = json.loads(deprecated_path.read_text(encoding="utf-8"))
    if not isinstance(jp_tags, list) or not isinstance(deprecated_tags, list):
        raise ValueError("JP tag resolver inputs must be JSON arrays")
    return CrosswalkResolver(jp_tags, deprecated_tags, origin_replacements)
