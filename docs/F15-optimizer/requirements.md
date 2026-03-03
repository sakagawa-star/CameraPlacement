# 要求仕様書: F15 最適化エンジン・結果出力

## 1. プロジェクト概要

- **何を作るか**: scipy の差分進化（differential_evolution）アルゴリズムを用いて、6台カメラの最適配置を探索するモジュール。最適化結果のテキストレポート生成と3D可視化機能を含む
- **なぜ作るか**: F12 の手動設計プリセットでは探索範囲が限定的であり、36次元パラメータ空間から品質スコアを最大化する配置を自動探索する必要がある。F14 で定義した目的関数を最適化アルゴリズムに渡し、計算機的に最適な配置を求める
- **誰が使うか**: 開発者（CLI またはスクリプトから実行）
- **どこで使うか**: Python 3.12 ローカル環境

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| 差分進化 (differential evolution, DE) | scipy.optimize.differential_evolution で実装されたグローバル最適化アルゴリズム。勾配不要で境界制約つき最適化に対応 |
| 世代 (generation) | DE における1回の集団更新ステップ。全個体の試行ベクトル生成・評価・選択を含む |
| 個体 (individual) | パラメータベクトル（36次元）1つ。1つのカメラ配置案に対応 |
| 集団サイズ (population size) | 1世代内の個体数。`popsize × n_params`（n_params = num_cameras × 6） |
| 最適化グリッド (optimization grid) | 最適化中の目的関数評価に使用する粗いグリッド。grid_spacing で指定 |
| 評価グリッド (evaluation grid) | 最適化完了後の最終評価に使用する細かいグリッド。eval_grid_spacing で指定 |
| 収束履歴 (convergence history) | 各世代の終了時点での最良目的関数値のリスト |
| 初期解 (initial solution) | 最適化の出発点として提供するパラメータベクトル。F12 プリセットから変換可能 |
| 最適化設定 (optimization config) | DE のアルゴリズムパラメータと評価パラメータを束ねた設定オブジェクト |

## 3. 機能要求一覧

### FR-01: 最適化設定

最適化に必要な全パラメータを1つのデータクラスで管理する。

- データクラス名: `OptimizationConfig`
- frozen=True（イミュータブル）
- フィールド:

| フィールド | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| maxiter | int | 50 | DE の最大世代数。1 以上 |
| popsize | int | 5 | 集団サイズ乗数。実際の集団サイズは `popsize × n_params`。1 以上 |
| tol | float | 0.01 | 収束判定の相対許容誤差。0 以上 |
| mutation | tuple[float, float] | (0.5, 1.0) | DE の突然変異定数の範囲 (dithering)。各要素は 0 より大きく 2 以下 |
| recombination | float | 0.7 | DE の交叉確率。0 以上 1 以下 |
| seed | int \| None | None | 乱数シード。None の場合は再現性なし |
| strategy | str | "best1bin" | DE の戦略。scipy がサポートする戦略名のいずれか。不正な戦略名の場合は scipy が ValueError を送出する |
| polish | bool | False | True の場合、DE 完了後に L-BFGS-B で局所探索を行う |
| grid_spacing | float | 0.5 | 最適化中の目的関数評価に使用するグリッド間隔 [m]。0 より大きい |
| eval_grid_spacing | float | 0.2 | 最適化後の最終評価に使用するグリッド間隔 [m]。0 より大きい |
| penalty_weight | float | 100.0 | 設置領域制約のペナルティ係数。0 以上 |
| weight_coverage | float | 0.5 | カバレッジの重み。0 以上 |
| weight_angle | float | 0.3 | 角度スコアの重み。0 以上 |
| weight_projection | float | 0.2 | 投影スコアの重み。0 以上 |
| num_cameras | int | 6 | カメラ台数。1 以上 |

- バリデーション（`__post_init__` で実施）:
  - maxiter < 1 → ValueError
  - popsize < 1 → ValueError
  - tol < 0 → ValueError
  - mutation の各要素が 0 以下 または 2 より大きい → ValueError
  - recombination < 0 または > 1 → ValueError
  - grid_spacing <= 0 → ValueError
  - eval_grid_spacing <= 0 → ValueError
  - penalty_weight < 0 → ValueError
  - weight_coverage, weight_angle, weight_projection のいずれかが負 → ValueError
  - weight_coverage + weight_angle + weight_projection == 0 → ValueError
  - num_cameras < 1 → ValueError
  - strategy のバリデーションは scipy.optimize.differential_evolution に委任する（不正な戦略名の場合 scipy が ValueError を送出する）
- 受け入れ基準: デフォルト値で `OptimizationConfig()` を生成できること。不正値で ValueError が送出されること

### FR-02: 最適化実行

差分進化アルゴリズムでカメラ配置を最適化する。

