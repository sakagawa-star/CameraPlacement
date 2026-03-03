"""F06: 視認性統合。

F04（視錐台判定）とF05（ベッドオクルージョン判定）を統合し、
1台または複数台のカメラから3D空間内の各点が視認可能かを最終判定する。
"""

from __future__ import annotations

import numpy as np

from camera_placement.core.frustum import FrustumChecker
from camera_placement.core.occlusion import check_bed_occlusion
from camera_placement.models.camera import Camera
from camera_placement.models.environment import AABB


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
    frustum_checker = FrustumChecker(camera=camera, near=near, far=far)
    in_frustum = frustum_checker.is_visible(points)
    occluded = check_bed_occlusion(camera.position, points, bed_aabb, eps)
    return in_frustum & ~occluded


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
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    n_points = pts.shape[0]
    m_cameras = len(cameras)
    result = np.zeros((m_cameras, n_points), dtype=bool)
    for i, cam in enumerate(cameras):
        result[i] = check_visibility(cam, pts, bed_aabb, near, far, eps)
    return result
