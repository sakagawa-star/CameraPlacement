# 要求仕様書: F10 統合品質スコア

## 1. プロジェクト概要

- **何を作るか**: F07（カバレッジ）、F08（三角測量角度スコア）、F09（2D投影サイズスコア）の3つの評価指標を統合し、カメラ配置全体の品質を1つのスコアで返す関数
- **なぜ作るか**: F13（配置比較）で複数の配置パターンを単一スコアで比較するため、F14（目的関数）で最適化の評価関数として使用するため
- **誰が使うか**: F13（配置比較モジュール）、F14（目的関数モジュール）、開発者
- **どこで使うか**: Python 3.12 ローカル環境

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| 統合品質スコア (quality score) | カバレッジスコア・角度スコア・投影スコアの加重和。値域 [0.0, 1.0] |
| カバレッジスコア (coverage score) | F07 `CoverageResult.stats.coverage_3plus`。3台以上のカメラから視認可能な点の割合。値域 [0.0, 1.0] |
| 角度スコア (angle score) | F08 `AngleScoreResult.mean_score`。全グリッド点のベストペアスコアの算術平均。値域 [0.0, 1.0] |
| 投影スコア (projection score) | F09 `ProjectionScoreResult.mean_score`。全グリッド点のベストスコアの算術平均。値域 [0.0, 1.0] |
| 重み (weight) | 各コンポーネントスコアに掛ける係数。3つの重みの合計は 1.0 に正規化される |
| コンポーネントスコア (component score) | カバレッジスコア・角度スコア・投影スコアの総称 |
| ポイント品質スコア (point quality score) | 各グリッド点における角度スコアと投影スコアの加重和。値域 [0.0, 1.0]。カバレッジは点レベルでは「視認カメラ数」であり [0.0, 1.0] スコアではないため含まない |

## 3. 機能要件

### FR-01: 統合品質スコアの計算

F07・F08・F09 の計算結果を受け取り、加重和で統合品質スコアを算出する。

- 計算式: `quality_score = w_cov * coverage_score + w_angle * angle_score + w_proj * projection_score`
- 入力の各スコアの値域は [0.0, 1.0]。バリデーションは行わない（呼び出し元の責務。F07/F08/F09 が返すスコアは常に [0.0, 1.0] の範囲内）
- 出力の値域は [0.0, 1.0]（入力が [0.0, 1.0] の場合）
- デフォルト重み: `w_cov = 0.5, w_angle = 0.3, w_proj = 0.2`
- 受け入れ基準: 既知の3コンポーネントスコアから手動計算した加重和と一致すること（atol=1e-10）

### FR-02: 重みの正規化

ユーザー指定の重みは合計が 1.0 でなくても許容し、内部で合計 1.0 に正規化する。

- 計算式: `w_normalized = w / sum(w_cov, w_angle, w_proj)`
- 重みの合計が 0 の場合: `ValueError` を送出
- 個々の重みが負の場合: `ValueError` を送出
- 受け入れ基準: `weights=(2, 1, 1)` が `(0.5, 0.25, 0.25)` と同じ結果を返すこと

### FR-03: コンポーネントスコアの保持

結果に各コンポーネントスコア（カバレッジ・角度・投影）と正規化後の重みを保持する。F13が個別スコアを比較表で表示するため。

- 受け入れ基準: `QualityScoreResult` から各コンポーネントスコアと重みを取り出せること

### FR-04: ポイント品質スコアの計算

各グリッド点において、角度ベストスコアと投影ベストスコアの加重和でポイント品質スコアを算出する。

- 計算式: `point_quality = w_angle_norm * point_angle_best + w_proj_norm * point_proj_best`
  - ここで `w_angle_norm = w_angle / (w_angle + w_proj)`, `w_proj_norm = w_proj / (w_angle + w_proj)`
  - カバレッジは点レベルスコアに含めない（点レベルでは [0, M] の整数であり、[0.0, 1.0] のスコアではないため）
