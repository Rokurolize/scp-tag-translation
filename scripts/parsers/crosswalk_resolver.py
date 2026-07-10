"""Resolve official crosswalk rows to names in the current JP tag list."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from pathlib import Path


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
        jp_tags: list[dict],
        deprecated_tags: list[dict] | None = None,
        origin_replacements: dict[str, str] | None = None,
    ) -> None:
        self.jp_names: set[str] = set()
        self.source_to_jp: dict[str, str] = {}
        for entry in jp_tags:
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid JP tag entry: {entry!r}")
            self.jp_names.add(name)
            source_tags = entry.get("source_tags") or []
            if not source_tags and entry.get("en_tag"):
                source_tags = [entry["en_tag"]]
            for source_tag in source_tags:
                if not isinstance(source_tag, str) or not source_tag:
                    continue
                existing = self.source_to_jp.get(source_tag)
                if existing is not None and existing != name:
                    raise ValueError(
                        "source tag maps to multiple current JP tags: "
                        f"{source_tag!r}->{existing!r}/{name!r}"
                    )
                self.source_to_jp[source_tag] = name

        self.en_replacements: dict[str, str] = {}
        for entry in deprecated_tags or []:
            if (entry.get("source_lang") or "EN") != "EN":
                continue
            source_tag = entry.get("en_tag")
            replacement = entry.get("replacement")
            if (
                isinstance(source_tag, str)
                and isinstance(replacement, str)
                and replacement in self.jp_names
            ):
                self.en_replacements[source_tag] = replacement
        for source_tag, replacement in (origin_replacements or {}).items():
            if replacement in self.jp_names:
                self.en_replacements[source_tag] = replacement

        self.normalized_jp_names: dict[str, set[str]] = {}
        for name in self.jp_names:
            self.normalized_jp_names.setdefault(normalize_tag(name), set()).add(name)

    def _resolve_en(self, value: str) -> str | None:
        normalized = normalize_tag(value)
        if normalized in self.jp_names:
            return normalized
        return self.source_to_jp.get(normalized) or self.en_replacements.get(
            normalized
        )

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
        if semantic_replacements:
            if len(semantic_replacements) == 1:
                return next(iter(semantic_replacements))
            return None

        targets = {
            target
            for value in normalized_en_values
            if (target := self._resolve_en(value)) is not None
        }
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
