from pathlib import Path

import pytest

from scripts.commands import parse_sources
from scripts.domain.tag_policy import (
    EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    EN_ORIGIN_TAG_REPLACEMENTS,
)
from scripts.parsers import branch_guide_parser, int_parser, ko_parser
from scripts.parsers.crosswalk_resolver import CrosswalkResolver, normalize_tag
from scripts.parsers.crosswalk_table import (
    EMPTY_CELL_MARKERS,
    split_wikidot_table_row,
)


def test_int_crosswalk_parses_multibranch_vectors():
    source = Path(__file__).parent.parent / "sources" / "int" / "tag-guide.txt"
    mappings = int_parser.parse_int_crosswalk_raw(source)
    assert mappings["cn"]["认知危害"] == "認識災害"
    assert mappings["de"]["lebendig"] == "生命"
    assert mappings["int"]["cognitohazard"] == "認識災害"


def test_ko_crosswalk_parses_direct_jp_vectors():
    source = Path(__file__).parent.parent / "sources" / "ko" / "translate-tags.txt"
    mappings = ko_parser.parse_ko_crosswalk_raw(source)
    assert mappings["ko"]["생물"] == "生命"
    assert mappings["ko"]["정신조작"] == "精神影響"


def test_crosswalk_resolver_normalizes_stale_ko_jp_labels(
    jp_tags_data,
    deprecated_tags_data,
):
    resolver = CrosswalkResolver(
        jp_tags_data,
        deprecated_tags_data,
        EN_ORIGIN_TAG_REPLACEMENTS,
    )
    source = Path(__file__).parent.parent / "sources" / "ko" / "translate-tags.txt"
    mappings = ko_parser.parse_ko_crosswalk(source, resolver.resolve)["ko"]

    assert mappings["감정이입"] == "精神感応"
    assert mappings["비격리"] == "未収容"
    assert mappings["염력"] == "念力"
    assert mappings["유산"] == "殿堂入り"
    assert mappings["야쿠시"] == "yakushi"
    assert mappings["제cn-15구역"] == "エリア-cn-15"
    assert mappings["제cn-34기지"] == "サイト-cn-34"
    assert "제zh-22기지" not in mappings
    assert "템플릿" not in mappings


def test_crosswalk_resolver_rejects_conflicting_current_targets(jp_tags_data):
    resolver = CrosswalkResolver(jp_tags_data)

    assert resolver.resolve(["empathic"], ["念力"]) is None
    assert normalize_tag("yakushi\u202c") == "yakushi"


def test_crosswalk_resolver_normalizes_index_keys_and_detects_collisions():
    resolver = CrosswalkResolver(
        [
            {"name": "対象A", "source_tags": ["foo\u200b"]},
            {"name": "対象B", "source_tags": ["bar"]},
        ],
        [
            {
                "source_lang": "EN",
                "source_tag": "old\u200b",
                "replacement": "対象A",
            }
        ],
    )

    assert resolver.resolve(["foo"], []) == "対象A"
    assert resolver.resolve(["old"], ["対象B"]) == "対象A"
    assert resolver.resolve(["old", "bar"], []) is None

    with pytest.raises(ValueError, match="source tag maps to multiple"):
        CrosswalkResolver(
            [
                {"name": "対象A", "source_tags": ["foo\u200b"]},
                {"name": "対象B", "source_tags": ["foo"]},
            ]
        )


def test_crosswalk_resolver_rejects_normalized_replacement_collisions():
    with pytest.raises(ValueError, match="deprecated source tag maps to multiple"):
        CrosswalkResolver(
            [
                {"name": "対象A", "source_tags": []},
                {"name": "対象B", "source_tags": []},
            ],
            [{"source_tag": "old", "replacement": "対象A"}],
            {"ｏｌｄ": "対象B"},
        )


def test_en_resolution_prefers_declared_source_alias_over_coincident_jp_name():
    resolver = CrosswalkResolver(
        [
            {"name": "semantic-target", "source_tags": ["collision"]},
            {"name": "collision", "source_tags": []},
        ]
    )

    assert resolver.resolve(["collision"], []) == "semantic-target"
    assert resolver.resolve([], ["collision"]) == "collision"


