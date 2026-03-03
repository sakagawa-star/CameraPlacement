"""F13: 配置比較・レポートのテスト。"""

import pytest
from pathlib import Path

from camera_placement.placement.comparison import (
    ComparisonResult,
    EvaluationParams,
    PresetEvaluation,
    compare_presets,
    evaluate_preset,
    generate_report,
    save_report,
)
from camera_placement.placement.patterns import (
    PlacementPreset,
    get_all_presets,
    get_preset,
)
from camera_placement.evaluation.evaluator import EvaluationResult
from camera_placement.models.environment import Room, create_default_room
from camera_placement.models.activity import ActivityType


# --- フィクスチャ ---


@pytest.fixture
def room() -> Room:
    return create_default_room()


@pytest.fixture
def single_preset() -> PlacementPreset:
    return get_preset("upper_corners")


@pytest.fixture
def comparison_result(room: Room) -> ComparisonResult:
    """全プリセット比較結果（grid_spacing=0.5 で高速化）。"""
    return compare_presets(room, grid_spacing=0.5)


# --- カテゴリA: evaluate_preset ---


class TestEvaluatePreset:
    """evaluate_preset のテスト。"""

    def test_a1_basic(self, single_preset: PlacementPreset, room: Room) -> None:
        """A1: 基本動作。"""
        result = evaluate_preset(single_preset, room, grid_spacing=0.5)
        assert isinstance(result, PresetEvaluation)

    def test_a2_preset_matches(
        self, single_preset: PlacementPreset, room: Room
    ) -> None:
        """A2: preset が一致。"""
        result = evaluate_preset(single_preset, room, grid_spacing=0.5)
        assert result.preset.name == "upper_corners"

    def test_a3_evaluation_type(
        self, single_preset: PlacementPreset, room: Room
    ) -> None:
        """A3: evaluation が EvaluationResult。"""
        result = evaluate_preset(single_preset, room, grid_spacing=0.5)
        assert isinstance(result.evaluation, EvaluationResult)

    def test_a4_quality_score_range(
        self, single_preset: PlacementPreset, room: Room
    ) -> None:
        """A4: quality_score が [0.0, 1.0]。"""
        result = evaluate_preset(single_preset, room, grid_spacing=0.5)
        score = result.evaluation.quality.quality_score
        assert 0.0 <= score <= 1.0

    def test_a5_all_presets(self, room: Room) -> None:
        """A5: 全プリセットで動作。"""
        for preset in get_all_presets():
            result = evaluate_preset(preset, room, grid_spacing=0.5)
            assert isinstance(result, PresetEvaluation)

    def test_a6_volume_qualities(
        self, single_preset: PlacementPreset, room: Room
    ) -> None:
        """A6: volume_qualities が3種類。"""
        result = evaluate_preset(single_preset, room, grid_spacing=0.5)
        vq = result.evaluation.volume_qualities
        assert ActivityType.WALKING in vq
        assert ActivityType.SEATED in vq
        assert ActivityType.SUPINE in vq

    def test_a7_custom_weights(
        self, single_preset: PlacementPreset, room: Room
    ) -> None:
        """A7: カスタム重みで動作（カバレッジのみ）。"""
        result = evaluate_preset(
            single_preset,
            room,
            grid_spacing=0.5,
            weight_coverage=1.0,
            weight_angle=0.0,
            weight_projection=0.0,
        )
        q = result.evaluation.quality
        assert abs(q.quality_score - q.coverage_score) < 1e-9


# --- カテゴリB: compare_presets ---


