"""F04: FrustumChecker テスト。"""

import numpy as np
import pytest

from camera_placement.core.frustum import FrustumChecker
from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera


def _make_camera(
    position=(0, 0, 2.3),
    look_at=(1.4, 1.75, 0.5),
) -> Camera:
    """テスト用カメラを生成する。"""
    return create_camera(position=position, look_at=look_at)


# --- 生成テスト ---


class TestFrustumCheckerCreation:
    """FrustumChecker 生成テスト。"""

    def test_normal_creation(self) -> None:
        """#1: 正常な FrustumChecker 生成。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        assert fc.near == 0.1
        assert fc.far == 10.0

    def test_negative_near_raises(self) -> None:
        """#2: near < 0 で ValueError。"""
        cam = _make_camera()
        with pytest.raises(ValueError, match="near must be >= 0"):
            FrustumChecker(camera=cam, near=-0.1)

    def test_far_lte_near_raises(self) -> None:
        """#3: far <= near で ValueError。"""
        cam = _make_camera()
        with pytest.raises(ValueError, match="far must be > near"):
            FrustumChecker(camera=cam, near=5.0, far=3.0)

    def test_near_zero_allowed(self) -> None:
        """#4: near=0 は許容。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.0, far=10.0)
        assert fc.near == 0.0


# --- is_visible テスト ---


class TestIsVisible:
    """is_visible メソッドのテスト。"""

    def test_look_at_point_visible(self) -> None:
        """#5: look_at 点は視野内。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        result = fc.is_visible(cam.look_at)
        assert result[0] is np.True_

    def test_forward_point_visible(self) -> None:
        """#6: カメラ真正面の点は視野内。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        point = cam.position + 2.0 * cam.forward
        result = fc.is_visible(point)
        assert result[0] is np.True_

    def test_behind_camera_not_visible(self) -> None:
        """#7: カメラ後方の点は視野外。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        point = cam.position - 2.0 * cam.forward
        result = fc.is_visible(point)
        assert result[0] is np.False_

    def test_too_close_not_visible(self) -> None:
        """#8: near 未満の近距離は視野外。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=1.0, far=10.0)
        point = cam.position + 0.5 * cam.forward
        result = fc.is_visible(point)
        assert result[0] is np.False_

    def test_too_far_not_visible(self) -> None:
        """#9: far 超の遠距離は視野外。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.1, far=3.0)
        point = cam.position + 5.0 * cam.forward
        result = fc.is_visible(point)
        assert result[0] is np.False_

    def test_hfov_boundary_inside(self) -> None:
        """#10: 水平FOV境界内ギリギリ。"""
        cam = create_camera(position=(0, 0, 0), look_at=(0, 1, 0))
        fc = FrustumChecker(camera=cam)
        half_hfov = cam.intrinsics.hfov / 2.0
        epsilon = 0.001
        angle = half_hfov - epsilon
        dist = 5.0
        point = cam.position + dist * cam.forward + dist * np.tan(angle) * cam.right
        result = fc.is_visible(point)
        assert result[0] is np.True_

    def test_hfov_boundary_outside(self) -> None:
        """#11: 水平FOV境界外ギリギリ。"""
        cam = create_camera(position=(0, 0, 0), look_at=(0, 1, 0))
        fc = FrustumChecker(camera=cam)
        half_hfov = cam.intrinsics.hfov / 2.0
        epsilon = 0.001
        angle = half_hfov + epsilon
        dist = 5.0
        point = cam.position + dist * cam.forward + dist * np.tan(angle) * cam.right
        result = fc.is_visible(point)
        assert result[0] is np.False_

    def test_vfov_boundary_inside(self) -> None:
        """#12: 垂直FOV境界内ギリギリ。"""
        cam = create_camera(position=(0, 0, 0), look_at=(0, 1, 0))
        fc = FrustumChecker(camera=cam)
        half_vfov = cam.intrinsics.vfov / 2.0
        epsilon = 0.001
        angle = half_vfov - epsilon
        dist = 5.0
        point = cam.position + dist * cam.forward + dist * np.tan(angle) * cam.up
        result = fc.is_visible(point)
        assert result[0] is np.True_

    def test_vfov_boundary_outside(self) -> None:
        """#13: 垂直FOV境界外ギリギリ。"""
        cam = create_camera(position=(0, 0, 0), look_at=(0, 1, 0))
        fc = FrustumChecker(camera=cam)
        half_vfov = cam.intrinsics.vfov / 2.0
        epsilon = 0.001
        angle = half_vfov + epsilon
        dist = 5.0
        point = cam.position + dist * cam.forward + dist * np.tan(angle) * cam.up
        result = fc.is_visible(point)
        assert result[0] is np.False_

    def test_fov_boundary_exact(self) -> None:
        """#14: FOV境界ちょうどは視野内。"""
        cam = create_camera(position=(0, 0, 0), look_at=(0, 1, 0))
        fc = FrustumChecker(camera=cam)
        half_hfov = cam.intrinsics.hfov / 2.0
        dist = 5.0
        point = cam.position + dist * cam.forward + dist * np.tan(half_hfov) * cam.right
        result = fc.is_visible(point)
        assert result[0] is np.True_

    def test_batch_mixed_visibility(self) -> None:
        """#15: バッチ処理: 視野内外の混在。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        points = np.array([
            cam.position + 2.0 * cam.forward,               # 前方 → True
            cam.look_at,                                      # look_at → True
            cam.position + 5.0 * cam.forward,                # 前方遠方 → True
            cam.position - 2.0 * cam.forward,                # 後方 → False
            cam.position + 2.0 * cam.forward + 100 * cam.right,  # 横に大きくずれ → False
        ])
        result = fc.is_visible(points)
        assert result.shape == (5,)
        assert result[0] is np.True_
        assert result[1] is np.True_
        assert result[2] is np.True_
        assert result[3] is np.False_
        assert result[4] is np.False_

    def test_single_point_shape(self) -> None:
        """#16: 単一点 shape (3,)。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        point = cam.look_at  # shape (3,)
        result = fc.is_visible(point)
        assert result.shape == (1,)

    def test_large_batch_performance(self) -> None:
        """#17: 大量点群（性能確認）。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        rng = np.random.default_rng(42)
        points = rng.uniform(-5, 10, size=(100_000, 3))
        result = fc.is_visible(points)
        assert result.shape == (100_000,)
        assert result.dtype == bool

    def test_tilted_camera(self) -> None:
        """#18: 斜め向きカメラ。"""
        cam = _make_camera(position=(0, 0, 2.3), look_at=(1.4, 1.75, 0.5))
        fc = FrustumChecker(camera=cam)
        # forward方向近傍の点
        point = cam.position + 1.0 * cam.forward
        result = fc.is_visible(point)
        assert result[0] is np.True_


