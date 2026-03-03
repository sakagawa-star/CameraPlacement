# 機能設計書: F10 統合品質スコア

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 4.1 `calculate_quality_score`、5.1 統合スコア計算アルゴリズム |
| FR-02 | 5.1 Step 1 重みの正規化 |
| FR-03 | 3.1 `QualityScoreResult` のフィールド |
| FR-04 | 5.1 Step 3 ポイント品質スコア |
| FR-05 | 4.2 `evaluate_placement`、5.2 一括計算フロー |
| FR-06 | 5.2 Step 5 活動ボリューム別スコア、3.3 `VolumeQualityScore` |

## 2. ファイル構成

```
src/camera_placement/
  evaluation/
    __init__.py             # 更新: QualityScoreResult, EvaluationResult, VolumeQualityScore,
                            #       calculate_quality_score, evaluate_placement を追加
    coverage.py             # 既存 (F07)
    angle_score.py          # 既存 (F08)
    projection_score.py     # 既存 (F09)
    evaluator.py            # 新規作成: F10 メインモジュール
tests/
  test_evaluator.py         # 新規作成: F10テスト
tests/results/
  F10_test_result.txt       # テスト結果
```

ファイル名は `evaluator.py` とする（`docs/plan.md` の想定ファイル構成に従う）。

## 3. データ構造

### 3.1 QualityScoreResult dataclass

```python
@dataclass
class QualityScoreResult:
    """統合品質スコアの計算結果。

    Attributes:
        quality_score: 統合品質スコア。加重和。値域 [0.0, 1.0]。
        coverage_score: カバレッジスコア (coverage_3plus)。値域 [0.0, 1.0]。
        angle_score: 角度スコア (mean_score)。値域 [0.0, 1.0]。
        projection_score: 投影スコア (mean_score)。値域 [0.0, 1.0]。
        weight_coverage: 正規化後のカバレッジ重み。
        weight_angle: 正規化後の角度重み。
        weight_projection: 正規化後の投影重み。
        point_quality_scores: 各点のポイント品質スコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。
        mean_point_quality: point_quality_scores の算術平均。点数0の場合は 0.0。
    """

    quality_score: float
    coverage_score: float
    angle_score: float
    projection_score: float
    weight_coverage: float
    weight_angle: float
    weight_projection: float
    point_quality_scores: np.ndarray  # shape (N,), dtype=float64
    mean_point_quality: float
```

全フィールドを `calculate_quality_score` 内で計算し、フィールドとして格納する（property ではなくフィールド）。F08, F09 と同様の方針。

### 3.2 EvaluationResult dataclass

```python
@dataclass
class EvaluationResult:
    """一括評価の全体結果。

    evaluate_placement の戻り値。F07/F08/F09/F10 の全結果を保持する。

    Attributes:
        quality: 統合品質スコア（統合グリッド全体）。
        coverage_result: F07 のカバレッジ計算結果。
        angle_result: F08 の角度スコア計算結果。
        projection_result: F09 の投影スコア計算結果。
        volume_qualities: 活動ボリューム別の品質スコア。
    """

    quality: QualityScoreResult
    coverage_result: CoverageResult
    angle_result: AngleScoreResult
    projection_result: ProjectionScoreResult
    volume_qualities: dict[ActivityType, VolumeQualityScore]
```

### 3.3 VolumeQualityScore dataclass

```python
@dataclass
class VolumeQualityScore:
    """活動ボリューム別の品質スコア。

    Attributes:
        activity_type: 動作パターンの種別。
        quality_score: 統合品質スコア [0.0, 1.0]。
        coverage_score: カバレッジスコア (coverage_3plus) [0.0, 1.0]。
        angle_score: 角度スコア (mean_score) [0.0, 1.0]。
        projection_score: 投影スコア (mean_score) [0.0, 1.0]。
    """

    activity_type: ActivityType
    quality_score: float
    coverage_score: float
    angle_score: float
    projection_score: float
```

`VolumeQualityScore` は `QualityScoreResult` より軽量にする。ポイント品質スコア配列は含めない。理由: 活動ボリューム別の配列を全て保持するとメモリ消費が大きく、F13/F14 では活動ボリューム別のスカラースコアのみ必要。

## 4. 関数設計

### 4.1 calculate_quality_score

