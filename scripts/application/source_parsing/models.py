"""Value objects shared by source parsing workflow collaborators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from scripts.parsers.contracts import CrosswalkMappings

ParserOutput: TypeAlias = Sequence[Mapping[str, object]] | CrosswalkMappings


@dataclass(frozen=True)
class ParseBatch:
    outputs: Mapping[Path, ParserOutput]
    messages: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


__all__ = ["ParseBatch", "ParserOutput"]
