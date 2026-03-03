# 要求仕様書: F14 目的関数定義

## 1. プロジェクト概要

- **何を作るか**: 最適化アルゴリズム（F15）が使用する目的関数を定義するモジュール。6台のカメラの配置パラメータ（位置・注視点）を36次元のベクトルとして表現し、品質スコアの最大化（目的関数値の最小化）と設置領域制約のペナルティを統合した目的関数を提供する
- **なぜ作るか**: F15（最適化エンジン）がカメラ配置を最適化するために、パラメータ空間から品質スコアへのマッピングが必要。また、設置領域制約を満たさない配置にペナルティを与えることで、実行可能解への収束を促すため
- **誰が使うか**: F15（最適化エンジンモジュール）、開発者
- **どこで使うか**: Python 3.12 ローカル環境

## 2. 用語定義

| 用語 | 定義 |
|------|------|
| パラメータベクトル (parameter vector) | 6台のカメラの配置を表す36次元の1次元配列。shape (36,), dtype=float64 |
| パラメータ (parameter) | カメラ1台あたり6個の数値。[x, y, z, lx, ly, lz] = [位置x, 位置y, 位置z, 注視点x, 注視点y, 注視点z] |
| 目的関数 (objective function) | パラメータベクトルを入力とし、最小化すべきスカラー値を返す関数 |
| 目的関数値 (objective value) | 目的関数の出力。`-quality_score + penalty`。最小化対象 |
| 品質スコア (quality score) | F10 `evaluate_placement` が返す `quality_score`。値域 [0.0, 1.0]。最大化したい指標 |
| ペナルティ (penalty) | 制約違反に対する罰則値。0以上。制約を満たしている場合は 0.0 |
| ペナルティ係数 (penalty weight) | 位置制約ペナルティ値にかける係数。デフォルト 100.0 |
| 設置領域制約 (placement constraint) | カメラ位置が `room.camera_zone` 内にあること |
| 実行可能解 (feasible solution) | 全ての制約を満たし、有効なカメラ構成であるパラメータベクトル |
| 非実行可能解 (infeasible solution) | 1つ以上の制約に違反、または無効なカメラ構成であるパラメータベクトル |
| バウンド (bounds) | 各パラメータの探索範囲の上下限。shape (36, 2) |
| 不正カメラ構成 (invalid camera configuration) | position == look_at、または forward ベクトルと up_hint が平行であるカメラ構成。Camera コンストラクタが ValueError を送出する |

## 3. 機能要求一覧

### FR-01: パラメータベクトルとカメラ間の変換

パラメータベクトル（36次元）と Camera リスト（6台）の相互変換を行う。

**params_to_cameras**:
- 入力:
  - `params`: np.ndarray, shape (num_cameras * 6,), dtype=float64
  - `num_cameras`: int（デフォルト 6）
  - `intrinsics`: CameraIntrinsics | None（デフォルト None）
- 出力: list[Camera]（num_cameras 個）
- パラメータの配置:
  - params[i*6 : i*6+3] がカメラ i の位置 (x, y, z)
  - params[i*6+3 : i*6+6] がカメラ i の注視点 (lx, ly, lz)
- intrinsics が None の場合はデフォルトの CameraIntrinsics を使用
- 不正なカメラ構成の場合は ValueError を送出（Camera のコンストラクタが送出する）
- 受け入れ基準: params_to_cameras で6台の Camera が生成されること

**cameras_to_params**:
- 入力: cameras (list[Camera])
- 出力: np.ndarray, shape (len(cameras) * 6,), dtype=float64
- cameras[i].position → params[i*6 : i*6+3]
- cameras[i].look_at → params[i*6+3 : i*6+6]
- 受け入れ基準: cameras_to_params(params_to_cameras(params)) と元の params が一致すること（atol=1e-10）

### FR-02: パラメータ境界の定義

各パラメータの探索範囲（上下限）を定義する。

- 入力: room (Room)、num_cameras (int, デフォルト 6)
- 出力: np.ndarray, shape (num_cameras * 6, 2)。[:,0] が下限、[:,1] が上限
- 位置パラメータ（params[i*6+0], params[i*6+1], params[i*6+2]）:
  - 下限: room.camera_zone.min_point（デフォルト [0.2, 0.2, 0.2]）
  - 上限: room.camera_zone.max_point（デフォルト [2.6, 3.3, 2.3]）
