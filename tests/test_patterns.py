"""F12: 配置パターン定義のテスト。"""

import numpy as np
import pytest

from camera_placement.models.camera import Camera
from camera_placement.models.environment import AABB, Room, create_default_room
from camera_placement.placement.patterns import (
    CameraConfig,
    PlacementPreset,
    create_cameras,
    get_all_presets,
    get_preset,
    list_preset_names,
)

EXPECTED_NAMES = [
    "upper_corners",
    "wall_uniform",
    "overhead_grid",
    "bed_focused",
    "hybrid",
]

ROOM_CENTER_TARGET = (1.4, 1.75, 0.9)
BED_CENTER_TARGET = (1.4, 2.5, 0.5)


# =============================================================================
# カテゴリA: get_preset
# =============================================================================


class TestGetPreset:
    """A: get_preset のテスト。"""

    def test_a1_get_valid_preset(self) -> None:
        """A1: 有効な名前で PlacementPreset を取得できる。"""
        preset = get_preset("upper_corners")
        assert isinstance(preset, PlacementPreset)
        assert preset.name == "upper_corners"

    @pytest.mark.parametrize("name", EXPECTED_NAMES)
    def test_a2_all_preset_names_retrievable(self, name: str) -> None:
        """A2: 全プリセット名で取得可能。"""
        preset = get_preset(name)
        assert isinstance(preset, PlacementPreset)
        assert preset.name == name

    def test_a3_invalid_name_raises_key_error(self) -> None:
        """A3: 存在しない名前で KeyError。"""
        with pytest.raises(KeyError):
            get_preset("invalid")

    def test_a4_empty_string_raises_key_error(self) -> None:
        """A4: 空文字列で KeyError。"""
        with pytest.raises(KeyError):
            get_preset("")

    def test_a5_uppercase_raises_key_error(self) -> None:
        """A5: 大文字で KeyError（大文字小文字を区別）。"""
        with pytest.raises(KeyError):
            get_preset("UPPER_CORNERS")

    def test_a6_key_error_message_contains_available_names(self) -> None:
        """A6: KeyError メッセージに利用可能名一覧を含む。"""
        with pytest.raises(KeyError, match="Available") as exc_info:
            get_preset("invalid")
        assert "upper_corners" in str(exc_info.value)


# =============================================================================
# カテゴリB: get_all_presets
# =============================================================================


class TestGetAllPresets:
    """B: get_all_presets のテスト。"""

    def test_b1_list_length(self) -> None:
        """B1: リスト長が5。"""
        presets = get_all_presets()
        assert len(presets) == 5

    def test_b2_all_elements_are_placement_preset(self) -> None:
        """B2: 全要素が PlacementPreset。"""
        presets = get_all_presets()
        for preset in presets:
            assert isinstance(preset, PlacementPreset)

    def test_b3_order(self) -> None:
        """B3: 定義順の順序。"""
        presets = get_all_presets()
        names = [p.name for p in presets]
        assert names == EXPECTED_NAMES

    def test_b4_camera_configs_length(self) -> None:
        """B4: 全プリセットで camera_configs が6要素。"""
        presets = get_all_presets()
        for preset in presets:
            assert len(preset.camera_configs) == 6


# =============================================================================
# カテゴリC: list_preset_names
# =============================================================================


class TestListPresetNames:
    """C: list_preset_names のテスト。"""

    def test_c1_names_list(self) -> None:
        """C1: 名前一覧が期待通り。"""
        names = list_preset_names()
        assert names == EXPECTED_NAMES

    def test_c2_list_length(self) -> None:
        """C2: リスト長が5。"""
        names = list_preset_names()
        assert len(names) == 5


# =============================================================================
# カテゴリD: PlacementPreset / CameraConfig データ検証
# =============================================================================


