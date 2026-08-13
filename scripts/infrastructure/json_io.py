"""Shared JSON loading and serialization for generated artifacts."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from scripts.infrastructure.file_modes import DEFAULT_NEW_FILE_MODE


def load_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {path}: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})"
        ) from exc


def json_text(data: object, *, sort_top_level: bool = False) -> str:
    if sort_top_level and isinstance(data, dict):
        data = dict(sorted(data.items()))
    return f"{json.dumps(data, ensure_ascii=False, indent=2)}\n"


def write_text(path: Path, content: str) -> None:
    """Atomically serialize complete UTF-8 text to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            descriptor = -1
            file.write(content)
        mode = (
            stat.S_IMODE(path.stat().st_mode)
            if path.exists()
            else DEFAULT_NEW_FILE_MODE
        )
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def write_json(
    path: Path,
    data: object,
    *,
    sort_top_level: bool = False,
) -> None:
    write_text(
        path,
        json_text(data, sort_top_level=sort_top_level),
    )
