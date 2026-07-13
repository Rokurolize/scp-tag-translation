"""ENパーサー・JPパーサーの単体テスト"""
from pathlib import Path

import pytest

from scripts.commands import parse_sources
from scripts.domain.tag_policy import (
    EN_CROSSWALK_SEMANTIC_REPLACEMENTS,
    EN_ORIGIN_TAG_REPLACEMENTS,
)
from scripts.parsers import branch_guide_parser, en_parser, int_parser, jp_parser, ko_parser
from scripts.parsers.crosswalk_resolver import CrosswalkResolver, normalize_tag
from scripts.parsers.en_parser import _parse_meta_line as _EN_PARSE_META_LINE
from scripts.parsers.en_parser import _TAG_PATTERN as _EN_TAG_PATTERN
from scripts.parsers.jp_parser import _PAIR_RE as _JP_PAIR_RE
from scripts.parsers.jp_parser import _iter_uncommented_lines as _JP_UNCOMMENTED_LINES

_EN_SOURCE = Path(__file__).parent.parent / "sources" / "en" / "tag-list.txt"
_JP_SOURCE_DIR = Path(__file__).parent.parent / "sources" / "jp"


class TestEnParser:
    def test_en_entry_schema(self, en_tags_data):
        for entry in en_tags_data:
            assert "name" in entry, f"nameキーがない: {entry}"
            assert "description" in entry, f"descriptionキーがない: {entry}"
            assert "category" in entry, f"categoryキーがない: {entry}"
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
        source.write_text(
            "* **[https://scpwiki.com/system:page-tags/tag/amoni-ram Amoni-Ram]** -- City-state.\n",
            encoding="utf-8",
        )

        parsed = en_parser.parse(source)

        assert parsed[0]["name"] == "amoni-ram"

    def test_en_description_starts_after_link_even_with_double_hyphen(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/foo--bar "
            "foo--bar]** -- Real description\n",
            encoding="utf-8",
        )

        parsed = en_parser.parse(source)

        assert parsed[0]["name"] == "foo--bar"
        assert parsed[0]["description"] == "Real description"

    def test_en_tag_outside_tab_has_none_category(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/standalone "
            "standalone]** -- Description\n",
            encoding="utf-8",
        )

        assert en_parser.parse(source) == [
            {
                "name": "standalone",
                "description": "Description",
                "category": None,
                "meta": {},
            }
        ]

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

    def test_jp_no_duplicate_source_tags(self, jp_tags_data):
        source_tags = [
            source_tag
            for entry in jp_tags_data
            for source_tag in entry["source_tags"]
        ]
        seen = set()
        duplicates = [
            tag for tag in source_tags if tag in seen or seen.add(tag)
        ]
        assert not duplicates, f"重複するJP側source tag対応: {duplicates}"

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
        assert len(jp_tags_data) >= 1500, f"JPタグ件数が少なすぎます: {len(jp_tags_data)}"

    def test_jp_exhaustive_coverage(self, jp_tags_data):
        """ソース中でスラッグ非空のタグ行（重複除去後）が全てパース結果に含まれること。
        fragment-unused.txt は parse_unused() で別途処理するため除外する。"""
        source_slugs: set[str] = set()
        for name in jp_parser._REGISTERED_FRAGMENT_NAMES:
            fp = _JP_SOURCE_DIR / name
            if not fp.exists():
                continue
            for line in _JP_UNCOMMENTED_LINES(fp):
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
        source.write_text(
            "\n".join(
                [
                    "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは//世界観//タグに置換してください。",
                    "* **[[[/system/page-tags/tag/_occ|_occ]]]** //(_occ)// - ライセンス不明。",
                ]
            ),
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused(source)

        assert [entry["source_lang"] for entry in parsed] == ["EN", "EN"]
        assert [entry["source_tag"] for entry in parsed] == ["resource", "_occ"]
        assert parsed[0]["replacement"] == "世界観"

    def test_parse_unused_records_source_language_sections(self, tmp_path):
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

        parsed = jp_parser.parse_unused(source)
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

    def test_parse_unused_does_not_pick_context_dependent_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/エッセイ・ガイド|エッセイ・ガイド]]]** //(guide)// - //エッセイ//あるいは//他支部公式//に置換してください。",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused(source)
        assert parsed[0]["replacement"] is None

    def test_parse_unused_trims_replacement(self, tmp_path):
        source = tmp_path / "fragment-unused.txt"
        source.write_text(
            "+++ EN\n"
            "* **[[[/system:page-tags/tag/資料|資料]]]** //(resource)// - JPでは// 世界観 //タグに置換してください。",
            encoding="utf-8",
        )

        parsed = jp_parser.parse_unused(source)
        assert parsed[0]["replacement"] == "世界観"

    def test_parse_unused_deduplicates_per_source_language(self, tmp_path):
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

        parsed = jp_parser.parse_unused(source)
        assert [
            (entry["source_lang"], entry["source_tag"]) for entry in parsed
        ] == [
            ("CN", "wanderers"),
            ("ZH", "wanderers"),
        ]

    def test_parse_unused_covers_all_uncommented_source_pairs(self, tmp_path):
        source = _JP_SOURCE_DIR / "fragment-unused.txt"
        expected = set()
        source_lang = "EN"

        for line in _JP_UNCOMMENTED_LINES(source):
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

        parsed = jp_parser.parse_unused(source)
        parsed_pairs = {
            (entry["source_lang"], entry["source_tag"]) for entry in parsed
        }
        assert parsed_pairs == expected

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

        parsed = jp_parser.parse(source_dir)
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

        parsed = jp_parser.parse(source_dir)
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

        parsed = jp_parser.parse(source_dir)
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

        parsed = jp_parser.parse(source_dir)

        assert parsed[0]["source_tags"] == ["first", "second"]
        assert parsed[0]["use_restricted"] is True
        assert parsed[0]["translation_exempt"] is True

    def test_current_jp_sources_include_wrapper_tags_and_policy_vectors(self, jp_tags_data):
        by_name = {entry["name"]: entry for entry in jp_tags_data}
        assert {"始のいろは", "scp漢字ドリル", "t-arot"} <= set(by_name)
        assert by_name["テーマ"]["use_restricted"] is True
        assert by_name["テーマ"]["translation_exempt"] is False
        assert by_name["エッセイ"]["translation_exempt"] is True
        assert by_name["フラグメント"]["use_restricted"] is False


