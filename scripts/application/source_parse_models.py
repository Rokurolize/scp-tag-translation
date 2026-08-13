"""Value objects shared by source parsing workflow collaborators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParseBatch:
    outputs: Mapping[Path, object]
    messages: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


__all__ = ["ParseBatch"]
