from pathlib import Path

import pytest

from scripts.application import source_parse
from scripts.application.source_parse import (
    ParseOutputPaths,
    ParseSourcePaths,
    ParseWorkflowConfig,
)
from scripts.parsers.contracts import BranchGuideAnalysis


def _empty_branch_analysis() -> BranchGuideAnalysis:
    return BranchGuideAnalysis(
        mappings={"ua": {}},
        stats={
            "ua": {
                "parsed_rows": 0,
                "resolved_rows": 0,
                "accepted_tags": 0,
                "conflicting_tags": 0,
                "unresolved_source_tags": 0,
            }
        },
    )


def test_run_all_blocks_publication_on_malformed_crosswalk_rows(
    tmp_path: Path,
    monkeypatch,
):
    sources = tmp_path / "sources"
    data = tmp_path / "data"
    jp_dir = sources / "jp"
    jp_dir.mkdir(parents=True)
    data.mkdir()
    source_en = sources / "en.txt"
    source_int = sources / "int.txt"
    source_ko = sources / "ko.txt"
    source_guide = sources / "guide.txt"
    for source in (source_en, source_guide):
        source.write_text("fixture\n", encoding="utf-8")
    source_int.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| [/system:page-tags/tag/ broken || 対象 || ||\n",
        encoding="utf-8",
    )
    source_ko.write_text(
        "||~ ^^English^^ ||~ ^^日本語^^ ||~ ^^한국어^^ ||\n"
        "|| source || 対象 || [*/system:page-tags/tag/ broken] ||\n",
        encoding="utf-8",
    )
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
    for index, output in enumerate(outputs):
        output.write_text(f"old-{index}\n", encoding="utf-8")
    old_payloads = {path: path.read_bytes() for path in outputs}
    config = ParseWorkflowConfig(
        sources=ParseSourcePaths(
            en=source_en,
            jp=jp_dir,
            jp_unused=None,
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
    monkeypatch.setattr(
        source_parse.en_parser,
        "parse_en_tags",
        lambda _path, **_kwargs: [{"name": "source", "category": None, "meta": {}}],
    )
    monkeypatch.setattr(
        source_parse.jp_parser,
        "parse_jp_tags",
        lambda _path, **_kwargs: [{"name": "target", "source_tags": ["source"]}],
    )
    monkeypatch.setattr(
        source_parse.jp_parser,
        "parse_unused_tag_records",
        lambda _path, **_kwargs: [],
    )
    monkeypatch.setattr(
        source_parse.branch_guide_parser,
        "analyze_branch_guides",
        lambda *_args, **_kwargs: _empty_branch_analysis(),
    )
    publish_calls = []
    monkeypatch.setattr(
        source_parse,
        "publish_outputs",
        lambda payloads: publish_calls.append(payloads),
    )

    with pytest.raises(ValueError, match="malformed source record"):
        source_parse.parse_and_publish_sources("all", config=config)

    assert publish_calls == []
    assert {path: path.read_bytes() for path in outputs} == old_payloads
