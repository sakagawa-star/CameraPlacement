# 要求仕様書: F07 カバレッジ計算

## 1. 目的

F06（視認性統合）の `check_visibility_multi_camera` が返す visibility_matrix `(M, N) bool` を集計し、構造化されたカバレッジ統計を返す。Phase 3（カバレッジ評価）の最初の機能であり、後続の F08（角度スコア）、F09（投影スコア）、F10（統合スコア）、F11（可視化）に視認情報を提供する基盤となる。

### Phase内での位置づけ

- **入力**: F06 `check_visibility_multi_camera` の戻り値 `(M, N) bool`
- **出力**: カバレッジ統計（`CoverageResult`）
- **後続**: F08, F09, F10, F11, F13 が `CoverageResult` のフィールドを利用

## 2. 入力パラメータ

### `calculate_coverage` 関数（メイン関数）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト。len = M（通常6台） |
| room | Room | (必須) | 病室モデル。room.bed をオクルージョン判定に使用 |
| volumes | list[ActivityVolume] \| None | None | 活動ボリュームのリスト。Noneの場合は `create_activity_volumes(room, grid_spacing)` で自動生成 |
| grid_spacing | float | 0.2 | volumes=None の場合のグリッド間隔 [m] |
| near | float | 0.1 | ニアクリップ距離 [m] |
| far | float | 10.0 | ファークリップ距離 [m] |

### `calculate_coverage_stats` 関数（統計計算ユーティリティ）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| visibility_matrix | np.ndarray, shape (M, N), dtype=bool | (必須) | 視認性行列 |

### `calculate_volume_coverage` 関数（活動ボリューム別統計）

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト |
| volume | ActivityVolume | (必須) | 単一の活動ボリューム |
| bed_aabb | AABB | (必須) | ベッドのAABB |
| near | float | 0.1 | ニアクリップ距離 [m] |
| far | float | 10.0 | ファークリップ距離 [m] |

## 3. 出力（提供する機能）

### 3.1 `calculate_coverage(cameras, room, ...) -> CoverageResult`

メイン関数。全活動ボリュームの統合グリッドに対するカバレッジを計算し、活動ボリューム別の統計も内部で計算して結果に含める。

### 3.2 `calculate_coverage_stats(visibility_matrix) -> CoverageStats`

純粋な統計計算ユーティリティ。任意の visibility_matrix に対してカバレッジ統計を計算する。後続機能（F08/F09/F10）が部分的にカバレッジ統計を計算する際にも利用可能。

### 3.3 `calculate_volume_coverage(cameras, volume, bed_aabb, ...) -> VolumeCoverage`

単一の活動ボリュームに対するカバレッジを計算する。

## 4. 機能要件

### FR-01: 視認カメラ数の計算

`check_visibility_multi_camera(cameras, grid_points, room.bed)` を呼び出し、`visibility_matrix.sum(axis=0)` で各点の視認カメラ数を計算する。

### FR-02: カバレッジ統計の算出

以下の統計量を計算する:

- **visible_counts**: 各点の視認カメラ数 (shape (N,), dtype=int)
- **coverage_at_least**: k台以上カバー率の辞書 (key: k=1,2,...,M, value: float 0.0〜1.0)
- **min_visible**: 最小視認カメラ数 (int)
- **max_visible**: 最大視認カメラ数 (int)
- **mean_visible**: 平均視認カメラ数 (float)
- **coverage_3plus**: 3台以上カバー率 (float, 最重要指標)

### FR-03: 活動ボリューム別カバレッジ

歩行(WALKING)・座位(SEATED)・臥位(SUPINE) それぞれの活動ボリュームに対して個別にカバレッジ統計を計算する。統合グリッドの全体統計も計算する。

### FR-04: visibility_matrix の保持

`CoverageResult` に `visibility_matrix` を保持する。F08, F09 が visibility_matrix を直接使うため。

### FR-05: 統合グリッドの保持

`CoverageResult` に `merged_grid` (統合グリッド点群) を保持する。F11（可視化）がカバレッジマップを表示する際に必要。

## 5. 後続機能が必要とするインターフェース

| 後続機能 | F07に必要なもの | 用途 |
|---------|---------------|------|
| F08 角度スコア | `CoverageResult.visibility_matrix` (M, N) bool + `CoverageResult.cameras` + `CoverageResult.merged_grid` | 視認可能カメラペアの角度分離計算 |
| F09 投影スコア | `CoverageResult.visibility_matrix` (M, N) bool + `CoverageResult.cameras` + `CoverageResult.merged_grid` | 距離ベースの2D投影サイズスコア |
| F10 統合スコア | `CoverageResult.stats.coverage_3plus` + 他の統計量 | カバレッジスコアとして統合品質スコアに組み込み |
| F11 可視化 | `CoverageResult.stats.visible_counts` + `CoverageResult.merged_grid` | カバレッジマップ（各点を視認カメラ数で色分け） |
| F13 配置比較 | `CoverageResult.volume_coverages[ActivityType.WALKING]` 等 | 活動ボリューム別の比較表 |

F08での使用イメージ:

```python
from camera_placement.evaluation.coverage import calculate_coverage

result = calculate_coverage(cameras, room)

# 統合グリッドの視認性行列
vis_matrix = result.visibility_matrix  # (6, N) bool

# 全体の3台以上カバー率
print(f"3+ coverage: {result.stats.coverage_3plus:.1%}")

# 活動ボリューム別の統計
for activity_type, vc in result.volume_coverages.items():
    print(f"{activity_type.value}: 3+ = {vc.stats.coverage_3plus:.1%}")

# F08が角度スコアを計算する際
for j in range(result.merged_grid.shape[0]):
    visible_cam_indices = np.where(vis_matrix[:, j])[0]
    if len(visible_cam_indices) >= 2:
        # 視認可能カメラペアの角度分離を計算...
        pass
```

## 6. 制約・品質基準

### 正確性

- `visibility_matrix.sum(axis=0)` と `stats.visible_counts` が完全に一致すること
- `stats.coverage_at_least[k]` = `(visible_counts >= k).mean()` であること
- `stats.coverage_3plus` = `stats.coverage_at_least[3]` であること
- 活動ボリューム別統計の合計ポイント数が各ボリュームの `num_points` と一致すること

### 性能

- F07自身の集計処理（F06呼び出しを除く）は、N=10,000点・M=6台で100ms以内に完了すること
- 計算のボトルネックは `check_visibility_multi_camera` (F06) にあり、F07自身はNumPyの `sum(axis=0)` や `mean()` 等の集計処理のみで軽量

### エッジケース

| ケース | 期待動作 |
|--------|---------|
| cameras が空リスト | 全点の視認カメラ数=0、カバレッジ率=0.0 |
| 全点が全カメラから視認不可 | 全統計値が0 |
| 全点が全カメラから視認可能 | coverage_at_least[M] = 1.0 |
| 単一点のグリッド | 正常に統計計算 |
| volumes が空リスト | merged_grid は shape (0, 3)、統計はゼロ値 |

### スコープ外

- セルフオクルージョンは扱わない（F06と同様）
- 三角測量角度や投影サイズの評価はF08/F09の責務
- カメラ配置の良し悪しの総合判定はF10の責務
