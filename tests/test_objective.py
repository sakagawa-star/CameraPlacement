"""F14: 目的関数定義のテスト。"""

import numpy as np
import pytest

from camera_placement.evaluation.evaluator import EvaluationResult
from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera
from camera_placement.models.environment import AABB, Room, create_default_room
from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    calculate_position_penalty,
    cameras_to_params,
    get_parameter_bounds,
    params_to_cameras,
)


# ---------- Fixtures ----------


@pytest.fixture
def room() -> Room:
    return create_default_room()


@pytest.fixture
def objective(room: Room) -> ObjectiveFunction:
    return ObjectiveFunction(room, grid_spacing=0.5)  # テスト用に粗いグリッド


# ---------- Helpers ----------


def _corner_params() -> np.ndarray:
    """テスト用コーナー配置のパラメータベクトル。"""
    target = [1.4, 1.75, 0.9]
    cameras_data = [
        [0.2, 0.2, 2.3] + target,
        [2.6, 0.2, 2.3] + target,
        [0.2, 3.3, 2.3] + target,
        [2.6, 3.3, 2.3] + target,
        [1.4, 0.2, 2.3] + target,
        [1.4, 3.3, 2.3] + target,
    ]
    return np.array([v for cam in cameras_data for v in cam], dtype=np.float64)


def _out_of_zone_params() -> np.ndarray:
    """テスト用の範囲外パラメータベクトル。

    1台目のカメラ位置 x を 0.0 に設定（camera_zone 下限 0.2 を下回る）。
    """
    params = _corner_params()
    params[0] = 0.0  # x = 0.0 < 0.2
    return params


# ========== カテゴリA: params_to_cameras / cameras_to_params ==========


class TestParamsConversion:
    """A: パラメータ変換のテスト。"""

    def test_a1_roundtrip(self) -> None:
        """A1: 往復変換で元の params と一致する。"""
        params = _corner_params()
        cameras = params_to_cameras(params)
        roundtrip = cameras_to_params(cameras)
        np.testing.assert_allclose(roundtrip, params, atol=1e-10)

    def test_a2_camera_position(self) -> None:
        """A2: カメラ位置が params の最初の3要素と一致する。"""
        params = _corner_params()
        cameras = params_to_cameras(params)
        np.testing.assert_allclose(cameras[0].position, params[0:3], atol=1e-10)

    def test_a3_camera_look_at(self) -> None:
        """A3: 注視点が params の次の3要素と一致する。"""
        params = _corner_params()
        cameras = params_to_cameras(params)
        np.testing.assert_allclose(cameras[0].look_at, params[3:6], atol=1e-10)

    def test_a4_six_cameras(self) -> None:
        """A4: 6台の Camera が生成される。"""
        params = _corner_params()
        cameras = params_to_cameras(params)
        assert len(cameras) == 6

    def test_a5_invalid_shape(self) -> None:
        """A5: shape 不正で ValueError。"""
        params = np.zeros(35, dtype=np.float64)
        with pytest.raises(ValueError):
            params_to_cameras(params)

    def test_a6_num_cameras_one(self) -> None:
        """A6: num_cameras=1 で1台生成。"""
        params = np.array([0.2, 0.2, 2.3, 1.4, 1.75, 0.9], dtype=np.float64)
        cameras = params_to_cameras(params, num_cameras=1)
        assert len(cameras) == 1

    def test_a7_position_equals_look_at(self) -> None:
        """A7: position == look_at で ValueError。"""
        params = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        with pytest.raises(ValueError):
            params_to_cameras(params, num_cameras=1)

    def test_a8_empty_cameras(self) -> None:
        """A8: 空リストで ValueError。"""
        with pytest.raises(ValueError):
            cameras_to_params([])

    def test_a9_custom_intrinsics(self) -> None:
        """A9: カスタム intrinsics が伝播する。"""
        params = np.array([0.2, 0.2, 2.3, 1.4, 1.75, 0.9], dtype=np.float64)
        custom = CameraIntrinsics(focal_length=5.0)
        cameras = params_to_cameras(params, num_cameras=1, intrinsics=custom)
        assert cameras[0].intrinsics.focal_length == 5.0

    def test_a10_num_cameras_zero(self) -> None:
        """A10: num_cameras=0 で ValueError。"""
        with pytest.raises(ValueError):
            params_to_cameras(np.array([]), num_cameras=0)


# ========== カテゴリB: get_parameter_bounds ==========


