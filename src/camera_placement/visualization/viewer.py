"""F11: 3D可視化。

病室空間・ベッド・カメラ・視錐台・カバレッジマップを plotly で
3Dインタラクティブ表示する可視化モジュール。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from camera_placement.core.frustum import FrustumChecker
from camera_placement.evaluation.coverage import CoverageResult
from camera_placement.models.camera import Camera
from camera_placement.models.environment import AABB, Room

# --- 定数 ---

CAMERA_COLORS: list[str] = [
    "rgb(31, 119, 180)",   # 青
    "rgb(255, 127, 14)",   # 橙
    "rgb(44, 160, 44)",    # 緑
    "rgb(214, 39, 40)",    # 赤
    "rgb(148, 103, 189)",  # 紫
    "rgb(140, 86, 75)",    # 茶
]

ROOM_COLOR: str = "rgb(0, 0, 0)"
ROOM_LINE_WIDTH: int = 2

BED_COLOR: str = "lightblue"
BED_OPACITY: float = 0.3

CAMERA_MARKER_SIZE: int = 6
CAMERA_MARKER_COLOR: str = "rgb(0, 0, 0)"
CAMERA_MARKER_SYMBOL: str = "diamond"
CAMERA_DIRECTION_LENGTH: float = 0.3
CAMERA_DIRECTION_WIDTH: int = 3

FRUSTUM_LINE_WIDTH: float = 1.5

COVERAGE_MARKER_SIZE: int = 3
COVERAGE_COLORSCALE: str = "RdYlGn"

FIGURE_WIDTH: int = 1000
FIGURE_HEIGHT: int = 800


# --- 内部ヘルパー ---


def _aabb_wireframe_coords(
    aabb: AABB,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """AABBの12辺のワイヤフレーム座標を生成する。

    Args:
        aabb: 対象のAABB。

    Returns:
        (xs, ys, zs) のタプル。各リストは辺の端点座標を含み、
        辺の区切りとして None を挿入する。
        各リストの長さは 12辺 × 3要素（始点, 終点, None） = 36。
    """
    x0, y0, z0 = aabb.min_point
    x1, y1, z1 = aabb.max_point

    vertices = [
        (x0, y0, z0),  # v0: 底面 手前左
        (x1, y0, z0),  # v1: 底面 手前右
        (x1, y1, z0),  # v2: 底面 奥右
        (x0, y1, z0),  # v3: 底面 奥左
        (x0, y0, z1),  # v4: 上面 手前左
        (x1, y0, z1),  # v5: 上面 手前右
        (x1, y1, z1),  # v6: 上面 奥右
        (x0, y1, z1),  # v7: 上面 奥左
    ]

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # 底面4辺
        (4, 5), (5, 6), (6, 7), (7, 4),  # 上面4辺
        (0, 4), (1, 5), (2, 6), (3, 7),  # 垂直4辺
    ]

    xs: list[float | None] = []
    ys: list[float | None] = []
    zs: list[float | None] = []
    for a, b in edges:
        xs.extend([vertices[a][0], vertices[b][0], None])
        ys.extend([vertices[a][1], vertices[b][1], None])
        zs.extend([vertices[a][2], vertices[b][2], None])

    return xs, ys, zs


def _frustum_wireframe_coords(
    corners: np.ndarray,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """視錐台の8頂点から12辺のワイヤフレーム座標を生成する。

    Args:
        corners: shape (8, 3)。FrustumChecker.get_frustum_corners() の戻り値。
            順序: [near_tl, near_tr, near_bl, near_br,
                    far_tl,  far_tr,  far_bl,  far_br]

    Returns:
        (xs, ys, zs) のタプル。各リストの長さは 36。
    """
    edges = [
        (0, 1), (1, 3), (3, 2), (2, 0),  # near面
        (4, 5), (5, 7), (7, 6), (6, 4),  # far面
        (0, 4), (1, 5), (2, 6), (3, 7),  # near-far接続
    ]

    xs: list[float | None] = []
    ys: list[float | None] = []
    zs: list[float | None] = []
    for a, b in edges:
        xs.extend([float(corners[a, 0]), float(corners[b, 0]), None])
        ys.extend([float(corners[a, 1]), float(corners[b, 1]), None])
        zs.extend([float(corners[a, 2]), float(corners[b, 2]), None])

    return xs, ys, zs


# --- 公開関数 ---


def create_room_traces(room: Room) -> list[go.Scatter3d]:
    """部屋のAABBワイヤフレームトレースを生成する。

    Args:
        room: 病室モデル。

    Returns:
        go.Scatter3d トレースのリスト（要素数1）。
    """
    xs, ys, zs = _aabb_wireframe_coords(room.room_aabb)
    trace = go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode="lines",
        line=dict(color=ROOM_COLOR, width=ROOM_LINE_WIDTH),
        name="Room",
        showlegend=True,
    )
    return [trace]


def create_bed_traces(room: Room) -> list[go.Mesh3d]:
    """ベッドの半透明ボックストレースを生成する。

    Args:
        room: 病室モデル（room.bed を使用）。

    Returns:
        go.Mesh3d トレースのリスト（要素数1）。
    """
    aabb = room.bed
    x0, y0, z0 = aabb.min_point
    x1, y1, z1 = aabb.max_point

    x = [x0, x1, x1, x0, x0, x1, x1, x0]
    y = [y0, y0, y1, y1, y0, y0, y1, y1]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]

    # 12個の三角形面（6面 × 2三角形）
    i = [0, 0, 4, 4, 0, 0, 2, 2, 0, 0, 1, 1]
    j = [1, 2, 5, 6, 1, 5, 3, 7, 3, 7, 2, 6]
    k = [2, 3, 6, 7, 5, 4, 7, 6, 7, 4, 6, 5]

    trace = go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        color=BED_COLOR,
        opacity=BED_OPACITY,
        name="Bed",
        showlegend=True,
    )
    return [trace]


def create_camera_traces(cameras: list[Camera]) -> list[go.Scatter3d]:
    """カメラ位置マーカーと方向線トレースを生成する。

    Args:
        cameras: カメラのリスト。

    Returns:
        go.Scatter3d トレースのリスト。
        cameras が空の場合は空リスト（要素数0）。
        cameras が1台以上の場合は要素数2（位置マーカー + 方向線）。
    """
    if len(cameras) == 0:
        return []

    # カメラ位置マーカー
    positions = [cam.position for cam in cameras]
    x = [float(p[0]) for p in positions]
    y = [float(p[1]) for p in positions]
    z = [float(p[2]) for p in positions]
    text = [f"C{i + 1}" for i in range(len(cameras))]

    marker_trace = go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="markers+text",
        marker=dict(
            size=CAMERA_MARKER_SIZE,
            color=CAMERA_MARKER_COLOR,
            symbol=CAMERA_MARKER_SYMBOL,
        ),
        text=text,
        textposition="top center",
        name="Cameras",
        showlegend=True,
    )

    # 方向線
    xs: list[float | None] = []
    ys: list[float | None] = []
    zs: list[float | None] = []
    for cam in cameras:
        start = cam.position
        end = cam.position + CAMERA_DIRECTION_LENGTH * cam.forward
        xs.extend([float(start[0]), float(end[0]), None])
        ys.extend([float(start[1]), float(end[1]), None])
        zs.extend([float(start[2]), float(end[2]), None])

    direction_trace = go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode="lines",
        line=dict(color=CAMERA_MARKER_COLOR, width=CAMERA_DIRECTION_WIDTH),
        name="Camera Direction",
        showlegend=True,
    )

    return [marker_trace, direction_trace]


def create_frustum_traces(
    cameras: list[Camera],
    near: float = 0.1,
    far: float = 3.0,
) -> list[go.Scatter3d]:
    """視錐台ワイヤフレームトレースを生成する。

    Args:
        cameras: カメラのリスト。
        near: ニアクリップ距離 [m]。
        far: 表示用ファークリップ距離 [m]。

    Returns:
        go.Scatter3d トレースのリスト（カメラ1台につき1トレース）。
        cameras が空の場合は空リスト（要素数0）。

    Raises:
        ValueError: far <= 0 の場合。
        ValueError: near < 0 の場合（FrustumChecker.__post_init__ に委譲）。
        ValueError: far <= near の場合（FrustumChecker.__post_init__ に委譲）。
    """
    if far <= 0:
        raise ValueError(f"far must be > 0, got {far}")

    if len(cameras) == 0:
        return []

    traces: list[go.Scatter3d] = []
    for i, cam in enumerate(cameras):
        checker = FrustumChecker(camera=cam, near=near, far=far)
        corners = checker.get_frustum_corners()
        xs, ys, zs = _frustum_wireframe_coords(corners)

        color = CAMERA_COLORS[i % len(CAMERA_COLORS)]
        trace = go.Scatter3d(
            x=xs,
            y=ys,
            z=zs,
            mode="lines",
            line=dict(color=color, width=FRUSTUM_LINE_WIDTH),
            name=f"Frustum C{i + 1}",
            legendgroup="frustums",
            showlegend=True,
        )
        traces.append(trace)

    return traces


def create_coverage_traces(
    grid_points: np.ndarray,
    visible_counts: np.ndarray,
    num_cameras: int = 6,
) -> list[go.Scatter3d]:
    """カバレッジマップトレースを生成する。

    Args:
        grid_points: グリッド点群。shape (N, 3)。
        visible_counts: 各点の視認カメラ数。shape (N,)。
        num_cameras: カラースケールの上限値（cmax）。

    Returns:
        go.Scatter3d トレースのリスト（要素数1）。
        N=0 の場合もリスト要素数は1（データなしの Scatter3d）。
    """
    if len(grid_points) == 0:
        trace = go.Scatter3d(
            x=[],
            y=[],
            z=[],
            mode="markers",
            marker=dict(size=COVERAGE_MARKER_SIZE),
            name="Coverage",
            showlegend=True,
        )
        return [trace]

    trace = go.Scatter3d(
        x=grid_points[:, 0],
        y=grid_points[:, 1],
        z=grid_points[:, 2],
        mode="markers",
        marker=dict(
            size=COVERAGE_MARKER_SIZE,
            color=visible_counts,
            colorscale=COVERAGE_COLORSCALE,
            cmin=0,
            cmax=num_cameras,
            colorbar=dict(title="Visible Cameras"),
        ),
        name="Coverage",
        showlegend=True,
    )
    return [trace]


def create_scene(
    room: Room,
    cameras: list[Camera],
    coverage_result: CoverageResult | None = None,
    show_frustums: bool = True,
    show_grid: bool = True,
    frustum_far: float = 3.0,
    title: str = "Camera Placement Visualization",
) -> go.Figure:
    """3Dインタラクティブシーンを生成する。

    Args:
        room: 病室モデル。
        cameras: カメラのリスト。
        coverage_result: F07 のカバレッジ計算結果。None の場合はカバレッジマップを表示しない。
        show_frustums: True の場合、視錐台を表示する。
        show_grid: True の場合かつ coverage_result が非 None の場合、カバレッジマップを表示する。
        frustum_far: 視錐台の表示用ファークリップ距離 [m]。
        title: 図のタイトル。

    Returns:
        go.Figure インスタンス。

    Raises:
        ValueError: frustum_far <= 0 の場合。
    """
    if frustum_far <= 0:
        raise ValueError(f"frustum_far must be > 0, got {frustum_far}")

    traces: list[go.Scatter3d | go.Mesh3d] = []

    traces.extend(create_room_traces(room))
    traces.extend(create_bed_traces(room))
    traces.extend(create_camera_traces(cameras))

    if show_frustums and len(cameras) > 0:
        traces.extend(create_frustum_traces(cameras, near=0.1, far=frustum_far))

    if show_grid and coverage_result is not None:
        traces.extend(create_coverage_traces(
            coverage_result.merged_grid,
            coverage_result.stats.visible_counts,
            coverage_result.stats.num_cameras,
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="X [m]",
            yaxis_title="Y [m]",
            zaxis_title="Z [m]",
            aspectmode="data",
        ),
        width=FIGURE_WIDTH,
        height=FIGURE_HEIGHT,
    )

    return fig


def save_html(fig: go.Figure, filepath: str | Path) -> Path:
    """plotly Figure を HTML ファイルに保存する。

    Args:
        fig: 保存する Figure。
        filepath: 保存先のファイルパス。

    Returns:
        保存先の Path オブジェクト。
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(path), include_plotlyjs=True)
    return path
