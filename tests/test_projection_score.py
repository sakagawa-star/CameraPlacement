"""F09: 2D投影サイズスコアのテスト。"""

import numpy as np
import pytest

from camera_placement.evaluation.projection_score import (
    ProjectionScoreResult,
    calculate_pixel_per_meter,
    calculate_projection_score,
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


# ===========================================================================
# カテゴリA: calculate_pixel_per_meter（低レベル関数）
# ===========================================================================

class TestCalculatePixelPerMeter:
    """calculate_pixel_per_meter のテスト。"""

    def test_a1_distance_1m(self) -> None:
        """A1: 距離1mでの基本計算。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([[1.0, 0.0, 0.0]])
        ppm = calculate_pixel_per_meter(cam, points, fx=1000.0)
        assert ppm.shape == (1,)
        np.testing.assert_allclose(ppm, [1000.0])

    def test_a2_distance_2m(self) -> None:
        """A2: 距離2mで逆比例の確認。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([[2.0, 0.0, 0.0]])
        ppm = calculate_pixel_per_meter(cam, points, fx=1000.0)
        np.testing.assert_allclose(ppm, [500.0])

    def test_a3_batch(self) -> None:
        """A3: バッチ計算（複数点）。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [4.0, 0.0, 0.0],
        ])
        ppm = calculate_pixel_per_meter(cam, points, fx=1000.0)
        assert ppm.shape == (3,)
        np.testing.assert_allclose(ppm, [1000.0, 500.0, 250.0])

    def test_a4_zero_distance(self) -> None:
        """A4: カメラと点が同一位置でゼロ除算防止。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        ppm = calculate_pixel_per_meter(cam, points, fx=1000.0)
        np.testing.assert_allclose(ppm, [0.0])

    def test_a5_3d_distance(self) -> None:
        """A5: 3次元ユークリッド距離（3-4-5三角形）。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([[3.0, 4.0, 0.0]])
        ppm = calculate_pixel_per_meter(cam, points, fx=1000.0)
        # distance = 5.0, ppm = 1000/5 = 200
        np.testing.assert_allclose(ppm, [200.0])

    def test_a6_real_camera_fx(self) -> None:
        """A6: 実カメラのfx値での計算。"""
        cam = np.array([0.0, 0.0, 0.0])
        points = np.array([[3.0, 0.0, 0.0]])
        fx = 1166.67
        ppm = calculate_pixel_per_meter(cam, points, fx=fx)
        np.testing.assert_allclose(ppm, [fx / 3.0], atol=0.01)


# ===========================================================================
# カテゴリB: calculate_projection_score（メイン関数）
# ===========================================================================

class TestCalculateProjectionScore:
    """calculate_projection_score のテスト。"""

    def test_b1_close_distance(self) -> None:
        """B1: 近距離1台、1点。ppm > target_ppm → score = 1.0。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True]])
        result = calculate_projection_score([cam], points, vis, target_ppm=500.0)

        assert isinstance(result, ProjectionScoreResult)
        # fx ≈ 1166.67, distance = 1.0, ppm ≈ 1166.67 > 500 → score = 1.0
        np.testing.assert_allclose(result.point_best_scores, [1.0])
        assert result.mean_score == pytest.approx(1.0)

    def test_b2_far_distance(self) -> None:
        """B2: 遠距離1台、1点。score ≈ 0.467。"""
        cam = create_camera([5.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True]])
        result = calculate_projection_score([cam], points, vis, target_ppm=500.0)

        # fx ≈ 1166.67, distance = 5.0, ppm ≈ 233.33, score ≈ 0.4667
        np.testing.assert_allclose(result.point_best_scores, [233.33 / 500.0], atol=0.01)

    def test_b3_two_cameras_different_distances(self) -> None:
        """B3: 2台（距離異なる）、1点。近い方がベスト。"""
        cam_near = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_far = create_camera([4.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True]])
        result = calculate_projection_score(
            [cam_near, cam_far], points, vis, target_ppm=500.0
        )

        # 近い方: ppm ≈ 1166.67, score = 1.0
        # 遠い方: ppm ≈ 291.67, score ≈ 0.583
        np.testing.assert_allclose(result.point_best_scores, [1.0])
        assert result.point_mean_scores[0] < result.point_best_scores[0]

    def test_b4_partial_visibility(self) -> None:
        """B4: 部分視認。1台のみ可視の場合、そのカメラのスコアのみ反映。"""
        cam_near = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_far = create_camera([4.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        # cam_far のみ可視
        vis = np.array([[False], [True]])
        result = calculate_projection_score(
            [cam_near, cam_far], points, vis, target_ppm=500.0
        )

        # 遠い方のみ: ppm ≈ 291.67, score ≈ 0.583
        fx = cam_far.intrinsics.fx
        expected_score = min(fx / 4.0 / 500.0, 1.0)
        np.testing.assert_allclose(result.point_best_scores, [expected_score], atol=0.01)

    def test_b5_target_ppm_effect(self) -> None:
        """B5: target_ppmパラメータの効果。低いtargetの方がスコア高い。"""
        cam = create_camera([3.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True]])

        result_high = calculate_projection_score([cam], points, vis, target_ppm=500.0)
        result_low = calculate_projection_score([cam], points, vis, target_ppm=200.0)

        assert result_low.mean_score > result_high.mean_score

    def test_b6_mean_score(self) -> None:
        """B6: mean_score = point_best_scores.mean() の検証。"""
        cam1 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam2 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 3.0, 0.0],
        ])
        vis = np.array([
            [True, True, False],
            [True, False, True],
        ])
        result = calculate_projection_score([cam1, cam2], points, vis, target_ppm=500.0)

        expected_mean = float(result.point_best_scores.mean())
        assert result.mean_score == pytest.approx(expected_mean)

    def test_b7_point_mean_scores(self) -> None:
        """B7: point_mean_scores = 全視認カメラのスコアの平均。"""
        cam1 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam2 = create_camera([4.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0]])
        vis = np.array([[True], [True]])
        result = calculate_projection_score([cam1, cam2], points, vis, target_ppm=500.0)

        fx = cam1.intrinsics.fx
        score1 = min(fx / 1.0 / 500.0, 1.0)
        score2 = min(fx / 4.0 / 500.0, 1.0)
        expected_mean = (score1 + score2) / 2.0
        np.testing.assert_allclose(result.point_mean_scores, [expected_mean], atol=0.01)


