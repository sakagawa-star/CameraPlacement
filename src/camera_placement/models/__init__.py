"""空間モデル定義サブパッケージ。"""

from camera_placement.models.environment import AABB, Room, create_default_room
from camera_placement.models.camera import CameraIntrinsics, Camera, create_camera
from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
    create_merged_grid,
)

__all__ = [
    "AABB",
    "Room",
    "create_default_room",
    "CameraIntrinsics",
    "Camera",
    "create_camera",
    "ActivityType",
    "ActivityVolume",
    "create_activity_volumes",
    "create_merged_grid",
]
