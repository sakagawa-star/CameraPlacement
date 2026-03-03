"""F02: カメラモデルのテスト。"""

import numpy as np
import pytest

from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera


class TestCameraIntrinsics:
    """CameraIntrinsicsのテスト。"""

    def test_default_values(self) -> None:
        """テスト1: デフォルト値の確認。"""
        intr = CameraIntrinsics()
        assert intr.focal_length == 3.5
        assert intr.sensor_width == 5.76
        assert intr.sensor_height == 3.6
        assert intr.resolution_w == 1920
        assert intr.resolution_h == 1200

    def test_hfov(self) -> None:
        """テスト2: 水平FOVの計算。"""
        intr = CameraIntrinsics()
        expected = 2.0 * np.arctan(5.76 / (2.0 * 3.5))
        assert np.isclose(intr.hfov, expected)
        assert np.isclose(np.degrees(intr.hfov), 79.0, atol=1.0)

    def test_vfov(self) -> None:
        """テスト3: 垂直FOVの計算。"""
        intr = CameraIntrinsics()
        expected = 2.0 * np.arctan(3.6 / (2.0 * 3.5))
        assert np.isclose(intr.vfov, expected)
        assert np.isclose(np.degrees(intr.vfov), 54.0, atol=1.0)

    def test_pixel_size(self) -> None:
        """テスト4: ピクセルサイズの計算。"""
        intr = CameraIntrinsics()
        assert np.isclose(intr.pixel_size, 5.76 / 1920)
        assert np.isclose(intr.pixel_size, 0.003)

    def test_fx_fy(self) -> None:
        """テスト5: fx, fyの計算。"""
        intr = CameraIntrinsics()
        assert np.isclose(intr.fx, 3.5 / 0.003, atol=0.01)
        assert np.isclose(intr.fy, 3.5 * 1200 / 3.6, atol=0.01)
        assert np.isclose(intr.fx, intr.fy, atol=0.01)

    def test_cx_cy(self) -> None:
        """テスト6: cx, cyの計算。"""
        intr = CameraIntrinsics()
        assert intr.cx == 960.0
        assert intr.cy == 600.0

    def test_intrinsic_matrix(self) -> None:
        """テスト7: 内部行列Kの形状と値。"""
        intr = CameraIntrinsics()
        K = intr.intrinsic_matrix
        assert K.shape == (3, 3)
        assert np.isclose(K[0, 0], intr.fx)
        assert np.isclose(K[1, 1], intr.fy)
        assert np.isclose(K[0, 2], intr.cx)
        assert np.isclose(K[1, 2], intr.cy)
        assert np.isclose(K[2, 2], 1.0)
        assert np.isclose(K[0, 1], 0.0)
        assert np.isclose(K[1, 0], 0.0)


class TestCameraCreation:
    """Camera生成のテスト。"""

    def test_normal_creation(self) -> None:
        """テスト8: 正常なカメラ生成。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 2.0]),
            look_at=np.array([1.4, 1.75, 1.0]),
        )
        assert cam.position.shape == (3,)
        assert cam.look_at.shape == (3,)

    def test_same_position_look_at_raises(self) -> None:
        """テスト9: position==look_atでValueError。"""
        with pytest.raises(ValueError, match="same point"):
            Camera(
                position=np.array([1.0, 1.0, 1.0]),
                look_at=np.array([1.0, 1.0, 1.0]),
            )

    def test_parallel_forward_up_hint_raises(self) -> None:
        """テスト10: forward//up_hintでValueError。"""
        with pytest.raises(ValueError, match="parallel"):
            Camera(
                position=np.array([0.0, 0.0, 0.0]),
                look_at=np.array([0.0, 0.0, 1.0]),
                up_hint=np.array([0.0, 0.0, 1.0]),
            )

    def test_list_input_converts_to_float64(self) -> None:
        """テスト11: list入力でnp.float64に変換。"""
        cam = Camera(
            position=[1.0, 2.0, 3.0],
            look_at=[4.0, 5.0, 6.0],
        )
        assert cam.position.dtype == np.float64
        assert cam.look_at.dtype == np.float64
        assert cam.up_hint.dtype == np.float64

    def test_invalid_shape_raises(self) -> None:
        """テスト12: shape不正でValueError。"""
        with pytest.raises(ValueError, match="shape"):
            Camera(
                position=np.array([1.0, 2.0]),
                look_at=np.array([3.0, 4.0, 5.0]),
            )


