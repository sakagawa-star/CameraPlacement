# F02: カメラモデル — 機能設計書

## ファイル構成

```
src/camera_placement/
  models/
    __init__.py       # CameraIntrinsics, Camera, create_camera を追加export
    camera.py         # F02: CameraIntrinsics, Camera, create_camera()
tests/
  test_camera.py      # F02テスト
```

## データ構造

### `CameraIntrinsics` (frozen dataclass)

カメラの内部パラメータ。6台全てで同一仕様のため、インスタンスを共有可能。

```python
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class CameraIntrinsics:
    """カメラの内部パラメータ。

    Attributes:
        focal_length: 焦点距離 [mm]。
        sensor_width: センサー幅 [mm]。
        sensor_height: センサー高さ [mm]。
        resolution_w: 水平解像度 [px]。
        resolution_h: 垂直解像度 [px]。
    """
    focal_length: float = 3.5
    sensor_width: float = 5.76
    sensor_height: float = 3.6
    resolution_w: int = 1920
    resolution_h: int = 1200

    @property
    def hfov(self) -> float:
        """水平画角 [rad]。"""
        return 2.0 * np.arctan(self.sensor_width / (2.0 * self.focal_length))

    @property
    def vfov(self) -> float:
        """垂直画角 [rad]。"""
        return 2.0 * np.arctan(self.sensor_height / (2.0 * self.focal_length))

    @property
    def pixel_size(self) -> float:
        """ピクセルサイズ [mm]。sensor_width / resolution_w から計算。"""
        return self.sensor_width / self.resolution_w

    @property
    def fx(self) -> float:
        """焦点距離のピクセル単位換算 (水平) [px]。"""
        return self.focal_length / self.pixel_size

    @property
    def fy(self) -> float:
        """焦点距離のピクセル単位換算 (垂直) [px]。"""
        return self.focal_length * self.resolution_h / self.sensor_height

    @property
    def cx(self) -> float:
        """画像中心 X座標 [px]。"""
        return self.resolution_w / 2.0

    @property
    def cy(self) -> float:
        """画像中心 Y座標 [px]。"""
        return self.resolution_h / 2.0

    @property
    def intrinsic_matrix(self) -> np.ndarray:
        """3x3 カメラ内部行列 (K)。

        Returns:
            shape (3, 3):
            [[fx,  0, cx],
             [ 0, fy, cy],
             [ 0,  0,  1]]
        """
```

### `Camera` (dataclass)

カメラの内部・外部パラメータを統合したモデル。

```python
@dataclass
class Camera:
    """カメラの内部・外部パラメータを統合したモデル。

    Attributes:
        position: カメラ位置 [m]。shape (3,)。
        look_at: 注視点 [m]。shape (3,)。
        up_hint: 上方向ヒントベクトル。shape (3,)。デフォルト [0,0,1]。
        intrinsics: カメラ内部パラメータ。
    """
    position: np.ndarray
    look_at: np.ndarray
    up_hint: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0]))
    intrinsics: CameraIntrinsics = field(default_factory=CameraIntrinsics)

    def __post_init__(self) -> None:
        """np.float64に変換し、バリデーションを行う。

        検証内容:
        - position, look_at, up_hint が shape (3,) であること
        - position と look_at が同一座標でないこと（距離が eps 未満なら ValueError）
        - forward と up_hint が平行でないこと（外積のノルムが eps 未満なら ValueError）
        """

    @property
    def forward(self) -> np.ndarray:
        """カメラの前方方向ベクトル（単位ベクトル）。shape (3,)。"""

    @property
    def right(self) -> np.ndarray:
        """カメラの右方向ベクトル（単位ベクトル）。shape (3,)。"""

    @property
    def up(self) -> np.ndarray:
        """カメラの上方向ベクトル（単位ベクトル）。shape (3,)。"""

    @property
    def rotation_matrix(self) -> np.ndarray:
        """ワールド→カメラ座標系の回転行列 (3x3)。

        カメラ座標系: X=右, Y=上, Z=前方。
        R @ (world_point - position) でカメラ座標を得る。

        Returns:
            shape (3, 3)。行方向に [right, up, forward] を並べた正規直交行列。
        """

    def world_to_camera(self, points: np.ndarray) -> np.ndarray:
        """ワールド座標をカメラ座標に変換する。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N, 3)。カメラ座標（X=右, Y=上, Z=前方）。
        """

    def project_to_image(self, points: np.ndarray) -> np.ndarray:
        """ワールド座標を画像座標（ピクセル）に投影する。

        ピンホールカメラモデルによる投影。カメラ後方の点には NaN を返す。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N, 2)。画像座標 [u, v]（ピクセル）。
            カメラ後方の点は [NaN, NaN]。
        """
```

### ファクトリ関数

