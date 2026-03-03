# 機能設計書: F13 配置比較・レポート

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 4.1 `evaluate_preset` |
| FR-02 | 4.2 `compare_presets` |
| FR-03 | 4.3 `generate_report` |
| FR-04 | 4.4 `save_report` |

## 2. ファイル構成

```
src/camera_placement/
  placement/
    __init__.py             # 更新: F13 の公開シンボルを追加
    patterns.py             # 既存 (F12)
    comparison.py           # 新規作成: F13 メインモジュール
tests/
  test_comparison.py        # 新規作成: F13 テスト
tests/results/
  F13_test_result.txt       # テスト結果
```

## 3. データ構造

### 3.1 `PresetEvaluation`

```python
@dataclass
class PresetEvaluation:
    """1つのプリセットの評価結果。

    Attributes:
        preset: 評価対象のプリセット。
        evaluation: evaluate_placement の結果。
    """

    preset: PlacementPreset
    evaluation: EvaluationResult
```

- `dataclass`（`frozen` なし）。不変性の強制は不要
- `preset` から名前・説明を、`evaluation` から全スコアを取得できる

### 3.2 `ComparisonResult`

```python
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
```

### 3.3 `EvaluationParams`

```python
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
```

- `frozen=True` で不変オブジェクトとする。パラメータは一度設定したら変更しない

## 4. 公開関数設計

### 4.1 `evaluate_preset`

```python
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
```

**処理ロジック**:
```
入力: preset, room, 評価パラメータ
  │
  ├── Step 1: Camera オブジェクト生成
  │     cameras = create_cameras(preset, room)
  │
  ├── Step 2: 一括評価
  │     evaluation = evaluate_placement(
  │         cameras, room,
  │         grid_spacing=grid_spacing,
  │         near=near, far=far,
  │         target_ppm=target_ppm,
  │         weight_coverage=weight_coverage,
  │         weight_angle=weight_angle,
  │         weight_projection=weight_projection,
  │     )
  │
  └── Step 3: 結果を返す
        return PresetEvaluation(preset=preset, evaluation=evaluation)
```

### 4.2 `compare_presets`

```python
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
```

**処理ロジック**:
```
入力: room, presets, 評価パラメータ
  │
  ├── Step 1: プリセット取得
  │     if presets is None:
  │         presets = get_all_presets()
  │     if len(presets) == 0:
  │         raise ValueError("presets must not be empty")
  │
  ├── Step 2: 各プリセットを評価
  │     evaluations = []
  │     for preset in presets:
  │         pe = evaluate_preset(
  │             preset, room,
  │             grid_spacing=grid_spacing,
  │             near=near, far=far,
  │             target_ppm=target_ppm,
  │             weight_coverage=weight_coverage,
  │             weight_angle=weight_angle,
  │             weight_projection=weight_projection,
  │         )
  │         evaluations.append(pe)
  │
  ├── Step 3: ランキング（統合品質スコアの降順ソート）
  │     rankings = sorted(
  │         evaluations,
  │         key=lambda pe: pe.evaluation.quality.quality_score,
  │         reverse=True,
  │     )
  │     # sorted は安定ソートなので、同スコアの場合は入力順を保持する
  │
  ├── Step 4: EvaluationParams を作成
  │     params = EvaluationParams(
  │         grid_spacing=grid_spacing,
  │         near=near, far=far,
  │         target_ppm=target_ppm,
  │         weight_coverage=weight_coverage,
  │         weight_angle=weight_angle,
  │         weight_projection=weight_projection,
  │     )
  │
  └── Step 5: 結果を返す
        return ComparisonResult(
            rankings=rankings,
            best=rankings[0],
            evaluation_params=params,
        )
```

### 4.3 `generate_report`

```python
def generate_report(result: ComparisonResult) -> str:
    """比較結果からテキストレポートを生成する。

    Args:
        result: 比較結果。

    Returns:
        複数行のテキストレポート。
    """
```

