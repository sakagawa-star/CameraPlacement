"""placement パッケージ: カメラ配置パターンの定義と比較。"""

from camera_placement.placement.comparison import (
    ComparisonResult,
    EvaluationParams,
    PresetEvaluation,
    compare_presets,
    evaluate_preset,
    generate_report,
    save_report,
)
from camera_placement.placement.patterns import (
    CameraConfig,
    PlacementPreset,
    create_cameras,
    get_all_presets,
    get_preset,
    list_preset_names,
)

__all__ = [
    "CameraConfig",
    "ComparisonResult",
    "EvaluationParams",
    "PlacementPreset",
    "PresetEvaluation",
    "compare_presets",
    "create_cameras",
    "evaluate_preset",
    "generate_report",
    "get_all_presets",
    "get_preset",
    "list_preset_names",
    "save_report",
]
