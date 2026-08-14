"""Atomic parse-source orchestration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.commands import parse_sources
from scripts.application import source_parse as parse_workflow
from scripts.application.source_parse import (
    ParseOutputPaths,
    ParseSourcePaths,
    ParseWorkflowConfig,
)
from scripts.application.source_parsing.crosswalks import (
    CrosswalkParseInputs,
    collect_crosswalk_parses,
)
from scripts.application.source_parsing import crosswalks as crosswalk_stage
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
    batch = source_parse_models.ParseBatch(
        outputs={},
        messages=("parsed",),
        diagnostics=("warning",),
    )

    merged = source_parse_reporting.merge_batches([batch])
    assert merged.messages == ("parsed",)
    assert merged.diagnostics == ("warning",)


def test_source_parse_requires_existing_input_file(tmp_path):
    existing = tmp_path / "source.txt"
    existing.write_text("source", encoding="utf-8")
    source_parse_records.require_file(existing, "source")

    with pytest.raises(FileNotFoundError, match="missing"):
        source_parse_records.require_file(tmp_path / "missing.txt", "missing")


def test_parse_workflow_rejects_diagnostics_before_publication(monkeypatch):
    batch = source_parse_models.ParseBatch(
        outputs={},
        messages=("parsed",),
        diagnostics=("source:1: malformed",),
    )
    publish_calls = []
    monkeypatch.setattr(
        parse_workflow,
        "collect_parsed_source_outputs",
        lambda _language, *, config=None: batch,
    )
    monkeypatch.setattr(
        parse_workflow,
        "publish_parsed_source_outputs",
        lambda outputs: publish_calls.append(outputs),
    )

    with pytest.raises(ValueError, match="不完全なレコード"):
        parse_workflow.parse_and_publish_sources("en")

    assert publish_calls == []


def test_crosswalk_stage_collects_parser_results_and_diagnostics(tmp_path):
    int_source = tmp_path / "int.txt"
    ko_source = tmp_path / "ko.txt"
    guide_source = tmp_path / "guide.txt"
    int_source.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| source || target || ||\n",
        encoding="utf-8",
    )
    ko_source.write_text(
        "||~ ^^English^^ ||~ ^^日本語^^ ||~ ^^한국어^^ ||\n"
        "|| source || target || [*/system:page-tags/tag/ko-tag] ||\n",
        encoding="utf-8",
    )
    guide_source.write_text("**source** (source)\n", encoding="utf-8")

    result = collect_crosswalk_parses(
        inputs=CrosswalkParseInputs(
            int_source=int_source,
            ko_source=ko_source,
            branch_guide_sources={"ua": (guide_source,)},
        ),
        resolver=CrosswalkResolver(
            [{"name": "target", "source_tags": ["source"]}]
        ),
    )

    assert result.int_mappings["en"] == {"source": "target"}
    assert result.ko_mappings == {"ko": {"ko-tag": "target"}}
    assert result.branch_analysis.mappings == {"ua": {"source": "target"}}
    assert result.diagnostics == ()


def _redirect_pipeline_paths(tmp_path: Path) -> tuple[ParseWorkflowConfig, tuple[Path, ...]]:
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
    config = ParseWorkflowConfig(
        sources=ParseSourcePaths(
            en=source_en,
            jp=jp_dir,
            jp_unused=jp_dir / "fragment-unused.txt",
            int=source_int,
            ko=source_ko,
            branch_guides={"ua": (source_guide,)},
        ),
        outputs=ParseOutputPaths(
            en=outputs[0],
            jp=outputs[1],
            deprecated=outputs[2],
            int_crosswalk=outputs[3],
            ko_crosswalk=outputs[4],
            branch_guide_crosswalk=outputs[5],
        ),
    )
    return config, outputs


def test_run_jp_clears_deprecated_data_when_unused_source_missing(
    tmp_path,
    monkeypatch,
):
    config, outputs = _redirect_pipeline_paths(tmp_path)
    (config.sources.jp / "fragment-basic.txt").write_text(
        "* **[[[/system:page-tags/tag/scp|scp]]]** //(scp)// - SCP。",
        encoding="utf-8",
    )
    outputs[2].write_text(
        json.dumps([{"source_tag": "stale", "replacement": "古い置換"}]),
        encoding="utf-8",
    )

    parse_workflow.parse_and_publish_sources("jp", config=config)

    assert json.loads(outputs[1].read_text(encoding="utf-8"))[0]["name"] == "scp"
    assert json.loads(outputs[2].read_text(encoding="utf-8")) == []


def test_run_all_does_not_publish_when_last_parser_fails(tmp_path, monkeypatch):
    config, outputs = _redirect_pipeline_paths(tmp_path)
    config.sources.en.write_text(
        "* **[https://scp-wiki.wikidot.com/system:page-tags/tag/source source]**\n",
        encoding="utf-8",
    )
    (config.sources.jp / "fragment-basic.txt").write_text(
        "**[[[/system:page-tags/tag/jp-target|jp-target]]]** //(source)//\n",
        encoding="utf-8",
    )
    config.sources.int.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| source || jp-target || local ||\n",
        encoding="utf-8",
    )
    config.sources.ko.write_text(
        "||~ ^^English^^ ||~ ^^日本語^^ ||~ ^^한국어^^ ||\n"
        "|| source || jp-target || [*/system:page-tags/tag/ko-source] ||\n",
        encoding="utf-8",
    )
    next(iter(config.sources.branch_guides.values()))[0].write_text(
        "**local** (source)\n",
        encoding="utf-8",
    )
    old_payloads = {}
    for index, output in enumerate(outputs):
        old_payloads[output] = f"old-{index}\n".encode()
        output.write_bytes(old_payloads[output])

    monkeypatch.setattr(
        crosswalk_stage.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("late parser failure")),
    )

    with pytest.raises(ValueError, match="late parser failure"):
        parse_workflow.parse_and_publish_sources("all", config=config)

    assert {path: path.read_bytes() for path in outputs} == old_payloads


def test_crosswalks_reparse_jp_sources_without_persisted_outputs(tmp_path, monkeypatch):
    config, outputs = _redirect_pipeline_paths(tmp_path)
    outputs[1].write_text("not current JSON", encoding="utf-8")
    outputs[2].write_text("not current JSON", encoding="utf-8")
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

    monkeypatch.setattr(crosswalk_stage.int_parser, "parse_int_crosswalk", parse_int)
    monkeypatch.setattr(
        crosswalk_stage.ko_parser,
        "parse_ko_crosswalk",
        lambda *_args, **_kwargs: {"ko": {}},
    )
    monkeypatch.setattr(
        crosswalk_stage.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _branch_analysis(
            {"ua": {"local": "new-target"}},
            accepted=1,
            conflicting=2,
            unresolved=3,
        ),
    )

    batch = parse_workflow.collect_parsed_source_outputs("crosswalks", config=config)

    assert batch.outputs[outputs[3]] == {"en": {"semantic": "new-target"}}
    assert batch.outputs[outputs[5]] == {"ua": {"local": "new-target"}}
    assert any(
        "accepted=1, conflicting=2, unresolved=3" in message
        for message in batch.messages
    )
    assert set(batch.outputs) == set(outputs[3:])


def test_crosswalk_selector_collects_jp_sources_once(monkeypatch):
    jp_batch = source_parse_models.ParseBatch(outputs={}, messages=(), diagnostics=())
    calls = []
    monkeypatch.setattr(
        parse_workflow,
        "_collect_jp_outputs",
        lambda _config: calls.append(True) or (jp_batch, [], []),
    )
    monkeypatch.setattr(
        parse_workflow,
        "_collect_crosswalk_outputs",
        lambda _config, _jp_tags, _deprecated_tags: jp_batch,
    )

    parse_workflow.collect_parsed_source_outputs("crosswalks")

    assert calls == [True]


def test_run_all_publishes_six_outputs_in_one_atomic_batch(tmp_path, monkeypatch):
    config, outputs = _redirect_pipeline_paths(tmp_path)
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
        crosswalk_stage.int_parser,
        "parse_int_crosswalk",
        lambda *_args, **_kwargs: {"en": {}},
    )
    monkeypatch.setattr(
        crosswalk_stage.ko_parser,
        "parse_ko_crosswalk",
        lambda *_args, **_kwargs: {"ko": {}},
    )
    monkeypatch.setattr(
        crosswalk_stage.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _branch_analysis(),
    )
    calls = []
    real_publish = parse_workflow.publish_files_atomically

    def publish_and_record(writers):
        calls.append(writers)
        real_publish(writers)

    monkeypatch.setattr(parse_workflow, "publish_files_atomically", publish_and_record)

    batch = parse_workflow.parse_and_publish_sources("all", config=config)

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
    config, outputs = _redirect_pipeline_paths(tmp_path)
    config.sources.en.write_text(
        "* **[https://scp-wiki.wikidot.com/system:page-tags/tag/source source]**\n",
        encoding="utf-8",
    )
    (config.sources.jp / "fragment-basic.txt").write_text(
        "**[[[/system:page-tags/tag/jp-target|jp-target]]]** //(source)//\n",
        encoding="utf-8",
    )
    config.sources.int.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| source || jp-target || local ||\n",
        encoding="utf-8",
    )
    config.sources.ko.write_text(
        "|| source || jp-target || "
        "[[[/system:page-tags/tag/ko-source]]] ||\n",
        encoding="utf-8",
    )
    next(iter(config.sources.branch_guides.values()))[0].write_text(
        "**local** (source)\n",
        encoding="utf-8",
    )

    batch = parse_workflow.parse_and_publish_sources("all", config=config)

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


def test_collect_parsed_source_outputs_rejects_unknown_language():
    with pytest.raises(ValueError, match="未対応"):
        parse_workflow.collect_parsed_source_outputs("typo")


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


def test_main_reports_successful_batch_in_command_adapter(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["parse_sources.py", "--lang", "all"])
    batch = source_parse_models.ParseBatch(
        outputs={},
        messages=("published",),
        diagnostics=(),
    )
    reported = []
    monkeypatch.setattr(
        parse_workflow,
        "parse_and_publish_sources",
        lambda _language: batch,
    )
    monkeypatch.setattr(parse_sources, "_report_batch", reported.append)

    parse_sources.main()

    assert reported == [batch]


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