**処理ロジック**:
```
入力: result (ComparisonResult)
  │
  ├── Step 1: ヘッダー
  │     lines = ["=== Camera Placement Comparison Report ===", ""]
  │
  ├── Step 2: 評価パラメータ
  │     params = result.evaluation_params
  │     lines.append("Evaluation Parameters:")
  │     lines.append(f"  Grid Spacing: {params.grid_spacing} m")
  │     lines.append(f"  Near Clip: {params.near} m")
  │     lines.append(f"  Far Clip: {params.far} m")
  │     lines.append(f"  Target PPM: {params.target_ppm} px/m")
  │     lines.append(f"  Weights: coverage={params.weight_coverage}, "
  │                  f"angle={params.weight_angle}, "
  │                  f"projection={params.weight_projection}")
  │     lines.append("")
  │
  ├── Step 3: ランキング表
  │     lines.append("Overall Ranking:")
  │     lines.append(f"{'Rank':<6}{'Preset':<20}{'Quality':>10}"
  │                  f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}")
  │     lines.append("-" * 66)
  │     for i, pe in enumerate(result.rankings):
  │         q = pe.evaluation.quality
  │         lines.append(
  │             f"{i + 1:<6}{pe.preset.name:<20}{q.quality_score:>10.3f}"
  │             f"{q.coverage_score:>10.3f}{q.angle_score:>10.3f}"
  │             f"{q.projection_score:>10.3f}"
  │         )
  │     lines.append("")
  │
  ├── Step 4: 活動ボリューム別比較表
  │     活動ボリューム = [WALKING, SEATED, SUPINE] (ActivityType の定義順)
  │     for act_type in [ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE]:
  │         lines.append(f"Volume: {act_type.value}")
  │         lines.append(f"{'Rank':<6}{'Preset':<20}{'Quality':>10}"
  │                      f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}")
  │         lines.append("-" * 66)
  │         # この活動ボリュームについてスコア降順でソートして表示
  │         volume_rankings = sorted(
  │             result.rankings,
  │             key=lambda pe: (
  │                 pe.evaluation.volume_qualities[act_type].quality_score
  │                 if act_type in pe.evaluation.volume_qualities
  │                 else 0.0
  │             ),
  │             reverse=True,
  │         )
  │         for i, pe in enumerate(volume_rankings):
  │             if act_type in pe.evaluation.volume_qualities:
  │                 vq = pe.evaluation.volume_qualities[act_type]
  │                 lines.append(
  │                     f"{i + 1:<6}{pe.preset.name:<20}{vq.quality_score:>10.3f}"
  │                     f"{vq.coverage_score:>10.3f}{vq.angle_score:>10.3f}"
  │                     f"{vq.projection_score:>10.3f}"
  │                 )
  │             else:
  │                 lines.append(
  │                     f"{i + 1:<6}{pe.preset.name:<20}{'N/A':>10}"
  │                     f"{'N/A':>10}{'N/A':>10}{'N/A':>10}"
  │                 )
  │         lines.append("")
  │
  ├── Step 5: ベストプリセットサマリー
  │     best = result.best
  │     lines.append("Best Preset:")
  │     lines.append(f"  Name: {best.preset.name}")
  │     lines.append(f"  Description: {best.preset.description}")
  │     lines.append(f"  Quality Score: {best.evaluation.quality.quality_score:.3f}")
  │     lines.append(f"  Coverage Score: {best.evaluation.quality.coverage_score:.3f}")
  │     lines.append(f"  Angle Score: {best.evaluation.quality.angle_score:.3f}")
  │     lines.append(f"  Projection Score: {best.evaluation.quality.projection_score:.3f}")
  │
  └── return "\n".join(lines)
```

**レポート出力例**:
```
=== Camera Placement Comparison Report ===

Evaluation Parameters:
  Grid Spacing: 0.2 m
  Near Clip: 0.1 m
  Far Clip: 10.0 m
  Target PPM: 500.0 px/m
  Weights: coverage=0.5, angle=0.3, projection=0.2

Overall Ranking:
Rank  Preset                Quality  Coverage     Angle Projection
------------------------------------------------------------------
1     hybrid                  0.782     0.950     0.623     0.548
2     wall_uniform            0.755     0.920     0.612     0.530
3     upper_corners           0.740     0.900     0.600     0.520
4     bed_focused             0.680     0.800     0.580     0.510
5     overhead_grid           0.650     0.850     0.400     0.480

Volume: walking
Rank  Preset                Quality  Coverage     Angle Projection
------------------------------------------------------------------
1     wall_uniform            0.780     0.950     0.620     0.550
2     hybrid                  0.770     0.940     0.610     0.540
3     upper_corners           0.760     0.930     0.600     0.530
4     overhead_grid           0.700     0.900     0.420     0.500
5     bed_focused             0.550     0.600     0.500     0.480

Volume: seated
Rank  Preset                Quality  Coverage     Angle Projection
------------------------------------------------------------------
...

Volume: supine
Rank  Preset                Quality  Coverage     Angle Projection
------------------------------------------------------------------
...

Best Preset:
  Name: hybrid
  Description: ハイブリッド型: 上部4隅で広範囲カバレッジ + 壁面中段2台でベッド角度改善
  Quality Score: 0.782
  Coverage Score: 0.950
  Angle Score: 0.623
  Projection Score: 0.548
```

