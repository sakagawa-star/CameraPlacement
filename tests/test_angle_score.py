"""F08: 三角測量角度スコアのテスト。"""

import numpy as np
import pytest

from camera_placement.evaluation.angle_score import (
    AngleScoreResult,
    calculate_angle_score,
    calculate_pair_angles,
)
from camera_placement.models.camera import Camera, create_camera


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


def _create_clustered_cameras() -> list[Camera]:
    """テスト用密集配置カメラ（同一壁面に集中）。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([0.4, 0.2, 2.3], center),
        create_camera([0.6, 0.2, 2.3], center),
        create_camera([0.8, 0.2, 2.3], center),
        create_camera([1.0, 0.2, 2.3], center),
        create_camera([1.2, 0.2, 2.3], center),
    ]


# ===========================================================================
# カテゴリA: calculate_pair_angles（低レベル関数）
# ===========================================================================

class TestCalculatePairAngles:
    """calculate_pair_angles のテスト。"""

    def test_a1_90_degree_separation(self) -> None:
        """A1: 90° 角度分離。"""
        cam_a = np.array([1.0, 0.0, 0.0])
        cam_b = np.array([0.0, 1.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (1,)
        np.testing.assert_allclose(angles[0], np.pi / 2, atol=1e-10)

    def test_a2_0_degree_separation(self) -> None:
        """A2: 0° 角度分離（同一方向）。"""
        cam_a = np.array([0.0, 0.0, 0.0])
        cam_b = np.array([1.0, 0.0, 0.0])
        points = np.array([[2.0, 0.0, 0.0]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (1,)
        np.testing.assert_allclose(angles[0], 0.0, atol=1e-10)

    def test_a3_180_degree_separation(self) -> None:
        """A3: 180° 角度分離（反対方向）。"""
        cam_a = np.array([1.0, 0.0, 0.0])
        cam_b = np.array([-1.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (1,)
        np.testing.assert_allclose(angles[0], np.pi, atol=1e-10)

    def test_a4_60_degree_separation(self) -> None:
        """A4: 60° 角度分離。"""
        cam_a = np.array([1.0, 0.0, 0.0])
        cam_b = np.array([0.5, np.sqrt(3) / 2, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (1,)
        np.testing.assert_allclose(angles[0], np.pi / 3, atol=1e-10)

    def test_a5_batch_calculation(self) -> None:
        """A5: バッチ計算（複数点）。"""
        cam_a = np.array([1.0, 0.0, 0.0])
        cam_b = np.array([0.0, 1.0, 0.0])
        points = np.array([
            [0.0, 0.0, 0.0],  # 90°
            [2.0, 0.0, 0.0],  # cam_a方向寄り
            [0.0, 2.0, 0.0],  # cam_b方向寄り
        ])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (3,)
        # 点1: 90°
        np.testing.assert_allclose(angles[0], np.pi / 2, atol=1e-10)
        # 各点の角度が独立に計算されることを検証
        for i in range(3):
            single = calculate_pair_angles(
                cam_a, cam_b, points[i : i + 1]
            )
            np.testing.assert_allclose(angles[i], single[0], atol=1e-10)

    def test_a6_camera_at_point(self) -> None:
        """A6: カメラが点と同一位置（ゼロ除算防止）。"""
        cam_a = np.array([0.0, 0.0, 0.0])
        cam_b = np.array([1.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        assert angles.shape == (1,)
        assert angles[0] == 0.0

    def test_a7_3d_angle(self) -> None:
        """A7: 3D空間の角度。"""
        cam_a = np.array([0.0, 0.0, 0.0])
        cam_b = np.array([0.0, 0.0, 1.0])
        points = np.array([[1.0, 0.0, 0.5]])

        angles = calculate_pair_angles(cam_a, cam_b, points)

        # 手動計算
        v_a = np.array([1.0, 0.0, 0.5])
        v_b = np.array([1.0, 0.0, -0.5])
        cos_val = np.dot(v_a, v_b) / (np.linalg.norm(v_a) * np.linalg.norm(v_b))
        expected = np.arccos(cos_val)

        assert angles.shape == (1,)
        np.testing.assert_allclose(angles[0], expected, atol=1e-10)


# ===========================================================================
# カテゴリB: calculate_angle_score（メイン関数）
# ===========================================================================

class TestCalculateAngleScore:
    """calculate_angle_score のテスト。"""

    def test_b1_two_cameras_90_degree(self) -> None:
        """B1: 2台カメラ、90°配置、1点。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True]])

        result = calculate_angle_score([cam_a, cam_b], points, vis)

        assert isinstance(result, AngleScoreResult)
        np.testing.assert_allclose(result.point_best_scores[0], 1.0, atol=1e-10)
        np.testing.assert_allclose(result.point_best_angles[0], np.pi / 2, atol=1e-10)
        assert result.point_num_pairs[0] == 1
        np.testing.assert_allclose(result.mean_score, 1.0, atol=1e-10)

    def test_b2_two_cameras_same_direction(self) -> None:
        """B2: 2台カメラ、同一方向、1点。"""
        cam_a = create_camera([0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        cam_b = create_camera([1.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        points = np.array([[10.0, 0.0, 0.0]])
        vis = np.array([[True], [True]])

        result = calculate_angle_score([cam_a, cam_b], points, vis)

        np.testing.assert_allclose(result.point_best_scores[0], 0.0, atol=1e-6)

    def test_b3_three_cameras_all_visible(self) -> None:
        """B3: 3台カメラ、1点、全視認。"""
        cam_0 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_1 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        cam_2 = create_camera([-1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True], [True]])

        result = calculate_angle_score([cam_0, cam_1, cam_2], points, vis)

        # ペア(0,1): angle=π/2, score=1.0
        # ペア(0,2): angle=π, score=sin(π)≈0.0
        # ペア(1,2): angle=π/2, score=1.0
        assert result.point_num_pairs[0] == 3
        np.testing.assert_allclose(result.point_best_scores[0], 1.0, atol=1e-10)
        # mean_score = (1.0 + ~0.0 + 1.0) / 3
        np.testing.assert_allclose(
            result.point_mean_scores[0], 2.0 / 3.0, atol=1e-6
        )

    def test_b4_three_cameras_partial_visibility(self) -> None:
        """B4: 3台カメラ、1点、部分視認（2台のみ）。"""
        cam_0 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_1 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        cam_2 = create_camera([-1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        # cam_2 からは視認不可
        vis = np.array([[True], [True], [False]])

        result = calculate_angle_score([cam_0, cam_1, cam_2], points, vis)

        # 有効ペアは (0,1) のみ
        assert result.point_num_pairs[0] == 1
        np.testing.assert_allclose(result.point_best_scores[0], 1.0, atol=1e-10)

    def test_b5_multiple_points_different_scores(self) -> None:
        """B5: 複数点で異なるスコア。"""
        cam_0 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_1 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        cam_2 = create_camera([-1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([
            [0.0, 0.0, 0.0],  # 点0
            [0.5, 0.5, 0.0],  # 点1
        ])
        # 点0: cam_0, cam_1 のみ視認。点1: cam_1, cam_2 のみ視認
        vis = np.array([
            [True, False],   # cam_0
            [True, True],    # cam_1
            [False, True],   # cam_2
        ])

        result = calculate_angle_score([cam_0, cam_1, cam_2], points, vis)

        # 各点のスコアが独立に計算されていることを検証
        assert result.point_num_pairs[0] == 1  # (0,1)
        assert result.point_num_pairs[1] == 1  # (1,2)
        # 点0: ペア(0,1) の角度スコア
        # 点1: ペア(1,2) の角度スコア
        assert result.point_best_scores[0] > 0
        assert result.point_best_scores[1] > 0

    def test_b6_point_mean_scores(self) -> None:
        """B6: point_mean_scores の検証。"""
        cam_0 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_1 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        cam_2 = create_camera([-1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True], [True]])

        result = calculate_angle_score([cam_0, cam_1, cam_2], points, vis)

        # 3ペア: (0,1)=π/2→1.0, (0,2)=π→~0, (1,2)=π/2→1.0
        # mean = (1.0 + ~0 + 1.0) / 3 ≈ 0.667
        expected_mean = (np.sin(np.pi / 2) + np.sin(np.pi) + np.sin(np.pi / 2)) / 3
        np.testing.assert_allclose(
            result.point_mean_scores[0], expected_mean, atol=1e-6
        )

    def test_b7_mean_score(self) -> None:
        """B7: mean_score の検証（全体スコア = point_best_scoresの平均）。"""
        cam_0 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_1 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([
            [0.0, 0.0, 0.0],   # 90°
            [0.5, 0.5, 0.0],   # 異なる角度
            [2.0, 0.0, 0.0],   # cam_0 方向寄り
        ])
        vis = np.ones((2, 3), dtype=bool)

        result = calculate_angle_score([cam_0, cam_1], points, vis)

        expected_mean = float(result.point_best_scores.mean())
        np.testing.assert_allclose(result.mean_score, expected_mean, atol=1e-10)


# ===========================================================================
# カテゴリC: エッジケース
# ===========================================================================

class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_c1_no_cameras(self) -> None:
        """C1: カメラ0台。"""
        points = np.zeros((0, 3))
        vis = np.zeros((0, 0), dtype=bool)

        result = calculate_angle_score([], points, vis)

        assert result.mean_score == 0.0
        assert result.point_best_scores.shape == (0,)
        assert result.point_mean_scores.shape == (0,)
        assert result.point_best_angles.shape == (0,)
        assert result.point_num_pairs.shape == (0,)

    def test_c2_single_camera(self) -> None:
        """C2: カメラ1台（ペアなし）。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        vis = np.array([[True, True]])

        result = calculate_angle_score([cam], points, vis)

        assert result.mean_score == 0.0
        np.testing.assert_array_equal(result.point_best_scores, [0.0, 0.0])
        np.testing.assert_array_equal(result.point_num_pairs, [0, 0])

    def test_c3_no_grid_points(self) -> None:
        """C3: グリッド点0個。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.zeros((0, 3))
        vis = np.zeros((2, 0), dtype=bool)

        result = calculate_angle_score([cam_a, cam_b], points, vis)

        assert result.mean_score == 0.0
        assert result.point_best_scores.shape == (0,)

    def test_c4_all_points_single_camera_visibility(self) -> None:
        """C4: 全点が1台以下からのみ視認。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        # 各点は1台のみから視認
        vis = np.array([
            [True, False],
            [False, True],
        ])

        result = calculate_angle_score([cam_a, cam_b], points, vis)

        np.testing.assert_array_equal(result.point_best_scores, [0.0, 0.0])
        np.testing.assert_array_equal(result.point_num_pairs, [0, 0])

    def test_c5_grid_points_not_2d(self) -> None:
        """C5: grid_points が2Dでない場合にValueError。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([1.0, 2.0, 3.0])  # 1D
        vis = np.array([[True], [True]])

        with pytest.raises(ValueError, match="grid_points must be 2D"):
            calculate_angle_score([cam_a, cam_b], points, vis)

    def test_c6_grid_points_wrong_columns(self) -> None:
        """C6: grid_points.shape[1] != 3 の場合にValueError。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[1.0, 2.0]])  # shape (1, 2)
        vis = np.array([[True], [True]])

        with pytest.raises(ValueError, match="grid_points.shape\\[1\\] must be 3"):
            calculate_angle_score([cam_a, cam_b], points, vis)

    def test_c7_visibility_not_2d(self) -> None:
        """C7: visibility_matrix が2Dでない場合にValueError。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([True, True])  # 1D

        with pytest.raises(ValueError, match="visibility_matrix must be 2D"):
            calculate_angle_score([cam_a, cam_b], points, vis)

    def test_c8_shape0_mismatch(self) -> None:
        """C8: visibility_matrix.shape[0] != len(cameras)。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True], [True]])  # 3行だがカメラは2台

        with pytest.raises(ValueError, match="visibility_matrix.shape\\[0\\]"):
            calculate_angle_score([cam_a, cam_b], points, vis)

    def test_c9_shape1_mismatch(self) -> None:
        """C9: visibility_matrix.shape[1] != grid_points.shape[0]。"""
        cam_a = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_b = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True, True], [True, True]])  # 2列だが点は1つ

        with pytest.raises(ValueError, match="visibility_matrix.shape\\[1\\]"):
            calculate_angle_score([cam_a, cam_b], points, vis)


# ===========================================================================
# カテゴリD: 実環境シナリオ
# ===========================================================================

class TestRealWorldScenarios:
    """実環境シナリオのテスト。"""

    def test_d1_corner_placement(self) -> None:
        """D1: コーナー配置6台で正のスコア。"""
        cameras = _create_corner_cameras()
        # 小規模グリッド
        grid = np.array([
            [0.5, 0.5, 0.5],
            [1.4, 1.75, 0.5],
            [2.0, 1.0, 1.0],
            [1.0, 2.5, 0.3],
        ])
        # 全カメラから全点が視認可能と仮定
        vis = np.ones((6, 4), dtype=bool)

        result = calculate_angle_score(cameras, grid, vis)

        assert result.mean_score > 0.3
        assert result.point_best_scores.shape == (4,)
        assert np.all(result.point_best_scores > 0)

    def test_d2_clustered_placement_lower_score(self) -> None:
        """D2: 密集配置は角度分離が小さくスコアが低い。"""
        corner_cameras = _create_corner_cameras()
        clustered_cameras = _create_clustered_cameras()

        grid = np.array([
            [0.5, 0.5, 0.5],
            [1.4, 1.75, 0.5],
            [2.0, 1.0, 1.0],
            [1.0, 2.5, 0.3],
        ])
        vis = np.ones((6, 4), dtype=bool)

        corner_result = calculate_angle_score(corner_cameras, grid, vis)
        clustered_result = calculate_angle_score(clustered_cameras, grid, vis)

        assert corner_result.mean_score > clustered_result.mean_score

    def test_d3_f07_integration(self) -> None:
        """D3: F07結果との連携（calculate_coverage → calculate_angle_score）。"""
        from camera_placement.evaluation.coverage import calculate_coverage
        from camera_placement.models.environment import create_default_room

        cameras = _create_corner_cameras()
        room = create_default_room()
        coverage_result = calculate_coverage(cameras, room, grid_spacing=0.5)

        result = calculate_angle_score(
            coverage_result.cameras,
            coverage_result.merged_grid,
            coverage_result.visibility_matrix,
        )

        assert isinstance(result, AngleScoreResult)
        assert result.point_best_scores.shape[0] == coverage_result.merged_grid.shape[0]
        assert 0.0 <= result.mean_score <= 1.0
        # コーナー配置なのでそれなりのスコアが出るはず
        assert result.mean_score > 0.0
