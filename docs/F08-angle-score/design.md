# 機能設計書: F08 三角測量角度スコア

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 4.1 `calculate_pair_angles`、5.1 アルゴリズム |
| FR-02 | 5.2 ペアスコア計算（sin適用） |
| FR-03 | 4.2 `calculate_angle_score`、5.2 メイン処理フロー |
| FR-04 | 3.1 `AngleScoreResult.mean_score`、5.2 Step 7 |
| FR-05 | 4.2 の引数設計（任意の visibility_matrix を受け付ける） |

## 2. ファイル構成

```
src/camera_placement/
  evaluation/
    __init__.py       # 更新: AngleScoreResult, calculate_angle_score, calculate_pair_angles を追加
    coverage.py       # 既存 (F07)
    angle_score.py    # 新規作成: F08 メインモジュール
tests/
  test_angle_score.py # 新規作成: F08テスト
tests/results/
  F08_test_result.txt # テスト結果
```

## 3. データ構造

### 3.1 AngleScoreResult dataclass

```python
@dataclass
class AngleScoreResult:
    """角度スコアの計算結果。

    point_best_scores を主要指標とし、mean_score は point_best_scores から導出する。

    Attributes:
        point_best_scores: 各点のベストペアスコア (sin(angle))。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。有効ペアなしの点は 0.0。
        point_mean_scores: 各点の平均ペアスコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。有効ペアなしの点は 0.0。
        point_best_angles: 各点のベストペア角度 [rad]。shape (N,), dtype=float64。
            値域 [0.0, π]。有効ペアなしの点は 0.0。
        point_num_pairs: 各点の有効ペア数。shape (N,), dtype=int。
        mean_score: point_best_scores の算術平均。float。点数0の場合は 0.0。
    """

    point_best_scores: np.ndarray   # shape (N,), dtype=float64
    point_mean_scores: np.ndarray   # shape (N,), dtype=float64
    point_best_angles: np.ndarray   # shape (N,), dtype=float64
    point_num_pairs: np.ndarray     # shape (N,), dtype=int
    mean_score: float
```

`mean_score` は `calculate_angle_score` 内で計算してフィールドに格納する（property ではなくフィールド）。理由: F07 の `CoverageStats` とは異なり、一次データ (`point_best_scores`) から常に再計算する必要がないため。

## 4. 関数設計

### 4.1 calculate_pair_angles

```python
def calculate_pair_angles(
    camera_pos_a: np.ndarray,
    camera_pos_b: np.ndarray,
    points: np.ndarray,
) -> np.ndarray:
    """2台のカメラの視線角度差を全点に対してバッチ計算する。

    各点について、カメラAからの視線ベクトルとカメラBからの視線ベクトルの
    間の角度を計算する。

    Args:
        camera_pos_a: カメラA位置 [m]。shape (3,)。
        camera_pos_b: カメラB位置 [m]。shape (3,)。
        points: 3D点群 [m]。shape (N, 3)。

    Returns:
        shape (N,) の角度配列 [rad]。値域 [0, π]。
        カメラが点と同一位置の場合は 0.0。
    """
```

### 4.2 calculate_angle_score

```python
def calculate_angle_score(
    cameras: list[Camera],
    grid_points: np.ndarray,
    visibility_matrix: np.ndarray,
) -> AngleScoreResult:
    """三角測量角度スコアを計算する。

    各グリッド点について、視認可能な全カメラペアの角度分離を計算し、
    sin(angle) をスコアとして集約する。

    Args:
        cameras: カメラのリスト。len = M。
        grid_points: グリッド点群 [m]。shape (N, 3)。
        visibility_matrix: 視認性行列。shape (M, N), dtype=bool。

    Returns:
        AngleScoreResult インスタンス。

    Raises:
        ValueError: grid_points が2次元でない場合。
        ValueError: grid_points.shape[1] != 3 の場合。
        ValueError: visibility_matrix が2次元でない場合。
        ValueError: visibility_matrix.shape[0] != len(cameras) の場合。
        ValueError: visibility_matrix.shape[1] != grid_points.shape[0] の場合。
    """
```