class TestParameterBounds:
    """B: パラメータ境界のテスト。"""

    def test_b1_shape(self, room: Room) -> None:
        """B1: bounds の shape が (36, 2)。"""
        bounds = get_parameter_bounds(room)
        assert bounds.shape == (36, 2)

    def test_b2_position_x_lower(self, room: Room) -> None:
        """B2: 位置 x 下限が 0.2。"""
        bounds = get_parameter_bounds(room)
        assert bounds[0, 0] == pytest.approx(0.2)

    def test_b3_position_x_upper(self, room: Room) -> None:
        """B3: 位置 x 上限が 2.6。"""
        bounds = get_parameter_bounds(room)
        assert bounds[0, 1] == pytest.approx(2.6)

    def test_b4_position_y_bounds(self, room: Room) -> None:
        """B4: 位置 y のバウンド。"""
        bounds = get_parameter_bounds(room)
        assert bounds[1, 0] == pytest.approx(0.2)
        assert bounds[1, 1] == pytest.approx(3.3)

    def test_b5_position_z_bounds(self, room: Room) -> None:
        """B5: 位置 z のバウンド。"""
        bounds = get_parameter_bounds(room)
        assert bounds[2, 0] == pytest.approx(0.2)
        assert bounds[2, 1] == pytest.approx(2.3)

    def test_b6_look_at_x_bounds(self, room: Room) -> None:
        """B6: 注視点 x のバウンド。"""
        bounds = get_parameter_bounds(room)
        assert bounds[3, 0] == pytest.approx(0.0)
        assert bounds[3, 1] == pytest.approx(2.8)

    def test_b7_look_at_y_bounds(self, room: Room) -> None:
        """B7: 注視点 y のバウンド。"""
        bounds = get_parameter_bounds(room)
        assert bounds[4, 0] == pytest.approx(0.0)
        assert bounds[4, 1] == pytest.approx(3.5)

    def test_b8_look_at_z_bounds(self, room: Room) -> None:
        """B8: 注視点 z のバウンド。"""
        bounds = get_parameter_bounds(room)
        assert bounds[5, 0] == pytest.approx(0.0)
        assert bounds[5, 1] == pytest.approx(2.5)

    def test_b9_all_cameras_same_bounds(self, room: Room) -> None:
        """B9: 全カメラが同一バウンド。"""
        bounds = get_parameter_bounds(room)
        for i in range(1, 6):
            np.testing.assert_array_equal(bounds[0:6], bounds[i * 6 : (i + 1) * 6])

    def test_b10_num_cameras_one(self, room: Room) -> None:
        """B10: num_cameras=1 で shape (6, 2)。"""
        bounds = get_parameter_bounds(room, num_cameras=1)
        assert bounds.shape == (6, 2)

    def test_b11_num_cameras_zero(self, room: Room) -> None:
        """B11: num_cameras=0 で ValueError。"""
        with pytest.raises(ValueError):
            get_parameter_bounds(room, num_cameras=0)


# ========== カテゴリC: calculate_position_penalty ==========


class TestPositionPenalty:
    """C: 設置領域制約ペナルティのテスト。"""

    @pytest.fixture
    def camera_zone(self) -> AABB:
        return AABB(
            min_point=np.array([0.2, 0.2, 0.2]),
            max_point=np.array([2.6, 3.3, 2.3]),
        )

    def test_c1_all_inside(self, camera_zone: AABB) -> None:
        """C1: 全カメラ範囲内 → 0.0。"""
        positions = np.array([
            [0.5, 0.5, 1.0],
            [1.0, 1.0, 1.0],
            [2.0, 2.0, 2.0],
            [0.2, 0.2, 0.2],
            [2.6, 3.3, 2.3],
            [1.4, 1.75, 1.25],
        ])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.0)

    def test_c2_x_lower_violation(self, camera_zone: AABB) -> None:
        """C2: x 下限逸脱 0.1m → 0.01。"""
        positions = np.array([[0.1, 0.2, 2.3]])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.01)

    def test_c3_x_upper_violation(self, camera_zone: AABB) -> None:
        """C3: x 上限逸脱 0.1m → 0.01。"""
        positions = np.array([[2.7, 0.2, 2.3]])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.01)

    def test_c4_multi_dimension_violation(self, camera_zone: AABB) -> None:
        """C4: 複数次元逸脱 → 0.03。"""
        # x, y, z それぞれ 0.1m 逸脱
        positions = np.array([[0.1, 0.1, 0.1]])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.03)

    def test_c5_multi_camera_violation(self, camera_zone: AABB) -> None:
        """C5: 複数カメラ逸脱 → 0.02。"""
        positions = np.array([
            [0.1, 0.2, 2.3],  # x 0.1m 逸脱
            [2.7, 0.2, 2.3],  # x 0.1m 逸脱
        ])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.02)

    def test_c6_large_violation(self, camera_zone: AABB) -> None:
        """C6: 大きな逸脱 → 1.44。"""
        # x = -1.0, zone_min_x = 0.2, 差 = 1.2
        positions = np.array([[-1.0, 0.2, 2.3]])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(1.44)

    def test_c7_boundary_position(self, camera_zone: AABB) -> None:
        """C7: 境界上の位置 → 0.0。"""
        positions = np.array([
            [0.2, 0.2, 0.2],
            [2.6, 3.3, 2.3],
        ])
        penalty = calculate_position_penalty(positions, camera_zone)
        assert penalty == pytest.approx(0.0)


