"""F07: カバレッジ計算のテスト。"""

import numpy as np
import pytest

from camera_placement.evaluation.coverage import (
    CoverageResult,
    CoverageStats,
    VolumeCoverage,
    calculate_coverage,
    calculate_coverage_stats,
    calculate_volume_coverage,
)
from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
)
from camera_placement.models.camera import Camera, create_camera
from camera_placement.models.environment import AABB, Room, create_default_room


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

def _create_corner_cameras() -> list[Camera]:
    """テスト用6台コーナー配置カメラ。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([2.6, 0.2, 2.3], center),
        create_camera([0.2, 3.3, 2.3], center),
        create_camera([2.6, 3.3, 2.3], center),
        create_camera([1.4, 0.2, 2.3], center),
        create_camera([1.4, 3.3, 2.3], center),
    ]


def _small_activity_volume(activity_type: ActivityType) -> ActivityVolume:
    """テスト用の小規模活動ボリューム（計算時間短縮）。"""
    grid = np.array([
        [0.5, 0.5, 0.5],
        [1.0, 1.0, 0.5],
        [1.5, 0.5, 1.0],
        [0.5, 1.0, 1.5],
    ])
    return ActivityVolume(activity_type, grid)


# ===========================================================================
# カテゴリA: CoverageStats の統計計算 (calculate_coverage_stats)
# ===========================================================================

class TestCalculateCoverageStats:
    """calculate_coverage_stats のテスト。"""

    def test_a1_all_visible(self) -> None:
        """A1: 全カメラから視認可能な場合。"""
        vis = np.ones((3, 4), dtype=bool)
        stats = calculate_coverage_stats(vis)
        np.testing.assert_array_equal(stats.visible_counts, [3, 3, 3, 3])
        assert stats.coverage_3plus == 1.0
        assert stats.num_cameras == 3
        assert stats.num_points == 4

    def test_a2_partial_visibility(self) -> None:
        """A2: 部分視認の場合。手動計算と一致。"""
        # カメラ0: 点0,1 が視認可能
        # カメラ1: 点1,2 が視認可能
        # カメラ2: 点0,1,2,3 が視認可能
        vis = np.array([
            [True, True, False, False],
            [False, True, True, False],
            [True, True, True, True],
        ])
        stats = calculate_coverage_stats(vis)
        # 点0: 2台, 点1: 3台, 点2: 2台, 点3: 1台
        np.testing.assert_array_equal(stats.visible_counts, [2, 3, 2, 1])
        assert stats.coverage_3plus == pytest.approx(1.0 / 4.0)  # 1/4 = 0.25
        assert stats.min_visible == 1
        assert stats.max_visible == 3
        assert stats.mean_visible == pytest.approx(2.0)  # (2+3+2+1)/4

    def test_a3_all_invisible(self) -> None:
        """A3: 全点が視認不可の場合。"""
        vis = np.zeros((3, 4), dtype=bool)
        stats = calculate_coverage_stats(vis)
        np.testing.assert_array_equal(stats.visible_counts, [0, 0, 0, 0])
        assert stats.coverage_3plus == 0.0
        assert stats.min_visible == 0
        assert stats.max_visible == 0
        assert stats.mean_visible == 0.0

    def test_a4_coverage_at_least_thresholds(self) -> None:
        """A4: coverage_at_least の各閾値が正しいこと。"""
        # 4カメラ, 5点: 視認カメラ数 = [0, 1, 2, 3, 4]
        vis = np.array([
            [False, True, True, True, True],
            [False, False, True, True, True],
            [False, False, False, True, True],
            [False, False, False, False, True],
        ])
        stats = calculate_coverage_stats(vis)
        np.testing.assert_array_equal(stats.visible_counts, [0, 1, 2, 3, 4])
        cal = stats.coverage_at_least
        assert cal[1] == pytest.approx(4.0 / 5.0)  # 点1,2,3,4
        assert cal[2] == pytest.approx(3.0 / 5.0)  # 点2,3,4
        assert cal[3] == pytest.approx(2.0 / 5.0)  # 点3,4
        assert cal[4] == pytest.approx(1.0 / 5.0)  # 点4

    def test_a5_min_max_mean(self) -> None:
        """A5: min/max/mean_visible の個別検証。"""
        vis = np.array([
            [True, False, True],
            [True, True, False],
        ])
        stats = calculate_coverage_stats(vis)
        # 点0: 2台, 点1: 1台, 点2: 1台
        assert stats.min_visible == 1
        assert stats.max_visible == 2
        assert stats.mean_visible == pytest.approx(4.0 / 3.0)

    def test_a6_empty_points(self) -> None:
        """A6: 空の行列 shape (3, 0) の場合。"""
        vis = np.zeros((3, 0), dtype=bool)
        stats = calculate_coverage_stats(vis)
        assert stats.num_cameras == 3
        assert stats.num_points == 0
        assert stats.coverage_3plus == 0.0
        assert stats.min_visible == 0
        assert stats.max_visible == 0
        assert stats.mean_visible == 0.0
        assert stats.coverage_at_least == {1: 0.0, 2: 0.0, 3: 0.0}

    def test_a7_single_point(self) -> None:
        """A7: 単一点 shape (3, 1) の場合。"""
        vis = np.array([[True], [False], [True]])
        stats = calculate_coverage_stats(vis)
        assert stats.num_points == 1
        np.testing.assert_array_equal(stats.visible_counts, [2])
        assert stats.min_visible == 2
        assert stats.max_visible == 2
        assert stats.mean_visible == 2.0
        assert stats.coverage_3plus == 0.0

    def test_a8_non_2d_input(self) -> None:
        """A8: 2Dでない入力は ValueError。"""
        with pytest.raises(ValueError, match="2D"):
            calculate_coverage_stats(np.array([True, False, True]))


# ===========================================================================
# カテゴリB: calculate_volume_coverage
# ===========================================================================

class TestCalculateVolumeCoverage:
    """calculate_volume_coverage のテスト。"""

    def test_b1_basic(self) -> None:
        """B1: 基本動作。VolumeCoverage の各フィールドが正しく設定される。"""
        cameras = [
            create_camera([0.2, 0.2, 2.3], [0.5, 0.5, 0.5]),
            create_camera([2.6, 0.2, 2.3], [0.5, 0.5, 0.5]),
        ]
        vol = _small_activity_volume(ActivityType.WALKING)
        bed_aabb = AABB(
            min_point=np.array([0.9, 1.5, 0.0]),
            max_point=np.array([1.9, 3.5, 0.2]),
        )
        vc = calculate_volume_coverage(cameras, vol, bed_aabb)
        assert isinstance(vc, VolumeCoverage)
        assert vc.activity_type == ActivityType.WALKING
        assert isinstance(vc.stats, CoverageStats)
        assert vc.stats.num_cameras == 2

    def test_b2_visibility_matrix_shape(self) -> None:
        """B2: visibility_matrix の shape が (M, N)。"""
        cameras = [
            create_camera([0.2, 0.2, 2.3], [1.0, 1.0, 0.5]),
            create_camera([2.6, 0.2, 2.3], [1.0, 1.0, 0.5]),
            create_camera([1.4, 3.3, 2.3], [1.0, 1.0, 0.5]),
        ]
        vol = _small_activity_volume(ActivityType.SEATED)
        bed_aabb = AABB(
            min_point=np.array([0.9, 1.5, 0.0]),
            max_point=np.array([1.9, 3.5, 0.2]),
        )
        vc = calculate_volume_coverage(cameras, vol, bed_aabb)
        assert vc.visibility_matrix.shape == (3, 4)

    def test_b3_num_points_consistency(self) -> None:
        """B3: stats.num_points == volume.num_points。"""
        cameras = [create_camera([0.2, 0.2, 2.3], [1.0, 1.0, 0.5])]
        vol = _small_activity_volume(ActivityType.SUPINE)
        bed_aabb = AABB(
            min_point=np.array([0.9, 1.5, 0.0]),
            max_point=np.array([1.9, 3.5, 0.2]),
        )
        vc = calculate_volume_coverage(cameras, vol, bed_aabb)
        assert vc.stats.num_points == vol.num_points


# ===========================================================================
# カテゴリC: calculate_coverage（メイン関数）
# ===========================================================================

class TestCalculateCoverage:
    """calculate_coverage のテスト。"""

    def test_c1_basic_default_volumes(self) -> None:
        """C1: デフォルトvolumesでの基本動作。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert isinstance(result, CoverageResult)
        assert result.merged_grid.ndim == 2
        assert result.merged_grid.shape[1] == 3
        assert result.visibility_matrix.ndim == 2
        assert isinstance(result.stats, CoverageStats)
        assert len(result.volume_coverages) == 3

    def test_c2_custom_volumes(self) -> None:
        """C2: 指定volumesが使用される。"""
        cameras = [
            create_camera([0.2, 0.2, 2.3], [1.0, 1.0, 0.5]),
            create_camera([2.6, 0.2, 2.3], [1.0, 1.0, 0.5]),
        ]
        room = create_default_room()
        custom_vols = [_small_activity_volume(ActivityType.WALKING)]
        result = calculate_coverage(cameras, room, volumes=custom_vols)
        assert len(result.volume_coverages) == 1
        assert ActivityType.WALKING in result.volume_coverages

    def test_c3_volume_coverages_keys(self) -> None:
        """C3: デフォルト3ボリュームのキーが WALKING, SEATED, SUPINE。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert set(result.volume_coverages.keys()) == {
            ActivityType.WALKING,
            ActivityType.SEATED,
            ActivityType.SUPINE,
        }

    def test_c4_cameras_preserved(self) -> None:
        """C4: result.cameras が入力と同じ。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result.cameras is cameras

    def test_c5_merged_grid_shape(self) -> None:
        """C5: merged_grid が (N, 3) shape を持つ。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result.merged_grid.shape[1] == 3
        assert result.merged_grid.shape[0] > 0

    def test_c6_visibility_matrix_shape_consistency(self) -> None:
        """C6: visibility_matrix の shape が (M, N_merged)。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result.visibility_matrix.shape == (
            len(cameras),
            result.merged_grid.shape[0],
        )

    def test_c7_near_far_propagation(self) -> None:
        """C7: far=1.0 で遠方の点が視認不可になる。"""
        cameras = [create_camera([0.2, 0.2, 2.3], [1.4, 1.75, 0.5])]
        room = create_default_room()
        # far=10.0（デフォルト）
        result_far = calculate_coverage(cameras, room, grid_spacing=0.5, far=10.0)
        # far=1.0（厳しい制約）
        result_near = calculate_coverage(cameras, room, grid_spacing=0.5, far=1.0)
        # far が短いほどカバレッジが低い
        assert result_near.stats.mean_visible <= result_far.stats.mean_visible


