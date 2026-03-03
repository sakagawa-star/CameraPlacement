"""F08: 三角測量角度スコア。

同一の3Dグリッド点を観測する複数カメラの視線角度差（角度分離）を計算し、
三角測量精度の指標としてスコア化する。スコア関数は sin(angle) を使用する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.models.camera import Camera


@dataclass
class AngleScoreResult:
    """角度スコアの計算結果。

    point_best_scores を主要指標とし、mean_score は point_best_scores から導出する。

    Attributes:
        point_best_scores: 各点のベストペアスコア (sin(angle))。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。有効ペアなしの点は 0.0。
        point_mean_scores: 各点の平均ペアスコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。有効ペアなしの点は 0.0。
        point_best_angles: 各点のベストペア角度 [rad]。shape (N,), dtype=float64。
            値域 [0.0, π]。有効ペアなしの点は 0.0。
        point_num_pairs: 各点の有効ペア数。shape (N,), dtype=int。
        mean_score: point_best_scores の算術平均。float。点数0の場合は 0.0。
    """

    point_best_scores: np.ndarray   # shape (N,), dtype=float64
    point_mean_scores: np.ndarray   # shape (N,), dtype=float64
    point_best_angles: np.ndarray   # shape (N,), dtype=float64
    point_num_pairs: np.ndarray     # shape (N,), dtype=int
    mean_score: float


def calculate_pair_angles(
    camera_pos_a: np.ndarray,
    camera_pos_b: np.ndarray,
    points: np.ndarray,
) -> np.ndarray:
    """2台のカメラの視線角度差を全点に対してバッチ計算する。

    各点について、カメラAからの視線ベクトルとカメラBからの視線ベクトルの
    間の角度を計算する。

    Args:
        camera_pos_a: カメラA位置 [m]。shape (3,)。
        camera_pos_b: カメラB位置 [m]。shape (3,)。
        points: 3D点群 [m]。shape (N, 3)。

    Returns:
        shape (N,) の角度配列 [rad]。値域 [0, π]。
        カメラが点と同一位置の場合は 0.0。
    """
    v_a = points - camera_pos_a  # (N, 3)
    v_b = points - camera_pos_b  # (N, 3)

    norm_a = np.linalg.norm(v_a, axis=1)  # (N,)
    norm_b = np.linalg.norm(v_b, axis=1)  # (N,)

    denom = norm_a * norm_b  # (N,)
    zero_mask = denom < 1e-10
    safe_denom = np.where(zero_mask, 1.0, denom)

    dot_product = np.sum(v_a * v_b, axis=1)  # (N,)
    cos_angle = dot_product / safe_denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)

    angles = np.arccos(cos_angle)  # (N,)
    angles[zero_mask] = 0.0

    return angles


def calculate_angle_score(
    cameras: list[Camera],
    grid_points: np.ndarray,
    visibility_matrix: np.ndarray,
) -> AngleScoreResult:
    """三角測量角度スコアを計算する。

    各グリッド点について、視認可能な全カメラペアの角度分離を計算し、
    sin(angle) をスコアとして集約する。

    Args:
        cameras: カメラのリスト。len = M。
        grid_points: グリッド点群 [m]。shape (N, 3)。
        visibility_matrix: 視認性行列。shape (M, N), dtype=bool。

    Returns:
        AngleScoreResult インスタンス。

    Raises:
        ValueError: grid_points が2次元でない場合。
        ValueError: grid_points.shape[1] != 3 の場合。
        ValueError: visibility_matrix が2次元でない場合。
        ValueError: visibility_matrix.shape[0] != len(cameras) の場合。
        ValueError: visibility_matrix.shape[1] != grid_points.shape[0] の場合。
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

    # 早期リターン
    if M < 2 or N == 0:
        return AngleScoreResult(
            point_best_scores=np.zeros(N, dtype=np.float64),
            point_mean_scores=np.zeros(N, dtype=np.float64),
            point_best_angles=np.zeros(N, dtype=np.float64),
            point_num_pairs=np.zeros(N, dtype=int),
            mean_score=0.0,
        )

    # 初期化
    point_best_scores = np.zeros(N, dtype=np.float64)
    point_score_sums = np.zeros(N, dtype=np.float64)
    point_num_pairs = np.zeros(N, dtype=int)
    point_best_angles = np.zeros(N, dtype=np.float64)

    # カメラ位置配列
    cam_positions = np.array([c.position for c in cameras])  # (M, 3)

    # 全ペアをループ
    for i in range(M):
        for j in range(i + 1, M):
            pair_visible = vis[i] & vis[j]  # (N,)
            if not pair_visible.any():
                continue

            angles = calculate_pair_angles(
                cam_positions[i], cam_positions[j], pts
            )  # (N,)
            pair_scores = np.sin(angles)  # (N,)

            # ベストスコアの更新
            improved = pair_visible & (pair_scores > point_best_scores)
            point_best_scores[improved] = pair_scores[improved]
            point_best_angles[improved] = angles[improved]

            # 合計・ペア数の更新
            point_score_sums += pair_scores * pair_visible
            point_num_pairs += pair_visible.astype(int)

    # 平均ペアスコア
    has_pairs = point_num_pairs > 0
    point_mean_scores = np.zeros(N, dtype=np.float64)
    point_mean_scores[has_pairs] = (
        point_score_sums[has_pairs] / point_num_pairs[has_pairs]
    )

    # 全体スコア
    mean_score = float(point_best_scores.mean()) if N > 0 else 0.0

    return AngleScoreResult(
        point_best_scores=point_best_scores,
        point_mean_scores=point_mean_scores,
        point_best_angles=point_best_angles,
        point_num_pairs=point_num_pairs,
        mean_score=mean_score,
    )
