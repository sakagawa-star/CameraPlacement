# 要求仕様書: F08 三角測量角度スコア

## 1. 目的

同一の3Dグリッド点を観測する複数カメラの視線角度差（角度分離）を計算し、三角測量精度の指標としてスコア化する。三角測量の精度はカメラペア間の角度分離に大きく依存し、90°前後が理想、15°未満では精度が大幅に低下する（CLAUDE.md品質指標参照）。

### Phase内での位置づけ

- **入力**: F07 `CoverageResult` の `visibility_matrix` (M, N) bool、`cameras` list[Camera]、`merged_grid` (N, 3)
- **出力**: 角度スコア (`AngleScoreResult`)
- **後続**: F10 が角度スコアを統合品質スコアに組み込む

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| 角度分離 (angle separation) | 同一3D点を観測する2台のカメラの視線ベクトル間の角度 [rad]。値域 [0, π] |
| 視線ベクトル (view ray) | カメラ位置から3D点に向かう方向ベクトル。`point - camera.position` |
| ペアスコア (pair score) | 1組のカメラペアの角度分離に基づくスコア値。`sin(angle)` で計算。値域 [0.0, 1.0] |
| ポイントスコア (point score) | 1つの3D点における全有効ペアのスコアを集約した値 |
| ベストペアスコア (best pair score) | ある点における全カメラペア中の最大ペアスコア。その点で最良の三角測量精度を表す |
| 平均ペアスコア (mean pair score) | ある点における全有効ペアのペアスコアの算術平均 |
| 有効ペア (valid pair) | 両方のカメラから点が視認可能であるカメラペア |

## 3. 機能要件

### FR-01: 角度分離の計算

2台のカメラ位置と3D点群から、各点における視線ベクトル間の角度をバッチ計算する。

- 入力: カメラA位置 shape (3,)、カメラB位置 shape (3,)、3D点群 shape (N, 3)
- 出力: 角度配列 shape (N,) [rad]、値域 [0, π]
- 計算式:
  - `v_a = point - camera_a_position`
  - `v_b = point - camera_b_position`
  - `angle = arccos(dot(v_a, v_b) / (|v_a| * |v_b|))`
- カメラ位置が点と一致する場合（ノルムが 1e-10 未満）: angle = 0.0

### FR-02: ペアスコアの計算

角度分離をスコア値に変換する。

- スコア関数: `score = sin(angle)`
- 値域: [0.0, 1.0]
- 代表的な値:
  - angle = 90° (π/2 rad) → score = 1.0（最適）
  - angle = 0° → score = 0.0（最悪、同一方向）
  - angle = 180° (π rad) → score = 0.0（最悪、反対方向）
  - angle = 15° (π/12 rad) → score ≈ 0.259（精度低下の目安）
  - angle = 30° (π/6 rad) → score = 0.5
  - angle = 60° (π/3 rad) → score ≈ 0.866

### FR-03: ポイントスコアの計算

各グリッド点について、視認可能な全カメラペアのスコアを集約する。

- 有効ペア数 ≥ 1 の場合:
  - ベストペアスコア: 全有効ペア中の最大 `sin(angle)`
  - 平均ペアスコア: 全有効ペアの `sin(angle)` の算術平均
  - ベストペア角度: ベストペアスコアに対応する角度 [rad]
- 有効ペア数 = 0 の場合（視認カメラ数が 0 または 1）:
  - ベストペアスコア = 0.0
  - 平均ペアスコア = 0.0
  - ベストペア角度 = 0.0

### FR-04: 全体スコアの計算

全グリッド点のベストペアスコアの算術平均を全体スコアとする。

- `mean_score = mean(point_best_scores)`
- グリッド点数が 0 の場合: `mean_score = 0.0`

### FR-05: 活動ボリューム別対応

F07の `CoverageResult` から取得した `visibility_matrix` と `merged_grid` に対してスコアを計算する。`calculate_angle_score` は任意の `visibility_matrix` と対応する `grid_points` を受け付けるため、`VolumeCoverage.visibility_matrix` と対応する `ActivityVolume.grid_points` を渡すことで活動ボリューム別の角度スコアを計算できる。

## 4. 入力パラメータ

### `calculate_angle_score` 関数（メイン関数）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト。len = M |
| grid_points | np.ndarray, shape (N, 3), float64 | (必須) | グリッド点群 [m] |
| visibility_matrix | np.ndarray, shape (M, N), dtype=bool | (必須) | 視認性行列。F07の出力 |

