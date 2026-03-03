"""F10: 統合品質スコアのテスト。"""

import numpy as np
import pytest

from camera_placement.evaluation.evaluator import (
    EvaluationResult,
    QualityScoreResult,
    VolumeQualityScore,
    calculate_quality_score,
    evaluate_placement,
)
from camera_placement.evaluation.coverage import CoverageResult
from camera_placement.evaluation.angle_score import AngleScoreResult
from camera_placement.evaluation.projection_score import ProjectionScoreResult
from camera_placement.models.activity import ActivityType
from camera_placement.models.camera import Camera, create_camera
from camera_placement.models.environment import create_default_room


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
# カテゴリA: calculate_quality_score（コアロジック）
# ===========================================================================

class TestCalculateQualityScore:
    """calculate_quality_score のテスト。"""

    def test_a1_default_weights_basic(self) -> None:
        """A1: デフォルト重みでの基本計算。"""
        result = calculate_quality_score(
            coverage_score=1.0,
            angle_score=0.8,
            projection_score=0.6,
            point_angle_scores=np.array([0.8]),
            point_projection_scores=np.array([0.6]),
        )
        # quality = 0.5*1.0 + 0.3*0.8 + 0.2*0.6 = 0.5 + 0.24 + 0.12 = 0.86
        assert isinstance(result, QualityScoreResult)
        np.testing.assert_allclose(result.quality_score, 0.86, atol=1e-10)
        # point_quality: w_ang_pt=0.6, w_proj_pt=0.4
        # [0.6*0.8 + 0.4*0.6] = [0.48 + 0.24] = [0.72]
        np.testing.assert_allclose(result.point_quality_scores, [0.72], atol=1e-10)
        np.testing.assert_allclose(result.mean_point_quality, 0.72, atol=1e-10)

    def test_a2_all_zero(self) -> None:
        """A2: 全スコア 0.0。"""
        result = calculate_quality_score(
            coverage_score=0.0,
            angle_score=0.0,
            projection_score=0.0,
            point_angle_scores=np.array([0.0]),
            point_projection_scores=np.array([0.0]),
        )
        np.testing.assert_allclose(result.quality_score, 0.0, atol=1e-10)

    def test_a3_all_one(self) -> None:
        """A3: 全スコア 1.0。"""
        result = calculate_quality_score(
            coverage_score=1.0,
            angle_score=1.0,
            projection_score=1.0,
            point_angle_scores=np.array([1.0]),
            point_projection_scores=np.array([1.0]),
        )
        np.testing.assert_allclose(result.quality_score, 1.0, atol=1e-10)

    def test_a4_custom_equal_weights(self) -> None:
        """A4: カスタム均等重み。"""
        result = calculate_quality_score(
            coverage_score=0.8,
            angle_score=0.6,
            projection_score=0.4,
            point_angle_scores=np.array([0.6]),
            point_projection_scores=np.array([0.4]),
            weight_coverage=1.0,
            weight_angle=1.0,
            weight_projection=1.0,
        )
        # quality = (0.8 + 0.6 + 0.4) / 3 = 0.6
        np.testing.assert_allclose(result.quality_score, 0.6, atol=1e-10)

    def test_a5_weight_normalization(self) -> None:
        """A5: 重みの正規化。"""
        result = calculate_quality_score(
            coverage_score=1.0,
            angle_score=0.0,
            projection_score=0.0,
            point_angle_scores=np.array([0.0]),
            point_projection_scores=np.array([0.0]),
            weight_coverage=2,
            weight_angle=1,
            weight_projection=1,
        )
        # quality = 0.5*1.0 + 0.25*0.0 + 0.25*0.0 = 0.5
        np.testing.assert_allclose(result.quality_score, 0.5, atol=1e-10)

    def test_a6_coverage_only_weight(self) -> None:
        """A6: coverage のみ重み。"""
        result = calculate_quality_score(
            coverage_score=0.8,
            angle_score=0.6,
            projection_score=0.4,
            point_angle_scores=np.array([0.6]),
            point_projection_scores=np.array([0.4]),
            weight_coverage=1,
            weight_angle=0,
            weight_projection=0,
        )
        np.testing.assert_allclose(result.quality_score, 0.8, atol=1e-10)

    def test_a7_angle_only_weight(self) -> None:
        """A7: angle のみ重み。"""
        result = calculate_quality_score(
            coverage_score=0.8,
            angle_score=0.6,
            projection_score=0.4,
            point_angle_scores=np.array([0.6]),
            point_projection_scores=np.array([0.4]),
            weight_coverage=0,
            weight_angle=1,
            weight_projection=0,
        )
        np.testing.assert_allclose(result.quality_score, 0.6, atol=1e-10)

    def test_a8_projection_only_weight(self) -> None:
        """A8: projection のみ重み。"""
        result = calculate_quality_score(
            coverage_score=0.8,
            angle_score=0.6,
            projection_score=0.4,
            point_angle_scores=np.array([0.6]),
            point_projection_scores=np.array([0.4]),
            weight_coverage=0,
            weight_angle=0,
            weight_projection=1,
        )
        np.testing.assert_allclose(result.quality_score, 0.4, atol=1e-10)


