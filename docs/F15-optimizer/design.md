# 機能設計書: F15 最適化エンジン・結果出力

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 3.1 `OptimizationConfig` |
| FR-02 | 4.1 `optimize_placement`、5.1 最適化処理フロー |
| FR-03 | 3.2 `OptimizationResult` |
| FR-04 | 4.2 `generate_optimization_report`、5.2 レポートフォーマット |
| FR-05 | 4.3 `save_optimization_report` |
| FR-06 | 4.4 `visualize_result` |
| FR-07 | 4.5 `create_convergence_plot` |

## 2. ファイル構成

```
src/camera_placement/
  optimization/
    __init__.py             # 既存: F15 の公開シンボルを追加
    objective.py            # 既存: F14（変更なし）
    optimizer.py            # 新規作成: F15 メインモジュール
tests/
  test_optimizer.py         # 新規作成: F15 テスト
tests/results/
  F15_test_result.txt       # テスト結果
```

ファイル名は `optimizer.py` とする（`docs/plan.md` の想定ファイル構成に従う）。

## 3. データ構造

### 3.1 OptimizationConfig dataclass

```python
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
```

- frozen=True でイミュータブル
- `__post_init__` でバリデーション（セクション 5.3 参照）

### 3.2 OptimizationResult dataclass

```python
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
```

- frozen なし（EvaluationResult が frozen でないため、F14 の ObjectiveResult と同じ方針）

## 4. 公開関数・メソッド設計

### 4.1 optimize_placement

```python
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
```

### 4.2 generate_optimization_report

```python
def generate_optimization_report(result: OptimizationResult) -> str:
    """最適化結果のテキストレポートを生成する。

    Args:
        result: 最適化結果。

    Returns:
        複数行のテキストレポート。
    """
```

### 4.3 save_optimization_report

```python
def save_optimization_report(report: str, filepath: str | Path) -> Path:
    """テキストレポートをファイルに保存する。

    Args:
        report: レポートテキスト。
        filepath: 保存先のファイルパス。

    Returns:
        保存先の Path オブジェクト。
    """
```

### 4.4 visualize_result

```python
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
```

### 4.5 create_convergence_plot

```python
def create_convergence_plot(result: OptimizationResult) -> go.Figure:
    """収束履歴のプロットを生成する。

    Args:
        result: 最適化結果。

    Returns:
        go.Figure インスタンス。
        convergence_history が空の場合は空のプロットを返す。
    """
```

## 5. アルゴリズム

### 5.1 最適化処理フロー（optimize_placement）

```
入力: room, config, init_preset, init_params
  │
  ├── Step 1: 設定の準備
  │           config が None → config = OptimizationConfig()
  │
  ├── Step 2: 初期解の検証
  │           init_preset と init_params の両方が非 None → ValueError
  │
  ├── Step 3: 初期解の準備
  │           x0 = None
  │           if init_preset is not None:
  │               preset = get_preset(init_preset)  # KeyError 可能性あり
  │               cameras = create_cameras(preset, room)
  │               x0 = cameras_to_params(cameras)
  │           elif init_params is not None:
  │               init_params = np.asarray(init_params, dtype=np.float64)
  │               expected = (config.num_cameras * 6,)
  │               init_params.shape != expected → ValueError
  │               x0 = init_params
  │
  ├── Step 4: 目的関数の初期化（最適化グリッド）
  │           obj = ObjectiveFunction(
  │               room,
  │               grid_spacing=config.grid_spacing,
  │               penalty_weight=config.penalty_weight,
  │               weight_coverage=config.weight_coverage,
  │               weight_angle=config.weight_angle,
  │               weight_projection=config.weight_projection,
  │               num_cameras=config.num_cameras,
  │           )
  │
  ├── Step 5: 収束履歴コールバックの準備
  │           convergence_history: list[float] = []
  │           def _callback(intermediate_result):
  │               convergence_history.append(float(intermediate_result.fun))
  │               gen = len(convergence_history)
  │               logger.info(
  │                   "Generation %d: best_value=%.6f",
  │                   gen, intermediate_result.fun,
  │               )
  │
  ├── Step 6: bounds の準備
  │           # scipy DE の bounds は (min, max) のリスト
  │           bounds_list = list(
  │               zip(obj.bounds[:, 0].tolist(), obj.bounds[:, 1].tolist())
  │           )
  │
  ├── Step 7: 計時開始
  │           start_time = time.monotonic()
  │
  ├── Step 8: differential_evolution 実行
  │           scipy_result = differential_evolution(
  │               func=obj,
  │               bounds=bounds_list,
  │               maxiter=config.maxiter,
  │               popsize=config.popsize,
  │               tol=config.tol,
  │               mutation=config.mutation,
  │               recombination=config.recombination,
  │               seed=config.seed,
  │               strategy=config.strategy,
  │               polish=config.polish,
  │               callback=_callback,
  │               x0=x0,
  │               init="latinhypercube",
  │               updating="immediate",
  │               workers=1,
  │               disp=False,
  │           )
  │
  ├── Step 9: 計時終了
  │           elapsed = time.monotonic() - start_time
  │
  ├── Step 10: 最良パラメータの詳細評価（最適化グリッド）
  │            best_params = scipy_result.x
  │            detail = obj.evaluate_detail(best_params)
  │            best_cameras = params_to_cameras(best_params, config.num_cameras)
  │
  ├── Step 11: 最良パラメータの最終評価（評価グリッド）
  │            fine_evaluation = evaluate_placement(
  │                best_cameras,
  │                room,
  │                grid_spacing=config.eval_grid_spacing,
  │                weight_coverage=config.weight_coverage,
  │                weight_angle=config.weight_angle,
  │                weight_projection=config.weight_projection,
  │            )
  │
  └── Step 12: 結果を返す
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
```

