# F04: 視錐台（FOV）判定 — 機能設計書

## ファイル構成

```
src/camera_placement/
  core/
    __init__.py        # FrustumChecker を export
    frustum.py         # F04: FrustumChecker クラス
tests/
  test_frustum.py      # F04テスト
tests/results/
  F04_test_result.txt  # テスト結果
```

新規ディレクトリ `src/camera_placement/core/` を作成する。

## データ構造

### `FrustumChecker` (dataclass)

```python
from dataclasses import dataclass
import numpy as np
from camera_placement.models.camera import Camera


@dataclass
class FrustumChecker:
    """カメラの視錐台による視野内判定を行う。

    カメラのFOVに基づいて視錐台を構成し、3D点群が視野内にあるかを
    バッチ判定する。内部ではカメラ座標系でのFOV角度判定を行う。

    Attributes:
        camera: F02のCameraインスタンス。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
    """
    camera: Camera
    near: float = 0.1
    far: float = 10.0

    def __post_init__(self) -> None:
        """バリデーション。

        Raises:
            ValueError: near < 0、far <= near の場合。
        """
        if self.near < 0:
            raise ValueError(f"near must be >= 0, got {self.near}")
        if self.far <= self.near:
            raise ValueError(
                f"far must be > near, got near={self.near}, far={self.far}"
            )

    def is_visible(self, points: np.ndarray) -> np.ndarray:
        """点群が視錐台内にあるかを判定する。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N,) の bool 配列。True = 視野内。
        """

    def get_frustum_planes(self) -> np.ndarray:
        """視錐台を構成する6平面を返す。

        Returns:
            shape (6, 4)。各行は [nx, ny, nz, d]。
            法線はフラスタム内側を向く。
            順序: [near, far, left, right, top, bottom]。
            平面方程式: nx*x + ny*y + nz*z + d >= 0 で内側。
        """

    def get_frustum_corners(self) -> np.ndarray:
        """視錐台の8頂点のワールド座標を返す。

        Returns:
            shape (8, 3)。
            順序: [near_tl, near_tr, near_bl, near_br,
                    far_tl,  far_tr,  far_bl,  far_br]
            tl=top-left, tr=top-right, bl=bottom-left, br=bottom-right
            （カメラから見た方向で定義）
        """
```

## アルゴリズム

### 方法B: カメラ座標でのFOV角度判定（採用）

`is_visible` の判定ロジック:

```
1. cam_pts = camera.world_to_camera(points)  # (N, 3) カメラ座標
2. X_cam, Y_cam, Z_cam = cam_pts の各列

3. 前方判定 + 距離クリップ:
   depth_ok = (Z_cam >= near) & (Z_cam <= far)

4. 水平FOV判定:
   half_hfov = camera.intrinsics.hfov / 2
   hfov_ok = np.abs(X_cam) <= Z_cam * tan(half_hfov)
   （※ Z_cam > 0 が前提。depth_ok で保証）

5. 垂直FOV判定:
   half_vfov = camera.intrinsics.vfov / 2
   vfov_ok = np.abs(Y_cam) <= Z_cam * tan(half_vfov)

6. 最終判定:
   visible = depth_ok & hfov_ok & vfov_ok
```

**ステップ4, 5の数学的根拠**:

カメラ座標系で、点 (X, Y, Z) がFOV内にあるための条件:
- 水平方向: `|arctan(X/Z)| <= hfov/2`
- これは `|X/Z| <= tan(hfov/2)` と同値
- 両辺に Z を掛けて（Z>0なので不等号は変わらない）: `|X| <= Z * tan(hfov/2)`

この変形により、`arctan` の計算を避け、乗算と比較だけで判定できる。10万点規模でも高速。

### `get_frustum_planes` のアルゴリズム

6平面をワールド座標系で表現する。各平面は `ax + by + cz + d = 0` の形式で、法線 (a, b, c) がフラスタム内側を向く。

```
half_hfov = camera.intrinsics.hfov / 2
half_vfov = camera.intrinsics.vfov / 2

# カメラローカル座標系での法線ベクトル（内向き）
# near:   カメラ前方方向  -> (0, 0, 1)
# far:    カメラ後方方向  -> (0, 0, -1)
# left:   右に傾いた法線  -> (sin(half_hfov), 0, cos(half_hfov))
# right:  左に傾いた法線  -> (-sin(half_hfov), 0, cos(half_hfov))
# top:    下に傾いた法線  -> (0, -sin(half_vfov), cos(half_vfov))
# bottom: 上に傾いた法線  -> (0, sin(half_vfov), cos(half_vfov))

# ワールド座標系に変換:
# R = camera.rotation_matrix (3x3)
# ワールド法線 = R.T @ ローカル法線
# d = -dot(ワールド法線, 平面上の1点)
```