**注意**: 上記のスコア数値はレイアウト例示用のダミー値であり、実際の計算結果とは異なる。

### 4.4 `save_report`

```python
def save_report(report: str, filepath: str | Path) -> Path:
    """テキストレポートをファイルに保存する。

    Args:
        report: レポートテキスト。
        filepath: 保存先のファイルパス。

    Returns:
        保存先の Path オブジェクト。
    """
```

**処理ロジック**:
```
入力: report (str), filepath (str | Path)
  │
  ├── path = Path(filepath)
  ├── path.parent.mkdir(parents=True, exist_ok=True)
  ├── path.write_text(report, encoding="utf-8")
  └── return path
```

## 5. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| presets が空リスト | `ValueError("presets must not be empty")` を送出 | `compare_presets` |
| カメラ位置がカメラ設置可能領域外 | `ValueError`（`create_cameras` 経由） | `evaluate_preset` |
| 重みが不正（負値、合計0） | `ValueError`（`evaluate_placement` 経由） | `evaluate_preset` |
| ファイル書き込み失敗 | OSError を呼び出し元に伝搬 | `save_report` |

## 6. 境界条件

| ケース | 期待動作 |
|--------|---------|
| presets=None | `get_all_presets()` で5つのプリセットを取得 |
| presets が1要素 | rankings は1要素、best はその1つ |
| presets が空リスト | `ValueError` |
| 全プリセットが同一スコア | rankings の順序は入力順を保持 |
| volume_qualities に活動ボリュームが存在しない | レポートで "N/A" と表示 |

## 7. モジュール間依存関係

### 7.1 F10（統合品質スコア）

- `evaluate_placement(cameras, room, ...)` で一括評価
- `EvaluationResult`, `QualityScoreResult`, `VolumeQualityScore` を結果参照に使用
- インポート: `from camera_placement.evaluation.evaluator import evaluate_placement, EvaluationResult`

### 7.2 F12（配置パターン定義）

- `get_all_presets()` で全プリセットを取得
- `create_cameras(preset, room)` で Camera オブジェクトを生成
- `PlacementPreset` を型ヒントに使用
- インポート: `from camera_placement.placement.patterns import PlacementPreset, get_all_presets, create_cameras`

### 7.3 F01（空間モデル）

- `Room` を型ヒントに使用
- インポート: `from camera_placement.models.environment import Room`

### 7.4 F03（活動ボリューム）

- `ActivityType` を活動ボリューム別比較で使用
- インポート: `from camera_placement.models.activity import ActivityType`

## 8. 設計判断

### 8.1 ComparisonResult に EvaluationParams を保持する理由

- **採用案**: `EvaluationParams` データクラスで評価パラメータを保持
- **却下案**: パラメータを保持せず、レポート生成時に別途渡す
  - 却下理由: 評価パラメータはレポートに出力する重要な情報。比較結果と一体で管理することで、後から「どのパラメータで評価したか」を追跡できる。`generate_report` の引数も減り、使いやすくなる

### 8.2 ランキングのソートキーを quality_score のみとする理由

- **採用案**: `quality_score` の降順のみでソート
- **却下案**: 複合キー（quality_score, coverage_score, angle_score の順）でソート
  - 却下理由: F10 の `quality_score` は3つのコンポーネントを加重和で統合したスコアであり、単一スコアでの比較が F10 の設計意図に合致する。複合キーは判断基準が曖昧になる

### 8.3 可視化をスコープ外とする理由

- **採用案**: F13 はデータ処理とテキストレポートのみ。可視化は呼び出し元が F11 を直接使用する
- **却下案**: F13 内で比較用の可視化（複数プリセットの並列表示）も生成する
  - 却下理由: F13 の責務を明確にする。可視化は F11 の責務であり、F13 は評価・比較ロジックに集中する。呼び出し元は `PresetEvaluation.evaluation.coverage_result` を F11 に渡すことで可視化できる