### 5.2 レポートフォーマット

generate_optimization_report が出力するテキストレポートのフォーマット:

```
=== Camera Placement Optimization Report ===

Optimization Parameters:
  Algorithm: differential_evolution
  Strategy: best1bin
  Max Iterations: 50
  Population Size: 5 (actual: 180)
  Tolerance: 0.01
  Mutation: (0.5, 1.0)
  Recombination: 0.7
  Polish: False
  Seed: None
  Optimization Grid Spacing: 0.5 m
  Evaluation Grid Spacing: 0.2 m
  Penalty Weight: 100.0
  Weights: coverage=0.5, angle=0.3, projection=0.2
  Num Cameras: 6

Optimization Results:
  Iterations: 42
  Function Evaluations: 7740
  Elapsed Time: 12.3 min
  Success: True
  Message: ...
  Optimization Objective Value: -0.743210

Final Evaluation (grid_spacing=0.2):
  Quality Score: 0.756
  Coverage Score: 0.812
  Angle Score: 0.689
  Projection Score: 0.724

Volume Quality:
  Rank  Volume               Quality  Coverage     Angle Projection
  --------------------------------------------------------------------
  1     walking                0.781     0.845     0.712     0.738
  2     seated                 0.734     0.789     0.667     0.710
  3     supine                 0.712     0.756     0.651     0.698

Camera Placement:
  Camera 1: position=(0.213, 0.321, 2.278), look_at=(1.423, 1.831, 0.782)
  Camera 2: position=(2.551, 0.254, 2.173), look_at=(1.352, 1.682, 0.923)
  Camera 3: ...
  Camera 4: ...
  Camera 5: ...
  Camera 6: ...
```

レポートのフォーマット詳細:

- ヘッダー行: `=== Camera Placement Optimization Report ===`
- Population Size 行: `popsize (actual: popsize × num_cameras × 6)` の形式
- Elapsed Time: 60秒以上の場合 `{分:.1f} min`、60秒未満の場合 `{秒:.1f} sec`
- スコア: 小数点以下3桁（`:.3f`）
- 座標: 小数点以下3桁（`:.3f`）
- Objective Value: 小数点以下6桁（`:.6f`）
- Volume Quality テーブル: 活動ボリューム別品質スコアを quality_score の降順でソート
- Volume Quality テーブルのカラム幅: Rank 6文字、Volume 20文字、Quality/Coverage/Angle/Projection 各10文字
- Volume Quality テーブルで `volume_qualities` に対応する `ActivityType` が存在しない場合: その活動ボリュームをスキップする（行を出力しない）

### 5.3 generate_optimization_report の処理フロー

