from pathlib import Path

import pytest

from scripts.parsers import jp_parser
from scripts.domain.policy.tag_policy import build_jp_names_and_source_map
from scripts.parsers.errors import SourceParseError

_JP_SOURCE_DIR = Path(__file__).parent.parent / "sources" / "jp"


class TestJpParser:
    def test_jp_entry_schema(self, jp_tags_data):
        for entry in jp_tags_data:
            assert "name" in entry, f"nameキーがない: {entry}"
            assert "en_tag" not in entry, f"legacy en_tagキーが残っています: {entry}"
            assert "description" in entry, f"descriptionキーがない: {entry}"
            assert "source_tags" in entry, f"source_tagsキーがない: {entry}"
            assert "use_restricted" in entry
            assert "edit_restricted" in entry
            assert "translation_exempt" in entry

    def test_jp_no_duplicate_names(self, jp_tags_data):
        names = [e["name"] for e in jp_tags_data]
        seen = set()
        dups = [n for n in names if n in seen or seen.add(n)]
        assert not dups, f"重複するJPタグ名: {dups}"

    def test_jp_duplicate_source_tags_have_explicit_resolution(self, jp_tags_data):
        source_tags = [
            source_tag for entry in jp_tags_data for source_tag in entry["source_tags"]
        ]
        seen = set()
        duplicates = [tag for tag in source_tags if tag in seen or seen.add(tag)]
        assert set(duplicates) == {"ghost", "orientation"}

        _jp_names, source_map = build_jp_names_and_source_map(jp_tags_data)
        assert source_map["ghost"] == "幽霊"
        assert source_map["orientation"] == "オリエンテーション"

    def test_jp_known_tags_exist(self, jp_tags_data):
        jp_names = {e["name"] for e in jp_tags_data}
        for tag in ("scp", "補足", "ハブ"):
            assert tag in jp_names, f"既知タグ '{tag}' が見つかりません"

    def test_jp_names_and_source_tags_are_trimmed(self, jp_tags_data):
        bad_entries = [
            entry
            for entry in jp_tags_data
            if entry["name"] != entry["name"].strip()
            or any(tag != tag.strip() for tag in entry["source_tags"])
        ]
        assert not bad_entries, f"前後空白付きのJPタグデータ: {bad_entries[:10]}"

    def test_jp_count_lower_bound(self, jp_tags_data):
        assert len(jp_tags_data) >= 1500, (
            f"JPタグ件数が少なすぎます: {len(jp_tags_data)}"
        )

    def test_jp_parser_accepts_wikidot_tag_url_variants(self, tmp_path):
        """system:page-tags と system/page-tags の両形式をタグリンクとして扱う。"""
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        (source_dir / "fragment-basic.txt").write_text(
            "\n".join(
                [
                    "* **[[[/system:page-tags/tag/世界観|世界観]]]** //(resource)//",
                    "* **[[[/system/page-tags/tag/_occ|_occ]]]** //(_occ)//",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_jp_tags(source_dir)

        assert {entry["name"] for entry in parsed} == {"世界観", "_occ"}
        assert {tag for entry in parsed for tag in entry["source_tags"]} == {
            "resource",
            "_occ",
        }

    def test_strict_mode_reports_malformed_tag_records(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        source = source_dir / "fragment-basic.txt"
        source.write_text(
            "* **[[[/system:page-tags/tag/ broken]]]**\n",
            encoding="utf-8",
        )
        diagnostics = []

        assert jp_parser.parse_jp_tags(
            source_dir,
            strict=True,
            diagnostics=diagnostics,
        ) == []
        assert diagnostics == [
            f"{source}:1: malformed source record (invalid JP tag link)"
        ]
        with pytest.raises(SourceParseError, match="invalid JP tag link"):
            jp_parser.parse_jp_tags(source_dir, strict=True)

    def test_parse_unused_tag_records_covers_wikidot_tag_url_variants(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "\n".join(
                [
                    "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは//世界観//タグに置換してください。",
                    "* **[[[/system/page-tags/tag/_occ|_occ]]]** //(_occ)// - ライセンス不明。",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused_tag_records(source)

        assert [entry["source_lang"] for entry in parsed] == ["EN", "EN"]
        assert [entry["source_tag"] for entry in parsed] == ["resource", "_occ"]
        assert parsed[0]["replacement"] == "世界観"

    def test_parse_unused_tag_records_source_language_sections(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "\n".join(
                [
                    "+++ EN",
                    "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは//世界観//タグに置換してください。",
                    "+++ PL",
                    "* **[[[/system:page-tags/tag/映像作品|映像作品]]]** //(film)// - //映像添付//タグに置換してください。",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused_tag_records(source)
        assert parsed == [
            {
                "source_lang": "EN",
                "source_tag": "resource",
                "replacement": "世界観",
                "description": "JPでは//世界観//タグに置換してください。",
            },
            {
                "source_lang": "PL",
                "source_tag": "film",
                "replacement": "映像添付",
                "description": "//映像添付//タグに置換してください。",
            },
        ]

    def test_parse_unused_tag_records_does_not_pick_context_dependent_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/エッセイ・ガイド|エッセイ・ガイド]]]** //(guide)// - //エッセイ//あるいは//他支部公式//に置換してください。",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused_tag_records(source)
        assert parsed[0]["replacement"] is None

    def test_parse_unused_tag_records_trims_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは// 世界観 //タグに置換してください。",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused_tag_records(source)
        assert parsed[0]["replacement"] == "世界観"

    def test_parse_unused_tag_records_deduplicates_per_source_language(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "\n".join(
                [
                    "+++ CN",
                    "* **[[[/system:page-tags/tag/wanderers|wanderers]]]** //(wanderers)// - CN。",
                    "+++ ZH",
                    "* **[[[/system:page-tags/tag/wanderers|wanderers]]]** //(wanderers)// - ZH。",
                    "* **[[[/system:page-tags/tag/wanderers|wanderers]]]** //(wanderers)// - ZH duplicate。",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused_tag_records(source)
        assert [(entry["source_lang"], entry["source_tag"]) for entry in parsed] == [
            ("CN", "wanderers"),
            ("ZH", "wanderers"),
        ]

    def test_jp_parser_ignores_wikidot_comments(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        (source_dir / "fragment-basic.txt").write_text(
            "\n".join(
                [
                    "* **[[[/system:page-tags/tag/有効|有効]]]** //(active)// - 有効。",
                    "[!--",
                    "* **[[[/system:page-tags/tag/未申請|未申請]]]** //(draft)// - 未申請。",
                    "--]",
                    "* **[[[/system:page-tags/tag/後続|後続]]]** //(after)// - 後続。",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_jp_tags(source_dir)
        names = {entry["name"] for entry in parsed}

        assert {"有効", "後続"} <= names
        assert "未申請" not in names

    def test_jp_parser_handles_inline_wikidot_comments(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        (source_dir / "fragment-basic.txt").write_text(
            (
                "* **[[[/system:page-tags/tag/前|前]]]** //(before)//"
                "[!-- **[[[/system:page-tags/tag/中|中]]]** //(inside)// --]"
                " / **[[[/system:page-tags/tag/後|後]]]** //(after)// - 説明。"
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_jp_tags(source_dir)
        names = {entry["name"] for entry in parsed}

        assert {"前", "後"} <= names
        assert "inside" not in names

    def test_jp_parser_trims_tag_slug_and_source_tag(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        (source_dir / "fragment-basic.txt").write_text(
            "* **[[[/system:page-tags/tag/年頃のガイア |年頃のガイア]]]** //( teenage-gaea )// - 説明。",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_jp_tags(source_dir)
        assert parsed[0]["name"] == "年頃のガイア"
        assert parsed[0]["source_tags"] == ["teenage-gaea"]

    def test_jp_parser_merges_aliases_and_reads_restriction_prefixes(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        (source_dir / "fragment-basic.txt").write_text(
            "* ,,\uf05e,,,,\uf084,,**[[[/system:page-tags/tag/対象|対象]]]** //(first)//\n"
            "* **[[[/system:page-tags/tag/対象|対象]]]** //(second)//\n",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_jp_tags(source_dir)

        assert parsed[0]["source_tags"] == ["first", "second"]
        assert parsed[0]["use_restricted"] is True
        assert parsed[0]["translation_exempt"] is True

    def test_current_jp_sources_include_wrapper_tags_and_policy_vectors(
        self, jp_tags_data
    ):
        by_name = {entry["name"]: entry for entry in jp_tags_data}
        assert {"始のいろは", "scp漢字ドリル", "t-arot"} <= set(by_name)
        assert by_name["テーマ"]["use_restricted"] is True
        assert by_name["テーマ"]["translation_exempt"] is False
        assert by_name["エッセイ"]["translation_exempt"] is True
        assert by_name["フラグメント"]["use_restricted"] is False
