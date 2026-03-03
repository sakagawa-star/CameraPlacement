"""F13: 配置比較・レポート。

F12 で定義された配置プリセットを F10 の evaluate_placement で評価し、
プリセット間の品質スコアを比較・テキストレポートとして出力する。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from camera_placement.evaluation.evaluator import EvaluationResult, evaluate_placement
from camera_placement.models.activity import ActivityType
from camera_placement.models.environment import Room
from camera_placement.placement.patterns import (
    PlacementPreset,
    create_cameras,
    get_all_presets,
)


@dataclass
class PresetEvaluation:
    """1つのプリセットの評価結果。

    Attributes:
        preset: 評価対象のプリセット。
        evaluation: evaluate_placement の結果。
    """

    preset: PlacementPreset
    evaluation: EvaluationResult


@dataclass(frozen=True)
class EvaluationParams:
    """評価パラメータ。レポート出力用に保持する。

    Attributes:
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。
    """

    grid_spacing: float
    near: float
    far: float
    target_ppm: float
    weight_coverage: float
    weight_angle: float
    weight_projection: float


@dataclass
class ComparisonResult:
    """複数プリセットの比較結果。

    Attributes:
        rankings: 統合品質スコアの降順でソートされたプリセット評価結果。
        best: 最良のプリセット評価結果。rankings[0] と同一オブジェクト。
        evaluation_params: 評価に使用したパラメータ。
    """

    rankings: list[PresetEvaluation]
    best: PresetEvaluation
    evaluation_params: EvaluationParams


def evaluate_preset(
    preset: PlacementPreset,
    room: Room,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
    target_ppm: float = 500.0,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> PresetEvaluation:
    """単一プリセットを評価する。

    Args:
        preset: 評価対象のプリセット。
        room: 病室モデル。
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。

    Returns:
        PresetEvaluation インスタンス。

    Raises:
        ValueError: create_cameras でカメラ位置が範囲外の場合。
        ValueError: evaluate_placement で重みが不正の場合。
    """
    cameras = create_cameras(preset, room)
    evaluation = evaluate_placement(
        cameras,
        room,
        grid_spacing=grid_spacing,
        near=near,
        far=far,
        target_ppm=target_ppm,
        weight_coverage=weight_coverage,
        weight_angle=weight_angle,
        weight_projection=weight_projection,
    )
    return PresetEvaluation(preset=preset, evaluation=evaluation)


def compare_presets(
    room: Room,
    presets: list[PlacementPreset] | None = None,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
    target_ppm: float = 500.0,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
) -> ComparisonResult:
    """複数プリセットを一括比較する。

    Args:
        room: 病室モデル。
        presets: 比較対象のプリセット。None の場合は get_all_presets() で全プリセットを取得。
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。

    Returns:
        ComparisonResult インスタンス。

    Raises:
        ValueError: presets が空リストの場合。
        ValueError: create_cameras でカメラ位置が範囲外の場合。
        ValueError: evaluate_placement で重みが不正の場合。
    """
    if presets is None:
        presets = get_all_presets()
    if len(presets) == 0:
        raise ValueError("presets must not be empty")

    evaluations = []
    for preset in presets:
        pe = evaluate_preset(
            preset,
            room,
            grid_spacing=grid_spacing,
            near=near,
            far=far,
            target_ppm=target_ppm,
            weight_coverage=weight_coverage,
            weight_angle=weight_angle,
            weight_projection=weight_projection,
        )
        evaluations.append(pe)

    rankings = sorted(
        evaluations,
        key=lambda pe: pe.evaluation.quality.quality_score,
        reverse=True,
    )

    params = EvaluationParams(
        grid_spacing=grid_spacing,
        near=near,
        far=far,
        target_ppm=target_ppm,
        weight_coverage=weight_coverage,
        weight_angle=weight_angle,
        weight_projection=weight_projection,
    )

    return ComparisonResult(
        rankings=rankings,
        best=rankings[0],
        evaluation_params=params,
    )


def generate_report(result: ComparisonResult) -> str:
    """比較結果からテキストレポートを生成する。

    Args:
        result: 比較結果。

    Returns:
        複数行のテキストレポート。
    """
    lines: list[str] = []

    # ヘッダー
    lines.append("=== Camera Placement Comparison Report ===")
    lines.append("")

    # 評価パラメータ
    params = result.evaluation_params
    lines.append("Evaluation Parameters:")
    lines.append(f"  Grid Spacing: {params.grid_spacing} m")
    lines.append(f"  Near Clip: {params.near} m")
    lines.append(f"  Far Clip: {params.far} m")
    lines.append(f"  Target PPM: {params.target_ppm} px/m")
    lines.append(
        f"  Weights: coverage={params.weight_coverage}, "
        f"angle={params.weight_angle}, "
        f"projection={params.weight_projection}"
    )
    lines.append("")

    # ランキング表
    lines.append("Overall Ranking:")
    lines.append(
        f"{'Rank':<6}{'Preset':<20}{'Quality':>10}"
        f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}"
    )
    lines.append("-" * 66)
    for i, pe in enumerate(result.rankings):
        q = pe.evaluation.quality
        lines.append(
            f"{i + 1:<6}{pe.preset.name:<20}{q.quality_score:>10.3f}"
            f"{q.coverage_score:>10.3f}{q.angle_score:>10.3f}"
            f"{q.projection_score:>10.3f}"
        )
    lines.append("")

    # 活動ボリューム別比較表
    for act_type in [ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE]:
        lines.append(f"Volume: {act_type.value}")
        lines.append(
            f"{'Rank':<6}{'Preset':<20}{'Quality':>10}"
            f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}"
        )
        lines.append("-" * 66)
        volume_rankings = sorted(
            result.rankings,
            key=lambda pe, at=act_type: (
                pe.evaluation.volume_qualities[at].quality_score
                if at in pe.evaluation.volume_qualities
                else 0.0
            ),
            reverse=True,
        )
        for i, pe in enumerate(volume_rankings):
            if act_type in pe.evaluation.volume_qualities:
                vq = pe.evaluation.volume_qualities[act_type]
                lines.append(
                    f"{i + 1:<6}{pe.preset.name:<20}{vq.quality_score:>10.3f}"
                    f"{vq.coverage_score:>10.3f}{vq.angle_score:>10.3f}"
                    f"{vq.projection_score:>10.3f}"
                )
            else:
                lines.append(
                    f"{i + 1:<6}{pe.preset.name:<20}{'N/A':>10}"
                    f"{'N/A':>10}{'N/A':>10}{'N/A':>10}"
                )
        lines.append("")

    # ベストプリセットサマリー
    best = result.best
    lines.append("Best Preset:")
    lines.append(f"  Name: {best.preset.name}")
    lines.append(f"  Description: {best.preset.description}")
    lines.append(f"  Quality Score: {best.evaluation.quality.quality_score:.3f}")
    lines.append(f"  Coverage Score: {best.evaluation.quality.coverage_score:.3f}")
    lines.append(f"  Angle Score: {best.evaluation.quality.angle_score:.3f}")
    lines.append(f"  Projection Score: {best.evaluation.quality.projection_score:.3f}")

    return "\n".join(lines)


def save_report(report: str, filepath: str | Path) -> Path:
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