```python
def calculate_quality_score(
    coverage_score: float,
    angle_score: float,
    projection_score: float,
    point_angle_scores: np.ndarray,
    point_projection_scores: np.ndarray,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> QualityScoreResult:
    """統合品質スコアを計算する。

    3つのコンポーネントスコアの加重和で統合品質スコアを算出する。
    重みは内部で合計 1.0 に正規化される。

    Args:
        coverage_score: カバレッジスコア [0.0, 1.0]。
        angle_score: 角度スコア [0.0, 1.0]。
        projection_score: 投影スコア [0.0, 1.0]。
        point_angle_scores: 各点の角度ベストスコア。shape (N,), dtype=float64。
        point_projection_scores: 各点の投影ベストスコア。shape (N,), dtype=float64。
        weight_coverage: カバレッジの重み。非負。
        weight_angle: 角度スコアの重み。非負。
        weight_projection: 投影スコアの重み。非負。

    Returns:
        QualityScoreResult インスタンス。

    Raises:
        ValueError: 重みのいずれかが負の場合。
        ValueError: 重みの合計が 0 の場合。
        ValueError: point_angle_scores と point_projection_scores の長さが不一致の場合。
    """
```

### 4.2 evaluate_placement

```python
def evaluate_placement(
    cameras: list[Camera],
    room: Room,
    volumes: list[ActivityVolume] | None = None,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
    target_ppm: float = 500.0,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> EvaluationResult:
    """カメラ配置を一括評価する。

    F07（カバレッジ）→ F08（角度スコア）→ F09（投影スコア）→ F10（統合スコア）
    の全計算を実行し、結果を返す。

    Args:
        cameras: カメラのリスト。
        room: 病室モデル。
        volumes: 活動ボリューム。None の場合は自動生成。
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。

    Returns:
        EvaluationResult インスタンス。
    """
```

## 5. アルゴリズム

### 5.1 calculate_quality_score の処理フロー

```
入力: coverage_score float, angle_score float, projection_score float,
      point_angle_scores (N,), point_projection_scores (N,),
      weight_coverage float, weight_angle float, weight_projection float
  │
  ├── Step 1: 重みのバリデーションと正規化
  │           - いずれかの重みが負 → ValueError
  │           - 重みの合計が 0 → ValueError
  │           - point_angle_scores.shape[0] != point_projection_scores.shape[0] → ValueError
  │           - w_sum = weight_coverage + weight_angle + weight_projection
  │           - w_cov = weight_coverage / w_sum
  │           - w_ang = weight_angle / w_sum
  │           - w_proj = weight_projection / w_sum
  │
  ├── Step 2: 統合品質スコアの計算
  │           quality_score = w_cov * coverage_score + w_ang * angle_score + w_proj * projection_score
  │
  ├── Step 3: ポイント品質スコアの計算
  │           w_point_sum = weight_angle + weight_projection
  │           if w_point_sum > 0:
  │               w_ang_pt = weight_angle / w_point_sum
  │               w_proj_pt = weight_projection / w_point_sum
  │               point_quality = w_ang_pt * point_angle_scores + w_proj_pt * point_projection_scores
  │           else:
  │               point_quality = zeros(N)
  │
  ├── Step 4: mean_point_quality の計算
  │           N > 0: mean_point_quality = point_quality.mean()
  │           N == 0: mean_point_quality = 0.0
  │
  └── Step 5: QualityScoreResult を返す
```

擬似コード:

```python
def calculate_quality_score(
    coverage_score, angle_score, projection_score,
    point_angle_scores, point_projection_scores,
    weight_coverage=0.5, weight_angle=0.3, weight_projection=0.2,
):
    # バリデーション
    if weight_coverage < 0 or weight_angle < 0 or weight_projection < 0:
        raise ValueError("weights must be non-negative")
    w_sum = weight_coverage + weight_angle + weight_projection
    if w_sum == 0:
        raise ValueError("sum of weights must be positive")

    pt_angle = np.asarray(point_angle_scores, dtype=np.float64)
    pt_proj = np.asarray(point_projection_scores, dtype=np.float64)
    if pt_angle.shape[0] != pt_proj.shape[0]:
        raise ValueError(
            f"point_angle_scores length {pt_angle.shape[0]} != "
            f"point_projection_scores length {pt_proj.shape[0]}"
        )

    N = pt_angle.shape[0]

    # 重みの正規化
    w_cov = weight_coverage / w_sum
    w_ang = weight_angle / w_sum
    w_proj = weight_projection / w_sum

    # 統合品質スコア
    quality = w_cov * coverage_score + w_ang * angle_score + w_proj * projection_score

    # ポイント品質スコア
    w_point_sum = weight_angle + weight_projection
    if w_point_sum > 0:
        w_ang_pt = weight_angle / w_point_sum
        w_proj_pt = weight_projection / w_point_sum
        point_quality = w_ang_pt * pt_angle + w_proj_pt * pt_proj
    else:
        point_quality = np.zeros(N, dtype=np.float64)

    # mean_point_quality
    mean_pq = float(point_quality.mean()) if N > 0 else 0.0

    return QualityScoreResult(
        quality_score=quality,
        coverage_score=coverage_score,
        angle_score=angle_score,
        projection_score=projection_score,
        weight_coverage=w_cov,
        weight_angle=w_ang,
        weight_projection=w_proj,
        point_quality_scores=point_quality,
        mean_point_quality=mean_pq,
    )
```