# ===========================================================================
# カテゴリB: ポイント品質スコア
# ===========================================================================

class TestPointQualityScore:
    """ポイント品質スコアのテスト。"""

    def test_b1_multiple_points(self) -> None:
        """B1: 複数点のポイント品質。"""
        result = calculate_quality_score(
            coverage_score=0.5,
            angle_score=0.5,
            projection_score=0.5,
            point_angle_scores=np.array([1.0, 0.5, 0.0]),
            point_projection_scores=np.array([0.5, 1.0, 0.0]),
        )
        # w_ang_pt = 0.3/0.5 = 0.6, w_proj_pt = 0.2/0.5 = 0.4
        # [0.6*1.0+0.4*0.5, 0.6*0.5+0.4*1.0, 0.6*0.0+0.4*0.0] = [0.8, 0.7, 0.0]
        np.testing.assert_allclose(
            result.point_quality_scores, [0.8, 0.7, 0.0], atol=1e-10
        )

    def test_b2_coverage_only_zero_point_quality(self) -> None:
        """B2: coverage のみ重み → point_quality = zeros。"""
        result = calculate_quality_score(
            coverage_score=0.8,
            angle_score=0.6,
            projection_score=0.4,
            point_angle_scores=np.array([0.8, 0.4, 0.2]),
            point_projection_scores=np.array([0.6, 0.3, 0.1]),
            weight_coverage=1,
            weight_angle=0,
            weight_projection=0,
        )
        np.testing.assert_allclose(
            result.point_quality_scores, [0.0, 0.0, 0.0], atol=1e-10
        )

    def test_b3_angle_only_point_quality(self) -> None:
        """B3: angle のみ重み → point_quality = angle。"""
        result = calculate_quality_score(
            coverage_score=0.0,
            angle_score=0.0,
            projection_score=0.0,
            point_angle_scores=np.array([0.8, 0.4]),
            point_projection_scores=np.array([0.6, 0.2]),
            weight_coverage=0,
            weight_angle=1,
            weight_projection=0,
        )
        np.testing.assert_allclose(
            result.point_quality_scores, [0.8, 0.4], atol=1e-10
        )

    def test_b4_empty_points(self) -> None:
        """B4: 空の点配列。"""
        result = calculate_quality_score(
            coverage_score=0.5,
            angle_score=0.5,
            projection_score=0.5,
            point_angle_scores=np.array([]),
            point_projection_scores=np.array([]),
        )
        assert result.point_quality_scores.shape == (0,)
        np.testing.assert_allclose(result.mean_point_quality, 0.0, atol=1e-10)

    def test_b5_mean_point_quality(self) -> None:
        """B5: mean_point_quality の検証。"""
        result = calculate_quality_score(
            coverage_score=0.5,
            angle_score=0.5,
            projection_score=0.5,
            point_angle_scores=np.array([0.8, 0.4]),
            point_projection_scores=np.array([0.6, 0.2]),
        )
        # w_ang_pt=0.6, w_proj_pt=0.4
        # [0.6*0.8+0.4*0.6, 0.6*0.4+0.4*0.2] = [0.72, 0.32]
        # mean = (0.72 + 0.32) / 2 = 0.52
        expected_pq = np.array([0.72, 0.32])
        np.testing.assert_allclose(result.point_quality_scores, expected_pq, atol=1e-10)
        np.testing.assert_allclose(
            result.mean_point_quality, expected_pq.mean(), atol=1e-10
        )