near平面上の1点: `camera.position + near * camera.forward`
far平面上の1点: `camera.position + far * camera.forward`
left/right/top/bottom 平面上の1点: `camera.position`（全てカメラ位置を通る）

### `get_frustum_corners` のアルゴリズム

```
half_hfov = camera.intrinsics.hfov / 2
half_vfov = camera.intrinsics.vfov / 2

# near面の半幅・半高
near_half_w = near * tan(half_hfov)
near_half_h = near * tan(half_vfov)

# far面の半幅・半高
far_half_w = far * tan(half_hfov)
far_half_h = far * tan(half_vfov)

# カメラローカル座標での8頂点
# near面中心: (0, 0, near)
# far面中心:  (0, 0, far)
# 各頂点 = 面中心 + (±half_w) * (1,0,0) + (±half_h) * (0,1,0)

# ワールド座標に変換:
# world_point = camera.position + R.T @ local_point
```

頂点の順序:
```
near_tl = near_center + (-near_half_w) * right + (+near_half_h) * up  (カメラ座標)
near_tr = near_center + (+near_half_w) * right + (+near_half_h) * up
near_bl = near_center + (-near_half_w) * right + (-near_half_h) * up
near_br = near_center + (+near_half_w) * right + (-near_half_h) * up
（far面も同様）
```

ワールド座標への変換:
```
world_corner = camera.position + dist * forward + hw * right + hh * up
```

## 設計判断

### 方法B（カメラ座標FOV角度判定）を採用する理由

| 比較項目 | 方法A（6平面法） | 方法B（角度判定） |
|---------|----------------|----------------|
| 実装の簡潔さ | 6平面の法線計算が必要 | `world_to_camera` を使い3条件のAND |
| F02との連携 | 平面計算に独自ロジックが必要 | `world_to_camera()` をそのまま活用 |
| 計算コスト | 6回の内積+比較 | 1回の座標変換+3条件比較 |
| near/farクリップ | 統合的に扱える | Z_cam の範囲チェックで対応 |

方法Bの決め手:
1. F02の `world_to_camera()` を直接活用でき、座標変換ロジックの重複がない
2. 判定ロジックが直感的で理解しやすい
3. `arctan` を避けた `|X| <= Z * tan(hfov/2)` の形に変形でき、計算効率も高い
4. near/far クリップは Z_cam の範囲チェックで自然に対応可能

### `get_frustum_planes` と `get_frustum_corners` を提供する理由

- `is_visible` の判定は方法Bで行うが、可視化（F11）では視錐台の形状を描画する必要がある
- `get_frustum_corners` は視錐台のワイヤーフレーム描画に直接使える
- `get_frustum_planes` は将来的にレイ-平面交差判定などが必要になった場合に備える

### near/far のデフォルト値

- near = 0.1m: カメラに10cm未満の距離の物体は実用上存在しない（カメラ設置高さ1.8m以上、対象は床面〜1.8m）
- far = 10.0m: 部屋対角線は約5.1mなので、10mなら部屋内の全点を確実にカバー。ユーザーが制限したい場合のみ変更

## F02との連携方法

1. **座標変換**: `camera.world_to_camera(points)` を呼び出してカメラ座標を取得
2. **FOV取得**: `camera.intrinsics.hfov` / `camera.intrinsics.vfov` を参照
3. **方向ベクトル**: `camera.forward`, `camera.right`, `camera.up` を `get_frustum_corners` / `get_frustum_planes` で使用
4. **カメラ位置**: `camera.position` を視錐台頂点の基準点として使用

F04は Camera オブジェクトを受け取るだけで動作し、Camera の内部実装に依存しない（公開インターフェースのみ使用）。

## 後続機能との接続点

| 後続機能 | 使用するメソッド | 用途 |
|---------|----------------|------|
| F06 視認性統合 | `FrustumChecker.is_visible(points)` | 点群の視野内判定。F05のオクルージョン判定と AND 結合 |
| F11 可視化 | `FrustumChecker.get_frustum_corners()` | 視錐台のワイヤーフレーム表示 |

