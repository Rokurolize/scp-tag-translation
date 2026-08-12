"""Shared JSON loading and serialization for generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def json_text(data: object, *, sort_top_level: bool = False) -> str:
    if sort_top_level and isinstance(data, dict):
        data = dict(sorted(data.items()))
    return f"{json.dumps(data, ensure_ascii=False, indent=2)}\n"


def write_json(
    path: Path,
    data: object,
    *,
    sort_top_level: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json_text(data, sort_top_level=sort_top_level),
        encoding="utf-8",
    )
