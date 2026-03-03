# 要求仕様書: F13 配置比較・レポート

## 1. プロジェクト概要

- **何を作るか**: F12 で定義された全5種類の配置プリセットを F10 の `evaluate_placement` で評価し、プリセット間の品質スコアを比較表・テキストレポートとして出力するモジュール
- **なぜ作るか**: 複数の配置パターンを定量的に比較し、どの配置が最も優れているかを判断するため。F15（最適化）のベースラインとしても使用する
- **誰が使うか**: 開発者、F15（最適化結果との比較用ベースライン）
- **どこで使うか**: Python 3.12 ローカル環境

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| 比較結果 (comparison result) | 複数プリセットの評価結果を集約したデータ構造。`ComparisonResult` インスタンスとして表現する |
| プリセット評価結果 (preset evaluation result) | 1つのプリセットの評価結果。プリセット情報と `EvaluationResult` のペア。`PresetEvaluation` インスタンスとして表現する |
| ランキング (ranking) | 統合品質スコア (`quality_score`) の降順で並べたプリセットの順位。1位が最良 |
| 比較レポート (comparison report) | 比較結果をテキスト形式でフォーマットした文字列。コンソール出力やファイル保存用 |
| 全体スコア (overall score) | `EvaluationResult.quality.quality_score`。統合グリッド全体の品質スコア |
| ボリューム別スコア (volume score) | `EvaluationResult.volume_qualities` に含まれる活動ボリューム別の品質スコア |
| `evaluate_placement` | F10 で定義された一括評価関数。cameras, room を受け取り `EvaluationResult` を返す |
| `PlacementPreset` | F12 で定義された配置プリセット。name, description, camera_configs を持つ |
| `EvaluationResult` | F10 で定義された評価結果。quality, coverage_result, angle_result, projection_result, volume_qualities を持つ |

## 3. 機能要求一覧

### FR-01: 単一プリセットの評価

プリセットを受け取り、Camera オブジェクトを生成し、`evaluate_placement` で評価して結果を返す。

- 入力:
  - `preset: PlacementPreset`（必須）
  - `room: Room`（必須）
  - `grid_spacing: float`（デフォルト 0.2）
  - `near: float`（デフォルト 0.1）
  - `far: float`（デフォルト 10.0）
  - `target_ppm: float`（デフォルト 500.0）
  - `weight_coverage: float`（デフォルト 0.5）
  - `weight_angle: float`（デフォルト 0.3）
  - `weight_projection: float`（デフォルト 0.2）
- 出力: `PresetEvaluation` インスタンス（preset と evaluation を保持）
- 受け入れ基準: 任意のプリセットと Room を渡して `PresetEvaluation` が返り、`evaluation.quality.quality_score` が [0.0, 1.0] の範囲内であること

### FR-02: 全プリセットの一括比較

F12 の全5プリセットを一括評価し、統合品質スコアの降順でランキングした比較結果を返す。

- 入力:
  - `room: Room`（必須）
  - `presets: list[PlacementPreset] | None`（デフォルト None。None の場合は `get_all_presets()` で全プリセットを取得）
  - 評価パラメータ（FR-01 と同一）
- 出力: `ComparisonResult` インスタンス
- `ComparisonResult` は以下を保持する:
  - `rankings`: `list[PresetEvaluation]`（統合品質スコア `quality_score` の降順でソート）
  - `best`: 最良のプリセット評価結果（`rankings[0]` と同一）
- ソートは `quality_score` の降順。同スコアの場合は入力順を保持する（安定ソート）
- 受け入れ基準: `rankings` が統合品質スコアの降順であること。`best.preset.name` が最高スコアのプリセット名と一致すること

### FR-03: テキスト比較レポートの生成

比較結果からテキスト形式の比較レポートを生成する。

- 入力: `ComparisonResult`
- 出力: `str`（複数行のテキスト）
- レポートの構成（この順序で出力する）:
  1. **ヘッダー行**: `"=== Camera Placement Comparison Report ==="`
  2. **空行**: 1行
  3. **評価パラメータ**: grid_spacing, near, far, target_ppm, weights
  4. **空行**: 1行
  5. **ランキング表**: 順位、プリセット名、統合品質スコア、カバレッジスコア、角度スコア、投影スコア
  6. **空行**: 1行
  7. **活動ボリューム別比較表**: 各活動ボリュームの統合品質スコアをプリセット別に表示
  8. **空行**: 1行
  9. **ベストプリセットサマリー**: 最良プリセットの名前、説明、スコア
- レポートの数値フォーマット: 小数点以下3桁（`:.3f`）
- 受け入れ基準: 生成されたテキストに「Camera Placement Comparison Report」ヘッダー、全プリセット名、全スコアが含まれること

### FR-04: レポートのファイル保存

テキストレポートを指定パスにテキストファイルとして保存する。

- 入力:
  - `report: str`（レポートテキスト）
  - `filepath: str | Path`（保存先パス）
- 出力: `Path`（保存先の Path オブジェクト）
- 親ディレクトリが存在しない場合は自動作成する
- エンコーディング: UTF-8
- 受け入れ基準: 指定パスにファイルが作成され、内容がレポートテキストと一致すること

## 4. 非機能要求

### パフォーマンス

- 全5プリセットの一括比較（`compare_presets`）: grid_spacing=0.2 で 30秒以内（`evaluate_placement` が各プリセットで数秒）
- レポート生成（`generate_report`）: 10ms 以内（文字列フォーマットのみ）

### 対応環境

- Python 3.12
- numpy >= 2.4.2（既存依存）

### 信頼性

- 該当なし。入力データの永続化は行わない。レポートファイルの書き込み失敗時は例外を呼び出し元に伝搬する

## 5. 制約条件

- 使用ライブラリ: numpy（既存依存のみ。追加のライブラリは不要）
- F10（`evaluate_placement`, `EvaluationResult`）、F12（`PlacementPreset`, `get_all_presets`, `create_cameras`）の既存インターフェースを変更しない
- F11（`viewer.py`）の既存インターフェースを変更しない
- レポートのテキスト形式は英語表記とする（プリセット名は英語スネークケースのため）
- 可視化（HTMLファイル）はF13のスコープ外とする。可視化が必要な場合は呼び出し元がF11を直接使用する

## 6. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 単一プリセットの評価 | Must |
| FR-02 全プリセットの一括比較 | Must |
| FR-03 テキスト比較レポートの生成 | Must |
| FR-04 レポートのファイル保存 | Must |

## 7. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| presets=None（デフォルト） | `get_all_presets()` で全5プリセットを取得して比較 |
| presets が1要素のリスト | 正常動作。rankings は1要素。best はその1つ |
| presets が空リスト | `ValueError` を送出。メッセージ: `"presets must not be empty"` |
| 全プリセットが同一スコア | rankings の順序は入力順を保持（安定ソート） |
| evaluate_placement が例外を送出 | 例外を呼び出し元に伝搬する（キャッチしない） |
| filepath の親ディレクトリが存在しない | 自動作成して保存する |

## 8. スコープ外

- 3D可視化の生成（F11 の責務。呼び出し元が直接使用する）
- CSV/JSON 形式でのレポート出力（テキスト形式のみ）
- ユーザー定義の配置（`list[Camera]` を直接渡す）の評価（プリセット経由のみ）
- 複数の Room での比較
- プリセットの部分比較（指定したプリセットのみ比較する機能は presets パラメータで対応済み）
- 配置の推奨理由の自動生成
