"""ENパーサー・JPパーサーの単体テスト"""
import json
from pathlib import Path

from parsers import en_parser
from parsers.en_parser import _parse_meta_line as _EN_PARSE_META_LINE
from parsers.en_parser import tag_pattern as _EN_TAG_PATTERN
from parsers import jp_parser
from parsers.jp_parser import _PAIR_RE as _JP_PAIR_RE
from parsers.jp_parser import _iter_uncommented_lines as _JP_UNCOMMENTED_LINES

_EN_SOURCE = Path(__file__).parent.parent / "sources" / "en" / "tag-list.txt"
_JP_SOURCE_DIR = Path(__file__).parent.parent / "sources" / "jp"


class TestEnParser:
    def test_en_entry_schema(self, en_tags_data):
        for entry in en_tags_data:
            assert "name" in entry, f"nameキーがない: {entry}"
            assert "description" in entry, f"descriptionキーがない: {entry}"
            assert "meta" in entry, f"metaキーがない: {entry}"

    def test_en_no_duplicate_names(self, en_tags_data):
        names = [e["name"] for e in en_tags_data]
        seen = set()
        dups = [n for n in names if n in seen or seen.add(n)]
        assert not dups, f"重複するENタグ名: {dups}"

    def test_en_known_tags_exist(self, en_tag_names):
        for tag in ("scp", "tale", "goi-format"):
            assert tag in en_tag_names, f"既知タグ '{tag}' が見つかりません"

    def test_en_parser_covers_all_source_tag_lines(self, en_tags_data):
        parsed_names = {entry["name"] for entry in en_tags_data}
        apparent_tag_count = 0
        missed = []

        for line in _EN_SOURCE.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("* **[http"):
                continue
            apparent_tag_count += 1
            match = _EN_TAG_PATTERN.match(line)
            if not match or match.group(1) not in parsed_names:
                missed.append(line)

        assert apparent_tag_count == len(parsed_names)
        assert not missed, f"ENパーサーの取りこぼし: {missed[:10]}"

    def test_en_known_tag_metadata_is_parsed(self, en_tags_data):
        by_name = {e["name"]: e for e in en_tags_data}

        assert by_name["scp"]["meta"]["requires-any-of-category"] == ["object-class"]
        assert by_name["scp"]["meta"]["conflicts-with"] == ["foundation-format"]
        assert by_name["component"]["meta"]["superseded-by"] == [
            "theme",
            "more-by",
        ]

    def test_en_parser_uses_url_slug_not_link_display(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        output = tmp_path / "en_tags.json"
        source.write_text(
            "* **[https://scpwiki.com/system:page-tags/tag/amoni-ram Amoni-Ram]** -- City-state.\n",
            encoding="utf-8",
        )

        en_parser.parse(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert parsed[0]["name"] == "amoni-ram"

    def test_en_colon_metadata_handles_quoted_values_with_and(self):
        assert _EN_PARSE_META_LINE("* //Requires: 'scp', and 'tale'//") == (
            "requires",
            ["scp", "tale"],
        )

    def test_en_all_metadata_lines_are_parsed(self):
        unparsed = []
        for line in _EN_SOURCE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("* //") and _EN_PARSE_META_LINE(line) is None:
                unparsed.append(line)

        assert not unparsed, f"未解析のENメタ行: {unparsed[:10]}"

    def test_en_count_lower_bound(self, en_tags_data):
        assert len(en_tags_data) >= 800, f"ENタグ件数が少なすぎます: {len(en_tags_data)}"

    def test_en_exhaustive_coverage(self, en_tags_data):
        """ソース中で tag_pattern にマッチする全行がパース結果に含まれること"""
        source_count = sum(
            1
            for line in _EN_SOURCE.read_text(encoding="utf-8").splitlines()
            if _EN_TAG_PATTERN.match(line)
        )
        parsed_count = len(en_tags_data)
        assert parsed_count == source_count, (
            f"ENパーサーの取りこぼし: ソース={source_count}件, パース結果={parsed_count}件"
        )


class TestJpParser:
    def test_jp_entry_schema(self, jp_tags_data):
        for entry in jp_tags_data:
            assert "name" in entry, f"nameキーがない: {entry}"
            assert "en_tag" in entry, f"en_tagキーがない: {entry}"
            assert "description" in entry, f"descriptionキーがない: {entry}"

    def test_jp_no_duplicate_names(self, jp_tags_data):
        names = [e["name"] for e in jp_tags_data]
        seen = set()
        dups = [n for n in names if n in seen or seen.add(n)]
        assert not dups, f"重複するJPタグ名: {dups}"

    def test_jp_en_tag_is_str_or_none(self, jp_tags_data):
        for entry in jp_tags_data:
            en_tag = entry.get("en_tag")
            assert en_tag is None or isinstance(en_tag, str), (
                f"en_tagがstrでもNoneでもない: {entry}"
            )

    def test_jp_no_duplicate_en_tags(self, jp_tags_data):
        en_tags = [e["en_tag"] for e in jp_tags_data if e.get("en_tag")]
        seen = set()
        dups = [n for n in en_tags if n in seen or seen.add(n)]
        assert not dups, f"重複するJP側ENタグ対応: {dups}"

    def test_jp_known_tags_exist(self, jp_tags_data):
        jp_names = {e["name"] for e in jp_tags_data}
        for tag in ("scp", "補足", "ハブ"):
            assert tag in jp_names, f"既知タグ '{tag}' が見つかりません"

    def test_jp_names_and_en_tags_are_trimmed(self, jp_tags_data):
        bad_entries = [
            entry
            for entry in jp_tags_data
            if entry["name"] != entry["name"].strip()
            or (
                isinstance(entry.get("en_tag"), str)
                and entry["en_tag"] != entry["en_tag"].strip()
            )
        ]
        assert not bad_entries, f"前後空白付きのJPタグデータ: {bad_entries[:10]}"

    def test_jp_count_lower_bound(self, jp_tags_data):
        assert len(jp_tags_data) >= 1500, f"JPタグ件数が少なすぎます: {len(jp_tags_data)}"

    def test_jp_exhaustive_coverage(self, jp_tags_data):
        """ソース中でスラッグ非空のタグ行（重複除去後）が全てパース結果に含まれること。
        fragment-unused.txt は parse_unused() で別途処理するため除外する。"""
        source_slugs: set[str] = set()
        for fp in sorted(_JP_SOURCE_DIR.glob("fragment-*.txt")):
            if fp.name == "fragment-unused.txt":
                continue
            for line in _JP_UNCOMMENTED_LINES(str(fp)):
                if "**[[[/system" not in line or "page-tags/tag/" not in line:
                    continue
                for m in _JP_PAIR_RE.finditer(line):
                    slug = m.group(1).strip()
                    if slug:
                        source_slugs.add(slug)

        parsed_slugs = {e["name"] for e in jp_tags_data}
        missing = source_slugs - parsed_slugs
        assert not missing, (
            f"JPパーサーの取りこぼし ({len(missing)}件): {sorted(missing)[:10]}"
        )

    def test_jp_pair_pattern_accepts_wikidot_tag_url_variants(self):
        """system:page-tags と system/page-tags の両形式をタグリンクとして扱う。"""
        colon_line = "* **[[[/system:page-tags/tag/世界観|世界観]]]** //(resource)//"
        slash_line = "* **[[[/system/page-tags/tag/_occ|_occ]]]** //(_occ)//"

        colon_match = _JP_PAIR_RE.search(colon_line)
        slash_match = _JP_PAIR_RE.search(slash_line)

        assert colon_match is not None
        assert colon_match.group(1) == "世界観"
        assert colon_match.group(3) == "resource"
        assert slash_match is not None
        assert slash_match.group(1) == "_occ"
        assert slash_match.group(3) == "_occ"

    def test_parse_unused_covers_wikidot_tag_url_variants(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
        source.write_text(
            "\n".join(
                [
                    "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは//世界観//タグに置換してください。",
                    "* **[[[/system/page-tags/tag/_occ|_occ]]]** //(_occ)// - ライセンス不明。",
                ]
            ),
            encoding="utf-8",
        )

        jp_parser.parse_unused(str(source), str(output))

        parsed = output.read_text(encoding="utf-8")
        assert '"source_lang": "EN"' in parsed
        assert '"en_tag": "resource"' in parsed
        assert '"replacement": "世界観"' in parsed
        assert '"en_tag": "_occ"' in parsed

    def test_parse_unused_records_source_language_sections(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
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

        jp_parser.parse_unused(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert parsed == [
            {
                "source_lang": "EN",
                "en_tag": "resource",
                "replacement": "世界観",
            },
            {
                "source_lang": "PL",
                "en_tag": "film",
                "replacement": "映像添付",
            },
        ]

    def test_parse_unused_does_not_pick_context_dependent_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/エッセイ・ガイド|エッセイ・ガイド]]]** //(guide)// - //エッセイ//あるいは//他支部公式//に置換してください。",
            encoding="utf-8",
        )

        jp_parser.parse_unused(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert parsed[0]["replacement"] is None

    def test_parse_unused_trims_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは// 世界観 //タグに置換してください。",
            encoding="utf-8",
        )

        jp_parser.parse_unused(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert parsed[0]["replacement"] == "世界観"

    def test_parse_unused_deduplicates_per_source_language(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
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

        jp_parser.parse_unused(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert [(entry["source_lang"], entry["en_tag"]) for entry in parsed] == [
            ("CN", "wanderers"),
            ("ZH", "wanderers"),
        ]

    def test_parse_unused_covers_all_uncommented_source_pairs(self, tmp_path):
        source = _JP_SOURCE_DIR / "fragment-unused.txt"
        output = tmp_path / "deprecated_tags.json"
        expected = set()
        source_lang = "EN"

        for line in _JP_UNCOMMENTED_LINES(str(source)):
            section_match = jp_parser._SECTION_RE.match(line.strip())
            if section_match:
                source_lang = section_match.group(1)
                continue
            if "**[[[/system" not in line or "page-tags/tag/" not in line:
                continue
            for match in _JP_PAIR_RE.finditer(line):
                en_tag = match.group(3)
                if en_tag:
                    expected.add((source_lang, en_tag))

        jp_parser.parse_unused(str(source), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        parsed_pairs = {(entry["source_lang"], entry["en_tag"]) for entry in parsed}
        assert parsed_pairs == expected

    def test_jp_parser_ignores_wikidot_comments(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        output = tmp_path / "jp_tags.json"
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

        jp_parser.parse(str(source_dir), str(output))

        parsed = output.read_text(encoding="utf-8")
        assert '"name": "有効"' in parsed
        assert '"name": "後続"' in parsed
        assert "未申請" not in parsed

    def test_jp_parser_handles_inline_wikidot_comments(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        output = tmp_path / "jp_tags.json"
        (source_dir / "fragment-basic.txt").write_text(
            (
                "* **[[[/system:page-tags/tag/前|前]]]** //(before)//"
                "[!-- **[[[/system:page-tags/tag/中|中]]]** //(inside)// --]"
                " / **[[[/system:page-tags/tag/後|後]]]** //(after)// - 説明。"
            ),
            encoding="utf-8",
        )

        jp_parser.parse(str(source_dir), str(output))

        parsed = output.read_text(encoding="utf-8")
        assert '"name": "前"' in parsed
        assert '"name": "後"' in parsed
        assert "inside" not in parsed

    def test_jp_parser_trims_tag_slug_and_en_tag(self, tmp_path):
        source_dir = tmp_path / "jp"
        source_dir.mkdir()
        output = tmp_path / "jp_tags.json"
        (source_dir / "fragment-basic.txt").write_text(
            "* **[[[/system:page-tags/tag/年頃のガイア |年頃のガイア]]]** //( teenage-gaea )// - 説明。",
            encoding="utf-8",
        )

        jp_parser.parse(str(source_dir), str(output))

        parsed = json.loads(output.read_text(encoding="utf-8"))
        assert parsed[0]["name"] == "年頃のガイア"
        assert parsed[0]["en_tag"] == "teenage-gaea"