- w_angle と w_proj の合計が 0 の場合: `point_quality = zeros(N)`
- 値域: [0.0, 1.0]
- F14（目的関数）が点レベルの品質を参照してペナルティを計算する際に使用
- 受け入れ基準: 手動計算した加重和と一致すること

### FR-05: 一括計算関数

カメラリストとRoomから、F07→F08→F09→F10 の全計算を一括実行する便利関数を提供する。

- 入力: cameras, room, 各種オプション（grid_spacing, near, far, target_ppm, weights）
- 出力: `QualityScoreResult`（内部で CoverageResult, AngleScoreResult, ProjectionScoreResult を保持）
- F13（配置比較）が複数配置パターンをワンコールで評価するために使用
- 受け入れ基準: `evaluate_placement(cameras, room)` の1回の呼び出しで全スコアが取得できること

### FR-06: 活動ボリューム別スコア

活動ボリューム（歩行・座位・臥位）ごとの統合品質スコアも計算する。

- 各活動ボリュームの `visibility_matrix` と `grid_points` を使って F08・F09 を個別計算し、統合品質スコアを算出
- 結果を `dict[ActivityType, VolumeQualityScore]` として保持
- 受け入れ基準: 3つの活動ボリューム（WALKING, SEATED, SUPINE）それぞれの統合品質スコアが取得できること

## 4. 入力パラメータ

### `calculate_quality_score` 関数（コアロジック）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| coverage_score | float | (必須) | カバレッジスコア [0.0, 1.0]。F07 `stats.coverage_3plus` |
| angle_score | float | (必須) | 角度スコア [0.0, 1.0]。F08 `mean_score` |
| projection_score | float | (必須) | 投影スコア [0.0, 1.0]。F09 `mean_score` |
| point_angle_scores | np.ndarray, shape (N,), float64 | (必須) | 各点の角度ベストスコア。F08 `point_best_scores` |
| point_projection_scores | np.ndarray, shape (N,), float64 | (必須) | 各点の投影ベストスコア。F09 `point_best_scores` |
| weight_coverage | float | 0.5 | カバレッジの重み。非負 |
| weight_angle | float | 0.3 | 角度スコアの重み。非負 |
| weight_projection | float | 0.2 | 投影スコアの重み。非負 |

### `evaluate_placement` 関数（一括計算）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト |
| room | Room | (必須) | 病室モデル |
| volumes | list[ActivityVolume] \| None | None | 活動ボリューム。None の場合は自動生成 |
| grid_spacing | float | 0.2 | グリッド間隔 [m] |
| near | float | 0.1 | ニアクリップ距離 [m] |
| far | float | 10.0 | ファークリップ距離 [m] |
| target_ppm | float | 500.0 | 目標投影解像度 [px/m] |
| weight_coverage | float | 0.5 | カバレッジの重み |
| weight_angle | float | 0.3 | 角度スコアの重み |
| weight_projection | float | 0.2 | 投影スコアの重み |

## 5. 出力

### QualityScoreResult

| フィールド | 型 | 説明 |
|---|---|---|
| quality_score | float | 統合品質スコア [0.0, 1.0] |
| coverage_score | float | カバレッジスコア (coverage_3plus) [0.0, 1.0] |
| angle_score | float | 角度スコア (mean_score) [0.0, 1.0] |
| projection_score | float | 投影スコア (mean_score) [0.0, 1.0] |
| weight_coverage | float | 正規化後のカバレッジ重み |
| weight_angle | float | 正規化後の角度重み |
| weight_projection | float | 正規化後の投影重み |
| point_quality_scores | np.ndarray, shape (N,), float64 | 各点のポイント品質スコア [0.0, 1.0] |
| mean_point_quality | float | point_quality_scores の算術平均。点数 0 の場合は 0.0 |

### EvaluationResult（一括計算の結果）

| フィールド | 型 | 説明 |
|---|---|---|
| quality | QualityScoreResult | 統合品質スコア（統合グリッド全体） |
| coverage_result | CoverageResult | F07 のカバレッジ計算結果 |
| angle_result | AngleScoreResult | F08 の角度スコア計算結果 |
| projection_result | ProjectionScoreResult | F09 の投影スコア計算結果 |
| volume_qualities | dict[ActivityType, VolumeQualityScore] | 活動ボリューム別の品質スコア |

