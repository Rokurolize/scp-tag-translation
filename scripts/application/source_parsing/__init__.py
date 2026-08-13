"""Private collaborators for the source-parse application workflow.

The :mod:`scripts.application.source_parse` module is the public workflow
entry point; this package keeps its stage contracts, values, persistence,
crosswalk coordination, and reporting behind one explicit boundary.
"""

from .contracts import (
    BranchGuideParser,
    CrosswalkParsers,
    EnParser,
    IntParser,
    JpParser,
    KoParser,
)
from .crosswalks import CrosswalkParseResult, collect_crosswalk_parses
from .models import ParseBatch, ParserOutput
from .records import load_json_array, load_persisted_jp_records, require_file
from .reporting import SourceParseDiagnosticsError, merge_batches, report_batch

__all__ = [
    "BranchGuideParser",
    "CrosswalkParseResult",
    "CrosswalkParsers",
    "EnParser",
    "IntParser",
    "JpParser",
    "KoParser",
    "ParseBatch",
    "ParserOutput",
    "SourceParseDiagnosticsError",
    "collect_crosswalk_parses",
    "load_json_array",
    "load_persisted_jp_records",
    "merge_batches",
    "report_batch",
    "require_file",
]
