# 要求仕様書: F09 2D投影サイズスコア

## 1. 目的

カメラからの距離に基づき、各グリッド点における画像上の空間解像度（ピクセル/メートル）を計算し、2Dキーポイント検出精度の指標としてスコア化する。カメラから遠い点ほど被写体が画像上で小さくなり、2Dキーポイント検出精度が低下する（CLAUDE.md品質指標参照）。この距離依存の品質劣化を定量化する。

### Phase内での位置づけ

- **入力**: F07 `CoverageResult` の `visibility_matrix` (M, N) bool、`cameras` list[Camera]、`merged_grid` (N, 3)
- **出力**: 投影スコア (`ProjectionScoreResult`)
- **後続**: F10 が投影スコアを統合品質スコアに組み込む

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| 投影解像度 (projection resolution, ppm) | ある距離における画像上の空間解像度 [px/m]。`fx / distance` で計算。値域 (0, ∞) |
| ユークリッド距離 (Euclidean distance) | カメラ位置から3D点までの直線距離 [m]。`‖point - camera.position‖` |
| fx | カメラ内部パラメータの水平焦点距離のピクセル単位換算 [px]。`Camera.intrinsics.fx`。デフォルト値 ≈ 1166.67（= 3.5mm / 0.003mm） |
| 目標投影解像度 (target_ppm) | スコアが 1.0 となる投影解像度の閾値 [px/m]。この値以上であれば2D検出が十分に高精度とみなす |
| ポイントスコア (point score) | 1つの3D点における投影スコア値 [0.0, 1.0] |
| ベストスコア (best score) | ある点における全視認カメラ中の最大投影スコア。最も近い（=最良解像度の）カメラの品質を表す |
| 平均スコア (mean score) | ある点における全視認カメラの投影スコアの算術平均 |

## 3. 機能要件

### FR-01: 投影解像度の計算

1台のカメラ位置と3D点群から、各点における投影解像度をバッチ計算する。

- 入力: カメラ位置 shape (3,)、水平焦点距離 fx [px]、3D点群 shape (N, 3)
- 出力: 投影解像度配列 shape (N,) [px/m]
- 計算式:
  - `distance = ‖point - camera_position‖`
  - `ppm = fx / distance`
- カメラ位置が点と一致する場合（距離が 1e-10 未満）: ppm = 0.0
- 受け入れ基準: 既知の距離・fx値で期待通りのppm値が得られること

### FR-02: ポイントスコアの計算

投影解像度を [0.0, 1.0] のスコアに変換する。

- スコア関数: `score = min(ppm / target_ppm, 1.0)`
- 値域: [0.0, 1.0]
- デフォルト target_ppm: 500.0 [px/m]
- 代表的な値（デフォルトパラメータ、fx ≈ 1167 の場合）:
  - distance = 1.0 m → ppm ≈ 1167, score = 1.0
  - distance = 2.0 m → ppm ≈ 583, score = 1.0
  - distance = 2.33 m → ppm ≈ 500, score = 1.0（飽和境界）
  - distance = 3.0 m → ppm ≈ 389, score ≈ 0.778
  - distance = 4.0 m → ppm ≈ 292, score ≈ 0.583
  - distance = 5.0 m → ppm ≈ 233, score ≈ 0.467
- 受け入れ基準: 上記代表値が許容誤差内（atol=0.01）で得られること

### FR-03: ポイントスコアの集約

各グリッド点について、視認可能な全カメラのスコアを集約する。

- 視認カメラ数 ≥ 1 の場合:
  - ベストスコア: 全視認カメラ中の最大スコア
  - 平均スコア: 全視認カメラのスコアの算術平均
  - ベスト投影解像度: ベストスコアに対応する投影解像度 [px/m]
- 視認カメラ数 = 0 の場合:
  - ベストスコア = 0.0
  - 平均スコア = 0.0
  - ベスト投影解像度 = 0.0
- 受け入れ基準: 2台以上のカメラで距離が異なる場合、近い方のカメラのスコアがベストスコアに選ばれること

### FR-04: 全体スコアの計算

全グリッド点のベストスコアの算術平均を全体スコアとする。

- `mean_score = mean(point_best_scores)`
- グリッド点数が 0 の場合: `mean_score = 0.0`
- 受け入れ基準: `mean_score == np.mean(point_best_scores)` が成立すること

### FR-05: 活動ボリューム別対応

F07の `CoverageResult` から取得した `visibility_matrix` と `merged_grid` に対してスコアを計算する。`calculate_projection_score` は任意の `visibility_matrix` と対応する `grid_points` を受け付けるため、`VolumeCoverage.visibility_matrix` と対応する `ActivityVolume.grid_points` を渡すことで活動ボリューム別の投影スコアを計算できる。

