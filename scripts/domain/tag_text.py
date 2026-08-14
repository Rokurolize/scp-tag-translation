"""Dependency-free normalization for source tag text."""

from __future__ import annotations

import unicodedata


def normalize_tag(value: str) -> str:
    """Normalize compatibility glyphs and discard invisible format controls."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    ).strip()


__all__ = ["normalize_tag"]