### `calculate_pair_angles` 関数（低レベルユーティリティ）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| camera_pos_a | np.ndarray, shape (3,), float64 | (必須) | カメラA位置 [m] |
| camera_pos_b | np.ndarray, shape (3,), float64 | (必須) | カメラB位置 [m] |
| points | np.ndarray, shape (N, 3), float64 | (必須) | 3D点群 [m] |

## 5. 出力

### AngleScoreResult

| フィールド | 型 | 説明 |
|---|---|---|
| point_best_scores | np.ndarray, shape (N,), float64 | 各点のベストペアスコア `sin(angle)` [0.0-1.0]。有効ペアなしの点は 0.0 |
| point_mean_scores | np.ndarray, shape (N,), float64 | 各点の平均ペアスコア [0.0-1.0]。有効ペアなしの点は 0.0 |
| point_best_angles | np.ndarray, shape (N,), float64 | 各点のベストペア角度 [rad] [0.0-π]。有効ペアなしの点は 0.0 |
| point_num_pairs | np.ndarray, shape (N,), int | 各点の有効ペア数 |
| mean_score | float | point_best_scores の算術平均。全体スコア。点数 0 の場合は 0.0 |

### 使用イメージ

```python
from camera_placement.evaluation.coverage import calculate_coverage
from camera_placement.evaluation.angle_score import calculate_angle_score

# F07 でカバレッジ計算
coverage_result = calculate_coverage(cameras, room)

# F08 で角度スコア計算
angle_result = calculate_angle_score(
    coverage_result.cameras,
    coverage_result.merged_grid,
    coverage_result.visibility_matrix,
)

print(f"全体角度スコア: {angle_result.mean_score:.3f}")
print(f"最悪点スコア: {angle_result.point_best_scores.min():.3f}")

# 活動ボリューム別にも計算可能
# grid_points は ActivityVolume から取得する
volumes = create_activity_volumes(room, grid_spacing=0.2)
supine_vol = [v for v in volumes if v.activity_type == ActivityType.SUPINE][0]
vc = coverage_result.volume_coverages[ActivityType.SUPINE]
angle_supine = calculate_angle_score(
    coverage_result.cameras,
    supine_vol.grid_points,  # shape (N_vol, 3)
    vc.visibility_matrix,
)
```

## 6. 非機能要求

### パフォーマンス

- M=6台、N=5,000点での計算時間: 500ms以内（F08自身の計算のみ、F07呼び出しを除く）
- NumPyのベクトル化演算を使用し、点単位のPythonループを排除する

### 対応環境

- Python 3.12
- numpy のみ使用（追加ライブラリ不要）

## 7. 制約条件

- 使用ライブラリ: numpy のみ（scipy、itertools等の標準ライブラリは使用可）
- F07 の `CoverageResult` から得られるデータを入力として使用する
- セルフオクルージョンは考慮しない（F06/F07と同様）
- カメラ台数は最大6台を想定するが、任意のM台で動作すること

## 8. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 角度分離の計算 | Must |
| FR-02 ペアスコアの計算 (sin) | Must |
| FR-03 ポイントスコア (best/mean) | Must |
| FR-04 全体スコア | Must |
| FR-05 活動ボリューム別対応 | Should |

## 9. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| cameras が空リスト | 全 point_best_scores = 0.0、mean_score = 0.0 |
| cameras が1台のみ | ペアなし。全 point_best_scores = 0.0、mean_score = 0.0 |
| 全点が1台以下のカメラからのみ視認可能 | 全 point_best_scores = 0.0 |
| grid_points が空 shape (0, 3) | mean_score = 0.0、空の配列 |
| 2台のカメラが完全に90°で1点を観測 | point_best_scores[j] = 1.0 |
| 2台のカメラが同一方向から観測 (angle ≈ 0) | point_best_scores[j] ≈ 0.0 |
| 2台のカメラが反対方向から観測 (angle ≈ π) | point_best_scores[j] ≈ 0.0 |

## 10. スコープ外

- セルフオクルージョンの考慮
- 2D投影サイズの評価（F09の責務）
- カバレッジ・角度・投影サイズの統合評価（F10の責務）
- 個別カメラペアの最適角度への配置調整（F14/F15の責務）
