# SCP Tag Translation Tool

SCP財団のタグを多言語翻訳するための静的ツールです。
既存のタグをスペース区切り・連結タグの両方で入力し、一括して翻訳結果を得られます。

## 特長

- JP以外のローカルコーパス支部タグから日本語(jp)タグへの翻訳に対応
- 連結タグ（例: `fireinscription`）を最長一致で分割して翻訳
- 未定義タグ、未対応タグ、非使用タグはログ表示
- ダークモード対応
- レスポンシブデザインにより、PC/モバイルどちらでも快適
- SCP Wiki 独自の「支部タグ」を翻訳結果に付加（例: 翻訳元が `pt-br` なら訳結果に `pt` タグを自動追加）

対応している翻訳元支部は、`cn`、`cs`、`de`、`el`、`en`、`es`、`fr`、`hu`、`id`、`it`、`ko`、`kz`、`pl`、`pt-br`、`th`、`tr`、`ua`、`vn`、`zh-tr`です。翻訳先はJPタグです。

## デモ

[GitHub Pages](https://scp-jp.github.io/scp-tag-translation/index.html)

## 使い方

1. リポジトリをクローン or ダウンロード
2. `index.html` と `dictionaries/` ディレクトリを同階層に配置
3. GitHub Pages などの静的ホスティング、またはローカルHTTPサーバー経由で `index.html` を開く
4. 翻訳元・翻訳先言語を選択（翻訳先はJP）
5. 翻訳したいタグを入力すると、自動で翻訳結果が表示されます
6. 「コピー」ボタンで出力をクリップボードにコピー可能

ローカルで確認する場合は、ブラウザの `file://` 制限により辞書JSONを読み込めないことがあります。次のように静的HTTPサーバーを起動してアクセスしてください。

```bash
python -m http.server 8000
```

その後、`http://localhost:8000/index.html` を開きます。

## ディレクトリ構造

```
scp-tag-translation/
├── index.html              # 静的翻訳ツール
├── dictionaries/
│   ├── en_to_jp.json              # EN→JP 翻訳辞書（スクリプトで自動生成）
│   └── deprecated_en_to_jp.json   # EN非使用タグの置換辞書
├── sources/                # Wikidot から取得した原典ページソース
│   ├── en/
│   │   └── tag-list.txt    # 05commandのENタグリスト
│   └── jp/
│       ├── fragment-basic.txt
│       ├── fragment-series.txt
│       ├── fragment-universe.txt
│       ├── fragment-event.txt
│       └── fragment-unused.txt
├── scripts/                # 辞書生成パイプライン
│   ├── parse_sources.py    # sources/ を解析して data/ に出力
│   ├── build_dict.py       # data/ から辞書を生成
│   ├── build_branch_dicts_from_corpus.py # corpusメタデータから支部別JP辞書を生成
│   └── parsers/
│       ├── en_parser.py
│       └── jp_parser.py
└── tests/                  # 翻訳整合性テスト
```

## 辞書の更新方法（開発者向け）

`sources/` のページソースを最新に差し替えた後、以下の順で実行します。

```bash
# 1. ソースを解析して data/ に出力
python scripts/parse_sources.py

# 2. data/ から辞書を生成（既存の手動追記を保護）
python scripts/build_dict.py

# 3. ローカルコーパスのメタデータから、JP以外の支部→JP辞書を生成
python scripts/build_branch_dicts_from_corpus.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus

# 4. 可視化用の支部タグカバレッジデータを生成
python scripts/build_branch_tag_coverage_data.py --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus

# 5. 単一HTMLのカバレッジ可視化を生成
python scripts/build_branch_tag_coverage_html.py

# 強制上書きする場合
python scripts/build_dict.py --overwrite
```

支部別辞書は `dictionaries/<source>_to_jp.json`、置換辞書は `dictionaries/deprecated_<source>_to_jp.json` に出力されます。`pt-br_to_jp.json` と `zh-tr_to_jp.json` のように、コーパス側の支部ディレクトリ名をそのままファイル名に使います。ただしJP側の支部タグはそれぞれ `pt`、`zh` に正規化されます。

`null` は、非使用タグ、単一の置換先がないタグ、またはまだJPタグへ対応付けていないコーパス由来タグを表します。置換辞書に単一置換先がある場合はUIが置換先を出力し、ない場合はログに「未対応または非使用タグ」と表示します。

可視化用データは `visualization/branch_tag_coverage.json` と `visualization/branch_tag_coverage.tsv` に出力されます。各支部の全タグについて、JPタグリスト側で登録タグ・別名・非使用タグとして扱われているか、ローカル上書きのみか、未収録かを分類します。

`visualization/branch_tag_coverage.html` は、上記JSONを埋め込んだ自己完結HTMLです。外部JSONの `fetch()` に依存しないため、ローカルでそのまま開けます。

## テスト

```bash
python -m pytest                                              # 全テスト
python -m pytest tests/test_translation_integrity.py -v      # 整合性テストのみ
```

テストは `sources/` から動的にパースするため、`data/` の事前生成は不要です。

## コントリビュート

Pull Request 大歓迎です。新タグ・新ペアを追加する際は、対応する JSON ファイルを `dictionaries/` に置いてください。

## ライセンス

### ソースコード

`index.html`・`scripts/`・`tests/` などのソースコードは [MIT ライセンス](LICENSE) の下で公開しています。

### ソースデータ（`sources/` 配下）

`sources/` 配下のファイルは各 Wikidot ページのページソースを保存したものであり、[Creative Commons Attribution-ShareAlike 3.0 License](https://creativecommons.org/licenses/by-sa/3.0/) が適用されます。

**`sources/en/tag-list.txt`**
- Title: Tech Hub Tag List
- Author: SCP Wiki
- Source: https://05command.wikidot.com/tech-hub-tag-list
- License: CC BY-SA 3.0 https://creativecommons.org/licenses/by-sa/3.0/legalcode.en

**`sources/jp/` 配下のフラグメントファイル**（fragment-basic.txt / fragment-series.txt / fragment-universe.txt / fragment-event.txt / fragment-unused.txt）
- Title: タグリスト
- Author: SCP財団
- Source: http://scp-jp.wikidot.com/tag-list
- License: CC BY-SA 3.0 https://creativecommons.org/licenses/by-sa/3.0/legalcode.en