- 関数名: `optimize_placement`
- 入力:

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| room | Room | (必須) | 病室モデル |
| config | OptimizationConfig \| None | None | 最適化設定。None の場合は OptimizationConfig() を使用 |
| init_preset | str \| None | None | 初期解として使用する F12 プリセット名 |
| init_params | np.ndarray \| None | None | 初期解のパラメータベクトル。shape (num_cameras * 6,) |

- 出力: OptimizationResult（FR-03 参照）
- 処理の概要:
  1. OptimizationConfig のデフォルト適用
  2. F14 ObjectiveFunction を config.grid_spacing で初期化
  3. 初期解の準備（init_preset → パラメータ変換、または init_params を使用）
  4. scipy.optimize.differential_evolution を実行
  5. 最適化完了後、最良パラメータを config.eval_grid_spacing で再評価（F10 evaluate_placement を直接使用）
  6. OptimizationResult を構築して返す
- 制約:
  - init_preset と init_params の両方が指定された場合 → ValueError
  - init_preset が存在しないプリセット名の場合 → KeyError（get_preset から伝播）
  - init_params の shape が (num_cameras * 6,) でない場合 → ValueError
- 受け入れ基準:
  - デフォルト設定で optimize_placement(room) を呼び出し、OptimizationResult が返ること
  - 返り値の best_cameras が num_cameras 台の Camera リストであること
  - 返り値の fine_evaluation が eval_grid_spacing で計算されていること
  - 最適化結果の品質スコアが、全カメラを部屋の1隅に密集させた配置より高いこと

### FR-03: 最適化結果

最適化の結果を保持するデータ構造。

- データクラス名: `OptimizationResult`
- フィールド:

| フィールド | 型 | 説明 |
|---|---|---|
| best_params | np.ndarray | 最良パラメータベクトル。shape (num_cameras * 6,) |
| best_cameras | list[Camera] | 最良パラメータから復元した Camera リスト |
| best_value | float | 最良目的関数値（最適化グリッドでの値） |
| detail | ObjectiveResult | 最良パラメータの詳細結果（最適化グリッドでの評価） |
| fine_evaluation | EvaluationResult | 最良パラメータの評価グリッドでの F10 評価結果 |
| config | OptimizationConfig | 使用した最適化設定 |
| nit | int | 実行した世代数 |
| nfev | int | 目的関数の呼び出し回数 |
| elapsed_seconds | float | 最適化の所要時間 [秒] |
| success | bool | scipy DE の収束判定結果 |
| message | str | scipy DE の終了メッセージ |
| convergence_history | list[float] | 各世代の最良目的関数値。長さはコールバック呼び出し回数に等しく、通常 nit と一致する。polish=True の場合は nit に polish 分が含まれないため len(convergence_history) <= nit となる場合がある |

- 受け入れ基準:
  - best_params.shape == (num_cameras * 6,)
  - len(best_cameras) == num_cameras
  - abs(best_value - detail.value) < 1e-6（浮動小数点演算の誤差を許容）
  - nit >= 0、nfev >= 0
  - elapsed_seconds >= 0
  - len(convergence_history) >= 1（少なくとも初期集団の最良値を含む）

### FR-04: テキストレポート生成

最適化結果をテキストレポートとして出力する。

- 関数名: `generate_optimization_report`
- 入力: result (OptimizationResult)
- 出力: str（複数行のテキスト）
- レポートの構成:
  1. ヘッダー: "=== Camera Placement Optimization Report ==="
  2. 最適化パラメータ: maxiter, popsize, tol, strategy, grid_spacing, eval_grid_spacing, penalty_weight, weights, num_cameras, seed
  3. 最適化結果サマリー: nit, nfev, elapsed_seconds (分・秒表記), success, message, best_value（Optimization Objective Value、小数点以下6桁）
  4. 品質スコア（評価グリッド）: quality_score, coverage_score, angle_score, projection_score
  5. 活動ボリューム別品質スコア: 各活動ボリューム（walking, seated, supine）の quality_score, coverage_score, angle_score, projection_score を quality_score の降順で表示。volume_qualities に対応する ActivityType が存在しない場合はスキップする
  6. カメラ配置: 各カメラの position と look_at（小数点以下3桁）
- 受け入れ基準:
  - レポートに上記6セクションが全て含まれること
  - 数値の書式: 品質スコアは小数点以下3桁、位置座標は小数点以下3桁、時間は小数点以下1桁

### FR-05: レポート保存

テキストレポートをファイルに保存する。

- 関数名: `save_optimization_report`
- 入力: report (str), filepath (str | Path)
- 出力: Path（保存先のパスオブジェクト）
- filepath の親ディレクトリが存在しない場合は自動作成する
- エンコーディング: UTF-8
- 受け入れ基準: 指定パスにファイルが作成され、内容が report と一致すること