```
入力: result (OptimizationResult)
  │
  ├── Step 1: lines: list[str] を初期化
  │
  ├── Step 2: ヘッダー
  │           lines.append("=== Camera Placement Optimization Report ===")
  │           lines.append("")
  │
  ├── Step 3: 最適化パラメータセクション
  │           lines.append("Optimization Parameters:")
  │           cfg = result.config
  │           actual_pop = cfg.popsize * cfg.num_cameras * 6
  │           lines.append(f"  Algorithm: differential_evolution")
  │           lines.append(f"  Strategy: {cfg.strategy}")
  │           lines.append(f"  Max Iterations: {cfg.maxiter}")
  │           lines.append(f"  Population Size: {cfg.popsize} (actual: {actual_pop})")
  │           lines.append(f"  Tolerance: {cfg.tol}")
  │           lines.append(f"  Mutation: ({cfg.mutation[0]}, {cfg.mutation[1]})")
  │           lines.append(f"  Recombination: {cfg.recombination}")
  │           lines.append(f"  Polish: {cfg.polish}")
  │           lines.append(f"  Seed: {cfg.seed}")
  │           lines.append(f"  Optimization Grid Spacing: {cfg.grid_spacing} m")
  │           lines.append(f"  Evaluation Grid Spacing: {cfg.eval_grid_spacing} m")
  │           lines.append(f"  Penalty Weight: {cfg.penalty_weight}")
  │           lines.append(f"  Weights: coverage={cfg.weight_coverage}, "
  │                        f"angle={cfg.weight_angle}, "
  │                        f"projection={cfg.weight_projection}")
  │           lines.append(f"  Num Cameras: {cfg.num_cameras}")
  │           lines.append("")
  │
  ├── Step 4: 最適化結果サマリー
  │           lines.append("Optimization Results:")
  │           lines.append(f"  Iterations: {result.nit}")
  │           lines.append(f"  Function Evaluations: {result.nfev}")
  │           # 時間表記: 60秒以上なら分、未満なら秒
  │           if result.elapsed_seconds >= 60:
  │               lines.append(f"  Elapsed Time: {result.elapsed_seconds / 60:.1f} min")
  │           else:
  │               lines.append(f"  Elapsed Time: {result.elapsed_seconds:.1f} sec")
  │           lines.append(f"  Success: {result.success}")
  │           lines.append(f"  Message: {result.message}")
  │           lines.append(f"  Optimization Objective Value: {result.best_value:.6f}")
  │           lines.append("")
  │
  ├── Step 5: 品質スコア（評価グリッド）
  │           q = result.fine_evaluation.quality
  │           lines.append(f"Final Evaluation (grid_spacing={cfg.eval_grid_spacing}):")
  │           lines.append(f"  Quality Score: {q.quality_score:.3f}")
  │           lines.append(f"  Coverage Score: {q.coverage_score:.3f}")
  │           lines.append(f"  Angle Score: {q.angle_score:.3f}")
  │           lines.append(f"  Projection Score: {q.projection_score:.3f}")
  │           lines.append("")
  │
  ├── Step 6: 活動ボリューム別品質スコア
  │           lines.append("Volume Quality:")
  │           lines.append(
  │               f"{'Rank':<6}{'Volume':<20}{'Quality':>10}"
  │               f"{'Coverage':>10}{'Angle':>10}{'Projection':>10}"
  │           )
  │           lines.append("-" * 66)
  │           # volume_qualities から存在する ActivityType のみ取得
  │           volume_items = []
  │           for act_type in [ActivityType.WALKING, ActivityType.SEATED, ActivityType.SUPINE]:
  │               if act_type in result.fine_evaluation.volume_qualities:
  │                   volume_items.append(
  │                       (act_type, result.fine_evaluation.volume_qualities[act_type])
  │                   )
  │           # quality_score の降順でソート
  │           volume_items.sort(key=lambda item: item[1].quality_score, reverse=True)
  │           for rank, (act_type, vq) in enumerate(volume_items, 1):
  │               lines.append(
  │                   f"{rank:<6}{act_type.value:<20}{vq.quality_score:>10.3f}"
  │                   f"{vq.coverage_score:>10.3f}{vq.angle_score:>10.3f}"
  │                   f"{vq.projection_score:>10.3f}"
  │               )
  │           lines.append("")
  │
  ├── Step 7: カメラ配置
  │           lines.append("Camera Placement:")
  │           for i, cam in enumerate(result.best_cameras):
  │               pos = cam.position
  │               la = cam.look_at
  │               lines.append(
  │                   f"  Camera {i + 1}: "
  │                   f"position=({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}), "
  │                   f"look_at=({la[0]:.3f}, {la[1]:.3f}, {la[2]:.3f})"
  │               )
  │
  └── Step 8: 返す
              return "\n".join(lines)
```

### 5.4 OptimizationConfig バリデーション（__post_init__）

```
Step 1: maxiter < 1 → ValueError("maxiter must be >= 1")
Step 2: popsize < 1 → ValueError("popsize must be >= 1")
Step 3: tol < 0 → ValueError("tol must be >= 0")
Step 4: len(mutation) != 2 → ValueError("mutation must be a 2-tuple")
        mutation[0] <= 0 or mutation[0] > 2 → ValueError("mutation values must be in (0, 2]")
        mutation[1] <= 0 or mutation[1] > 2 → ValueError 同上
Step 5: recombination < 0 or recombination > 1 → ValueError("recombination must be in [0, 1]")
Step 6: grid_spacing <= 0 → ValueError("grid_spacing must be > 0")
Step 7: eval_grid_spacing <= 0 → ValueError("eval_grid_spacing must be > 0")
Step 8: penalty_weight < 0 → ValueError("penalty_weight must be >= 0")
Step 9: weight_coverage < 0 or weight_angle < 0 or weight_projection < 0
        → ValueError("weights must be non-negative")
Step 10: weight_coverage + weight_angle + weight_projection == 0
         → ValueError("sum of weights must be positive")
Step 11: num_cameras < 1 → ValueError("num_cameras must be >= 1")
# strategy のバリデーションは scipy.optimize.differential_evolution に委任する。
# 不正な戦略名の場合、scipy が ValueError を送出する。
```

