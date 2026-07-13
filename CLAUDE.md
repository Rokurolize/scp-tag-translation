# CLAUDE.md

このファイルは、このリポジトリを扱うコーディングエージェント向けの開発メモです。
利用者向けの説明とライセンス帰属は`README.md`を参照してください。

## 検証コマンド

```bash
python -m scripts.commands.sync_tag_sources_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python -m scripts.commands.parse_sources
python -m scripts.commands.build_branch_dicts_from_corpus \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python -m scripts.commands.build_browser_config
python -m scripts.commands.build_branch_tag_coverage_data \
  --corpus-root /home/roku/src/Rokurolize/scp-wiki-translation/corpus
python -m scripts.commands.build_branch_tag_coverage_html
python -m pytest
```

`sources/`を更新する場合だけ、同期コマンドへ`--write`を追加します。
コーパスは読み取り専用の入力として扱います。

## 対応支部

翻訳元は`cn`、`cs`、`de`、`en`、`es`、`fr`、`int`、`it`、`ko`、`pl`、`pt-br`、`th`、`ua`、`vn`、`zh-tr`です。
翻訳先はSCP-JPです。
支部コード、Wikidotサイト名、SCP-JP支部タグの正本は`scripts/domain/branch_config.py`です。

## 生成パイプライン

`scripts/commands/parse_sources.py`は次の中間JSONを`data/`へ生成します。
`data/`はGit管理の対象外です。

- `en_tags.json`：ENの現行タグ
- `jp_tags.json`：JPの現行タグ、翻訳元別名、利用制限
- `deprecated_tags.json`：JPの非使用タグと単一置換先
- `int_tag_crosswalk.json`：SCP-INTの公式対訳表
- `ko_tag_crosswalk.json`：SCP-KOの公式対訳表
- `branch_guide_crosswalk.json`：各支部の公式タグガイド

`scripts/parsers/crosswalk_resolver.py`は、ENの意味タグと公式表のJP表記を現行JPタグへ正規化します。
複数の現行JPタグへ分かれる行は採用しません。
`scripts/parsers/branch_guide_parser.py`は、同じ翻訳元タグに未解決行が併記されている場合も採用しません。

`scripts/commands/build_branch_dicts_from_corpus.py`は、指定15支部の全`meta.json`に現れるタグを辞書キーへ含めます。
同じスクリプトが`dictionaries/jp_tag_policy.json`も生成します。
INTはENのタグ体系を基礎にするため、ENとINTの非使用タグ規則を両方適用します。

## 辞書とUIの契約

`dictionaries/<branch>_to_jp.json`の文字列値は、現行JPタグへ直接変換できることを示します。
値が`null`の場合は、置換辞書とJP利用ポリシーを確認する必要があります。

`index.html`は次の区分を混同してはいけません。

- 単一置換できる非使用タグ
- JPで省略するタグ
- スタッフ許可が必要なタグ
- JPタグの申請または確認が必要なタグ
- 翻訳元コーパスに存在しない入力
- JP利用ポリシーにない変換先

コピー欄には、JP利用ポリシーが翻訳時のコピーを許可したタグだけを出力します。
JP利用ポリシーを読み込めない場合は安全側へ倒し、タグをコピー欄へ出しません。

## カバレッジ生成物

`visualization/branch_tag_coverage.json`とTSVは、全コーパスタグを変換根拠と翻訳時の処理へ分類します。
`visualization/tag_application_inventory.json`とTSVは、処理が`tag_application_required`となる行だけを収録します。
`visualization/branch_tag_coverage.html`は、カバレッジJSONを埋め込んだ自己完結型のダッシュボードです。

生成辞書や可視化JSONだけを直接編集してはいけません。
変更は公式ソースの同期、パーサー、JP規則、査読済み上書きのいずれかへ反映し、生成コマンドを実行します。
