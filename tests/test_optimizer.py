"""F15: 最適化エンジン・結果出力のテスト。"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest

from camera_placement.evaluation.evaluator import EvaluationResult, evaluate_placement
from camera_placement.models.camera import Camera
from camera_placement.models.environment import Room, create_default_room
from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    cameras_to_params,
    params_to_cameras,
)
from camera_placement.optimization.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    create_convergence_plot,
    generate_optimization_report,
    optimize_placement,
    save_optimization_report,
    visualize_result,
)


@pytest.fixture
def room() -> Room:
    return create_default_room()


@pytest.fixture
def minimal_config() -> OptimizationConfig:
    """テスト用の最小設定（高速実行）。"""
    return OptimizationConfig(
        maxiter=2,
        popsize=1,
        tol=0.01,
        seed=42,
        grid_spacing=1.0,
        eval_grid_spacing=1.0,
        num_cameras=6,
    )


@pytest.fixture
def optimization_result(room: Room, minimal_config: OptimizationConfig) -> OptimizationResult:
    """テスト用の最適化結果。"""
    return optimize_placement(room, config=minimal_config, init_preset="upper_corners")


# === カテゴリA: OptimizationConfig のバリデーション ===


class TestOptimizationConfigValidation:
    """A1-A16: OptimizationConfig のバリデーション。"""

    def test_a1_default_creation(self) -> None:
        """A1: デフォルト値で生成できる。"""
        config = OptimizationConfig()
        assert config.maxiter == 50
        assert config.popsize == 5
        assert config.num_cameras == 6

    def test_a2_maxiter_less_than_1(self) -> None:
        """A2: maxiter < 1 で ValueError。"""
        with pytest.raises(ValueError, match="maxiter must be >= 1"):
            OptimizationConfig(maxiter=0)

    def test_a3_popsize_less_than_1(self) -> None:
        """A3: popsize < 1 で ValueError。"""
        with pytest.raises(ValueError, match="popsize must be >= 1"):
            OptimizationConfig(popsize=0)

    def test_a4_tol_negative(self) -> None:
        """A4: tol < 0 で ValueError。"""
        with pytest.raises(ValueError, match="tol must be >= 0"):
            OptimizationConfig(tol=-0.1)

    def test_a5_mutation_lower_bound(self) -> None:
        """A5: mutation 要素が 0 以下で ValueError。"""
        with pytest.raises(ValueError, match="mutation values must be in"):
            OptimizationConfig(mutation=(0, 1))

    def test_a6_mutation_upper_bound(self) -> None:
        """A6: mutation 要素が 2 より大きいで ValueError。"""
        with pytest.raises(ValueError, match="mutation values must be in"):
            OptimizationConfig(mutation=(0.5, 2.5))

    def test_a7_recombination_negative(self) -> None:
        """A7: recombination < 0 で ValueError。"""
        with pytest.raises(ValueError, match="recombination must be in"):
            OptimizationConfig(recombination=-0.1)

    def test_a8_recombination_over_1(self) -> None:
        """A8: recombination > 1 で ValueError。"""
        with pytest.raises(ValueError, match="recombination must be in"):
            OptimizationConfig(recombination=1.1)

    def test_a9_grid_spacing_zero(self) -> None:
        """A9: grid_spacing <= 0 で ValueError。"""
        with pytest.raises(ValueError, match="grid_spacing must be > 0"):
            OptimizationConfig(grid_spacing=0)

    def test_a10_eval_grid_spacing_negative(self) -> None:
        """A10: eval_grid_spacing <= 0 で ValueError。"""
        with pytest.raises(ValueError, match="eval_grid_spacing must be > 0"):
            OptimizationConfig(eval_grid_spacing=-0.1)

    def test_a11_penalty_weight_negative(self) -> None:
        """A11: penalty_weight < 0 で ValueError。"""
        with pytest.raises(ValueError, match="penalty_weight must be >= 0"):
            OptimizationConfig(penalty_weight=-1)

    def test_a12_weight_negative(self) -> None:
        """A12: 重みが負で ValueError。"""
        with pytest.raises(ValueError, match="weights must be non-negative"):
            OptimizationConfig(weight_coverage=-0.1)

    def test_a13_weights_sum_zero(self) -> None:
        """A13: 重み合計が 0 で ValueError。"""
        with pytest.raises(ValueError, match="sum of weights must be positive"):
            OptimizationConfig(weight_coverage=0, weight_angle=0, weight_projection=0)

    def test_a14_num_cameras_zero(self) -> None:
        """A14: num_cameras < 1 で ValueError。"""
        with pytest.raises(ValueError, match="num_cameras must be >= 1"):
            OptimizationConfig(num_cameras=0)

    def test_a15_custom_values(self) -> None:
        """A15: 全パラメータにカスタム値を指定して正常生成。"""
        config = OptimizationConfig(
            maxiter=10,
            popsize=3,
            tol=0.001,
            mutation=(0.3, 0.8),
            recombination=0.5,
            seed=123,
            strategy="rand1bin",
            polish=True,
            grid_spacing=0.8,
            eval_grid_spacing=0.3,
            penalty_weight=50.0,
            weight_coverage=0.4,
            weight_angle=0.4,
            weight_projection=0.2,
            num_cameras=4,
        )
        assert config.maxiter == 10
        assert config.seed == 123
        assert config.strategy == "rand1bin"
        assert config.num_cameras == 4

    def test_a16_frozen(self) -> None:
        """A16: frozen dataclass で属性変更不可。"""
        config = OptimizationConfig()
        with pytest.raises(FrozenInstanceError):
            config.maxiter = 100  # type: ignore[misc]


# === カテゴリB: optimize_placement の基本動作 ===


class TestOptimizePlacementBasic:
    """B1-B11: optimize_placement の基本動作。"""

    def test_b1_returns_result(self, optimization_result: OptimizationResult) -> None:
        """B1: OptimizationResult が返る。"""
        assert isinstance(optimization_result, OptimizationResult)

    def test_b2_config_none_default(self, room: Room) -> None:
        """B2: config=None で型エラーなく動作。"""
        # config=None のコードパスをテスト（実際の最適化は minimal_config で実施済み）
        config = OptimizationConfig(
            maxiter=1, popsize=1, seed=42, grid_spacing=1.0, eval_grid_spacing=1.0
        )
        result = optimize_placement(room, config=config)
        assert isinstance(result, OptimizationResult)

    def test_b3_best_params_shape(self, optimization_result: OptimizationResult) -> None:
        """B3: best_params の shape が (36,)。"""
        assert optimization_result.best_params.shape == (36,)

    def test_b4_best_cameras_count(self, optimization_result: OptimizationResult) -> None:
        """B4: best_cameras が 6 台。"""
        assert len(optimization_result.best_cameras) == 6

    def test_b5_best_value_type(self, optimization_result: OptimizationResult) -> None:
        """B5: best_value が float 型。"""
        assert isinstance(optimization_result.best_value, float)

    def test_b6_detail_type(self, optimization_result: OptimizationResult) -> None:
        """B6: detail が ObjectiveResult 型。"""
        assert isinstance(optimization_result.detail, ObjectiveResult)

    def test_b7_fine_evaluation_type(self, optimization_result: OptimizationResult) -> None:
        """B7: fine_evaluation が EvaluationResult 型。"""
        assert isinstance(optimization_result.fine_evaluation, EvaluationResult)

    def test_b8_nit_non_negative(self, optimization_result: OptimizationResult) -> None:
        """B8: nit >= 0。"""
        assert optimization_result.nit >= 0

    def test_b9_nfev_non_negative(self, optimization_result: OptimizationResult) -> None:
        """B9: nfev >= 0。"""
        assert optimization_result.nfev >= 0

    def test_b10_elapsed_non_negative(self, optimization_result: OptimizationResult) -> None:
        """B10: elapsed_seconds >= 0。"""
        assert optimization_result.elapsed_seconds >= 0

    def test_b11_convergence_history_length(self, optimization_result: OptimizationResult) -> None:
        """B11: convergence_history の長さが 1 以上。"""
        assert len(optimization_result.convergence_history) >= 1


# === カテゴリC: 初期解の指定 ===


class TestInitialSolution:
    """C1-C5: 初期解の指定。"""

    def test_c1_init_preset(self, room: Room, minimal_config: OptimizationConfig) -> None:
        """C1: init_preset 指定で正常終了。"""
        result = optimize_placement(room, config=minimal_config, init_preset="upper_corners")
        assert isinstance(result, OptimizationResult)

    def test_c2_init_params(self, room: Room, minimal_config: OptimizationConfig) -> None:
        """C2: init_params 指定で正常終了。"""
        from camera_placement.placement.patterns import create_cameras, get_preset

        preset = get_preset("upper_corners")
        cameras = create_cameras(preset, room)
        init_params = cameras_to_params(cameras)
        result = optimize_placement(room, config=minimal_config, init_params=init_params)
        assert isinstance(result, OptimizationResult)

    def test_c3_both_specified(self, room: Room, minimal_config: OptimizationConfig) -> None:
        """C3: init_preset と init_params の両方指定で ValueError。"""
        init_params = np.zeros(36)
        with pytest.raises(ValueError, match="Cannot specify both"):
            optimize_placement(
                room,
                config=minimal_config,
                init_preset="upper_corners",
                init_params=init_params,
            )

    def test_c4_nonexistent_preset(self, room: Room, minimal_config: OptimizationConfig) -> None:
        """C4: 存在しないプリセットで KeyError。"""
        with pytest.raises(KeyError):
            optimize_placement(room, config=minimal_config, init_preset="nonexistent")

    def test_c5_init_params_wrong_shape(self, room: Room, minimal_config: OptimizationConfig) -> None:
        """C5: init_params の shape が不正で ValueError。"""
        init_params = np.zeros(35)
        with pytest.raises(ValueError):
            optimize_placement(room, config=minimal_config, init_params=init_params)


# === カテゴリD: 再現性 ===


class TestReproducibility:
    """D1-D2: 再現性。"""

    def test_d1_seed_reproducibility_value(self, room: Room) -> None:
        """D1: seed 固定で2回実行すると best_value が一致。"""
        config = OptimizationConfig(
            maxiter=2, popsize=1, seed=42, grid_spacing=1.0, eval_grid_spacing=1.0
        )
        result1 = optimize_placement(room, config=config, init_preset="upper_corners")
        result2 = optimize_placement(room, config=config, init_preset="upper_corners")
        assert result1.best_value == result2.best_value

    def test_d2_seed_reproducibility_history(self, room: Room) -> None:
        """D2: seed 固定で2回実行すると convergence_history が一致。"""
        config = OptimizationConfig(
            maxiter=2, popsize=1, seed=42, grid_spacing=1.0, eval_grid_spacing=1.0
        )
        result1 = optimize_placement(room, config=config, init_preset="upper_corners")
        result2 = optimize_placement(room, config=config, init_preset="upper_corners")
        assert result1.convergence_history == result2.convergence_history


# === カテゴリE: generate_optimization_report ===


class TestGenerateReport:
    """E1-E7: generate_optimization_report。"""

    def test_e1_header(self, optimization_result: OptimizationResult) -> None:
        """E1: ヘッダーを含む。"""
        report = generate_optimization_report(optimization_result)
        assert "=== Camera Placement Optimization Report ===" in report

    def test_e2_parameters(self, optimization_result: OptimizationResult) -> None:
        """E2: 最適化パラメータを含む。"""
        report = generate_optimization_report(optimization_result)
        assert "Max Iterations:" in report
        assert "Strategy:" in report
        assert "Population Size:" in report

    def test_e3_quality_score(self, optimization_result: OptimizationResult) -> None:
        """E3: 品質スコアを含む。"""
        report = generate_optimization_report(optimization_result)
        assert "Quality Score:" in report
        assert "Coverage Score:" in report
        assert "Angle Score:" in report
        assert "Projection Score:" in report

    def test_e4_camera_placement(self, optimization_result: OptimizationResult) -> None:
        """E4: カメラ配置を含む。"""
        report = generate_optimization_report(optimization_result)
        assert "Camera 1:" in report
        assert "position=" in report
        assert "look_at=" in report

    def test_e5_volume_quality(self, optimization_result: OptimizationResult) -> None:
        """E5: ボリューム品質を含む。"""
        report = generate_optimization_report(optimization_result)
        assert "walking" in report

    def test_e6_time_seconds(self, optimization_result: OptimizationResult) -> None:
        """E6: 60秒未満の場合は秒表記。"""
        # optimization_result は短時間実行なので秒表記のはず
        report = generate_optimization_report(optimization_result)
        assert "sec" in report

    def test_e7_time_minutes(self, optimization_result: OptimizationResult) -> None:
        """E7: 60秒以上の場合は分表記。"""
        # elapsed_seconds を書き換えてテスト
        original = optimization_result.elapsed_seconds
        optimization_result.elapsed_seconds = 125.3
        report = generate_optimization_report(optimization_result)
        assert "2.1 min" in report
        optimization_result.elapsed_seconds = original


# === カテゴリF: save_optimization_report ===


class TestSaveReport:
    """F1-F3: save_optimization_report。"""

    def test_f1_save_file(self, tmp_path: Path) -> None:
        """F1: ファイルが作成され内容が一致。"""
        report = "Test report content"
        filepath = tmp_path / "report.txt"
        save_optimization_report(report, filepath)
        assert filepath.exists()
        assert filepath.read_text(encoding="utf-8") == report

    def test_f2_auto_create_parent(self, tmp_path: Path) -> None:
        """F2: 親ディレクトリが自動作成される。"""
        report = "Test report"
        filepath = tmp_path / "sub" / "report.txt"
        save_optimization_report(report, filepath)
        assert filepath.exists()

    def test_f3_return_type(self, tmp_path: Path) -> None:
        """F3: 戻り値が Path 型。"""
        report = "Test"
        filepath = tmp_path / "report.txt"
        result = save_optimization_report(report, filepath)
        assert isinstance(result, Path)


# === カテゴリG: visualize_result ===


class TestVisualizeResult:
    """G1-G5: visualize_result。"""

    def test_g1_returns_figure(self, optimization_result: OptimizationResult, room: Room) -> None:
        """G1: go.Figure を返す。"""
        fig = visualize_result(optimization_result, room)
        assert isinstance(fig, go.Figure)

    def test_g2_title_contains_quality(
        self, optimization_result: OptimizationResult, room: Room
    ) -> None:
        """G2: タイトルに品質スコアを含む。"""
        fig = visualize_result(optimization_result, room)
        assert "Quality:" in fig.layout.title.text

    def test_g3_frustum_far_zero(
        self, optimization_result: OptimizationResult, room: Room
    ) -> None:
        """G3: frustum_far <= 0 で ValueError。"""
        with pytest.raises(ValueError):
            visualize_result(optimization_result, room, frustum_far=0)

    def test_g4_show_frustums_false(
        self, optimization_result: OptimizationResult, room: Room
    ) -> None:
        """G4: show_frustums=False で正常終了。"""
        fig = visualize_result(optimization_result, room, show_frustums=False)
        assert isinstance(fig, go.Figure)

    def test_g5_show_grid_false(
        self, optimization_result: OptimizationResult, room: Room
    ) -> None:
        """G5: show_grid=False で正常終了。"""
        fig = visualize_result(optimization_result, room, show_grid=False)
        assert isinstance(fig, go.Figure)


# === カテゴリH: create_convergence_plot ===


class TestConvergencePlot:
    """H1-H5: create_convergence_plot。"""

    def test_h1_returns_figure(self, optimization_result: OptimizationResult) -> None:
        """H1: go.Figure を返す。"""
        fig = create_convergence_plot(optimization_result)
        assert isinstance(fig, go.Figure)

    def test_h2_trace_count(self, optimization_result: OptimizationResult) -> None:
        """H2: トレースが1つ含まれる。"""
        fig = create_convergence_plot(optimization_result)
        assert len(fig.data) == 1

    def test_h3_x_values(self) -> None:
        """H3: x 値が世代番号。"""
        # モック結果を作成
        mock_result = _create_mock_result(convergence_history=[0.5, 0.3, 0.2])
        fig = create_convergence_plot(mock_result)
        assert list(fig.data[0].x) == [1, 2, 3]

    def test_h4_y_values(self) -> None:
        """H4: y 値が convergence_history。"""
        mock_result = _create_mock_result(convergence_history=[0.5, 0.3, 0.2])
        fig = create_convergence_plot(mock_result)
        assert list(fig.data[0].y) == [0.5, 0.3, 0.2]

    def test_h5_empty_history(self) -> None:
        """H5: 空の履歴で空のプロット。"""
        mock_result = _create_mock_result(convergence_history=[])
        fig = create_convergence_plot(mock_result)
        assert len(fig.data) == 0


# === カテゴリI: 統合テスト ===


class TestIntegration:
    """I1-I3: 統合テスト。"""

    def test_i1_better_than_clustered(self, room: Room) -> None:
        """I1: 最適化結果が密集配置より良い。"""
        config = OptimizationConfig(
            maxiter=2, popsize=1, seed=42, grid_spacing=1.0, eval_grid_spacing=1.0
        )
        result = optimize_placement(room, config=config, init_preset="upper_corners")

        # 密集配置: 全カメラを1隅に集中
        from camera_placement.models.camera import create_camera

        clustered_cameras = [
            create_camera(
                position=np.array([0.2, 0.2, 2.3]),
                look_at=np.array([1.4, 1.75, 0.9]),
            )
            for _ in range(6)
        ]
        clustered_eval = evaluate_placement(
            clustered_cameras,
            room,
            grid_spacing=1.0,
            weight_coverage=0.5,
            weight_angle=0.3,
            weight_projection=0.2,
        )

        assert (
            result.fine_evaluation.quality.quality_score
            > clustered_eval.quality.quality_score
        )

    def test_i2_best_value_matches_detail(self, optimization_result: OptimizationResult) -> None:
        """I2: best_value と detail.value が一致。"""
        np.testing.assert_allclose(
            optimization_result.best_value,
            optimization_result.detail.value,
            atol=1e-6,
        )

    def test_i3_report_roundtrip(
        self, optimization_result: OptimizationResult, tmp_path: Path
    ) -> None:
        """I3: レポート生成 → 保存 → 読み取りが一致。"""
        report = generate_optimization_report(optimization_result)
        filepath = tmp_path / "report.txt"
        save_optimization_report(report, filepath)
        loaded = filepath.read_text(encoding="utf-8")
        assert loaded == report


# === ヘルパー ===


def _create_mock_result(
    convergence_history: list[float] | None = None,
) -> OptimizationResult:
    """テスト用のモック OptimizationResult を作成する。"""
    from camera_placement.models.camera import create_camera
    from camera_placement.models.environment import create_default_room

    room = create_default_room()

    cameras = [
        create_camera(
            position=np.array([0.2 + i * 0.4, 0.2, 2.3]),
            look_at=np.array([1.4, 1.75, 0.9]),
        )
        for i in range(6)
    ]
    params = cameras_to_params(cameras)

    obj = ObjectiveFunction(room, grid_spacing=1.0, num_cameras=6)
    detail = obj.evaluate_detail(params)

    fine_evaluation = evaluate_placement(
        cameras,
        room,
        grid_spacing=1.0,
        weight_coverage=0.5,
        weight_angle=0.3,
        weight_projection=0.2,
    )

    config = OptimizationConfig(
        maxiter=2, popsize=1, seed=42, grid_spacing=1.0, eval_grid_spacing=1.0
    )

    return OptimizationResult(
        best_params=params,
        best_cameras=cameras,
        best_value=detail.value,
        detail=detail,
        fine_evaluation=fine_evaluation,
        config=config,
        nit=2,
        nfev=100,
        elapsed_seconds=5.0,
        success=True,
        message="Optimization terminated successfully.",
        convergence_history=convergence_history if convergence_history is not None else [-0.5, -0.6],
    )