### 5.5 visualize_result の処理フロー

```
入力: result, room, show_frustums, show_grid, frustum_far
  │
  ├── Step 1: frustum_far <= 0 → ValueError
  │
  ├── Step 2: タイトルの生成
  │           quality = result.fine_evaluation.quality.quality_score
  │           title = f"Optimized Camera Placement (Quality: {quality:.3f})"
  │
  ├── Step 3: create_scene の呼び出し
  │           fig = create_scene(
  │               room=room,
  │               cameras=result.best_cameras,
  │               coverage_result=result.fine_evaluation.coverage_result,
  │               show_frustums=show_frustums,
  │               show_grid=show_grid,
  │               frustum_far=frustum_far,
  │               title=title,
  │           )
  │
  └── Step 4: 返す
              return fig
```

### 5.6 create_convergence_plot の処理フロー

```
入力: result
  │
  ├── Step 1: convergence_history の取得
  │           history = result.convergence_history
  │
  ├── Step 2: プロットの生成
  │           if len(history) == 0:
  │               fig = go.Figure()
  │           else:
  │               generations = list(range(1, len(history) + 1))
  │               trace = go.Scatter(
  │                   x=generations,
  │                   y=history,
  │                   mode="lines+markers",
  │                   line=dict(color="rgb(31, 119, 180)"),
  │                   marker=dict(size=4),
  │                   name="Best Objective Value",
  │               )
  │               fig = go.Figure(data=[trace])
  │
  ├── Step 3: レイアウト設定
  │           fig.update_layout(
  │               title="Convergence History",
  │               xaxis_title="Generation",
  │               yaxis_title="Best Objective Value",
  │               width=800,
  │               height=500,
  │           )
  │
  └── Step 4: 返す
              return fig
```

### 5.7 データフロー図

```
OptimizationConfig
    │
    ├── grid_spacing, penalty_weight, weights, num_cameras
    │       │
    │       ▼
    │   ObjectiveFunction (最適化グリッド)
    │       │
    │       ├── bounds → scipy DE bounds
    │       └── __call__ → scipy DE func
    │
    ├── maxiter, popsize, tol, mutation, recombination,
    │   seed, strategy, polish
    │       │
    │       ▼
    │   scipy.optimize.differential_evolution
    │       │
    │       ├── callback → convergence_history に追加
    │       │
    │       └── scipy_result
    │             ├── x → best_params
    │             ├── fun → best_value
    │             ├── nit, nfev, success, message
    │             │
    │             ▼
    │         best_params
    │             │
    │             ├── params_to_cameras → best_cameras
    │             ├── obj.evaluate_detail → detail (ObjectiveResult)
    │             │
    │             └── eval_grid_spacing
    │                   │
    │                   ▼
    │               evaluate_placement (評価グリッド)
    │                   │
    │                   ▼
    │               fine_evaluation (EvaluationResult)
    │
    └── OptimizationResult
          │
          ├── generate_optimization_report → テキストレポート
          │     └── save_optimization_report → ファイル保存
          │
          ├── visualize_result
          │     └── create_scene (F11) → go.Figure
          │           └── save_html (F11) → HTML ファイル
          │
          └── create_convergence_plot → go.Figure
                └── save_html (F11) → HTML ファイル
```

## 6. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| OptimizationConfig のバリデーション失敗 | ValueError を送出 | `__post_init__` |
| init_preset と init_params の両方が指定 | `ValueError("Cannot specify both init_preset and init_params")` を送出 | `optimize_placement` |
| init_preset に存在しないプリセット名 | KeyError を送出（get_preset から伝播） | `optimize_placement` |
| init_params の shape 不正 | `ValueError` を送出 | `optimize_placement` |
| scipy DE が収束しなかった | success=False の OptimizationResult を返す。例外は送出しない | `optimize_placement` |
| scipy DE 内部エラー | scipy からの例外をそのまま伝播 | scipy |
| frustum_far <= 0 | `ValueError` を送出 | `visualize_result` |
| params_to_cameras が失敗（最良パラメータが不正カメラ構成） | 理論上は発生しない（DE は目的関数の値が有限な解を返すため、infeasible 解は高ペナルティで排除される）。万が一発生した場合は ValueError が伝播する | `optimize_placement` Step 10 |

## 7. 境界条件