# ===========================================================================
# カテゴリD: エッジケース
# ===========================================================================

class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_d1_no_cameras(self) -> None:
        """D1: カメラ0台で全点のカバレッジが0。"""
        cameras: list[Camera] = []
        room = create_default_room()
        custom_vols = [_small_activity_volume(ActivityType.WALKING)]
        result = calculate_coverage(cameras, room, volumes=custom_vols)
        assert result.stats.coverage_3plus == 0.0
        np.testing.assert_array_equal(
            result.stats.visible_counts,
            np.zeros(result.merged_grid.shape[0], dtype=int),
        )

    def test_d2_all_visible(self) -> None:
        """D2: 全カメラから全点が視認可能な場合（近距離・小グリッド）。"""
        # カメラを点群の近くに配置
        center = [0.5, 0.5, 0.5]
        cameras = [
            create_camera([0.2, 0.2, 1.5], center),
            create_camera([0.8, 0.2, 1.5], center),
            create_camera([0.2, 0.8, 1.5], center),
            create_camera([0.8, 0.8, 1.5], center),
            create_camera([0.5, 0.2, 1.5], center),
            create_camera([0.5, 0.8, 1.5], center),
        ]
        grid = np.array([[0.5, 0.5, 0.5]])
        vol = ActivityVolume(ActivityType.WALKING, grid)
        room = create_default_room()
        result = calculate_coverage(cameras, room, volumes=[vol])
        assert result.stats.coverage_3plus == 1.0

    def test_d3_grid_spacing(self) -> None:
        """D3: grid_spacing を変更するとポイント数が変わる。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result_02 = calculate_coverage(cameras, room, grid_spacing=0.2)
        result_05 = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result_02.merged_grid.shape[0] > result_05.merged_grid.shape[0]

    def test_d4_empty_volumes(self) -> None:
        """D4: volumes が空リストの場合。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, volumes=[])
        assert result.merged_grid.shape == (0, 3)
        assert result.stats.num_points == 0
        assert result.stats.coverage_3plus == 0.0
        assert result.volume_coverages == {}


