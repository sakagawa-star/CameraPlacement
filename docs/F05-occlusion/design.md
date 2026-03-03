# F05: ベッドオクルージョン判定 — 機能設計書

## ファイル構成

```
src/camera_placement/
  core/
    __init__.py           # check_bed_occlusion, check_bed_occlusion_multi_camera を export
    occlusion.py          # F05 メインモジュール
tests/
  test_occlusion.py       # F05テスト
tests/results/
  F05_test_result.txt     # テスト結果
```

`src/camera_placement/core/` ディレクトリはF04と共有する（F04で新規作成）。

## データ構造（関数設計）

### 内部関数

```python
def _ray_aabb_intersect(
    origins: np.ndarray,
    directions: np.ndarray,
    aabb_min: np.ndarray,
    aabb_max: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """レイ群とAABBの交差パラメータをslab法で計算する。

    各レイについて交差区間 [t_enter, t_exit] を返す。
    交差しない場合は t_enter > t_exit となる。

    Args:
        origins: レイの始点。shape (N, 3)。
        directions: レイの方向ベクトル（正規化不要）。shape (N, 3)。
        aabb_min: AABBの最小座標。shape (3,)。
        aabb_max: AABBの最大座標。shape (3,)。

    Returns:
        t_enter: shape (N,)。交差区間の開始パラメータ。
        t_exit: shape (N,)。交差区間の終了パラメータ。
    """
```

### メイン関数

```python
def check_bed_occlusion(
    camera_position: np.ndarray,
    points: np.ndarray,
    bed_aabb: AABB,
    eps: float = 1e-6,
) -> np.ndarray:
    """カメラから各点への視線がベッドAABBと交差するか判定する。

    slab法（Kay-Kajiya法）によるレイ-AABB交差判定を行う。
    レイの origin=camera_position、endpoint=point とし、
    パラメータ t ∈ (eps, 1-eps) の範囲でAABBと交差する場合にオクルージョンありと判定する。

    Args:
        camera_position: カメラ位置。shape (3,)。
        points: 対象点群。shape (N, 3) または (3,)。
        bed_aabb: ベッドのAABB。
        eps: 端点除外の許容誤差。デフォルト 1e-6。

    Returns:
        shape (N,) の bool配列。True = オクルージョンあり。
    """
```

### 便利関数

```python
def check_bed_occlusion_multi_camera(
    cameras: list[Camera],
    points: np.ndarray,
    bed_aabb: AABB,
    eps: float = 1e-6,
) -> np.ndarray:
    """複数カメラについてベッドオクルージョンをバッチ判定する。

    Args:
        cameras: カメラのリスト。len = M。
        points: 対象点群。shape (N, 3)。
        bed_aabb: ベッドのAABB。
        eps: 端点除外の許容誤差。

    Returns:
        shape (M, N) の bool配列。occluded[i, j] = True ならカメラiから点jはオクルージョンあり。
    """
```

### `core/__init__.py` の内容

```python
"""core パッケージ: 視認性判定のコア機能。"""

from camera_placement.core.frustum import FrustumChecker
from camera_placement.core.occlusion import (
    check_bed_occlusion,
    check_bed_occlusion_multi_camera,
)

__all__ = [
    "FrustumChecker",
    "check_bed_occlusion",
    "check_bed_occlusion_multi_camera",
]
```

## アルゴリズム

### slab法（Kay-Kajiya法）の詳細

レイを `P(t) = origin + t * direction` と定義する。ここで:
- `origin = camera_position` (shape (N,3) にブロードキャスト)
- `direction = point - camera_position` (shape (N,3))
- `t = 0` がカメラ位置、`t = 1` が対象点

AABBは3つの軸（X, Y, Z）それぞれについて「スラブ」（2つの平行な平面で挟まれた区間）を持つ。各軸 k (k=0,1,2) について:

```
t_k_min = (aabb_min[k] - origin[k]) / direction[k]
t_k_max = (aabb_max[k] - origin[k]) / direction[k]
```

direction[k] が負の場合、t_k_min と t_k_max を入れ替える:
```
if direction[k] < 0:
    t_k_min, t_k_max = t_k_max, t_k_min
```

