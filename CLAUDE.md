# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このディレクトリについて

**SCP財団タグ翻訳ツール** - SCPタグを英語から日本語へ（将来的には多言語へ）翻訳するためのスタンドアロンツール。親プロジェクトの翻訳準備支援とは独立して動作します。

### 現在の状態 (2025-08-12)

- **マッピング率**: 81% (722/893タグ)
- **バリデーション**: ✅ クリティカルエラーなし、疑わしいマッピングなし
- **品質保証**: Linus Torvaldsエージェント承認済み

## 主な機能

1. **タグリスト取得** - Wikidotサイトから最新のタグリストを取得
2. **タグパース** - Wikidot形式のタグリストをJSON形式に変換
3. **タグ翻訳** - 英語タグを日本語タグへマッピング
4. **連結タグ対応** - `fireinscription`のような連結タグを最長一致で分割
5. **Webインターフェース** - HTMLベースの静的ツールとして提供

## プロジェクト構造

```
scpwiki_tag_translator/
├── pyproject.toml             # uvベースの依存関係管理
├── index.html                  # Webインターフェース（静的HTML）
├── dictionaries/
│   └── en_to_jp.json          # 英日タグ翻訳辞書（722/893タグマッピング済み）
├── generate_dictionary.py     # ⭐ Wikidot→JSON直接生成（メインスクリプト）
├── validate_mappings.py       # マッピングバリデーション
├── check_mapping_status.py    # マッピング状態レポート生成
├── fetch_jp_fragments.py      # JP断片ページ取得
├── retrieve_wikidot_page.py  # Wikidotページ取得スクリプト
├── parse_en_tags.py           # 旧タグリストパーサー（非推奨）
├── *.wikidot                  # Wikidotソースファイル群
└── mapping_status.tsv         # マッピング状態レポート
```

## よく使うコマンド

### 環境セットアップ（初回のみ）

```bash
# uvで依存関係をインストール
uv sync
```

### タグデータの更新（推奨ワークフロー）

```bash
# 1. Wikidotから最新のタグリストを取得
uv run python retrieve_wikidot_page.py
uv run python fetch_jp_fragments.py

# 2. 辞書を生成（Wikidot→JSON直接変換）
uv run python generate_dictionary.py

# 3. バリデーション実行
uv run python validate_mappings.py

# 4. マッピング状態レポート生成（オプション）
uv run python check_mapping_status.py
```

### Webツールの使用

```bash
# ローカルでWebサーバーを起動（Python 3）
python -m http.server 8000

# ブラウザで開く
open http://localhost:8000/index.html
```

## 重要なファイル説明

### `dictionaries/en_to_jp.json`

- SCPタグの英日対訳辞書
- 722/893タグ（81%）がマッピング済み
- `null`値はマッピングなし（JP側に対応タグが存在しない）

### `generate_dictionary.py` ⭐メインスクリプト

- WikidotソースファイルからJSON辞書を直接生成
- 中間ファイル不要（TSVやCSVを経由しない）
- 正規表現パターンでENとJPタグを抽出・マッピング
- 実行結果: マッピング率81%達成

### `validate_mappings.py`

- 生成された辞書の品質チェック
- クリティカルエラー検出（オブジェクトクラス、シリーズ番号など）
- 疑わしいマッピングの警告
- 自動修正機能付き

### `check_mapping_status.py`

- マッピング状態の詳細レポート生成
- TSV形式での出力（mapping_status.tsv）
- マップ済み/未マップ/JP専用タグの分類

### `retrieve_wikidot_page.py`

- WikidotからSCPタグリストを自動取得
- 対象ページ:
  - `scp-jp:tag-list` - 日本支部タグリスト
  - `05command:tech-hub-tag-list` - 技術ハブタグリスト
- wikidotライブラリを使用

### `index.html`

- 完全スタンドアロンのWebアプリケーション
- JavaScriptのみで動作（サーバーサイド処理不要）
- レスポンシブデザイン、ダークモード対応
- GitHub Pagesでのホスティング可能

## 開発上の注意点

1. **独立性を保つ** - 親プロジェクトの依存関係を使わない
2. **静的ファイルのみ** - サーバーサイド処理は追加しない
3. **辞書の更新** - 新タグは`dictionaries/en_to_jp.json`に追加
4. **型ヒント** - Python 3.12+の型エイリアス（TypeAlias）を使用
5. **uv環境** - すべてのPythonスクリプトは`uv run`経由で実行
6. **依存関係管理** - pyproject.tomlで管理（pip不使用）

## 辞書メンテナンス

### 新しいタグの追加

```json
{
  "new-tag": "新規タグ",
  "unused-tag": null
}
```

### タグの分類

- 通常タグ: 文字列で翻訳を定義
- 非使用タグ: `null`を設定
- 未定義タグ: 辞書に含めない

## マッピング率について

### なぜ81%で十分なのか

現在のマッピング率81%（722/893タグ）は実用上十分な水準です。未マップの171タグは主に：

1. **言語/GoIタグ（31個）** - `_cn`, `_de`など。これらは言語固有で翻訳不要
2. **EN専用タグ（140個）** - `action`, `adventure`など。JP側に対応概念がない

これらのタグは構造的にマッピング不可能であり、100%達成は現実的ではありません。

## トラブルシューティング

- **wikidotライブラリエラー**: `uv sync`を実行（pip不使用）
- **CORS エラー**: ローカルサーバー経由でindex.htmlを開く
- **タグが見つからない**: 辞書ファイルの更新を確認
- **Python環境エラー**: `uv sync`で環境を再構築

## 今後の拡張予定

- [ ] 多言語対応（jp→en、cn→enなど）
- [ ] タグの自動更新機能
- [ ] 非使用タグの自動検出
- [ ] タグ説明文の翻訳支援

## まとめ

このツールはSCPタグの翻訳に特化した独立ツールです。親プロジェクトの翻訳準備支援とは異なり、タグのメタデータ管理と翻訳マッピングに焦点を当てています。静的HTMLとして動作するため、どこでもホスティング可能です。
