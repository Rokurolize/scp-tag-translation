# SCP Tag Translation Tool

SCP財団の各言語版で使われているタグを、SCP-JPで使用するタグへ変換する静的Webツールです。
スペース区切りのタグと、複数タグを連結した入力に対応します。

## 対応サイト

翻訳元は次の15サイトです。
翻訳先はSCP-JPです。

- `scp-wiki-cn`
- `scp-cs`
- `scp-wiki-de`
- `scp-wiki`
- `lafundacionscp`
- `fondationscp`
- `scp-int`
- `fondazionescp`
- `scpko`
- `scp-pl`
- `scp-pt-br`
- `scp-th`
- `scp-ukrainian`
- `scp-vn`
- `scp-zh-tr`

公開版は[GitHub Pages](https://rokurolize.github.io/scp-tag-translation/)で利用できます。

## 翻訳結果の区分

出力欄には、現在のSCP-JPタグリストと翻訳時の利用規則に照らしてコピー可能なタグだけを表示します。
翻訳元の支部タグもSCP-JPの表記へ正規化して追加します（`pt-br`は`pt`、`zh-tr`は`zh`）。

そのまま使えないタグは、理由とともにログへ表示します。

- **申請または確認が必要**：SCP-JPに対応タグがないため、`未訳-<翻訳元タグ>`として表示します。
- **SCP-JPでは付与しない**：非使用タグまたは翻訳時に省略するタグです。
- **スタッフ許可が必要**：使用制限があり、翻訳時の制限緩和がないタグです。
- **翻訳元タグ未確認**：現在のコーパスにない入力です。`未確認-<入力>`として表示します。
- **データ不整合**：変換先がSCP-JPポリシーにない場合です。安全のためコピー対象から除外します。

使用制限があっても翻訳時の制限緩和が明記されたタグは、注記をログへ残してコピー欄へ出力します。

## ローカルでの利用

ブラウザは`file://`からのJSON読み込みを制限することがあります。
リポジトリ直下でHTTPサーバーを起動してください。

```bash
python -m http.server 8000
```

その後、`http://localhost:8000/index.html`を開きます。

## 辞書の更新方法（開発者向け）

開発用スクリプトとテストにはPython 3.11以上が必要です。

ローカルコーパスのページソースをWikidotから更新する場合は、リポジトリの
`wikidot.py`フォークを通して公式ページソースを取得し、`AGENTS.md`の手順に従ってください。
取得した原典を確認した後、次のコマンドでソースと辞書を再生成します。

更新前に、リポジトリの`wikidot.py`フォークで公式ページソースを取得し、JPタグリストのマニフェストに列挙されたフラグメントだけを更新対象にしてください。`curl`や検索結果を原典として使わず、取得・同期・検証の詳細は`AGENTS.md`の「Updating Wikidot source snapshots」に従ってください。

```bash
python -m scripts.commands.parse_sources --lang all
python -m scripts.commands.build_branch_dicts_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
```

## データ生成

辞書は、ローカルコーパスに保存された公式タグガイドと全ページの`meta.json`から生成します。
ネットワーク経由でWikidotを取得する処理はありません。

生成パイプラインは`sources/`の公式ページソースを`data/`の中間JSONへ解析し、その結果とコーパスのメタデータから`dictionaries/`と`visualization/`を生成します。`data/`は再生成可能なローカル中間データであり、Gitにはコミットしません。

生成処理は次の根拠を順に適用します。

1. 現行のSCP-JPタグ名とタグリスト記載の翻訳元別名
2. SCP-JPの非使用タグと単一置換先
3. SCP-JPのFAQに基づく変換規則
4. SCP-INT、SCP-KO、各支部の公式対訳表
5. 対象支部ごとの査読済み上書き

公式対訳表の参照先が複数のSCP-JPタグへ分かれる行、または同じ翻訳元タグに未解決の参照が併記される行は採用しません。
対訳先は、現行のSCP-JPタグリストに登録されている名前へ正規化します。

```bash
# 1. コーパス内の公式ページソースとsources/の一致を確認
python -m scripts.commands.sync_tag_sources_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus

# 必要な場合だけ、コーパスからsources/へ同期
python -m scripts.commands.sync_tag_sources_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus \
  --write

# 2. タグリストと公式対訳表を解析
python -m scripts.commands.parse_sources

# 3. 15支部の全コーパスタグを含む辞書とSCP-JP利用ポリシーを生成
python -m scripts.commands.build_branch_dicts_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus

# 4. ブラウザ用の支部設定を生成
python -m scripts.commands.build_browser_config

# 5. 全メタデータのカバレッジと申請対象一覧を生成
python -m scripts.commands.build_branch_tag_coverage_data \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus

# 6. 自己完結型の可視化HTMLを生成
python -m scripts.commands.build_branch_tag_coverage_html
```

主な生成物は次のとおりです。

- `dictionaries/<branch>_to_jp.json`：支部別の変換辞書
- `dictionaries/deprecated_<branch>_to_jp.json`：非使用タグの単一置換先
- `dictionaries/jp_tag_policy.json`：SCP-JP登録タグの使用制限と翻訳時の扱い
- `branch_config.js`：ブラウザ用の対応支部設定
- `visualization/branch_tag_coverage.json`：全支部タグの分類結果
- `visualization/branch_tag_coverage.tsv`：カバレッジの表形式データ
- `visualization/tag_application_inventory.json`：申請または確認が必要なタグの一覧
- `visualization/tag_application_inventory.tsv`：申請対象一覧の表形式データ
- `visualization/branch_tag_coverage.html`：JSONを埋め込んだ自己完結型ダッシュボード

`null`は単なる変換失敗を意味しません。
UIは置換辞書とSCP-JP利用ポリシーを参照し、省略、スタッフ許可、申請または確認のいずれに当たるかを区別します。

`scripts/commands/build_dict.py`はコーパスを渡せない既存自動化向けの互換CLIです。正規の生成経路は`build_branch_dicts_from_corpus`だけであり、互換CLIも同じ`scripts/domain/tag_dictionary.py`へ委譲します。互換CLIの所有者はリポジトリメンテナで、外部自動化の参照を確認する作業を毎年1月の依存更新時に行います。引数なしの互換動作に依存する外部自動化がなくなった時点で、このCLIを削除します。複数成果物の公開は`scripts/infrastructure/atomic_output.py`が一括ステージングと失敗時のロールバックを担います。

## テスト

```bash
python -m pytest
pyright
```

テストは、公式ソースの解析、対訳表の曖昧行除外、15支部の辞書整合性、SCP-JP利用ポリシー、申請対象一覧、ブラウザ内の翻訳処理を検証します。
`pyright`は`scripts/`の型注釈を検査します。開発環境の依存関係は`requirements-dev.txt`からインストールしてください。
ブラウザ内の翻訳処理を検証するテストにはNode.jsが必要です。Python部分だけを意図的に実行する場合は`SCP_ALLOW_MISSING_NODE=1`を指定すると、Node.js依存テストが明示的にスキップされます。

Pythonモジュールの公開面は、コマンド入口では`main`、直接利用するライブラリでは`__all__`に列挙し、その他の実装ヘルパーはアンダースコアで始める規則です。新しい直接利用モジュールを追加するときは、公開関数・型・定数を`__all__`に明示してください。
実コーパスの連結タグ回帰は外部コーパスを必要とするため、GitHub Actionsの`Corpus regression` workflowを手動実行し、`scp-wiki-translation`のブランチ別Release assetを指定してください。ローカルでは`SCP_WIKI_CORPUS_ROOT=/path/to/corpus python -m pytest -m corpus_integration`を実行し、変数が未設定の通常実行では合成コーパスのスモークテストを維持します。

## ディレクトリ構成

```text
scp-tag-translation/
├── index.html
├── dictionaries/
├── data/                                  # Git管理外の中間JSON
├── sources/
│   ├── cn/ cs/ de/ en/ es/ fr/ int/ it/ ko/
│   ├── pl/ pt-br/ th/ ua/ vn/ zh-tr/
│   └── jp/
├── scripts/
│   ├── assets/                               # 生成HTMLのソーステンプレート
│   ├── commands/                             # 同期・解析・生成CLI
│   ├── application/                          # CLIから呼び出す生成・同期ワークフロー
│   │   └── source_parsing/                    # ソース解析のレコード・交差表・診断調整
│   ├── compatibility/                        # 外部自動化向けの旧互換ワークフロー
│   ├── contracts/                             # 層をまたぐ共有エラー
│   ├── domain/                               # スキーマ・検証・変換規則・支部設定
│   │   ├── policy/                            # ソースからJPへのマッピング規則
│   │   └── records/                           # 入力レコードと境界検証
│   ├── infrastructure/                       # パス・JSON・原子的な成果物公開
│   ├── pipeline/                             # コーパス走査・入力・ソース構成
│   ├── parsers/                              # 公式タグソース解析
├── tests/
└── visualization/
```

### パッケージの依存方向

パッケージ間の依存方向は、コマンド入口からアプリケーション、パイプライン、ドメイン、パーサー、インフラストラクチャへ一方向に保ちます。コマンドはドメイン・パーサー・パイプライン・インフラストラクチャを直接インポートせず、ドメインはアプリケーション・パイプライン・パーサーを参照しません。許可された依存関係は`tests/test_architecture_boundaries.py`で実行可能な契約として検証します。

## ライセンス

### ソースコード

`index.html`、`scripts/`、`tests/`などのソースコードは[MIT License](LICENSE)で公開しています。

### 公式タグガイドのページソース

`sources/`に保存したWikidotページソースには[Creative Commons Attribution-ShareAlike 3.0 License](https://creativecommons.org/licenses/by-sa/3.0/)が適用されます。
各ファイルは、次の公式ページをローカルコーパスから複製したものです。

| 保存先 | 公式ページ |
|---|---|
| `sources/jp/` | [タグガイド](https://scp-jp.wikidot.com/tag-guide)、[タグリスト](https://scp-jp.wikidot.com/tag-list)とそのincludeフラグメント |
| `sources/en/tag-guide.txt` | [Tech Hub Tag](https://05command.wikidot.com/tech-hub-tag) |
| `sources/en/tag-list.txt` | [Tech Hub Tag List](https://05command.wikidot.com/tech-hub-tag-list) |
| `sources/en/tag-list-manifest.txt` | [Tag List Manifest](https://05command.wikidot.com/tag-list-manifest) |
| `sources/int/tag-guide.txt` | [SCP-INT Tag Guide](https://scp-int.wikidot.com/tag-guide) |
| `sources/ko/translate-tags.txt` | [SCP-KO Translate Tags](https://scpko.wikidot.com/translate:tags) |
| `sources/cn/tag-guide.txt` | [SCP-CN标签指导](https://scp-wiki-cn.wikidot.com/tag-guide) |
| `sources/de/tag-guide.txt` | [SCP-DE Tag Guide](https://scp-wiki-de.wikidot.com/tag-guide) |
| `sources/es/tag-guide.txt` | [SCP-ES Guía de Etiquetas](https://lafundacionscp.wikidot.com/tag-guide) |
| `sources/fr/guide-des-tags.txt` | [SCP-FR Guide des Tags](https://fondationscp.wikidot.com/guide-des-tags) |
| `sources/it/tag-guide.txt` | [SCP-IT Tag Guide](https://fondazionescp.wikidot.com/tag-guide) |
| `sources/pl/tag-list.txt` | [SCP-PL Lista tagów](https://scp-pl.wikidot.com/tag-list) |
| `sources/pt-br/fragment-lista-mestra.txt` | [SCP-PT-BR Lista Mestra](https://scp-pt-br.wikidot.com/fragment:lista-mestra) |
| `sources/th/tag-list.txt` | [SCP-TH Tag List](https://scp-th.wikidot.com/tag-list) |
| `sources/ua/tag-guide.txt` | [SCP-UA Tag Guide](https://scp-ukrainian.wikidot.com/tag-guide) |
| `sources/vn/fragment-tag-guide-for-translator.txt` | [SCP-VN Tag Guide for Translator](https://scp-vn.wikidot.com/fragment:tag-guide-for-translator) |
| `sources/zh-tr/` | [SCP-ZH-TR Tag Guide](https://scp-zh-tr.wikidot.com/tag-guide)のincludeフラグメント |

各ページの著作者は、該当するSCP Wiki支部の履歴に記録された投稿者です。個別のページソースにはCC BY-SA 3.0が適用され、[ライセンス本文](https://creativecommons.org/licenses/by-sa/3.0/legalcode.en)で詳細を確認できます。