# --- get_frustum_corners テスト ---


class TestGetFrustumCorners:
    """get_frustum_corners メソッドのテスト。"""

    def test_corners_shape(self) -> None:
        """#19: 頂点数と形状。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        corners = fc.get_frustum_corners()
        assert corners.shape == (8, 3)

    def test_near_corners_at_near_distance(self) -> None:
        """#20: near面の4頂点がnear距離にある。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.5, far=5.0)
        corners = fc.get_frustum_corners()
        near_corners = corners[:4]  # near_tl, near_tr, near_bl, near_br
        for corner in near_corners:
            diff = corner - cam.position
            depth = np.dot(diff, cam.forward)
            np.testing.assert_allclose(depth, 0.5, atol=1e-10)

    def test_far_corners_at_far_distance(self) -> None:
        """#21: far面の4頂点がfar距離にある。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.5, far=5.0)
        corners = fc.get_frustum_corners()
        far_corners = corners[4:]  # far_tl, far_tr, far_bl, far_br
        for corner in far_corners:
            diff = corner - cam.position
            depth = np.dot(diff, cam.forward)
            np.testing.assert_allclose(depth, 5.0, atol=1e-10)

    def test_all_corners_visible(self) -> None:
        """#22: 全8頂点が is_visible で True（境界精度を考慮し僅かに内側で検証）。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.5, far=5.0)
        corners = fc.get_frustum_corners()
        # 各角を視錐台中心に向かって1%内側に寄せる（浮動小数点精度対策）
        frustum_center = cam.position + (fc.near + fc.far) / 2.0 * cam.forward
        shrunk = corners + (frustum_center - corners) * 0.01
        result = fc.is_visible(shrunk)
        assert np.all(result)

    def test_near_face_width(self) -> None:
        """#23: near面の幅が 2*near*tan(hfov/2)。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam, near=0.5, far=5.0)
        corners = fc.get_frustum_corners()
        near_tl = corners[0]
        near_tr = corners[1]
        expected_width = 2 * 0.5 * np.tan(cam.intrinsics.hfov / 2.0)
        actual_width = np.linalg.norm(near_tr - near_tl)
        np.testing.assert_allclose(actual_width, expected_width, atol=1e-10)


# --- get_frustum_planes テスト ---


class TestGetFrustumPlanes:
    """get_frustum_planes メソッドのテスト。"""

    def test_planes_shape(self) -> None:
        """#24: 平面数と形状。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        planes = fc.get_frustum_planes()
        assert planes.shape == (6, 4)

    def test_inside_point_all_planes(self) -> None:
        """#25: フラスタム内の点が全平面の内側。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        planes = fc.get_frustum_planes()
        point = cam.look_at  # look_at点はフラスタム内
        for i in range(6):
            n = planes[i, :3]
            d = planes[i, 3]
            val = np.dot(n, point) + d
            assert val >= -1e-10, f"Plane {i}: {val}"

    def test_outside_point_at_least_one_plane(self) -> None:
        """#26: フラスタム外の点が少なくとも1平面で外側。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        planes = fc.get_frustum_planes()
        point = cam.position - 2.0 * cam.forward  # カメラ後方
        outside_count = 0
        for i in range(6):
            n = planes[i, :3]
            d = planes[i, 3]
            val = np.dot(n, point) + d
            if val < -1e-10:
                outside_count += 1
        assert outside_count >= 1


# --- is_visible 整合性テスト ---


class TestIsVisibleConsistency:
    """is_visible の整合性テスト。"""

    def test_z_axis_camera(self) -> None:
        """#27: Z軸正方向を向くカメラ。"""
        cam = create_camera(
            position=[1.4, 1.75, 0.0],
            look_at=[1.4, 1.75, 2.0],
            up_hint=[0, 1, 0],
        )
        fc = FrustumChecker(camera=cam)
        # Z方向前方の点 → 視野内
        result = fc.is_visible(np.array([1.4, 1.75, 1.0]))
        assert result[0] is np.True_
        # Z方向後方の点 → 視野外
        result = fc.is_visible(np.array([1.4, 1.75, -1.0]))
        assert result[0] is np.False_

    def test_project_to_image_consistency(self) -> None:
        """#28: project_to_image との整合。"""
        cam = _make_camera()
        fc = FrustumChecker(camera=cam)
        # 視野内の点
        point = cam.position + 3.0 * cam.forward
        in_fov = fc.is_visible(point)
        assert in_fov[0] is np.True_
        # project_to_image の結果が画像範囲内
        uv = cam.project_to_image(point)
        intr = cam.intrinsics
        assert 0 <= uv[0, 0] <= intr.resolution_w
        assert 0 <= uv[0, 1] <= intr.resolution_h