# ========== カテゴリD: ObjectiveFunction の基本動作 ==========


class TestObjectiveFunctionBasic:
    """D: 目的関数の基本動作テスト。"""

    def test_d1_corner_value_range(self, objective: ObjectiveFunction) -> None:
        """D1: コーナー配置の目的関数値が [-1.0, 0.0] の範囲内。"""
        params = _corner_params()
        value = objective(params)
        assert -1.0 <= value <= 0.0

    def test_d2_value_consistency(self, objective: ObjectiveFunction) -> None:
        """D2: value == -quality_score + penalty。"""
        params = _corner_params()
        result = objective.evaluate_detail(params)
        expected = -result.quality_score + result.penalty
        assert result.value == pytest.approx(expected, abs=1e-10)

    def test_d3_is_feasible(self, objective: ObjectiveFunction) -> None:
        """D3: コーナー配置で is_feasible = True。"""
        params = _corner_params()
        result = objective.evaluate_detail(params)
        assert result.is_feasible is True

    def test_d4_evaluation_not_none(self, objective: ObjectiveFunction) -> None:
        """D4: コーナー配置で evaluation が非 None。"""
        params = _corner_params()
        result = objective.evaluate_detail(params)
        assert result.evaluation is not None

    def test_d5_evaluation_type(self, objective: ObjectiveFunction) -> None:
        """D5: evaluation が EvaluationResult 型。"""
        params = _corner_params()
        result = objective.evaluate_detail(params)
        assert isinstance(result.evaluation, EvaluationResult)

    def test_d6_call_equals_evaluate_detail(
        self, objective: ObjectiveFunction
    ) -> None:
        """D6: __call__ と evaluate_detail の value が一致。"""
        params = _corner_params()
        call_value = objective(params)
        detail_value = objective.evaluate_detail(params).value
        assert call_value == detail_value

    def test_d7_bounds_shape(self, objective: ObjectiveFunction) -> None:
        """D7: bounds の shape が (36, 2)。"""
        assert objective.bounds.shape == (36, 2)

    def test_d8_n_params(self, objective: ObjectiveFunction) -> None:
        """D8: n_params が 36。"""
        assert objective.n_params == 36


# ========== カテゴリE: ペナルティ ==========


class TestPenalty:
    """E: ペナルティのテスト。"""

    def test_e1_inside_no_penalty(self, objective: ObjectiveFunction) -> None:
        """E1: 範囲内 → penalty=0。"""
        params = _corner_params()
        result = objective.evaluate_detail(params)
        assert result.penalty == pytest.approx(0.0)

    def test_e2_outside_positive_penalty(
        self, objective: ObjectiveFunction
    ) -> None:
        """E2: 範囲外 → penalty > 0。"""
        params = _out_of_zone_params()
        result = objective.evaluate_detail(params)
        assert result.penalty > 0

    def test_e3_outside_worse_value(self, objective: ObjectiveFunction) -> None:
        """E3: 範囲外の方が目的関数値が大きい。"""
        inside_value = objective(_corner_params())
        outside_value = objective(_out_of_zone_params())
        assert inside_value < outside_value

    def test_e4_position_equals_look_at(self, room: Room) -> None:
        """E4: position == look_at → is_feasible=False, value > 0。"""
        obj = ObjectiveFunction(room, grid_spacing=0.5, num_cameras=1)
        params = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        result = obj.evaluate_detail(params)
        assert result.is_feasible is False
        assert result.value > 0

    def test_e5_penalty_weight_effect(self, room: Room) -> None:
        """E5: penalty_weight の影響。"""
        params = _out_of_zone_params()
        obj10 = ObjectiveFunction(room, grid_spacing=0.5, penalty_weight=10.0)
        obj100 = ObjectiveFunction(room, grid_spacing=0.5, penalty_weight=100.0)
        result10 = obj10.evaluate_detail(params)
        result100 = obj100.evaluate_detail(params)
        # penalty_weight が 10 倍なら penalty も約 10 倍
        assert result100.penalty == pytest.approx(result10.penalty * 10.0, rel=1e-10)

    def test_e6_invalid_camera_value_ge_one(self, room: Room) -> None:
        """E6: 不正カメラの value >= 1.0。"""
        obj = ObjectiveFunction(room, grid_spacing=0.5, num_cameras=1)
        # position == look_at
        params = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        result = obj.evaluate_detail(params)
        assert result.value >= 1.0