### 5.2 evaluate_placement の処理フロー

```
入力: cameras, room, volumes, grid_spacing, near, far, target_ppm,
      weight_coverage, weight_angle, weight_projection
  │
  ├── Step 0: 重みのバリデーション（早期検出）
  │           - いずれかの重みが負 → ValueError
  │           - 重みの合計が 0 → ValueError
  │           ※ F07/F08/F09 の計算前に不正な重みを検出し、無駄な計算を防ぐ
  │
  ├── Step 1: F07 カバレッジ計算
  │           coverage_result = calculate_coverage(cameras, room, volumes, grid_spacing, near, far)
  │
  ├── Step 2: F08 角度スコア計算（統合グリッド）
  │           angle_result = calculate_angle_score(
  │               coverage_result.cameras,
  │               coverage_result.merged_grid,
  │               coverage_result.visibility_matrix,
  │           )
  │
  ├── Step 3: F09 投影スコア計算（統合グリッド）
  │           projection_result = calculate_projection_score(
  │               coverage_result.cameras,
  │               coverage_result.merged_grid,
  │               coverage_result.visibility_matrix,
  │               target_ppm,
  │           )
  │
  ├── Step 4: F10 統合品質スコア計算（統合グリッド）
  │           quality = calculate_quality_score(
  │               coverage_result.stats.coverage_3plus,
  │               angle_result.mean_score,
  │               projection_result.mean_score,
  │               angle_result.point_best_scores,
  │               projection_result.point_best_scores,
  │               weight_coverage, weight_angle, weight_projection,
  │           )
  │
  ├── Step 5: 活動ボリューム別スコア計算
  │           volume_qualities = {}
  │           volumes_list = coverage_result.volume_coverages から取得可能な ActivityVolume を参照
  │           ※ ActivityVolume.grid_points が必要なため、volumes を再利用する
  │
  │           volumes_used: calculate_coverage に渡した volumes を取得
  │           （volumes が None の場合は create_activity_volumes(room, grid_spacing) で再生成）
  │
  │           for vol in volumes_used:
  │               vc = coverage_result.volume_coverages[vol.activity_type]
  │               vol_angle = calculate_angle_score(
  │                   coverage_result.cameras, vol.grid_points, vc.visibility_matrix
  │               )
  │               vol_proj = calculate_projection_score(
  │                   coverage_result.cameras, vol.grid_points, vc.visibility_matrix, target_ppm
  │               )
  │               vol_w_sum = weight_coverage + weight_angle + weight_projection
  │               w_cov = weight_coverage / vol_w_sum
  │               w_ang = weight_angle / vol_w_sum
  │               w_proj = weight_projection / vol_w_sum
  │               vol_quality = (
  │                   w_cov * vc.stats.coverage_3plus
  │                   + w_ang * vol_angle.mean_score
  │                   + w_proj * vol_proj.mean_score
  │               )
  │               volume_qualities[vol.activity_type] = VolumeQualityScore(
  │                   activity_type=vol.activity_type,
  │                   quality_score=vol_quality,
  │                   coverage_score=vc.stats.coverage_3plus,
  │                   angle_score=vol_angle.mean_score,
  │                   projection_score=vol_proj.mean_score,
  │               )
  │
  └── Step 6: EvaluationResult を返す
```

擬似コード:

