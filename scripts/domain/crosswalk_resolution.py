"""Resolve official crosswalk rows to names in the current JP tag list."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from scripts.domain.policy.tag_policy import build_jp_names_and_source_map
from scripts.domain.records.tag_records import DeprecatedTag, JpTag
from scripts.domain.records.tag_validation import validate_deprecated_tags, validate_jp_tags
from scripts.shared.tag_text import normalize_tag


class CrosswalkResolver:
    """Resolve EN semantic anchors and JP labels to one current JP tag."""

    def __init__(
        self,
        jp_tags: list[JpTag],
        deprecated_tags: list[DeprecatedTag] | None = None,
        origin_replacements: Mapping[str, str] | None = None,
    ) -> None:
        validated_jp_tags = validate_jp_tags(jp_tags)
        validated_deprecated_tags = validate_deprecated_tags(
            deprecated_tags or [],
            validated_jp_tags,
        )

        self.jp_names: set[str] = set()
        self.normalized_jp_names: dict[str, set[str]] = {}
        self.source_to_jp: dict[str, str] = {}
        self.en_replacements: dict[str, str] = {}

        self._index_current_tags(validated_jp_tags)
        self._index_en_replacements(
            validated_deprecated_tags,
            origin_replacements or {},
        )

    def _index_current_tags(self, jp_tags: list[JpTag]) -> None:
        """Populate indexes derived from current JP tags."""

        for entry in jp_tags:
            name = entry["name"]
            self.jp_names.add(name)
            self.normalized_jp_names.setdefault(normalize_tag(name), set()).add(name)
        _, source_map = build_jp_names_and_source_map(jp_tags)
        for source_tag, name in source_map.items():
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

    def _index_en_replacements(
        self,
        deprecated_tags: list[DeprecatedTag],
        origin_replacements: Mapping[str, str],
    ) -> None:
        """Populate deterministic EN replacement mappings."""

        for entry in deprecated_tags:
            if (entry.get("source_lang") or "EN") != "EN":
                continue
            source_tag = entry["source_tag"]
            replacement = entry.get("replacement")
            if replacement is not None:
                targets = self.normalized_jp_names.get(normalize_tag(replacement), set())
                if len(targets) == 1:
                    self._add_en_replacement(source_tag, next(iter(targets)))
        for source_tag, replacement in origin_replacements.items():
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
        if not semantic_replacements:
            targets.update(
                target
                for value in jp_values
                if (target := self._resolve_jp(value)) is not None
            )
        if len(targets) != 1:
            return None
        return next(iter(targets))


__all__ = ["CrosswalkResolver", "normalize_tag"]