- 注視点パラメータ（params[i*6+3], params[i*6+4], params[i*6+5]）:
  - 下限: [0.0, 0.0, 0.0]（部屋の原点）
  - 上限: [room.width, room.depth, room.height]（デフォルト [2.8, 3.5, 2.5]）
- 受け入れ基準: bounds.shape == (36, 2)。位置バウンドが camera_zone に一致。注視点バウンドが部屋の AABB に一致

### FR-03: 設置領域制約のペナルティ計算

カメラ位置が設置可能領域外の場合にペナルティ値を計算する。

- 入力: positions (np.ndarray, shape (M, 3))、camera_zone (AABB)
- 出力: float（ペナルティ値、0以上。ペナルティ係数は未適用）
- 計算方法:
  - 各カメラ位置の各次元について、camera_zone からの逸脱量を計算する
  - 下限逸脱量 = max(0, zone_min[d] - pos[d])
  - 上限逸脱量 = max(0, pos[d] - zone_max[d])
  - ペナルティ = 全カメラ・全次元の (下限逸脱量^2 + 上限逸脱量^2) の総和
- 全カメラが設置可能領域内の場合、ペナルティは 0.0
- 受け入れ基準:
  - 全カメラが範囲内 → 0.0
  - カメラ位置が1次元で 0.1m 逸脱 → ペナルティ = 0.01（= 0.1^2）

### FR-04: 目的関数クラス

最適化用の目的関数をクラスとして提供する。

- クラス名: `ObjectiveFunction`
- 初期化パラメータ:

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| room | Room | (必須) | 病室モデル |
| grid_spacing | float | 0.2 | グリッド間隔 [m] |
| near | float | 0.1 | ニアクリップ距離 [m] |
| far | float | 10.0 | ファークリップ距離 [m] |
| target_ppm | float | 500.0 | 目標投影解像度 [px/m] |
| weight_coverage | float | 0.5 | カバレッジの重み |
| weight_angle | float | 0.3 | 角度スコアの重み |
| weight_projection | float | 0.2 | 投影スコアの重み |
| penalty_weight | float | 100.0 | ペナルティ係数。0.0 以上 |
| num_cameras | int | 6 | カメラ台数。1 以上 |

- `__call__(params: np.ndarray) -> float`:
  - パラメータベクトルを受け取り、目的関数値（最小化対象のスカラー）を返す
  - 目的関数値 = -quality_score + total_penalty
  - total_penalty = penalty_weight * position_penalty + infeasible_penalty
  - position_penalty: FR-03 で計算される設置領域制約ペナルティ（係数未適用）
  - infeasible_penalty: 不正なカメラ構成の場合 1.0、正常な場合 0.0
  - 実行可能解の値域: [-1.0, 0.0]
  - 非実行可能解の値域: 正の値
  - params の shape が不正な場合は ValueError を送出
  - それ以外の例外（カメラ構成不正、評価エラー）は送出しない。ペナルティ付きのスカラー値を返す
- `evaluate_detail(params: np.ndarray) -> ObjectiveResult`:
  - パラメータベクトルを受け取り、詳細な評価結果を返す
  - params の shape が不正な場合は ValueError を送出
  - それ以外の例外は送出しない
- `bounds` プロパティ: np.ndarray, shape (num_cameras * 6, 2)
- `n_params` プロパティ: int（= num_cameras * 6）
- 初期化時のバリデーション:
  - num_cameras <= 0 → ValueError
  - penalty_weight < 0 → ValueError
  - weight_coverage, weight_angle, weight_projection のいずれかが負 → ValueError
  - weight_coverage + weight_angle + weight_projection == 0 → ValueError
  - grid_spacing, near, far, target_ppm のバリデーションは evaluate_placement に委任する（F10 の責務）
- 受け入れ基準:
  - コーナー配置のパラメータで `__call__` を呼び出した場合、値が [-1.0, 0.0] の範囲内
  - 全位置が範囲外のパラメータで `__call__` を呼び出した場合、値が正

### FR-05: 目的関数の評価結果

目的関数の詳細な評価結果を保持するデータ構造。

- データクラス名: `ObjectiveResult`
- フィールド:

