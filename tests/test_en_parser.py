from pathlib import Path

import pytest

from scripts.parsers import en_parser
from scripts.parsers.errors import SourceParseError

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
        apparent_tag_count = 0

        for line in _EN_SOURCE.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("* **[http"):
                continue
            apparent_tag_count += 1

        assert apparent_tag_count == len(en_tags_data)

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

    def test_strict_mode_reports_malformed_tag_records(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/ broken]**\n",
            encoding="utf-8",
        )
        diagnostics = []

        assert en_parser.parse_en_tags(source, strict=True, diagnostics=diagnostics) == []
        assert diagnostics == [
            f"{source}:1: malformed source record (invalid EN tag link)"
        ]
        with pytest.raises(SourceParseError, match="invalid EN tag link"):
            en_parser.parse_en_tags(source, strict=True)

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

    def test_en_colon_metadata_handles_quoted_values_with_and(self, tmp_path):
        source = tmp_path / "tag-list.txt"
        source.write_text(
            "* **[https://example.test/system:page-tags/tag/example example]** -- Description\n"
            "* //Requires: 'scp', and 'tale'//\n",
            encoding="utf-8",
        )

        assert en_parser.parse_en_tags(source)[0]["meta"] == {
            "requires": ["scp", "tale"]
        }

    def test_en_count_lower_bound(self, en_tags_data):
        assert len(en_tags_data) >= 800, (
            f"ENタグ件数が少なすぎます: {len(en_tags_data)}"
        )