| ケース | 期待動作 |
|--------|---------|
| maxiter=1, popsize=1 | 最小限の最適化が実行される。結果は粗いが正常終了 |
| seed を固定して2回実行 | 同一の best_params, best_value, convergence_history が得られる |
| init_preset="upper_corners" | プリセット配置を初期解としてDE が探索開始。初期解に近い解が得られやすい |
| init_params が bounds 外の値を含む | scipy DE は bounds 内にクランプして処理する |
| convergence_history が空 | create_convergence_plot は空のプロットを返す |
| 全活動ボリュームの品質が0 | レポートに 0.000 と表示。正常動作 |
| elapsed_seconds < 60 | レポートに秒表記 (`X.X sec`) |
| elapsed_seconds >= 60 | レポートに分表記 (`X.X min`) |

## 8. 設計判断

### 8.1 最適化アルゴリズムに差分進化のみを採用する理由

- **採用案**: scipy.optimize.differential_evolution のみ
- **却下案1**: PSO (Particle Swarm Optimization)
  - 却下理由: scipy に組み込みの PSO 実装がない。pyswarm, pyswarms などの外部ライブラリが必要だが、依存を最小化する方針に反する。scipy DE は十分に検証された実装であり、36次元の境界制約つき最適化に適している
- **却下案2**: scipy.optimize.dual_annealing
  - 却下理由: DE と同等の性能が期待できるが、初期解（x0）のサポートが限定的。F12 プリセットを初期解として活用する設計との親和性が DE の方が高い
- **却下案3**: 複数アルゴリズムの選択式
  - 却下理由: アルゴリズムごとにパラメータが異なり、設計の複雑さが増す。まず DE で実用的な結果を得てから、必要に応じて拡張する

### 8.2 最適化と最終評価でグリッド間隔を分離する理由

- **採用案**: grid_spacing=0.5（最適化用）と eval_grid_spacing=0.2（最終評価用）を分離
- **却下案**: 全工程で同一のグリッド間隔を使用
  - 却下理由: grid_spacing=0.2 では1回の目的関数評価に数秒かかる。popsize=5, n_params=36 の場合、1世代の集団サイズは 180 個体。1世代あたり 180 × 数秒 = 数百秒となり、50世代で数時間以上かかる。grid_spacing=0.5 では評価時間が大幅に短縮される（グリッド点数が約15分の1）ため、実用的な時間で最適化が完了する。最終評価では細かいグリッドで正確な品質スコアを計算する

### 8.3 polish=False をデフォルトとする理由

- **採用案**: polish=False（局所探索なし）
- **却下案**: polish=True（DE 完了後に L-BFGS-B で局所探索）
  - 却下理由: 目的関数は粗いグリッド（grid_spacing=0.5）で評価しており、微分が不連続な箇所がある。L-BFGS-B は連続微分可能な関数を前提としており、粗いグリッドの目的関数には不適。ユーザーが fine grid での polish を望む場合は、config で polish=True と eval_grid_spacing 相当の grid_spacing を設定できる

### 8.4 workers=1 固定とする理由

- **採用案**: workers=1（シングルプロセス）
- **却下案**: workers=-1（全CPUコアで並列評価）
  - 却下理由: scipy DE の並列評価は multiprocessing を使用し、目的関数がピクル可能である必要がある。ObjectiveFunction は Room, Camera 等の複雑なオブジェクトを保持しており、ピクル化のテスト・対応が必要になる。初版ではシンプルさを優先し、シングルプロセスで実装する

### 8.5 popsize=5 をデフォルトとする理由

- **採用案**: popsize=5（集団サイズ = 5 × 36 = 180）
- **却下案1**: popsize=15（scipy デフォルト。集団サイズ = 540）
  - 却下理由: 目的関数の評価コストが高いため、集団サイズ 540 では1世代の計算時間が長すぎる。popsize=5 でも 180 個体あり、36次元空間の探索には十分な多様性を持つ
- **却下案2**: popsize=1（最小集団サイズ = 36）
  - 却下理由: 集団の多様性が不足し、局所解に陥りやすい

### 8.6 maxiter=50 をデフォルトとする理由

- **採用案**: maxiter=50
- **却下案1**: maxiter=1000（scipy デフォルト）
  - 却下理由: 目的関数の評価コストが高く、1000世代は非現実的な計算時間になる
- **却下案2**: maxiter=10
  - 却下理由: 36次元空間の探索には不十分。50世代であれば、集団サイズ 180 × 50 = 9000 回の評価で、十分な探索が期待できる
- **パフォーマンス推定**: grid_spacing=0.5 ではグリッド点数が grid_spacing=0.2 の約15分の1に減少し、1回の目的関数評価は約0.1〜0.5秒と推定される。9000回 × 0.3秒 ≈ 45分であり、60分以内の目標に収まる

### 8.7 コールバックに OptimizeResult パターンを使用する理由

- **採用案**: `callback(intermediate_result)` で `intermediate_result.fun` を記録
- **却下案**: `callback(x, convergence)` パターン
  - 却下理由: OptimizeResult パターンの方が新しい scipy のインターフェースであり、fun（最良目的関数値）を直接取得できる。convergence パターンの convergence 値は相対値であり、目的関数値そのものを記録するには x を使って再評価が必要になる