全軸について:
```
t_enter = max(t_0_min, t_1_min, t_2_min)
t_exit  = min(t_0_max, t_1_max, t_2_max)
```

交差条件: `t_enter <= t_exit`（レイがAABBと交差する）

### オクルージョン判定条件

レイがAABBと交差し、かつ交差区間 `[t_enter, t_exit]` が `(eps, 1-eps)` と重なる場合にオクルージョンありと判定する。

```python
occluded = (t_enter < 1 - eps) & (t_exit > eps) & (t_enter <= t_exit)
```

この条件の意味:
- `t_enter <= t_exit`: レイがAABBと幾何学的に交差する
- `t_exit > eps`: 交差がカメラ位置より先にある（カメラ背後の交差を除外）
- `t_enter < 1 - eps`: 交差が対象点より手前にある（対象点の先の交差を除外）

### direction成分がゼロの場合の処理

方向ベクトルの成分が0の場合（レイが特定の軸に平行）:

```python
eps_zero = 1e-12  # ゼロ判定の閾値
is_parallel = np.abs(directions) < eps_zero  # (N, 3) bool

# 安全な逆数計算（ゼロ除算回避）
safe_dir = np.where(is_parallel, 1.0, directions)
inv_dir = 1.0 / safe_dir

# 各軸のt値計算
t1 = (aabb_min - origins) * inv_dir  # (N, 3)
t2 = (aabb_max - origins) * inv_dir  # (N, 3)

# direction < 0 の場合にスワップ（np.minimum/maximumで自動対応）
t_min_per_axis = np.minimum(t1, t2)  # (N, 3)
t_max_per_axis = np.maximum(t1, t2)  # (N, 3)

# 平行レイの処理
inside_slab = (origins >= aabb_min) & (origins <= aabb_max)  # (N, 3) bool
t_min_per_axis = np.where(is_parallel & inside_slab, -np.inf, t_min_per_axis)
t_max_per_axis = np.where(is_parallel & inside_slab, np.inf, t_max_per_axis)
t_min_per_axis = np.where(is_parallel & ~inside_slab, np.inf, t_min_per_axis)
t_max_per_axis = np.where(is_parallel & ~inside_slab, -np.inf, t_max_per_axis)

# 全軸でのenter/exit
t_enter = np.max(t_min_per_axis, axis=1)  # (N,)
t_exit = np.min(t_max_per_axis, axis=1)   # (N,)
```

### カメラ位置 = 対象点の場合

`direction = [0, 0, 0]` となるため、全軸で `is_parallel = True`。
direction のノルムが eps_zero 未満の場合は、オクルージョンなしとする:

```python
zero_direction = np.linalg.norm(directions, axis=1) < eps_zero  # (N,) bool
occluded = occluded & ~zero_direction
```

## 設計判断

### t パラメータ範囲を (eps, 1-eps) とする理由

- t=0: カメラ自身がAABB境界上にある場合、数値誤差で「交差あり」と判定される誤りを防ぐ
- t=1: 対象点がAABB境界上にある場合（例: ベッド上面 Z=0.2 にあるキーポイント）、その点は物理的に露出しているためオクルージョンなしとすべき
- eps = 1e-6 はメートル単位で 0.001 mm であり、実用上十分な精度

### 内部関数 `_ray_aabb_intersect` を分離する理由

- t_enter, t_exit を直接返すことで、テストや将来の拡張（例: 交差距離の計算）に再利用可能
- check_bed_occlusion はこの関数のラッパーとして、t範囲のフィルタリングのみを担当

### `check_bed_occlusion_multi_camera` を提供する理由

- F06/F07 で「M台のカメラ x N個の点」の全組み合わせを一括判定する用途が想定される
- 内部実装はカメラごとに `check_bed_occlusion` を呼ぶ単純なループ（カメラ数は最大6台、ボトルネックにならない）

### occluded の意味を True=遮蔽 とする理由

- 後続のF06では `visible = in_frustum & ~occluded` となるため、遮蔽をTrueで返す方が自然
- 関数名も `check_bed_occlusion`（遮蔽の有無を調べる）で意味が明確