## 5. アルゴリズム

### 5.1 calculate_pair_angles の処理フロー

```
入力: camera_pos_a (3,), camera_pos_b (3,), points (N, 3)
  │
  ├── Step 1: 視線ベクトルの計算
  │           v_a = points - camera_pos_a  → shape (N, 3)
  │           v_b = points - camera_pos_b  → shape (N, 3)
  │
  ├── Step 2: ノルムの計算
  │           norm_a = ||v_a|| (axis=1)  → shape (N,)
  │           norm_b = ||v_b|| (axis=1)  → shape (N,)
  │
  ├── Step 3: 内積と cos(angle) の計算
  │           dot_product = sum(v_a * v_b, axis=1)  → shape (N,)
  │           denom = norm_a * norm_b  → shape (N,)
  │           ゼロ除算防止: denom < 1e-10 の場合は denom = 1.0 に置換
  │           cos_angle = dot_product / denom  → shape (N,)
  │
  ├── Step 4: 数値誤差対策
  │           cos_angle = clip(cos_angle, -1.0, 1.0)
  │
  ├── Step 5: 角度の計算
  │           angles = arccos(cos_angle)  → shape (N,)
  │
  └── Step 6: カメラが点と同一位置のケース
              (norm_a < 1e-10) | (norm_b < 1e-10) の点は angles = 0.0
```

擬似コード:

```python
def calculate_pair_angles(camera_pos_a, camera_pos_b, points):
    v_a = points - camera_pos_a  # (N, 3)
    v_b = points - camera_pos_b  # (N, 3)

    norm_a = np.linalg.norm(v_a, axis=1)  # (N,)
    norm_b = np.linalg.norm(v_b, axis=1)  # (N,)

    denom = norm_a * norm_b  # (N,)
    zero_mask = denom < 1e-10
    safe_denom = np.where(zero_mask, 1.0, denom)

    dot_product = np.sum(v_a * v_b, axis=1)  # (N,)
    cos_angle = dot_product / safe_denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    angles = np.arccos(cos_angle)  # (N,)
    angles[zero_mask] = 0.0

    return angles
```

### 5.2 calculate_angle_score の処理フロー

```
入力: cameras (M台), grid_points (N, 3), visibility_matrix (M, N) bool
  │
  ├── Step 1: バリデーション
  │           - grid_points.ndim == 2
  │           - grid_points.shape[1] == 3
  │           - visibility_matrix.ndim == 2
  │           - visibility_matrix.shape[0] == len(cameras)
  │           - visibility_matrix.shape[1] == grid_points.shape[0]
  │
  ├── Step 2: M < 2 または N == 0 の早期リターン
  │           → 全ゼロの AngleScoreResult を返す
  │
  ├── Step 3: 結果配列の初期化
  │           point_best_scores = zeros(N, dtype=float64)
  │           point_score_sums = zeros(N, dtype=float64)
  │           point_num_pairs = zeros(N, dtype=int)
  │           point_best_angles = zeros(N, dtype=float64)
  │
  ├── Step 4: カメラ位置の配列化
  │           cam_positions = array([c.position for c in cameras])  → (M, 3)
  │
  ├── Step 5: 全カメラペア (i, j) where i < j についてループ
  │     │     （最大 C(M, 2) 回。M=6 で 15 回）
  │     │
  │     ├── Step 5a: pair_visible = visibility_matrix[i] & visibility_matrix[j]
  │     │            → shape (N,) bool
  │     │
  │     ├── Step 5b: pair_visible が全て False なら次のペアへスキップ
  │     │
  │     ├── Step 5c: angles = calculate_pair_angles(
  │     │                cam_positions[i], cam_positions[j], grid_points
  │     │            )  → shape (N,)
  │     │
  │     ├── Step 5d: pair_scores = sin(angles)  → shape (N,)
  │     │
  │     └── Step 5e: pair_visible な点についてのみ更新:
  │                  - improved = pair_visible & (pair_scores > point_best_scores)
  │                  - point_best_scores[improved] = pair_scores[improved]
  │                  - point_best_angles[improved] = angles[improved]
  │                  - point_score_sums += pair_scores * pair_visible
  │                  - point_num_pairs += pair_visible.astype(int)
  │
  ├── Step 6: point_mean_scores の計算
  │           has_pairs = point_num_pairs > 0
  │           point_mean_scores = zeros(N, dtype=float64)
  │           point_mean_scores[has_pairs] = point_score_sums[has_pairs] / point_num_pairs[has_pairs]
  │
  ├── Step 7: mean_score の計算
  │           N > 0: mean_score = point_best_scores.mean()
  │           N == 0: mean_score = 0.0
  │
  └── Step 8: AngleScoreResult を返す
```