- 受け入れ基準: `CoverageResult` から得たデータを入力として渡し、エラーなく実行されること

## 4. 入力パラメータ

### `calculate_projection_score` 関数（メイン関数）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト。len = M |
| grid_points | np.ndarray, shape (N, 3), float64 | (必須) | グリッド点群 [m] |
| visibility_matrix | np.ndarray, shape (M, N), dtype=bool | (必須) | 視認性行列。F07の出力 |
| target_ppm | float | 500.0 | 目標投影解像度 [px/m]。正の値のみ。この値以上でスコア=1.0 |

### `calculate_pixel_per_meter` 関数（低レベルユーティリティ）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| camera_pos | np.ndarray, shape (3,), float64 | (必須) | カメラ位置 [m] |
| points | np.ndarray, shape (N, 3), float64 | (必須) | 3D点群 [m] |
| fx | float | (必須) | 水平焦点距離 [px]（Camera.intrinsics.fx） |

## 5. 出力

### ProjectionScoreResult

| フィールド | 型 | 説明 |
|---|---|---|
| point_best_scores | np.ndarray, shape (N,), float64 | 各点のベストスコア [0.0-1.0]。視認カメラなしの点は 0.0 |
| point_mean_scores | np.ndarray, shape (N,), float64 | 各点の平均スコア [0.0-1.0]。視認カメラなしの点は 0.0 |
| point_best_ppm | np.ndarray, shape (N,), float64 | 各点のベスト投影解像度 [px/m]。視認カメラなしの点は 0.0 |
| mean_score | float | point_best_scores の算術平均。全体スコア。点数 0 の場合は 0.0 |

### 使用イメージ

```python
from camera_placement.evaluation.coverage import calculate_coverage
from camera_placement.evaluation.projection_score import calculate_projection_score

# F07 でカバレッジ計算
coverage_result = calculate_coverage(cameras, room)

# F09 で投影スコア計算
proj_result = calculate_projection_score(
    coverage_result.cameras,
    coverage_result.merged_grid,
    coverage_result.visibility_matrix,
)

print(f"全体投影スコア: {proj_result.mean_score:.3f}")
print(f"最悪点スコア: {proj_result.point_best_scores.min():.3f}")

# 活動ボリューム別にも計算可能
volumes = create_activity_volumes(room, grid_spacing=0.2)
supine_vol = [v for v in volumes if v.activity_type == ActivityType.SUPINE][0]
vc = coverage_result.volume_coverages[ActivityType.SUPINE]
proj_supine = calculate_projection_score(
    coverage_result.cameras,
    supine_vol.grid_points,
    vc.visibility_matrix,
)
```

## 6. 非機能要求

### パフォーマンス

- M=6台、N=5,000点での計算時間: 200ms以内（F09自身の計算のみ、F07呼び出しを除く）
- NumPyのベクトル化演算を使用し、点単位のPythonループを排除する

### 対応環境

- Python 3.12
- numpy のみ使用（追加ライブラリ不要）

## 7. 制約条件

- 使用ライブラリ: numpy のみ（標準ライブラリは使用可）
- F07 の `CoverageResult` から得られるデータを入力として使用する
- セルフオクルージョンは考慮しない（F06/F07と同様）
- カメラ台数は最大6台を想定するが、任意のM台で動作すること
- target_ppm は正の値でなければならない（0以下は ValueError）

## 8. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 投影解像度の計算 | Must |
| FR-02 ポイントスコアの計算 | Must |
| FR-03 ポイントスコアの集約 (best/mean) | Must |
| FR-04 全体スコア | Must |
| FR-05 活動ボリューム別対応 | Should |

## 9. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| cameras が空リスト | 全 point_best_scores = 0.0、mean_score = 0.0 |
| cameras が1台のみ | その1台から計算。best_score = mean_score（各点） |
| 全点が視認不可 | 全 point_best_scores = 0.0 |
| grid_points が空 shape (0, 3) | mean_score = 0.0、全配列が空 shape (0,) |
| カメラが点と同一位置 (distance < 1e-10) | ppm = 0.0、score = 0.0 |
| target_ppm ≤ 0 | ValueError |
| 非常に遠い点 (distance → ∞) | ppm → 0、score → 0.0 |
| 非常に近い点 (distance → 0+、ただし > 1e-10) | ppm → ∞、score = 1.0 (min でクランプ) |

## 10. スコープ外

- セルフオクルージョンの考慮
- 画像端部での歪みによる精度劣化の考慮（TV歪曲 0.4% と微小なため）
- カメラ光軸に対する角度（foreshortening）の考慮
- 三角測量角度の評価（F08の責務）
- カバレッジ・角度・投影サイズの統合評価（F10の責務）
- 個別カメラの最適距離への配置調整（F14/F15の責務）