```python
def evaluate_placement(
    cameras, room, volumes=None, grid_spacing=0.2, near=0.1, far=10.0,
    target_ppm=500.0, weight_coverage=0.5, weight_angle=0.3, weight_projection=0.2,
):
    # Step 0: 重みのバリデーション（早期検出）
    if weight_coverage < 0 or weight_angle < 0 or weight_projection < 0:
        raise ValueError("weights must be non-negative")
    if weight_coverage + weight_angle + weight_projection == 0:
        raise ValueError("sum of weights must be positive")

    # Step 1: F07
    coverage_result = calculate_coverage(cameras, room, volumes, grid_spacing, near, far)

    # Step 2: F08
    angle_result = calculate_angle_score(
        coverage_result.cameras,
        coverage_result.merged_grid,
        coverage_result.visibility_matrix,
    )

    # Step 3: F09
    projection_result = calculate_projection_score(
        coverage_result.cameras,
        coverage_result.merged_grid,
        coverage_result.visibility_matrix,
        target_ppm,
    )

    # Step 4: F10
    quality = calculate_quality_score(
        coverage_result.stats.coverage_3plus,
        angle_result.mean_score,
        projection_result.mean_score,
        angle_result.point_best_scores,
        projection_result.point_best_scores,
        weight_coverage,
        weight_angle,
        weight_projection,
    )

    # Step 5: 活動ボリューム別
    # volumes を再取得（calculate_coverage 内で生成されたものと同じ条件で）
    if volumes is None:
        volumes_used = create_activity_volumes(room, grid_spacing)
    else:
        volumes_used = volumes

    # 重みの正規化（活動ボリューム別スコア計算用）
    w_sum = weight_coverage + weight_angle + weight_projection
    # w_sum > 0 は calculate_quality_score のバリデーションで保証済み
    w_cov = weight_coverage / w_sum
    w_ang = weight_angle / w_sum
    w_proj = weight_projection / w_sum

    volume_qualities: dict[ActivityType, VolumeQualityScore] = {}
    for vol in volumes_used:
        act_type = vol.activity_type
        if act_type not in coverage_result.volume_coverages:
            continue
        vc = coverage_result.volume_coverages[act_type]
        vol_angle = calculate_angle_score(
            coverage_result.cameras, vol.grid_points, vc.visibility_matrix
        )
        vol_proj = calculate_projection_score(
            coverage_result.cameras, vol.grid_points, vc.visibility_matrix, target_ppm
        )
        vol_quality = (
            w_cov * vc.stats.coverage_3plus
            + w_ang * vol_angle.mean_score
            + w_proj * vol_proj.mean_score
        )
        volume_qualities[act_type] = VolumeQualityScore(
            activity_type=act_type,
            quality_score=vol_quality,
            coverage_score=vc.stats.coverage_3plus,
            angle_score=vol_angle.mean_score,
            projection_score=vol_proj.mean_score,
        )

    return EvaluationResult(
        quality=quality,
        coverage_result=coverage_result,
        angle_result=angle_result,
        projection_result=projection_result,
        volume_qualities=volume_qualities,
    )
```

### 5.3 データフロー図

```
cameras, room
    │
    ▼
calculate_coverage (F07)
    │
    ├── CoverageResult
    │     ├── .cameras
    │     ├── .merged_grid (N, 3)
    │     ├── .visibility_matrix (M, N) bool
    │     ├── .stats.coverage_3plus → coverage_score
    │     └── .volume_coverages
    │
    ├──────────────────────────────────────────────────┐
    │                                                  │
    ▼                                                  ▼
calculate_angle_score (F08)                calculate_projection_score (F09)
    │                                                  │
    ├── AngleScoreResult                    ├── ProjectionScoreResult
    │     ├── .mean_score → angle_score     │     ├── .mean_score → projection_score
    │     └── .point_best_scores (N,)       │     └── .point_best_scores (N,)
    │                                                  │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
              calculate_quality_score (F10)
                       │
                       ▼
              QualityScoreResult
                ├── quality_score = w_cov * cov + w_ang * ang + w_proj * proj
                ├── coverage_score, angle_score, projection_score
                ├── weight_coverage, weight_angle, weight_projection
                ├── point_quality_scores (N,)
                └── mean_point_quality

活動ボリューム別:
    for each volume in volumes:
        vc = coverage_result.volume_coverages[activity_type]
        │
        ├── calculate_angle_score(cameras, vol.grid_points, vc.visibility_matrix)
        ├── calculate_projection_score(cameras, vol.grid_points, vc.visibility_matrix, target_ppm)
        │
        └── VolumeQualityScore
              ├── quality_score (加重和)
              ├── coverage_score
              ├── angle_score
              └── projection_score
```

## 6. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| weight のいずれかが負 | `ValueError` を送出 | F10 (`calculate_quality_score`) |
| weight の合計が 0 | `ValueError` を送出 | F10 (`calculate_quality_score`) |
| point_angle_scores と point_projection_scores の長さ不一致 | `ValueError` を送出 | F10 (`calculate_quality_score`) |
| 入力スコア（coverage_score, angle_score, projection_score）が [0.0, 1.0] 外 | バリデーションしない。呼び出し元の責務。F07/F08/F09 が返すスコアは常に [0.0, 1.0] | F10（バリデーション不要） |
| point_angle_scores, point_projection_scores の値が [0.0, 1.0] 外 | バリデーションしない。呼び出し元の責務 | F10（バリデーション不要） |
| cameras が空リスト | F07/F08/F09 が正常に全ゼロを返す。F10 も quality_score=0.0。volume_qualities は 3 キー（WALKING, SEATED, SUPINE）で全て quality_score=0.0 | F07/F08/F09 |
| grid_points が空 | F07/F08/F09 が正常に空配列を返す。F10 も quality_score=0.0 | F07/F08/F09 |
| target_ppm <= 0 | `calculate_projection_score` が `ValueError` | F09 |
| F07/F08/F09 内部エラー | 各モジュールで ValueError が伝播 | F07/F08/F09 |

