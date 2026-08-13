"""Batch merging and user-facing reporting for source parsing."""

from __future__ import annotations

from collections.abc import Sequence

from scripts.application.source_parse_models import ParseBatch


class SourceParseDiagnosticsError(ValueError):
    """Identify strict parser diagnostics that block publication."""

    def __init__(self, diagnostics: Sequence[str]) -> None:
        super().__init__(
            "ソース解析で不完全なレコードがあります:\n"
            + "\n".join(diagnostics)
        )
        self.diagnostics = tuple(diagnostics)


def merge_batches(batches: Sequence[ParseBatch]) -> ParseBatch:
    """Combine output files, messages, and diagnostics in phase order."""
    outputs = {}
    messages: list[str] = []
    diagnostics: list[str] = []
    for batch in batches:
        outputs.update(batch.outputs)
        messages.extend(batch.messages)
        diagnostics.extend(batch.diagnostics)
    return ParseBatch(
        outputs=outputs,
        messages=tuple(messages),
        diagnostics=tuple(diagnostics),
    )


def report_batch(batch: ParseBatch) -> None:
    """Print phase messages and explicit parser diagnostics."""
    for message in batch.messages:
        print(message)
    for diagnostic in batch.diagnostics:
        print(f"警告: {diagnostic}")


__all__ = ["SourceParseDiagnosticsError", "merge_batches", "report_batch"]