```python
def create_camera(
    position: np.ndarray | list[float],
    look_at: np.ndarray | list[float],
    up_hint: np.ndarray | list[float] | None = None,
    intrinsics: CameraIntrinsics | None = None,
) -> Camera:
    """デフォルト内部パラメータでカメラを生成する。

    Args:
        position: カメラ位置 [m]。
        look_at: 注視点 [m]。
        up_hint: 上方向ヒント。None時は [0,0,1]。
        intrinsics: 内部パラメータ。None時はデフォルト（CLAUDE.md仕様）。

    Returns:
        Camera インスタンス。
    """
```

## アルゴリズム

### ローカル座標系の計算（Gram-Schmidt風）

```
1. forward = normalize(look_at - position)
2. right   = normalize(cross(up_hint, forward))
3. up      = cross(forward, right)
```

- `cross(up_hint, forward)` で右方向を得る。この順序により右手座標系（det(R) = +1）が保証される。forward と up_hint が平行だと外積がゼロベクトルになるため、`__post_init__` で事前チェックする。
- `up = cross(forward, right)` で正規直交系が確定する。right, forward が互いに直交する単位ベクトルのため、up も自動的に単位ベクトルになる。
- 右手系の検証: `right × up = cross(up_hint, forward) × cross(forward, right) = forward` が成り立つ。

### ワールド→カメラ座標変換

```
camera_point = R @ (world_point - position)
```

R は `rotation_matrix`（3x3）。行方向に right, up, forward を並べた正規直交行列。

バッチ処理: `translated = pts - position` (N,3)、`result = (R @ translated.T).T` (N,3)。

### 画像座標への投影（ピンホールモデル）

```
cam = world_to_camera(points)        # (N, 3) カメラ座標
X_cam, Y_cam, Z_cam = cam の各列

u = fx * X_cam / Z_cam + cx
v = fy * (-Y_cam) / Z_cam + cy       # Y軸反転（カメラY=上、画像v=下）

Z_cam <= 0 の場合は [NaN, NaN] を返す
```

**Y軸反転の理由**: カメラ座標の Y=上 に対し、画像座標の v=下向き なので、投影時に `-Y_cam` とする。

## 設計判断

### 姿勢表現: position + look_at（注視点ベース）

| 代替案 | 問題点 |
|-------|-------|
| オイラー角 | ジンバルロックの問題あり、直感性に劣る |
| 四元数 | 正規化制約があり最適化の探索空間が制限される |
| 回転行列直接指定 | 9パラメータ+直交制約で冗長 |

注視点ベースの利点:
1. **直感性**: 「コーナーに置いて中央を見る」という指定が自然
2. **最適化との親和性**: position (3) + look_at (3) = 6パラメータは連続値で、PSO/差分進化に適合
3. **回転行列はプロパティで算出**: position/look_at から都度計算

### カメラ座標系: X=右, Y=上, Z=前方

- forward を Z軸にすることで `project_to_image` の Z除算が自然
- 画像座標の v 軸（下向き）との対応は投影時に Y を反転するだけ

### CameraIntrinsics を frozen にする理由

- 内部パラメータはハードウェア仕様で決まり、実行中に変更されない
- 複数カメラ間で同一インスタンスを共有可能（6台とも同じカメラ・レンズ構成）

### レンズ歪みの省略

- CLAUDE.md に「TV歪曲 0.4% 以下」と記載。初期段階では無視が妥当
- 必要時は `project_to_image` に歪みパラメータを追加するだけで拡張可能

## 後続機能との接続点

| 後続機能 | 使用するプロパティ/メソッド | 用途 |
|---------|--------------------------|------|
| F04 視錐台 | `position`, `forward`, `right`, `up`, `intrinsics.hfov`, `intrinsics.vfov` | 視錐台の平面法線と距離を計算 |
| F05 オクルージョン | `position` | カメラ位置からグリッド点へのレイの始点 |
| F08 角度スコア | `position` | 2台のカメラ位置と対象点から三角測量角度を計算 |
| F09 投影スコア | `project_to_image()`, `intrinsics.resolution_w`, `intrinsics.resolution_h` | 画像上座標の取得、画像内判定 |
| F11 可視化 | `position`, `forward`, `look_at` | カメラ位置・方向の3D表示 |
| F12 配置パターン | `create_camera()` | プリセット配置で6台のカメラを生成 |

## テスト計画

テストファイル: `tests/test_camera.py`