擬似コード:

```python
def calculate_angle_score(cameras, grid_points, visibility_matrix):
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

    # 早期リターン
    if M < 2 or N == 0:
        return AngleScoreResult(
            point_best_scores=np.zeros(N, dtype=np.float64),
            point_mean_scores=np.zeros(N, dtype=np.float64),
            point_best_angles=np.zeros(N, dtype=np.float64),
            point_num_pairs=np.zeros(N, dtype=int),
            mean_score=0.0,
        )

    # 初期化
    point_best_scores = np.zeros(N, dtype=np.float64)
    point_score_sums = np.zeros(N, dtype=np.float64)
    point_num_pairs = np.zeros(N, dtype=int)
    point_best_angles = np.zeros(N, dtype=np.float64)

    # カメラ位置配列
    cam_positions = np.array([c.position for c in cameras])  # (M, 3)

    # 全ペアをループ
    for i in range(M):
        for j in range(i + 1, M):
            pair_visible = vis[i] & vis[j]  # (N,)
            if not pair_visible.any():
                continue

            angles = calculate_pair_angles(
                cam_positions[i], cam_positions[j], pts
            )  # (N,)
            pair_scores = np.sin(angles)  # (N,)

            # ベストスコアの更新
            improved = pair_visible & (pair_scores > point_best_scores)
            point_best_scores[improved] = pair_scores[improved]
            point_best_angles[improved] = angles[improved]

            # 合計・ペア数の更新
            point_score_sums += pair_scores * pair_visible
            point_num_pairs += pair_visible.astype(int)

    # 平均ペアスコア
    has_pairs = point_num_pairs > 0
    point_mean_scores = np.zeros(N, dtype=np.float64)
    point_mean_scores[has_pairs] = (
        point_score_sums[has_pairs] / point_num_pairs[has_pairs]
    )

    # 全体スコア
    mean_score = float(point_best_scores.mean()) if N > 0 else 0.0

    return AngleScoreResult(
        point_best_scores=point_best_scores,
        point_mean_scores=point_mean_scores,
        point_best_angles=point_best_angles,
        point_num_pairs=point_num_pairs,
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
                calculate_angle_score(cameras, grid_points, visibility_matrix)
                             │
                             ├── cam_positions = [c.position for c in cameras]  (M, 3)
                             │
                             ├── for each pair (i, j) where i < j:
                             │     │
                             │     ├── pair_visible = vis[i] & vis[j]
                             │     │
                             │     ├── calculate_pair_angles(
                             │     │       cam_positions[i], cam_positions[j], grid_points
                             │     │   )  → angles (N,)
                             │     │
                             │     ├── pair_scores = sin(angles)  (N,)
                             │     │
                             │     └── update best_scores, best_angles, score_sums, num_pairs
                             │
                             └── AngleScoreResult
                                   ├── point_best_scores  (N,)
                                   ├── point_mean_scores  (N,)
                                   ├── point_best_angles  (N,)
                                   ├── point_num_pairs    (N,)
                                   └── mean_score         float
```

### 5.4 ベクトル化の方針

- `calculate_pair_angles` は N 点すべてに対してNumPyベクトル化演算で一括計算する
- 外側のカメラペアループは Python の `for` ループ。最大 C(6,2)=15 回であり、オーバーヘッドは無視できる
- 各ペアに対する `sin(angles)` 計算とスコア更新もNumPyベクトル化で N 点一括処理

