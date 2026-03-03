"""F10: 統合品質スコア。

F07（カバレッジ）、F08（三角測量角度スコア）、F09（2D投影サイズスコア）の
3つの評価指標を統合し、カメラ配置全体の品質を1つのスコアで返す。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.evaluation.angle_score import (
    AngleScoreResult,
    calculate_angle_score,
)
from camera_placement.evaluation.coverage import (
    CoverageResult,
    calculate_coverage,
)
from camera_placement.evaluation.projection_score import (
    ProjectionScoreResult,
    calculate_projection_score,
)
from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
)
from camera_placement.models.camera import Camera
from camera_placement.models.environment import Room


@dataclass
class QualityScoreResult:
    """統合品質スコアの計算結果。

    Attributes:
        quality_score: 統合品質スコア。加重和。値域 [0.0, 1.0]。
        coverage_score: カバレッジスコア (coverage_3plus)。値域 [0.0, 1.0]。
        angle_score: 角度スコア (mean_score)。値域 [0.0, 1.0]。
        projection_score: 投影スコア (mean_score)。値域 [0.0, 1.0]。
        weight_coverage: 正規化後のカバレッジ重み。
        weight_angle: 正規化後の角度重み。
        weight_projection: 正規化後の投影重み。
        point_quality_scores: 各点のポイント品質スコア。shape (N,), dtype=float64。
            値域 [0.0, 1.0]。
        mean_point_quality: point_quality_scores の算術平均。点数0の場合は 0.0。
    """

    quality_score: float
    coverage_score: float
    angle_score: float
    projection_score: float
    weight_coverage: float
    weight_angle: float
    weight_projection: float
    point_quality_scores: np.ndarray  # shape (N,), dtype=float64
    mean_point_quality: float


@dataclass
class VolumeQualityScore:
    """活動ボリューム別の品質スコア。

    Attributes:
        activity_type: 動作パターンの種別。
        quality_score: 統合品質スコア [0.0, 1.0]。
        coverage_score: カバレッジスコア (coverage_3plus) [0.0, 1.0]。
        angle_score: 角度スコア (mean_score) [0.0, 1.0]。
        projection_score: 投影スコア (mean_score) [0.0, 1.0]。
    """

    activity_type: ActivityType
    quality_score: float
    coverage_score: float
    angle_score: float
    projection_score: float


@dataclass
class EvaluationResult:
    """一括評価の全体結果。

    evaluate_placement の戻り値。F07/F08/F09/F10 の全結果を保持する。

    Attributes:
        quality: 統合品質スコア（統合グリッド全体）。
        coverage_result: F07 のカバレッジ計算結果。
        angle_result: F08 の角度スコア計算結果。
        projection_result: F09 の投影スコア計算結果。
        volume_qualities: 活動ボリューム別の品質スコア。
    """

    quality: QualityScoreResult
    coverage_result: CoverageResult
    angle_result: AngleScoreResult
    projection_result: ProjectionScoreResult
    volume_qualities: dict[ActivityType, VolumeQualityScore]


def _validate_weights(
    weight_coverage: float,
    weight_angle: float,
    weight_projection: float,
) -> None:
    """重みのバリデーション。

    Args:
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。

    Raises:
        ValueError: 重みのいずれかが負の場合。
        ValueError: 重みの合計が 0 の場合。
    """
    if weight_coverage < 0 or weight_angle < 0 or weight_projection < 0:
        raise ValueError("weights must be non-negative")
    if weight_coverage + weight_angle + weight_projection == 0:
        raise ValueError("sum of weights must be positive")


def calculate_quality_score(
    coverage_score: float,
    angle_score: float,
    projection_score: float,
    point_angle_scores: np.ndarray,
    point_projection_scores: np.ndarray,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> QualityScoreResult:
    """統合品質スコアを計算する。

    3つのコンポーネントスコアの加重和で統合品質スコアを算出する。
    重みは内部で合計 1.0 に正規化される。

    Args:
        coverage_score: カバレッジスコア [0.0, 1.0]。
        angle_score: 角度スコア [0.0, 1.0]。
        projection_score: 投影スコア [0.0, 1.0]。
        point_angle_scores: 各点の角度ベストスコア。shape (N,), dtype=float64。
        point_projection_scores: 各点の投影ベストスコア。shape (N,), dtype=float64。
        weight_coverage: カバレッジの重み。非負。
        weight_angle: 角度スコアの重み。非負。
        weight_projection: 投影スコアの重み。非負。

    Returns:
        QualityScoreResult インスタンス。

    Raises:
        ValueError: 重みのいずれかが負の場合。
        ValueError: 重みの合計が 0 の場合。
        ValueError: point_angle_scores と point_projection_scores の長さが不一致の場合。
    """
    _validate_weights(weight_coverage, weight_angle, weight_projection)

    pt_angle = np.asarray(point_angle_scores, dtype=np.float64)
    pt_proj = np.asarray(point_projection_scores, dtype=np.float64)
    if pt_angle.shape[0] != pt_proj.shape[0]:
        raise ValueError(
            f"point_angle_scores length {pt_angle.shape[0]} != "
            f"point_projection_scores length {pt_proj.shape[0]}"
        )

    n = pt_angle.shape[0]

    # 重みの正規化
    w_sum = weight_coverage + weight_angle + weight_projection
    w_cov = weight_coverage / w_sum
    w_ang = weight_angle / w_sum
    w_proj = weight_projection / w_sum

    # 統合品質スコア
    quality = w_cov * coverage_score + w_ang * angle_score + w_proj * projection_score

    # ポイント品質スコア
    w_point_sum = weight_angle + weight_projection
    if w_point_sum > 0:
        w_ang_pt = weight_angle / w_point_sum
        w_proj_pt = weight_projection / w_point_sum
        point_quality = w_ang_pt * pt_angle + w_proj_pt * pt_proj
    else:
        point_quality = np.zeros(n, dtype=np.float64)

    # mean_point_quality
    mean_pq = float(point_quality.mean()) if n > 0 else 0.0

    return QualityScoreResult(
        quality_score=quality,
        coverage_score=coverage_score,
        angle_score=angle_score,
        projection_score=projection_score,
        weight_coverage=w_cov,
        weight_angle=w_ang,
        weight_projection=w_proj,
        point_quality_scores=point_quality,
        mean_point_quality=mean_pq,
    )


def evaluate_placement(
    cameras: list[Camera],
    room: Room,
    volumes: list[ActivityVolume] | None = None,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
    target_ppm: float = 500.0,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> EvaluationResult:
    """カメラ配置を一括評価する。

    F07（カバレッジ）→ F08（角度スコア）→ F09（投影スコア）→ F10（統合スコア）
    の全計算を実行し、結果を返す。

    Args:
        cameras: カメラのリスト。
        room: 病室モデル。
        volumes: 活動ボリューム。None の場合は自動生成。
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。

    Returns:
        EvaluationResult インスタンス。

    Raises:
        ValueError: 重みのいずれかが負の場合。
        ValueError: 重みの合計が 0 の場合。
    """
    # Step 0: 重みのバリデーション（早期検出）
    _validate_weights(weight_coverage, weight_angle, weight_projection)

    # Step 1: F07 カバレッジ計算
    coverage_result = calculate_coverage(cameras, room, volumes, grid_spacing, near, far)

    # Step 2: F08 角度スコア計算（統合グリッド）
    angle_result = calculate_angle_score(
        coverage_result.cameras,
        coverage_result.merged_grid,
        coverage_result.visibility_matrix,
    )

    # Step 3: F09 投影スコア計算（統合グリッド）
    projection_result = calculate_projection_score(
        coverage_result.cameras,
        coverage_result.merged_grid,
        coverage_result.visibility_matrix,
        target_ppm,
    )

    # Step 4: F10 統合品質スコア計算（統合グリッド）
    quality = calculate_quality_score(
        coverage_result.stats.coverage_3plus,
        angle_result.mean_score,
        projection_result.mean_score,
        angle_result.point_best_scores,
        projection_result.point_best_scores,
        weight_coverage,
        weight_angle,
        weight_projection,
    )

    # Step 5: 活動ボリューム別スコア計算
    if volumes is None:
        volumes_used = create_activity_volumes(room, grid_spacing)
    else:
        volumes_used = volumes

    w_sum = weight_coverage + weight_angle + weight_projection
    w_cov = weight_coverage / w_sum
    w_ang = weight_angle / w_sum
    w_proj = weight_projection / w_sum

    volume_qualities: dict[ActivityType, VolumeQualityScore] = {}
    for vol in volumes_used:
        act_type = vol.activity_type
        if act_type not in coverage_result.volume_coverages:
            continue
        vc = coverage_result.volume_coverages[act_type]
        vol_angle = calculate_angle_score(
            coverage_result.cameras, vol.grid_points, vc.visibility_matrix
        )
        vol_proj = calculate_projection_score(
            coverage_result.cameras, vol.grid_points, vc.visibility_matrix, target_ppm
        )
        vol_quality = (
            w_cov * vc.stats.coverage_3plus
            + w_ang * vol_angle.mean_score
            + w_proj * vol_proj.mean_score
        )
        volume_qualities[act_type] = VolumeQualityScore(
            activity_type=act_type,
            quality_score=vol_quality,
            coverage_score=vc.stats.coverage_3plus,
            angle_score=vol_angle.mean_score,
            projection_score=vol_proj.mean_score,
        )

    return EvaluationResult(
        quality=quality,
        coverage_result=coverage_result,
        angle_result=angle_result,
        projection_result=projection_result,
        volume_qualities=volume_qualities,
    )
