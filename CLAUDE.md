# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## コマンド

```bash
# テスト
python -m pytest                                          # 全テスト
python -m pytest tests/test_translation_integrity.py -v  # 整合性テストのみ
python -m pytest tests/test_parsers.py -v                 # パーサーテストのみ

# 辞書の更新（sources/ を更新した後）
python scripts/parse_sources.py          # sources/ → data/ (中間JSON)
python scripts/build_dict.py             # data/ → dictionaries/en_to_jp.json
python scripts/build_dict.py --overwrite # 手動追記を無視して強制上書き

# 個別言語のみ解析
python scripts/parse_sources.py --lang en
python scripts/parse_sources.py --lang jp
```

## アーキテクチャ概要

### データフロー（辞書生成パイプライン）

```
sources/en/tag-list.txt        →  en_parser.py  →  data/en_tags.json
sources/jp/fragment-*.txt      →  jp_parser.py  →  data/jp_tags.json
                                                        ↓
                                              build_dict.py
                                                        ↓
                                         dictionaries/en_to_jp.json
```

`data/` は中間ファイルであり、gitignore 対象。テストは `sources/` から動的パースするため `data/` の事前生成は不要。

### フロントエンド（index.html）

サーバー不要の単一ページ静的アプリ。`dictionaries/` フォルダの JSON を `fetch()` で遅延ロードしてメモリにキャッシュする。連結タグ（例: `fireinscription`）は前方最長一致で分割して翻訳する。

### 辞書フォーマット（`dictionaries/en_to_jp.json`）

```json
{
  "en-tag-name": "jp対応タグ名",
  "unused-tag": null
}
```

- `null` = 非使用タグ（翻訳結果には含まれず、ログ表示される）
- ファイル名は `{source}_to_{target}.json` で統一
- `build_dict.py` は既存ファイルとマージするため、手動追記した翻訳は上書きされない（`--overwrite` を使わない限り）

### パーサー仕様

**EN パーサー** (`scripts/parsers/en_parser.py`): Wikidot形式のタグリストを解析。`* **[url tag]** -- description` 形式の行を認識する。

**JP パーサー** (`scripts/parsers/jp_parser.py`): `sources/jp/fragment-*.txt` を全て処理。`**[[[/system:page-tags/tag/{slug}|{display}]]]** //(en-tag)//` 形式を解析。ENタグ対応がある場合は `en_tag` フィールドに格納、JP固有タグは `en_tag: null`。

### テスト

`tests/conftest.py` がセッションスコープのフィクスチャとして en_tags, jp_tags, committed_dict（現在のJSONファイル）を提供する。整合性テスト（`test_translation_integrity.py`）は辞書と sources/ の双方向整合性を検証する。

## 今後の拡張

他言語ペアを追加する際は：
1. `sources/` に対象言語のソースを追加
2. 対応パーサーを `scripts/parsers/` に実装
3. `dictionaries/{src}_to_{dst}.json` を生成
4. `index.html` のドロップダウンのコメントアウトを外す