## 6. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| grid_points が 2D でない | `ValueError` を送出 | F08 |
| grid_points.shape[1] != 3 | `ValueError` を送出 | F08 |
| visibility_matrix が 2D でない | `ValueError` を送出 | F08 |
| visibility_matrix.shape[0] != len(cameras) | `ValueError` を送出 | F08 |
| visibility_matrix.shape[1] != grid_points.shape[0] | `ValueError` を送出 | F08 |
| cameras が空リスト | 正常動作。M=0 < 2 で早期リターン。全スコア 0.0 | F08 |
| cameras が1台のみ | 正常動作。M=1 < 2 で早期リターン。全スコア 0.0 | F08 |
| grid_points が空 shape (0, 3) | 正常動作。N=0 で早期リターン。mean_score=0.0、空配列 | F08 |
| カメラが点と同一位置 | `calculate_pair_angles` のゼロ除算防止で angle=0.0 | F08 |

## 7. 境界条件

| ケース | 期待動作 |
|--------|---------|
| grid_points が空 (0, 3) | mean_score=0.0、全配列が空 (shape (0,)) |
| cameras が空 | 全 point_best_scores=0.0、mean_score=0.0 |
| cameras が1台 | ペアなし。全 point_best_scores=0.0 |
| 全点が1台以下のカメラからのみ視認 | 全 point_best_scores=0.0 |
| 全カメラが同一方向から観測 (angle ≈ 0) | point_best_scores ≈ 0.0 |
| 2台のカメラが完全に90°で観測 | point_best_scores = 1.0 |
| 2台のカメラが反対方向 (angle = π) | point_best_scores ≈ 0.0 (sin(π) ≈ 0) |

## 8. 設計判断

### 8.1 スコア関数に sin(angle) を採用する理由

- **採用案**: `sin(angle)`
- **却下案1**: `min(angle, π-angle) / (π/2)` (線形関数)
  - 却下理由: 三角測量の幾何学的誤差は `1/sin(angle)` に比例するため、`sin` を使うのが物理的に最も正当。線形関数は誤差特性を反映しない
- **却下案2**: ガウス関数 (90°中心)
  - 却下理由: 分散σのハイパーパラメータ選定が必要。`sin` はパラメータフリーで自然

### 8.2 ベストペアスコアを主要指標とする理由

- **採用案**: 各点のベストペアスコア（最大 `sin(angle)`）を主要指標 (`mean_score` の計算元)
- **却下案**: 平均ペアスコアを主要指標とする
  - 却下理由: 三角測量は最も良いカメラペアで行えば十分な精度が得られる。6台中1ペアでも良好な角度があれば実用上問題ない。平均は低角度の不要ペアに引きずられ、配置の良さを過小評価する

### 8.3 CoverageResult を引数に取らない理由

- **採用案**: `cameras`, `grid_points`, `visibility_matrix` を個別の引数で受け取る
- **却下案**: `CoverageResult` を直接受け取る
  - 却下理由: `CoverageResult` への結合度を下げ、活動ボリューム別の `VolumeCoverage` の `visibility_matrix` にも適用可能にする。テスト時にも任意の visibility_matrix を渡せて柔軟

### 8.4 角度計算を全点一括でベクトル化する理由

- **採用案**: `calculate_pair_angles` で N 点一括ベクトル化
- **却下案**: 点ごとにPythonループ
  - 却下理由: N=5,000、ペア数15 で最大 75,000 回の Python ループは遅い。NumPy ベクトル化で数桁高速化できる

### 8.5 ペアループに Python for ループを使う理由

- **採用案**: `C(M, 2)` 回の Python `for` ループ（各反復内はNumPyベクトル化）
- **却下案**: 全ペアを 3D テンソルで一括計算
  - 却下理由: M=6 で最大 15 ペアなので Python ループのオーバーヘッドは無視できる。3D テンソルは `(15, N, 3)` のメモリが必要でコードも複雑化する。可読性を優先

### 8.6 mean_score をフィールド（property ではなく）にする理由

