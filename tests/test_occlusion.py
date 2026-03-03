"""F05: ベッドオクルージョン判定テスト。"""

import numpy as np
import pytest

from camera_placement.core.occlusion import (
    _ray_aabb_intersect,
    check_bed_occlusion,
    check_bed_occlusion_multi_camera,
)
from camera_placement.models.camera import create_camera
from camera_placement.models.environment import AABB


def _bed_aabb() -> AABB:
    """テスト用ベッドAABB（CLAUDE.md仕様準拠）。"""
    return AABB(
        min_point=np.array([0.9, 1.5, 0.0]),
        max_point=np.array([1.9, 3.5, 0.2]),
    )


class TestCheckBedOcclusion:
    """check_bed_occlusion のテスト。"""

    def test_ray_through_bed(self) -> None:
        """#1: レイがベッドを貫通する → オクルージョンあり。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        target = np.array([1.4, 2.5, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.True_

    def test_ray_misses_bed(self) -> None:
        """#2: レイがベッドを通らない → オクルージョンなし。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        target = np.array([0.0, 0.0, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_target_on_bed_surface(self) -> None:
        """#3: 対象点がベッド上面 (Z=0.2) → オクルージョンなし。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        target = np.array([1.4, 2.5, 0.2])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_camera_above_target_on_bed(self) -> None:
        """#4: カメラ真上からベッド上面の点 → オクルージョンなし。"""
        cam_pos = np.array([1.4, 2.5, 2.0])
        target = np.array([1.4, 2.5, 0.2])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_camera_above_through_bed_to_floor(self) -> None:
        """#5: カメラ真上からベッド下（床面）→ オクルージョンあり。"""
        cam_pos = np.array([1.4, 2.5, 2.0])
        target = np.array([1.4, 2.5, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.True_

    def test_ray_passes_beside_bed(self) -> None:
        """#6: レイがベッドの横を通過 → オクルージョンなし。"""
        cam_pos = np.array([0.0, 2.5, 1.0])
        target = np.array([0.8, 2.5, 0.1])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_z_parallel_outside_bed_xy(self) -> None:
        """#7: Z軸方向のみ（ベッドXY外）→ オクルージョンなし。"""
        cam_pos = np.array([0.5, 0.5, 2.0])
        target = np.array([0.5, 0.5, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_z_parallel_inside_bed_xy(self) -> None:
        """#8: Z軸方向のみ（ベッドXY内で貫通）→ オクルージョンあり。"""
        cam_pos = np.array([1.4, 2.5, 2.0])
        target = np.array([1.4, 2.5, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.True_

    def test_batch_mixed(self) -> None:
        """#9: 複数点（遮蔽あり/なし混在）。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        points = np.array([
            [1.4, 2.5, 0.0],   # ベッド貫通 → True
            [0.0, 0.0, 0.0],   # ベッド外 → False
            [1.4, 2.5, 0.2],   # ベッド上面 → False
        ])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, points, bed)
        assert result.shape == (3,)
        assert result[0] is np.True_
        assert result[1] is np.False_
        assert result[2] is np.False_

    def test_single_point_shape(self) -> None:
        """#10: 単一点入力 shape (3,)。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        target = np.array([0.0, 0.0, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result.shape == (1,)

    def test_camera_equals_target(self) -> None:
        """#11: カメラ位置 = 対象点 → オクルージョンなし。"""
        cam_pos = np.array([1.4, 2.5, 2.0])
        target = np.array([1.4, 2.5, 2.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_

    def test_target_inside_bed(self) -> None:
        """#12: 対象点がベッドAABB内部 → オクルージョンあり。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        target = np.array([1.4, 2.5, 0.1])  # ベッド内部
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.True_

    def test_all_not_occluded(self) -> None:
        """#15: 全ての点が遮蔽なし。"""
        cam_pos = np.array([0.0, 0.0, 2.0])
        points = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
        ])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, points, bed)
        assert np.all(~result)

    def test_ray_grazes_aabb_edge(self) -> None:
        """#14: レイがAABBの辺をかすめる → オクルージョンなし。"""
        # ベッドの角のX=0.9, Y=1.5のラインをかすめるレイ
        cam_pos = np.array([0.0, 0.0, 2.0])
        # ベッド角の延長線より少し外側
        target = np.array([0.89, 1.49, 0.0])
        bed = _bed_aabb()
        result = check_bed_occlusion(cam_pos, target, bed)
        assert result[0] is np.False_


class TestCheckBedOcclusionMultiCamera:
    """check_bed_occlusion_multi_camera のテスト。"""

    def test_multi_camera(self) -> None:
        """#13: 複数カメラの一括判定。"""
        cam1 = create_camera(
            position=[0.0, 0.0, 2.0], look_at=[1.4, 2.5, 0.0]
        )
        cam2 = create_camera(
            position=[2.8, 0.0, 2.0], look_at=[1.4, 2.5, 0.0]
        )
        points = np.array([
            [1.4, 2.5, 0.0],   # ベッド中央下
            [0.0, 0.0, 0.0],   # ベッド外
        ])
        bed = _bed_aabb()
        result = check_bed_occlusion_multi_camera([cam1, cam2], points, bed)
        assert result.shape == (2, 2)
        # 両カメラからベッド中央下は遮蔽あり
        assert result[0, 0] is np.True_
        assert result[1, 0] is np.True_
        # ベッド外の点は遮蔽なし
        assert result[0, 1] is np.False_
        assert result[1, 1] is np.False_


class TestRayAabbIntersect:
    """_ray_aabb_intersect 内部関数のテスト。"""

    def test_known_intersection(self) -> None:
        """#16: 既知の入力でt_enter, t_exitが正しい値。"""
        # 原点からZ軸正方向へのレイ、Z=1〜3のAABB
        origins = np.array([[0.0, 0.0, 0.0]])
        directions = np.array([[0.0, 0.0, 1.0]])
        aabb_min = np.array([-1.0, -1.0, 1.0])
        aabb_max = np.array([1.0, 1.0, 3.0])
        t_enter, t_exit = _ray_aabb_intersect(
            origins, directions, aabb_min, aabb_max
        )
        np.testing.assert_allclose(t_enter[0], 1.0, atol=1e-10)
        np.testing.assert_allclose(t_exit[0], 3.0, atol=1e-10)