| フィールド | 型 | 説明 |
|---|---|---|
| value | float | 目的関数値（`__call__` の戻り値と同一）。-quality_score + penalty |
| quality_score | float | F10 の品質スコア [0.0, 1.0]。不正な場合は 0.0 |
| penalty | float | ペナルティ値合計（penalty_weight 適用済み + infeasible_penalty）。0.0 以上 |
| is_feasible | bool | 全制約を満たし、有効なカメラ構成の場合 True |
| evaluation | EvaluationResult &#124; None | F10 の評価結果。不正な場合は None |

- 受け入れ基準: value == -quality_score + penalty

## 4. 非機能要求

### パフォーマンス

- `__call__` の計算時間: grid_spacing=0.2 で 5秒以内（`evaluate_placement` の計算時間に支配される）
- `params_to_cameras` の計算時間: 1ms 以内
- `cameras_to_params` の計算時間: 1ms 以内
- `get_parameter_bounds` の計算時間: 1ms 以内
- `calculate_position_penalty` の計算時間: 1ms 以内

### 対応環境

- Python 3.12
- numpy >= 2.4.2（既存依存）

### 信頼性

- `__call__` と `evaluate_detail` は params の shape 不正以外の例外を送出しない（不正なカメラ構成やF10評価エラーに対してはペナルティ付きのスカラー値を返す）
- `__call__` は常に有限の float 値を返す（NaN, inf は返さない）

## 5. 制約条件

- 使用ライブラリ: numpy のみ（標準ライブラリは使用可）
- F10（`evaluate_placement`, `EvaluationResult`）の既存インターフェースを変更しない
- F02（`Camera`, `CameraIntrinsics`, `create_camera`）の既存インターフェースを変更しない
- F01（`Room`, `AABB`）の既存インターフェースを変更しない
- カメラ台数はデフォルト 6 だが、任意の正の整数で動作すること
- up_hint は固定 [0, 0, 1]（Camera のデフォルト値を使用）

## 6. 優先順位

| 要件 | MoSCoW |
|------|--------|
| FR-01 パラメータ変換 | Must |
| FR-02 パラメータ境界 | Must |
| FR-03 ペナルティ計算 | Must |
| FR-04 目的関数クラス | Must |
| FR-05 評価結果 | Must |

## 7. エッジケースの期待動作

| ケース | 期待動作 |
|--------|---------|
| 全カメラが設置可能領域内の良好な配置 | penalty = 0.0、value = -quality_score、is_feasible = True |
| 1台のカメラが領域外 | penalty > 0、value > -quality_score |
| 全カメラが領域外 | penalty が大きい正の値、value が正の値 |
| position == look_at のカメラが存在 | quality_score = 0.0、is_feasible = False、infeasible_penalty 1.0 加算 |
| forward // up_hint のカメラが存在 | quality_score = 0.0、is_feasible = False、infeasible_penalty 1.0 加算 |
| num_cameras = 1 | 正常動作。params shape (6,)、bounds shape (6, 2) |
| num_cameras = 0 | ValueError |
| num_cameras < 0 | ValueError |
| params の shape が (num_cameras * 6,) でない | ValueError |
| cameras が空リスト | cameras_to_params で ValueError |
| penalty_weight = 0.0 | 正常動作。設置領域制約ペナルティは 0 だが infeasible_penalty は 1.0 のまま |
| penalty_weight < 0 | ObjectiveFunction.__init__ で ValueError |
| params に NaN を含む | Camera 構成不正として処理。is_feasible = False、infeasible_penalty 1.0 加算 |
| params に inf を含む | Camera 構成不正として処理。is_feasible = False、infeasible_penalty 1.0 加算 |
| weight_coverage, weight_angle, weight_projection が不正（負値、合計0） | ObjectiveFunction.__init__ で ValueError（evaluate_placement に渡す前に検証） |

## 8. スコープ外

- 最適化アルゴリズムの実装（F15 の責務）
- カメラ間の最小距離制約（将来課題として検討）
- セルフオクルージョンの考慮
- カメラの配置対称性を利用した探索空間の削減（F15 で検討）
- 注視点の活動ボリューム内制約（bounds で部屋内に制限するのみ）
- 目的関数の勾配計算（差分進化・PSO は勾配不要）