- **採用案**: `mean_score` を `calculate_angle_score` 内で計算し、フィールドとして格納
- **却下案**: `point_best_scores` から property で導出
  - 却下理由: `AngleScoreResult` は immutable なスナップショットとして扱う。property にすると毎回 mean() を再計算するが、結果は変わらないので冗長な計算になる

## 9. ログ・デバッグ設計

F08 は純粋な計算モジュールであり、ログ出力は行わない。F07 と同様の方針。デバッグ時は呼び出し元でログを出力すること。

## 10. 技術スタック

- **Python**: 3.12
- **numpy**: ベクトル演算（arccos, sin, clip, linalg.norm 等）
- **itertools**: 不使用（二重ループで十分）
- **pytest**: テスト用
- 新規ライブラリの追加は不要

## 11. 依存機能との連携

### 10.1 F02（カメラモデル）

- `Camera.position` (shape (3,), float64) を使用してカメラ位置を取得
- インポート: `from camera_placement.models.camera import Camera`

### 10.2 F07（カバレッジ計算）

- `CoverageResult` のフィールドを展開して `calculate_angle_score` に渡す
- F08 自体は `CoverageResult` をインポートしない（疎結合）
- 使用パターン:

```python
from camera_placement.evaluation.coverage import calculate_coverage
from camera_placement.evaluation.angle_score import calculate_angle_score

result = calculate_coverage(cameras, room)
angle_result = calculate_angle_score(
    result.cameras, result.merged_grid, result.visibility_matrix
)
```

## 12. 後続機能との接続点

| 後続機能 | 使用するフィールド | 用途 |
|---------|------------------|------|
| F10 統合スコア | `AngleScoreResult.mean_score`、`point_best_scores` | 角度スコアとして統合品質スコアに組み込み |
| F11 可視化 | `AngleScoreResult.point_best_scores`、`point_best_angles` | 角度スコアマップの色分け表示（F11の設計次第） |
| F13 配置比較 | `AngleScoreResult.mean_score` | 配置パターン間の角度スコア比較 |

## 13. テスト計画

テストファイル: `tests/test_angle_score.py`

### カテゴリA: calculate_pair_angles（低レベル関数）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 90° 角度分離 | cam_a=[1,0,0], cam_b=[0,1,0], point=[0,0,0] | angle = π/2 | 理想角度 |
| A2 | 0° 角度分離（同一方向） | cam_a=[0,0,0], cam_b=[1,0,0], point=[2,0,0] | angle = 0 | 最悪ケース（同方向） |
| A3 | 180° 角度分離（反対方向） | cam_a=[1,0,0], cam_b=[-1,0,0], point=[0,0,0] | angle = π | 反対方向 |
| A4 | 60° 角度分離 | cam_a=[1,0,0], cam_b=[0.5, √3/2, 0], point=[0,0,0] | angle = π/3 | 中間角度の精度検証 |
| A5 | バッチ計算（複数点） | 2台のカメラ、3点（90°/0°/60°） | 各点の角度が個別計算と一致 | ベクトル化の正確性 |
| A6 | カメラが点と同一位置 | cam_a=[0,0,0], cam_b=[1,0,0], point=[0,0,0] | angle = 0.0 | ゼロ除算防止 |
| A7 | 3D空間の角度 | cam_a=[0,0,0], cam_b=[0,0,1], point=[1,0,0.5] | arccos による手動計算値 | 3次元の正確性 |

### テストA1の詳細計算

```
cam_a = [1, 0, 0], cam_b = [0, 1, 0], point = [0, 0, 0]
v_a = point - cam_a = [-1, 0, 0]
v_b = point - cam_b = [0, -1, 0]
dot(v_a, v_b) = 0
|v_a| = 1, |v_b| = 1
cos(angle) = 0 / 1 = 0
angle = arccos(0) = π/2
```

### テストA4の詳細計算

