"""parse_sources.py の生成ファイル更新テスト"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import parse_sources


def test_run_jp_clears_deprecated_data_when_unused_source_missing(
    tmp_path,
    monkeypatch,
):
    sources_jp = tmp_path / "sources" / "jp"
    data_dir = tmp_path / "data"
    sources_jp.mkdir(parents=True)
    data_dir.mkdir()

    (sources_jp / "fragment-basic.txt").write_text(
        "* **[[[/system:page-tags/tag/scp|scp]]]** //(scp)// - SCP。",
        encoding="utf-8",
    )
    data_deprecated = data_dir / "deprecated_tags.json"
    data_deprecated.write_text(
        json.dumps([{"en_tag": "stale", "replacement": "古い置換"}]),
        encoding="utf-8",
    )

    monkeypatch.setattr(parse_sources, "_SOURCES_JP", sources_jp)
    monkeypatch.setattr(
        parse_sources,
        "_SOURCES_JP_UNUSED",
        sources_jp / "fragment-unused.txt",
    )
    monkeypatch.setattr(parse_sources, "_DATA_JP", data_dir / "jp_tags.json")
    monkeypatch.setattr(parse_sources, "_DATA_DEPRECATED", data_deprecated)

    parse_sources.run_jp()

    assert json.loads(data_deprecated.read_text(encoding="utf-8")) == []