# ===========================================================================
# カテゴリC: エッジケース・バリデーション
# ===========================================================================

class TestEdgeCasesAndValidation:
    """エッジケースとバリデーションのテスト。"""

    def test_c1_negative_coverage_weight(self) -> None:
        """C1: 負の重み（coverage）。"""
        with pytest.raises(ValueError, match="non-negative"):
            calculate_quality_score(
                coverage_score=0.5,
                angle_score=0.5,
                projection_score=0.5,
                point_angle_scores=np.array([0.5]),
                point_projection_scores=np.array([0.5]),
                weight_coverage=-1,
            )

    def test_c2_negative_angle_weight(self) -> None:
        """C2: 負の重み（angle）。"""
        with pytest.raises(ValueError, match="non-negative"):
            calculate_quality_score(
                coverage_score=0.5,
                angle_score=0.5,
                projection_score=0.5,
                point_angle_scores=np.array([0.5]),
                point_projection_scores=np.array([0.5]),
                weight_angle=-0.1,
            )

    def test_c3_negative_projection_weight(self) -> None:
        """C3: 負の重み（projection）。"""
        with pytest.raises(ValueError, match="non-negative"):
            calculate_quality_score(
                coverage_score=0.5,
                angle_score=0.5,
                projection_score=0.5,
                point_angle_scores=np.array([0.5]),
                point_projection_scores=np.array([0.5]),
                weight_projection=-1,
            )

    def test_c4_zero_sum_weights(self) -> None:
        """C4: 重み合計 0。"""
        with pytest.raises(ValueError, match="positive"):
            calculate_quality_score(
                coverage_score=0.5,
                angle_score=0.5,
                projection_score=0.5,
                point_angle_scores=np.array([0.5]),
                point_projection_scores=np.array([0.5]),
                weight_coverage=0,
                weight_angle=0,
                weight_projection=0,
            )

    def test_c5_point_length_mismatch(self) -> None:
        """C5: point 配列の長さ不一致。"""
        with pytest.raises(ValueError, match="length"):
            calculate_quality_score(
                coverage_score=0.5,
                angle_score=0.5,
                projection_score=0.5,
                point_angle_scores=np.array([0.5, 0.3, 0.1]),
                point_projection_scores=np.array([0.5, 0.3]),
            )

    def test_c6_normalized_weights_in_result(self) -> None:
        """C6: 正規化後の重みが結果に保持される。"""
        result = calculate_quality_score(
            coverage_score=0.5,
            angle_score=0.5,
            projection_score=0.5,
            point_angle_scores=np.array([0.5]),
            point_projection_scores=np.array([0.5]),
            weight_coverage=2,
            weight_angle=1,
            weight_projection=1,
        )
        np.testing.assert_allclose(result.weight_coverage, 0.5, atol=1e-10)
        np.testing.assert_allclose(result.weight_angle, 0.25, atol=1e-10)
        np.testing.assert_allclose(result.weight_projection, 0.25, atol=1e-10)


# ===========================================================================
# カテゴリD: evaluate_placement（一括計算）
# ===========================================================================