### 8.4 活動ボリューム別比較表のソートをボリュームごとに行う理由

- **採用案**: 各活動ボリュームの比較表で、そのボリュームの `quality_score` の降順でソート
- **却下案**: 全体ランキングと同じ順序で表示
  - 却下理由: 活動ボリュームごとに最適なプリセットは異なり得る（例: 歩行では wall_uniform が最良だが、臥位では bed_focused が最良）。ボリュームごとにソートすることで、各動作に最適な配置が一目でわかる

### 8.5 レポートを英語表記とする理由

- **採用案**: レポートのラベル・ヘッダーは英語
- **却下案**: 日本語
  - 却下理由: プリセット名が英語スネークケースであり、コード内の変数名やデータ構造名も英語。レポート全体を英語にすることで一貫性を保つ。ただし `preset.description` は日本語のため、ベストプリセットサマリーには日本語が含まれる

## 9. ログ・デバッグ設計

F13 はログ出力を行わない。`evaluate_preset` での各プリセットの評価は `evaluate_placement` に委譲しており、評価処理自体のログは F07〜F10 の責務。F13 のエラーは例外（`ValueError`）として呼び出し元に伝搬する。

## 10. ファイル・ディレクトリ設計

### 10.1 レポートファイル

- パス: 呼び出し元が指定する。推奨パスは `reports/comparison_report.txt`
- エンコーディング: UTF-8
- 改行コード: プラットフォーム依存（`\n`）

### 10.2 `save_report` の出力

- `path.parent.mkdir(parents=True, exist_ok=True)` で親ディレクトリを自動作成
- `path.write_text(report, encoding="utf-8")` でファイル書き込み

## 11. 技術スタック

- **Python**: 3.12
- **numpy** (>=2.4.2): 直接使用しないが、依存モジュール（F10, F12）経由で使用
- **pathlib**: `save_report` でファイルパス操作に使用（標準ライブラリ）
- **pytest**: テスト用（既存）

## 12. 後続機能との接続点

| 後続機能 | 使用するクラス/関数 | 用途 |
|---------|-------------------|------|
| F15 最適化 | `ComparisonResult`, `compare_presets` | 最適化前のベースライン比較 |

F15 での使用イメージ:

```python
from camera_placement.placement.comparison import compare_presets
from camera_placement.models.environment import create_default_room

# ベースライン比較
room = create_default_room()
baseline = compare_presets(room)
print(f"ベースライン最良: {baseline.best.preset.name} "
      f"(score={baseline.best.evaluation.quality.quality_score:.3f})")

# 最適化結果と比較
# optimized_score = optimizer.run(...)
# if optimized_score > baseline.best.evaluation.quality.quality_score:
#     print("最適化により改善")
```

## 13. `placement/__init__.py` の更新内容

```python
"""placement パッケージ: カメラ配置パターンの定義と比較。"""

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
    CameraConfig,
    PlacementPreset,
    create_cameras,
    get_all_presets,
    get_preset,
    list_preset_names,
)

__all__ = [
    "CameraConfig",
    "ComparisonResult",
    "EvaluationParams",
    "PlacementPreset",
    "PresetEvaluation",
    "compare_presets",
    "create_cameras",
    "evaluate_preset",
    "generate_report",
    "get_all_presets",
    "get_preset",
    "list_preset_names",
    "save_report",
]
```

## 14. テスト計画

テストファイル: `tests/test_comparison.py`

### テスト用ヘルパー

```python
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
```

### テスト用フィクスチャ

```python
@pytest.fixture
def room() -> Room:
    return create_default_room()

@pytest.fixture
def single_preset() -> PlacementPreset:
    return get_preset("upper_corners")
```

### カテゴリA: evaluate_preset

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 基本動作 | upper_corners, default_room | PresetEvaluation が返る | 基本動作 |
| A2 | preset が一致 | upper_corners, default_room | pe.preset.name == "upper_corners" | プリセット情報の保持 |
| A3 | evaluation が EvaluationResult | upper_corners, default_room | isinstance(pe.evaluation, EvaluationResult) | 型チェック |
| A4 | quality_score が [0.0, 1.0] | upper_corners, default_room | 0.0 <= score <= 1.0 | 値域チェック |
| A5 | 全プリセットで動作 | 全5プリセット, default_room | 全て PresetEvaluation が返る | 全プリセット対応 |
| A6 | volume_qualities が3種類 | upper_corners, default_room | WALKING, SEATED, SUPINE の3キー | ボリューム別スコア |
| A7 | カスタム重みで動作 | upper_corners, default_room, weights=(1,0,0) | coverage_score == quality_score | 重みカスタマイズ |