@pytest.mark.parametrize(
    ("jp_tags", "deprecated_tags", "message"),
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
def test_crosswalk_resolver_rejects_noncanonical_schema(
    jp_tags,
    deprecated_tags,
    message,
):
    with pytest.raises(ValueError, match=message):
        CrosswalkResolver(jp_tags, deprecated_tags)


def test_crosswalk_table_row_splits_cells_and_discards_trailing_delimiter():
    assert split_wikidot_table_row("|| EN || || JP ||") == ["EN", "", "JP"]
    assert {"-", "N/A".casefold(), "none"} <= EMPTY_CELL_MARKERS


def test_int_and_ko_crosswalks_ignore_placeholder_cells(tmp_path):
    int_source = tmp_path / "int.txt"
    int_source.write_text(
        "|| **EN** || **JP** || **CN** ||\n"
        "|| foo || 日本語 || - ||\n"
        "|| bar || 日本語 || N/A ||\n",
        encoding="utf-8",
    )
    ko_source = tmp_path / "ko.txt"
    ko_source.write_text(
        "|| foo || - || [https://ko.example/system:page-tags/tag/한국어 한국어] ||\n",
        encoding="utf-8",
    )

    int_mappings = int_parser.parse_int_crosswalk_raw(int_source)
    ko_mappings = ko_parser.parse_ko_crosswalk_raw(ko_source)

    assert "-" not in int_mappings.get("cn", {})
    assert "N/A" not in int_mappings.get("cn", {})
    assert ko_mappings == {"ko": {}}


def test_crosswalk_semantic_replacement_overrides_stale_raw_jp_label(
    jp_tags_data,
    deprecated_tags_data,
):
    resolver = CrosswalkResolver(
        jp_tags_data,
        deprecated_tags_data,
        EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    )

    assert resolver.resolve(["guide"], ["ガイド"]) == "他支部公式"


def test_int_crosswalk_uses_en_semantics_for_current_jp_targets(
    jp_tags_data,
    deprecated_tags_data,
):
    resolver = CrosswalkResolver(
        jp_tags_data,
        deprecated_tags_data,
        EN_ORIGIN_TAG_REPLACEMENTS,
    )
    source = Path(__file__).parent.parent / "sources" / "int" / "tag-guide.txt"
    mappings = int_parser.parse_int_crosswalk(source, resolver.resolve)

    assert mappings["ko"]["감정이입"] == "精神感応"
    assert mappings["int"]["resource"] == "資料"


def test_branch_guides_resolve_current_jp_tags_and_reject_ambiguous_rows(
    jp_tags_data,
    deprecated_tags_data,
):
    resolver = CrosswalkResolver(
        jp_tags_data,
        deprecated_tags_data,
        EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    )
    analysis = branch_guide_parser.analyze_branch_guides(
        parse_sources.BRANCH_GUIDE_SOURCES,
        resolver.resolve,
    )
    mappings = analysis.mappings
    stats = analysis.stats

    assert mappings["cn"]["指导"] == "他支部公式"
    assert mappings["de"]["amphibisch"] == "両生類"
    assert mappings["es"]["adulto"] == "アダルト"
    assert mappings["fr"]["adulte"] == "アダルト"
    assert mappings["it"]["caino"] == "カイン"
    assert mappings["pl"]["poradnik"] == "他支部公式"
    assert mappings["pt-br"]["guia"] == "他支部公式"
    assert mappings["th"]["การทหาร"] == "軍事"
    assert mappings["ua"]["телекінез"] == "念力"
    assert mappings["vn"]["hướng-dẫn"] == "他支部公式"
    assert mappings["zh-tr"]["指導"] == "他支部公式"

    assert "建筑" not in mappings["cn"]
    assert "oria" not in mappings["pt-br"]
    assert "roedor" not in mappings["pt-br"]
    for tag in (
        "作者頁面",
        "軍事",
        "宗教",
        "joicl",
        "en-8000",
        "麥地奇藝術學院",
        "int",
    ):
        assert tag not in mappings["zh-tr"]

    assert sum(branch["accepted_tags"] for branch in stats.values()) >= 5000


def test_branch_guide_analysis_accepts_callable_and_reports_exact_audit(tmp_path):
    source = tmp_path / "ua.txt"
    source.write_text(
        "**foo** (a)\n**foo** (b)\n**bar** (unknown)\n**ok** (ok)\n",
        encoding="utf-8",
    )
    targets = {"a": "A", "b": "B", "ok": "A"}
    calls = []

    def resolve(en_values, jp_values):
        calls.append((list(en_values), list(jp_values)))
        return targets.get(calls[-1][0][0])

    analysis = branch_guide_parser.analyze_branch_guides(
        {"ua": (source,)},
        resolve,
    )

    assert analysis.mappings == {"ua": {"ok": "A"}}
    assert analysis.stats == {
        "ua": {
            "parsed_rows": 4,
            "resolved_rows": 3,
            "accepted_tags": 1,
            "conflicting_tags": 1,
            "unresolved_source_tags": 1,
        }
    }
    assert calls == [
        (["a"], []),
        (["b"], []),
        (["unknown"], []),
        (["ok"], []),
    ]
