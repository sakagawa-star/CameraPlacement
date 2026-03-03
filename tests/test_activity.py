"""F03: 活動ボリューム・グリッド生成のテスト。"""

import numpy as np
import pytest

from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
    create_merged_grid,
)
from camera_placement.models.environment import AABB, Room, create_default_room


def _grid_1d(start: float, stop: float, spacing: float) -> np.ndarray:
    """テスト用: 実装と同じグリッド生成ロジック。"""
    vals = np.arange(start, stop + spacing / 2, spacing)
    return vals[vals <= stop + 1e-10]


class TestActivityVolume:
    """ActivityVolumeの基本テスト。"""

    def test_valid_grid_points(self) -> None:
        """テスト1: grid_pointsのshape検証。"""
        points = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        vol = ActivityVolume(ActivityType.WALKING, points)
        assert vol.num_points == 2

    def test_invalid_shape_raises(self) -> None:
        """テスト2: 不正なshapeでValueError。"""
        with pytest.raises(ValueError, match="shape"):
            ActivityVolume(
                ActivityType.WALKING,
                np.array([[0.0, 0.0], [1.0, 1.0]]),
            )

    def test_empty_grid(self) -> None:
        """テスト3: 空の点群(0,3)。"""
        vol = ActivityVolume(ActivityType.WALKING, np.empty((0, 3)))
        assert vol.num_points == 0


class TestWalkingGrid:
    """歩行グリッドのテスト。"""

    @pytest.fixture()
    def walking_volume(self) -> ActivityVolume:
        volumes = create_activity_volumes()
        return volumes[0]

    def test_points_generated(self, walking_volume: ActivityVolume) -> None:
        """テスト4: 点群が生成される。"""
        assert walking_volume.num_points > 0

    def test_no_points_in_bed_xy(self, walking_volume: ActivityVolume) -> None:
        """テスト5: 全点がベッドXY投影外。"""
        room = create_default_room()
        pts = walking_volume.grid_points
        bed_min = room.bed.min_point[:2]
        bed_max = room.bed.max_point[:2]
        in_bed = np.all(
            (pts[:, :2] >= bed_min) & (pts[:, :2] <= bed_max), axis=1
        )
        assert np.sum(in_bed) == 0

    def test_z_range(self, walking_volume: ActivityVolume) -> None:
        """テスト6: Z範囲が 0~1.8。"""
        pts = walking_volume.grid_points
        assert pts[:, 2].min() >= 0.0
        assert pts[:, 2].max() <= 1.8 + 1e-10

    def test_xy_range(self, walking_volume: ActivityVolume) -> None:
        """テスト7: XY範囲が部屋内。"""
        pts = walking_volume.grid_points
        assert pts[:, 0].min() >= 0.0
        assert pts[:, 0].max() <= 2.8 + 1e-10
        assert pts[:, 1].min() >= 0.0
        assert pts[:, 1].max() <= 3.5 + 1e-10

    def test_known_point_count(self) -> None:
        """テスト8: 既知の点数と一致。"""
        volumes = create_activity_volumes(grid_spacing=0.2)
        walking = volumes[0]
        xs = _grid_1d(0.0, 2.8, 0.2)
        ys = _grid_1d(0.0, 3.5, 0.2)
        zs = _grid_1d(0.0, 1.8, 0.2)
        xx, yy = np.meshgrid(xs, ys, indexing="ij")
        xy = np.column_stack([xx.ravel(), yy.ravel()])
        bed_min = np.array([0.9, 1.5])
        bed_max = np.array([1.9, 3.5])
        in_bed = np.all((xy >= bed_min) & (xy <= bed_max), axis=1)
        n_xy_outside = np.sum(~in_bed)
        expected = n_xy_outside * len(zs)
        assert walking.num_points == expected


class TestSeatedGrid:
    """座位グリッドのテスト。"""

    @pytest.fixture()
    def seated_volume(self) -> ActivityVolume:
        volumes = create_activity_volumes()
        return volumes[1]

    def test_points_generated(self, seated_volume: ActivityVolume) -> None:
        """テスト9: 点群が生成される。"""
        assert seated_volume.num_points > 0

    def test_all_in_bed_xy(self, seated_volume: ActivityVolume) -> None:
        """テスト10: 全点がベッドXY投影内。"""
        pts = seated_volume.grid_points
        assert np.all(pts[:, 0] >= 0.9 - 1e-10)
        assert np.all(pts[:, 0] <= 1.9 + 1e-10)
        assert np.all(pts[:, 1] >= 1.5 - 1e-10)
        assert np.all(pts[:, 1] <= 3.5 + 1e-10)

    def test_z_range(self, seated_volume: ActivityVolume) -> None:
        """テスト11: Z範囲が 0.2~1.1。"""
        pts = seated_volume.grid_points
        assert pts[:, 2].min() >= 0.2 - 1e-10
        assert pts[:, 2].max() <= 1.1 + 1e-10

    def test_known_point_count(self) -> None:
        """テスト12: 既知の点数と一致。"""
        volumes = create_activity_volumes(grid_spacing=0.2)
        seated = volumes[1]
        xs = _grid_1d(0.9, 1.9, 0.2)
        ys = _grid_1d(1.5, 3.5, 0.2)
        zs = _grid_1d(0.2, 1.1, 0.2)
        expected = len(xs) * len(ys) * len(zs)
        assert seated.num_points == expected