### カテゴリB: compare_presets

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | デフォルト（全プリセット） | default_room, presets=None | rankings の長さ5 | 全プリセット比較 |
| B2 | rankings の型 | default_room | 全要素が PresetEvaluation | 型チェック |
| B3 | rankings がスコア降順 | default_room | rankings[i].quality_score >= rankings[i+1].quality_score | ソート順 |
| B4 | best が rankings[0] | default_room | best is rankings[0] | ベスト一致 |
| B5 | best のスコアが最大 | default_room | best の quality_score が全プリセット中最大 | ベスト確認 |
| B6 | 指定プリセットで比較 | default_room, presets=[upper_corners, hybrid] | rankings の長さ2 | 部分比較 |
| B7 | 1プリセットで比較 | default_room, presets=[upper_corners] | rankings の長さ1, best == rankings[0] | 1要素 |
| B8 | 空リスト | default_room, presets=[] | ValueError | 空リストエラー |
| B9 | evaluation_params が保持される | default_room | params.grid_spacing == 0.2 | パラメータ保持 |
| B10 | カスタムパラメータが反映 | default_room, grid_spacing=0.5 | params.grid_spacing == 0.5 | カスタムパラメータ |

### カテゴリC: generate_report

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | ヘッダーが含まれる | ComparisonResult | "Camera Placement Comparison Report" を含む | ヘッダー |
| C2 | 全プリセット名が含まれる | ComparisonResult (5プリセット) | 5つのプリセット名が全て含まれる | プリセット名 |
| C3 | スコアが3桁で表示 | ComparisonResult | "0." + 数字3桁のパターンが含まれる | 数値フォーマット |
| C4 | 評価パラメータが含まれる | ComparisonResult | "Grid Spacing" が含まれる | パラメータ表示 |
| C5 | 活動ボリューム別が含まれる | ComparisonResult | "walking", "seated", "supine" が含まれる | ボリューム別 |
| C6 | ベストプリセットサマリーが含まれる | ComparisonResult | "Best Preset:" が含まれる | サマリー |
| C7 | ランキング表のヘッダーが含まれる | ComparisonResult | "Rank", "Preset", "Quality" が含まれる | 表ヘッダー |
| C8 | 1プリセットのレポート | ComparisonResult (1プリセット) | 正常なテキストが返る | 1要素対応 |
| C9 | レポートが文字列 | ComparisonResult | isinstance(report, str) | 型チェック |

### カテゴリD: save_report

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | ファイル保存 | report, tmp_path / "report.txt" | ファイルが存在し内容が一致 | 基本動作 |
| D2 | 戻り値が Path | report, tmp_path / "report.txt" | isinstance(result, Path) | 型チェック |
| D3 | 親ディレクトリ自動作成 | report, tmp_path / "sub/dir/report.txt" | ファイルが存在 | 自動作成 |
| D4 | UTF-8 エンコーディング | 日本語含むレポート, tmp_path / "report.txt" | 内容が一致 | エンコーディング |

### カテゴリE: 統合テスト

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | 比較→レポート→保存の一連フロー | default_room | レポートファイルが作成され、全プリセット名を含む | End-to-end |
| E2 | 異なる重みで結果が変わる | default_room, 2種類の重み | 2回の比較でランキングまたはスコアが異なる | 重みの影響 |

### テスト総数: 32 件

### テストの実行時間に関する注意

`evaluate_placement` は計算負荷が高い（1プリセットあたり数秒）。全5プリセットの一括比較テスト（B1〜B5）は実行に 10〜30 秒かかる。テスト効率のため、以下を考慮する:

- `evaluate_preset` のテスト（カテゴリA）では `grid_spacing=0.5` を使用してグリッド点数を減らし、テスト時間を短縮する
- `compare_presets` のテスト（カテゴリB）でも `grid_spacing=0.5` を使用する
- `generate_report` / `save_report` のテスト（カテゴリC, D）では、カテゴリBの結果をフィクスチャ化して再利用する
