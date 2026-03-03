"""optimization パッケージ: カメラ配置の最適化機能。"""

from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    calculate_position_penalty,
    cameras_to_params,
    get_parameter_bounds,
    params_to_cameras,
)

__all__ = [
    "ObjectiveFunction",
    "ObjectiveResult",
    "calculate_position_penalty",
    "cameras_to_params",
    "get_parameter_bounds",
    "params_to_cameras",
]
