# F06: 視認性統合 — 機能設計書

## ファイル構成

```
src/camera_placement/
  core/
    __init__.py           # check_visibility, check_visibility_multi_camera を追加 export
    visibility.py         # F06 メインモジュール（新規作成）
tests/
  test_visibility.py      # F06テスト（新規作成）
tests/results/
  F06_test_result.txt     # テスト結果
```

`src/camera_placement/core/` ディレクトリはF04で作成済み。`visibility.py` を新規追加する。

## データ構造（関数設計）

### メイン関数

```python
def check_visibility(
    camera: Camera,
    points: np.ndarray,
    bed_aabb: AABB,
    near: float = 0.1,
    far: float = 10.0,
    eps: float = 1e-6,
) -> np.ndarray:
    """1台のカメラから各点が視認可能かを判定する。

    視錐台内判定（F04）とベッドオクルージョン判定（F05）を統合する。
    visible = is_in_frustum AND NOT is_occluded

    Args:
        camera: F02のCameraインスタンス。
        points: 対象点群。shape (N, 3) または (3,)。ワールド座標 [m]。
        bed_aabb: ベッドのAABB。Room.bed から取得。
        near: ニアクリップ距離 [m]。FrustumCheckerに渡す。
        far: ファークリップ距離 [m]。FrustumCheckerに渡す。
        eps: オクルージョン判定の端点除外許容誤差。

    Returns:
        shape (N,) の bool配列。True = 視認可能。
    """
```

### 便利関数

```python
def check_visibility_multi_camera(
    cameras: list[Camera],
    points: np.ndarray,
    bed_aabb: AABB,
    near: float = 0.1,
    far: float = 10.0,
    eps: float = 1e-6,
) -> np.ndarray:
    """複数カメラから各点が視認可能かを一括判定する。

    Args:
        cameras: カメラのリスト。len = M。
        points: 対象点群。shape (N, 3) または (3,)。ワールド座標 [m]。
        bed_aabb: ベッドのAABB。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        eps: オクルージョン判定の端点除外許容誤差。

    Returns:
        shape (M, N) の bool配列。visibility[i, j] = True ならカメラiから点jが視認可能。
    """
```

### `core/__init__.py` の更新後の内容

```python
"""core パッケージ: 視認性判定のコア機能。"""

from camera_placement.core.frustum import FrustumChecker
from camera_placement.core.occlusion import (
    check_bed_occlusion,
    check_bed_occlusion_multi_camera,
)
from camera_placement.core.visibility import (
    check_visibility,
    check_visibility_multi_camera,
)

__all__ = [
    "FrustumChecker",
    "check_bed_occlusion",
    "check_bed_occlusion_multi_camera",
    "check_visibility",
    "check_visibility_multi_camera",
]
```

## アルゴリズム

### `check_visibility` の処理フロー

```
入力: camera, points, bed_aabb, near, far, eps
  │
  ├── Step 1: FrustumChecker(camera=camera, near=near, far=far) を生成
  │
  ├── Step 2: frustum_checker.is_visible(points) → in_frustum (N,) bool
  │           （F04内部で: ワールド→カメラ座標変換、depth判定、FOV判定）
  │
  ├── Step 3: check_bed_occlusion(camera.position, points, bed_aabb, eps) → occluded (N,) bool
  │           （F05内部で: レイ生成、slab法によるAABB交差判定）
  │
  └── Step 4: visible = in_frustum & ~occluded → (N,) bool を返す
```

擬似コード:
```python
def check_visibility(camera, points, bed_aabb, near=0.1, far=10.0, eps=1e-6):
    frustum_checker = FrustumChecker(camera=camera, near=near, far=far)
    in_frustum = frustum_checker.is_visible(points)
    occluded = check_bed_occlusion(camera.position, points, bed_aabb, eps)
    return in_frustum & ~occluded
```

### `check_visibility_multi_camera` の処理フロー

```
入力: cameras (M台), points (N,3), bed_aabb, near, far, eps
  │
  ├── Step 1: points の shape を正規化（(3,) → (1,3)）して N を確定
  │
  ├── Step 2: result = np.zeros((M, N), dtype=bool) を初期化
  │
  ├── Step 3: for i, cam in enumerate(cameras):
  │             result[i] = check_visibility(cam, points, bed_aabb, near, far, eps)
  │
  └── Step 4: result (M, N) bool を返す
```

擬似コード:
```python
def check_visibility_multi_camera(cameras, points, bed_aabb, near=0.1, far=10.0, eps=1e-6):
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    n_points = pts.shape[0]
    m_cameras = len(cameras)
    result = np.zeros((m_cameras, n_points), dtype=bool)
    for i, cam in enumerate(cameras):
        result[i] = check_visibility(cam, pts, bed_aabb, near, far, eps)
    return result
```