## F01/F02との連携方法

### F01（空間モデル）

- `Room.bed` (AABB) を `bed_aabb` パラメータとして受け取る
- AABB の `min_point`, `max_point` 属性を直接使用する

### F02（カメラモデル）

- `Camera.position` を `camera_position` パラメータとして使用する
- `check_bed_occlusion_multi_camera` では Camera オブジェクトのリストを受け取り、各 `.position` を使用
- カメラの姿勢（FOV等）はオクルージョン判定に不要なため、position のみを使用

## 後続機能との接続点

| 後続機能 | 使用する機能 | 用途 |
|---------|------------|------|
| F06 視認性統合 | `check_bed_occlusion()` | 1台のカメラに対するオクルージョン判定 |
| F06 視認性統合 | `check_bed_occlusion_multi_camera()` | M台一括のオクルージョン判定 |

## テスト計画

テストファイル: `tests/test_occlusion.py`

| # | カテゴリ | テストケース | カメラ位置 | 対象点 | 期待値 |
|---|---------|-------------|-----------|--------|--------|
| 1 | 基本 | レイがベッドを貫通する | (0.0, 0.0, 2.0) | (1.4, 2.5, 0.0) | True（遮蔽あり） |
| 2 | 基本 | レイがベッドを通らない | (0.0, 0.0, 2.0) | (0.0, 0.0, 0.0) | False（遮蔽なし） |
| 3 | 端点除外 | 対象点がベッド上面 (Z=0.2) | (0.0, 0.0, 2.0) | (1.4, 2.5, 0.2) | False（遮蔽なし） |
| 4 | 端点除外 | カメラ真上からベッド上面の点 | (1.4, 2.5, 2.0) | (1.4, 2.5, 0.2) | False（遮蔽なし） |
| 5 | 貫通 | カメラ真上からベッド下（床面） | (1.4, 2.5, 2.0) | (1.4, 2.5, 0.0) | True（遮蔽あり） |
| 6 | 非交差 | レイがベッドの横を通過 | (0.0, 2.5, 1.0) | (0.8, 2.5, 0.1) | False（遮蔽なし） |
| 7 | 軸平行 | Z軸方向のみ（ベッドXY外） | (0.5, 0.5, 2.0) | (0.5, 0.5, 0.0) | False（遮蔽なし） |
| 8 | 軸平行 | Z軸方向のみ（ベッドXY内で貫通） | (1.4, 2.5, 2.0) | (1.4, 2.5, 0.0) | True（遮蔽あり） |
| 9 | バッチ | 複数点（遮蔽あり/なし混在） | (0.0, 0.0, 2.0) | 混在点群 | 混在結果 |
| 10 | shape | 単一点入力 shape (3,) | (0.0, 0.0, 2.0) | shape (3,) | shape (1,) の結果 |
| 11 | エッジ | カメラ位置 = 対象点 | (1.4, 2.5, 2.0) | (1.4, 2.5, 2.0) | False（遮蔽なし） |
| 12 | 内部 | 対象点がベッドAABB内部 | (0.0, 0.0, 2.0) | (1.4, 2.5, 0.1) | True（遮蔽あり） |
| 13 | multi | 複数カメラの一括判定 | カメラ2台 | 点群 | shape (2, N) |
| 14 | 境界 | レイがAABBの辺をかすめる | ベッド角付近 | ベッド角の延長線上 | False（遮蔽なし） |
| 15 | 全非遮蔽 | 全ての点が遮蔽なし | ベッド外のカメラ | ベッドと反対方向 | 全 False |
| 16 | 内部関数 | _ray_aabb_intersect の t値検証 | 既知の入力 | t_enter, t_exit が正しい値 |

## 依存ライブラリ

- numpy（ベクトル演算、バッチ処理） — 追加済み
- dataclasses（標準ライブラリ）
- pytest（テスト用） — 追加済み
- F01: AABB（`camera_placement.models.environment` からインポート）
- F02: Camera（`camera_placement.models.camera` からインポート、multi_camera関数の型ヒント用）

新規ライブラリの追加は不要。
