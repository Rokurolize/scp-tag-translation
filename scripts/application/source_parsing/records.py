"""Shared source-input checks for the parse workflow."""

from __future__ import annotations

from pathlib import Path

def require_file(path: Path, label: str) -> None:
    """Require one parser input file to exist."""
    if not path.is_file():
        raise FileNotFoundError(f"{label}が見つかりません: {path}")

__all__ = ["require_file"]