### FR-06: 結果の3D可視化

最適化結果のカメラ配置とカバレッジマップを3Dインタラクティブ表示する。

- 関数名: `visualize_result`
- 入力:

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| result | OptimizationResult | (必須) | 最適化結果 |
| room | Room | (必須) | 病室モデル |
| show_frustums | bool | True | 視錐台の表示 |
| show_grid | bool | True | カバレッジマップの表示 |
| frustum_far | float | 3.0 | 視錐台の表示用ファークリップ距離 [m]。0 より大きい |

- 出力: go.Figure
- F11 の create_scene を使用して3Dシーンを生成する
- タイトル: "Optimized Camera Placement (Quality: {quality_score:.3f})"
- 受け入れ基準:
  - 返り値が go.Figure であること
  - title に品質スコアが含まれること
  - frustum_far <= 0 の場合、ValueError が送出されること

### FR-07: 収束プロット生成

最適化の収束履歴をプロットする。

- 関数名: `create_convergence_plot`
- 入力: result (OptimizationResult)
- 出力: go.Figure
- X軸: 世代番号（1 始まり）
- Y軸: 目的関数値（最良値）
- タイトル: "Convergence History"
- 線の色: 青（"rgb(31, 119, 180)"）
- convergence_history が空の場合: 空のプロットを返す（データなし）
- 受け入れ基準:
  - 返り値が go.Figure であること
  - data にトレースが1つ含まれること
  - トレースの x 値が [1, 2, ..., len(convergence_history)] であること
  - トレースの y 値が convergence_history と一致すること

## 4. 非機能要求

### パフォーマンス

- デフォルト設定（maxiter=50, popsize=5, grid_spacing=0.5, num_cameras=6）での最適化完了時間: 60分以内
- generate_optimization_report の生成時間: 1秒以内
- visualize_result の生成時間: 30秒以内（評価グリッドでのカバレッジ計算を含むため）
- create_convergence_plot の生成時間: 1秒以内

### 対応環境

- Python 3.12
- numpy >= 2.4.2（既存依存）
- scipy >= 1.15（新規追加。differential_evolution に必要）
- plotly >= 6.6.0（既存依存）

### 信頼性

- optimize_placement は最適化が収束しなかった場合でも例外を送出しない。success=False の OptimizationResult を返す
- optimize_placement は有限の best_value を常に返す

## 5. 制約条件

- 使用ライブラリ: scipy（新規追加）、numpy、plotly（既存）
- F14（ObjectiveFunction, ObjectiveResult, params_to_cameras, cameras_to_params）の既存インターフェースを変更しない
- F11（create_scene, save_html）の既存インターフェースを変更しない
- F10（evaluate_placement, EvaluationResult）の既存インターフェースを変更しない
- F12（get_preset, create_cameras, PlacementPreset）の既存インターフェースを変更しない
- scipy.optimize.differential_evolution を直接使用する（ラッパーライブラリは使用しない）
- 最適化中の並列評価（workers パラメータ）は使用しない（workers=1 固定）

## 6. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 最適化設定 | Must |
| FR-02 最適化実行 | Must |
| FR-03 最適化結果 | Must |
| FR-04 テキストレポート生成 | Must |
| FR-05 レポート保存 | Must |
| FR-06 結果の3D可視化 | Must |
| FR-07 収束プロット生成 | Should |

## 7. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| デフォルト設定での最適化 | 正常終了。OptimizationResult が返る |
| init_preset="upper_corners" | upper_corners プリセットを初期解として使用。正常終了 |
| init_preset と init_params を両方指定 | ValueError |
| init_preset に存在しないプリセット名 | KeyError |
| init_params の shape が不正 | ValueError |
| maxiter=1 | 1世代のみ実行。結果は粗いが正常終了 |
| popsize=1 | 集団サイズ = 1 × n_params。正常動作 |
| seed を指定して2回実行 | 同一の結果が得られる（再現性） |
| 最適化が tol に到達せず maxiter に達した場合 | success=False の結果が返る。例外は送出しない |
| convergence_history が空（理論上は発生しない） | create_convergence_plot は空のプロットを返す |
| config=None | OptimizationConfig() がデフォルト適用 |
| frustum_far <= 0 で visualize_result | ValueError |

## 8. スコープ外

- PSO（Particle Swarm Optimization）の実装（scipy に組み込みがなく、外部ライブラリが必要）
- 並列評価（workers > 1）（ObjectiveFunction のプロセス間共有の複雑さを回避）
- 最適化結果の JSON/バイナリ保存・復元（将来課題）
- プリセットとの自動比較レポート（F13 を手動で使用すれば可能）
- 多目的最適化（パレート最適化）
- セルフオクルージョンの考慮
- GUI による最適化パラメータ調整