## 7. 境界条件

| ケース | 期待動作 |
|--------|---------|
| 全コンポーネントスコアが 0.0 | quality_score = 0.0 |
| 全コンポーネントスコアが 1.0 | quality_score = 1.0 |
| cameras が空 | quality_score = 0.0, point_quality_scores = shape (0,) or all zeros |
| cameras が 1 台 | coverage_3plus = 0.0, angle_mean = 0.0 → quality_score = w_proj * projection_score |
| grid_points が空 (0, 3) | quality_score = 0.0, point_quality_scores shape (0,) |
| weight_coverage=1, weight_angle=0, weight_projection=0 | quality_score = coverage_score, point_quality = zeros(N) |
| weight_angle=0, weight_projection=0 | point_quality = zeros(N)（w_point_sum = 0 のケース） |
| point 配列の長さが 0 | mean_point_quality = 0.0 |

## 8. 設計判断

### 8.1 加重和を統合方式に採用する理由

- **採用案**: 加重和 `quality = w1*s1 + w2*s2 + w3*s3`
- **却下案1**: 乗算 `quality = s1^w1 * s2^w2 * s3^w3`（幾何平均ベース）
  - 却下理由: いずれかのスコアが 0.0 の場合に全体が 0.0 になる。カバレッジが低い初期配置でも角度・投影の部分的な改善を反映したいため、加算方式の方が最適化に適している
- **却下案2**: 最小値 `quality = min(s1, s2, s3)`
  - 却下理由: 3つのスコアのバランスを重み付けで調整できない。F14（最適化）のグラデーション（連続的な改善）が得られにくい

### 8.2 デフォルト重みの根拠

- `w_cov=0.5, w_angle=0.3, w_proj=0.2`
- CLAUDE.md の品質指標の優先順位に基づく:
  1. **カバレッジ（最重要）**: 「各キーポイントが常に3台以上のカメラから観測される」が最終目標。w=0.5
  2. **角度分離（重要）**: 三角測量精度に直接影響。15°未満で大幅低下。w=0.3
  3. **投影サイズ（補助的）**: 2D検出精度に影響するが、病室内の距離範囲（1〜5m）では極端な劣化は起きにくい。w=0.2
- ユーザーが重みを変更可能（F14 での最適化時にチューニングできる）

### 8.3 ポイント品質スコアにカバレッジを含めない理由

- **採用案**: ポイント品質 = w_angle_norm * angle + w_proj_norm * projection（カバレッジ含めない）
- **却下案**: ポイント品質 = w_cov * (visible_count/M) + w_angle * angle + w_proj * projection
  - 却下理由: カバレッジは「何台のカメラから見えるか」という離散値（0〜M）であり、[0,1] に正規化するには M で割る必要がある。しかし M=6 台で 3 台以上を目標とする場合 3/6=0.5 が閾値となり、スコアの解釈が直感的でない。カバレッジは全体統計（coverage_3plus）で十分評価できるため、ポイントレベルでは角度と投影の品質に注力する方が有用

### 8.4 VolumeQualityScore を QualityScoreResult の軽量版にする理由

- **採用案**: `VolumeQualityScore` はスカラーフィールドのみ（point 配列なし）
- **却下案**: 各活動ボリュームにも `QualityScoreResult` を使う
  - 却下理由: 3 つの活動ボリュームそれぞれに point_quality_scores 配列を持つとメモリ消費が大きい。F13（配置比較）では活動ボリューム別のスカラースコアのみ使用。必要なら呼び出し元が個別に `calculate_quality_score` を呼べばよい

### 8.5 evaluate_placement で volumes を再生成する理由

- `calculate_coverage` 内部で volumes が生成されるが、`CoverageResult` には volumes オブジェクト自体（`grid_points` を持つ `ActivityVolume`）は保持されない
- 活動ボリューム別のF08/F09 計算には `ActivityVolume.grid_points` が必要
- そのため `evaluate_placement` 内で `volumes` が `None` の場合に `create_activity_volumes(room, grid_spacing)` を再度呼び出す
- `create_activity_volumes` は決定論的（同じ入力に対して同じ出力）なので、結果の一貫性は保証される

