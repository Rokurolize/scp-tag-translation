"""
build_dict.py - data/ の解析済みタグ情報から辞書ファイルを生成する

使い方:
  python scripts/build_dict.py [--overwrite]

動作:
  1. data/jp_tags.json の en_tag が設定されているエントリを {en_tag: jp_name} にマッピング
  2. data/en_tags.json のうちマッピングが存在しないものを {en_name: null} として追加
  3. 既存の dictionaries/en_to_jp.json があればマージして手動追記を保護

オプション:
  --overwrite  既存の辞書を無視して強制上書き
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_DATA_EN = _ROOT / "data" / "en_tags.json"
_DATA_JP = _ROOT / "data" / "jp_tags.json"
_DATA_DEPRECATED = _ROOT / "data" / "deprecated_tags.json"
_DICT_OUT = _ROOT / "dictionaries" / "en_to_jp.json"
_DICT_DEPRECATED = _ROOT / "dictionaries" / "deprecated_en_to_jp.json"


def load_json(path: Path) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_deprecated_for_en_source(entry: dict) -> bool:
    source_lang = entry.get("source_lang") or "EN"
    return source_lang == "EN" and bool(entry.get("en_tag"))


def _ensure_unique(values, label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    if duplicates:
        sample = ", ".join(sorted(duplicates)[:10])
        raise ValueError(f"{label} が重複しています: {sample}")


def _ensure_no_case_variant_keys(existing_keys, source_keys, label: str) -> None:
    lower_to_source = {key.lower(): key for key in source_keys}
    collisions = []
    for key in existing_keys:
        source_key = lower_to_source.get(key.lower())
        if source_key is not None and key != source_key:
            collisions.append(f"{key} -> {source_key}")

    if collisions:
        sample = ", ".join(sorted(collisions)[:10])
        raise ValueError(f"{label} に大小文字違いの重複があります: {sample}")


def validate_build_inputs(
    en_tags: list[dict],
    jp_tags: list[dict],
    deprecated_raw: list[dict] | None = None,
) -> None:
    if not isinstance(en_tags, list):
        raise ValueError("ENタグデータは配列である必要があります")
    if not isinstance(jp_tags, list):
        raise ValueError("JPタグデータは配列である必要があります")
    if deprecated_raw is not None and not isinstance(deprecated_raw, list):
        raise ValueError("非使用タグデータは配列である必要があります")
    for index, entry in enumerate(en_tags):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"ENタグデータの項目が不正です: index={index}")
        if not entry["name"] or entry["name"] != entry["name"].strip():
            raise ValueError(f"ENタグ名が不正です: {entry['name']!r}")
    for index, entry in enumerate(jp_tags):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError(f"JPタグデータの項目が不正です: index={index}")
        if not entry["name"] or entry["name"] != entry["name"].strip():
            raise ValueError(f"JPタグ名が不正です: {entry['name']!r}")
        en_tag = entry.get("en_tag")
        if en_tag is not None and (
            not isinstance(en_tag, str) or not en_tag or en_tag != en_tag.strip()
        ):
            raise ValueError(f"JP側en_tagが不正です: {en_tag!r}")
    if deprecated_raw is not None:
        for index, entry in enumerate(deprecated_raw):
            if not isinstance(entry, dict):
                raise ValueError(f"非使用タグデータの項目が不正です: index={index}")
            en_tag = entry.get("en_tag")
            if en_tag is not None and (
                not isinstance(en_tag, str) or not en_tag or en_tag != en_tag.strip()
            ):
                raise ValueError(f"非使用タグのen_tagが不正です: {en_tag!r}")
            source_lang = entry.get("source_lang")
            if source_lang is not None and (
                not isinstance(source_lang, str)
                or not source_lang
                or source_lang != source_lang.strip()
            ):
                raise ValueError(f"非使用タグのsource_langが不正です: {source_lang!r}")
            replacement = entry.get("replacement")
            if replacement is not None and (
                not isinstance(replacement, str)
                or not replacement
                or replacement != replacement.strip()
            ):
                raise ValueError(f"非使用タグのreplacementが不正です: {replacement!r}")

    _ensure_unique((entry["name"] for entry in en_tags), "ENタグ名")
    _ensure_unique(
        (entry["en_tag"] for entry in jp_tags if entry.get("en_tag")),
        "JP側en_tag",
    )
    if deprecated_raw is not None:
        _ensure_unique(
            (
                entry["en_tag"]
                for entry in deprecated_raw
                if is_deprecated_for_en_source(entry)
            ),
            "EN非使用タグ",
        )


def validate_existing_dict(existing: dict[str, str | None]) -> None:
    if not isinstance(existing, dict):
        raise ValueError("既存辞書はオブジェクトである必要があります")
    for en_name, jp_name in existing.items():
        if not isinstance(en_name, str) or not en_name or en_name != en_name.strip():
            raise ValueError(f"既存辞書のキーが不正です: {en_name!r}")
        if jp_name is not None and (
            not isinstance(jp_name, str) or not jp_name or jp_name != jp_name.strip()
        ):
            raise ValueError(f"既存辞書の値が不正です: {en_name!r} -> {jp_name!r}")


def build(
    en_tags: list[dict],
    jp_tags: list[dict],
    existing: dict[str, str | None] | None = None,
    deprecated_en_tags: set[str] | None = None,
) -> dict[str, str | None]:
    """
    ENタグリストとJPタグリストから辞書を構築する。

    Args:
        en_tags: ENタグのリスト（各エントリに "name" キーを持つ）
        jp_tags: JPタグのリスト（各エントリに "name", "en_tag" キーを持つ）
        existing: 既存辞書（手動追記を保護するため）
        deprecated_en_tags: 非使用ENタグのセット（これらは既存値があってもnullにする）

    Returns:
        ソート済みの {en_name: jp_name | None} 辞書
    """
    if existing is None:
        existing = {}
    if deprecated_en_tags is None:
        deprecated_en_tags = set()
    validate_build_inputs(en_tags, jp_tags)
    validate_existing_dict(existing)
    _ensure_no_case_variant_keys(
        existing.keys(),
        (entry["name"] for entry in en_tags),
        "既存辞書キー",
    )

    # JP → EN マッピングを構築（en_tag フィールドが設定されているJPタグのみ）
    jp_map: dict[str, str] = {}
    for entry in jp_tags:
        en_tag = entry.get("en_tag")
        if en_tag:
            jp_map[en_tag] = entry["name"]

    new_dict: dict[str, str | None] = {}

    for entry in en_tags:
        en_name: str = entry["name"]

        if en_name in deprecated_en_tags:
            # 非使用タグは既存値やJP対応があってもnull（置換先はdeprecated辞書で管理）
            new_dict[en_name] = None
        elif en_name in jp_map:
            # JPタグに対応するENタグが存在する
            new_dict[en_name] = jp_map[en_name]
        elif en_name in existing and existing[en_name] is not None:
            # 既存辞書に手動追記がある場合はそれを保護
            new_dict[en_name] = existing[en_name]
        else:
            # 未マッピング
            new_dict[en_name] = None

    # 既存辞書にあってENタグリストにないエントリも保持（手動追記の保護）
    # ただし非使用タグは保護しない（nullで上書き）
    for en_name, jp_name in existing.items():
        if en_name not in new_dict:
            new_dict[en_name] = None if en_name in deprecated_en_tags else jp_name

    return dict(sorted(new_dict.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="data/ から辞書ファイルを生成する")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存の辞書を無視して強制上書きする",
    )
    args = parser.parse_args()

    # --- 入力ファイルの確認 ---
    for path in (_DATA_EN, _DATA_JP):
        if not path.exists():
            print(f"エラー: {path} が見つかりません。先に parse_sources.py を実行してください。")
            sys.exit(1)

    en_tags: list[dict] = load_json(_DATA_EN)
    jp_tags: list[dict] = load_json(_DATA_JP)

    # --- 非使用タグセットの読み込み ---
    deprecated_en_tags: set[str] = set()
    deprecated_raw: list[dict] = []
    if _DATA_DEPRECATED.exists():
        deprecated_raw = load_json(_DATA_DEPRECATED)
    try:
        validate_build_inputs(en_tags, jp_tags, deprecated_raw)
    except ValueError as err:
        print(f"エラー: {err}")
        sys.exit(1)

    for entry in deprecated_raw:
        if is_deprecated_for_en_source(entry):
            deprecated_en_tags.add(entry["en_tag"])

    # --- 既存辞書の読み込み（手動追記を保護するため） ---
    existing: dict[str, str | None] = {}
    if not args.overwrite and _DICT_OUT.exists():
        existing = load_json(_DICT_OUT)
        try:
            validate_existing_dict(existing)
        except ValueError as err:
            print(f"エラー: {err}")
            sys.exit(1)

    try:
        sorted_dict = build(en_tags, jp_tags, existing, deprecated_en_tags)
    except ValueError as err:
        print(f"エラー: {err}")
        sys.exit(1)

    _DICT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(_DICT_OUT, "w", encoding="utf-8") as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

    mapped = sum(1 for v in sorted_dict.values() if v is not None)
    total = len(sorted_dict)
    print(f"辞書生成完了: {mapped}/{total} エントリがマッピング済み → {_DICT_OUT}")

    # 非使用タグの置換辞書を生成
    deprecated_dict = {
        entry["en_tag"]: entry["replacement"]
        for entry in deprecated_raw
        if is_deprecated_for_en_source(entry) and entry.get("replacement")
    }
    _DICT_DEPRECATED.parent.mkdir(parents=True, exist_ok=True)
    with open(_DICT_DEPRECATED, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(deprecated_dict.items())), f, ensure_ascii=False, indent=2)
    print(f"非使用タグ置換辞書: {len(deprecated_dict)} エントリ → {_DICT_DEPRECATED}")


if __name__ == "__main__":
    main()
