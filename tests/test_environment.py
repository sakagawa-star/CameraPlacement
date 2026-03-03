"""F01: 空間モデルのテスト。

設計書のテスト計画（19ケース）に基づく。
"""

import numpy as np
import pytest

from camera_placement.models.environment import AABB, Room, create_default_room


class TestAABBContains:
    """AABB.contains の基本テスト。"""

    def test_point_inside(self) -> None:
        aabb = AABB(min_point=np.array([0.0, 0.0, 0.0]), max_point=np.array([1.0, 1.0, 1.0]))
        result = aabb.contains(np.array([0.5, 0.5, 0.5]))
        assert result[0] is np.True_

    def test_point_outside(self) -> None:
        aabb = AABB(min_point=np.array([0.0, 0.0, 0.0]), max_point=np.array([1.0, 1.0, 1.0]))
        result = aabb.contains(np.array([1.5, 0.5, 0.5]))
        assert result[0] is np.False_

    def test_point_on_boundary(self) -> None:
        aabb = AABB(min_point=np.array([0.0, 0.0, 0.0]), max_point=np.array([1.0, 1.0, 1.0]))
        result = aabb.contains(np.array([0.0, 0.0, 0.0]))
        assert result[0] is np.True_


class TestIsInsideRoom:
    """Room.is_inside_room のテスト（テストケース #1〜#5）。"""

    @pytest.fixture()
    def room(self) -> Room:
        return create_default_room()

    def test_01_room_center_is_inside(self, room: Room) -> None:
        """#1: 部屋中央は内部。"""
        result = room.is_inside_room(np.array([1.4, 1.75, 1.25]))
        assert result[0] is np.True_

    def test_02_outside_room(self, room: Room) -> None:
        """#2: 部屋外の点。"""
        result = room.is_inside_room(np.array([3.0, 0.0, 0.0]))
        assert result[0] is np.False_

    def test_03_origin_is_inside(self, room: Room) -> None:
        """#3: 境界上の点（原点）は内部。"""
        result = room.is_inside_room(np.array([0.0, 0.0, 0.0]))
        assert result[0] is np.True_

    def test_04_max_corner_is_inside(self, room: Room) -> None:
        """#4: 境界上の点（最大）は内部。"""
        result = room.is_inside_room(np.array([2.8, 3.5, 2.5]))
        assert result[0] is np.True_

    def test_05_negative_coord_is_outside(self, room: Room) -> None:
        """#5: 負の座標は外部。"""
        result = room.is_inside_room(np.array([-0.1, 1.0, 1.0]))
        assert result[0] is np.False_


class TestIsOnBed:
    """Room.is_on_bed のテスト（テストケース #6〜#9）。"""

    @pytest.fixture()
    def room(self) -> Room:
        return create_default_room()

    def test_06_bed_center_is_on_bed(self, room: Room) -> None:
        """#6: ベッド中央はon_bed。"""
        result = room.is_on_bed(np.array([1.4, 2.5, 0.1]))
        assert result[0] is np.True_

    def test_07_outside_bed(self, room: Room) -> None:
        """#7: ベッド外はnot on_bed。"""
        result = room.is_on_bed(np.array([0.5, 1.0, 0.1]))
        assert result[0] is np.False_

    def test_08_above_bed_is_not_on_bed(self, room: Room) -> None:
        """#8: ベッド上面超過はnot on_bed。"""
        result = room.is_on_bed(np.array([1.4, 2.5, 0.5]))
        assert result[0] is np.False_

    def test_09_bed_boundary_is_on_bed(self, room: Room) -> None:
        """#9: ベッド境界はon_bed。"""
        result = room.is_on_bed(np.array([0.9, 1.5, 0.0]))
        assert result[0] is np.True_


class TestIsValidCameraPosition:
    """Room.is_valid_camera_position のテスト（テストケース #10〜#13）。"""

    @pytest.fixture()
    def room(self) -> Room:
        return create_default_room()

    def test_10_inside_camera_zone(self, room: Room) -> None:
        """#10: 設置領域内。"""
        result = room.is_valid_camera_position(np.array([1.4, 1.75, 2.0]))
        assert result[0] is np.True_

    def test_11_outside_camera_zone_near_wall(self, room: Room) -> None:
        """#11: 設置領域外（壁際）。"""
        result = room.is_valid_camera_position(np.array([0.1, 1.75, 2.0]))
        assert result[0] is np.False_

    def test_12_camera_zone_min_boundary(self, room: Room) -> None:
        """#12: 設置領域境界（最小）。"""
        result = room.is_valid_camera_position(np.array([0.2, 0.2, 0.2]))
        assert result[0] is np.True_

    def test_13_camera_zone_max_boundary(self, room: Room) -> None:
        """#13: 設置領域境界（最大）。"""
        result = room.is_valid_camera_position(np.array([2.6, 3.3, 2.3]))
        assert result[0] is np.True_


class TestBatchProcessing:
    """バッチ処理のテスト（テストケース #14〜#16）。"""

    @pytest.fixture()
    def room(self) -> Room:
        return create_default_room()

    def test_14_batch_is_inside_room(self, room: Room) -> None:
        """#14: バッチ処理 is_inside_room。"""
        points = np.array([
            [1.4, 1.75, 1.25],  # 内部
            [3.0, 0.0, 0.0],    # 外部
            [0.0, 0.0, 0.0],    # 境界（内部）
            [-0.1, 1.0, 1.0],   # 外部
        ])
        result = room.is_inside_room(points)
        expected = np.array([True, False, True, False])
        np.testing.assert_array_equal(result, expected)

    def test_15_batch_is_on_bed(self, room: Room) -> None:
        """#15: バッチ処理 is_on_bed。"""
        points = np.array([
            [1.4, 2.5, 0.1],  # ベッド上
            [0.5, 1.0, 0.1],  # ベッド外
            [1.4, 2.5, 0.5],  # ベッド上面超過
            [0.9, 1.5, 0.0],  # ベッド境界
        ])
        result = room.is_on_bed(points)
        expected = np.array([True, False, False, True])
        np.testing.assert_array_equal(result, expected)

    def test_16_batch_is_valid_camera_position(self, room: Room) -> None:
        """#16: バッチ処理 is_valid_camera_position。"""
        points = np.array([
            [1.4, 1.75, 2.0],  # 設置領域内
            [0.1, 1.75, 2.0],  # 壁際（外）
            [0.2, 0.2, 0.2],   # 境界（最小）
            [2.6, 3.3, 2.3],   # 境界（最大）
        ])
        result = room.is_valid_camera_position(points)
        expected = np.array([True, False, True, True])
        np.testing.assert_array_equal(result, expected)


class TestCreateDefaultRoom:
    """create_default_room のテスト（テストケース #17〜#19）。"""

    def test_17_default_room_dimensions(self) -> None:
        """#17: デフォルトRoom寸法の確認。"""
        room = create_default_room()
        assert room.width == 2.8
        assert room.depth == 3.5
        assert room.height == 2.5

    def test_18_default_bed(self) -> None:
        """#18: デフォルトBedの確認。"""
        room = create_default_room()
        np.testing.assert_array_equal(room.bed.min_point, [0.9, 1.5, 0.0])
        np.testing.assert_array_equal(room.bed.max_point, [1.9, 3.5, 0.2])

    def test_19_default_camera_zone(self) -> None:
        """#19: デフォルトCameraZoneの確認。"""
        room = create_default_room()
        np.testing.assert_array_equal(room.camera_zone.min_point, [0.2, 0.2, 0.2])
        np.testing.assert_array_equal(room.camera_zone.max_point, [2.6, 3.3, 2.3])
