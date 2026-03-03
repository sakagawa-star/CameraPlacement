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

__all__ = [
    "AngleScoreResult",
    "CoverageResult",
    "CoverageStats",
    "VolumeCoverage",
    "calculate_angle_score",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_pair_angles",
    "calculate_volume_coverage",
]
