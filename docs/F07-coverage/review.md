# F07 カバレッジ計算 — レビュー結果

## レビュー履歴

| 回 | 日付 | レビュー方法 | 基準 |
|---|------|-------------|------|
| 1回目 | 2026-03-03 | Subagent（自動レビュー） | 独自観点 |
| 2回目 | 2026-03-03 | Subagent（自動レビュー） | 独自観点（1回目の修正確認） |
| 3回目 | 2026-03-03 | Subagent（自動レビュー） | `docs/REVIEW_CRITERIA.md` 準拠（8観点） |

---

## 要修正項目

| # | 状態 | 対象ファイル | 内容 | 重要度 | 検出回 |
|---|------|-------------|------|--------|--------|
| ISSUE-1 | 修正済み | requirements.md | セクション2 `volumes` パラメータの説明を `create_activity_volumes(room, grid_spacing)` に修正 | 中 | 1回目 |
| ISSUE-2 | 修正済み | design.md | セクション4 エラー処理表に `shape (0, N)` → `sum(axis=0)` で全ゼロになる仕組みを追記 | 低 | 1回目 |
| ISSUE-3 | 修正済み | design.md | セクション5.5 に `eps` パラメータを露出しない設計判断を追記 | 中 | 1回目 |
| ISSUE-4 | 対応不要 | requirements.md | 空volumes時の `volume_coverages` が空辞書になる記載不足。擬似コードから自明 | 低 | 2回目 |
| ISSUE-5 | 修正済み | design.md | テスト計画カテゴリDに `D4: volumes=[]` のテストケースを追加 | 中 | 2回目 |
| ISSUE-6 | 修正済み | requirements.md, design.md | `coverage_at_least` の説明を「N台以上」→「k台以上」に統一 | 中 | 3回目 |
| ISSUE-7 | 修正済み | requirements.md | 性能基準を「F07自身の集計処理はN=10,000点・M=6台で100ms以内」に具体化 | 中 | 3回目 |
| ISSUE-8 | 修正済み | design.md | テストE2の期待値を `volume_coverages[SUPINE].stats.coverage_3plus < volume_coverages[WALKING].stats.coverage_3plus` に具体化 | 中 | 3回目 |

---

## 3回目レビュー: REVIEW_CRITERIA.md 8観点の判定結果

| # | 観点 | 判定 | 詳細 |
|---|------|------|------|
| 1 | ドキュメント間の一貫性 | ISSUE | 「N台以上」表記がグリッド点数Nと混同する（ISSUE-6） |
| 2 | 曖昧性の排除 | ISSUE | 性能基準「実用的な速度」が曖昧（ISSUE-7）。テストE2の期待値が定性的（ISSUE-8） |
| 3 | エラーハンドリング・境界条件 | CONCERN | `cameras=[]`時の`coverage_at_least`空辞書、`near`/`far`異常値のF04委譲が未明記 |
| 4 | 技術スタック・依存関係 | CONCERN | numpy/pytestのバージョン未記載（プロジェクト全体の課題、F07固有ではない） |
| 5 | データフロー・I/O定義 | OK | データ型・形式・単位が全て明記。データフロー図が明確 |
| 6 | 状態遷移 | N/A | ステートレスな関数群。状態遷移は存在しない |
| 7 | 非機能要件 | ISSUE(低) | ログ出力方針が未定義（プロジェクト全体の課題、F07固有ではない） |
| 8 | 詳細設計の十分性 | OK | 擬似コード・dataclass定義・設計判断・テスト計画が十分に詳細 |

---

## 懸念事項（修正不要、記録のみ）

| # | 内容 | 備考 | 検出回 |
|---|------|------|--------|
| CONCERN-1 | 統合グリッドで `check_visibility_multi_camera` を再計算（4回呼び出し）のコスト | 現スケール（N=数千）では問題なし。将来の最適化ポイント | 1回目 |
| CONCERN-2 | `cameras=[]` のとき `coverage_at_least` が空辞書 `{}` になる | テストD1で明示的に検証するとよい | 1回目 |
| CONCERN-3 | テスト用ヘルパー `_small_activity_volume` は3タイプ全て同じ座標 | ボリューム別差異のテスト（E2）では `create_activity_volumes` を使うので問題なし | 1回目 |
| CONCERN-4 | `create_merged_grid` が `np.unique` でソートするため統合グリッドのインデックスが個別ボリュームと非対応 | F08/F09の設計時に注意 | 1回目 |
| CONCERN-5 | `volumes` に同じ `ActivityType` が重複した場合、後のものが上書き | docstringに注記があるとよい | 1回目 |
| CONCERN-6 | `cameras=[]` 時の `coverage_at_least` 空辞書の挙動が設計書に未明記 | 後続F10等が辞書アクセスする場合にKeyErrorの可能性 | 3回目 |
| CONCERN-7 | `near`/`far` の異常値バリデーションの責務がF04にあることがエラー処理テーブルに未明記 | 動作には影響なし | 3回目 |
| CONCERN-8 | numpy/pytestのバージョン未記載 | プロジェクト全体の課題。`pyproject.toml`で管理されている | 3回目 |
| CONCERN-9 | ログ出力方針が未定義 | プロジェクト全体の課題。F07固有ではない | 3回目 |

---

## 良い点

- `CoverageStats` の一次データ（`visible_counts`）と導出propertyの分離設計
- 後続機能（F08〜F13）のインターフェース要件がコード例付きで明確
- ドキュメント間の型定義が一貫
- テスト計画が5カテゴリ約25件で網羅的
- 既存コード（F01〜F06）とのインポートパスが全て正確
- データフロー図が明確
- エッジケースが要求仕様書・機能設計書間で整合
- 設計判断が6項目、理由付きで記載されている（特に5.1, 5.4, 5.5が優れている）
- dataclass定義・擬似コード・__init__.pyの内容が実装可能なレベルで詳細
