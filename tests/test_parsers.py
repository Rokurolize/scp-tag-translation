"""ENパーサー・JPパーサーの単体テスト"""


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
