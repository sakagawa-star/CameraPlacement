"""F15: 最適化エンジン・結果出力。

scipy.optimize.differential_evolution を使用して6台カメラの最適配置を探索する。
最適化結果のテキストレポート生成と3D可視化機能を含む。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from scipy.optimize import differential_evolution

from camera_placement.evaluation.evaluator import (
    EvaluationResult,
    evaluate_placement,
)
from camera_placement.models.activity import ActivityType
from camera_placement.models.camera import Camera
from camera_placement.models.environment import Room
from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    cameras_to_params,
    params_to_cameras,
)
from camera_placement.placement.patterns import create_cameras, get_preset
from camera_placement.visualization.viewer import create_scene

logger = logging.getLogger("camera_placement.optimization.optimizer")


@dataclass(frozen=True)
class OptimizationConfig:
    """最適化の設定パラメータ。

    Attributes:
        maxiter: DE の最大世代数。1 以上。
        popsize: 集団サイズ乗数。実際の集団サイズは popsize × n_params。1 以上。
        tol: 収束判定の相対許容誤差。0 以上。
        mutation: DE の突然変異定数の範囲 (dithering)。各要素は (0, 2]。
        recombination: DE の交叉確率。[0, 1]。
        seed: 乱数シード。None の場合は再現性なし。
        strategy: DE の戦略名。
        polish: True の場合、DE 完了後に L-BFGS-B で局所探索を行う。
        grid_spacing: 最適化中のグリッド間隔 [m]。
        eval_grid_spacing: 最適化後の最終評価グリッド間隔 [m]。
        penalty_weight: ペナルティ係数。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。
        num_cameras: カメラ台数。
    """

    maxiter: int = 50
    popsize: int = 5
    tol: float = 0.01
    mutation: tuple[float, float] = (0.5, 1.0)
    recombination: float = 0.7
    seed: int | None = None
    strategy: str = "best1bin"
    polish: bool = False
    grid_spacing: float = 0.5
    eval_grid_spacing: float = 0.2
    penalty_weight: float = 100.0
    weight_coverage: float = 0.5
    weight_angle: float = 0.3
    weight_projection: float = 0.2
    num_cameras: int = 6

    def __post_init__(self) -> None:
        """バリデーション。"""
        if self.maxiter < 1:
            raise ValueError("maxiter must be >= 1")
        if self.popsize < 1:
            raise ValueError("popsize must be >= 1")
        if self.tol < 0:
            raise ValueError("tol must be >= 0")
        if len(self.mutation) != 2:
            raise ValueError("mutation must be a 2-tuple")
        if self.mutation[0] <= 0 or self.mutation[0] > 2:
            raise ValueError("mutation values must be in (0, 2]")
        if self.mutation[1] <= 0 or self.mutation[1] > 2:
            raise ValueError("mutation values must be in (0, 2]")
        if self.recombination < 0 or self.recombination > 1:
            raise ValueError("recombination must be in [0, 1]")
        if self.grid_spacing <= 0:
            raise ValueError("grid_spacing must be > 0")
        if self.eval_grid_spacing <= 0:
            raise ValueError("eval_grid_spacing must be > 0")
        if self.penalty_weight < 0:
            raise ValueError("penalty_weight must be >= 0")
        if self.weight_coverage < 0 or self.weight_angle < 0 or self.weight_projection < 0:
            raise ValueError("weights must be non-negative")
        if self.weight_coverage + self.weight_angle + self.weight_projection == 0:
            raise ValueError("sum of weights must be positive")
        if self.num_cameras < 1:
            raise ValueError("num_cameras must be >= 1")


@dataclass
class OptimizationResult:
    """最適化の結果。

    Attributes:
        best_params: 最良パラメータベクトル。shape (num_cameras * 6,)。
        best_cameras: 最良パラメータから復元した Camera リスト。
        best_value: 最良目的関数値（最適化グリッドでの値）。
        detail: 最良パラメータの詳細結果（最適化グリッドでの ObjectiveResult）。
        fine_evaluation: 最良パラメータの評価グリッドでの F10 評価結果。
        config: 使用した最適化設定。
        nit: 実行した世代数。
        nfev: 目的関数の呼び出し回数。
        elapsed_seconds: 最適化の所要時間 [秒]。
        success: scipy DE の収束判定結果。
        message: scipy DE の終了メッセージ。
        convergence_history: 各世代の最良目的関数値。
    """

    best_params: np.ndarray
    best_cameras: list[Camera]
    best_value: float
    detail: ObjectiveResult
    fine_evaluation: EvaluationResult
    config: OptimizationConfig
    nit: int
    nfev: int
    elapsed_seconds: float
    success: bool
    message: str
    convergence_history: list[float]


def optimize_placement(
    room: Room,
    config: OptimizationConfig | None = None,
    init_preset: str | None = None,
    init_params: np.ndarray | None = None,
) -> OptimizationResult:
    """カメラ配置を最適化する。

    scipy.optimize.differential_evolution を使用して、
    F14 の目的関数を最小化する最適なカメラ配置を探索する。

    Args:
        room: 病室モデル。
        config: 最適化設定。None の場合は OptimizationConfig() を使用。
        init_preset: 初期解として使用する F12 プリセット名。
            指定した場合、プリセットのカメラ配置をパラメータベクトルに変換し、
            differential_evolution の x0 パラメータに渡す。
        init_params: 初期解のパラメータベクトル。shape (num_cameras * 6,)。
            init_preset と同時に指定することはできない。

    Returns:
        OptimizationResult インスタンス。

    Raises:
        ValueError: init_preset と init_params の両方が指定された場合。
        ValueError: init_params の shape が (num_cameras * 6,) でない場合。
        KeyError: init_preset に存在しないプリセット名が指定された場合。
    """
    # Step 1: 設定の準備
    if config is None:
        config = OptimizationConfig()

    # Step 2: 初期解の検証
    if init_preset is not None and init_params is not None:
        raise ValueError("Cannot specify both init_preset and init_params")

    # Step 3: 初期解の準備
    x0 = None
    if init_preset is not None:
        preset = get_preset(init_preset)
        cameras = create_cameras(preset, room)
        x0 = cameras_to_params(cameras)
    elif init_params is not None:
        init_params = np.asarray(init_params, dtype=np.float64)
        expected = (config.num_cameras * 6,)
        if init_params.shape != expected:
            raise ValueError(
                f"init_params must have shape {expected}, got {init_params.shape}"
            )
        x0 = init_params

    # Step 4: 目的関数の初期化（最適化グリッド）
    obj = ObjectiveFunction(
        room,
        grid_spacing=config.grid_spacing,
        penalty_weight=config.penalty_weight,
        weight_coverage=config.weight_coverage,
        weight_angle=config.weight_angle,
        weight_projection=config.weight_projection,
        num_cameras=config.num_cameras,
    )

    # x0 を bounds の内側にクリップ（scipy DE の内部スケーリングで
    # 浮動小数点精度により境界上の値がわずかに外れる問題を防止）
    if x0 is not None:
        _eps = 1e-10
        x0 = np.clip(x0, obj.bounds[:, 0] + _eps, obj.bounds[:, 1] - _eps)

    # Step 5: 収束履歴コールバックの準備
    convergence_history: list[float] = []

    def _callback(intermediate_result: object) -> None:
        convergence_history.append(float(intermediate_result.fun))  # type: ignore[attr-defined]
        gen = len(convergence_history)
        logger.info(
            "Generation %d: best_value=%.6f",
            gen,
            intermediate_result.fun,  # type: ignore[attr-defined]
        )

    # Step 6: bounds の準備
    bounds_list = list(
        zip(obj.bounds[:, 0].tolist(), obj.bounds[:, 1].tolist())
    )

    n_params = config.num_cameras * 6
    logger.info(
        "Starting optimization: maxiter=%d, popsize=%d, n_params=%d",
        config.maxiter,
        config.popsize,
        n_params,
    )

    # Step 7: 計時開始
    start_time = time.monotonic()

    # Step 8: differential_evolution 実行
    scipy_result = differential_evolution(
        func=obj,
        bounds=bounds_list,
        maxiter=config.maxiter,
        popsize=config.popsize,
        tol=config.tol,
        mutation=config.mutation,
        recombination=config.recombination,
        seed=config.seed,
        strategy=config.strategy,
        polish=config.polish,
        callback=_callback,
        x0=x0,
        init="latinhypercube",
        updating="immediate",
        workers=1,
        disp=False,
    )

    # Step 9: 計時終了
    elapsed = time.monotonic() - start_time

    logger.info(
        "Optimization completed: nit=%d, nfev=%d, elapsed=%.1fs, success=%s",
        scipy_result.nit,
        scipy_result.nfev,
        elapsed,
        scipy_result.success,
    )

    # Step 10: 最良パラメータの詳細評価（最適化グリッド）
    best_params = scipy_result.x
    detail = obj.evaluate_detail(best_params)
    best_cameras = params_to_cameras(best_params, config.num_cameras)

    # Step 11: 最良パラメータの最終評価（評価グリッド）
    logger.info("Running final evaluation with grid_spacing=%.2f", config.eval_grid_spacing)
    fine_evaluation = evaluate_placement(
        best_cameras,
        room,
        grid_spacing=config.eval_grid_spacing,
        weight_coverage=config.weight_coverage,
        weight_angle=config.weight_angle,
        weight_projection=config.weight_projection,
    )
    logger.info("Final quality_score=%.3f", fine_evaluation.quality.quality_score)

    # Step 12: 結果を返す
    return OptimizationResult(
        best_params=best_params,
        best_cameras=best_cameras,
        best_value=float(scipy_result.fun),
        detail=detail,
        fine_evaluation=fine_evaluation,
        config=config,
        nit=int(scipy_result.nit),
        nfev=int(scipy_result.nfev),
        elapsed_seconds=elapsed,
        success=bool(scipy_result.success),
        message=str(scipy_result.message),
        convergence_history=convergence_history,
    )


def generate_optimization_report(result: OptimizationResult) -> str:
    """最適化結果のテキストレポートを生成する。

    Args:
        result: 最適化結果。

    Returns:
        複数行のテキストレポート。
    """
    lines: list[str] = []
    cfg = result.config

    # ヘッダー
    lines.append("=== Camera Placement Optimization Report ===")
    lines.append("")

    # 最適化パラメータ
    actual_pop = cfg.popsize * cfg.num_cameras * 6
    lines.append("Optimization Parameters:")
    lines.append("  Algorithm: differential_evolution")
    lines.append(f"  Strategy: {cfg.strategy}")
    lines.append(f"  Max Iterations: {cfg.maxiter}")
    lines.append(f"  Population Size: {cfg.popsize} (actual: {actual_pop})")
    lines.append(f"  Tolerance: {cfg.tol}")
    lines.append(f"  Mutation: ({cfg.mutation[0]}, {cfg.mutation[1]})")
    lines.append(f"  Recombination: {cfg.recombination}")
    lines.append(f"  Polish: {cfg.polish}")
    lines.append(f"  Seed: {cfg.seed}")
    lines.append(f"  Optimization Grid Spacing: {cfg.grid_spacing} m")
    lines.append(f"  Evaluation Grid Spacing: {cfg.eval_grid_spacing} m")
    lines.append(f"  Penalty Weight: {cfg.penalty_weight}")
    lines.append(
        f"  Weights: coverage={cfg.weight_coverage}, "
        f"angle={cfg.weight_angle}, "
        f"projection={cfg.weight_projection}"
    )
    lines.append(f"  Num Cameras: {cfg.num_cameras}")
    lines.append("")

    # 最適化結果サマリー
    lines.append("Optimization Results:")
    lines.append(f"  Iterations: {result.nit}")
    lines.append(f"  Function Evaluations: {result.nfev}")
    if result.elapsed_seconds >= 60:
        lines.append(f"  Elapsed Time: {result.elapsed_seconds / 60:.1f} min")
    else:
        lines.append(f"  Elapsed Time: {result.elapsed_seconds:.1f} sec")
    lines.append(f"  Success: {result.success}")
    lines.append(f"  Message: {result.message}")
    lines.append(f"  Optimization Objective Value: {result.best_value:.6f}")
    lines.append("")

    # 品質スコア（評価グリッド）
    q = result.fine_evaluation.quality
    lines.append(f"Final Evaluation (grid_spacing={cfg.eval_grid_spacing}):")
    lines.append(f"  Quality Score: {q.quality_score:.3f}")
    lines.append(f"  Coverage Score: {q.coverage_score:.3f}")
    lines.append(f"  Angle Score: {q.angle_score:.3f}")
    lines.append(f"  Projection Score: {q.projection_score:.3f}")
    lines.append("")

    # 活動ボリューム別品質スコア
    lines.append("Volume Quality:")
    lines.append(
        f"{'Rank':<6}{'Volume':<20}{'Quality':>10}"
        f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}"
    )
    lines.append("-" * 66)
    volume_items = []
    for act_type in [ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE]:
        if act_type in result.fine_evaluation.volume_qualities:
            volume_items.append(
                (act_type, result.fine_evaluation.volume_qualities[act_type])
            )
    volume_items.sort(key=lambda item: item[1].quality_score, reverse=True)
    for rank, (act_type, vq) in enumerate(volume_items, 1):
        lines.append(
            f"{rank:<6}{act_type.value:<20}{vq.quality_score:>10.3f}"
            f"{vq.coverage_score:>10.3f}{vq.angle_score:>10.3f}"
            f"{vq.projection_score:>10.3f}"
        )
    lines.append("")

    # カメラ配置
    lines.append("Camera Placement:")
    for i, cam in enumerate(result.best_cameras):
        pos = cam.position
        la = cam.look_at
        lines.append(
            f"  Camera {i + 1}: "
            f"position=({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}), "
            f"look_at=({la[0]:.3f}, {la[1]:.3f}, {la[2]:.3f})"
        )

    return "\n".join(lines)


def save_optimization_report(report: str, filepath: str | Path) -> Path:
    """テキストレポートをファイルに保存する。

    Args:
        report: レポートテキスト。
        filepath: 保存先のファイルパス。

    Returns:
        保存先の Path オブジェクト。
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def visualize_result(
    result: OptimizationResult,
    room: Room,
    show_frustums: bool = True,
    show_grid: bool = True,
    frustum_far: float = 3.0,
) -> go.Figure:
    """最適化結果の3D可視化を生成する。

    F11 の create_scene を使用して、最適化されたカメラ配置と
    カバレッジマップを3Dインタラクティブ表示する。

    Args:
        result: 最適化結果。
        room: 病室モデル。
        show_frustums: True の場合、視錐台を表示する。
        show_grid: True の場合、カバレッジマップを表示する。
        frustum_far: 視錐台の表示用ファークリップ距離 [m]。0 より大きい。

    Returns:
        go.Figure インスタンス。

    Raises:
        ValueError: frustum_far <= 0 の場合。
    """
    if frustum_far <= 0:
        raise ValueError("frustum_far must be > 0")

    quality = result.fine_evaluation.quality.quality_score
    title = f"Optimized Camera Placement (Quality: {quality:.3f})"

    fig = create_scene(
        room=room,
        cameras=result.best_cameras,
        coverage_result=result.fine_evaluation.coverage_result,
        show_frustums=show_frustums,
        show_grid=show_grid,
        frustum_far=frustum_far,
        title=title,
    )

    return fig


def create_convergence_plot(result: OptimizationResult) -> go.Figure:
    """収束履歴のプロットを生成する。

    Args:
        result: 最適化結果。

    Returns:
        go.Figure インスタンス。
        convergence_history が空の場合は空のプロットを返す。
    """
    history = result.convergence_history

    if len(history) == 0:
        fig = go.Figure()
    else:
        generations = list(range(1, len(history) + 1))
        trace = go.Scatter(
            x=generations,
            y=history,
            mode="lines+markers",
            line=dict(color="rgb(31, 119, 180)"),
            marker=dict(size=4),
            name="Best Objective Value",
        )
        fig = go.Figure(data=[trace])

    fig.update_layout(
        title="Convergence History",
        xaxis_title="Generation",
        yaxis_title="Best Objective Value",
        width=800,
        height=500,
    )

    return fig