class TestLocalCoordinateSystem:
    """ローカル座標系のテスト。"""

    def test_forward_z_axis(self) -> None:
        """テスト13: forward: Z軸正方向を見る。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        np.testing.assert_allclose(cam.forward, [0.0, 0.0, 1.0], atol=1e-10)

    def test_forward_x_axis(self) -> None:
        """テスト14: forward: X軸正方向を見る。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([1.0, 0.0, 0.0]),
        )
        np.testing.assert_allclose(cam.forward, [1.0, 0.0, 0.0], atol=1e-10)

    def test_forward_y_axis(self) -> None:
        """テスト15: forward: Y軸正方向を見る。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 1.0, 0.0]),
        )
        np.testing.assert_allclose(cam.forward, [0.0, 1.0, 0.0], atol=1e-10)

    def test_orthonormal_system(self) -> None:
        """テスト16: forward, right, upが正規直交系。"""
        cam = Camera(
            position=np.array([0.2, 0.2, 2.3]),
            look_at=np.array([1.4, 1.75, 1.0]),
        )
        assert np.isclose(np.linalg.norm(cam.forward), 1.0)
        assert np.isclose(np.linalg.norm(cam.right), 1.0)
        assert np.isclose(np.linalg.norm(cam.up), 1.0)
        assert np.isclose(np.dot(cam.forward, cam.right), 0.0, atol=1e-10)
        assert np.isclose(np.dot(cam.forward, cam.up), 0.0, atol=1e-10)
        assert np.isclose(np.dot(cam.right, cam.up), 0.0, atol=1e-10)

    def test_rotation_matrix_orthonormal(self) -> None:
        """テスト17: rotation_matrixが正規直交行列。"""
        cam = Camera(
            position=np.array([0.2, 0.2, 2.3]),
            look_at=np.array([1.4, 1.75, 1.0]),
        )
        R = cam.rotation_matrix
        assert R.shape == (3, 3)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-10)
        assert np.isclose(np.linalg.det(R), 1.0, atol=1e-10)


class TestWorldToCamera:
    """world_to_cameraのテスト。"""

    def test_camera_position_is_origin(self) -> None:
        """テスト18: カメラ位置自身は原点。"""
        cam = Camera(
            position=np.array([1.0, 2.0, 3.0]),
            look_at=np.array([1.0, 2.0, 4.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        result = cam.world_to_camera(np.array([1.0, 2.0, 3.0]))
        np.testing.assert_allclose(result, [[0.0, 0.0, 0.0]], atol=1e-10)

    def test_look_at_on_z_axis(self) -> None:
        """テスト19: look_atはZ軸正方向。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 5.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        result = cam.world_to_camera(np.array([0.0, 0.0, 5.0]))
        np.testing.assert_allclose(result, [[0.0, 0.0, 5.0]], atol=1e-10)

    def test_right_direction(self) -> None:
        """テスト20: 右方向の点はカメラX正。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        # right = cross(up_hint, forward) = cross([0,1,0],[0,0,1]) = [1,0,0]
        # ワールドX正方向の点はカメラX正（右方向）
        result = cam.world_to_camera(np.array([1.0, 0.0, 1.0]))
        assert result[0, 0] > 0  # X_cam > 0

    def test_up_direction(self) -> None:
        """テスト21: 上方向の点はカメラY正。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        # up = cross(forward, right) = cross([0,0,1],[1,0,0]) = [0,1,0]
        result = cam.world_to_camera(np.array([0.0, 1.0, 1.0]))
        assert result[0, 1] > 0  # Y_cam > 0

    def test_batch_processing(self) -> None:
        """テスト22: バッチ処理 (N,3)。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        points = np.array([
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 2.0],
            [0.0, 1.0, 3.0],
        ])
        result = cam.world_to_camera(points)
        assert result.shape == (3, 3)
        for i in range(3):
            single = cam.world_to_camera(points[i])
            np.testing.assert_allclose(result[i], single[0], atol=1e-10)

    def test_single_point_shape(self) -> None:
        """テスト23: 単一点 shape (3,)。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        result = cam.world_to_camera(np.array([1.0, 2.0, 3.0]))
        assert result.shape == (1, 3)