### 8.6 calculate_quality_score を CoverageResult 等に依存しない理由

- **採用案**: スカラー値と点配列を個別引数で受け取る
- **却下案**: CoverageResult, AngleScoreResult, ProjectionScoreResult を引数に取る
  - 却下理由: F08, F09 と同様の疎結合方針。テスト時に任意のスコア値を渡せて柔軟。`evaluate_placement` がラッパーとして結合を担当する

### 8.7 活動ボリューム別スコアの重みを全体と同一にする理由

- **採用案**: 活動ボリューム別スコアの重みも `evaluate_placement` に渡された重みを使用
- **却下案**: 活動ボリュームごとに異なる重みを使用
  - 却下理由: 重みのパラメータ数が増えて複雑化する。F13（配置比較）では同一重みで比較することが公平。必要なら呼び出し元が活動ボリームごとに `calculate_quality_score` を異なる重みで呼べばよい

## 9. ログ・デバッグ設計

F10 は純粋な計算モジュールであり、ログ出力は行わない。F07/F08/F09 と同様の方針。デバッグ時は呼び出し元でログを出力すること。

## 10. 技術スタック

- **Python**: 3.12
- **numpy** (>=1.26): ベクトル演算（加重和の計算等）。pyproject.toml で管理
- **pytest**: テスト用
- 新規ライブラリの追加は不要

## 11. 依存機能との連携

### 11.1 F07（カバレッジ計算）

- `calculate_coverage(cameras, room, volumes, grid_spacing, near, far)` を呼び出し
- `CoverageResult.stats.coverage_3plus` をカバレッジスコアとして使用
- `CoverageResult.volume_coverages[activity_type].stats.coverage_3plus` を活動ボリューム別カバレッジスコアとして使用
- インポート: `from camera_placement.evaluation.coverage import CoverageResult, calculate_coverage`

### 11.2 F08（三角測量角度スコア）

- `calculate_angle_score(cameras, grid_points, visibility_matrix)` を呼び出し
- `AngleScoreResult.mean_score` を角度スコアとして使用
- `AngleScoreResult.point_best_scores` をポイント品質スコアの入力に使用
- インポート: `from camera_placement.evaluation.angle_score import AngleScoreResult, calculate_angle_score`

### 11.3 F09（2D投影サイズスコア）

- `calculate_projection_score(cameras, grid_points, visibility_matrix, target_ppm)` を呼び出し
- `ProjectionScoreResult.mean_score` を投影スコアとして使用
- `ProjectionScoreResult.point_best_scores` をポイント品質スコアの入力に使用
- インポート: `from camera_placement.evaluation.projection_score import ProjectionScoreResult, calculate_projection_score`

### 11.4 F03（活動ボリューム）

- `create_activity_volumes(room, grid_spacing)` を活動ボリューム再取得に使用
- `ActivityVolume.grid_points` を活動ボリューム別スコア計算に使用
- インポート: `from camera_placement.models.activity import ActivityType, ActivityVolume, create_activity_volumes`

### 11.5 F02（カメラモデル）、F01（空間モデル）

- `Camera`, `Room` を型ヒントに使用
- インポート: `from camera_placement.models.camera import Camera`
- インポート: `from camera_placement.models.environment import Room`

## 12. 後続機能との接続点

| 後続機能 | 使用するフィールド | 用途 |
|---------|------------------|------|
| F13 配置比較 | `EvaluationResult.quality.quality_score`, `.quality.coverage_score`, `.quality.angle_score`, `.quality.projection_score`, `.volume_qualities` | 配置パターン間の比較表生成。活動ボリューム別の比較 |
| F14 目的関数 | `EvaluationResult.quality.quality_score` | 最適化の目的関数値。`evaluate_placement` をワンコールで評価 |
| F11 可視化 | `EvaluationResult.quality.point_quality_scores`, `.coverage_result`, `.angle_result`, `.projection_result` | 品質スコアマップの色分け表示（F11 の設計次第） |

F13 での使用イメージ:

```python
from camera_placement.evaluation.evaluator import evaluate_placement

# 複数の配置パターンを評価
results = {}
for name, cameras in placement_patterns.items():
    results[name] = evaluate_placement(cameras, room)

# 比較表の生成
for name, result in results.items():
    q = result.quality
    print(f"{name}: total={q.quality_score:.3f} "
          f"cov={q.coverage_score:.3f} "
          f"ang={q.angle_score:.3f} "
          f"proj={q.projection_score:.3f}")
```

