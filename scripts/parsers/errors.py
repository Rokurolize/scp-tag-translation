"""Errors raised when an official source record is structurally malformed."""

from __future__ import annotations

from collections.abc import MutableSequence
from pathlib import Path

from scripts.domain.errors import InvalidDomainInputError


class SourceParseError(InvalidDomainInputError):
    """Identify a malformed source record with its file and line number."""

    def __init__(self, path: Path, line_number: int, detail: str) -> None:
        super().__init__(f"{path}:{line_number}: malformed source record ({detail})")
        self.path = path
        self.line_number = line_number
        self.detail = detail


def report_source_issue(
    path: Path,
    line_number: int,
    detail: str,
    diagnostics: MutableSequence[str] | None,
) -> None:
    """Raise an issue or append it to the caller's explicit diagnostics sink."""
    issue = SourceParseError(path, line_number, detail)
    if diagnostics is None:
        raise issue
    diagnostics.append(str(issue))


__all__ = ["SourceParseError", "report_source_issue"]
