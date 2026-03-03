"""F07: カバレッジ計算。

F06（視認性統合）の visibility_matrix を集計し、構造化されたカバレッジ統計を返す。
活動ボリューム別と統合グリッドの両方のカバレッジを計算する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.core.visibility import check_visibility_multi_camera
from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
    create_merged_grid,
)
from camera_placement.models.camera import Camera
from camera_placement.models.environment import AABB, Room


@dataclass
class CoverageStats:
    """カバレッジ統計情報。

    visible_counts を唯一の一次データとし、他の統計量は全て property で導出する。

    Attributes:
        visible_counts: 各点の視認カメラ数。shape (N,), dtype=int。
        num_cameras: カメラ総数 M。
        num_points: グリッド点数 N。
    """

    visible_counts: np.ndarray  # shape (N,), dtype=int
    num_cameras: int
    num_points: int

    @property
    def coverage_at_least(self) -> dict[int, float]:
        """k台以上カバー率の辞書。key: k=1,2,...,num_cameras, value: 0.0〜1.0。"""
        if self.num_points == 0:
            return {k: 0.0 for k in range(1, self.num_cameras + 1)}
        return {
            k: float((self.visible_counts >= k).mean())
            for k in range(1, self.num_cameras + 1)
        }

    @property
    def coverage_3plus(self) -> float:
        """3台以上カバー率（最重要指標）。"""
        if self.num_points == 0:
            return 0.0
        return float((self.visible_counts >= 3).mean())

    @property
    def min_visible(self) -> int:
        """最小視認カメラ数。"""
        if self.num_points == 0:
            return 0
        return int(self.visible_counts.min())

    @property
    def max_visible(self) -> int:
        """最大視認カメラ数。"""
        if self.num_points == 0:
            return 0
        return int(self.visible_counts.max())

    @property
    def mean_visible(self) -> float:
        """平均視認カメラ数。"""
        if self.num_points == 0:
            return 0.0
        return float(self.visible_counts.mean())


@dataclass
class VolumeCoverage:
    """単一活動ボリュームのカバレッジ結果。

    Attributes:
        activity_type: 動作パターンの種別。
        visibility_matrix: 視認性行列。shape (M, N_vol), dtype=bool。
        stats: カバレッジ統計。
    """

    activity_type: ActivityType
    visibility_matrix: np.ndarray  # shape (M, N_vol), dtype=bool
    stats: CoverageStats


@dataclass
class CoverageResult:
    """カバレッジ計算の全体結果。

    Attributes:
        cameras: 使用したカメラリスト。
        merged_grid: 統合グリッド点群。shape (N, 3)。
        visibility_matrix: 統合グリッドの視認性行列。shape (M, N), dtype=bool。
        stats: 統合グリッドのカバレッジ統計。
        volume_coverages: 活動ボリューム別のカバレッジ結果。
    """

    cameras: list[Camera]
    merged_grid: np.ndarray  # shape (N, 3)
    visibility_matrix: np.ndarray  # shape (M, N), dtype=bool
    stats: CoverageStats
    volume_coverages: dict[ActivityType, VolumeCoverage]


def calculate_coverage_stats(visibility_matrix: np.ndarray) -> CoverageStats:
    """視認性行列からカバレッジ統計を計算する。

    Args:
        visibility_matrix: shape (M, N) の bool配列。
            M はカメラ数、N はグリッド点数。

    Returns:
        CoverageStats インスタンス。

    Raises:
        ValueError: visibility_matrix が2次元でない場合。
    """
    vis = np.asarray(visibility_matrix, dtype=bool)
    if vis.ndim != 2:
        raise ValueError(f"visibility_matrix must be 2D, got {vis.ndim}D")
    visible_counts = vis.sum(axis=0).astype(int)
    return CoverageStats(
        visible_counts=visible_counts,
        num_cameras=vis.shape[0],
        num_points=vis.shape[1],
    )


def calculate_volume_coverage(
    cameras: list[Camera],
    volume: ActivityVolume,
    bed_aabb: AABB,
    near: float = 0.1,
    far: float = 10.0,
) -> VolumeCoverage:
    """単一の活動ボリュームに対するカバレッジを計算する。

    Args:
        cameras: カメラのリスト。
        volume: 活動ボリューム。
        bed_aabb: ベッドのAABB。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。

    Returns:
        VolumeCoverage インスタンス。
    """
    vis_matrix = check_visibility_multi_camera(
        cameras, volume.grid_points, bed_aabb, near, far
    )
    stats = calculate_coverage_stats(vis_matrix)
    return VolumeCoverage(
        activity_type=volume.activity_type,
        visibility_matrix=vis_matrix,
        stats=stats,
    )


def calculate_coverage(
    cameras: list[Camera],
    room: Room,
    volumes: list[ActivityVolume] | None = None,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
) -> CoverageResult:
    """6台全カメラのカバレッジを計算する。

    活動ボリューム別の統計と、統合グリッドの全体統計の両方を返す。

    Args:
        cameras: カメラのリスト。
        room: 病室モデル。
        volumes: 活動ボリューム。Noneの場合は自動生成。
        grid_spacing: volumes=None の場合のグリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。

    Returns:
        CoverageResult インスタンス。
    """
    if volumes is None:
        volumes = create_activity_volumes(room, grid_spacing)

    # 活動ボリューム別カバレッジ
    volume_coverages: dict[ActivityType, VolumeCoverage] = {}
    for vol in volumes:
        vc = calculate_volume_coverage(cameras, vol, room.bed, near, far)
        volume_coverages[vol.activity_type] = vc

    # 統合グリッドカバレッジ
    merged_grid = create_merged_grid(volumes)
    if merged_grid.shape[0] == 0:
        merged_vis_matrix = np.zeros((len(cameras), 0), dtype=bool)
    else:
        merged_vis_matrix = check_visibility_multi_camera(
            cameras, merged_grid, room.bed, near, far
        )
    merged_stats = calculate_coverage_stats(merged_vis_matrix)

    return CoverageResult(
        cameras=cameras,
        merged_grid=merged_grid,
        visibility_matrix=merged_vis_matrix,
        stats=merged_stats,
        volume_coverages=volume_coverages,
    )