class TestPresetDataValidation:
    """D: プリセットデータの検証。"""

    @pytest.fixture()
    def all_presets(self) -> list[PlacementPreset]:
        return get_all_presets()

    def test_d1_name_is_string(self, all_presets: list[PlacementPreset]) -> None:
        """D1: preset.name が文字列。"""
        for preset in all_presets:
            assert isinstance(preset.name, str)

    def test_d2_description_is_non_empty(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D2: preset.description が非空文字列。"""
        for preset in all_presets:
            assert isinstance(preset.description, str)
            assert len(preset.description) > 0

    def test_d3_camera_configs_is_tuple(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D3: camera_configs が tuple。"""
        for preset in all_presets:
            assert isinstance(preset.camera_configs, tuple)

    def test_d4_position_is_3_element_tuple(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D4: CameraConfig の position が3要素タプル。"""
        for preset in all_presets:
            for cfg in preset.camera_configs:
                assert isinstance(cfg.position, tuple)
                assert len(cfg.position) == 3

    def test_d5_look_at_is_3_element_tuple(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D5: CameraConfig の look_at が3要素タプル。"""
        for preset in all_presets:
            for cfg in preset.camera_configs:
                assert isinstance(cfg.look_at, tuple)
                assert len(cfg.look_at) == 3

    def test_d6_all_positions_within_camera_zone(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D6: 全カメラ位置がカメラ設置可能領域内。"""
        room = create_default_room()
        for preset in all_presets:
            positions = np.array([cfg.position for cfg in preset.camera_configs])
            valid = room.is_valid_camera_position(positions)
            assert np.all(valid), (
                f"Preset '{preset.name}': positions outside camera zone"
            )

    def test_d7_position_not_equal_look_at(
        self, all_presets: list[PlacementPreset]
    ) -> None:
        """D7: position != look_at。"""
        for preset in all_presets:
            for cfg in preset.camera_configs:
                assert cfg.position != cfg.look_at


# =============================================================================
# カテゴリE: create_cameras
# =============================================================================


class TestCreateCameras:
    """E: create_cameras のテスト。"""

    def test_e1_basic_creation_room_none(self) -> None:
        """E1: room=None で6台の Camera リスト。"""
        preset = get_preset("upper_corners")
        cameras = create_cameras(preset)
        assert len(cameras) == 6
        for cam in cameras:
            assert isinstance(cam, Camera)

    @pytest.mark.parametrize("name", EXPECTED_NAMES)
    def test_e2_all_presets_create_cameras(self, name: str) -> None:
        """E2: 全プリセットで生成可能。"""
        preset = get_preset(name)
        cameras = create_cameras(preset)
        assert len(cameras) == 6

    def test_e3_camera_position_matches_preset(self) -> None:
        """E3: Camera の position がプリセット定義と一致。"""
        preset = get_preset("upper_corners")
        cameras = create_cameras(preset)
        for cam, cfg in zip(cameras, preset.camera_configs):
            np.testing.assert_allclose(cam.position, np.array(cfg.position))

    def test_e4_camera_look_at_matches_preset(self) -> None:
        """E4: Camera の look_at がプリセット定義と一致。"""
        preset = get_preset("upper_corners")
        cameras = create_cameras(preset)
        for cam, cfg in zip(cameras, preset.camera_configs):
            np.testing.assert_allclose(cam.look_at, np.array(cfg.look_at))

    def test_e5_room_validation_passes_default(self) -> None:
        """E5: デフォルト Room でバリデーション通過。"""
        preset = get_preset("upper_corners")
        room = create_default_room()
        cameras = create_cameras(preset, room=room)
        assert len(cameras) == 6

    @pytest.mark.parametrize("name", EXPECTED_NAMES)
    def test_e6_all_presets_pass_room_validation(self, name: str) -> None:
        """E6: 全プリセットでデフォルト Room バリデーション通過。"""
        preset = get_preset(name)
        room = create_default_room()
        cameras = create_cameras(preset, room=room)
        assert len(cameras) == 6

    def test_e7_room_validation_fails_narrow_zone(self) -> None:
        """E7: 狭い camera_zone の Room で ValueError。"""
        preset = get_preset("upper_corners")
        narrow_room = Room(
            camera_zone=AABB(
                min_point=np.array([0.5, 0.5, 0.5]),
                max_point=np.array([2.0, 2.0, 2.0]),
            )
        )
        with pytest.raises(ValueError):
            create_cameras(preset, room=narrow_room)

    def test_e8_value_error_message_contains_details(self) -> None:
        """E8: ValueError メッセージにカメラインデックスと座標情報。"""
        preset = get_preset("upper_corners")
        narrow_room = Room(
            camera_zone=AABB(
                min_point=np.array([0.5, 0.5, 0.5]),
                max_point=np.array([2.0, 2.0, 2.0]),
            )
        )
        with pytest.raises(ValueError, match="Camera") as exc_info:
            create_cameras(preset, room=narrow_room)
        assert "position" in str(exc_info.value)


# =============================================================================
# カテゴリF: プリセット固有の検証
# =============================================================================


class TestPresetSpecificValidation:
    """F: プリセット固有の検証。"""

    def test_f1_upper_corners_all_z_2_3(self) -> None:
        """F1: upper_corners の全カメラ Z=2.3。"""
        preset = get_preset("upper_corners")
        for cfg in preset.camera_configs:
            assert cfg.position[2] == pytest.approx(2.3)

    def test_f2_wall_uniform_all_z_2_3(self) -> None:
        """F2: wall_uniform の全カメラ Z=2.3。"""
        preset = get_preset("wall_uniform")
        for cfg in preset.camera_configs:
            assert cfg.position[2] == pytest.approx(2.3)

    def test_f3_overhead_grid_all_z_2_3(self) -> None:
        """F3: overhead_grid の全カメラ Z=2.3。"""
        preset = get_preset("overhead_grid")
        for cfg in preset.camera_configs:
            assert cfg.position[2] == pytest.approx(2.3)

    def test_f4_hybrid_mixed_height(self) -> None:
        """F4: hybrid の C1-C4 が Z=2.3、C5-C6 が Z=1.8。"""
        preset = get_preset("hybrid")
        configs = preset.camera_configs
        for i in range(4):
            assert configs[i].position[2] == pytest.approx(2.3)
        for i in range(4, 6):
            assert configs[i].position[2] == pytest.approx(1.8)

    def test_f5_bed_focused_look_at(self) -> None:
        """F5: bed_focused の全カメラ注視点がベッド中央。"""
        preset = get_preset("bed_focused")
        for cfg in preset.camera_configs:
            assert cfg.look_at == BED_CENTER_TARGET

    def test_f6_hybrid_mixed_look_at(self) -> None:
        """F6: hybrid の C1-C4 が部屋中央、C5-C6 がベッド中央注視。"""
        preset = get_preset("hybrid")
        configs = preset.camera_configs
        for i in range(4):
            assert configs[i].look_at == ROOM_CENTER_TARGET
        for i in range(4, 6):
            assert configs[i].look_at == BED_CENTER_TARGET