# ========== カテゴリF: エッジケース ==========


class TestEdgeCases:
    """F: エッジケースのテスト。"""

    def test_f1_num_cameras_one(self, room: Room) -> None:
        """F1: num_cameras=1 で正常動作。"""
        obj = ObjectiveFunction(room, grid_spacing=0.5, num_cameras=1)
        params = np.array([1.4, 1.75, 2.3, 1.4, 1.75, 0.9], dtype=np.float64)
        value = obj(params)
        assert isinstance(value, float)
        assert np.isfinite(value)

    def test_f2_num_cameras_zero(self, room: Room) -> None:
        """F2: num_cameras=0 で ValueError。"""
        with pytest.raises(ValueError):
            ObjectiveFunction(room, num_cameras=0)

    def test_f3_penalty_weight_zero(self, room: Room) -> None:
        """F3: penalty_weight=0.0 → 範囲外でも pos_penalty=0。"""
        obj = ObjectiveFunction(room, grid_spacing=0.5, penalty_weight=0.0)
        params = _out_of_zone_params()
        result = obj.evaluate_detail(params)
        # penalty_weight=0 なので位置ペナルティは 0
        # ただし is_feasible は False（位置が範囲外のため）
        assert result.penalty == pytest.approx(0.0)

    def test_f4_penalty_weight_negative(self, room: Room) -> None:
        """F4: penalty_weight < 0 で ValueError。"""
        with pytest.raises(ValueError):
            ObjectiveFunction(room, penalty_weight=-1.0)

    def test_f5_no_exception_on_invalid_camera(self, room: Room) -> None:
        """F5: __call__ は shape 以外の例外を送出しない。"""
        obj = ObjectiveFunction(room, grid_spacing=0.5, num_cameras=1)
        # position == look_at（不正）
        params = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        value = obj(params)  # ValueError は送出されない
        assert isinstance(value, float)
        assert np.isfinite(value)

    def test_f6_invalid_shape_raises(self, objective: ObjectiveFunction) -> None:
        """F6: params の shape 不正で ValueError。"""
        params = np.zeros(35, dtype=np.float64)
        with pytest.raises(ValueError):
            objective(params)


# ========== カテゴリG: 統合テスト ==========


class TestIntegration:
    """G: 統合テスト。"""

    def test_g1_corner_vs_clustered(self, objective: ObjectiveFunction) -> None:
        """G1: コーナー配置 vs 密集配置。"""
        corner_params = _corner_params()
        corner_value = objective(corner_params)

        # 密集配置（同一壁面に集中）
        target = [1.4, 1.75, 0.9]
        clustered_data = [
            [0.2, 0.2, 2.3] + target,
            [0.4, 0.2, 2.3] + target,
            [0.6, 0.2, 2.3] + target,
            [0.8, 0.2, 2.3] + target,
            [1.0, 0.2, 2.3] + target,
            [1.2, 0.2, 2.3] + target,
        ]
        clustered_params = np.array(
            [v for cam in clustered_data for v in cam], dtype=np.float64
        )
        clustered_value = objective(clustered_params)

        # コーナー配置の方が良い（value が小さい）
        assert corner_value < clustered_value

    def test_g2_preset_conversion(self, room: Room) -> None:
        """G2: プリセットからの変換往復。"""
        from camera_placement.placement.patterns import create_cameras, get_preset

        preset = get_preset("upper_corners")
        preset_cameras = create_cameras(preset, room)
        params = cameras_to_params(preset_cameras)
        restored_cameras = params_to_cameras(params)

        for orig, restored in zip(preset_cameras, restored_cameras):
            np.testing.assert_allclose(
                restored.position, orig.position, atol=1e-10
            )
            np.testing.assert_allclose(
                restored.look_at, orig.look_at, atol=1e-10
            )
