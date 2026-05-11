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
python scripts/build_branch_dicts_from_corpus.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python scripts/build_branch_tag_coverage_data.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python scripts/build_branch_tag_coverage_html.py

# 個別言語のみ解析
python scripts/parse_sources.py --lang en
python scripts/parse_sources.py --lang jp
```

## アーキテクチャ概要

### データフロー（辞書生成パイプライン）

```
sources/en/tag-list.txt              →  en_parser.py   →  data/en_tags.json
sources/jp/fragment-*.txt            →  jp_parser.py   →  data/jp_tags.json
  (fragment-unused.txt を除く)
sources/jp/fragment-unused.txt       →  parse_unused() →  data/deprecated_tags.json
                                                                ↓
                                                        build_dict.py
                                                          ↙         ↘
                                     dictionaries/en_to_jp.json   dictionaries/deprecated_en_to_jp.json

/home/roku/src/Rokurolize/scp-wiki-translation/corpus/<branch>/pages/*/meta.json
sources/branch_to_jp_overrides.json
data/jp_tags.json
data/deprecated_tags.json
                                                                ↓
                                        build_branch_dicts_from_corpus.py
                                        build_branch_tag_coverage_data.py
                                                          ↙         ↘
                                     dictionaries/<branch>_to_jp.json
                                     dictionaries/deprecated_<branch>_to_jp.json
                                     visualization/branch_tag_coverage.json
                                     visualization/branch_tag_coverage.tsv
                                     visualization/branch_tag_coverage.html
```

`data/` は中間ファイルであり、gitignore 対象。テストは `sources/` から動的パースするため `data/` の事前生成は不要。

支部別JP辞書を更新する場合は、先に `python scripts/parse_sources.py` と `python scripts/build_dict.py` を実行し、その後で `python scripts/build_branch_dicts_from_corpus.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus` を実行する。コーパスは読み取り専用の入力として扱う。

支部タグカバレッジを可視化するデータは、`python scripts/build_branch_tag_coverage_data.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus` で `visualization/branch_tag_coverage.json` と `visualization/branch_tag_coverage.tsv` に出力する。`python scripts/build_branch_tag_coverage_html.py` は、そのJSONを埋め込んだ自己完結HTMLを `visualization/branch_tag_coverage.html` に出力する。

### フロントエンド（index.html）

単一ページの静的アプリ。`dictionaries/` フォルダの JSON を `fetch()` で遅延ロードしてメモリにキャッシュするため、GitHub Pages などの静的ホスティング、またはローカルHTTPサーバー経由で開く必要がある。連結タグ（例: `fireinscription`）は前方最長一致で分割して翻訳する。

翻訳元支部は `cn`、`cs`、`de`、`el`、`en`、`es`、`fr`、`hu`、`id`、`it`、`ko`、`kz`、`pl`、`pt-br`、`th`、`tr`、`ua`、`vn`、`zh-tr`。翻訳先はJP。`pt-br` はJP支部タグ `pt`、`zh-tr` はJP支部タグ `zh` に正規化する。

### 辞書フォーマット

**`dictionaries/en_to_jp.json`**

```json
{
  "en-tag-name": "jp対応タグ名",
  "unused-tag": null
}
```

- `null` = 非使用タグまたは未マッピング。`deprecated_en_to_jp.json` に置換先があれば UI 上で自動置換されログに通知される
- ファイル名は `{source}_to_{target}.json` で統一
- `build_dict.py` は既存ファイルとマージするため、手動追記した翻訳は上書きされない（`--overwrite` を使わない限り）
- `fragment-unused.txt` 由来の非使用タグは既存値があっても強制的に `null` になる

**`dictionaries/deprecated_en_to_jp.json`**

```json
{
  "unused-en-tag": "replacement-jp-tag"
}
```

- `fragment-unused.txt` の「JPでは//○○//タグに置換してください」記述から自動生成
- 単一置換先のみ対象（複数タグへの置換は含まない）
- UI はこのファイルを参照し、`null` タグに置換先があれば翻訳結果に含めて「置換されました」と表示する

**`dictionaries/<branch>_to_jp.json` / `dictionaries/deprecated_<branch>_to_jp.json`**

- `build_branch_dicts_from_corpus.py` がローカルコーパスの `meta.json` に出現するタグをキーとして生成する
- 非null値は必ず `sources/jp/fragment-*.txt` から解析できるJPタグ名
- `null` は非使用、単一置換先なし、または未対応のコーパス由来タグを表す
- 高頻度の支部ローカルタグは `sources/branch_to_jp_overrides.json` に根拠付きで追加する
- ファイル名はコーパス支部名を使うため、`pt-br_to_jp.json`、`zh-tr_to_jp.json` のようなハイフン付き名も正規の辞書名

**`visualization/branch_tag_coverage.json` / `visualization/branch_tag_coverage.tsv`**

- 支部ごとに、コーパスメタデータに存在する全タグ集合を出力する
- `jp_tag_name`: タグ文字列そのものがJPタグ名として登録済み
- `jp_tag_alias`: JPタグリスト上の `//(source-tag)//` 表記として扱われている
- `jp_unused_replacement`: JP非使用タグリスト上で単一置換先がある
- `jp_unused_no_single_replacement`: JP非使用タグリスト上で扱われているが、単一置換先はない
- `curated_override_only`: JPタグリストには未収録だが、ローカル上書きで翻訳機は扱う
- `unhandled`: JPタグリストにもローカル上書きにも未収録

**`visualization/branch_tag_coverage.html`**

- `branch_tag_coverage.json` をHTML内へ埋め込む単一ファイルのダッシュボード
- 外部JSONやCDNに依存しないため、`file://` でそのまま開ける
- 支部別の積み上げ分布、分類フィルター、検索、詳細テーブル、絞り込みTSV出力を提供する

### パーサー仕様

**EN パーサー** (`scripts/parsers/en_parser.py`): Wikidot形式のタグリストを解析。`* **[url tag]** -- description` 形式の行を認識する。

**JP パーサー** (`scripts/parsers/jp_parser.py`): `sources/jp/fragment-*.txt` のうち `fragment-unused.txt` を除くファイルを処理。`**[[[/system:page-tags/tag/{slug}|{display}]]]** //(en-tag)//` 形式を解析。ENタグ対応がある場合は `en_tag` フィールドに格納、JP固有タグは `en_tag: null`。

`parse_unused()` 関数が `fragment-unused.txt` を別途解析し、支部見出し（`+++ EN` など）・元タグ・単一置換先（「JPでは//○○//タグに置換してください」「//○○//タグに置換してください」など）を `data/deprecated_tags.json` に出力する。`build_dict.py` は en→jp 辞書生成時に `source_lang: "EN"` の非使用タグだけを適用する。支部別辞書生成では各支部の `source_lang` に一致する非使用タグと置換先を使う。

### テスト

`tests/conftest.py` がセッションスコープのフィクスチャとして en_tags, jp_tags, committed_dict（現在のJSONファイル）を提供する。整合性テスト（`test_translation_integrity.py`）は辞書と sources/ の双方向整合性を検証する。

## 今後の拡張

他言語ペアを追加する際は：
1. `sources/` に対象言語のソースを追加
2. 対応パーサーを `scripts/parsers/` に実装
3. `dictionaries/{src}_to_{dst}.json` を生成
4. 非使用タグがあれば `dictionaries/deprecated_{src}_to_{dst}.json` も生成
5. `index.html` のドロップダウンのコメントアウトを外す

JP向けの支部辞書を拡充する場合は、対象タグを `sources/branch_to_jp_overrides.json` に追加し、生成コマンドと `python -m pytest` を実行する。直接辞書JSONだけを手で直すと次回生成で上書きされる。
