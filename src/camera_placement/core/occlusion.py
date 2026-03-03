"""F05: ベッドオクルージョン判定。

カメラ位置から対象点への視線（レイ）がベッドのAABBと交差するかを
slab法（Kay-Kajiya法）でバッチ判定する。
"""

from __future__ import annotations

import numpy as np

from camera_placement.models.camera import Camera
from camera_placement.models.environment import AABB


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
    eps_zero = 1e-12

    is_parallel = np.abs(directions) < eps_zero  # (N, 3)

    # ゼロ除算回避のための安全な逆数計算
    safe_dir = np.where(is_parallel, 1.0, directions)
    inv_dir = 1.0 / safe_dir

    # 各軸のt値計算
    t1 = (aabb_min - origins) * inv_dir  # (N, 3)
    t2 = (aabb_max - origins) * inv_dir  # (N, 3)

    # direction < 0 の場合にスワップ（np.minimum/maximumで自動対応）
    t_min_per_axis = np.minimum(t1, t2)  # (N, 3)
    t_max_per_axis = np.maximum(t1, t2)  # (N, 3)

    # 平行レイの処理
    inside_slab = (origins >= aabb_min) & (origins <= aabb_max)  # (N, 3)
    t_min_per_axis = np.where(
        is_parallel & inside_slab, -np.inf, t_min_per_axis
    )
    t_max_per_axis = np.where(
        is_parallel & inside_slab, np.inf, t_max_per_axis
    )
    t_min_per_axis = np.where(
        is_parallel & ~inside_slab, np.inf, t_min_per_axis
    )
    t_max_per_axis = np.where(
        is_parallel & ~inside_slab, -np.inf, t_max_per_axis
    )

    # 全軸でのenter/exit
    t_enter = np.max(t_min_per_axis, axis=1)  # (N,)
    t_exit = np.min(t_max_per_axis, axis=1)  # (N,)

    return t_enter, t_exit


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
    cam_pos = np.asarray(camera_position, dtype=np.float64)
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)

    n = pts.shape[0]
    origins = np.broadcast_to(cam_pos, (n, 3)).copy()
    directions = pts - cam_pos  # (N, 3)

    t_enter, t_exit = _ray_aabb_intersect(
        origins, directions, bed_aabb.min_point, bed_aabb.max_point
    )

    # オクルージョン判定
    occluded = (t_enter < 1.0 - eps) & (t_exit > eps) & (t_enter <= t_exit)

    # direction がゼロベクトル（カメラ位置 = 対象点）の場合は遮蔽なし
    eps_zero = 1e-12
    zero_direction = np.linalg.norm(directions, axis=1) < eps_zero
    occluded = occluded & ~zero_direction

    return occluded


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
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)

    m = len(cameras)
    n = pts.shape[0]
    result = np.zeros((m, n), dtype=bool)

    for i, cam in enumerate(cameras):
        result[i] = check_bed_occlusion(cam.position, pts, bed_aabb, eps)

    return result
