# 機能設計書: F09 2D投影サイズスコア

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 4.1 `calculate_pixel_per_meter`、5.1 アルゴリズム |
| FR-02 | 5.2 スコア計算（min(ppm/target, 1.0)適用） |
| FR-03 | 4.2 `calculate_projection_score`、5.2 メイン処理フロー |
| FR-04 | 3.1 `ProjectionScoreResult.mean_score`、5.2 Step 6 |
| FR-05 | 4.2 の引数設計（任意の visibility_matrix を受け付ける） |

## 2. ファイル構成

```
src/camera_placement/
  evaluation/
    __init__.py             # 更新: ProjectionScoreResult, calculate_projection_score, calculate_pixel_per_meter を追加
    coverage.py             # 既存 (F07)
    angle_score.py          # 既存 (F08)
    projection_score.py     # 新規作成: F09 メインモジュール
tests/
  test_projection_score.py  # 新規作成: F09テスト
tests/results/
  F09_test_result.txt       # テスト結果
```

ファイル名は `projection_score.py` とする（`angle_score.py` との命名一貫性のため。`docs/plan.md` の `projection.py` から変更）。

## 3. データ構造

### 3.1 ProjectionScoreResult dataclass

```python
@dataclass
class ProjectionScoreResult:
    """2D投影サイズスコアの計算結果。

    point_best_scores を主要指標とし、mean_score は point_best_scores から導出する。

    Attributes:
        point_best_scores: 各点のベストスコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。視認カメラなしの点は 0.0。
        point_mean_scores: 各点の平均スコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。視認カメラなしの点は 0.0。
        point_best_ppm: 各点のベスト投影解像度 [px/m]。shape (N,), dtype=float64。
            値域 [0.0, ∞)。視認カメラなしの点は 0.0。
        mean_score: point_best_scores の算術平均。float。点数0の場合は 0.0。
    """

    point_best_scores: np.ndarray   # shape (N,), dtype=float64
    point_mean_scores: np.ndarray   # shape (N,), dtype=float64
    point_best_ppm: np.ndarray      # shape (N,), dtype=float64
    mean_score: float
```

`mean_score` は `calculate_projection_score` 内で計算してフィールドに格納する（property ではなくフィールド）。F08 の `AngleScoreResult` と同様の方針。

## 4. 関数設計

### 4.1 calculate_pixel_per_meter

```python
def calculate_pixel_per_meter(
    camera_pos: np.ndarray,
    points: np.ndarray,
    fx: float,
) -> np.ndarray:
    """1台のカメラから各点への投影解像度をバッチ計算する。

    カメラ位置から各3D点までのユークリッド距離に基づき、
    画像上の空間解像度（ピクセル/メートル）を計算する。

    Args:
        camera_pos: カメラ位置 [m]。shape (3,)。
        points: 3D点群 [m]。shape (N, 3)。
        fx: 水平焦点距離 [px]。

    Returns:
        shape (N,) の投影解像度配列 [px/m]。
        カメラが点と同一位置の場合は 0.0。
    """
```

### 4.2 calculate_projection_score

```python
def calculate_projection_score(
    cameras: list[Camera],
    grid_points: np.ndarray,
    visibility_matrix: np.ndarray,
    target_ppm: float = 500.0,
) -> ProjectionScoreResult:
    """2D投影サイズスコアを計算する。

    各グリッド点について、視認可能な全カメラの投影解像度を計算し、
    min(ppm / target_ppm, 1.0) をスコアとして集約する。

    Args:
        cameras: カメラのリスト。len = M。
        grid_points: グリッド点群 [m]。shape (N, 3)。
        visibility_matrix: 視認性行列。shape (M, N), dtype=bool。
        target_ppm: 目標投影解像度 [px/m]。正の値のみ。この値以上でスコア=1.0。

    Returns:
        ProjectionScoreResult インスタンス。

    Raises:
        ValueError: grid_points が2次元でない場合。
        ValueError: grid_points.shape[1] != 3 の場合。
        ValueError: visibility_matrix が2次元でない場合。
        ValueError: visibility_matrix.shape[0] != len(cameras) の場合。
        ValueError: visibility_matrix.shape[1] != grid_points.shape[0] の場合。
        ValueError: target_ppm <= 0 の場合。
    """
```

## 5. アルゴリズム

### 5.1 calculate_pixel_per_meter の処理フロー

