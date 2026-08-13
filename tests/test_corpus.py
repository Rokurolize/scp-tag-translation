"""Focused validation tests for corpus metadata boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pipeline.corpus import iter_corpus_page_tags


def _write_metadata(root: Path, value: object) -> Path:
    metadata = root / "en" / "pages" / "fixture" / "meta.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(json.dumps(value), encoding="utf-8")
    return metadata


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (["not", "an", "object"], "metadata root must be an object"),
        ({"tags": 3}, "invalid tags field"),
        ({"tags": ["", "scp"]}, "invalid tags field"),
        ({"tags": ["scp", 4]}, "invalid tags field"),
        ({"tags": ["scp", "scp"]}, "duplicate tags"),
    ],
)
def test_iter_corpus_page_tags_rejects_invalid_metadata(
    tmp_path: Path,
    metadata: object,
    message: str,
):
    metadata_path = _write_metadata(tmp_path, metadata)

    with pytest.raises(ValueError, match=message):
        list(iter_corpus_page_tags(tmp_path, "en"))

    assert metadata_path.is_file()


def test_iter_corpus_page_tags_reports_missing_pages_directory(tmp_path: Path):
    with pytest.raises(ValueError, match="pages directory"):
        list(iter_corpus_page_tags(tmp_path, "en"))


def test_iter_corpus_page_tags_accepts_single_string_tag(tmp_path: Path):
    _write_metadata(tmp_path, {"tags": "scp"})

    assert list(iter_corpus_page_tags(tmp_path, "en")) == [("fixture", ["scp"])]