F14 での使用イメージ:

```python
from camera_placement.evaluation.evaluator import evaluate_placement

def objective(camera_params):
    cameras = params_to_cameras(camera_params)
    result = evaluate_placement(cameras, room)
    return -result.quality.quality_score  # 最小化のため負にする
```

## 13. テスト計画

テストファイル: `tests/test_evaluator.py`

### カテゴリA: calculate_quality_score（コアロジック）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | デフォルト重みでの基本計算 | cov=1.0, ang=0.8, proj=0.6, pt_ang=[0.8], pt_proj=[0.6], default weights | quality = 0.5*1.0 + 0.3*0.8 + 0.2*0.6 = 0.86 | 基本動作 |
| A2 | 全スコア 0.0 | cov=0, ang=0, proj=0, pt_ang=[0], pt_proj=[0] | quality = 0.0 | ゼロケース |
| A3 | 全スコア 1.0 | cov=1, ang=1, proj=1, pt_ang=[1], pt_proj=[1] | quality = 1.0 | 最大ケース |
| A4 | カスタム重み | cov=0.8, ang=0.6, proj=0.4, weights=(1.0, 1.0, 1.0) | quality = (0.8+0.6+0.4)/3 = 0.6 | 均等重み |
| A5 | 重みの正規化 | cov=1.0, ang=0.0, proj=0.0, weights=(2, 1, 1) | quality = 0.5*1.0 + 0.25*0.0 + 0.25*0.0 = 0.5 | 正規化検証 |
| A6 | coverage のみ重み | cov=0.8, ang=0.6, proj=0.4, weights=(1, 0, 0) | quality = 0.8 | 単一コンポーネント |
| A7 | angle のみ重み | cov=0.8, ang=0.6, proj=0.4, weights=(0, 1, 0) | quality = 0.6 | 単一コンポーネント |
| A8 | projection のみ重み | cov=0.8, ang=0.6, proj=0.4, weights=(0, 0, 1) | quality = 0.4 | 単一コンポーネント |

### テストA1の詳細計算

```
coverage_score = 1.0, angle_score = 0.8, projection_score = 0.6
weights = (0.5, 0.3, 0.2)  → 合計 1.0、正規化不要
quality = 0.5 * 1.0 + 0.3 * 0.8 + 0.2 * 0.6
        = 0.5 + 0.24 + 0.12
        = 0.86

point_angle = [0.8], point_proj = [0.6]
w_point_sum = 0.3 + 0.2 = 0.5
w_ang_pt = 0.3 / 0.5 = 0.6
w_proj_pt = 0.2 / 0.5 = 0.4
point_quality = [0.6 * 0.8 + 0.4 * 0.6] = [0.48 + 0.24] = [0.72]
mean_point_quality = 0.72
```

### カテゴリB: ポイント品質スコア

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | 複数点のポイント品質 | pt_ang=[1.0, 0.5, 0.0], pt_proj=[0.5, 1.0, 0.0] | point_quality = [0.8, 0.7, 0.0] (default weights) | 点ごとの加重和 |
| B2 | coverage のみ重み → point_quality = zeros | weights=(1,0,0), pts 3点 | point_quality = [0, 0, 0] | w_point_sum=0 |
| B3 | angle のみ重み → point_quality = angle | weights=(0,1,0), pt_ang=[0.8, 0.4] | point_quality = [0.8, 0.4] | angle のみ反映 |
| B4 | 空の点配列 | pt_ang=[], pt_proj=[] | point_quality shape (0,), mean=0.0 | 空配列 |
| B5 | mean_point_quality の検証 | pt_ang=[0.8, 0.4], pt_proj=[0.6, 0.2] | mean_point_quality = mean(point_quality) | 平均値 |

### テストB1の詳細計算

```
weights = (0.5, 0.3, 0.2)
w_point_sum = 0.3 + 0.2 = 0.5
w_ang_pt = 0.3 / 0.5 = 0.6
w_proj_pt = 0.2 / 0.5 = 0.4

point[0]: 0.6 * 1.0 + 0.4 * 0.5 = 0.6 + 0.2 = 0.8
point[1]: 0.6 * 0.5 + 0.4 * 1.0 = 0.3 + 0.4 = 0.7
point[2]: 0.6 * 0.0 + 0.4 * 0.0 = 0.0
```