```
入力: camera_pos (3,), points (N, 3), fx float
  │
  ├── Step 1: 距離ベクトルの計算
  │           diff = points - camera_pos  → shape (N, 3)
  │
  ├── Step 2: ユークリッド距離の計算
  │           distances = ‖diff‖ (axis=1)  → shape (N,)
  │
  ├── Step 3: ゼロ距離のマスクと安全な除算
  │           zero_mask = distances < 1e-10
  │           safe_distances = where(zero_mask, 1.0, distances)
  │
  ├── Step 4: 投影解像度の計算
  │           ppm = fx / safe_distances  → shape (N,)
  │
  └── Step 5: ゼロ距離の点は ppm = 0.0
              ppm[zero_mask] = 0.0
```

擬似コード:

```python
def calculate_pixel_per_meter(camera_pos, points, fx):
    diff = points - camera_pos  # (N, 3)
    distances = np.linalg.norm(diff, axis=1)  # (N,)

    zero_mask = distances < 1e-10
    safe_distances = np.where(zero_mask, 1.0, distances)

    ppm = fx / safe_distances  # (N,)
    ppm[zero_mask] = 0.0

    return ppm
```

### 5.2 calculate_projection_score の処理フロー

```
入力: cameras (M台), grid_points (N, 3), visibility_matrix (M, N) bool, target_ppm float
  │
  ├── Step 1: バリデーション
  │           - grid_points.ndim == 2
  │           - grid_points.shape[1] == 3
  │           - visibility_matrix.ndim == 2
  │           - visibility_matrix.shape[0] == len(cameras)
  │           - visibility_matrix.shape[1] == grid_points.shape[0]
  │           - target_ppm > 0
  │
  ├── Step 2: M == 0 または N == 0 の早期リターン
  │           → 全ゼロの ProjectionScoreResult を返す
  │
  ├── Step 3: 結果配列の初期化
  │           point_best_ppm = zeros(N, dtype=float64)
  │           point_score_sums = zeros(N, dtype=float64)
  │           point_num_visible = zeros(N, dtype=int)
  │
  ├── Step 4: 各カメラ i についてループ（最大 M 回。M=6 で 6 回）
  │     │
  │     ├── Step 4a: cam_visible = visibility_matrix[i]  → shape (N,) bool
  │     │
  │     ├── Step 4b: cam_visible が全て False なら次のカメラへスキップ
  │     │
  │     ├── Step 4c: ppm = calculate_pixel_per_meter(
  │     │                cameras[i].position, grid_points, cameras[i].intrinsics.fx
  │     │            )  → shape (N,)
  │     │
  │     ├── Step 4d: cam_scores = min(ppm / target_ppm, 1.0)  → shape (N,)
  │     │
  │     └── Step 4e: cam_visible な点についてのみ更新:
  │                  - improved = cam_visible & (ppm > point_best_ppm)
  │                  - point_best_ppm[improved] = ppm[improved]
  │                  - point_score_sums += cam_scores * cam_visible
  │                  - point_num_visible += cam_visible.astype(int)
  │
  ├── Step 5: point_best_scores と point_mean_scores の計算
  │           point_best_scores = min(point_best_ppm / target_ppm, 1.0)
  │           has_visible = point_num_visible > 0
  │           point_mean_scores = zeros(N, dtype=float64)
  │           point_mean_scores[has_visible] = point_score_sums[has_visible] / point_num_visible[has_visible]
  │
  ├── Step 6: mean_score の計算
  │           N > 0: mean_score = point_best_scores.mean()
  │           N == 0: mean_score = 0.0
  │
  └── Step 7: ProjectionScoreResult を返す
```

擬似コード:

