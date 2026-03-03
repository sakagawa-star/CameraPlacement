"""evaluation パッケージ: カバレッジ・品質評価機能。"""

from camera_placement.evaluation.coverage import (
    CoverageResult,
    CoverageStats,
    VolumeCoverage,
    calculate_coverage,
    calculate_coverage_stats,
    calculate_volume_coverage,
)

__all__ = [
    "CoverageResult",
    "CoverageStats",
    "VolumeCoverage",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_volume_coverage",
]
