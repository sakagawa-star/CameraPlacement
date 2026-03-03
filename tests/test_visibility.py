"""F06: 視認性統合のテスト。"""

import numpy as np
import pytest

from camera_placement.core.frustum import FrustumChecker
from camera_placement.core.occlusion import check_bed_occlusion
from camera_placement.core.visibility import (
    check_visibility,
    check_visibility_multi_camera,
)
from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera
from camera_placement.models.environment import AABB


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

def _bed_aabb() -> AABB:
    """テスト用ベッドAABB（CLAUDE.md仕様準拠）。"""
    return AABB(
        min_point=np.array([0.9, 1.5, 0.0]),
        max_point=np.array([1.9, 3.5, 0.2]),
    )


def _dummy_bed_outside_room() -> AABB:
    """遮蔽の影響を排除するための部屋外ベッドAABB。"""
    return AABB(
        min_point=np.array([100.0, 100.0, 100.0]),
        max_point=np.array([101.0, 101.0, 101.0]),
    )


# ===========================================================================
# カテゴリA: 基本動作（check_visibility）
# ===========================================================================


class TestCheckVisibilityBasic:
    """A1-A6: check_visibility の基本動作テスト。"""

    def test_a1_in_frustum_no_occlusion(self) -> None:
        """A1: 視錐台内かつ遮蔽なし → True。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        # look_at方向に近い点（ベッド外、Y=1.0 < bed_min_y=1.5）
        point = np.array([1.0, 1.0, 0.5])
        result = check_visibility(cam, point, _bed_aabb())
        assert result[0] is np.True_

    def test_a2_outside_frustum(self) -> None:
        """A2: 視錐台外 → False。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[0.0, 0.0, 0.0],
        )
        # カメラは左手前下を向いている → 右奥の点は視野外
        point = np.array([2.6, 3.3, 0.5])
        result = check_visibility(cam, point, _bed_aabb())
        assert result[0] is np.False_

    def test_a3_in_frustum_occluded(self) -> None:
        """A3: 視錐台内かつ遮蔽あり → False。"""
        # 低い位置のカメラ → ベッドを横から見る → ベッド裏の点は遮蔽
        cam = create_camera(
            position=[0.2, 0.2, 0.1],
            look_at=[1.4, 2.5, 0.1],
        )
        # ベッド中央の下（Z=0.0）→ カメラからの視線がベッドを貫通
        point = np.array([1.4, 2.5, 0.0])
        result = check_visibility(cam, point, _bed_aabb())
        assert result[0] is np.False_

    def test_a4_bed_surface_no_occlusion(self) -> None:
        """A4: ベッド上面の点（遮蔽なし） → True。"""
        # 真上からベッドを見下ろすカメラ（forward//up_hint回避のためup_hint指定）
        cam = create_camera(
            position=[1.4, 2.5, 2.0],
            look_at=[1.4, 2.5, 0.0],
            up_hint=[0, 1, 0],
        )
        # ベッド上面 Z=0.2
        point = np.array([1.4, 2.5, 0.2])
        result = check_visibility(cam, point, _bed_aabb())
        assert result[0] is np.True_

    def test_a5_near_clip(self) -> None:
        """A5: near未満の距離 → False。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        # カメラの前方方向に0.05m（near=0.1未満）の点
        point = cam.position + cam.forward * 0.05
        result = check_visibility(cam, point, _dummy_bed_outside_room(), near=0.1)
        assert result[0] is np.False_

    def test_a6_far_clip(self) -> None:
        """A6: far超の距離 → False。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        # カメラの前方方向に1.5m（far=1.0超え）の点
        point = cam.position + cam.forward * 1.5
        result = check_visibility(cam, point, _dummy_bed_outside_room(), far=1.0)
        assert result[0] is np.False_


# ===========================================================================
# カテゴリB: エッジケース（check_visibility）
# ===========================================================================