# ===========================================================================
# カテゴリC: エッジケース
# ===========================================================================

class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_c1_no_cameras(self) -> None:
        """C1: カメラ0台。"""
        points = np.zeros((0, 3))
        vis = np.zeros((0, 0), dtype=bool)
        result = calculate_projection_score([], points, vis)

        assert result.mean_score == 0.0
        assert result.point_best_scores.shape == (0,)
        assert result.point_mean_scores.shape == (0,)
        assert result.point_best_ppm.shape == (0,)

    def test_c2_single_camera(self) -> None:
        """C2: カメラ1台。best = mean（各点）。"""
        cam = create_camera([2.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ])
        vis = np.array([[True, True]])
        result = calculate_projection_score([cam], points, vis, target_ppm=500.0)

        np.testing.assert_allclose(
            result.point_best_scores, result.point_mean_scores
        )

    def test_c3_empty_grid(self) -> None:
        """C3: グリッド点0個。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        points = np.zeros((0, 3))
        vis = np.zeros((1, 0), dtype=bool)
        result = calculate_projection_score([cam], points, vis)

        assert result.mean_score == 0.0
        assert result.point_best_scores.shape == (0,)

    def test_c4_all_invisible(self) -> None:
        """C4: 全点が視認不可。"""
        cam1 = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam2 = create_camera([0.0, 1.0, 0.0], [0.0, 0.0, 0.0])
        points = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        vis = np.array([[False, False], [False, False]])
        result = calculate_projection_score([cam1, cam2], points, vis)

        np.testing.assert_allclose(result.point_best_scores, [0.0, 0.0])
        assert result.mean_score == 0.0

    def test_c5_grid_not_2d(self) -> None:
        """C5: grid_pointsが2Dでない場合はValueError。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="grid_points must be 2D"):
            calculate_projection_score(
                [cam], np.array([1.0, 2.0, 3.0]), np.array([[True]])
            )

    def test_c6_grid_wrong_columns(self) -> None:
        """C6: grid_points.shape[1] != 3 の場合はValueError。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="grid_points.shape\\[1\\] must be 3"):
            calculate_projection_score(
                [cam], np.array([[1.0, 2.0]]), np.array([[True]])
            )

    def test_c7_vis_not_2d(self) -> None:
        """C7: visibility_matrixが2Dでない場合はValueError。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="visibility_matrix must be 2D"):
            calculate_projection_score(
                [cam], np.array([[0.0, 0.0, 0.0]]), np.array([True])
            )

    def test_c8_vis_shape0_mismatch(self) -> None:
        """C8: visibility_matrix.shape[0] != len(cameras)。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="visibility_matrix.shape\\[0\\]"):
            calculate_projection_score(
                [cam], np.array([[0.0, 0.0, 0.0]]), np.array([[True], [True]])
            )

    def test_c9_vis_shape1_mismatch(self) -> None:
        """C9: visibility_matrix.shape[1] != grid_points.shape[0]。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="visibility_matrix.shape\\[1\\]"):
            calculate_projection_score(
                [cam],
                np.array([[0.0, 0.0, 0.0]]),
                np.array([[True, True]]),
            )

    def test_c10_negative_target_ppm(self) -> None:
        """C10: target_ppm <= 0 でValueError。"""
        cam = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="target_ppm must be positive"):
            calculate_projection_score(
                [cam],
                np.array([[0.0, 0.0, 0.0]]),
                np.array([[True]]),
                target_ppm=-1.0,
            )


