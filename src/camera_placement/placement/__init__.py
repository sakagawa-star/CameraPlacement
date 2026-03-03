"""placement パッケージ: カメラ配置パターンの定義。"""

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
    "PlacementPreset",
    "create_cameras",
    "get_all_presets",
    "get_preset",
    "list_preset_names",
]