### VolumeQualityScore

| フィールド | 型 | 説明 |
|---|---|---|
| activity_type | ActivityType | 動作パターンの種別 |
| quality_score | float | 統合品質スコア [0.0, 1.0] |
| coverage_score | float | カバレッジスコア (coverage_3plus) [0.0, 1.0] |
| angle_score | float | 角度スコア (mean_score) [0.0, 1.0] |
| projection_score | float | 投影スコア (mean_score) [0.0, 1.0] |

### 使用イメージ

```python
from camera_placement.evaluation.evaluator import evaluate_placement

# 一括計算
result = evaluate_placement(cameras, room)

# 統合品質スコア
print(f"品質スコア: {result.quality.quality_score:.3f}")
print(f"  カバレッジ: {result.quality.coverage_score:.3f}")
print(f"  角度: {result.quality.angle_score:.3f}")
print(f"  投影: {result.quality.projection_score:.3f}")

# 活動ボリューム別
for act_type, vq in result.volume_qualities.items():
    print(f"{act_type.value}: {vq.quality_score:.3f}")

# 点レベル品質
worst_point = result.quality.point_quality_scores.min()
print(f"最悪点品質: {worst_point:.3f}")

# F14（目的関数）での使用
# F14 は result.quality.quality_score を最大化する
```

## 6. 非機能要求

### パフォーマンス

- `calculate_quality_score` の計算時間: N=10,000 点で 10ms 以内（加重和のみで軽量）
- `evaluate_placement` の計算時間: F07+F08+F09 の合計時間に支配される。F10 自身のオーバーヘッドは 50ms 以内

### 対応環境

- Python 3.12
- numpy のみ使用（追加ライブラリ不要）

## 7. 制約条件

- 使用ライブラリ: numpy のみ（標準ライブラリは使用可）
- F07, F08, F09 の既存インターフェースを変更しない
- セルフオクルージョンは考慮しない（F06/F07 と同様）
- カメラ台数は最大 6 台を想定するが、任意の M 台で動作すること
- 重みは全て非負でなければならない（負の値は ValueError）
- 重みの合計が 0 の場合は ValueError

## 8. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 統合品質スコアの計算 | Must |
| FR-02 重みの正規化 | Must |
| FR-03 コンポーネントスコアの保持 | Must |
| FR-04 ポイント品質スコアの計算 | Must |
| FR-05 一括計算関数 | Must |
| FR-06 活動ボリューム別スコア | Should |

## 9. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| 全コンポーネントスコアが 0.0 | quality_score = 0.0 |
| 全コンポーネントスコアが 1.0 | quality_score = 1.0 |
| cameras が空リスト | 全スコア 0.0（F07/F08/F09 がそれぞれ 0.0 を返すため）。volume_qualities は 3 キー（WALKING, SEATED, SUPINE）で全て quality_score=0.0 |
| cameras が 1 台のみ | coverage_3plus=0.0, angle_mean_score=0.0 のため quality_score は低い |
| grid_points が空 shape (0, 3) | quality_score = 0.0, point_quality_scores = shape (0,) |
| weight_coverage=1, weight_angle=0, weight_projection=0 | quality_score = coverage_score |
| weight_coverage=0, weight_angle=1, weight_projection=0 | quality_score = angle_score |
| 重みが全て 0 | ValueError |
| 重みに負の値 | ValueError |
| point_angle_scores と point_projection_scores の長さが不一致 | ValueError |
| 入力スコアが [0.0, 1.0] 外 | バリデーションしない。呼び出し元の責務。quality_score が [0.0, 1.0] を超える可能性がある |
| point 配列の値が [0.0, 1.0] 外 | バリデーションしない。呼び出し元の責務 |

## 10. スコープ外

- セルフオクルージョンの考慮
- 個別カメラペアの最適化（F14/F15 の責務）
- 配置パターン間の比較ロジック（F13 の責務）
- 3D 可視化（F11 の責務）
- 重みの自動チューニング（将来課題）