| # | カテゴリ | テストケース | 入力 | 期待値 |
|---|---------|-------------|------|--------|
| 1 | CameraIntrinsics | デフォルト値の確認 | `CameraIntrinsics()` | focal_length=3.5, sensor_width=5.76, sensor_height=3.6, resolution_w=1920, resolution_h=1200 |
| 2 | CameraIntrinsics | 水平FOVの計算 | デフォルト | `2*arctan(5.76/(2*3.5))` ≈ 1.379 rad ≈ 79.0° |
| 3 | CameraIntrinsics | 垂直FOVの計算 | デフォルト | `2*arctan(3.6/(2*3.5))` ≈ 0.943 rad ≈ 54.0° |
| 4 | CameraIntrinsics | ピクセルサイズの計算 | デフォルト | 5.76 / 1920 = 0.003 mm |
| 5 | CameraIntrinsics | fx, fyの計算 | デフォルト | fx = 3.5/0.003 ≈ 1166.67, fy = 3.5*1200/3.6 ≈ 1166.67 |
| 6 | CameraIntrinsics | cx, cyの計算 | デフォルト | cx = 960.0, cy = 600.0 |
| 7 | CameraIntrinsics | 内部行列Kの形状と値 | デフォルト | shape (3,3), K[0,0]=fx, K[1,1]=fy, K[0,2]=cx, K[1,2]=cy, K[2,2]=1 |
| 8 | Camera生成 | 正常なカメラ生成 | position=[0,0,2], look_at=[1.4,1.75,1] | エラーなし |
| 9 | Camera生成 | position==look_atでValueError | position=[1,1,1], look_at=[1,1,1] | ValueError |
| 10 | Camera生成 | forward//up_hintでValueError | position=[0,0,0], look_at=[0,0,1], up_hint=[0,0,1] | ValueError |
| 11 | Camera生成 | list入力でnp.float64に変換 | list [1.0, 2.0, 3.0] | dtype == np.float64 |
| 12 | Camera生成 | shape不正でValueError | position=[1,2] (2要素) | ValueError |
| 13 | ローカル座標系 | forward: Z軸正方向を見る | pos=[0,0,0], look_at=[0,0,1], up_hint=[0,1,0] | forward=[0,0,1] |
| 14 | ローカル座標系 | forward: X軸正方向を見る | pos=[0,0,0], look_at=[1,0,0] | forward=[1,0,0] |
| 15 | ローカル座標系 | forward: Y軸正方向を見る | pos=[0,0,0], look_at=[0,1,0] | forward=[0,1,0] |
| 16 | ローカル座標系 | forward, right, upが正規直交系 | 任意のカメラ | dot積 ≈ 0、各ノルム ≈ 1 |
| 17 | ローカル座標系 | rotation_matrixが正規直交行列 | 任意のカメラ | R @ R.T ≈ I, det(R) ≈ 1 |
| 18 | world_to_camera | カメラ位置自身は原点 | pos=[1,2,3], look_at=[1,2,4], up_hint=[0,1,0] | world_to_camera([1,2,3]) = [0,0,0] |
| 19 | world_to_camera | look_atはZ軸正方向 | pos=[0,0,0], look_at=[0,0,5], up_hint=[0,1,0] | world_to_camera([0,0,5]) = [0,0,5] |
| 20 | world_to_camera | 右方向の点はカメラX正 | 適切な入力 | X_cam > 0 |
| 21 | world_to_camera | 上方向の点はカメラY正 | 適切な入力 | Y_cam > 0 |
| 22 | world_to_camera | バッチ処理 (N,3) | 3点以上 | 個別計算と一致 |
| 23 | world_to_camera | 単一点 shape (3,) | shape (3,) | shape (1,3) の結果 |
| 24 | project_to_image | look_at点は画像中心に投影 | pos=[0,0,0], look_at=[0,0,5], up_hint=[0,1,0] | ≈ [960, 600] |
| 25 | project_to_image | カメラ後方の点はNaN | pos=[0,0,0], look_at=[0,0,1], up_hint=[0,1,0] | project([0,0,-1]) = [NaN, NaN] |
| 26 | project_to_image | 画像右上方向の投影 | 前方右上の点 | u > cx, v < cy |
| 27 | project_to_image | バッチ処理（前方+後方の混在） | 前方1点+後方1点 | 前方=有効値、後方=NaN |
| 28 | create_camera | デフォルト内部パラメータ | create_camera([0,0,2], [1,1,1]) | intrinsics がデフォルトと一致 |
| 29 | create_camera | カスタム内部パラメータ | intrinsics指定 | 指定値が使われる |
| 30 | create_camera | カスタムup_hint | up_hint=[0,1,0] | up_hint=[0,1,0]が使われる |
| 31 | create_camera | list入力で動作 | list型の position, look_at | エラーなし |

## 依存ライブラリ

- numpy（行列演算、ベクトル演算） — 追加済み
- dataclasses（標準ライブラリ）
- pytest（テスト用） — 追加済み

## 環境構築メモ

`src/camera_placement/models/__init__.py` に CameraIntrinsics, Camera, create_camera の export を追加する。