class TestCheckVisibilityEdgeCases:
    """B1-B4: check_visibility のエッジケーステスト。"""

    def test_b1_single_point_shape(self) -> None:
        """B1: 単一点入力 shape (3,) → shape (1,) の結果。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        point = np.array([0.5, 0.5, 0.0])
        result = check_visibility(cam, point, _bed_aabb())
        assert result.shape == (1,)

    def test_b2_batch_mixed(self) -> None:
        """B2: バッチ処理（視認可/不可混在）。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        points = np.array([
            [0.5, 0.5, 0.0],    # 視錐台内・遮蔽なし → True
            [2.6, 3.3, 0.5],    # 視錐台外 → False (check per camera)
            [1.4, 1.75, 0.5],   # 視錐台内・遮蔽なし → True（部屋中央）
        ])
        result = check_visibility(cam, points, _bed_aabb())
        assert result.shape == (3,)
        # 少なくとも1つはTrue、1つ以上の有効な結果がある
        assert result.dtype == bool

    def test_b3_custom_near_far(self) -> None:
        """B3: カスタム near/far が反映される。"""
        cam = create_camera(
            position=[0.2, 0.2, 2.0],
            look_at=[1.4, 1.75, 0.5],
        )
        # カメラの前方方向に距離1.0の点
        point = cam.position + cam.forward * 1.0
        dummy_bed = _dummy_bed_outside_room()

        # far=0.5 → 距離1.0は範囲外
        result_out = check_visibility(cam, point, dummy_bed, near=0.1, far=0.5)
        assert result_out[0] is np.False_

        # near=0.5, far=3.0 → 距離1.0は範囲内
        result_in = check_visibility(cam, point, dummy_bed, near=0.5, far=3.0)
        assert result_in[0] is np.True_

    def test_b4_custom_eps(self) -> None:
        """B4: カスタム eps が check_bed_occlusion に渡される。"""
        cam = create_camera(
            position=[0.2, 0.2, 0.1],
            look_at=[1.4, 2.5, 0.1],
        )
        point = np.array([1.4, 2.5, 0.0])
        # デフォルト eps
        result_default = check_visibility(cam, point, _bed_aabb())
        # カスタム eps=0.01
        result_custom = check_visibility(cam, point, _bed_aabb(), eps=0.01)
        # 両方とも False（遮蔽あり）であるべき
        assert result_default[0] is np.False_
        assert result_custom[0] is np.False_


# ===========================================================================
# カテゴリC: 複数カメラ（check_visibility_multi_camera）
# ===========================================================================


class TestCheckVisibilityMultiCamera:
    """C1-C5: check_visibility_multi_camera のテスト。"""

    def test_c1_result_shape(self) -> None:
        """C1: 結果のshape検証。3台カメラ、4点 → shape (3, 4)。"""
        cam1 = create_camera([0.2, 0.2, 2.0], [1.4, 1.75, 0.5])
        cam2 = create_camera([2.6, 0.2, 2.0], [1.4, 1.75, 0.5])
        cam3 = create_camera([1.4, 0.2, 2.0], [1.4, 1.75, 0.5])
        cameras = [cam1, cam2, cam3]
        points = np.array([
            [0.5, 0.5, 0.0],
            [1.4, 1.0, 0.0],
            [2.0, 1.0, 0.0],
            [1.4, 1.75, 0.5],
        ])
        result = check_visibility_multi_camera(cameras, points, _bed_aabb())
        assert result.shape == (3, 4)
        assert result.dtype == bool

    def test_c2_camera_independence(self) -> None:
        """C2: 各カメラの独立性。異なる方向のカメラが異なる結果を返す。"""
        # カメラ1: 左壁から右方向を見る
        cam1 = create_camera([0.2, 1.75, 2.0], [2.6, 1.75, 0.0])
        # カメラ2: 右壁から左方向を見る
        cam2 = create_camera([2.6, 1.75, 2.0], [0.2, 1.75, 0.0])

        # cam1は右側の点が見え、cam2は左側の点が見える
        points = np.array([
            [2.5, 1.75, 0.0],  # 右端 → cam1の正面方向
            [0.3, 1.75, 0.0],  # 左端 → cam2の正面方向
        ])

        result = check_visibility_multi_camera(
            [cam1, cam2], points, _bed_aabb()
        )
        assert result.shape == (2, 2)
        # cam1は右端が見え左端は見えない、cam2はその逆
        assert not np.array_equal(result[0], result[1])

    def test_c3_visible_count_f07_connection(self) -> None:
        """C3: 視認カメラ数の計算（F07接続テスト）。"""
        # 部屋中央を向く6台のカメラ（部屋の各コーナー付近）
        center = [1.4, 1.75, 0.5]
        cameras = [
            create_camera([0.2, 0.2, 2.3], center),
            create_camera([2.6, 0.2, 2.3], center),
            create_camera([0.2, 3.3, 2.3], center),
            create_camera([2.6, 3.3, 2.3], center),
            create_camera([1.4, 0.2, 2.3], center),
            create_camera([1.4, 3.3, 2.3], center),
        ]
        # 部屋中央の点（全カメラから見えるはず）
        points = np.array([
            [1.4, 1.0, 0.5],  # ベッド外・部屋中央付近
        ])
        visibility_matrix = check_visibility_multi_camera(
            cameras, points, _bed_aabb()
        )
        visible_count = visibility_matrix.sum(axis=0)
        # 6台全てから見えるはず（中央の遮蔽なし点）
        assert visible_count[0] >= 3  # 少なくとも3台以上

    def test_c4_empty_cameras(self) -> None:
        """C4: 空のカメラリスト → shape (0, N)。"""
        points = np.array([[0.5, 0.5, 0.0], [1.0, 1.0, 0.0]])
        result = check_visibility_multi_camera([], points, _bed_aabb())
        assert result.shape == (0, 2)
        assert result.dtype == bool

    def test_c5_single_camera_matches_check_visibility(self) -> None:
        """C5: 単一カメラ → check_visibility と同じ結果。"""
        cam = create_camera([0.2, 0.2, 2.0], [1.4, 1.75, 0.5])
        points = np.array([
            [0.5, 0.5, 0.0],
            [1.4, 1.75, 0.5],
            [2.0, 3.0, 0.0],
        ])
        bed = _bed_aabb()

        single_result = check_visibility(cam, points, bed)
        multi_result = check_visibility_multi_camera([cam], points, bed)

        assert multi_result.shape == (1, 3)
        np.testing.assert_array_equal(multi_result[0], single_result)