### 8.8 init パラメータに "latinhypercube" を使用する理由

- **採用案**: init="latinhypercube"
- **却下案1**: init="sobol"
  - 却下理由: Sobol シーケンスは高次元で優れたカバレッジを持つが、scipy バージョンによってはサポートされない可能性がある。Latin Hypercube は広くサポートされており、36次元でも十分な性能を持つ
- **却下案2**: init="random"
  - 却下理由: Latin Hypercube の方がパラメータ空間を均等にカバーし、初期集団の多様性が高い

### 8.9 レポートフォーマットを F13 と統一しない理由

- **採用案**: F15 独自のレポートフォーマット
- **却下案**: F13 の generate_report と同一フォーマット
  - 却下理由: F13 はプリセット間の比較レポートであり、F15 は最適化の結果レポートである。目的が異なるため、最適化パラメータ、収束情報、カメラ座標など F15 固有の情報を含むフォーマットが必要。ただし、品質スコアの表示形式（カラム幅、小数桁数）は F13 と揃える

### 8.10 bounds の渡し方

- **採用案**: `list(zip(obj.bounds[:, 0].tolist(), obj.bounds[:, 1].tolist()))` でリスト of タプルに変換
- **却下案**: `obj.bounds.tolist()` でリスト of リストに変換
  - 却下理由: scipy DE の bounds パラメータは (min, max) ペアのシーケンスを要求する。`zip` で生成したタプルのリストが最も明示的で、scipy ドキュメントのサンプルと一致する

### 8.11 best_value に scipy_result.fun を使用する理由

- **採用案**: `best_value = float(scipy_result.fun)`（scipy が返す目的関数値をそのまま使用）
- **却下案**: `best_value = detail.value`（evaluate_detail で再計算した値を使用）
  - 却下理由: polish=True の場合、scipy 内部で L-BFGS-B による追加評価が行われ、scipy_result.fun が更新される可能性がある。scipy_result.fun は最適化プロセス全体の最良値を反映するため、こちらを使用する。detail.value は同じパラメータでの再評価であり、通常は一致するが、scipy_result.fun の方が最適化の正式な結果である

## 9. ログ・デバッグ設計

F15 は長時間実行される最適化処理を含むため、Python の `logging` モジュールを使用して進捗を出力する。

- ロガー名: `camera_placement.optimization.optimizer`
- ログレベルと出力ポイント:

| ログレベル | 出力ポイント | メッセージ例 |
|-----------|------------|-------------|
| INFO | 最適化開始時 | `"Starting optimization: maxiter=%d, popsize=%d, n_params=%d"` |
| INFO | 各世代完了時（コールバック内） | `"Generation %d: best_value=%.6f"` |
| INFO | 最適化完了時 | `"Optimization completed: nit=%d, nfev=%d, elapsed=%.1fs, success=%s"` |
| INFO | 最終評価開始時 | `"Running final evaluation with grid_spacing=%.2f"` |
| INFO | 最終評価完了時 | `"Final quality_score=%.3f"` |

デフォルトではログは出力されない（ユーザーが logging.basicConfig() で設定した場合のみ出力される）。

## 10. ファイル・ディレクトリ設計

### 10.1 モジュールファイル

- 新規作成: `src/camera_placement/optimization/optimizer.py`
- 既存更新: `src/camera_placement/optimization/__init__.py`（F15 の公開シンボルを追加）

### 10.2 テストファイル

- テストコード: `tests/test_optimizer.py`
- テスト結果: `tests/results/F15_test_result.txt`

### 10.3 出力ファイル（ユーザーが save 関数で生成）

- レポート: 任意のパス（ユーザー指定）
- 可視化 HTML: 任意のパス（ユーザーが save_html で保存）

## 11. 技術スタック

- **Python**: 3.12
- **scipy** (>=1.15, 新規追加): differential_evolution アルゴリズム
- **numpy** (>=2.4.2, 既存): ベクトル演算
- **plotly** (>=6.6.0, 既存): 可視化（収束プロット）
- **pytest**: テスト用
- `uv add scipy` でプロジェクトに追加する

## 12. 依存機能との連携

### 12.1 F14（目的関数）

- `ObjectiveFunction`: 目的関数を生成。scipy DE の func パラメータに渡す
- `ObjectiveResult`: 最良パラメータの詳細評価結果
- `params_to_cameras`: 最良パラメータから Camera リストを復元
- `cameras_to_params`: プリセットのカメラ配置をパラメータベクトルに変換
- インポート: `from camera_placement.optimization.objective import ObjectiveFunction, ObjectiveResult, params_to_cameras, cameras_to_params`

### 12.2 F11（3D可視化）

