# memories.md

> **Historical record:** This document describes earlier design discussions and is not the current architecture. The current implementation, supported commands, and generated-data workflow are documented in [README.md](../README.md).

## 記録の範囲

このファイルには、静的Webツールの初期設計と過去の検討事項だけを残します。現在の実装を説明する資料としては使用せず、変更時はREADME.md、AGENTS.md、および実際の生成コードを確認してください。

## 過去の検討事項

- 初期案では複数の言語ペアを一つの汎用辞書で扱い、辞書をペア単位で遅延読み込みする設計を検討しました。
- Google翻訳風の左右入力欄、ダークモード、レスポンシブ表示、LocalStorageの利用可否を検討しました。
- 連結タグの最長一致、未定義タグのログ表示、非使用タグの扱い、静的ホスティング時のHTTP配信を検討しました。

## 現在の資料への案内

現在は、複数支部のタグをSCP-JPタグへ変換するJP専用のポリシー駆動ワークフローです。対応支部、出力区分、生成手順、互換CLI、テスト、ライセンスはREADME.mdを参照してください。

過去の設計と異なる大きな変更を記録する場合は、まずREADME.mdの現行説明を更新し、このファイルには歴史的な背景としてのみ追記してください。
