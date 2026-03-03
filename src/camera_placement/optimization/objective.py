"""F14: 目的関数定義。

最適化アルゴリズム（F15）が使用する目的関数を定義する。
6台のカメラの配置パラメータ（位置・注視点）を36次元のベクトルとして表現し、
品質スコアの最大化（目的関数値の最小化）と設置領域制約のペナルティを統合した
目的関数を提供する。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from camera_placement.evaluation.evaluator import EvaluationResult, evaluate_placement
from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera
from camera_placement.models.environment import AABB, Room


@dataclass
class ObjectiveResult:
    """目的関数の詳細な評価結果。

    Attributes:
        value: 目的関数値（最小化対象）。-quality_score + penalty。
        quality_score: F10 品質スコア [0.0, 1.0]。不正な場合は 0.0。
        penalty: ペナルティ値合計（penalty_weight 適用済み + infeasible_penalty）。0.0 以上。
        is_feasible: 全制約を満たし、有効なカメラ構成の場合 True。
        evaluation: F10 の評価結果。不正な場合は None。
    """

    value: float
    quality_score: float
    penalty: float
    is_feasible: bool
    evaluation: EvaluationResult | None


def params_to_cameras(
    params: np.ndarray,
    num_cameras: int = 6,
    intrinsics: CameraIntrinsics | None = None,
) -> list[Camera]:
    """パラメータベクトルから Camera リストを生成する。

    Args:
        params: パラメータベクトル。shape (num_cameras * 6,)。
            params[i*6 : i*6+3] がカメラ i の位置 (x, y, z)。
            params[i*6+3 : i*6+6] がカメラ i の注視点 (lx, ly, lz)。
        num_cameras: カメラ台数。1 以上。
        intrinsics: カメラ内部パラメータ。None の場合はデフォルト。

    Returns:
        Camera のリスト（num_cameras 個）。

    Raises:
        ValueError: num_cameras が 0 以下の場合。
        ValueError: params の shape が (num_cameras * 6,) でない場合。
        ValueError: position == look_at の場合（Camera.__post_init__ による）。
        ValueError: forward // up_hint の場合（Camera.__post_init__ による）。
    """
    if num_cameras <= 0:
        raise ValueError("num_cameras must be positive")

    params = np.asarray(params, dtype=np.float64)
    expected_shape = (num_cameras * 6,)
    if params.shape != expected_shape:
        raise ValueError(
            f"params must have shape {expected_shape}, got {params.shape}"
        )

    reshaped = params.reshape(num_cameras, 6)
    cameras: list[Camera] = []
    for i in range(num_cameras):
        position = reshaped[i, 0:3]
        look_at = reshaped[i, 3:6]
        cam = create_camera(
            position=position,
            look_at=look_at,
            intrinsics=intrinsics,
        )
        cameras.append(cam)

    return cameras


def cameras_to_params(cameras: list[Camera]) -> np.ndarray:
    """Camera リストからパラメータベクトルを生成する。

    Args:
        cameras: Camera のリスト。1台以上。

    Returns:
        パラメータベクトル。shape (len(cameras) * 6,), dtype=float64。

    Raises:
        ValueError: cameras が空リストの場合。
    """
    if len(cameras) == 0:
        raise ValueError("cameras must not be empty")

    params = np.zeros(len(cameras) * 6, dtype=np.float64)
    for i, cam in enumerate(cameras):
        params[i * 6 : i * 6 + 3] = cam.position
        params[i * 6 + 3 : i * 6 + 6] = cam.look_at

    return params


def get_parameter_bounds(
    room: Room,
    num_cameras: int = 6,
) -> np.ndarray:
    """パラメータの探索範囲（上下限）を取得する。

    Args:
        room: 病室モデル。
        num_cameras: カメラ台数。1 以上。

    Returns:
        shape (num_cameras * 6, 2) の配列。[:,0] が下限、[:,1] が上限。

    Raises:
        ValueError: num_cameras が 0 以下の場合。
    """
    if num_cameras <= 0:
        raise ValueError("num_cameras must be positive")

    single_bounds = np.array([
        [room.camera_zone.min_point[0], room.camera_zone.max_point[0]],  # x
        [room.camera_zone.min_point[1], room.camera_zone.max_point[1]],  # y
        [room.camera_zone.min_point[2], room.camera_zone.max_point[2]],  # z
        [0.0, room.width],   # lx
        [0.0, room.depth],   # ly
        [0.0, room.height],  # lz
    ])  # shape (6, 2)

    bounds = np.tile(single_bounds, (num_cameras, 1))
    # shape (num_cameras * 6, 2)

    return bounds


def calculate_position_penalty(
    positions: np.ndarray,
    camera_zone: AABB,
) -> float:
    """カメラ位置の設置領域制約ペナルティを計算する。

    各カメラ位置が camera_zone から逸脱している量の二乗和を返す。
    ペナルティ係数は適用しない（呼び出し元が掛ける）。

    Args:
        positions: カメラ位置。shape (M, 3)。
        camera_zone: カメラ設置可能領域。

    Returns:
        ペナルティ値。0.0 以上。全カメラが範囲内なら 0.0。
    """
    positions = np.asarray(positions, dtype=np.float64)
    # 下限からの逸脱（zone_min より小さい場合に正）
    lower_violation = np.maximum(0.0, camera_zone.min_point - positions)
    # 上限からの逸脱（zone_max より大きい場合に正）
    upper_violation = np.maximum(0.0, positions - camera_zone.max_point)

    penalty = float(np.sum(lower_violation**2) + np.sum(upper_violation**2))
    return penalty


class ObjectiveFunction:
    """最適化用の目的関数。

    パラメータベクトル（num_cameras * 6 次元）からカメラ配置を評価し、
    最小化すべきスカラー値を返す。

    目的関数値 = -quality_score + penalty_weight * position_penalty + infeasible_penalty
    """

    def __init__(
        self,
        room: Room,
        grid_spacing: float = 0.2,
        near: float = 0.1,
        far: float = 10.0,
        target_ppm: float = 500.0,
        weight_coverage: float = 0.5,
        weight_angle: float = 0.3,
        weight_projection: float = 0.2,
        penalty_weight: float = 100.0,
        num_cameras: int = 6,
    ) -> None:
        """目的関数を初期化する。

        Args:
            room: 病室モデル。
            grid_spacing: グリッド間隔 [m]。
            near: ニアクリップ距離 [m]。
            far: ファークリップ距離 [m]。
            target_ppm: 目標投影解像度 [px/m]。
            weight_coverage: カバレッジの重み。
            weight_angle: 角度スコアの重み。
            weight_projection: 投影スコアの重み。
            penalty_weight: ペナルティ係数。0.0 以上。
            num_cameras: カメラ台数。1 以上。

        Raises:
            ValueError: num_cameras が 0 以下の場合。
            ValueError: penalty_weight が負の場合。
            ValueError: weight_coverage, weight_angle, weight_projection のいずれかが負の場合。
            ValueError: weight_coverage + weight_angle + weight_projection が 0 の場合。
        """
        if num_cameras <= 0:
            raise ValueError("num_cameras must be positive")
        if penalty_weight < 0:
            raise ValueError("penalty_weight must be non-negative")
        if weight_coverage < 0 or weight_angle < 0 or weight_projection < 0:
            raise ValueError("weights must be non-negative")
        if weight_coverage + weight_angle + weight_projection == 0:
            raise ValueError("sum of weights must be positive")

        self._room = room
        self._grid_spacing = grid_spacing
        self._near = near
        self._far = far
        self._target_ppm = target_ppm
        self._weight_coverage = weight_coverage
        self._weight_angle = weight_angle
        self._weight_projection = weight_projection
        self._penalty_weight = penalty_weight
        self._num_cameras = num_cameras
        self._bounds = get_parameter_bounds(room, num_cameras)

    @property
    def bounds(self) -> np.ndarray:
        """パラメータの上下限。

        Returns:
            shape (n_params, 2)。[:,0] が下限、[:,1] が上限。
        """
        return self._bounds

    @property
    def n_params(self) -> int:
        """パラメータ数。num_cameras * 6。"""
        return self._num_cameras * 6

    def __call__(self, params: np.ndarray) -> float:
        """目的関数を評価する。

        Args:
            params: パラメータベクトル。shape (n_params,)。

        Returns:
            目的関数値。最小化対象のスカラー値。
            実行可能解: [-1.0, 0.0]、非実行可能解: 正の値。

        Raises:
            ValueError: params の shape が (n_params,) でない場合。
        """
        result = self.evaluate_detail(params)
        return result.value

    def evaluate_detail(self, params: np.ndarray) -> ObjectiveResult:
        """目的関数を評価し、詳細結果を返す。

        Args:
            params: パラメータベクトル。shape (n_params,)。

        Returns:
            ObjectiveResult インスタンス。

        Raises:
            ValueError: params の shape が (n_params,) でない場合。
        """
        # Step 1: params の shape 検証
        params = np.asarray(params, dtype=np.float64)
        expected_shape = (self.n_params,)
        if params.shape != expected_shape:
            raise ValueError(
                f"params must have shape {expected_shape}, got {params.shape}"
            )

        # Step 2: カメラ位置の抽出と制約ペナルティ計算
        reshaped = params.reshape(self._num_cameras, 6)
        positions = reshaped[:, 0:3]  # shape (num_cameras, 3)
        pos_penalty_raw = calculate_position_penalty(positions, self._room.camera_zone)
        pos_penalty = self._penalty_weight * pos_penalty_raw

        # Step 3: Camera オブジェクトの生成
        try:
            cameras = params_to_cameras(params, self._num_cameras)
        except Exception:
            infeasible_penalty = 1.0
            total_penalty = pos_penalty + infeasible_penalty
            return ObjectiveResult(
                value=total_penalty,
                quality_score=0.0,
                penalty=total_penalty,
                is_feasible=False,
                evaluation=None,
            )

        # Step 4: F10 で品質スコアを計算
        try:
            evaluation = evaluate_placement(
                cameras,
                self._room,
                grid_spacing=self._grid_spacing,
                near=self._near,
                far=self._far,
                target_ppm=self._target_ppm,
                weight_coverage=self._weight_coverage,
                weight_angle=self._weight_angle,
                weight_projection=self._weight_projection,
            )
            quality_score = evaluation.quality.quality_score
        except Exception:
            infeasible_penalty = 1.0
            total_penalty = pos_penalty + infeasible_penalty
            return ObjectiveResult(
                value=total_penalty,
                quality_score=0.0,
                penalty=total_penalty,
                is_feasible=False,
                evaluation=None,
            )

        # Step 5: 実行可能性の判定
        is_feasible = pos_penalty_raw == 0.0

        # Step 6: 目的関数値の計算
        value = -quality_score + pos_penalty

        # Step 7: 結果を返す
        return ObjectiveResult(
            value=value,
            quality_score=quality_score,
            penalty=pos_penalty,
            is_feasible=is_feasible,
            evaluation=evaluation,
        )