class TestProjectToImage:
    """project_to_imageのテスト。"""

    def test_look_at_projects_to_center(self) -> None:
        """テスト24: look_at点は画像中心に投影。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 5.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        result = cam.project_to_image(np.array([0.0, 0.0, 5.0]))
        np.testing.assert_allclose(result[0], [960.0, 600.0], atol=0.01)

    def test_behind_camera_returns_nan(self) -> None:
        """テスト25: カメラ後方の点はNaN。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        result = cam.project_to_image(np.array([0.0, 0.0, -1.0]))
        assert np.all(np.isnan(result[0]))

    def test_image_right_upper(self) -> None:
        """テスト26: 画像右上方向の投影。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        # right = [1,0,0], up = [0,1,0], forward = [0,0,1]
        # 右上の点: camera X>0 かつ camera Y>0
        # camera X>0 → world X>0 (rightが[1,0,0]なので)
        # camera Y>0 → world Y>0 (upが[0,1,0]なので)
        # u > cx (右), v < cy (上: Y反転なので)
        result = cam.project_to_image(np.array([1.0, 1.0, 5.0]))
        assert result[0, 0] > 960.0  # u > cx
        assert result[0, 1] < 600.0  # v < cy

    def test_batch_with_mixed_front_behind(self) -> None:
        """テスト27: バッチ処理（前方+後方の混在）。"""
        cam = Camera(
            position=np.array([0.0, 0.0, 0.0]),
            look_at=np.array([0.0, 0.0, 1.0]),
            up_hint=np.array([0.0, 1.0, 0.0]),
        )
        points = np.array([
            [0.0, 0.0, 5.0],   # 前方
            [0.0, 0.0, -5.0],  # 後方
        ])
        result = cam.project_to_image(points)
        assert result.shape == (2, 2)
        assert not np.any(np.isnan(result[0]))  # 前方は有効
        assert np.all(np.isnan(result[1]))       # 後方はNaN


class TestCreateCamera:
    """create_cameraファクトリのテスト。"""

    def test_default_intrinsics(self) -> None:
        """テスト28: デフォルト内部パラメータ。"""
        cam = create_camera([0.0, 0.0, 2.0], [1.0, 1.0, 1.0])
        default = CameraIntrinsics()
        assert cam.intrinsics.focal_length == default.focal_length
        assert cam.intrinsics.resolution_w == default.resolution_w

    def test_custom_intrinsics(self) -> None:
        """テスト29: カスタム内部パラメータ。"""
        custom = CameraIntrinsics(focal_length=5.0)
        cam = create_camera([0.0, 0.0, 2.0], [1.0, 1.0, 1.0], intrinsics=custom)
        assert cam.intrinsics.focal_length == 5.0

    def test_custom_up_hint(self) -> None:
        """テスト30: カスタムup_hint。"""
        cam = create_camera(
            [0.0, 0.0, 2.0], [1.0, 1.0, 1.0], up_hint=[0.0, 1.0, 0.0]
        )
        np.testing.assert_allclose(cam.up_hint, [0.0, 1.0, 0.0])

    def test_list_input(self) -> None:
        """テスト31: list入力で動作。"""
        cam = create_camera([0.0, 0.0, 2.0], [1.0, 1.0, 1.0])
        assert isinstance(cam, Camera)
        assert cam.position.dtype == np.float64