```python
def calculate_projection_score(cameras, grid_points, visibility_matrix, target_ppm=500.0):
    # バリデーション
    vis = np.asarray(visibility_matrix, dtype=bool)
    pts = np.asarray(grid_points, dtype=np.float64)
    if pts.ndim != 2:
        raise ValueError(f"grid_points must be 2D, got {pts.ndim}D")
    if pts.shape[1] != 3:
        raise ValueError(f"grid_points.shape[1] must be 3, got {pts.shape[1]}")
    if vis.ndim != 2:
        raise ValueError(f"visibility_matrix must be 2D, got {vis.ndim}D")
    M = len(cameras)
    N = pts.shape[0]
    if vis.shape[0] != M:
        raise ValueError(
            f"visibility_matrix.shape[0]={vis.shape[0]} != len(cameras)={M}"
        )
    if vis.shape[1] != N:
        raise ValueError(
            f"visibility_matrix.shape[1]={vis.shape[1]} != grid_points rows={N}"
        )
    if target_ppm <= 0:
        raise ValueError(f"target_ppm must be positive, got {target_ppm}")

    # 早期リターン
    if M == 0 or N == 0:
        return ProjectionScoreResult(
            point_best_scores=np.zeros(N, dtype=np.float64),
            point_mean_scores=np.zeros(N, dtype=np.float64),
            point_best_ppm=np.zeros(N, dtype=np.float64),
            mean_score=0.0,
        )

    # 初期化
    point_best_ppm = np.zeros(N, dtype=np.float64)
    point_score_sums = np.zeros(N, dtype=np.float64)
    point_num_visible = np.zeros(N, dtype=int)

    # 各カメラをループ
    for i in range(M):
        cam_visible = vis[i]  # (N,)
        if not cam_visible.any():
            continue

        ppm = calculate_pixel_per_meter(
            cameras[i].position, pts, cameras[i].intrinsics.fx
        )  # (N,)
        cam_scores = np.minimum(ppm / target_ppm, 1.0)  # (N,)

        # ベストppmの更新
        improved = cam_visible & (ppm > point_best_ppm)
        point_best_ppm[improved] = ppm[improved]

        # 合計・カメラ数の更新
        point_score_sums += cam_scores * cam_visible
        point_num_visible += cam_visible.astype(int)

    # ベストスコア
    point_best_scores = np.minimum(point_best_ppm / target_ppm, 1.0)

    # 平均スコア
    has_visible = point_num_visible > 0
    point_mean_scores = np.zeros(N, dtype=np.float64)
    point_mean_scores[has_visible] = (
        point_score_sums[has_visible] / point_num_visible[has_visible]
    )

    # 全体スコア
    mean_score = float(point_best_scores.mean()) if N > 0 else 0.0

    return ProjectionScoreResult(
        point_best_scores=point_best_scores,
        point_mean_scores=point_mean_scores,
        point_best_ppm=point_best_ppm,
        mean_score=mean_score,
    )
```

### 5.3 データフロー図

```
CoverageResult (F07)
  │
  ├── .cameras ──────────────┐
  ├── .merged_grid ──────────┤
  └── .visibility_matrix ────┤
                             │
                             ▼
                calculate_projection_score(cameras, grid_points, visibility_matrix, target_ppm)
                             │
                             ├── for each camera i:
                             │     │
                             │     ├── cam_visible = vis[i]
                             │     │
                             │     ├── calculate_pixel_per_meter(
                             │     │       cameras[i].position, grid_points, cameras[i].intrinsics.fx
                             │     │   )  → ppm (N,)
                             │     │
                             │     ├── cam_scores = min(ppm / target_ppm, 1.0)  (N,)
                             │     │
                             │     └── update best_ppm, score_sums, num_visible
                             │
                             └── ProjectionScoreResult
                                   ├── point_best_scores  (N,)
                                   ├── point_mean_scores  (N,)
                                   ├── point_best_ppm     (N,)
                                   └── mean_score          float
```

### 5.4 ベクトル化の方針

- `calculate_pixel_per_meter` は N 点すべてに対してNumPyベクトル化演算で一括計算する
- 外側のカメラループは Python の `for` ループ。最大 M=6 回であり、オーバーヘッドは無視できる
- 各カメラに対するスコア計算と更新もNumPyベクトル化で N 点一括処理

### 5.5 F08 との構造的な差異

| 項目 | F08（角度スコア） | F09（投影スコア） |
|------|-----------------|-----------------|
| ループ対象 | カメラペア C(M,2) 回 | カメラ単体 M 回 |
| 低レベル関数の入力 | 2台のカメラ位置 | 1台のカメラ位置 + fx |
| スコア関数 | sin(angle)（パラメータフリー） | min(ppm/target, 1.0)（target_ppm パラメータ） |
| ベスト基準 | 最大 sin(angle) のペア | 最大 ppm のカメラ（=最も近いカメラ） |

