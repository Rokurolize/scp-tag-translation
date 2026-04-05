# SCP Tag Translation Tool

SCP財団のタグを多言語翻訳するための静的ツールです。
既存のタグをスペース区切り・連結タグの両方で入力し、一括して翻訳結果を得られます。

## 特長

- 英語(en)・日本語(jp)など複数の SCP 支部タグに対応（現在は en → jp のみ実装中）
- 連結タグ（例: `fireinscription`）を最長一致で分割して翻訳
- 未定義タグや非使用タグはログ表示
- ダークモード対応
- レスポンシブデザインにより、PC/モバイルどちらでも快適
- SCP Wiki 独自の「支部タグ」を翻訳結果に付加（例: 翻訳元が en なら訳結果に `en` タグを自動追加）

## デモ

[GitHub Pages](https://scp-jp.github.io/scp-tag-translation/index.html)

## 使い方

1. リポジトリをクローン or ダウンロード
2. `index.html` と `dictionaries/` ディレクトリを同階層に配置
3. ブラウザで `index.html` を開く
4. 翻訳元・翻訳先言語を選択（現在は en→jp のみ）
5. 翻訳したいタグを入力すると、自動で翻訳結果が表示されます
6. 「コピー」ボタンで出力をクリップボードにコピー可能

## ディレクトリ構造

```
scp-tag-translation/
├── index.html              # ブラウザで開く翻訳ツール
├── dictionaries/
│   └── en_to_jp.json       # EN→JP 翻訳辞書（スクリプトで自動生成）
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

# 強制上書きする場合
python scripts/build_dict.py --overwrite
```

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