class TestComparePresets:
    """compare_presets のテスト。"""

    def test_b1_default_all_presets(self, room: Room) -> None:
        """B1: デフォルト（全プリセット）。"""
        result = compare_presets(room, grid_spacing=0.5)
        assert len(result.rankings) == 5

    def test_b2_rankings_type(self, room: Room) -> None:
        """B2: rankings の型。"""
        result = compare_presets(room, grid_spacing=0.5)
        for pe in result.rankings:
            assert isinstance(pe, PresetEvaluation)

    def test_b3_rankings_descending(self, room: Room) -> None:
        """B3: rankings がスコア降順。"""
        result = compare_presets(room, grid_spacing=0.5)
        scores = [pe.evaluation.quality.quality_score for pe in result.rankings]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_b4_best_is_first(self, room: Room) -> None:
        """B4: best が rankings[0]。"""
        result = compare_presets(room, grid_spacing=0.5)
        assert result.best is result.rankings[0]

    def test_b5_best_has_max_score(self, room: Room) -> None:
        """B5: best のスコアが最大。"""
        result = compare_presets(room, grid_spacing=0.5)
        best_score = result.best.evaluation.quality.quality_score
        for pe in result.rankings:
            assert best_score >= pe.evaluation.quality.quality_score

    def test_b6_specified_presets(self, room: Room) -> None:
        """B6: 指定プリセットで比較。"""
        presets = [get_preset("upper_corners"), get_preset("hybrid")]
        result = compare_presets(room, presets=presets, grid_spacing=0.5)
        assert len(result.rankings) == 2

    def test_b7_single_preset(self, room: Room) -> None:
        """B7: 1プリセットで比較。"""
        presets = [get_preset("upper_corners")]
        result = compare_presets(room, presets=presets, grid_spacing=0.5)
        assert len(result.rankings) == 1
        assert result.best is result.rankings[0]

    def test_b8_empty_presets(self, room: Room) -> None:
        """B8: 空リスト。"""
        with pytest.raises(ValueError, match="presets must not be empty"):
            compare_presets(room, presets=[])

    def test_b9_evaluation_params(self, room: Room) -> None:
        """B9: evaluation_params が保持される。"""
        result = compare_presets(room, grid_spacing=0.5)
        params = result.evaluation_params
        assert isinstance(params, EvaluationParams)
        assert params.grid_spacing == 0.5
        assert params.near == 0.1
        assert params.far == 10.0
        assert params.target_ppm == 500.0
        assert params.weight_coverage == 0.5
        assert params.weight_angle == 0.3
        assert params.weight_projection == 0.2

    def test_b10_custom_params(self, room: Room) -> None:
        """B10: カスタムパラメータが反映。"""
        presets = [get_preset("upper_corners")]
        result = compare_presets(
            room,
            presets=presets,
            grid_spacing=0.5,
            near=0.5,
            far=5.0,
            target_ppm=300.0,
            weight_coverage=0.4,
            weight_angle=0.4,
            weight_projection=0.2,
        )
        params = result.evaluation_params
        assert params.grid_spacing == 0.5
        assert params.near == 0.5
        assert params.far == 5.0
        assert params.target_ppm == 300.0
        assert params.weight_coverage == 0.4
        assert params.weight_angle == 0.4
        assert params.weight_projection == 0.2


# --- カテゴリC: generate_report ---