```
cam_a = [1, 0, 0], cam_b = [0.5, √3/2, 0], point = [0, 0, 0]
v_a = [-1, 0, 0]
v_b = [-0.5, -√3/2, 0]
dot(v_a, v_b) = 0.5
|v_a| = 1, |v_b| = 1
cos(angle) = 0.5
angle = arccos(0.5) = π/3
```

### カテゴリB: calculate_angle_score（メイン関数）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | 2台カメラ、90°配置、1点 | cam_a=[1,0,0], cam_b=[0,1,0], point=[0,0,0], vis=[[True],[True]] | best_score=1.0, best_angle=π/2, num_pairs=1 | 理想ケース |
| B2 | 2台カメラ、同一方向、1点 | cam_a=[0,0,0], cam_b=[1,0,0], point=[10,0,0], vis=[[True],[True]] | best_score ≈ 0.0 | 最悪ケース |
| B3 | 3台カメラ、1点、全視認 | 3台、1点、全True | num_pairs=3、best_scoreは3ペア中の最大 | 複数ペアの集約 |
| B4 | 3台カメラ、1点、部分視認 | 3台中2台のみ視認 | num_pairs=1 | visibility_matrix の反映 |
| B5 | 複数点で異なるスコア | 3台、2点、各点で視認カメラが異なる | 各点のスコアが個別に正しい | 点ごとの独立計算 |
| B6 | point_mean_scores の検証 | 3台、1点、全視認可能 | mean_score = (s1+s2+s3)/3 | 平均スコアの計算 |
| B7 | mean_score の検証 | 2台、3点 | mean_score = point_best_scores.mean() | 全体スコア |

### テストB3の詳細

```
3台カメラ: cam_0=[1,0,0], cam_1=[0,1,0], cam_2=[-1,0,0]
1点: [0, 0, 0]
全視認可能: vis = [[True],[True],[True]]

ペア(0,1): v_a=[-1,0,0], v_b=[0,-1,0] → angle=π/2, score=1.0
ペア(0,2): v_a=[-1,0,0], v_b=[1,0,0] → angle=π, score=sin(π)≈0.0
ペア(1,2): v_a=[0,-1,0], v_b=[1,0,0] → angle=π/2, score=1.0

best_score = 1.0 (ペア(0,1)またはペア(1,2))
mean_score = (1.0 + 0.0 + 1.0) / 3 ≈ 0.667
num_pairs = 3
```

### カテゴリC: エッジケース

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | カメラ0台 | cameras=[], grid=(0,3), vis=(0,0) | mean_score=0.0 | 空カメラ |
| C2 | カメラ1台 | 1台、N点、vis=(1,N) | 全score=0.0（ペアなし） | ペア不足 |
| C3 | グリッド点0個 | M台、grid=(0,3), vis=(M,0) | mean_score=0.0、空配列 | 空グリッド |
| C4 | 全点が1台以下からのみ視認 | 各列の True 数 ≤ 1 | 全score=0.0 | 三角測量不可 |
| C5 | grid_points が 2D でない | 1D配列 | ValueError | バリデーション |
| C6 | grid_points.shape[1] != 3 | shape (N, 2) | ValueError | バリデーション |
| C7 | visibility_matrix が 2D でない | 1D配列 | ValueError | バリデーション |
| C8 | shape[0] 不整合 | shape[0] != len(cameras) | ValueError | バリデーション |
| C9 | shape[1] 不整合 | shape[1] != grid_points.shape[0] | ValueError | バリデーション |

### カテゴリD: 実環境シナリオ

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | コーナー配置6台 | 病室4コーナー上部+中間2台、小グリッド | mean_score > 0.3 | 実用配置でスコアが正 |
| D2 | 密集配置（悪い配置） | 同一壁面に6台密集 | mean_score が D1 より有意に低い | 角度分離の差が反映される |
| D3 | F07結果との連携 | calculate_coverage → calculate_angle_score | エラーなく計算完了、妥当なスコア範囲 | F07との統合テスト |

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

__all__ = [
    "AngleScoreResult",
    "CoverageResult",
    "CoverageStats",
    "VolumeCoverage",
    "calculate_angle_score",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_pair_angles",
    "calculate_volume_coverage",
]
```
