"""Behavioral tests for the corpus source synchronization command."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.application import source_sync as source_workflow
from scripts.commands import sync_tag_sources_from_corpus as source_sync
from scripts.pipeline.source_manifest import corpus_source_map


def _configure_source_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, dict[str, str]]:
    repository_root = tmp_path / "repository"
    corpus_root = tmp_path / "corpus"
    source_map = {
        "sources/en/tag-guide.txt": "en/pages/tag-guide/source.wikidot.txt",
        "sources/jp/tag-guide.txt": "jp/pages/tag-guide/source.wikidot.txt",
    }
    repository_root.mkdir()
    corpus_root.mkdir()
    monkeypatch.setattr(source_workflow, "ROOT", repository_root)
    monkeypatch.setattr(source_workflow, "corpus_source_map", lambda: source_map)
    return repository_root, corpus_root, source_map


def _write_mapped_file(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_corpus_root_is_required(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sync_tag_sources_from_corpus.py"])

    with pytest.raises(SystemExit) as excinfo:
        source_sync.main()

    assert excinfo.value.code == 2
    assert "the following arguments are required: --corpus-root" in (
        capsys.readouterr().err
    )


def test_check_reports_all_sources_current(tmp_path, monkeypatch, capsys):
    repository_root, corpus_root, source_map = _configure_source_tree(
        tmp_path,
        monkeypatch,
    )
    for destination, source in source_map.items():
        _write_mapped_file(corpus_root, source, destination)
        _write_mapped_file(repository_root, destination, destination)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sync_tag_sources_from_corpus.py", "--corpus-root", str(corpus_root)],
    )

    source_sync.main()

    assert capsys.readouterr().out == "tag sources current: 2 files\n"


def test_check_reports_stale_destination_without_changing_it(
    tmp_path,
    monkeypatch,
    capsys,
):
    repository_root, corpus_root, source_map = _configure_source_tree(
        tmp_path,
        monkeypatch,
    )
    destinations = list(source_map)
    for destination, source in source_map.items():
        _write_mapped_file(corpus_root, source, f"new:{destination}")
        _write_mapped_file(repository_root, destination, f"new:{destination}")
    stale_path = repository_root / destinations[0]
    stale_path.write_text("old", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["sync_tag_sources_from_corpus.py", "--corpus-root", str(corpus_root)],
    )

    with pytest.raises(SystemExit) as excinfo:
        source_sync.main()

    assert excinfo.value.code == 1
    assert stale_path.read_text(encoding="utf-8") == "old"
    assert capsys.readouterr().out == (
        "tag sources are stale or missing:\n"
        f"  {destinations[0]}\n"
    )


def test_write_refuses_partial_source_set_without_publishing(
    tmp_path,
    monkeypatch,
    capsys,
):
    repository_root, corpus_root, source_map = _configure_source_tree(
        tmp_path,
        monkeypatch,
    )
    destinations = list(source_map)
    sources = list(source_map.values())
    available_source = _write_mapped_file(corpus_root, sources[0], "new-en")
    first_destination = _write_mapped_file(
        repository_root,
        destinations[0],
        "old-en",
    )
    second_destination = _write_mapped_file(
        repository_root,
        destinations[1],
        "old-jp",
    )
    missing_source = corpus_root / sources[1]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_tag_sources_from_corpus.py",
            "--corpus-root",
            str(corpus_root),
            "--write",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        source_sync.main()

    assert excinfo.value.code == 1
    assert available_source.read_text(encoding="utf-8") == "new-en"
    assert first_destination.read_text(encoding="utf-8") == "old-en"
    assert second_destination.read_text(encoding="utf-8") == "old-jp"
    output = capsys.readouterr().out
    assert f"missing corpus source: {missing_source}\n" in output
    assert f"  {destinations[0]}\n" in output
    assert f"  {destinations[1]}\n" in output


def test_write_reports_zero_files_when_missing_source_blocks_publication(tmp_path):
    repository_root = tmp_path / "repository"
    corpus_root = tmp_path / "corpus"
    source_map = {
        "sources/en/tag-guide.txt": "en/pages/tag-guide/source.wikidot.txt",
        "sources/jp/tag-guide.txt": "jp/pages/tag-guide/source.wikidot.txt",
    }
    available_source = _write_mapped_file(
        corpus_root,
        source_map["sources/en/tag-guide.txt"],
        "new-en",
    )
    destination = _write_mapped_file(
        repository_root,
        "sources/en/tag-guide.txt",
        "old-en",
    )
    result = source_workflow.sync_tag_sources(
        corpus_root,
        config=source_workflow.SourceSyncConfig(
            source_map=source_map,
            repository_root=repository_root,
        ),
    )

    assert available_source.read_text(encoding="utf-8") == "new-en"
    assert destination.read_text(encoding="utf-8") == "old-en"
    assert result.wrote_files == 0
    assert result.missing_sources == (
        corpus_root / source_map["sources/jp/tag-guide.txt"],
    )


def test_write_synchronizes_every_stale_destination(
    tmp_path,
    monkeypatch,
    capsys,
):
    repository_root, corpus_root, source_map = _configure_source_tree(
        tmp_path,
        monkeypatch,
    )
    for index, (destination, source) in enumerate(source_map.items()):
        _write_mapped_file(corpus_root, source, f"new-{index}")
        _write_mapped_file(repository_root, destination, f"old-{index}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_tag_sources_from_corpus.py",
            "--corpus-root",
            str(corpus_root),
            "--write",
        ],
    )

    source_sync.main()

    for destination, source in source_map.items():
        assert (repository_root / destination).read_bytes() == (
            corpus_root / source
        ).read_bytes()
    assert capsys.readouterr().out == "tag sources synced: 2 files\n"


def test_write_synchronizes_the_complete_source_manifest(tmp_path):
    repository_root = tmp_path / "repository"
    corpus_root = tmp_path / "corpus"
    source_map = corpus_source_map()
    config = source_workflow.SourceSyncConfig(
        source_map=source_map,
        repository_root=repository_root,
    )
    for index, source_rel in enumerate(source_map.values()):
        _write_mapped_file(corpus_root, source_rel, f"source-{index}")

    result = source_workflow.sync_tag_sources(
        corpus_root,
        config=config,
    )

    assert result.stale_paths == ()
    assert result.missing_sources == ()
    assert result.wrote_files == len(source_map)
    for index, destination_rel in enumerate(source_map):
        assert (repository_root / destination_rel).read_text(encoding="utf-8") == (
            f"source-{index}"
        )


def test_write_reports_publication_failure_without_traceback(
    tmp_path,
    monkeypatch,
    capsys,
):
    repository_root, corpus_root, source_map = _configure_source_tree(
        tmp_path,
        monkeypatch,
    )
    for destination, source in source_map.items():
        _write_mapped_file(corpus_root, source, "new")
        _write_mapped_file(repository_root, destination, "old")

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(
        source_workflow,
        "publish_files_atomically",
        fail_publication,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sync_tag_sources_from_corpus.py",
            "--corpus-root",
            str(corpus_root),
            "--write",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        source_sync.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "エラー: タグソース同期に失敗しました: disk full\n"
    )
    for destination in source_map:
        assert (repository_root / destination).read_text(encoding="utf-8") == "old"
