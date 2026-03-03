"""F01: 空間モデル（部屋・ベッド・カメラ設置可能領域）。

病室の3D空間をAABB（軸平行境界ボックス）でモデル化し、
点の包含判定機能を提供する。
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AABB:
    """軸平行境界ボックス。

    Attributes:
        min_point: 最小座標 [x_min, y_min, z_min]。shape (3,)。
        max_point: 最大座標 [x_max, y_max, z_max]。shape (3,)。
    """

    min_point: np.ndarray
    max_point: np.ndarray

    def __post_init__(self) -> None:
        """np.float64配列に変換し、shapeを検証する。"""
        self.min_point = np.asarray(self.min_point, dtype=np.float64)
        self.max_point = np.asarray(self.max_point, dtype=np.float64)
        if self.min_point.shape != (3,):
            raise ValueError(f"min_point must have shape (3,), got {self.min_point.shape}")
        if self.max_point.shape != (3,):
            raise ValueError(f"max_point must have shape (3,), got {self.max_point.shape}")

    def contains(self, points: np.ndarray) -> np.ndarray:
        """点がAABB内にあるか判定する。

        境界上の点は内側として扱う。

        Args:
            points: 判定対象の点群。shape (N, 3) または (3,)。

        Returns:
            shape (N,) の bool配列。単一点入力時も (1,) を返す。
        """
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts.reshape(1, 3)
        if pts.ndim != 2 or pts.shape[1] != 3:
            raise ValueError(f"points must have shape (N, 3) or (3,), got {pts.shape}")

        inside = np.all(
            (pts >= self.min_point) & (pts <= self.max_point), axis=1
        )
        return inside


def _default_bed() -> AABB:
    """デフォルトのベッドAABBを生成する。"""
    return AABB(
        min_point=np.array([0.9, 1.5, 0.0]),
        max_point=np.array([1.9, 3.5, 0.2]),
    )


def _default_camera_zone() -> AABB:
    """デフォルトのカメラ設置可能領域AABBを生成する。"""
    return AABB(
        min_point=np.array([0.2, 0.2, 0.2]),
        max_point=np.array([2.6, 3.3, 2.3]),
    )


@dataclass
class Room:
    """病室の3D空間モデル。

    Attributes:
        width: 部屋の幅 X方向 [m]。
        depth: 部屋の奥行 Y方向 [m]。
        height: 部屋の高さ Z方向 [m]。
        bed: ベッドのAABB。
        camera_zone: カメラ設置可能領域のAABB。
    """

    width: float = 2.8
    depth: float = 3.5
    height: float = 2.5
    bed: AABB = field(default_factory=_default_bed)
    camera_zone: AABB = field(default_factory=_default_camera_zone)

    @property
    def room_aabb(self) -> AABB:
        """部屋全体のAABBを返す。"""
        return AABB(
            min_point=np.array([0.0, 0.0, 0.0]),
            max_point=np.array([self.width, self.depth, self.height]),
        )

    def is_inside_room(self, points: np.ndarray) -> np.ndarray:
        """点が部屋内にあるか判定する。

        Args:
            points: shape (N, 3) または (3,)。

        Returns:
            shape (N,) の bool配列。
        """
        return self.room_aabb.contains(points)

    def is_on_bed(self, points: np.ndarray) -> np.ndarray:
        """点がベッド領域内にあるか判定する。

        Args:
            points: shape (N, 3) または (3,)。

        Returns:
            shape (N,) の bool配列。
        """
        return self.bed.contains(points)

    def is_valid_camera_position(self, points: np.ndarray) -> np.ndarray:
        """点がカメラ設置可能領域内にあるか判定する。

        Args:
            points: shape (N, 3) または (3,)。

        Returns:
            shape (N,) の bool配列。
        """
        return self.camera_zone.contains(points)


def create_default_room() -> Room:
    """CLAUDE.mdの仕様に基づくデフォルト病室を生成する。

    Returns:
        デフォルトパラメータの Room インスタンス。
    """
    return Room()
