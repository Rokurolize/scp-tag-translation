"""翻訳整合性テスト — dictionaries/en_to_jp.json と sources/ の整合性を検証する"""
from collections import defaultdict
import json
from pathlib import Path

from scripts.build_dict import EN_ORIGIN_TAG_REPLACEMENTS
from scripts.parsers.int_parser import parse_raw as parse_int_crosswalk


ROOT = Path(__file__).parent.parent


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


def test_jp_source_tags_are_consistent_with_dict(
    jp_tags_data,
    en_tag_names,
    committed_dict,
):
    """JP tag source aliases present in EN resolve to their JP record."""
    failures = []
    for entry in jp_tags_data:
        for source_tag in entry["source_tags"]:
            if source_tag not in en_tag_names:
                continue
            if source_tag not in committed_dict:
                failures.append(
                    f"'{entry['name']}'.source_tags contains missing {source_tag!r}"
                )
            elif committed_dict[source_tag] != entry["name"]:
                failures.append(
                    f"dict['{source_tag}']={committed_dict[source_tag]!r} "
                    f"≠ '{entry['name']}'"
                )
    assert not failures, "\n".join(failures)


def test_bidirectional_consistency(committed_dict, jp_tags_data, en_tag_names):
    """EN辞書の値にJPリスト・FAQ・公式対応表の根拠がある。"""
    jp_pairs = {
        (source_tag, j["name"])
        for j in jp_tags_data
        for source_tag in j["source_tags"]
        if source_tag in en_tag_names
    }
    jp_names = {j["name"] for j in jp_tags_data}
    jp_pairs.update((name, name) for name in jp_names & en_tag_names)

    raw_overrides = json.loads(
        (ROOT / "sources" / "branch_to_jp_overrides.json").read_text(
            encoding="utf-8"
        )
    )
    for branch in ("*", "en"):
        for source_tag, value in raw_overrides.get(branch, {}).items():
            target = value["jp_tag"] if isinstance(value, dict) else value
            jp_pairs.add((source_tag, target))

    official = parse_int_crosswalk(ROOT / "sources" / "int" / "tag-guide.txt")
    jp_pairs.update(official.get("en", {}).items())
    failures = [
        f"dict['{en}']={jp!r} but JP source_tags has no ({en!r}, {jp!r}) pair"
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


def test_duplicate_jp_targets_are_documented_aliases(committed_dict, jp_tags_data):
    """同一JPタグへ収束するENタグはJPリスト記載の別名に限る。"""
    reverse = defaultdict(list)
    for en, jp in committed_dict.items():
        if jp is not None:
            reverse[jp].append(en)
    documented = {
        entry["name"]: set(entry.get("source_tags") or [])
        for entry in jp_tags_data
    }
    failures = {
        jp: ens
        for jp, ens in reverse.items()
        if len(ens) > 1 and not set(ens) <= documented.get(jp, set())
    }
    assert not failures, f"Undocumented duplicate JP target mappings: {failures}"


def test_deprecated_replacement_dict_matches_sources(
    deprecated_tags_data,
    committed_dict,
    committed_deprecated_dict,
):
    """deprecated_en_to_jp.json が fragment-unused.txt の単一置換先と一致する"""
    expected = {
        entry["source_tag"]: entry["replacement"]
        for entry in deprecated_tags_data
        if (entry.get("source_lang") or "EN") == "EN" and entry.get("replacement")
    }
    expected.update(
        {
            source_tag: replacement
            for source_tag, replacement in EN_ORIGIN_TAG_REPLACEMENTS.items()
            if source_tag in committed_dict
        }
    )
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
        source_tag = entry["source_tag"]
        if (
            (entry.get("source_lang") or "EN") != "EN"
            or source_tag not in en_tag_names
        ):
            continue
        if committed_dict.get(source_tag) is not None:
            failures.append(
                f"dict['{source_tag}'] must be null because it is deprecated"
            )
    assert not failures, "\n".join(failures)