- `create_scene`: 3D シーンの生成
- `save_html`: HTML ファイルへの保存
- インポート: `from camera_placement.visualization.viewer import create_scene, save_html`

### 12.3 F10（統合品質スコア）

- `evaluate_placement`: 評価グリッドでの最終評価
- `EvaluationResult`: 最終評価結果を OptimizationResult.fine_evaluation に保持
- インポート: `from camera_placement.evaluation.evaluator import EvaluationResult, evaluate_placement`

### 12.4 F12（配置プリセット）

- `get_preset`: プリセット名からプリセットを取得（init_preset 用）
- `create_cameras`: プリセットから Camera リストを生成
- インポート: `from camera_placement.placement.patterns import get_preset, create_cameras`

### 12.5 F01（空間モデル）

- `Room`: 病室モデルを受け取る
- インポート: `from camera_placement.models.environment import Room`

### 12.6 F02（カメラモデル）

- `Camera`: 型ヒントに使用
- インポート: `from camera_placement.models.camera import Camera`

## 13. `optimization/__init__.py` の更新内容

```python
"""optimization パッケージ: カメラ配置の最適化機能。"""

from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    calculate_position_penalty,
    cameras_to_params,
    get_parameter_bounds,
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

__all__ = [
    "ObjectiveFunction",
    "ObjectiveResult",
    "OptimizationConfig",
    "OptimizationResult",
    "calculate_position_penalty",
    "cameras_to_params",
    "create_convergence_plot",
    "generate_optimization_report",
    "get_parameter_bounds",
    "optimize_placement",
    "params_to_cameras",
    "save_optimization_report",
    "visualize_result",
]
```

## 14. テスト計画

テストファイル: `tests/test_optimizer.py`

### テスト用ヘルパー

```python
import pytest
import numpy as np
from unittest.mock import patch
import plotly.graph_objects as go

from camera_placement.optimization.optimizer import (
    OptimizationConfig,
    OptimizationResult,
    create_convergence_plot,
    generate_optimization_report,
    optimize_placement,
    save_optimization_report,
    visualize_result,
)
from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    cameras_to_params,
    params_to_cameras,
)
from camera_placement.models.environment import Room, create_default_room
from camera_placement.models.camera import Camera
from camera_placement.evaluation.evaluator import EvaluationResult


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
```

### カテゴリA: OptimizationConfig のバリデーション

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | デフォルト値で生成 | OptimizationConfig() | 正常生成 | デフォルト |
| A2 | maxiter < 1 | maxiter=0 | ValueError | バリデーション |
| A3 | popsize < 1 | popsize=0 | ValueError | バリデーション |
| A4 | tol < 0 | tol=-0.1 | ValueError | バリデーション |
| A5 | mutation 要素が範囲外 | mutation=(0, 1) | ValueError | mutation下限 |
| A6 | mutation 要素が上限超過 | mutation=(0.5, 2.5) | ValueError | mutation上限 |
| A7 | recombination < 0 | recombination=-0.1 | ValueError | バリデーション |
| A8 | recombination > 1 | recombination=1.1 | ValueError | バリデーション |
| A9 | grid_spacing <= 0 | grid_spacing=0 | ValueError | バリデーション |
| A10 | eval_grid_spacing <= 0 | eval_grid_spacing=-0.1 | ValueError | バリデーション |
| A11 | penalty_weight < 0 | penalty_weight=-1 | ValueError | バリデーション |
| A12 | 重みが負 | weight_coverage=-0.1 | ValueError | バリデーション |
| A13 | 重み合計が0 | weight_coverage=0, weight_angle=0, weight_projection=0 | ValueError | バリデーション |
| A14 | num_cameras < 1 | num_cameras=0 | ValueError | バリデーション |
| A15 | 全パラメータ指定 | 全フィールドにカスタム値 | 正常生成 | カスタム設定 |
| A16 | frozen 確認 | config.maxiter = 100 | FrozenInstanceError | イミュータブル |

### カテゴリB: optimize_placement の基本動作

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | デフォルト config | room, minimal_config | OptimizationResult が返る | 基本動作 |
| B2 | config=None のデフォルト適用 | optimize_placement 内で config=None が OptimizationConfig() に変換されることを確認（実際には minimal_config を渡して軽量テスト。config=None のコードパスは B1 と同じ構造のため、デフォルト値生成の単体テストで検証） | config=None 渡しで型エラーなく動作 | デフォルト適用 |
| B3 | best_params の shape | minimal_config | best_params.shape == (36,) | パラメータ形状 |
| B4 | best_cameras の台数 | minimal_config | len(best_cameras) == 6 | カメラ数 |
| B5 | best_value の型 | minimal_config | isinstance(best_value, float) | 型 |
| B6 | detail の型 | minimal_config | isinstance(detail, ObjectiveResult) | 型 |
| B7 | fine_evaluation の型 | minimal_config | isinstance(fine_evaluation, EvaluationResult) | 型 |
| B8 | nit >= 0 | minimal_config | nit >= 0 | 世代数 |
| B9 | nfev >= 0 | minimal_config | nfev >= 0 | 評価回数 |
| B10 | elapsed_seconds >= 0 | minimal_config | elapsed_seconds >= 0 | 所要時間 |
| B11 | convergence_history 長さ | minimal_config | len(convergence_history) >= 1 | 収束履歴 |

