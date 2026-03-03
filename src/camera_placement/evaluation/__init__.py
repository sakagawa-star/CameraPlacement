"""evaluation パッケージ: カバレッジ・品質評価機能。"""

from camera_placement.evaluation.angle_score import (
    AngleScoreResult,
    calculate_angle_score,
    calculate_pair_angles,
)
from camera_placement.evaluation.coverage import (
    CoverageResult,
    CoverageStats,
    VolumeCoverage,
    calculate_coverage,
    calculate_coverage_stats,
    calculate_volume_coverage,
)
from camera_placement.evaluation.evaluator import (
    EvaluationResult,
    QualityScoreResult,
    VolumeQualityScore,
    calculate_quality_score,
    evaluate_placement,
)
from camera_placement.evaluation.projection_score import (
    ProjectionScoreResult,
    calculate_pixel_per_meter,
    calculate_projection_score,
)

__all__ = [
    "AngleScoreResult",
    "CoverageResult",
    "CoverageStats",
    "EvaluationResult",
    "ProjectionScoreResult",
    "QualityScoreResult",
    "VolumeCoverage",
    "VolumeQualityScore",
    "calculate_angle_score",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_pair_angles",
    "calculate_pixel_per_meter",
    "calculate_projection_score",
    "calculate_quality_score",
    "calculate_volume_coverage",
    "evaluate_placement",
]
