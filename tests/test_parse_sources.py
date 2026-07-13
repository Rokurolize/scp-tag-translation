"""Atomic parse-source orchestration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.commands import parse_sources
from scripts.parsers.contracts import BranchGuideAnalysis


def _branch_analysis(
    mappings=None,
    *,
    accepted=0,
    conflicting=0,
    unresolved=0,
):
    return BranchGuideAnalysis(
        mappings=mappings or {"ua": {}},
        stats={
            "ua": {
                "parsed_rows": accepted + conflicting + unresolved,
                "resolved_rows": accepted + conflicting,
                "accepted_tags": accepted,
                "conflicting_tags": conflicting,
                "unresolved_source_tags": unresolved,
            }
        },
    )


def _redirect_pipeline_paths(monkeypatch, tmp_path: Path) -> tuple[Path, ...]:
    sources = tmp_path / "sources"
    data = tmp_path / "data"
    jp_dir = sources / "jp"
    jp_dir.mkdir(parents=True)
    data.mkdir()

    source_en = sources / "en.txt"
    source_int = sources / "int.txt"
    source_ko = sources / "ko.txt"
    source_guide = sources / "guide.txt"
    for source in (source_en, source_int, source_ko, source_guide):
        source.write_text("fixture\n", encoding="utf-8")

    outputs = tuple(
        data / name
        for name in (
            "en_tags.json",
            "jp_tags.json",
            "deprecated_tags.json",
            "int_tag_crosswalk.json",
            "ko_tag_crosswalk.json",
            "branch_guide_crosswalk.json",
        )
    )
    replacements = {
        "SOURCES_EN": source_en,
        "SOURCES_JP": jp_dir,
        "SOURCES_JP_UNUSED": jp_dir / "fragment-unused.txt",
        "SOURCES_INT": source_int,
        "SOURCES_KO": source_ko,
        "BRANCH_GUIDE_SOURCES": {"ua": (source_guide,)},
        "DATA_EN": outputs[0],
        "DATA_JP": outputs[1],
        "DATA_DEPRECATED": outputs[2],
        "DATA_INT_CROSSWALK": outputs[3],
        "DATA_KO_CROSSWALK": outputs[4],
        "DATA_BRANCH_GUIDE_CROSSWALK": outputs[5],
    }
    for name, value in replacements.items():
        monkeypatch.setattr(parse_sources, name, value)
    return outputs


def test_run_jp_clears_deprecated_data_when_unused_source_missing(
    tmp_path,
    monkeypatch,
):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    (parse_sources.SOURCES_JP / "fragment-basic.txt").write_text(
        "* **[[[/system:page-tags/tag/scp|scp]]]** //(scp)// - SCP。",
        encoding="utf-8",
    )
    outputs[2].write_text(
        json.dumps([{"source_tag": "stale", "replacement": "古い置換"}]),
        encoding="utf-8",
    )

    parse_sources.run("jp")

    assert json.loads(outputs[1].read_text(encoding="utf-8"))[0]["name"] == "scp"
    assert json.loads(outputs[2].read_text(encoding="utf-8")) == []


def test_run_all_does_not_publish_when_last_parser_fails(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    old_payloads = {}
    for index, output in enumerate(outputs):
        old_payloads[output] = f"old-{index}\n".encode()
        output.write_bytes(old_payloads[output])

    monkeypatch.setattr(
        parse_sources.en_parser,
        "parse_en_tags",
        lambda _path: [{"name": "source", "category": None, "meta": {}}],
    )
    monkeypatch.setattr(
        parse_sources.jp_parser,
        "parse_jp_tags",
        lambda _path: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(parse_sources.jp_parser, "parse_unused", lambda _path: [])
    monkeypatch.setattr(
        parse_sources.int_parser, "parse_int_crosswalk", lambda *_args: {"en": {}}
    )
    monkeypatch.setattr(
        parse_sources.ko_parser, "parse_ko_crosswalk", lambda *_args: {"ko": {}}
    )
    monkeypatch.setattr(
        parse_sources.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args: (_ for _ in ()).throw(ValueError("late parser failure")),
    )
    publish_calls = []
    monkeypatch.setattr(
        parse_sources,
        "publish_outputs",
        lambda payloads: publish_calls.append(payloads),
    )

    with pytest.raises(ValueError, match="late parser failure"):
        parse_sources.run("all")

    assert publish_calls == []
    assert {path: path.read_bytes() for path in outputs} == old_payloads


def test_all_crosswalks_use_same_run_jp_records(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    outputs[1].write_text("not current JSON", encoding="utf-8")
    outputs[2].write_text("not current JSON", encoding="utf-8")
    monkeypatch.setattr(parse_sources.en_parser, "parse_en_tags", lambda _path: [])
    monkeypatch.setattr(
        parse_sources.jp_parser,
        "parse_jp_tags",
        lambda _path: [{"name": "new-target", "source_tags": ["semantic"]}],
    )
    monkeypatch.setattr(parse_sources.jp_parser, "parse_unused", lambda _path: [])

    def parse_int(_path, resolver):
        return {"en": {"semantic": resolver(["semantic"], [])}}

    monkeypatch.setattr(parse_sources.int_parser, "parse_int_crosswalk", parse_int)
    monkeypatch.setattr(
        parse_sources.ko_parser, "parse_ko_crosswalk", lambda *_args: {"ko": {}}
    )
    monkeypatch.setattr(
        parse_sources.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args: _branch_analysis(
            {"ua": {"local": "new-target"}},
            accepted=1,
            conflicting=2,
            unresolved=3,
        ),
    )

    batch = parse_sources.collect_outputs("all")

    assert batch.outputs[outputs[3]] == {"en": {"semantic": "new-target"}}
    assert batch.outputs[outputs[5]] == {"ua": {"local": "new-target"}}
    assert any(
        "accepted=1, conflicting=2, unresolved=3" in message
        for message in batch.messages
    )
    assert set(batch.outputs) == set(outputs)


@pytest.mark.parametrize(
    ("jp_payload", "deprecated_payload", "message"),
    [
        ([{"name": "target", "source_tags": "alias"}], [], "source_tags"),
        ([{"name": "target", "en_tag": "alias"}], [], "旧en_tag"),
        (
            [{"name": "target", "source_tags": []}],
            [{"en_tag": "old", "replacement": "target"}],
            "旧en_tag",
        ),
    ],
)
def test_crosswalks_reject_noncanonical_persisted_schema(
    tmp_path,
    monkeypatch,
    jp_payload,
    deprecated_payload,
    message,
):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    outputs[1].write_text(json.dumps(jp_payload), encoding="utf-8")
    outputs[2].write_text(json.dumps(deprecated_payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        parse_sources.collect_outputs("crosswalks")

    assert not any(path.exists() for path in outputs[3:])


def test_run_all_publishes_six_outputs_in_one_atomic_batch(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(parse_sources.en_parser, "parse_en_tags", lambda _path: [])
    monkeypatch.setattr(
        parse_sources.jp_parser,
        "parse_jp_tags",
        lambda _path: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(parse_sources.jp_parser, "parse_unused", lambda _path: [])
    monkeypatch.setattr(
        parse_sources.int_parser, "parse_int_crosswalk", lambda *_args: {"en": {}}
    )
    monkeypatch.setattr(
        parse_sources.ko_parser, "parse_ko_crosswalk", lambda *_args: {"ko": {}}
    )
    monkeypatch.setattr(
        parse_sources.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args: _branch_analysis(),
    )
    calls = []
    monkeypatch.setattr(
        parse_sources,
        "publish_files_atomically",
        lambda writers: calls.append(writers),
    )

    batch = parse_sources.run("all")

    assert len(calls) == 1
    assert set(calls[0]) == set(outputs) == set(batch.outputs)
    for index, (destination, writer) in enumerate(calls[0].items()):
        temporary = tmp_path / f"staged-{index}.json"
        assert writer(temporary) is None
        payload = temporary.read_text(encoding="utf-8")
        assert payload.endswith("\n")
        assert json.loads(payload) == batch.outputs[destination]


def test_collect_outputs_rejects_unknown_language():
    with pytest.raises(ValueError, match="未対応"):
        parse_sources.collect_outputs("typo")


@pytest.mark.parametrize("error", [OSError("disk"), ValueError("schema")])
def test_main_reports_expected_input_failures(monkeypatch, capsys, error):
    monkeypatch.setattr(sys, "argv", ["parse_sources.py", "--lang", "all"])
    monkeypatch.setattr(
        parse_sources,
        "run",
        lambda _language: (_ for _ in ()).throw(error),
    )

    with pytest.raises(SystemExit) as caught:
        parse_sources.main()

    assert caught.value.code == 1
    assert capsys.readouterr().out == (f"エラー: ソース解析に失敗しました: {error}\n")


def test_main_does_not_hide_programming_errors(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["parse_sources.py", "--lang", "all"])
    monkeypatch.setattr(
        parse_sources,
        "run",
        lambda _language: (_ for _ in ()).throw(TypeError("bug")),
    )

    with pytest.raises(TypeError, match="bug"):
        parse_sources.main()


def test_importing_parse_sources_does_not_mutate_sys_path():
    root = Path(__file__).parent.parent
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; before=list(sys.path); "
                "import scripts.commands.parse_sources; "
                "assert sys.path == before"
            ),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
