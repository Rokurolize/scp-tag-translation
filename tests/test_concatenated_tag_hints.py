import json
from pathlib import Path

import pytest

from scripts.corpus import collect_corpus_tags_and_visible_sequences
from scripts.domain import concatenated_tags


def _visible_sequences(corpus_root: Path, branch: str):
    return collect_corpus_tags_and_visible_sequences(corpus_root, branch)[1]


def test_concatenated_tag_hints_restore_ambiguous_boundaries(tmp_path):
    pages = tmp_path / "int" / "pages"
    page_dir = pages / "separate"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["safe", "scp", "sculpture"]}),
        encoding="utf-8",
    )
    dictionary = {"safe": "safe", "scp": "scp", "sculpture": "彫像", "scpsculpture": None}

    hints = concatenated_tags.build_concatenated_tag_hints(
        "int",
        dictionary,
        _visible_sequences(tmp_path, "int"),
    )

    assert hints == {"safescpsculpture": ["safe", "scp", "sculpture"]}


def test_concatenated_tag_hints_reject_intrinsic_collisions(tmp_path):
    pages = tmp_path / "en" / "pages"
    for slug, tags in {
        "first": ["a", "bc"],
        "second": ["ab", "c"],
    }.items():
        page_dir = pages / slug
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": tags}),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="multiple corpus boundaries"):
        concatenated_tags.build_concatenated_tag_hints(
            "en",
            {"a": None, "ab": None, "bc": None, "c": None},
            _visible_sequences(tmp_path, "en"),
        )


def test_concatenated_tag_hints_reject_exact_dictionary_collision(tmp_path):
    page_dir = tmp_path / "en" / "pages" / "sample"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["scp", "sculpture"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exact dictionary key"):
        concatenated_tags.build_concatenated_tag_hints(
            "en",
            {"scp": "scp", "sculpture": "彫像", "scpsculpture": None},
            _visible_sequences(tmp_path, "en"),
        )


def test_concatenated_tag_hints_reject_tags_missing_from_dictionary(tmp_path):
    page_dir = tmp_path / "int" / "pages" / "new-tag"
    page_dir.mkdir(parents=True)
    (page_dir / "meta.json").write_text(
        json.dumps({"tags": ["known", "newtag"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="corpus tags missing from dictionary"):
        concatenated_tags.build_concatenated_tag_hints(
            "int",
            {"known": "known"},
            _visible_sequences(tmp_path, "int"),
        )