F06での使用イメージ:
```python
frustum = FrustumChecker(camera=cam)
in_fov = frustum.is_visible(points)          # shape (N,) bool
not_occluded = ~check_bed_occlusion(cam.position, points, room.bed)  # F05
visible = in_fov & not_occluded              # 最終的な視認性
```

## テスト計画

テストファイル: `tests/test_frustum.py`

| # | カテゴリ | テストケース | 入力 | 期待値 |
|---|---------|-------------|------|--------|
| 1 | 生成 | 正常な FrustumChecker 生成 | Camera + デフォルトnear/far | エラーなし |
| 2 | 生成 | near < 0 で ValueError | near=-0.1 | ValueError |
| 3 | 生成 | far <= near で ValueError | near=5.0, far=3.0 | ValueError |
| 4 | 生成 | near=0 は許容 | near=0, far=10 | エラーなし |
| 5 | is_visible | look_at 点は視野内 | カメラの注視点 | True |
| 6 | is_visible | カメラ真正面の点は視野内 | forward 方向にnear〜farの距離の点 | True |
| 7 | is_visible | カメラ後方の点は視野外 | カメラ後方の点 | False |
| 8 | is_visible | near 未満の近距離は視野外 | forward 方向に near 未満の距離 | False |
| 9 | is_visible | far 超の遠距離は視野外 | forward 方向に far 超の距離 | False |
| 10 | is_visible | 水平FOV境界内ギリギリ | hfov/2 - epsilon の角度 | True |
| 11 | is_visible | 水平FOV境界外ギリギリ | hfov/2 + epsilon の角度 | False |
| 12 | is_visible | 垂直FOV境界内ギリギリ | vfov/2 - epsilon の角度 | True |
| 13 | is_visible | 垂直FOV境界外ギリギリ | vfov/2 + epsilon の角度 | False |
| 14 | is_visible | FOV境界ちょうどは視野内 | hfov/2 ちょうどの角度 | True |
| 15 | is_visible | バッチ処理: 視野内外の混在 | 5点（内3点が視野内、2点が視野外） | [T,T,T,F,F] 的な結果 |
| 16 | is_visible | 単一点 shape (3,) | shape (3,) の1点 | shape (1,) の結果 |
| 17 | is_visible | 大量点群（性能確認） | 10万点のランダム点群 | 例外なく完了、結果のshapeが正しい |
| 18 | is_visible | 斜め向きカメラ | pos=[0,0,2.3], look_at=[1.4,1.75,0.5] | forward方向近傍の点がTrue |
| 19 | get_frustum_corners | 頂点数と形状 | 任意のカメラ | shape (8, 3) |
| 20 | get_frustum_corners | near面の4頂点がnear距離にある | 任意のカメラ | 各頂点とカメラ位置の、forward方向の距離 = near |
| 21 | get_frustum_corners | far面の4頂点がfar距離にある | 任意のカメラ | 各頂点とカメラ位置の、forward方向の距離 = far |
| 22 | get_frustum_corners | 全8頂点が is_visible で True | 任意のカメラ | 8点すべて True |
| 23 | get_frustum_corners | near面の幅が 2*near*tan(hfov/2) | 任意のカメラ | top-right と top-left の距離 = 2*near*tan(hfov/2) |
| 24 | get_frustum_planes | 平面数と形状 | 任意のカメラ | shape (6, 4) |
| 25 | get_frustum_planes | フラスタム内の点が全平面の内側 | look_at 点 | 全6平面で nx*x+ny*y+nz*z+d >= 0 |
| 26 | get_frustum_planes | フラスタム外の点が少なくとも1平面で外側 | カメラ後方の点 | 少なくとも1平面で nx*x+ny*y+nz*z+d < 0 |
| 27 | is_visible 整合性 | Z軸正方向を向くカメラ | pos=[1.4,1.75,0], look_at=[1.4,1.75,2] | Z方向に正しく判定 |
| 28 | is_visible 整合性 | project_to_image との整合 | 視野内の点 | project_to_image の結果が画像範囲内 |

## 依存ライブラリ

- numpy（行列演算、ベクトル演算） — 追加済み
- dataclasses（標準ライブラリ）
- pytest（テスト用） — 追加済み

新規ライブラリの追加は不要。