# ===========================================================================
# カテゴリD: 実環境シナリオ
# ===========================================================================

class TestRealWorldScenarios:
    """実環境シナリオのテスト。"""

    def test_d1_corner_placement(self) -> None:
        """D1: コーナー配置6台、小グリッドで正のスコア。"""
        cameras = _create_corner_cameras()
        # 部屋中央付近の小グリッド
        points = np.array([
            [1.0, 1.0, 0.5],
            [1.4, 1.75, 1.0],
            [2.0, 2.5, 0.3],
            [0.5, 0.5, 1.5],
        ])
        vis = np.ones((6, 4), dtype=bool)
        result = calculate_projection_score(cameras, points, vis)

        assert result.mean_score > 0.3
        assert all(s > 0.0 for s in result.point_best_scores)

    def test_d2_near_vs_far(self) -> None:
        """D2: 近距離配置 vs 遠距離配置。近い方がスコア高い。"""
        points = np.array([[0.0, 0.0, 0.0]])

        cam_near = create_camera([1.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        cam_far = create_camera([5.0, 0.0, 0.0], [0.0, 0.0, 0.0])

        vis = np.array([[True]])

        result_near = calculate_projection_score([cam_near], points, vis)
        result_far = calculate_projection_score([cam_far], points, vis)

        assert result_near.mean_score > result_far.mean_score

    def test_d3_f07_integration(self) -> None:
        """D3: F07の出力形式との連携テスト。"""
        from camera_placement.evaluation.coverage import calculate_coverage
        from camera_placement.models.environment import Room, create_default_room

        room = create_default_room()
        cameras = _create_corner_cameras()

        coverage_result = calculate_coverage(cameras, room)

        proj_result = calculate_projection_score(
            coverage_result.cameras,
            coverage_result.merged_grid,
            coverage_result.visibility_matrix,
        )

        assert isinstance(proj_result, ProjectionScoreResult)
        assert 0.0 <= proj_result.mean_score <= 1.0
        assert proj_result.point_best_scores.shape[0] == coverage_result.merged_grid.shape[0]
