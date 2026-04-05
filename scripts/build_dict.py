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

    # JP → EN マッピングを構築（en_tag フィールドが設定されているJPタグのみ）
    jp_map: dict[str, str] = {}
    for entry in jp_tags:
        en_tag = entry.get("en_tag")
        if en_tag:
            jp_map[en_tag] = entry["name"]

    new_dict: dict[str, str | None] = {}

    for entry in en_tags:
        en_name: str = entry["name"]

        if en_name in jp_map:
            # JPタグに対応するENタグが存在する
            new_dict[en_name] = jp_map[en_name]
        elif en_name in deprecated_en_tags:
            # 非使用タグは既存値があってもnull（置換先はdeprecated辞書で管理）
            new_dict[en_name] = None
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
    if _DATA_DEPRECATED.exists():
        for entry in load_json(_DATA_DEPRECATED):
            if entry.get("en_tag"):
                deprecated_en_tags.add(entry["en_tag"])

    # --- 既存辞書の読み込み（手動追記を保護するため） ---
    existing: dict[str, str | None] = {}
    if not args.overwrite and _DICT_OUT.exists():
        existing = load_json(_DICT_OUT)

    sorted_dict = build(en_tags, jp_tags, existing, deprecated_en_tags)

    _DICT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(_DICT_OUT, "w", encoding="utf-8") as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

    mapped = sum(1 for v in sorted_dict.values() if v is not None)
    total = len(sorted_dict)
    print(f"辞書生成完了: {mapped}/{total} エントリがマッピング済み → {_DICT_OUT}")

    # 非使用タグの置換辞書を生成
    if _DATA_DEPRECATED.exists():
        deprecated_raw: list[dict] = load_json(_DATA_DEPRECATED)
        deprecated_dict = {
            entry["en_tag"]: entry["replacement"]
            for entry in deprecated_raw
            if entry.get("replacement")
        }
        _DICT_DEPRECATED.parent.mkdir(parents=True, exist_ok=True)
        with open(_DICT_DEPRECATED, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(deprecated_dict.items())), f, ensure_ascii=False, indent=2)
        print(f"非使用タグ置換辞書: {len(deprecated_dict)} エントリ → {_DICT_DEPRECATED}")


if __name__ == "__main__":
    main()