## 6. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| grid_points が 2D でない | `ValueError` を送出 | F09 |
| grid_points.shape[1] != 3 | `ValueError` を送出 | F09 |
| visibility_matrix が 2D でない | `ValueError` を送出 | F09 |
| visibility_matrix.shape[0] != len(cameras) | `ValueError` を送出 | F09 |
| visibility_matrix.shape[1] != grid_points.shape[0] | `ValueError` を送出 | F09 |
| target_ppm <= 0 | `ValueError` を送出 | F09 |
| cameras が空リスト | 正常動作。M=0 で早期リターン。全スコア 0.0 | F09 |
| cameras が1台のみ | 正常動作。1台のカメラで計算 | F09 |
| grid_points が空 shape (0, 3) | 正常動作。N=0 で早期リターン。mean_score=0.0、空配列 | F09 |
| カメラが点と同一位置 | `calculate_pixel_per_meter` のゼロ除算防止で ppm=0.0 | F09 |

## 7. 境界条件

| ケース | 期待動作 |
|--------|---------|
| grid_points が空 (0, 3) | mean_score=0.0、全配列が空 (shape (0,)) |
| cameras が空 | 全 point_best_scores=0.0、mean_score=0.0 |
| cameras が1台 | best_score = mean_score（各点）。1台のカメラのスコアのみ |
| 全点が視認不可 | 全 point_best_scores=0.0 |
| 全カメラが同一位置に配置 | 全点で同じppm。best = mean（各点） |
| 点がカメラの直近 (distance ≈ 0+) | ppm → ∞、score = 1.0 (min でクランプ) |
| カメラが点と同一位置 (distance < 1e-10) | ppm = 0.0、score = 0.0 |

## 8. 設計判断

### 8.1 スコア関数に min(ppm/target_ppm, 1.0) を採用する理由

- **採用案**: クランプ線形関数 `min(ppm / target_ppm, 1.0)`
- **却下案1**: 指数関数 `1 - exp(-ppm / characteristic_ppm)`
  - 却下理由: characteristic_ppm パラメータの物理的解釈が直感的でない。線形関数は「target_ppm 以上なら十分」という単純な閾値概念を表現できる
- **却下案2**: sin ベース（F08 と同形式）
  - 却下理由: 距離と投影解像度の関係は逆比例（ppm = fx/d）であり、角度のような三角関数的な特性を持たない。sin を適用する物理的根拠がない
- **却下案3**: パラメータフリーの関数
  - 却下理由: 「何ピクセル/メートルで十分か」は応用依存であり、パラメータなしでは表現できない

### 8.2 ユークリッド距離を使用する理由（カメラ座標系の深度 z_cam ではなく）

- **採用案**: `‖point - camera_pos‖`（ユークリッド距離）
- **却下案**: `camera.world_to_camera(point)[:, 2]`（カメラ座標系の深度 z_cam）
  - 却下理由:
    - 低レベル関数がカメラの回転行列に依存しない（位置と fx のみで計算可能）
    - テスタビリティと疎結合を優先
    - FOV 79° の場合、光軸端部でユークリッド距離は深度の約 1/cos(39.5°) ≈ 1.30 倍だが、スコア指標としては十分な近似
    - F08 も同様にカメラ位置のみを使用（回転行列不使用）

### 8.3 fx（水平焦点距離）のみを使用する理由

- **採用案**: `Camera.intrinsics.fx`（水平焦点距離のピクセル換算）
- **却下案1**: `fy`（垂直焦点距離）
  - 却下理由: 本カメラでは fx = fy ≈ 1167（正方ピクセル 3µm × 3µm のため）。一般にセンサーが非正方ピクセルの場合は fx ≠ fy となりうる。fx を使う規約とすることで、異なるカメラへの拡張時にも一貫した基準となる
- **却下案2**: `sqrt(fx * fy)`（幾何平均）
  - 却下理由: コードが複雑化する割にスコア指標としてのメリットが薄い。1つの値で一貫性を保つ方が解釈しやすい
- **却下案3**: `min(fx, fy)`
  - 却下理由: 本カメラでは fx = fy なので同値。fx を直接使う方がシンプル

### 8.4 CoverageResult を引数に取らない理由

- **採用案**: `cameras`, `grid_points`, `visibility_matrix` を個別の引数で受け取る
- **却下案**: `CoverageResult` を直接受け取る
  - 却下理由: F08 と同じ。疎結合を維持し、活動ボリューム別の `VolumeCoverage` にも適用可能にする。テスト時に任意の visibility_matrix を渡せて柔軟

### 8.5 カメラ単位の Python ループを使用する理由

- **採用案**: M 回の Python `for` ループ（各反復内は NumPy ベクトル化）
- **却下案**: 全カメラを 2D テンソルで一括計算
  - 却下理由: M=6 で最大 6 回なので Python ループのオーバーヘッドは無視できる。2D テンソルは `(M, N)` のメモリが必要でコードも複雑化する。可読性を優先

