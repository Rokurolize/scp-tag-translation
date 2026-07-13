from pathlib import Path

from scripts.parsers import en_parser
from scripts.parsers.en_parser import _parse_meta_line as _EN_PARSE_META_LINE
from scripts.parsers.en_parser import _TAG_PATTERN as _EN_TAG_PATTERN

_EN_SOURCE = Path(__file__).parent.parent / "sources" / "en" / "tag-list.txt"


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

        parsed = en_parser.parse_en_tags(source)

        assert parsed[0]["name"] == "amoni-ram"

    def test_en_description_starts_after_link_even_with_double_hyphen(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/foo--bar "
            "foo--bar]** -- Real description\n",
            encoding="utf-8",
        )

        parsed = en_parser.parse_en_tags(source)

        assert parsed[0]["name"] == "foo--bar"
        assert parsed[0]["description"] == "Real description"

    def test_en_tag_outside_tab_has_none_category(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/standalone "
            "standalone]** -- Description\n",
            encoding="utf-8",
        )

        assert en_parser.parse_en_tags(source) == [
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
        assert len(en_tags_data) >= 800, (
            f"ENタグ件数が少なすぎます: {len(en_tags_data)}"
        )

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
