"""F12: 配置パターン定義。

手動設計の5種類のカメラ配置パターンをプリセットとして定義し、
Camera オブジェクトのリストを生成する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.models.camera import Camera, create_camera
from camera_placement.models.environment import Room


@dataclass(frozen=True)
class CameraConfig:
    """1台のカメラの位置と注視点の設定。

    Attributes:
        position: カメラ位置 (x, y, z) [m]。
        look_at: 注視点 (x, y, z) [m]。
    """

    position: tuple[float, float, float]
    look_at: tuple[float, float, float]


@dataclass(frozen=True)
class PlacementPreset:
    """カメラ配置プリセット。

    Attributes:
        name: プリセット名（英語スネークケース）。
        description: プリセットの説明（日本語）。
        camera_configs: 6台のカメラ設定。要素数は必ず6。
    """

    name: str
    description: str
    camera_configs: tuple[CameraConfig, ...]


# プリセット定義で使用する注視点の定数
_ROOM_CENTER_TARGET: tuple[float, float, float] = (1.4, 1.75, 0.9)
_BED_CENTER_TARGET: tuple[float, float, float] = (1.4, 2.5, 0.5)

# プリセット辞書（挿入順保持）
_PRESETS: dict[str, PlacementPreset] = {}


def _register(preset: PlacementPreset) -> None:
    """プリセットを辞書に登録する。"""
    _PRESETS[preset.name] = preset


# --- プリセット定義 ---

_register(PlacementPreset(
    name="upper_corners",
    description="上部コーナー型: カメラ設置可能領域の上部4隅 + 前後壁中央2箇所に配置",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="wall_uniform",
    description="壁面均等型: 左右壁面に各2台 + 前後壁面に各1台で周囲に均等分散",
    camera_configs=(
        CameraConfig(position=(0.2, 1.0, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 2.5, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.0, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 2.5, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="overhead_grid",
    description="天井格子型: 天井直下に2×3の格子状に配置",
    camera_configs=(
        CameraConfig(position=(0.8, 0.6, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 0.6, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.8, 1.75, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 1.75, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.8, 2.9, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 2.9, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="bed_focused",
    description="ベッド集中型: 6台全てがベッド中央を注視。ベッド周囲の座位・臥位カバレッジを重視",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(0.2, 1.75, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.75, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.0), look_at=_BED_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="hybrid",
    description="ハイブリッド型: 上部4隅で広範囲カバレッジ + 壁面中段2台でベッド角度改善",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 1.75, 1.8), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.75, 1.8), look_at=_BED_CENTER_TARGET),
    ),
))


# --- 公開関数 ---


def get_preset(name: str) -> PlacementPreset:
    """名前を指定してプリセットを取得する。

    Args:
        name: プリセット名。

    Returns:
        PlacementPreset インスタンス。

    Raises:
        KeyError: 指定された名前のプリセットが存在しない場合。
            メッセージに利用可能な名前一覧を含む。
    """
    if name not in _PRESETS:
        raise KeyError(
            f"Unknown preset name: '{name}'. "
            f"Available: {list(_PRESETS.keys())}"
        )
    return _PRESETS[name]


def get_all_presets() -> list[PlacementPreset]:
    """全プリセットをリストで取得する。

    Returns:
        PlacementPreset のリスト（5要素）。定義順。
    """
    return list(_PRESETS.values())


def list_preset_names() -> list[str]:
    """全プリセット名をリストで取得する。

    Returns:
        プリセット名のリスト（5要素）。定義順。
    """
    return list(_PRESETS.keys())


def create_cameras(
    preset: PlacementPreset,
    room: Room | None = None,
) -> list[Camera]:
    """プリセットから Camera オブジェクトのリストを生成する。

    Args:
        preset: カメラ配置プリセット。
        room: 病室モデル。非 None の場合、全カメラ位置が
            room.camera_zone 内にあることを検証する。

    Returns:
        Camera オブジェクトのリスト（6要素）。

    Raises:
        ValueError: room が非 None かつ、1台以上のカメラ位置が
            room.camera_zone の範囲外の場合。
    """
    if room is not None:
        positions = [np.array(cfg.position) for cfg in preset.camera_configs]
        positions_array = np.stack(positions)
        valid = room.is_valid_camera_position(positions_array)
        if not np.all(valid):
            invalid_indices = np.where(~valid)[0]
            details = [
                f"  Camera {i}: position={preset.camera_configs[i].position}"
                for i in invalid_indices
            ]
            raise ValueError(
                "Camera positions outside camera zone:\n" + "\n".join(details)
            )

    cameras = []
    for cfg in preset.camera_configs:
        cam = create_camera(
            position=list(cfg.position),
            look_at=list(cfg.look_at),
        )
        cameras.append(cam)
    return cameras