class TestGenerateReport:
    """generate_report のテスト。"""

    def test_c1_header(self, comparison_result: ComparisonResult) -> None:
        """C1: ヘッダーが含まれる。"""
        report = generate_report(comparison_result)
        assert "Camera Placement Comparison Report" in report

    def test_c2_all_preset_names(self, comparison_result: ComparisonResult) -> None:
        """C2: 全プリセット名が含まれる。"""
        report = generate_report(comparison_result)
        for pe in comparison_result.rankings:
            assert pe.preset.name in report

    def test_c3_score_format(self, comparison_result: ComparisonResult) -> None:
        """C3: スコアが3桁で表示。"""
        import re

        report = generate_report(comparison_result)
        # "0.xxx" パターンが存在する
        assert re.search(r"\d+\.\d{3}", report) is not None

    def test_c4_evaluation_params(self, comparison_result: ComparisonResult) -> None:
        """C4: 評価パラメータが含まれる。"""
        report = generate_report(comparison_result)
        assert "Grid Spacing" in report
        assert "Near Clip" in report
        assert "Far Clip" in report
        assert "Target PPM" in report
        assert "Weights" in report

    def test_c5_volume_sections(self, comparison_result: ComparisonResult) -> None:
        """C5: 活動ボリューム別が含まれる。"""
        report = generate_report(comparison_result)
        assert "walking" in report
        assert "seated" in report
        assert "supine" in report

    def test_c6_best_summary(self, comparison_result: ComparisonResult) -> None:
        """C6: ベストプリセットサマリーが含まれる。"""
        report = generate_report(comparison_result)
        assert "Best Preset:" in report

    def test_c7_ranking_header(self, comparison_result: ComparisonResult) -> None:
        """C7: ランキング表のヘッダーが含まれる。"""
        report = generate_report(comparison_result)
        assert "Rank" in report
        assert "Preset" in report
        assert "Quality" in report

    def test_c8_single_preset_report(self, room: Room) -> None:
        """C8: 1プリセットのレポート。"""
        presets = [get_preset("upper_corners")]
        result = compare_presets(room, presets=presets, grid_spacing=0.5)
        report = generate_report(result)
        assert isinstance(report, str)
        assert "upper_corners" in report

    def test_c9_report_is_string(self, comparison_result: ComparisonResult) -> None:
        """C9: レポートが文字列。"""
        report = generate_report(comparison_result)
        assert isinstance(report, str)


# --- カテゴリD: save_report ---


class TestSaveReport:
    """save_report のテスト。"""

    def test_d1_file_saved(self, tmp_path: Path) -> None:
        """D1: ファイル保存。"""
        report = "Test report content"
        filepath = tmp_path / "report.txt"
        result = save_report(report, filepath)
        assert filepath.exists()
        assert filepath.read_text(encoding="utf-8") == report

    def test_d2_returns_path(self, tmp_path: Path) -> None:
        """D2: 戻り値が Path。"""
        report = "Test report content"
        filepath = tmp_path / "report.txt"
        result = save_report(report, filepath)
        assert isinstance(result, Path)
        assert result == filepath

    def test_d3_auto_create_dirs(self, tmp_path: Path) -> None:
        """D3: 親ディレクトリ自動作成。"""
        report = "Test report content"
        filepath = tmp_path / "sub" / "dir" / "report.txt"
        save_report(report, filepath)
        assert filepath.exists()

    def test_d4_utf8_encoding(self, tmp_path: Path) -> None:
        """D4: UTF-8 エンコーディング。"""
        report = "日本語を含むレポート: ハイブリッド型"
        filepath = tmp_path / "report.txt"
        save_report(report, filepath)
        content = filepath.read_text(encoding="utf-8")
        assert content == report


# --- カテゴリE: 統合テスト ---


class TestIntegration:
    """統合テスト。"""

    def test_e1_end_to_end(self, room: Room, tmp_path: Path) -> None:
        """E1: 比較→レポート→保存の一連フロー。"""
        result = compare_presets(room, grid_spacing=0.5)
        report = generate_report(result)
        filepath = tmp_path / "comparison_report.txt"
        save_report(report, filepath)

        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        for pe in result.rankings:
            assert pe.preset.name in content

    def test_e2_different_weights(self, room: Room) -> None:
        """E2: 異なる重みで結果が変わる。"""
        presets = [get_preset("upper_corners"), get_preset("bed_focused")]

        result1 = compare_presets(
            room,
            presets=presets,
            grid_spacing=0.5,
            weight_coverage=1.0,
            weight_angle=0.0,
            weight_projection=0.0,
        )
        result2 = compare_presets(
            room,
            presets=presets,
            grid_spacing=0.5,
            weight_coverage=0.0,
            weight_angle=1.0,
            weight_projection=0.0,
        )

        # スコアまたはランキングが異なるはず
        scores1 = [
            pe.evaluation.quality.quality_score for pe in result1.rankings
        ]
        scores2 = [
            pe.evaluation.quality.quality_score for pe in result2.rankings
        ]
        names1 = [pe.preset.name for pe in result1.rankings]
        names2 = [pe.preset.name for pe in result2.rankings]
        assert scores1 != scores2 or names1 != names2
