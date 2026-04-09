"""ENパーサー・JPパーサーの単体テスト"""
from pathlib import Path

from parsers.en_parser import tag_pattern as _EN_TAG_PATTERN
from parsers.jp_parser import _PAIR_RE as _JP_PAIR_RE

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

    def test_jp_known_tags_exist(self, jp_tags_data):
        jp_names = {e["name"] for e in jp_tags_data}
        for tag in ("scp", "補足", "ハブ"):
            assert tag in jp_names, f"既知タグ '{tag}' が見つかりません"

    def test_jp_count_lower_bound(self, jp_tags_data):
        assert len(jp_tags_data) >= 1500, f"JPタグ件数が少なすぎます: {len(jp_tags_data)}"

    def test_jp_names_and_en_tags_are_trimmed(self, jp_tags_data):
        for entry in jp_tags_data:
            assert entry["name"] == entry["name"].strip(), (
                f"nameに前後空白が含まれています: {entry}"
            )
            en_tag = entry.get("en_tag")
            if en_tag is not None:
                assert en_tag == en_tag.strip(), (
                    f"en_tagに前後空白が含まれています: {entry}"
                )

    def test_jp_exhaustive_coverage(self, jp_tags_data):
        """ソース中でスラッグ非空のタグ行（重複除去後）が全てパース結果に含まれること。
        fragment-unused.txt は parse_unused() で別途処理するため除外する。"""
        source_slugs: set[str] = set()
        for fp in sorted(_JP_SOURCE_DIR.glob("fragment-*.txt")):
            if fp.name == "fragment-unused.txt":
                continue
            for line in fp.read_text(encoding="utf-8").splitlines():
                if "**[[[/system:page-tags/tag/" not in line:
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
