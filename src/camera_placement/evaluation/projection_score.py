"""F09: 2D投影サイズスコア。

カメラからの距離に基づき、各グリッド点における画像上の空間解像度（ピクセル/メートル）を
計算し、2Dキーポイント検出精度の指標としてスコア化する。
スコア関数は min(ppm / target_ppm, 1.0) を使用する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.models.camera import Camera


@dataclass
class ProjectionScoreResult:
    """2D投影サイズスコアの計算結果。

    point_best_scores を主要指標とし、mean_score は point_best_scores から導出する。

    Attributes:
        point_best_scores: 各点のベストスコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。視認カメラなしの点は 0.0。
        point_mean_scores: 各点の平均スコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。視認カメラなしの点は 0.0。
        point_best_ppm: 各点のベスト投影解像度 [px/m]。shape (N,), dtype=float64。
            値域 [0.0, ∞)。視認カメラなしの点は 0.0。
        mean_score: point_best_scores の算術平均。float。点数0の場合は 0.0。
    """

    point_best_scores: np.ndarray   # shape (N,), dtype=float64
    point_mean_scores: np.ndarray   # shape (N,), dtype=float64
    point_best_ppm: np.ndarray      # shape (N,), dtype=float64
    mean_score: float


def calculate_pixel_per_meter(
    camera_pos: np.ndarray,
    points: np.ndarray,
    fx: float,
) -> np.ndarray:
    """1台のカメラから各点への投影解像度をバッチ計算する。

    カメラ位置から各3D点までのユークリッド距離に基づき、
    画像上の空間解像度（ピクセル/メートル）を計算する。

    Args:
        camera_pos: カメラ位置 [m]。shape (3,)。
        points: 3D点群 [m]。shape (N, 3)。
        fx: 水平焦点距離 [px]。

    Returns:
        shape (N,) の投影解像度配列 [px/m]。
        カメラが点と同一位置の場合は 0.0。
    """
    diff = points - camera_pos  # (N, 3)
    distances = np.linalg.norm(diff, axis=1)  # (N,)

    zero_mask = distances < 1e-10
    safe_distances = np.where(zero_mask, 1.0, distances)

    ppm = fx / safe_distances  # (N,)
    ppm[zero_mask] = 0.0

    return ppm


def calculate_projection_score(
    cameras: list[Camera],
    grid_points: np.ndarray,
    visibility_matrix: np.ndarray,
    target_ppm: float = 500.0,
) -> ProjectionScoreResult:
    """2D投影サイズスコアを計算する。

    各グリッド点について、視認可能な全カメラの投影解像度を計算し、
    min(ppm / target_ppm, 1.0) をスコアとして集約する。

    Args:
        cameras: カメラのリスト。len = M。
        grid_points: グリッド点群 [m]。shape (N, 3)。
        visibility_matrix: 視認性行列。shape (M, N), dtype=bool。
        target_ppm: 目標投影解像度 [px/m]。正の値のみ。この値以上でスコア=1.0。

    Returns:
        ProjectionScoreResult インスタンス。

    Raises:
        ValueError: grid_points が2次元でない場合。
        ValueError: grid_points.shape[1] != 3 の場合。
        ValueError: visibility_matrix が2次元でない場合。
        ValueError: visibility_matrix.shape[0] != len(cameras) の場合。
        ValueError: visibility_matrix.shape[1] != grid_points.shape[0] の場合。
        ValueError: target_ppm <= 0 の場合。
    """
    vis = np.asarray(visibility_matrix, dtype=bool)
    pts = np.asarray(grid_points, dtype=np.float64)

    if pts.ndim != 2:
        raise ValueError(f"grid_points must be 2D, got {pts.ndim}D")
    if pts.shape[1] != 3:
        raise ValueError(f"grid_points.shape[1] must be 3, got {pts.shape[1]}")
    if vis.ndim != 2:
        raise ValueError(f"visibility_matrix must be 2D, got {vis.ndim}D")

    M = len(cameras)
    N = pts.shape[0]

    if vis.shape[0] != M:
        raise ValueError(
            f"visibility_matrix.shape[0]={vis.shape[0]} != len(cameras)={M}"
        )
    if vis.shape[1] != N:
        raise ValueError(
            f"visibility_matrix.shape[1]={vis.shape[1]} != grid_points rows={N}"
        )
    if target_ppm <= 0:
        raise ValueError(f"target_ppm must be positive, got {target_ppm}")

    # 早期リターン
    if M == 0 or N == 0:
        return ProjectionScoreResult(
            point_best_scores=np.zeros(N, dtype=np.float64),
            point_mean_scores=np.zeros(N, dtype=np.float64),
            point_best_ppm=np.zeros(N, dtype=np.float64),
            mean_score=0.0,
        )

    # 初期化
    point_best_ppm = np.zeros(N, dtype=np.float64)
    point_score_sums = np.zeros(N, dtype=np.float64)
    point_num_visible = np.zeros(N, dtype=int)

    # 各カメラをループ
    for i in range(M):
        cam_visible = vis[i]  # (N,)
        if not cam_visible.any():
            continue

        ppm = calculate_pixel_per_meter(
            cameras[i].position, pts, cameras[i].intrinsics.fx
        )  # (N,)
        cam_scores = np.minimum(ppm / target_ppm, 1.0)  # (N,)

        # ベストppmの更新
        improved = cam_visible & (ppm > point_best_ppm)
        point_best_ppm[improved] = ppm[improved]

        # 合計・カメラ数の更新
        point_score_sums += cam_scores * cam_visible
        point_num_visible += cam_visible.astype(int)

    # ベストスコア
    point_best_scores = np.minimum(point_best_ppm / target_ppm, 1.0)

    # 平均スコア
    has_visible = point_num_visible > 0
    point_mean_scores = np.zeros(N, dtype=np.float64)
    point_mean_scores[has_visible] = (
        point_score_sums[has_visible] / point_num_visible[has_visible]
    )

    # 全体スコア
    mean_score = float(point_best_scores.mean()) if N > 0 else 0.0

    return ProjectionScoreResult(
        point_best_scores=point_best_scores,
        point_mean_scores=point_mean_scores,
        point_best_ppm=point_best_ppm,
        mean_score=mean_score,
    )
