from pathlib import Path

import pytest

from scripts.application import source_parse
from scripts.application.source_parse import (
    ParseOutputPaths,
    ParseSourcePaths,
    ParseWorkflowConfig,
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
    source_en.write_text(
        "* **[https://scp-wiki.wikidot.com/system:page-tags/tag/source source]**\n",
        encoding="utf-8",
    )
    (jp_dir / "fragment-basic.txt").write_text(
        "**[[[/system:page-tags/tag/target|target]]]** //(source)//\n",
        encoding="utf-8",
    )
    source_guide.write_text("**local** (source)\n", encoding="utf-8")
    source_ko.write_text(
        "||~ ^^English^^ ||~ ^^日本語^^ ||~ ^^한국어^^ ||\n"
        "|| source || 対象 || [*/system:page-tags/tag/ko-source] ||\n",
        encoding="utf-8",
    )
    source_int.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| [/system:page-tags/tag/ broken || 対象 || ||\n",
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
    with pytest.raises(ValueError, match="malformed source record"):
        source_parse.parse_and_publish_sources("all", config=config)

    assert {path: path.read_bytes() for path in outputs} == old_payloads