### カテゴリC: エッジケース・バリデーション

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | 負の重み（coverage） | weight_coverage=-1 | ValueError | バリデーション |
| C2 | 負の重み（angle） | weight_angle=-0.1 | ValueError | バリデーション |
| C3 | 負の重み（projection） | weight_projection=-1 | ValueError | バリデーション |
| C4 | 重み合計 0 | weights=(0, 0, 0) | ValueError | バリデーション |
| C5 | point 配列の長さ不一致 | pt_ang shape (3,), pt_proj shape (2,) | ValueError | バリデーション |
| C6 | 正規化後の重みが結果に保持される | weights=(2, 1, 1) | w_cov=0.5, w_ang=0.25, w_proj=0.25 | 重み保持 |

### カテゴリD: evaluate_placement（一括計算）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | 基本動作（コーナー配置） | 6台コーナー配置、デフォルト設定 | quality_score > 0、各コンポーネント > 0 | 一括計算の動作 |
| D2 | 結果構造の検証 | 任意配置 | EvaluationResult の全フィールドが設定されている | データ構造 |
| D3 | coverage_result の保持 | 任意配置 | result.coverage_result が CoverageResult | 中間結果保持 |
| D4 | angle_result の保持 | 任意配置 | result.angle_result が AngleScoreResult | 中間結果保持 |
| D5 | projection_result の保持 | 任意配置 | result.projection_result が ProjectionScoreResult | 中間結果保持 |
| D6 | volume_qualities のキー | デフォルト volumes | WALKING, SEATED, SUPINE の 3 キー | 活動ボリューム別 |
| D7 | volume_qualities のスコア妥当性 | コーナー配置 | 各活動ボリュームの quality_score が [0.0, 1.0] 範囲内 | 値域チェック |
| D8 | スコアの一貫性 | コーナー配置 | quality_score == w_cov*cov + w_ang*ang + w_proj*proj (atol=1e-10) | 加重和の検証 |
| D9 | カメラ 0 台 | cameras=[] | quality_score = 0.0 | 空カメラ |
| D10 | カスタム重み | weights=(1, 1, 1) | 均等重みで計算 | 重みパラメータ伝播 |
| D11 | target_ppm パラメータ | target_ppm=200 | projection_score が target_ppm=500 より高い | パラメータ伝播 |

### カテゴリE: 実環境シナリオ

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | コーナー配置 vs 密集配置 | 2つの配置パターン | コーナー配置のスコアが密集配置より高い | 配置品質の弁別力 |
| E2 | 臥位のスコアが他より低い | コーナー配置 | volume_qualities[SUPINE].quality_score < volume_qualities[WALKING].quality_score | 物理的妥当性 |

### テスト用ヘルパー

```python
def _create_corner_cameras() -> list[Camera]:
    """テスト用6台コーナー配置カメラ。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([2.6, 0.2, 2.3], center),
        create_camera([0.2, 3.3, 2.3], center),
        create_camera([2.6, 3.3, 2.3], center),
        create_camera([1.4, 0.2, 2.3], center),
        create_camera([1.4, 3.3, 2.3], center),
    ]

def _create_clustered_cameras() -> list[Camera]:
    """テスト用密集配置カメラ（同一壁面に集中）。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([0.4, 0.2, 2.3], center),
        create_camera([0.6, 0.2, 2.3], center),
        create_camera([0.8, 0.2, 2.3], center),
        create_camera([1.0, 0.2, 2.3], center),
        create_camera([1.2, 0.2, 2.3], center),
    ]
```

### テスト総数: 約 28 件

## 14. `evaluation/__init__.py` の更新内容

```python
"""evaluation パッケージ: カバレッジ・品質評価機能。"""

from camera_placement.evaluation.angle_score import (
    AngleScoreResult,
    calculate_angle_score,
    calculate_pair_angles,
)
from camera_placement.evaluation.coverage import (
    CoverageResult,
    CoverageStats,
    VolumeCoverage,
    calculate_coverage,
    calculate_coverage_stats,
    calculate_volume_coverage,
)
from camera_placement.evaluation.evaluator import (
    EvaluationResult,
    QualityScoreResult,
    VolumeQualityScore,
    calculate_quality_score,
    evaluate_placement,
)
from camera_placement.evaluation.projection_score import (
    ProjectionScoreResult,
    calculate_pixel_per_meter,
    calculate_projection_score,
)

__all__ = [
    "AngleScoreResult",
    "CoverageResult",
    "CoverageStats",
    "EvaluationResult",
    "ProjectionScoreResult",
    "QualityScoreResult",
    "VolumeCoverage",
    "VolumeQualityScore",
    "calculate_angle_score",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_pair_angles",
    "calculate_pixel_per_meter",
    "calculate_projection_score",
    "calculate_quality_score",
    "calculate_volume_coverage",
    "evaluate_placement",
]
```
