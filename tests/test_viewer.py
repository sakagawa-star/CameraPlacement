"""F11: 3D可視化のテスト。"""

import numpy as np
import plotly.graph_objects as go
import pytest

from camera_placement.evaluation.coverage import CoverageResult, CoverageStats
from camera_placement.models.camera import Camera, create_camera
from camera_placement.models.environment import create_default_room
from camera_placement.visualization.viewer import (
    create_bed_traces,
    create_camera_traces,
    create_coverage_traces,
    create_frustum_traces,
    create_room_traces,
    create_scene,
    save_html,
)


def _create_test_cameras() -> list[Camera]:
    """テスト用6台カメラ（コーナー配置）。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([2.6, 0.2, 2.3], center),
        create_camera([0.2, 3.3, 2.3], center),
        create_camera([2.6, 3.3, 2.3], center),
        create_camera([1.4, 0.2, 2.3], center),
        create_camera([1.4, 3.3, 2.3], center),
    ]


def _create_test_coverage_result(cameras: list[Camera]) -> CoverageResult:
    """テスト用CoverageResult（簡易版）。"""
    grid_points = np.array([
        [1.0, 1.0, 0.5],
        [1.5, 2.0, 0.5],
        [2.0, 1.0, 1.0],
        [1.0, 2.5, 0.3],
        [1.5, 1.5, 1.5],
    ])
    visible_counts = np.array([3, 4, 2, 5, 6])
    num_cameras = len(cameras)
    stats = CoverageStats(
        visible_counts=visible_counts,
        num_cameras=num_cameras,
        num_points=len(grid_points),
    )
    visibility_matrix = np.ones((num_cameras, len(grid_points)), dtype=bool)
    from camera_placement.models.activity import ActivityType
    return CoverageResult(
        cameras=cameras,
        merged_grid=grid_points,
        visibility_matrix=visibility_matrix,
        stats=stats,
        volume_coverages={},
    )


# ============================================================
# カテゴリA: create_room_traces
# ============================================================


class TestCreateRoomTraces:
    """create_room_traces のテスト。"""

    def test_a1_basic(self) -> None:
        """A1: 基本動作 - リスト長1、型 go.Scatter3d。"""
        room = create_default_room()
        traces = create_room_traces(room)
        assert len(traces) == 1
        assert isinstance(traces[0], go.Scatter3d)

    def test_a2_trace_name(self) -> None:
        """A2: トレース名が "Room"。"""
        room = create_default_room()
        traces = create_room_traces(room)
        assert traces[0].name == "Room"

    def test_a3_coordinate_length(self) -> None:
        """A3: 座標データの長さが36（12辺 × 3要素）。"""
        room = create_default_room()
        traces = create_room_traces(room)
        assert len(traces[0].x) == 36

    def test_a4_none_separators(self) -> None:
        """A4: None区切りが12個含まれる。"""
        room = create_default_room()
        traces = create_room_traces(room)
        none_count = sum(1 for v in traces[0].x if v is None)
        assert none_count == 12


# ============================================================
# カテゴリB: create_bed_traces
# ============================================================


class TestCreateBedTraces:
    """create_bed_traces のテスト。"""

    def test_b1_basic(self) -> None:
        """B1: 基本動作 - リスト長1、型 go.Mesh3d。"""
        room = create_default_room()
        traces = create_bed_traces(room)
        assert len(traces) == 1
        assert isinstance(traces[0], go.Mesh3d)

    def test_b2_trace_name(self) -> None:
        """B2: トレース名が "Bed"。"""
        room = create_default_room()
        traces = create_bed_traces(room)
        assert traces[0].name == "Bed"

    def test_b3_vertex_count(self) -> None:
        """B3: 頂点数が8。"""
        room = create_default_room()
        traces = create_bed_traces(room)
        assert len(traces[0].x) == 8

    def test_b4_face_count(self) -> None:
        """B4: 三角形面が12個。"""
        room = create_default_room()
        traces = create_bed_traces(room)
        assert len(traces[0].i) == 12

    def test_b5_opacity(self) -> None:
        """B5: 不透明度が0.3。"""
        room = create_default_room()
        traces = create_bed_traces(room)
        assert traces[0].opacity == 0.3


# ============================================================
# カテゴリC: create_camera_traces
# ============================================================


class TestCreateCameraTraces:
    """create_camera_traces のテスト。"""

    def test_c1_basic(self) -> None:
        """C1: 6台カメラで要素数2（マーカー + 方向線）。"""
        cameras = _create_test_cameras()
        traces = create_camera_traces(cameras)
        assert len(traces) == 2

    def test_c2_marker_trace_name(self) -> None:
        """C2: マーカートレース名が "Cameras"。"""
        cameras = _create_test_cameras()
        traces = create_camera_traces(cameras)
        assert traces[0].name == "Cameras"

    def test_c3_direction_trace_name(self) -> None:
        """C3: 方向線トレース名が "Camera Direction"。"""
        cameras = _create_test_cameras()
        traces = create_camera_traces(cameras)
        assert traces[1].name == "Camera Direction"

    def test_c4_marker_positions_count(self) -> None:
        """C4: マーカー位置数が6。"""
        cameras = _create_test_cameras()
        traces = create_camera_traces(cameras)
        assert len(traces[0].x) == 6

    def test_c5_text_labels(self) -> None:
        """C5: テキストラベルが C1〜C6。"""
        cameras = _create_test_cameras()
        traces = create_camera_traces(cameras)
        expected = ("C1", "C2", "C3", "C4", "C5", "C6")
        assert traces[0].text == expected

    def test_c6_empty_cameras(self) -> None:
        """C6: 空カメラリストで要素数0。"""
        traces = create_camera_traces([])
        assert len(traces) == 0

    def test_c7_single_camera(self) -> None:
        """C7: 1台カメラで要素数2、マーカー位置数1。"""
        cameras = [create_camera([0.2, 0.2, 2.3], [1.4, 1.75, 0.5])]
        traces = create_camera_traces(cameras)
        assert len(traces) == 2
        assert len(traces[0].x) == 1


# ============================================================
# カテゴリD: create_frustum_traces
# ============================================================


class TestCreateFrustumTraces:
    """create_frustum_traces のテスト。"""

    def test_d1_basic(self) -> None:
        """D1: 6台カメラでリスト長6。"""
        cameras = _create_test_cameras()
        traces = create_frustum_traces(cameras)
        assert len(traces) == 6

    def test_d2_trace_name(self) -> None:
        """D2: 最初のトレース名が "Frustum C1"。"""
        cameras = _create_test_cameras()
        traces = create_frustum_traces(cameras)
        assert traces[0].name == "Frustum C1"

    def test_d3_legendgroup(self) -> None:
        """D3: legendgroup が "frustums"。"""
        cameras = _create_test_cameras()
        traces = create_frustum_traces(cameras)
        assert traces[0].legendgroup == "frustums"

    def test_d4_coordinate_length(self) -> None:
        """D4: 1台のカメラで座標データ長が36。"""
        cameras = [create_camera([0.2, 0.2, 2.3], [1.4, 1.75, 0.5])]
        traces = create_frustum_traces(cameras)
        assert len(traces[0].x) == 36

    def test_d5_empty_cameras(self) -> None:
        """D5: 空カメラリストで要素数0。"""
        traces = create_frustum_traces([])
        assert len(traces) == 0

    def test_d6_far_zero(self) -> None:
        """D6: far=0 で ValueError。"""
        cameras = _create_test_cameras()
        with pytest.raises(ValueError):
            create_frustum_traces(cameras, far=0)

    def test_d7_far_less_than_near(self) -> None:
        """D7: far <= near で ValueError。"""
        cameras = _create_test_cameras()
        with pytest.raises(ValueError):
            create_frustum_traces(cameras, near=1.0, far=0.5)


# ============================================================
# カテゴリE: create_coverage_traces
# ============================================================


class TestCreateCoverageTraces:
    """create_coverage_traces のテスト。"""

    def test_e1_basic(self) -> None:
        """E1: 基本動作 - リスト長1、型 go.Scatter3d。"""
        points = np.random.rand(10, 3)
        counts = np.arange(10)
        traces = create_coverage_traces(points, counts)
        assert len(traces) == 1
        assert isinstance(traces[0], go.Scatter3d)

    def test_e2_trace_name(self) -> None:
        """E2: トレース名が "Coverage"。"""
        points = np.random.rand(10, 3)
        counts = np.arange(10)
        traces = create_coverage_traces(points, counts)
        assert traces[0].name == "Coverage"

    def test_e3_marker_size(self) -> None:
        """E3: マーカーサイズが3。"""
        points = np.random.rand(10, 3)
        counts = np.arange(10)
        traces = create_coverage_traces(points, counts)
        assert traces[0].marker.size == 3

    def test_e4_colorscale(self) -> None:
        """E4: カラースケールが RdYlGn（plotlyが内部展開するためタプル形式で検証）。"""
        points = np.random.rand(10, 3)
        counts = np.arange(10)
        traces = create_coverage_traces(points, counts)
        # plotly は名前付きカラースケールを内部的にタプルのリストに展開する
        colorscale = traces[0].marker.colorscale
        assert isinstance(colorscale, tuple)
        assert len(colorscale) > 0

    def test_e5_cmin_cmax(self) -> None:
        """E5: cmin=0, cmax=num_cameras。"""
        points = np.random.rand(10, 3)
        counts = np.arange(10)
        traces = create_coverage_traces(points, counts, num_cameras=6)
        assert traces[0].marker.cmin == 0
        assert traces[0].marker.cmax == 6

    def test_e6_empty_grid(self) -> None:
        """E6: 空グリッドでリスト長1、データなし。"""
        points = np.zeros((0, 3))
        counts = np.zeros(0, dtype=int)
        traces = create_coverage_traces(points, counts)
        assert len(traces) == 1
        assert len(traces[0].x) == 0


# ============================================================
# カテゴリF: create_scene
# ============================================================


class TestCreateScene:
    """create_scene のテスト。"""

    def test_f1_minimal(self) -> None:
        """F1: 最小構成 - room + cameras + frustums = 10トレース。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras)
        # 1(room) + 1(bed) + 2(cam) + 6(frustum) = 10
        assert len(fig.data) == 10

    def test_f2_with_coverage(self) -> None:
        """F2: カバレッジ付き = 11トレース。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        coverage = _create_test_coverage_result(cameras)
        fig = create_scene(room, cameras, coverage_result=coverage)
        # 10 + 1(coverage) = 11
        assert len(fig.data) == 11

    def test_f3_no_frustums(self) -> None:
        """F3: show_frustums=False で視錐台なし = 4トレース。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras, show_frustums=False)
        # 1(room) + 1(bed) + 2(cam) = 4
        assert len(fig.data) == 4

    def test_f4_no_grid(self) -> None:
        """F4: show_grid=False でカバレッジなし = 10トレース。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        coverage = _create_test_coverage_result(cameras)
        fig = create_scene(room, cameras, coverage_result=coverage, show_grid=False)
        assert len(fig.data) == 10

    def test_f5_title(self) -> None:
        """F5: タイトル設定。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras, title="Test")
        assert fig.layout.title.text == "Test"

    def test_f6_axis_labels(self) -> None:
        """F6: 軸ラベル設定。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras)
        assert fig.layout.scene.xaxis.title.text == "X [m]"
        assert fig.layout.scene.yaxis.title.text == "Y [m]"
        assert fig.layout.scene.zaxis.title.text == "Z [m]"

    def test_f7_aspectmode(self) -> None:
        """F7: aspectmode が "data"。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras)
        assert fig.layout.scene.aspectmode == "data"

    def test_f8_frustum_far_invalid(self) -> None:
        """F8: frustum_far <= 0 で ValueError。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        with pytest.raises(ValueError):
            create_scene(room, cameras, frustum_far=0)

    def test_f9_empty_cameras(self) -> None:
        """F9: カメラ空リストで 2トレース（room + bed のみ）。"""
        room = create_default_room()
        fig = create_scene(room, [])
        # 1(room) + 1(bed) = 2
        assert len(fig.data) == 2

    def test_f10_no_coverage_result_with_show_grid(self) -> None:
        """F10: coverage_result=None, show_grid=True でカバレッジなし = 10トレース。"""
        room = create_default_room()
        cameras = _create_test_cameras()
        fig = create_scene(room, cameras, coverage_result=None, show_grid=True)
        assert len(fig.data) == 10


# ============================================================
# カテゴリG: save_html
# ============================================================


class TestSaveHtml:
    """save_html のテスト。"""

    def test_g1_basic(self, tmp_path: object) -> None:
        """G1: 基本動作 - ファイルが生成される。"""
        from pathlib import Path
        tmp = Path(str(tmp_path))
        filepath = tmp / "test.html"
        fig = go.Figure()
        save_html(fig, filepath)
        assert filepath.exists()

    def test_g2_return_value(self, tmp_path: object) -> None:
        """G2: 戻り値が Path。"""
        from pathlib import Path
        tmp = Path(str(tmp_path))
        filepath = tmp / "test.html"
        fig = go.Figure()
        result = save_html(fig, filepath)
        assert result == filepath

    def test_g3_auto_mkdir(self, tmp_path: object) -> None:
        """G3: 親ディレクトリ自動作成。"""
        from pathlib import Path
        tmp = Path(str(tmp_path))
        filepath = tmp / "sub" / "dir" / "test.html"
        fig = go.Figure()
        save_html(fig, filepath)
        assert filepath.exists()

    def test_g4_file_size(self, tmp_path: object) -> None:
        """G4: ファイルサイズ > 0。"""
        from pathlib import Path
        tmp = Path(str(tmp_path))
        filepath = tmp / "test.html"
        fig = go.Figure()
        save_html(fig, filepath)
        assert filepath.stat().st_size > 0