### 8.6 mean_score をフィールド（property ではなく）にする理由

- F08 の `AngleScoreResult` と同じ。immutable なスナップショットとして扱い、再計算を避ける

### 8.7 target_ppm のデフォルト値 500.0 の根拠

- fx ≈ 1167 の場合、distance ≈ 2.33 m で ppm = 500（飽和境界）
- この解像度では 0.3 m の体節（前腕長など）が 150 ピクセルに投影される（高精度な 2D 検出に十分）
- 病室内（2.8 m × 3.5 m）では距離範囲 1〜5 m に対してスコア範囲 0.47〜1.0 となる。2.33 m 以内はスコア 1.0 に飽和するが、3 m 以上の遠距離点では弁別力がある
- 表：

| 距離 [m] | ppm [px/m] | スコア |
|----------|-----------|--------|
| 1.0 | 1167 | 1.000 |
| 2.0 | 583 | 1.000 |
| 2.33 | 500 | 1.000 |
| 3.0 | 389 | 0.778 |
| 4.0 | 292 | 0.583 |
| 5.0 | 233 | 0.467 |

### 8.8 カメラが点と同一位置の場合の扱い（ppm = 0.0）

- **採用案**: ppm = 0.0、score = 0.0
- **却下案**: ppm = ∞、score = 1.0
  - 却下理由: 物理的にありえない状況。安全なデフォルト値（0.0）を返すことでゼロ除算を防止。F08 の angle=0.0 と同様の方針

## 9. ログ・デバッグ設計

F09 は純粋な計算モジュールであり、ログ出力は行わない。F07、F08 と同様の方針。デバッグ時は呼び出し元でログを出力すること。

## 10. 技術スタック

- **Python**: 3.12
- **numpy**: ベクトル演算（linalg.norm, minimum 等）
- **pytest**: テスト用
- 新規ライブラリの追加は不要

## 11. 依存機能との連携

### 11.1 F02（カメラモデル）

- `Camera.position` (shape (3,), float64) を使用してカメラ位置を取得
- `Camera.intrinsics.fx` (float) を使用して水平焦点距離を取得
- インポート: `from camera_placement.models.camera import Camera`

### 11.2 F07（カバレッジ計算）

- `CoverageResult` のフィールドを展開して `calculate_projection_score` に渡す
- F09 自体は `CoverageResult` をインポートしない（疎結合）
- 使用パターン:

```python
from camera_placement.evaluation.coverage import calculate_coverage
from camera_placement.evaluation.projection_score import calculate_projection_score

result = calculate_coverage(cameras, room)
proj_result = calculate_projection_score(
    result.cameras, result.merged_grid, result.visibility_matrix
)
```

## 12. 後続機能との接続点

| 後続機能 | 使用するフィールド | 用途 |
|---------|------------------|------|
| F10 統合スコア | `ProjectionScoreResult.mean_score`、`point_best_scores` | 投影スコアとして統合品質スコアに組み込み |
| F11 可視化 | `ProjectionScoreResult.point_best_scores`、`point_best_ppm` | 投影スコアマップの色分け表示（F11の設計次第） |
| F13 配置比較 | `ProjectionScoreResult.mean_score` | 配置パターン間の投影スコア比較 |

## 13. テスト計画

テストファイル: `tests/test_projection_score.py`

### カテゴリA: calculate_pixel_per_meter（低レベル関数）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 距離 1m | cam=[0,0,0], point=[1,0,0], fx=1000 | ppm = 1000.0 | 基本計算 |
| A2 | 距離 2m | cam=[0,0,0], point=[2,0,0], fx=1000 | ppm = 500.0 | 距離の逆比例 |
| A3 | バッチ計算（複数点） | cam=[0,0,0], 3点（1m/2m/4m）, fx=1000 | ppm = [1000, 500, 250] | ベクトル化の正確性 |
| A4 | カメラが点と同一位置 | cam=[0,0,0], point=[0,0,0], fx=1000 | ppm = 0.0 | ゼロ除算防止 |
| A5 | 3D距離 | cam=[0,0,0], point=[3,4,0], fx=1000 | distance=5, ppm=200 | 3次元ユークリッド距離 |
| A6 | 実カメラの fx | cam=[0,0,0], point=[3,0,0], fx=1166.67 | ppm ≈ 388.89 | 実ハードウェア値 |

