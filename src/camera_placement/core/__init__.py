"""core パッケージ: 視認性判定のコア機能。"""

from camera_placement.core.frustum import FrustumChecker
from camera_placement.core.occlusion import (
    check_bed_occlusion,
    check_bed_occlusion_multi_camera,
)
from camera_placement.core.visibility import (
    check_visibility,
    check_visibility_multi_camera,
)

__all__ = [
    "FrustumChecker",
    "check_bed_occlusion",
    "check_bed_occlusion_multi_camera",
    "check_visibility",
    "check_visibility_multi_camera",
]
