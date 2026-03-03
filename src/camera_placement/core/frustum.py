"""F04: 視錐台（FOV）判定。

カメラのFOVに基づいて視錐台を構成し、3D点群が視野内にあるかを
バッチ判定する機能を提供する。
"""

from dataclasses import dataclass

import numpy as np

from camera_placement.models.camera import Camera


@dataclass
class FrustumChecker:
    """カメラの視錐台による視野内判定を行う。

    カメラのFOVに基づいて視錐台を構成し、3D点群が視野内にあるかを
    バッチ判定する。内部ではカメラ座標系でのFOV角度判定を行う。

    Attributes:
        camera: F02のCameraインスタンス。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
    """

    camera: Camera
    near: float = 0.1
    far: float = 10.0

    def __post_init__(self) -> None:
        """バリデーション。

        Raises:
            ValueError: near < 0、far <= near の場合。
        """
        if self.near < 0:
            raise ValueError(f"near must be >= 0, got {self.near}")
        if self.far <= self.near:
            raise ValueError(
                f"far must be > near, got near={self.near}, far={self.far}"
            )

    def is_visible(self, points: np.ndarray) -> np.ndarray:
        """点群が視錐台内にあるかを判定する。

        Args:
            points: shape (N, 3) または (3,)。ワールド座標。

        Returns:
            shape (N,) の bool 配列。True = 視野内。
        """
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim == 1:
            pts = pts.reshape(1, 3)

        cam_pts = self.camera.world_to_camera(pts)
        x_cam = cam_pts[:, 0]
        y_cam = cam_pts[:, 1]
        z_cam = cam_pts[:, 2]

        # 前方判定 + 距離クリップ
        depth_ok = (z_cam >= self.near) & (z_cam <= self.far)

        # 水平FOV判定
        half_hfov = self.camera.intrinsics.hfov / 2.0
        tan_half_h = np.tan(half_hfov)
        hfov_ok = np.abs(x_cam) <= z_cam * tan_half_h

        # 垂直FOV判定
        half_vfov = self.camera.intrinsics.vfov / 2.0
        tan_half_v = np.tan(half_vfov)
        vfov_ok = np.abs(y_cam) <= z_cam * tan_half_v

        return depth_ok & hfov_ok & vfov_ok

    def get_frustum_planes(self) -> np.ndarray:
        """視錐台を構成する6平面を返す。

        Returns:
            shape (6, 4)。各行は [nx, ny, nz, d]。
            法線はフラスタム内側を向く。
            順序: [near, far, left, right, top, bottom]。
            平面方程式: nx*x + ny*y + nz*z + d >= 0 で内側。
        """
        half_hfov = self.camera.intrinsics.hfov / 2.0
        half_vfov = self.camera.intrinsics.vfov / 2.0
        sin_h = np.sin(half_hfov)
        cos_h = np.cos(half_hfov)
        sin_v = np.sin(half_vfov)
        cos_v = np.cos(half_vfov)

        # カメラローカル座標系での法線ベクトル（内向き）
        # カメラ座標系: X=右, Y=上, Z=前方
        local_normals = np.array([
            [0.0, 0.0, 1.0],         # near: 前方
            [0.0, 0.0, -1.0],        # far: 後方
            [sin_h, 0.0, cos_h],     # left: 右に傾いた法線
            [-sin_h, 0.0, cos_h],    # right: 左に傾いた法線
            [0.0, -sin_v, cos_v],    # top: 下に傾いた法線
            [0.0, sin_v, cos_v],     # bottom: 上に傾いた法線
        ])

        # ワールド座標系に変換
        # R = rotation_matrix: ワールド→カメラ（行方向に right, up, forward）
        # ワールド法線 = R^T @ ローカル法線
        R = self.camera.rotation_matrix
        world_normals = (R.T @ local_normals.T).T  # (6, 3)

        # 各平面上の1点
        pos = self.camera.position
        fwd = self.camera.forward
        near_point = pos + self.near * fwd
        far_point = pos + self.far * fwd

        # d = -dot(normal, point_on_plane)
        planes = np.zeros((6, 4))
        planes[:, :3] = world_normals

        # near平面: 点は near_point
        planes[0, 3] = -np.dot(world_normals[0], near_point)
        # far平面: 点は far_point
        planes[1, 3] = -np.dot(world_normals[1], far_point)
        # left, right, top, bottom: 点は camera.position
        for i in range(2, 6):
            planes[i, 3] = -np.dot(world_normals[i], pos)

        return planes

    def get_frustum_corners(self) -> np.ndarray:
        """視錐台の8頂点のワールド座標を返す。

        Returns:
            shape (8, 3)。
            順序: [near_tl, near_tr, near_bl, near_br,
                    far_tl,  far_tr,  far_bl,  far_br]
            tl=top-left, tr=top-right, bl=bottom-left, br=bottom-right
            （カメラから見た方向で定義）
        """
        half_hfov = self.camera.intrinsics.hfov / 2.0
        half_vfov = self.camera.intrinsics.vfov / 2.0
        tan_h = np.tan(half_hfov)
        tan_v = np.tan(half_vfov)

        near_half_w = self.near * tan_h
        near_half_h = self.near * tan_v
        far_half_w = self.far * tan_h
        far_half_h = self.far * tan_v

        pos = self.camera.position
        fwd = self.camera.forward
        r = self.camera.right
        u = self.camera.up

        near_center = pos + self.near * fwd
        far_center = pos + self.far * fwd

        corners = np.array([
            # near面
            near_center + (-near_half_w) * r + (+near_half_h) * u,  # near_tl
            near_center + (+near_half_w) * r + (+near_half_h) * u,  # near_tr
            near_center + (-near_half_w) * r + (-near_half_h) * u,  # near_bl
            near_center + (+near_half_w) * r + (-near_half_h) * u,  # near_br
            # far面
            far_center + (-far_half_w) * r + (+far_half_h) * u,     # far_tl
            far_center + (+far_half_w) * r + (+far_half_h) * u,     # far_tr
            far_center + (-far_half_w) * r + (-far_half_h) * u,     # far_bl
            far_center + (+far_half_w) * r + (-far_half_h) * u,     # far_br
        ])

        return corners