### テストA5の詳細計算

```
cam = [0, 0, 0], point = [3, 4, 0], fx = 1000
distance = sqrt(3² + 4²) = sqrt(9 + 16) = 5.0
ppm = 1000 / 5.0 = 200.0
```

### カテゴリB: calculate_projection_score（メイン関数）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | 近距離 1 台、1 点 | cam at 1m, vis=True, target=500 | score=1.0 (ppm≈1167>500) | 近距離→高スコア |
| B2 | 遠距離 1 台、1 点 | cam at 5m, vis=True, target=500 | score≈0.467 | 遠距離→低スコア |
| B3 | 2 台、異なる距離、1 点 | cam_near at 1m, cam_far at 4m, 1 point, 全可視 | best_score=1.0（近い方）、mean < best | ベストカメラ選択 |
| B4 | 部分視認 | 2 台、1 点、1 台のみ可視 | 可視カメラのスコアのみ | visibility_matrix 反映 |
| B5 | target_ppm パラメータの効果 | 同一配置、target_ppm=200 vs 500 | target=200 の方がスコア高い | パラメータ効果 |
| B6 | mean_score の検証 | 2 台、3 点 | mean_score = point_best_scores.mean() | 全体スコア |
| B7 | point_mean_scores の検証 | 2 台、1 点、全可視 | mean_score = (score_cam0 + score_cam1) / 2 | 平均スコア |

### テストB1の詳細計算

```
camera at [1, 0, 0], look_at [0, 0, 0]
point = [0, 0, 0]
distance = 1.0
fx ≈ 1166.67 (デフォルト intrinsics: 3.5mm / 0.003mm)
ppm = 1166.67 / 1.0 = 1166.67
target_ppm = 500.0
score = min(1166.67 / 500.0, 1.0) = min(2.333, 1.0) = 1.0
```

### テストB2の詳細計算

```
camera at [5, 0, 0], look_at [0, 0, 0]
point = [0, 0, 0]
distance = 5.0
fx ≈ 1166.67
ppm = 1166.67 / 5.0 = 233.33
target_ppm = 500.0
score = min(233.33 / 500.0, 1.0) = min(0.4667, 1.0) = 0.4667
```

### カテゴリC: エッジケース

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | カメラ 0 台 | cameras=[], grid=(0,3), vis=(0,0) | mean_score=0.0 | 空カメラ |
| C2 | カメラ 1 台 | 1 台、N 点、全可視 | best = mean（各点）| 1 台のみ |
| C3 | グリッド点 0 個 | M 台、grid=(0,3), vis=(M,0) | mean_score=0.0、空配列 | 空グリッド |
| C4 | 全点が視認不可 | 2 台、2 点、vis=全 False | 全 score=0.0 | 視認カメラなし |
| C5 | grid_points が 2D でない | 1D 配列 | ValueError | バリデーション |
| C6 | grid_points.shape[1] != 3 | shape (N, 2) | ValueError | バリデーション |
| C7 | visibility_matrix が 2D でない | 1D 配列 | ValueError | バリデーション |
| C8 | shape[0] 不整合 | shape[0] != len(cameras) | ValueError | バリデーション |
| C9 | shape[1] 不整合 | shape[1] != grid_points.shape[0] | ValueError | バリデーション |
| C10 | target_ppm ≤ 0 | target_ppm=-1.0 | ValueError | パラメータバリデーション |

### カテゴリD: 実環境シナリオ

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | コーナー配置 6 台 | 病室 4 コーナー上部 + 中間 2 台、小グリッド | mean_score > 0.3 | 実用配置でスコアが正 |
| D2 | 近距離配置 vs 遠距離配置 | 2 配置パターン：近い配置と遠い配置 | 近い方がスコア高い | 距離効果の反映 |
| D3 | F07 結果との連携 | calculate_coverage → calculate_projection_score | エラーなく計算完了、妥当なスコア範囲 | F07 との統合テスト |

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
```

### テスト総数: 約 24 件

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
from camera_placement.evaluation.projection_score import (
    ProjectionScoreResult,
    calculate_pixel_per_meter,
    calculate_projection_score,
)

__all__ = [
    "AngleScoreResult",
    "CoverageResult",
    "CoverageStats",
    "ProjectionScoreResult",
    "VolumeCoverage",
    "calculate_angle_score",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_pair_angles",
    "calculate_pixel_per_meter",
    "calculate_projection_score",
    "calculate_volume_coverage",
]
```