### データフロー図

```
cameras (list[Camera])      points (N,3)      bed_aabb (AABB)
    │                           │                  │
    │   ┌───────────────────────┼──────────────────┤
    │   │                       │                  │
    ▼   ▼                       ▼                  ▼
[カメラi] ──→ FrustumChecker ──→ is_visible(points) ──→ in_frustum_i (N,) bool
    │                           │                  │
    │                           ▼                  ▼
    └──────→ check_bed_occlusion(cam.position, points, bed_aabb) ──→ occluded_i (N,) bool
                                │
                                ▼
                    visible_i = in_frustum_i & ~occluded_i (N,) bool
                                │
                                ▼
                         result[i] = visible_i
                                │
                                ▼ (全カメラ完了後)
                    visibility_matrix (M, N) bool
```

## エラー処理

F06は薄い統合レイヤーであるため、独自のバリデーションは最小限とする。

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| near < 0, far <= near | FrustumChecker.__post_init__ で ValueError | F04 |
| points の shape 不正 | FrustumChecker.is_visible / check_bed_occlusion で処理 | F04/F05 |
| camera の position == look_at | Camera.__post_init__ で ValueError | F02 |
| cameras が空リスト | shape (0, N) の結果を返す（正常動作） | F06 |
| points が空 shape (0, 3) | shape (M, 0) の結果を返す（正常動作） | F06 |

## 設計判断

### モジュール関数方式を採用する理由

- F06は状態を持たない。FrustumChecker の生成は関数内部で行い、呼び出し側に不要な複雑さを見せない
- F04はカメラに紐づく状態（near/far）を持つためクラス方式が適切だったが、F06は単に F04 と F05 を組み合わせるだけの薄いレイヤーであり、クラスにする利点がない

### FrustumChecker を関数内で毎回生成する理由

- FrustumChecker の生成コストは `__post_init__` のバリデーションのみで、実質的にゼロ
- check_visibility_multi_camera でカメラ毎に FrustumChecker を生成するが、M=6 のループで性能問題にならない
- 呼び出し側に FrustumChecker のライフサイクル管理を求めないことで、インターフェースがシンプルになる

### 戻り値の意味を True=視認可能 とする理由

- F04の `is_visible` は True=視野内（可視）
- F05の `check_bed_occlusion` は True=遮蔽あり（不可視）
- F06は「視認可能か」を最終判定する機能であり、True=視認可能が最も自然
- F07での使用: `visible_count = visibility_matrix.sum(axis=0)` で直感的に視認カメラ数が得られる

### check_visibility_multi_camera で内部ループとする理由

- カメラ数は最大6台。ループのオーバーヘッドは無視できる
- NumPyのバッチ処理は点群 N 方向で行われている（F04/F05内部）。カメラ方向のバッチ化は複雑になるだけでメリットがない
- F05 の `check_bed_occlusion_multi_camera` と同じ設計パターン

## F04/F05との連携方法

### F04（視錐台判定）

- `FrustumChecker(camera=camera, near=near, far=far)` を `check_visibility` 内で生成
- `frustum_checker.is_visible(points)` を呼び出して (N,) bool を取得
- FrustumChecker は Camera の world_to_camera() メソッドと intrinsics.hfov/vfov プロパティを内部で使用

### F05（ベッドオクルージョン判定）

- `check_bed_occlusion(camera.position, points, bed_aabb, eps)` を呼び出して (N,) bool を取得
- Camera.position のみを使用（カメラの姿勢はオクルージョン判定に不要）
- bed_aabb は Room.bed から取得する AABB オブジェクト

## 後続機能との接続点

| 後続機能 | 使用する機能 | 用途 |
|---------|------------|------|
| F07 カバレッジ計算 | `check_visibility_multi_camera()` | 6台全カメラの視認性行列を取得し、各点の視認カメラ数を算出 |

F07での使用パターン:
```python
from camera_placement.core import check_visibility_multi_camera

visibility_matrix = check_visibility_multi_camera(cameras, grid_points, room.bed)
# visibility_matrix: shape (6, N) bool

visible_count = visibility_matrix.sum(axis=0)    # (N,) int: 各点の視認カメラ数
coverage_3plus = (visible_count >= 3).mean()      # 3台以上のカバレッジ率
```

## テスト計画

テストファイル: `tests/test_visibility.py`

### カテゴリA: 基本動作（check_visibility）

