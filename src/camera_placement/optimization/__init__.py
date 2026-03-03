"""optimization パッケージ: カメラ配置の最適化機能。"""

from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    calculate_position_penalty,
    cameras_to_params,
    get_parameter_bounds,
    params_to_cameras,
)
from camera_placement.optimization.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    create_convergence_plot,
    generate_optimization_report,
    optimize_placement,
    save_optimization_report,
    visualize_result,
)

__all__ = [
    "ObjectiveFunction",
    "ObjectiveResult",
    "OptimizationConfig",
    "OptimizationResult",
    "calculate_position_penalty",
    "cameras_to_params",
    "create_convergence_plot",
    "generate_optimization_report",
    "get_parameter_bounds",
    "optimize_placement",
    "params_to_cameras",
    "save_optimization_report",
    "visualize_result",
]
