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


def test_dict_values_do_not_have_surrounding_whitespace(committed_dict):
    failures = [
        f"{en} -> {jp!r}"
        for en, jp in committed_dict.items()
        if isinstance(jp, str) and jp != jp.strip()
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


def test_no_case_variant_duplicates_for_source_tags(en_tag_names, committed_dict):
    """ENソースタグの大小文字違いだけの別キーを辞書に残さない"""
    lower_to_source = {name.lower(): name for name in en_tag_names}
    failures = [
        f"{key} duplicates source tag {lower_to_source[key.lower()]}"
        for key in committed_dict
        if key not in en_tag_names
        and key.lower() in lower_to_source
        and key != lower_to_source[key.lower()]
    ]
    assert not failures, "\n".join(failures)


def test_no_duplicate_jp_names_in_dict(committed_dict):
    """複数のENタグが同一JPタグ名にマッピングされていない"""
    reverse = defaultdict(list)
    for en, jp in committed_dict.items():
        if jp is not None:
            reverse[jp].append(en)
    dups = {jp: ens for jp, ens in reverse.items() if len(ens) > 1}
    assert not dups, f"Duplicate JP name mappings: {dups}"


def test_deprecated_replacement_dict_matches_sources(
    deprecated_tags_data,
    committed_deprecated_dict,
):
    """deprecated_en_to_jp.json が fragment-unused.txt の単一置換先と一致する"""
    expected = {
        entry["en_tag"]: entry["replacement"]
        for entry in deprecated_tags_data
        if (entry.get("source_lang") or "EN") == "EN" and entry.get("replacement")
    }
    assert committed_deprecated_dict == expected


def test_deprecated_replacements_are_valid_and_null_in_main_dict(
    committed_dict,
    committed_deprecated_dict,
    jp_tags_data,
):
    """置換元はメイン辞書ではnull、置換先は有効なJPタグである"""
    jp_names = {j["name"] for j in jp_tags_data}
    failures = []
    for en, jp in committed_deprecated_dict.items():
        if committed_dict.get(en) is not None:
            failures.append(f"dict['{en}'] must be null before replacement")
        if jp not in jp_names:
            failures.append(f"replacement '{jp}' for '{en}' is not in jp_tags")
    assert not failures, "\n".join(failures)


def test_en_source_deprecated_official_tags_are_null(
    deprecated_tags_data,
    en_tag_names,
    committed_dict,
):
    """EN節の非使用公式タグはメイン辞書で翻訳値を持たない"""
    failures = []
    for entry in deprecated_tags_data:
        en_tag = entry["en_tag"]
        if (entry.get("source_lang") or "EN") != "EN" or en_tag not in en_tag_names:
            continue
        if committed_dict.get(en_tag) is not None:
            failures.append(f"dict['{en_tag}'] must be null because it is deprecated")
    assert not failures, "\n".join(failures)
