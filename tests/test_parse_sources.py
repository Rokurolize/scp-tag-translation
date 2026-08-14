"""Atomic parse-source orchestration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.commands import parse_sources
from scripts.application import source_parse as parse_workflow
from scripts.application.source_parsing.crosswalks import (
    CrosswalkParseInputs,
    collect_crosswalk_parses,
)
from scripts.application.source_parsing import models as source_parse_models
from scripts.application.source_parsing import records as source_parse_records
from scripts.application.source_parsing import reporting as source_parse_reporting
from scripts.domain.crosswalk_resolution import CrosswalkResolver
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


def test_source_parse_support_preserves_batch_diagnostics(tmp_path):
    output = tmp_path / "records.json"
    output.write_text("[]", encoding="utf-8")
    batch = source_parse_models.ParseBatch(
        outputs={output: []},
        messages=("parsed",),
        diagnostics=("warning",),
    )

    assert source_parse_records.load_json_array(output, "records") == []
    merged = source_parse_reporting.merge_batches([batch])
    assert merged.messages == ("parsed",)
    assert merged.diagnostics == ("warning",)


def test_parse_workflow_rejects_diagnostics_before_publication(monkeypatch):
    batch = source_parse_models.ParseBatch(
        outputs={},
        messages=("parsed",),
        diagnostics=("source:1: malformed",),
    )
    publish_calls = []
    monkeypatch.setattr(
        parse_workflow,
        "collect_outputs",
        lambda _language, *, config=None: batch,
    )
    monkeypatch.setattr(
        parse_workflow,
        "publish_outputs",
        lambda outputs: publish_calls.append(outputs),
    )

    with pytest.raises(ValueError, match="不完全なレコード"):
        parse_workflow.parse_and_publish_sources("en")

    assert publish_calls == []


def test_crosswalk_stage_collects_parser_results_and_diagnostics(tmp_path):
    int_source = tmp_path / "int.txt"
    ko_source = tmp_path / "ko.txt"
    guide_source = tmp_path / "guide.txt"
    for source in (int_source, ko_source, guide_source):
        source.write_text("fixture\n", encoding="utf-8")

    class IntParser:
        def parse_int_crosswalk(
            self,
            input_path,
            resolver,
            *,
            strict=False,
            diagnostics=None,
        ):
            assert input_path == int_source
            assert strict is True
            assert diagnostics == []
            assert resolver(["unknown"], []) is None
            return {"int": {"source": "対象"}}

    class KoParser:
        def parse_ko_crosswalk(
            self,
            input_path,
            resolver,
            *,
            strict=False,
            diagnostics=None,
        ):
            assert input_path == ko_source
            assert strict is True
            assert diagnostics == []
            assert resolver(["unknown"], []) is None
            return {"ko": {"한국어": "対象"}}

    class BranchGuideParser:
        def analyze_branch_guides(
            self,
            source_paths,
            resolver,
            *,
            strict,
            diagnostics,
        ):
            assert source_paths == {"ua": (guide_source,)}
            assert strict is True
            assert resolver(["unknown"], []) is None
            diagnostics.append("ua:1: unresolved")
            return _branch_analysis(accepted=1, unresolved=1)

    result = collect_crosswalk_parses(
        inputs=CrosswalkParseInputs(
            sources_int=int_source,
            sources_ko=ko_source,
            branch_guide_sources={"ua": (guide_source,)},
        ),
        int_parser_impl=IntParser(),
        ko_parser_impl=KoParser(),
        branch_guide_parser_impl=BranchGuideParser(),
        resolver=CrosswalkResolver([]),
    )

    assert result.int_mappings == {"int": {"source": "対象"}}
    assert result.ko_mappings == {"ko": {"한국어": "対象"}}
    assert result.branch_analysis.stats["ua"]["accepted_tags"] == 1
    assert result.diagnostics == ("ua:1: unresolved",)


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
        monkeypatch.setattr(parse_workflow, name, value)
    return outputs


def test_run_jp_clears_deprecated_data_when_unused_source_missing(
    tmp_path,
    monkeypatch,
):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    (parse_workflow.SOURCES_JP / "fragment-basic.txt").write_text(
        "* **[[[/system:page-tags/tag/scp|scp]]]** //(scp)// - SCP。",
        encoding="utf-8",
    )
    outputs[2].write_text(
        json.dumps([{"source_tag": "stale", "replacement": "古い置換"}]),
        encoding="utf-8",
    )

    parse_workflow.parse_and_publish_sources("jp")

    assert json.loads(outputs[1].read_text(encoding="utf-8"))[0]["name"] == "scp"
    assert json.loads(outputs[2].read_text(encoding="utf-8")) == []


def test_run_all_does_not_publish_when_last_parser_fails(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    old_payloads = {}
    for index, output in enumerate(outputs):
        old_payloads[output] = f"old-{index}\n".encode()
        output.write_bytes(old_payloads[output])

    monkeypatch.setattr(
        parse_workflow.en_parser,
        "parse_en_tags",
        lambda _path, **_kwargs: [{"name": "source", "category": None, "meta": {}}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_jp_tags",
        lambda _path, **_kwargs: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_unused_tag_records",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        parse_workflow.int_parser,
        "parse_int_crosswalk",
        lambda *_args, **_kwargs: {"en": {}},
    )
    monkeypatch.setattr(
        parse_workflow.ko_parser,
        "parse_ko_crosswalk",
        lambda *_args, **_kwargs: {"ko": {}},
    )
    monkeypatch.setattr(
        parse_workflow.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("late parser failure")),
    )
    publish_calls = []
    monkeypatch.setattr(
        parse_workflow,
        "publish_outputs",
        lambda payloads: publish_calls.append(payloads),
    )

    with pytest.raises(ValueError, match="late parser failure"):
        parse_workflow.parse_and_publish_sources("all")

    assert publish_calls == []
    assert {path: path.read_bytes() for path in outputs} == old_payloads


def test_run_all_blocks_publication_on_malformed_crosswalk_rows(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    for index, output in enumerate(outputs):
        output.write_text(f"old-{index}\n", encoding="utf-8")
    old_payloads = {path: path.read_bytes() for path in outputs}
    parse_workflow.SOURCES_INT.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| [/system:page-tags/tag/ broken || 対象 || ||\n",
        encoding="utf-8",
    )
    parse_workflow.SOURCES_KO.write_text(
        "||~ ^^English^^ ||~ ^^日本語^^ ||~ ^^한국어^^ ||\n"
        "|| source || 対象 || [*/system:page-tags/tag/ broken] ||\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        parse_workflow.en_parser,
        "parse_en_tags",
        lambda _path, **_kwargs: [{"name": "source", "category": None, "meta": {}}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_jp_tags",
        lambda _path, **_kwargs: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_unused_tag_records",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        parse_workflow.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _branch_analysis(),
    )
    publish_calls = []
    monkeypatch.setattr(
        parse_workflow,
        "publish_outputs",
        lambda payloads: publish_calls.append(payloads),
    )

    with pytest.raises(ValueError, match="malformed source record"):
        parse_workflow.parse_and_publish_sources("all")

    assert publish_calls == []
    assert {path: path.read_bytes() for path in outputs} == old_payloads


def test_all_crosswalks_use_same_run_jp_records(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    outputs[1].write_text("not current JSON", encoding="utf-8")
    outputs[2].write_text("not current JSON", encoding="utf-8")
    monkeypatch.setattr(
        parse_workflow.en_parser,
        "parse_en_tags",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_jp_tags",
        lambda _path, **_kwargs: [{"name": "new-target", "source_tags": ["semantic"]}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_unused_tag_records",
        lambda _path, **_kwargs: [],
    )

    def parse_int(_path, resolver, **_kwargs):
        return {"en": {"semantic": resolver(["semantic"], [])}}

    monkeypatch.setattr(parse_workflow.int_parser, "parse_int_crosswalk", parse_int)
    monkeypatch.setattr(
        parse_workflow.ko_parser,
        "parse_ko_crosswalk",
        lambda *_args, **_kwargs: {"ko": {}},
    )
    monkeypatch.setattr(
        parse_workflow.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _branch_analysis(
            {"ua": {"local": "new-target"}},
            accepted=1,
            conflicting=2,
            unresolved=3,
        ),
    )

    batch = parse_workflow.collect_outputs("all")

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
        parse_workflow.collect_outputs("crosswalks")

    assert not any(path.exists() for path in outputs[3:])


def test_run_all_publishes_six_outputs_in_one_atomic_batch(tmp_path, monkeypatch):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        parse_workflow.en_parser,
        "parse_en_tags",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_jp_tags",
        lambda _path, **_kwargs: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(
        parse_workflow.jp_parser,
        "parse_unused_tag_records",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        parse_workflow.int_parser,
        "parse_int_crosswalk",
        lambda *_args, **_kwargs: {"en": {}},
    )
    monkeypatch.setattr(
        parse_workflow.ko_parser,
        "parse_ko_crosswalk",
        lambda *_args, **_kwargs: {"ko": {}},
    )
    monkeypatch.setattr(
        parse_workflow.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _branch_analysis(),
    )
    calls = []
    real_publish = parse_workflow.publish_files_atomically

    def publish_and_record(writers):
        calls.append(writers)
        real_publish(writers)

    monkeypatch.setattr(parse_workflow, "publish_files_atomically", publish_and_record)

    batch = parse_workflow.parse_and_publish_sources("all")

    assert len(calls) == 1
    assert set(calls[0]) == set(outputs) == set(batch.outputs)
    for destination in outputs:
        assert json.loads(destination.read_text(encoding="utf-8")) == batch.outputs[
            destination
        ]
    assert not list(tmp_path.rglob(".*.tmp"))
    assert not list(tmp_path.rglob(".*.bak"))


def test_run_all_integrates_real_parsers_with_temporary_sources(
    tmp_path,
    monkeypatch,
):
    outputs = _redirect_pipeline_paths(monkeypatch, tmp_path)
    parse_workflow.SOURCES_EN.write_text(
        "* **[https://scp-wiki.wikidot.com/system:page-tags/tag/source source]**\n",
        encoding="utf-8",
    )
    (parse_workflow.SOURCES_JP / "fragment-basic.txt").write_text(
        "**[[[/system:page-tags/tag/jp-target|jp-target]]]** //(source)//\n",
        encoding="utf-8",
    )
    parse_workflow.SOURCES_INT.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| source || jp-target || local ||\n",
        encoding="utf-8",
    )
    parse_workflow.SOURCES_KO.write_text(
        "|| source || jp-target || "
        "[[[/system:page-tags/tag/ko-source]]] ||\n",
        encoding="utf-8",
    )
    next(iter(parse_workflow.BRANCH_GUIDE_SOURCES.values()))[0].write_text(
        "**local** (source)\n",
        encoding="utf-8",
    )

    batch = parse_workflow.parse_and_publish_sources("all")

    assert json.loads(outputs[0].read_text(encoding="utf-8"))[0]["name"] == "source"
    assert json.loads(outputs[1].read_text(encoding="utf-8"))[0]["name"] == "jp-target"
    assert json.loads(outputs[3].read_text(encoding="utf-8")) == {
        "cn": {"local": "jp-target"},
        "en": {"source": "jp-target"},
        "int": {"source": "jp-target"},
    }
    assert json.loads(outputs[4].read_text(encoding="utf-8")) == {
        "ko": {"ko-source": "jp-target"},
    }
    assert json.loads(outputs[5].read_text(encoding="utf-8")) == {
        "ua": {"local": "jp-target"},
    }
    assert set(batch.outputs) == set(outputs)


def test_collect_outputs_rejects_unknown_language():
    with pytest.raises(ValueError, match="未対応"):
        parse_workflow.collect_outputs("typo")


@pytest.mark.parametrize("error", [OSError("disk"), ValueError("schema")])
def test_main_reports_expected_input_failures(monkeypatch, capsys, error):
    monkeypatch.setattr(sys, "argv", ["parse_sources.py", "--lang", "all"])
    monkeypatch.setattr(
        parse_workflow,
        "parse_and_publish_sources",
        lambda _language: (_ for _ in ()).throw(error),
    )

    with pytest.raises(SystemExit) as caught:
        parse_sources.main()

    assert caught.value.code == 1
    assert capsys.readouterr().out == (f"エラー: ソース解析に失敗しました: {error}\n")


def test_main_does_not_hide_programming_errors(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["parse_sources.py", "--lang", "all"])
    monkeypatch.setattr(
        parse_workflow,
        "parse_and_publish_sources",
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