| # | テストケース | カメラ | 対象点 | 期待値 | 検証意図 |
|---|-------------|--------|--------|--------|---------|
| A1 | 視錐台内かつ遮蔽なし | pos=[0.2, 0.2, 2.0], look_at=[1.4, 1.75, 0.5] | [0.5, 0.5, 0.0]（ベッド外の床面） | True | 基本的な視認可能ケース |
| A2 | 視錐台外 | pos=[0.2, 0.2, 2.0], look_at=[0.0, 0.0, 0.0] | [2.6, 3.3, 0.5]（カメラの視野外） | False | 視錐台外のフィルタリング |
| A3 | 視錐台内かつ遮蔽あり | pos=[0.2, 0.2, 0.1], look_at=[1.4, 2.5, 0.1] | [1.4, 2.5, 0.0]（ベッド下） | False | オクルージョンによる視認不可 |
| A4 | ベッド上面の点（遮蔽なし） | pos=[1.4, 2.5, 2.0], look_at=[1.4, 2.5, 0.0] | [1.4, 2.5, 0.2]（ベッド上面 Z=0.2） | True | ベッド上面の点は遮蔽されない |
| A5 | near未満の距離 | pos=[1.4, 1.75, 1.0], look_at=[1.4, 1.75, 0.0] | near=0.1で [1.4, 1.75, 0.95]（距離0.05m） | False | ニアクリップ判定 |
| A6 | far超の距離 | pos=[0.2, 0.2, 2.0], look_at=[2.6, 3.3, 0.0] | far=1.0で [2.6, 3.3, 0.0]（距離>1.0） | False | ファークリップ判定 |

### カテゴリB: エッジケース（check_visibility）

| # | テストケース | 詳細 | 期待値 |
|---|-------------|------|--------|
| B1 | 単一点入力 shape (3,) | points = np.array([0.5, 0.5, 0.0]) | shape (1,) の結果 |
| B2 | バッチ処理（視認可/不可混在） | 5点: 視錐台内遮蔽なし、視錐台外、遮蔽あり の混在 | 正しいbool配列 |
| B3 | カスタム near/far | near=0.5, far=3.0 で判定 | パラメータが反映される |
| B4 | カスタム eps | eps=0.01 で判定 | パラメータが反映される |

### カテゴリC: 複数カメラ（check_visibility_multi_camera）

| # | テストケース | 詳細 | 期待値 |
|---|-------------|------|--------|
| C1 | 結果のshape検証 | 3台カメラ、4点 | shape (3, 4) |
| C2 | 各カメラの独立性 | 2台のカメラを異なる方向に配置。一方のみ見える点を用意 | カメラ毎に異なる結果 |
| C3 | 視認カメラ数の計算（F07接続テスト） | 6台カメラ、複数点。visibility_matrix.sum(axis=0) が期待値と一致 | 各点の視認カメラ数が正しい |
| C4 | 空のカメラリスト | cameras=[] | shape (0, N) |
| C5 | 単一カメラ | cameras=[cam1] | shape (1, N)。check_visibility と同じ結果 |

### カテゴリD: F04/F05との整合性

| # | テストケース | 詳細 | 期待値 |
|---|-------------|------|--------|
| D1 | F04単体との整合性 | 遮蔽がない設定（ベッドを部屋外に配置）でcheck_visibilityの結果がFrustumChecker.is_visibleと一致 | 完全一致 |
| D2 | F05単体との整合性 | 全点が視錐台内の設定でcheck_visibilityの結果が~check_bed_occlusionと一致 | 完全一致 |
| D3 | 実環境シナリオ | CLAUDE.mdの病室寸法でデフォルトベッド。高所カメラから活動ボリューム内のグリッド点群を判定 | 結果が物理的に妥当（床面が見え、ベッド裏は見えない） |

テストの合計: 約 18 件

### テスト用ヘルパー

```python
def _bed_aabb() -> AABB:
    """テスト用ベッドAABB（CLAUDE.md仕様準拠）。"""
    return AABB(
        min_point=np.array([0.9, 1.5, 0.0]),
        max_point=np.array([1.9, 3.5, 0.2]),
    )

def _dummy_bed_outside_room() -> AABB:
    """遮蔽の影響を排除するための部屋外ベッドAABB。"""
    return AABB(
        min_point=np.array([100.0, 100.0, 100.0]),
        max_point=np.array([101.0, 101.0, 101.0]),
    )
```

## 依存ライブラリ

- numpy（ベクトル演算） — 追加済み
- F04: FrustumChecker（`camera_placement.core.frustum` からインポート）
- F05: check_bed_occlusion（`camera_placement.core.occlusion` からインポート）
- F02: Camera（`camera_placement.models.camera` からインポート、型ヒント用）
- F01: AABB（`camera_placement.models.environment` からインポート、型ヒント用）
- pytest（テスト用） — 追加済み

新規ライブラリの追加は不要。
