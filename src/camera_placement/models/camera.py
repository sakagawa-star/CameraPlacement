"""F02: カメラモデル（内部パラメータ・外部パラメータ）。

カメラの内部パラメータ（焦点距離、センサーサイズ、解像度、FOV）と
外部パラメータ（位置、姿勢）をモデル化し、座標変換・投影機能を提供する。
"""

from dataclasses import dataclass, field

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
        return np.array([
            [self.fx, 0.0, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ])


_EPS = 1e-10


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

        Raises:
            ValueError: shape不正、position==look_at、forward//up_hint の場合。
        """
        self.position = np.asarray(self.position, dtype=np.float64)
        self.look_at = np.asarray(self.look_at, dtype=np.float64)
        self.up_hint = np.asarray(self.up_hint, dtype=np.float64)

        if self.position.shape != (3,):
            raise ValueError(
                f"position must have shape (3,), got {self.position.shape}"
            )
        if self.look_at.shape != (3,):
            raise ValueError(
                f"look_at must have shape (3,), got {self.look_at.shape}"
            )
        if self.up_hint.shape != (3,):
            raise ValueError(
                f"up_hint must have shape (3,), got {self.up_hint.shape}"
            )

        diff = self.look_at - self.position
        if np.linalg.norm(diff) < _EPS:
            raise ValueError("position and look_at must not be the same point")

        fwd = diff / np.linalg.norm(diff)
        cross = np.cross(fwd, self.up_hint)
        if np.linalg.norm(cross) < _EPS:
            raise ValueError("forward direction and up_hint must not be parallel")

    @property
    def forward(self) -> np.ndarray:
        """カメラの前方方向ベクトル（単位ベクトル）。shape (3,)。"""
        diff = self.look_at - self.position
        return diff / np.linalg.norm(diff)

    @property
    def right(self) -> np.ndarray:
        """カメラの右方向ベクトル（単位ベクトル）。shape (3,)。"""
        r = np.cross(self.up_hint, self.forward)
        return r / np.linalg.norm(r)

    @property
    def up(self) -> np.ndarray:
        """カメラの上方向ベクトル（単位ベクトル）。shape (3,)。"""
        return np.cross(self.forward, self.right)

    @property
    def rotation_matrix(self) -> np.ndarray:
        """ワールド→カメラ座標系の回転行列 (3x3)。

        カメラ座標系: X=右, Y=上, Z=前方。
        R @ (world_point - position) でカメラ座標を得る。

        Returns:
            shape (3, 3)。行方向に [right, up, forward] を並べた正規直交行列。
        """
        return np.vstack([self.right, self.up, self.forward])

    def world_to_camera(self, points: np.ndarray) -> np.ndarray:
        """ワールド座標をカメラ座標に変換する。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N, 3)。カメラ座標（X=右, Y=上, Z=前方）。
        """
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts.reshape(1, 3)
        if pts.ndim != 2 or pts.shape[1] != 3:
            raise ValueError(
                f"points must have shape (N, 3) or (3,), got {pts.shape}"
            )

        translated = pts - self.position
        R = self.rotation_matrix
        return (R @ translated.T).T

    def project_to_image(self, points: np.ndarray) -> np.ndarray:
        """ワールド座標を画像座標（ピクセル）に投影する。

        ピンホールカメラモデルによる投影。カメラ後方の点には NaN を返す。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N, 2)。画像座標 [u, v]（ピクセル）。
            カメラ後方の点は [NaN, NaN]。
        """
        cam = self.world_to_camera(points)
        x_cam = cam[:, 0]
        y_cam = cam[:, 1]
        z_cam = cam[:, 2]

        intr = self.intrinsics
        result = np.full((cam.shape[0], 2), np.nan)

        valid = z_cam > 0
        if np.any(valid):
            result[valid, 0] = intr.fx * x_cam[valid] / z_cam[valid] + intr.cx
            result[valid, 1] = intr.fy * (-y_cam[valid]) / z_cam[valid] + intr.cy

        return result


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
    pos = np.asarray(position, dtype=np.float64)
    la = np.asarray(look_at, dtype=np.float64)

    kwargs: dict = {"position": pos, "look_at": la}
    if up_hint is not None:
        kwargs["up_hint"] = np.asarray(up_hint, dtype=np.float64)
    if intrinsics is not None:
        kwargs["intrinsics"] = intrinsics

    return Camera(**kwargs)
