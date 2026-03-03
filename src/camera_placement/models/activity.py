"""F03: 活動ボリューム・グリッド生成。

3つの動作パターン（歩行・ベッド上座位・ベッド上臥位）の活動領域を
3D空間上に定義し、各領域内に等間隔の3Dグリッド点群を生成する。
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np

from camera_placement.models.environment import Room, create_default_room

_WALKING_Z_MAX = 1.8
_SEATED_Z_MIN = 0.2
_SEATED_Z_MAX = 1.1
_SUPINE_Z_MIN = 0.2
_SUPINE_Z_MAX = 0.5


def _grid_1d(start: float, stop: float, spacing: float) -> np.ndarray:
    """1次元のグリッド座標配列を生成する。

    np.arangeの浮動小数点誤差による端点オーバーシュートを防止する。

    Args:
        start: 開始値。
        stop: 終了値（含む）。
        spacing: 間隔。

    Returns:
        start から stop までの等間隔配列。stop を超える値は除外。
    """
    vals = np.arange(start, stop + spacing / 2, spacing)
    return vals[vals <= stop + 1e-10]


class ActivityType(Enum):
    """動作パターンの種別。"""

    WALKING = "walking"
    SEATED = "seated"
    SUPINE = "supine"


@dataclass
class ActivityVolume:
    """1つの動作パターンの活動ボリューム。

    Attributes:
        activity_type: 動作パターンの種別。
        grid_points: 活動領域内のグリッド点群。shape (N, 3)。dtype=np.float64。
    """

    activity_type: ActivityType
    grid_points: np.ndarray  # shape (N, 3)

    def __post_init__(self) -> None:
        """配列の型とshapeを検証する。

        Raises:
            ValueError: grid_points が2次元でない、または列数が3でない場合。
        """
        self.grid_points = np.asarray(self.grid_points, dtype=np.float64)
        if self.grid_points.ndim != 2 or self.grid_points.shape[1] != 3:
            raise ValueError(
                f"grid_points must have shape (N, 3), got {self.grid_points.shape}"
            )

    @property
    def num_points(self) -> int:
        """グリッド点数を返す。"""
        return self.grid_points.shape[0]


def _generate_walking_grid(room: Room, spacing: float) -> np.ndarray:
    """歩行領域のグリッド点を生成する。

    部屋のXY全体からベッドXY投影内の点を除外し、
    Z方向 0 ~ 1.8m の範囲でグリッドを生成する。

    Args:
        room: Roomインスタンス。
        spacing: グリッド間隔 [m]。

    Returns:
        shape (N, 3) のグリッド点群。
    """
    xs = _grid_1d(0.0, room.width, spacing)
    ys = _grid_1d(0.0, room.depth, spacing)
    zs = _grid_1d(0.0, _WALKING_Z_MAX, spacing)

    xx, yy = np.meshgrid(xs, ys, indexing="ij")
    xy_points = np.column_stack([xx.ravel(), yy.ravel()])

    bed_min_xy = room.bed.min_point[:2]
    bed_max_xy = room.bed.max_point[:2]
    in_bed = np.all(
        (xy_points >= bed_min_xy) & (xy_points <= bed_max_xy), axis=1
    )
    xy_outside_bed = xy_points[~in_bed]

    n_xy = xy_outside_bed.shape[0]
    n_z = len(zs)
    grid = np.empty((n_xy * n_z, 3), dtype=np.float64)
    grid[:, 0] = np.repeat(xy_outside_bed[:, 0], n_z)
    grid[:, 1] = np.repeat(xy_outside_bed[:, 1], n_z)
    grid[:, 2] = np.tile(zs, n_xy)

    return grid


def _generate_bed_grid(
    room: Room, spacing: float, z_min: float, z_max: float
) -> np.ndarray:
    """ベッド上のグリッド点を生成する。

    Args:
        room: Roomインスタンス。
        spacing: グリッド間隔 [m]。
        z_min: Z方向の最小値 [m]。
        z_max: Z方向の最大値 [m]。

    Returns:
        shape (N, 3) のグリッド点群。
    """
    xs = _grid_1d(room.bed.min_point[0], room.bed.max_point[0], spacing)
    ys = _grid_1d(room.bed.min_point[1], room.bed.max_point[1], spacing)
    zs = _grid_1d(z_min, z_max, spacing)

    xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")
    grid = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])

    return grid.astype(np.float64)


def create_activity_volumes(
    room: Room | None = None,
    grid_spacing: float = 0.2,
) -> list[ActivityVolume]:
    """3つの動作パターンの活動ボリュームを生成する。

    Args:
        room: Roomインスタンス。Noneの場合はデフォルト病室。
        grid_spacing: グリッド間隔 [m]。正の値であること。

    Returns:
        [walking, seated, supine] の順の ActivityVolume リスト。

    Raises:
        ValueError: grid_spacingが0以下の場合。
    """
    if grid_spacing <= 0:
        raise ValueError(f"grid_spacing must be positive, got {grid_spacing}")

    if room is None:
        room = create_default_room()

    walking_grid = _generate_walking_grid(room, grid_spacing)
    seated_grid = _generate_bed_grid(
        room, grid_spacing, _SEATED_Z_MIN, _SEATED_Z_MAX
    )
    supine_grid = _generate_bed_grid(
        room, grid_spacing, _SUPINE_Z_MIN, _SUPINE_Z_MAX
    )

    return [
        ActivityVolume(ActivityType.WALKING, walking_grid),
        ActivityVolume(ActivityType.SEATED, seated_grid),
        ActivityVolume(ActivityType.SUPINE, supine_grid),
    ]


def create_merged_grid(
    volumes: list[ActivityVolume],
    decimals: int = 6,
) -> np.ndarray:
    """複数のActivityVolumeのグリッド点を統合し重複を除去する。

    Args:
        volumes: ActivityVolumeのリスト。
        decimals: 重複判定用の丸め桁数。浮動小数点誤差対策。

    Returns:
        shape (M, 3) の統合グリッド点群。重複除去済み。
    """
    if not volumes:
        return np.empty((0, 3), dtype=np.float64)

    all_points = np.vstack([v.grid_points for v in volumes])
    rounded = np.round(all_points, decimals=decimals)
    unique = np.unique(rounded, axis=0)

    return unique
