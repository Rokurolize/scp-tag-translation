"""翻訳整合性テスト — dictionaries/en_to_jp.json と sources/ の整合性を検証する"""
from collections import defaultdict


def test_en_to_jp_values_are_valid_jp_names(committed_dict, jp_tags_data):
    """辞書の非nullエントリが jp_tags の name として実在する"""
    jp_names = {j["name"] for j in jp_tags_data}
    failures = [
        f"{en} -> '{jp}' (not in jp_tags)"
        for en, jp in committed_dict.items()
        if jp is not None and jp not in jp_names
    ]
    assert not failures, "\n".join(failures)


def test_jp_en_tag_consistent_with_dict(jp_tags_data, en_tag_names, committed_dict):
    """jp_tags[name=Y, en_tag=X] かつ X がENリストに存在するとき dict[X] == Y"""
    failures = []
    for j in jp_tags_data:
        en_tag, jp_name = j.get("en_tag"), j["name"]
        if not en_tag or en_tag not in en_tag_names:
            continue  # JP固有タグはスキップ
        if en_tag not in committed_dict:
            failures.append(f"'{jp_name}'.en_tag='{en_tag}' missing from dict")
        elif committed_dict[en_tag] != jp_name:
            failures.append(
                f"dict['{en_tag}']={committed_dict[en_tag]!r} ≠ '{jp_name}'"
            )
    assert not failures, "\n".join(failures)


def test_bidirectional_consistency(committed_dict, jp_tags_data, en_tag_names):
    """dict[en]=jp のとき jp_tags に (en_tag=en, name=jp) のペアが存在する"""
    jp_pairs = {
        (j["en_tag"], j["name"])
        for j in jp_tags_data
        if j.get("en_tag") and j["en_tag"] in en_tag_names
    }
    failures = [
        f"dict['{en}']={jp!r} but jp_tags has no entry with en_tag='{en}', name='{jp}'"
        for en, jp in committed_dict.items()
        if jp is not None and en in en_tag_names and (en, jp) not in jp_pairs
    ]
    assert not failures, "\n".join(failures)


def test_all_en_tags_present_in_dict(en_tags_data, committed_dict):
    """en_tags_data の全タグが committed_dict に存在する（辞書が古くない）"""
    missing = [e["name"] for e in en_tags_data if e["name"] not in committed_dict]
    assert not missing, f"辞書に存在しないENタグ: {missing}"


def test_no_duplicate_jp_names_in_dict(committed_dict):
    """複数のENタグが同一JPタグ名にマッピングされていない"""
    reverse = defaultdict(list)
    for en, jp in committed_dict.items():
        if jp is not None:
            reverse[jp].append(en)
    dups = {jp: ens for jp, ens in reverse.items() if len(ens) > 1}
    assert not dups, f"Duplicate JP name mappings: {dups}"