class TestSupineGrid:
    """臥位グリッドのテスト。"""

    @pytest.fixture()
    def supine_volume(self) -> ActivityVolume:
        volumes = create_activity_volumes()
        return volumes[2]

    def test_points_generated(self, supine_volume: ActivityVolume) -> None:
        """テスト13: 点群が生成される。"""
        assert supine_volume.num_points > 0

    def test_all_in_bed_xy(self, supine_volume: ActivityVolume) -> None:
        """テスト14: 全点がベッドXY投影内。"""
        pts = supine_volume.grid_points
        assert np.all(pts[:, 0] >= 0.9 - 1e-10)
        assert np.all(pts[:, 0] <= 1.9 + 1e-10)
        assert np.all(pts[:, 1] >= 1.5 - 1e-10)
        assert np.all(pts[:, 1] <= 3.5 + 1e-10)

    def test_z_range(self, supine_volume: ActivityVolume) -> None:
        """テスト15: Z範囲が 0.2~0.5。"""
        pts = supine_volume.grid_points
        assert pts[:, 2].min() >= 0.2 - 1e-10
        assert pts[:, 2].max() <= 0.5 + 1e-10

    def test_known_point_count(self) -> None:
        """テスト16: 既知の点数と一致。"""
        volumes = create_activity_volumes(grid_spacing=0.2)
        supine = volumes[2]
        xs = _grid_1d(0.9, 1.9, 0.2)
        ys = _grid_1d(1.5, 3.5, 0.2)
        zs = _grid_1d(0.2, 0.5, 0.2)
        expected = len(xs) * len(ys) * len(zs)
        assert supine.num_points == expected


class TestCreateActivityVolumes:
    """ファクトリ関数のテスト。"""

    def test_returns_three_volumes(self) -> None:
        """テスト17: 3つの ActivityVolume が返る。"""
        volumes = create_activity_volumes()
        assert len(volumes) == 3
        assert volumes[0].activity_type == ActivityType.WALKING
        assert volumes[1].activity_type == ActivityType.SEATED
        assert volumes[2].activity_type == ActivityType.SUPINE

    def test_none_room_uses_default(self) -> None:
        """テスト18: room=None でデフォルト room 使用。"""
        volumes = create_activity_volumes(room=None)
        assert len(volumes) == 3
        assert volumes[0].num_points > 0

    def test_zero_spacing_raises(self) -> None:
        """テスト19: grid_spacing=0 で ValueError。"""
        with pytest.raises(ValueError, match="positive"):
            create_activity_volumes(grid_spacing=0)

    def test_negative_spacing_raises(self) -> None:
        """テスト20: grid_spacing=負 で ValueError。"""
        with pytest.raises(ValueError, match="positive"):
            create_activity_volumes(grid_spacing=-0.1)


class TestMergedGrid:
    """統合グリッドのテスト。"""

    def test_deduplication(self) -> None:
        """テスト21: 重複除去が行われる。"""
        volumes = create_activity_volumes()
        merged = create_merged_grid(volumes)
        total = sum(v.num_points for v in volumes)
        assert merged.shape[0] < total

    def test_known_merged_count(self) -> None:
        """テスト22: 具体的な統合点数。"""
        volumes = create_activity_volumes(grid_spacing=0.2)
        merged = create_merged_grid(volumes)
        # 座位Z と 臥位Z の重複点を計算
        xs = _grid_1d(0.9, 1.9, 0.2)
        ys = _grid_1d(1.5, 3.5, 0.2)
        seated_zs = _grid_1d(0.2, 1.1, 0.2)
        supine_zs = _grid_1d(0.2, 0.5, 0.2)
        # 臥位Zは全て座位Zに含まれる → 重複 = 臥位の全点数
        n_bed_xy = len(xs) * len(ys)
        overlap_count = n_bed_xy * len(supine_zs)
        total = sum(v.num_points for v in volumes)
        expected = total - overlap_count
        assert merged.shape[0] == expected

    def test_empty_list(self) -> None:
        """テスト23: 空リストで(0,3)配列。"""
        merged = create_merged_grid([])
        assert merged.shape == (0, 3)


class TestGridSpacing:
    """グリッド間隔のテスト。"""

    def test_finer_spacing_more_points(self) -> None:
        """テスト24: spacing=0.1 で点数増加。"""
        vol_02 = create_activity_volumes(grid_spacing=0.2)
        vol_01 = create_activity_volumes(grid_spacing=0.1)
        for v02, v01 in zip(vol_02, vol_01):
            assert v01.num_points > v02.num_points

    def test_coarser_spacing_fewer_points(self) -> None:
        """テスト25: spacing=0.3 で点数減少。"""
        vol_02 = create_activity_volumes(grid_spacing=0.2)
        vol_03 = create_activity_volumes(grid_spacing=0.3)
        for v02, v03 in zip(vol_02, vol_03):
            assert v03.num_points < v02.num_points


class TestCustomRoom:
    """カスタムRoomのテスト。"""

    def test_custom_bed_exclusion(self) -> None:
        """テスト26: ベッド位置変更時の除外。"""
        room = Room(
            bed=AABB(
                min_point=np.array([0.5, 0.5, 0.0]),
                max_point=np.array([1.5, 2.5, 0.2]),
            )
        )
        volumes = create_activity_volumes(room=room)
        walking = volumes[0]
        pts = walking.grid_points
        bed_min = np.array([0.5, 0.5])
        bed_max = np.array([1.5, 2.5])
        in_bed = np.all(
            (pts[:, :2] >= bed_min) & (pts[:, :2] <= bed_max), axis=1
        )
        assert np.sum(in_bed) == 0


class TestDtype:
    """dtype確認のテスト。"""

    def test_all_grids_float64(self) -> None:
        """テスト27: 全グリッドが float64。"""
        volumes = create_activity_volumes()
        for vol in volumes:
            assert vol.grid_points.dtype == np.float64
        merged = create_merged_grid(volumes)
        assert merged.dtype == np.float64