# ===========================================================================
# カテゴリE: 実環境シナリオ
# ===========================================================================

class TestRealWorldScenarios:
    """実環境シナリオのテスト。"""

    def test_e1_corner_placement(self) -> None:
        """E1: コーナー配置6台で coverage_3plus > 0。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result.stats.coverage_3plus > 0.0

    def test_e2_volume_difference(self) -> None:
        """E2: 活動ボリューム別のカバレッジが個別に計算される。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.3)
        walking_vc = result.volume_coverages[ActivityType.WALKING]
        seated_vc = result.volume_coverages[ActivityType.SEATED]
        supine_vc = result.volume_coverages[ActivityType.SUPINE]
        # 各ボリュームが個別の統計を持つ
        assert walking_vc.stats.num_points > 0
        assert seated_vc.stats.num_points > 0
        assert supine_vc.stats.num_points > 0
        # 各ボリュームのvisibility_matrixのshapeが正しい
        assert walking_vc.visibility_matrix.shape == (6, walking_vc.stats.num_points)
        assert seated_vc.visibility_matrix.shape == (6, seated_vc.stats.num_points)
        assert supine_vc.visibility_matrix.shape == (6, supine_vc.stats.num_points)

    def test_e3_stats_consistency(self) -> None:
        """E3: coverage_at_least[3] == coverage_3plus の一貫性。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = calculate_coverage(cameras, room, grid_spacing=0.5)
        assert result.stats.coverage_at_least[3] == pytest.approx(
            result.stats.coverage_3plus
        )