def test_int_crosswalk_parses_multibranch_vectors():
    source = Path(__file__).parent.parent / "sources" / "int" / "tag-guide.txt"
    mappings = int_parser.parse_raw(source)
    assert mappings["cn"]["认知危害"] == "認識災害"
    assert mappings["de"]["lebendig"] == "生命"
    assert mappings["int"]["cognitohazard"] == "認識災害"


def test_ko_crosswalk_parses_direct_jp_vectors():
    source = Path(__file__).parent.parent / "sources" / "ko" / "translate-tags.txt"
    mappings = ko_parser.parse_raw(source)
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
    mappings = ko_parser.parse(source, resolver.resolve)["ko"]

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
        CrosswalkResolver([
            {"name": "対象A", "source_tags": ["foo\u200b"]},
            {"name": "対象B", "source_tags": ["foo"]},
        ])


def test_en_resolution_prefers_declared_source_alias_over_coincident_jp_name():
    resolver = CrosswalkResolver([
        {"name": "semantic-target", "source_tags": ["collision"]},
        {"name": "collision", "source_tags": []},
    ])

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

    int_mappings = int_parser.parse_raw(int_source)
    ko_mappings = ko_parser.parse_raw(ko_source)

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
    mappings = int_parser.parse(source, resolver.resolve)

    assert mappings["ko"]["감정이입"] == "精神感応"
    assert mappings["int"]["resource"] == "世界観"


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
    for tag in ("作者頁面", "軍事", "宗教", "joicl", "en-8000", "麥地奇藝術學院", "int"):
        assert tag not in mappings["zh-tr"]

    assert sum(branch["accepted_tags"] for branch in stats.values()) >= 5000


def test_branch_guide_analysis_accepts_callable_and_reports_exact_audit(tmp_path):
    source = tmp_path / "ua.txt"
    source.write_text(
        "**foo** (a)\n"
        "**foo** (b)\n"
        "**bar** (unknown)\n"
        "**ok** (ok)\n",
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