class TestEvaluatePlacement:
    """evaluate_placement のテスト。"""

    def test_d1_basic_corner_placement(self) -> None:
        """D1: 基本動作（コーナー配置）。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        assert isinstance(result, EvaluationResult)
        assert result.quality.quality_score > 0

    def test_d2_result_structure(self) -> None:
        """D2: 結果構造の検証。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        assert isinstance(result.quality, QualityScoreResult)
        assert isinstance(result.coverage_result, CoverageResult)
        assert isinstance(result.angle_result, AngleScoreResult)
        assert isinstance(result.projection_result, ProjectionScoreResult)
        assert isinstance(result.volume_qualities, dict)

    def test_d3_coverage_result_retained(self) -> None:
        """D3: coverage_result の保持。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        assert result.coverage_result.stats.num_cameras == 6
        assert result.coverage_result.merged_grid.shape[1] == 3

    def test_d4_angle_result_retained(self) -> None:
        """D4: angle_result の保持。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        assert result.angle_result.point_best_scores.shape[0] > 0
        assert 0.0 <= result.angle_result.mean_score <= 1.0

    def test_d5_projection_result_retained(self) -> None:
        """D5: projection_result の保持。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        assert result.projection_result.point_best_scores.shape[0] > 0
        assert 0.0 <= result.projection_result.mean_score <= 1.0

    def test_d6_volume_qualities_keys(self) -> None:
        """D6: volume_qualities のキー。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        expected_keys = {ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE}
        assert set(result.volume_qualities.keys()) == expected_keys

    def test_d7_volume_qualities_score_range(self) -> None:
        """D7: volume_qualities のスコア妥当性。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        for act_type, vq in result.volume_qualities.items():
            assert isinstance(vq, VolumeQualityScore)
            assert vq.activity_type == act_type
            assert 0.0 <= vq.quality_score <= 1.0
            assert 0.0 <= vq.coverage_score <= 1.0
            assert 0.0 <= vq.angle_score <= 1.0
            assert 0.0 <= vq.projection_score <= 1.0

    def test_d8_score_consistency(self) -> None:
        """D8: スコアの一貫性（加重和の検証）。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        q = result.quality
        expected = (
            q.weight_coverage * q.coverage_score
            + q.weight_angle * q.angle_score
            + q.weight_projection * q.projection_score
        )
        np.testing.assert_allclose(q.quality_score, expected, atol=1e-10)

    def test_d9_empty_cameras(self) -> None:
        """D9: カメラ 0 台。"""
        room = create_default_room()
        result = evaluate_placement([], room)
        np.testing.assert_allclose(result.quality.quality_score, 0.0, atol=1e-10)
        # volume_qualities は 3 キー
        expected_keys = {ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE}
        assert set(result.volume_qualities.keys()) == expected_keys
        for vq in result.volume_qualities.values():
            np.testing.assert_allclose(vq.quality_score, 0.0, atol=1e-10)

    def test_d10_custom_weights(self) -> None:
        """D10: カスタム重み。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(
            cameras, room, weight_coverage=1, weight_angle=1, weight_projection=1
        )
        q = result.quality
        # 均等重み (1/3, 1/3, 1/3)
        np.testing.assert_allclose(q.weight_coverage, 1 / 3, atol=1e-10)
        np.testing.assert_allclose(q.weight_angle, 1 / 3, atol=1e-10)
        np.testing.assert_allclose(q.weight_projection, 1 / 3, atol=1e-10)
        expected = (q.coverage_score + q.angle_score + q.projection_score) / 3
        np.testing.assert_allclose(q.quality_score, expected, atol=1e-10)

    def test_d11_target_ppm_parameter(self) -> None:
        """D11: target_ppm パラメータ。"""
        cameras = _create_corner_cameras()
        room = create_default_room()
        result_high = evaluate_placement(cameras, room, target_ppm=500.0)
        result_low = evaluate_placement(cameras, room, target_ppm=200.0)
        # target_ppm が低いと達成しやすいので projection_score が高くなる
        assert result_low.quality.projection_score >= result_high.quality.projection_score


# ===========================================================================
# カテゴリE: 実環境シナリオ
# ===========================================================================

class TestRealWorldScenarios:
    """実環境シナリオのテスト。"""

    def test_e1_corner_vs_clustered(self) -> None:
        """E1: コーナー配置 vs 密集配置。"""
        room = create_default_room()
        corner_result = evaluate_placement(_create_corner_cameras(), room)
        clustered_result = evaluate_placement(_create_clustered_cameras(), room)
        assert corner_result.quality.quality_score > clustered_result.quality.quality_score

    def test_e2_supine_higher_than_walking(self) -> None:
        """E2: 臥位のスコアが歩行より高い。

        臥位はベッド上の狭い範囲（Z:0.2-0.5m）に限定され、上方のカメラから
        近距離で観測されるため、投影サイズスコアとカバレッジが高くなる。
        一方、歩行はベッド外の広い床面エリア（Z:0-1.8m）をカバーするため、
        カメラから離れた点が含まれ平均スコアが下がる。
        """
        cameras = _create_corner_cameras()
        room = create_default_room()
        result = evaluate_placement(cameras, room)
        walking_score = result.volume_qualities[ActivityType.WALKING].quality_score
        supine_score = result.volume_qualities[ActivityType.SUPINE].quality_score
        assert supine_score > walking_score