### カテゴリC: 初期解の指定

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | init_preset 指定 | init_preset="upper_corners" | 正常終了 | プリセット初期解 |
| C2 | init_params 指定 | init_params=コーナー配置パラメータ | 正常終了 | カスタム初期解 |
| C3 | 両方指定 | init_preset="upper_corners", init_params=... | ValueError | 排他チェック |
| C4 | 存在しないプリセット | init_preset="nonexistent" | KeyError | プリセット不在 |
| C5 | init_params の shape 不正 | init_params=shape (35,) | ValueError | shape チェック |

### カテゴリD: 再現性

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | seed 固定で2回実行 | seed=42 × 2回 | best_value が一致 | 再現性 |
| D2 | seed 固定で convergence_history 一致 | seed=42 × 2回 | convergence_history が一致 | 再現性 |

### カテゴリE: generate_optimization_report

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | ヘッダー含む | optimization_result | "=== Camera Placement Optimization Report ===" を含む | ヘッダー |
| E2 | 最適化パラメータ含む | optimization_result | "Max Iterations:" を含む | パラメータ表示 |
| E3 | 品質スコア含む | optimization_result | "Quality Score:" を含む | スコア表示 |
| E4 | カメラ配置含む | optimization_result | "Camera 1:" を含む | 配置表示 |
| E5 | ボリューム品質含む | optimization_result | "walking" を含む | ボリューム表示 |
| E6 | 時間表記（秒） | elapsed_seconds=30.5 のモック | "30.5 sec" を含む | 時間表記 |
| E7 | 時間表記（分） | elapsed_seconds=125.3 のモック | "2.1 min" を含む | 時間表記 |

### カテゴリF: save_optimization_report

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| F1 | ファイル保存 | report, tmp_path / "report.txt" | ファイルが作成され内容が一致 | 基本保存 |
| F2 | 親ディレクトリ自動作成 | tmp_path / "sub" / "report.txt" | 親ディレクトリが作成される | 自動作成 |
| F3 | 戻り値が Path | report, filepath | isinstance(result, Path) | 戻り値型 |

### カテゴリG: visualize_result

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| G1 | 基本動作 | optimization_result, room | isinstance(fig, go.Figure) | 型 |
| G2 | タイトルに品質スコア含む | optimization_result, room | title に "Quality:" を含む | タイトル |
| G3 | frustum_far <= 0 | frustum_far=0 | ValueError | バリデーション |
| G4 | show_frustums=False | show_frustums=False | 正常終了（視錐台なし） | オプション |
| G5 | show_grid=False | show_grid=False | 正常終了（グリッドなし） | オプション |

### カテゴリH: create_convergence_plot

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| H1 | 基本動作 | optimization_result | isinstance(fig, go.Figure) | 型 |
| H2 | トレース数 | optimization_result | len(fig.data) == 1 | トレース |
| H3 | x 値 | history=[0.5, 0.3, 0.2] のモック | x == [1, 2, 3] | X軸 |
| H4 | y 値 | history=[0.5, 0.3, 0.2] のモック | y == [0.5, 0.3, 0.2] | Y軸 |
| H5 | 空の履歴 | convergence_history=[] のモック | 空のプロット（data が空またはデータなし） | 空履歴 |

### カテゴリI: 統合テスト

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| I1 | 最適化結果が密集配置より良い | minimal_config + 密集配置を直接評価 | 最適化結果の quality_score > 密集配置の quality_score | 弁別力 |
| I2 | best_value == detail.value | optimization_result | best_value と detail.value の差が atol=1e-6 以内 | 整合性 |
| I3 | レポート → ファイル保存 → 読み取り | optimization_result | 保存内容と生成レポートが一致 | エンドツーエンド |

### テスト総数: 50 件

### テスト実行時間の注意

- optimize_placement はテスト用に `maxiter=2, popsize=1, grid_spacing=1.0, seed=42` を使用して実行時間を短縮する
- `optimization_result` fixture は1回だけ optimize_placement を実行し、複数のテストで再利用する
- カテゴリ A, E, F, G, H のうちモックを使用するテストは高速（1秒以内）
- カテゴリ B, C, D, I の optimize_placement 呼び出しを含むテストは各数秒～数十秒かかる
- 再現性テスト（D1, D2）は optimize_placement を2回実行するため、合計実行時間が長い