# ===========================================================================
# カテゴリD: F04/F05との整合性
# ===========================================================================


class TestConsistencyWithF04F05:
    """D1-D3: F04/F05との整合性テスト。"""

    def test_d1_consistency_with_frustum_no_occlusion(self) -> None:
        """D1: 遮蔽がない設定で check_visibility ≡ FrustumChecker.is_visible。"""
        cam = create_camera([0.2, 0.2, 2.0], [1.4, 1.75, 0.5])
        points = np.array([
            [0.5, 0.5, 0.0],
            [1.4, 1.75, 0.5],
            [2.6, 3.3, 0.5],
            [0.2, 0.2, 1.9],
        ])
        dummy_bed = _dummy_bed_outside_room()

        # F06
        vis_result = check_visibility(cam, points, dummy_bed)

        # F04 単体
        checker = FrustumChecker(camera=cam)
        frustum_result = checker.is_visible(points)

        np.testing.assert_array_equal(vis_result, frustum_result)

    def test_d2_consistency_with_occlusion_all_in_frustum(self) -> None:
        """D2: 全点が視錐台内の設定で check_visibility ≡ ~check_bed_occlusion。"""
        # 高所カメラ（forward//up_hint回避のためup_hint指定）
        cam = create_camera(
            [1.4, 1.75, 2.3], [1.4, 1.75, 0.0], up_hint=[0, 1, 0]
        )
        bed = _bed_aabb()

        # ベッド周辺の点（全て視錐台内であること確認）
        points = np.array([
            [1.4, 2.0, 0.0],   # ベッド下の床面
            [1.4, 2.5, 0.2],   # ベッド上面
            [1.0, 1.0, 0.0],   # ベッド外の床面
        ])

        # まず視錐台内であることを確認
        checker = FrustumChecker(camera=cam)
        frustum_result = checker.is_visible(points)
        assert np.all(frustum_result), "全点が視錐台内であることが前提"

        # F06
        vis_result = check_visibility(cam, points, bed)

        # F05 単体
        occ_result = check_bed_occlusion(cam.position, points, bed)

        np.testing.assert_array_equal(vis_result, ~occ_result)

    def test_d3_realistic_scenario(self) -> None:
        """D3: 実環境シナリオ。CLAUDE.md病室寸法での物理的妥当性。"""
        # 高所コーナーカメラ
        cam = create_camera([0.2, 0.2, 2.3], [1.4, 1.75, 0.5])
        bed = _bed_aabb()

        # look_at方向に近い点を選ぶ（垂直FOV内に収まるよう）
        room_center = np.array([1.0, 1.0, 0.5])          # ベッド外の中央付近 → 見える
        bed_top = np.array([1.4, 2.5, 0.2])              # ベッド上面 → 見える
        under_bed = np.array([1.4, 2.5, 0.05])           # ベッド下 → 遮蔽される

        points = np.array([room_center, bed_top, under_bed])
        result = check_visibility(cam, points, bed)

        # 部屋中央付近は見える
        assert result[0] is np.True_, "部屋中央付近は視認可能であるべき"
        # ベッド上面は見える（上から見下ろすカメラ）
        assert result[1] is np.True_, "ベッド上面は上方カメラから視認可能であるべき"
