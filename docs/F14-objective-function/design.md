# 機能設計書: F14 目的関数定義

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 4.1 `params_to_cameras`、4.2 `cameras_to_params` |
| FR-02 | 4.3 `get_parameter_bounds` |
| FR-03 | 4.4 `calculate_position_penalty` |
| FR-04 | 3.2 `ObjectiveFunction`、4.5〜4.9、5.1 目的関数の処理フロー |
| FR-05 | 3.1 `ObjectiveResult` |

## 2. ファイル構成

```
src/camera_placement/
  optimization/
    __init__.py             # 新規作成: F14 の公開シンボル
    objective.py            # 新規作成: F14 メインモジュール
tests/
  test_objective.py         # 新規作成: F14 テスト
tests/results/
  F14_test_result.txt       # テスト結果
```

ファイル名は `objective.py` とする（`docs/plan.md` の想定ファイル構成に従う）。

## 3. データ構造

### 3.1 ObjectiveResult dataclass

```python
@dataclass
class ObjectiveResult:
    """目的関数の詳細な評価結果。

    Attributes:
        value: 目的関数値（最小化対象）。-quality_score + penalty。
        quality_score: F10 品質スコア [0.0, 1.0]。不正な場合は 0.0。
        penalty: ペナルティ値合計（penalty_weight 適用済み + infeasible_penalty）。0.0 以上。
        is_feasible: 全制約を満たし、有効なカメラ構成の場合 True。
        evaluation: F10 の評価結果。不正な場合は None。
    """

    value: float
    quality_score: float
    penalty: float
    is_feasible: bool
    evaluation: EvaluationResult | None
```

- `dataclass`（`frozen` なし）。結果の読み取り専用用途だが、frozen にする必要はない（EvaluationResult が frozen でないため）
- `value == -quality_score + penalty` が常に成立する

### 3.2 ObjectiveFunction クラス

```python
class ObjectiveFunction:
    """最適化用の目的関数。

    パラメータベクトル（num_cameras * 6 次元）からカメラ配置を評価し、
    最小化すべきスカラー値を返す。

    目的関数値 = -quality_score + penalty_weight * position_penalty + infeasible_penalty

    Attributes:
        _room: 病室モデル。
        _grid_spacing: グリッド間隔 [m]。
        _near: ニアクリップ距離 [m]。
        _far: ファークリップ距離 [m]。
        _target_ppm: 目標投影解像度 [px/m]。
        _weight_coverage: カバレッジの重み。
        _weight_angle: 角度スコアの重み。
        _weight_projection: 投影スコアの重み。
        _penalty_weight: ペナルティ係数。
        _num_cameras: カメラ台数。
        _bounds: パラメータの上下限。shape (n_params, 2)。
    """
```

- `__call__` で callable（scipy の最適化関数にそのまま渡せる）
- 初期化時に bounds を事前計算して保持する

## 4. 公開関数・メソッド設計

### 4.1 params_to_cameras

```python
def params_to_cameras(
    params: np.ndarray,
    num_cameras: int = 6,
    intrinsics: CameraIntrinsics | None = None,
) -> list[Camera]:
    """パラメータベクトルから Camera リストを生成する。

    Args:
        params: パラメータベクトル。shape (num_cameras * 6,)。
            params[i*6 : i*6+3] がカメラ i の位置 (x, y, z)。
            params[i*6+3 : i*6+6] がカメラ i の注視点 (lx, ly, lz)。
        num_cameras: カメラ台数。1 以上。
        intrinsics: カメラ内部パラメータ。None の場合はデフォルト。

    Returns:
        Camera のリスト（num_cameras 個）。

    Raises:
        ValueError: num_cameras が 0 以下の場合。
        ValueError: params の shape が (num_cameras * 6,) でない場合。
        ValueError: position == look_at の場合（Camera.__post_init__ による）。
        ValueError: forward // up_hint の場合（Camera.__post_init__ による）。
    """
```

### 4.2 cameras_to_params

```python
def cameras_to_params(cameras: list[Camera]) -> np.ndarray:
    """Camera リストからパラメータベクトルを生成する。

    Args:
        cameras: Camera のリスト。1台以上。

    Returns:
        パラメータベクトル。shape (len(cameras) * 6,), dtype=float64。

    Raises:
        ValueError: cameras が空リストの場合。
    """
```

### 4.3 get_parameter_bounds

```python
def get_parameter_bounds(
    room: Room,
    num_cameras: int = 6,
) -> np.ndarray:
    """パラメータの探索範囲（上下限）を取得する。

    Args:
        room: 病室モデル。
        num_cameras: カメラ台数。1 以上。

    Returns:
        shape (num_cameras * 6, 2) の配列。[:,0] が下限、[:,1] が上限。

    Raises:
        ValueError: num_cameras が 0 以下の場合。
    """
```

### 4.4 calculate_position_penalty

```python
def calculate_position_penalty(
    positions: np.ndarray,
    camera_zone: AABB,
) -> float:
    """カメラ位置の設置領域制約ペナルティを計算する。

    各カメラ位置が camera_zone から逸脱している量の二乗和を返す。
    ペナルティ係数は適用しない（呼び出し元が掛ける）。

    Args:
        positions: カメラ位置。shape (M, 3)。
        camera_zone: カメラ設置可能領域。

    Returns:
        ペナルティ値。0.0 以上。全カメラが範囲内なら 0.0。
    """
```

### 4.5 ObjectiveFunction.__init__

```python
def __init__(
    self,
    room: Room,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
    target_ppm: float = 500.0,
    weight_coverage: float = 0.5,
    weight_angle: float = 0.3,
    weight_projection: float = 0.2,
    penalty_weight: float = 100.0,
    num_cameras: int = 6,
) -> None:
    """目的関数を初期化する。

    Args:
        room: 病室モデル。
        grid_spacing: グリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。
        target_ppm: 目標投影解像度 [px/m]。
        weight_coverage: カバレッジの重み。
        weight_angle: 角度スコアの重み。
        weight_projection: 投影スコアの重み。
        penalty_weight: ペナルティ係数。0.0 以上。
        num_cameras: カメラ台数。1 以上。

    Raises:
        ValueError: num_cameras が 0 以下の場合。
        ValueError: penalty_weight が負の場合。
        ValueError: weight_coverage, weight_angle, weight_projection のいずれかが負の場合。
        ValueError: weight_coverage + weight_angle + weight_projection が 0 の場合。
    """
```

### 4.6 ObjectiveFunction.__call__

```python
def __call__(self, params: np.ndarray) -> float:
    """目的関数を評価する。

    Args:
        params: パラメータベクトル。shape (n_params,)。

    Returns:
        目的関数値。最小化対象のスカラー値。
        実行可能解: [-1.0, 0.0]、非実行可能解: 正の値。

    Raises:
        ValueError: params の shape が (n_params,) でない場合。
    """
```

### 4.7 ObjectiveFunction.evaluate_detail

```python
def evaluate_detail(self, params: np.ndarray) -> ObjectiveResult:
    """目的関数を評価し、詳細結果を返す。

    Args:
        params: パラメータベクトル。shape (n_params,)。

    Returns:
        ObjectiveResult インスタンス。

    Raises:
        ValueError: params の shape が (n_params,) でない場合。
    """
```

### 4.8 ObjectiveFunction.bounds プロパティ

```python
@property
def bounds(self) -> np.ndarray:
    """パラメータの上下限。

    Returns:
        shape (n_params, 2)。[:,0] が下限、[:,1] が上限。
    """
```

### 4.9 ObjectiveFunction.n_params プロパティ

```python
@property
def n_params(self) -> int:
    """パラメータ数。num_cameras * 6。"""
```

## 5. アルゴリズム

### 5.1 目的関数の処理フロー（evaluate_detail）

```
入力: params (shape (n_params,))
  │
  ├── Step 1: params の shape 検証
  │           params.shape != (n_params,) → ValueError
  │
  ├── Step 2: カメラ位置の抽出と制約ペナルティ計算
  │           positions を params から抽出: shape (num_cameras, 3)
  │             positions[i] = params[i*6 : i*6+3]
  │           pos_penalty_raw = calculate_position_penalty(positions, room.camera_zone)
  │           pos_penalty = penalty_weight * pos_penalty_raw
  │
  ├── Step 3: Camera オブジェクトの生成（try-except）
  │           try:
  │               cameras = params_to_cameras(params, num_cameras)
  │           except (ValueError, Exception):
  │               # 不正なカメラ構成（position == look_at, forward // up_hint, NaN 等）
  │               infeasible_penalty = 1.0
  │               total_penalty = pos_penalty + infeasible_penalty
  │               return ObjectiveResult(
  │                   value=total_penalty,     # -0.0 + total_penalty
  │                   quality_score=0.0,
  │                   penalty=total_penalty,
  │                   is_feasible=False,
  │                   evaluation=None,
  │               )
  │
  ├── Step 4: F10 で品質スコアを計算（try-except）
  │           # volumes=None（デフォルト）を使用。evaluate_placement 内で
  │           # create_activity_volumes(room, grid_spacing) が自動生成する。
  │           # 目的関数は配置全体の quality_score のみ使用するため、
  │           # volumes を明示的に渡す必要はない。
  │           try:
  │               evaluation = evaluate_placement(
  │                   cameras, room,
  │                   grid_spacing=grid_spacing, near=near, far=far,
  │                   target_ppm=target_ppm,
  │                   weight_coverage=weight_coverage,
  │                   weight_angle=weight_angle,
  │                   weight_projection=weight_projection,
  │               )
  │               quality_score = evaluation.quality.quality_score
  │           except Exception:
  │               # 評価中のエラー
  │               infeasible_penalty = 1.0
  │               total_penalty = pos_penalty + infeasible_penalty
  │               return ObjectiveResult(
  │                   value=total_penalty,
  │                   quality_score=0.0,
  │                   penalty=total_penalty,
  │                   is_feasible=False,
  │                   evaluation=None,
  │               )
  │
  ├── Step 5: 実行可能性の判定
  │           is_feasible = (pos_penalty_raw == 0.0)
  │
  ├── Step 6: 目的関数値の計算
  │           value = -quality_score + pos_penalty
  │
  └── Step 7: 結果を返す
              return ObjectiveResult(
                  value=value,
                  quality_score=quality_score,
                  penalty=pos_penalty,
                  is_feasible=is_feasible,
                  evaluation=evaluation,
              )
```

`__call__` は `evaluate_detail` を呼び出し、`result.value` のみを返す。

### 5.2 パラメータ変換 (params_to_cameras)

```
入力: params (shape (num_cameras * 6,)), num_cameras, intrinsics
  │
  ├── Step 1: バリデーション
  │           num_cameras <= 0 → ValueError("num_cameras must be positive")
  │           params = np.asarray(params, dtype=np.float64)
  │           params.shape != (num_cameras * 6,) → ValueError
  │
  ├── Step 2: params を (num_cameras, 6) に reshape
  │           reshaped = params.reshape(num_cameras, 6)
  │
  ├── Step 3: 各カメラを生成
  │           cameras = []
  │           for i in range(num_cameras):
  │               position = reshaped[i, 0:3]
  │               look_at = reshaped[i, 3:6]
  │               cam = create_camera(
  │                   position=position,
  │                   look_at=look_at,
  │                   intrinsics=intrinsics,
  │               )
  │               cameras.append(cam)
  │
  └── Step 4: 返す
              return cameras
```

`create_camera` は intrinsics が None の場合にデフォルトの CameraIntrinsics を使用する。

### 5.3 パラメータ変換 (cameras_to_params)

```
入力: cameras (list[Camera])
  │
  ├── Step 1: バリデーション
  │           len(cameras) == 0 → ValueError("cameras must not be empty")
  │
  ├── Step 2: 各カメラから位置と注視点を取得
  │           params = np.zeros(len(cameras) * 6, dtype=np.float64)
  │           for i, cam in enumerate(cameras):
  │               params[i*6 : i*6+3] = cam.position
  │               params[i*6+3 : i*6+6] = cam.look_at
  │
  └── Step 3: 返す
              return params
```

### 5.4 ペナルティ計算 (calculate_position_penalty)

```
入力: positions (shape (M, 3)), camera_zone (AABB)
  │
  ├── Step 1: 各次元の逸脱量を計算
  │           positions = np.asarray(positions, dtype=np.float64)
  │           # 下限からの逸脱（zone_min より小さい場合に正）
  │           lower_violation = np.maximum(0.0, camera_zone.min_point - positions)
  │           # 上限からの逸脱（zone_max より大きい場合に正）
  │           upper_violation = np.maximum(0.0, positions - camera_zone.max_point)
  │
  ├── Step 2: 二乗和を計算
  │           penalty = float(np.sum(lower_violation ** 2) + np.sum(upper_violation ** 2))
  │
  └── Step 3: 返す
              return penalty
```

### 5.5 パラメータ境界 (get_parameter_bounds)

```
入力: room (Room), num_cameras (int)
  │
  ├── Step 1: バリデーション
  │           num_cameras <= 0 → ValueError("num_cameras must be positive")
  │
  ├── Step 2: 1台分のバウンドを定義
  │           # 位置: camera_zone の範囲
  │           # 注視点: 部屋全体の範囲
  │           single_bounds = np.array([
  │               [room.camera_zone.min_point[0], room.camera_zone.max_point[0]],  # x
  │               [room.camera_zone.min_point[1], room.camera_zone.max_point[1]],  # y
  │               [room.camera_zone.min_point[2], room.camera_zone.max_point[2]],  # z
  │               [0.0, room.width],   # lx
  │               [0.0, room.depth],   # ly
  │               [0.0, room.height],  # lz
  │           ])  # shape (6, 2)
  │
  ├── Step 3: num_cameras 台分に繰り返す
  │           bounds = np.tile(single_bounds, (num_cameras, 1))
  │           # shape (num_cameras * 6, 2)
  │
  └── Step 4: 返す
              return bounds
```

### 5.6 位置パラメータの抽出

ObjectiveFunction 内でカメラ位置を抽出する際は、reshape + スライスで行う:

```python
reshaped = params.reshape(num_cameras, 6)
positions = reshaped[:, 0:3]  # shape (num_cameras, 3)
```

### 5.7 データフロー図

```
params (36,)
    │
    ├── reshape → (6, 6)
    │     │
    │     ├── [:, 0:3] → positions (6, 3)
    │     │                    │
    │     │     calculate_position_penalty(positions, camera_zone)
    │     │                    │
    │     │                    ▼
    │     │             pos_penalty_raw (float, ≥ 0)
    │     │                    │
    │     │              × penalty_weight
    │     │                    │
    │     │                    ▼
    │     │              pos_penalty (float, ≥ 0)
    │     │
    │     └── params_to_cameras(params, num_cameras)
    │              │
    │         try/except
    │              │
    │      ┌───────┴────────┐
    │      │成功             │失敗
    │      │                 │
    │      ▼                 ▼
    │   cameras (6台)    ObjectiveResult(
    │      │                value=pos_penalty + 1.0,
    │      │                quality_score=0.0,
    │      │                penalty=pos_penalty + 1.0,
    │      │                is_feasible=False,
    │      │                evaluation=None)
    │      │
    │      ▼
    │   evaluate_placement(cameras, room, ...)
    │      │
    │   try/except
    │      │
    │   ┌──┴──────────┐
    │   │成功          │失敗
    │   │              │
    │   ▼              ▼
    │   EvaluationResult  ObjectiveResult(同上)
    │   │
    │   ▼
    │   quality_score = evaluation.quality.quality_score
    │   is_feasible = (pos_penalty_raw == 0.0)
    │   value = -quality_score + pos_penalty
    │   │
    │   ▼
    │   ObjectiveResult(
    │       value=value,
    │       quality_score=quality_score,
    │       penalty=pos_penalty,
    │       is_feasible=is_feasible,
    │       evaluation=evaluation)
    │
    └── __call__: return result.value
```

## 6. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| num_cameras <= 0 | `ValueError("num_cameras must be positive")` を送出 | `__init__`, `params_to_cameras`, `get_parameter_bounds` |
| penalty_weight < 0 | `ValueError("penalty_weight must be non-negative")` を送出 | `__init__` |
| params の shape 不正 | `ValueError` を送出 | `__call__`, `evaluate_detail`, `params_to_cameras` |
| cameras が空リスト | `ValueError("cameras must not be empty")` を送出 | `cameras_to_params` |
| position == look_at（Camera 構成不正） | `__call__`/`evaluate_detail` 内でキャッチし、ObjectiveResult(is_feasible=False) を返す。`params_to_cameras` 単体では ValueError を送出 | Camera.__post_init__ |
| forward // up_hint（Camera 構成不正） | 同上 | Camera.__post_init__ |
| evaluate_placement 内部エラー | `__call__`/`evaluate_detail` 内でキャッチし、ObjectiveResult(is_feasible=False) を返す | evaluate_placement |
| params に NaN 含む | Camera 構成不正として処理（上記と同様）。infeasible_penalty 加算 | `__call__`, `evaluate_detail` |
| params に inf 含む | Camera 構成不正として処理（上記と同様）。infeasible_penalty 加算 | `__call__`, `evaluate_detail` |
| weight_coverage/angle/projection が負 | `ValueError` を送出 | `__init__` |
| weight の合計が 0 | `ValueError` を送出 | `__init__` |

**重要**: `__call__` と `evaluate_detail` は params の shape 不正以外の例外を送出しない。最適化アルゴリズムが任意のパラメータで目的関数を呼び出すため、常に有限の float 値を返す。params に NaN や inf が含まれる場合、Camera 構成が不正となり（Camera.__post_init__ が ValueError を送出するか、evaluate_placement 内で数値エラーが発生する）、try-except でキャッチされて infeasible として処理される。

## 7. 境界条件

| ケース | 期待動作 |
|--------|---------|
| 全カメラが camera_zone 内の良好な配置 | value ∈ [-1.0, 0.0]、penalty = 0.0、is_feasible = True |
| 全カメラが camera_zone 内だが品質が低い配置 | value ∈ [-1.0, 0.0]（0に近い）、penalty = 0.0、is_feasible = True |
| 1台が camera_zone から 0.5m 逸脱（1次元） | pos_penalty = 100.0 * 0.25 = 25.0、value > 0 |
| 全カメラが同一位置・同一注視点 | Camera 構成不正、value = pos_penalty + 1.0 |
| num_cameras = 1 | 正常動作、n_params = 6、bounds shape (6, 2) |
| params が全て bounds の下限値 | 正常動作。カメラは camera_zone の min_point に位置し、部屋の原点を注視 |
| params が全て bounds の上限値 | 正常動作。カメラは camera_zone の max_point に位置し、部屋の角を注視 |
| penalty_weight = 0.0 | pos_penalty = 0.0 となるが、infeasible_penalty = 1.0 は有効 |

## 8. 設計判断

### 8.1 パラメータ表現に position + look_at を採用する理由

- **採用案**: position (x, y, z) + look_at (x, y, z) = 6パラメータ/カメラ、合計36次元
- **却下案**: position (x, y, z) + pan (yaw) + tilt (pitch) = 5パラメータ/カメラ、合計30次元
  - 却下理由: Camera クラスが position + look_at を入力として受け取るため、角度↔look_at の変換コードが不要。plan.md で「6台×6パラメータ=36次元」と記載済み。また、look_at のバウンドは直感的に部屋内に制限できるが、角度のバウンドは周期性（2π の折り返し）の扱いが複雑になる

### 8.2 ペナルティ関数に二乗和を採用する理由

- **採用案**: ペナルティ = Σ(逸脱量^2)（二乗ペナルティ）
- **却下案1**: ペナルティ = Σ|逸脱量|（L1ペナルティ）
  - 却下理由: 境界付近で微分が不連続になり、一部の最適化手法で問題が生じる可能性がある
- **却下案2**: 死のペナルティ（制約違反なら固定の大きな値）
  - 却下理由: 制約違反の程度を反映しないため、最適化アルゴリズムが実行可能領域への戻り方向を判断できない。二乗ペナルティは違反量に応じた滑らかな勾配を提供する

### 8.3 ObjectiveFunction をクラスとして設計する理由

- **採用案**: クラス（`__call__` メソッドで callable）
- **却下案**: クロージャ（関数を返す関数）
  - 却下理由: bounds, n_params などのプロパティを自然に提供できる。evaluate_detail のような追加機能を持てる。F15 が bounds や n_params を参照しやすい

### 8.4 __call__ で例外を送出しない理由（shape 不正を除く）

- **採用案**: ValueError/Exception をキャッチしてペナルティ付きのスカラー値を返す
- **却下案**: 不正なパラメータで例外を送出する
  - 却下理由: scipy.optimize.differential_evolution や PSO などの最適化アルゴリズムは、目的関数が常にスカラー値を返すことを前提としている。例外を送出すると最適化が中断される。ただし params の shape 不正はプログラミングエラーであり、早期に検出すべきため ValueError を送出する

### 8.5 ペナルティ係数のデフォルト値を 100.0 とする根拠

- quality_score は [0, 1] の範囲。-quality_score は [-1, 0] の範囲
- position_penalty は逸脱量の二乗和。例: 1台が1次元で 0.1m 逸脱 → 0.01
- penalty_weight = 100 の場合: 0.1m 逸脱でペナルティ = 1.0
- これにより、微小な制約違反（0.1m）でも quality_score の最大改善幅（1.0）と同等のペナルティが発生する
- 実行可能領域内に収まるよう最適化アルゴリズムを誘導できる

### 8.6 不正なカメラ構成で infeasible_penalty = 1.0 を加算する根拠

- 不正なカメラ構成では evaluate_placement を実行できないため、quality_score = 0.0
- value = -0.0 + pos_penalty だが、pos_penalty = 0 の場合（位置は正しいが look_at が不正）value = 0.0 となる
- 品質スコア 0.0 の有効な解は value = 0.0 であり、これと区別できない
- infeasible_penalty = 1.0 を加算することで value >= 1.0 となり、任意の有効解（value ∈ [-1, 0]）より悪い値が保証される

### 8.7 注視点のバウンドを部屋全体とする理由

- **採用案**: 注視点のバウンドを部屋全体の AABB [0,0,0]〜[2.8,3.5,2.5] とする
- **却下案**: 注視点のバウンドを活動ボリュームに限定する
  - 却下理由: 最適化アルゴリズムが探索範囲を広く持つことで、意外な注視方向が高品質な配置を生む可能性がある。活動ボリュームは複数（歩行・座位・臥位）あり、1つに限定すると他の動作パターンに不利になる。部屋全体をバウンドとすることで十分な柔軟性を確保できる

### 8.8 params_to_cameras で create_camera を使用する理由

- **採用案**: `create_camera(position, look_at, intrinsics=intrinsics)` を使用
- **却下案**: `Camera(position=position, look_at=look_at, intrinsics=intrinsics or CameraIntrinsics())` を直接使用
  - 却下理由: F12（patterns.py）が `create_camera` を使用しており、一貫性を保つ。`create_camera` は intrinsics が None の場合にデフォルト値を使用する処理を担当する

### 8.9 is_feasible の判定に浮動小数点の厳密等価比較を使用する理由

- **採用案**: `is_feasible = (pos_penalty_raw == 0.0)` で厳密比較
- **却下案**: `is_feasible = (pos_penalty_raw < epsilon)` で近似比較
  - 却下理由: `calculate_position_penalty` は `np.maximum(0.0, zone_min - pos)` で逸脱量を計算する。位置が zone_min 以上の場合、`zone_min - pos <= 0` であり、`np.maximum(0.0, ...)` は数学的に正確に 0.0 を返す。浮動小数点の丸め誤差は発生しない（減算結果が 0 以下であれば `max` で 0.0 にクランプされるため）。したがって厳密等価比較で安全

### 8.10 evaluate_placement に volumes を渡さない理由

- **採用案**: `evaluate_placement(cameras, room, ...)` で volumes=None（デフォルト）を使用
- **却下案**: 活動ボリュームを事前生成して volumes パラメータとして渡す
  - 却下理由: 目的関数は `evaluation.quality.quality_score`（統合グリッド全体の品質スコア）のみを使用する。volumes=None の場合、`evaluate_placement` 内で `create_activity_volumes(room, grid_spacing)` が自動生成される。目的関数の呼び出しごとに volumes を事前生成するコストは小さく、コードの簡潔さを優先する

### 8.11 重みのバリデーションを __init__ で行う理由

- **採用案**: `__init__` で weight_coverage, weight_angle, weight_projection のバリデーションを行い、不正値なら ValueError
- **却下案**: `evaluate_placement` に委任し、`__call__` 内の try-except でキャッチする
  - 却下理由: 重みの不正値はプログラミングエラーであり、最適化実行前に検出すべき。`num_cameras` や `penalty_weight` のバリデーションも `__init__` で行っており、一貫性を保つ。F10 の `evaluate_placement` が既に `_validate_weights` を持つが、F14 は F10 の既存インターフェースを変更しない方針のため、F14 側でも独自にバリデーションする

### 8.12 grid_spacing, near, far, target_ppm のバリデーションを __init__ で行わない理由

- **採用案**: これらのパラメータのバリデーションは `evaluate_placement`（F10）に委任する
- **却下案**: `__init__` で独自にバリデーションする
  - 却下理由: これらのパラメータは `evaluate_placement` に直接渡されるもので、F10 側のバリデーションが最も正確。F14 で重複してバリデーションすると、F10 の仕様変更時に不整合が生じるリスクがある。重みのバリデーションとは異なり、これらのパラメータの有効範囲は F10 の内部実装に依存する

## 9. ログ・デバッグ設計

F14 はログ出力を行わない。F07〜F10 と同様の方針。デバッグ時は `evaluate_detail` を使用して詳細結果（quality_score、penalty、is_feasible、evaluation）を確認する。

## 10. ファイル・ディレクトリ設計

### 10.1 モジュールファイル

- パス: `src/camera_placement/optimization/objective.py`
- `src/camera_placement/optimization/__init__.py` を新規作成

### 10.2 テストファイル

- テストコード: `tests/test_objective.py`
- テスト結果: `tests/results/F14_test_result.txt`

## 11. 技術スタック

- **Python**: 3.12
- **numpy** (>=2.4.2): ベクトル演算（ペナルティ計算、パラメータ変換）
- **pytest**: テスト用
- 新規ライブラリの追加は不要

## 12. 依存機能との連携

### 12.1 F10（統合品質スコア）

- `evaluate_placement(cameras, room, ...)` でカメラ配置を評価
- `EvaluationResult` を `ObjectiveResult.evaluation` に保持
- インポート: `from camera_placement.evaluation.evaluator import evaluate_placement, EvaluationResult`

### 12.2 F02（カメラモデル）

- `create_camera(position, look_at, intrinsics)` でカメラオブジェクトを生成
- `Camera` クラスを型ヒントに使用
- `CameraIntrinsics` をカスタム内部パラメータの受け渡しに使用
- インポート: `from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera`

### 12.3 F01（空間モデル）

- `Room` で病室モデルを受け取る
- `AABB` で設置領域制約を参照（`room.camera_zone`）
- インポート: `from camera_placement.models.environment import Room, AABB`

## 13. 後続機能との接続点

| 後続機能 | 使用する要素 | 用途 |
|---------|------------|------|
| F15 最適化エンジン | `ObjectiveFunction` | 目的関数を scipy/PSO に渡す |
| F15 最適化エンジン | `ObjectiveFunction.bounds` | 探索範囲を最適化アルゴリズムに渡す |
| F15 最適化エンジン | `ObjectiveFunction.evaluate_detail` | 最適解の詳細評価 |
| F15 最適化エンジン | `params_to_cameras` | 最適パラメータから Camera リストを復元 |
| F15 最適化エンジン | `cameras_to_params` | 初期解の生成（プリセットからパラメータへ変換） |

F15 での使用イメージ:

```python
from camera_placement.optimization.objective import ObjectiveFunction, params_to_cameras
from camera_placement.models.environment import create_default_room

room = create_default_room()
obj = ObjectiveFunction(room, grid_spacing=0.2)

# scipy.optimize.differential_evolution で使用
from scipy.optimize import differential_evolution
result = differential_evolution(obj, bounds=obj.bounds.tolist(), maxiter=100)

# 最適解のカメラ配置を取得
best_cameras = params_to_cameras(result.x)
detail = obj.evaluate_detail(result.x)
print(f"最適品質スコア: {detail.quality_score:.3f}")
print(f"実行可能: {detail.is_feasible}")

# 初期解をプリセットから生成
from camera_placement.placement.patterns import get_preset, create_cameras
preset = get_preset("upper_corners")
preset_cameras = create_cameras(preset, room)
from camera_placement.optimization.objective import cameras_to_params
x0 = cameras_to_params(preset_cameras)
```

## 14. `optimization/__init__.py` の内容

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

__all__ = [
    "ObjectiveFunction",
    "ObjectiveResult",
    "calculate_position_penalty",
    "cameras_to_params",
    "get_parameter_bounds",
    "params_to_cameras",
]
```

## 15. テスト計画

テストファイル: `tests/test_objective.py`

### テスト用ヘルパー

```python
import pytest
import numpy as np
from camera_placement.optimization.objective import (
    ObjectiveFunction,
    ObjectiveResult,
    calculate_position_penalty,
    cameras_to_params,
    get_parameter_bounds,
    params_to_cameras,
)
from camera_placement.models.camera import Camera, CameraIntrinsics, create_camera
from camera_placement.models.environment import Room, AABB, create_default_room
from camera_placement.evaluation.evaluator import EvaluationResult


@pytest.fixture
def room() -> Room:
    return create_default_room()


@pytest.fixture
def objective(room: Room) -> ObjectiveFunction:
    return ObjectiveFunction(room, grid_spacing=0.5)  # テスト用に粗いグリッド


def _corner_params() -> np.ndarray:
    """テスト用コーナー配置のパラメータベクトル。

    upper_corners プリセットと同じ配置。
    """
    target = [1.4, 1.75, 0.9]
    cameras_data = [
        [0.2, 0.2, 2.3] + target,
        [2.6, 0.2, 2.3] + target,
        [0.2, 3.3, 2.3] + target,
        [2.6, 3.3, 2.3] + target,
        [1.4, 0.2, 2.3] + target,
        [1.4, 3.3, 2.3] + target,
    ]
    return np.array([v for cam in cameras_data for v in cam], dtype=np.float64)


def _out_of_zone_params() -> np.ndarray:
    """テスト用の範囲外パラメータベクトル。

    1台目のカメラ位置 x を 0.0 に設定（camera_zone 下限 0.2 を下回る）。
    """
    params = _corner_params()
    params[0] = 0.0  # x = 0.0 < 0.2
    return params
```

### カテゴリA: params_to_cameras / cameras_to_params

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 基本変換（往復） | コーナー配置 params | cameras_to_params(params_to_cameras(params)) と元 params が一致（atol=1e-10） | 往復一致 |
| A2 | カメラ位置の一致 | params の最初の3要素 [0.2, 0.2, 2.3] | cameras[0].position == params[0:3] | 位置抽出 |
| A3 | 注視点の一致 | params の次の3要素 [1.4, 1.75, 0.9] | cameras[0].look_at == params[3:6] | 注視点抽出 |
| A4 | 6台生成 | 36次元 params | len(cameras) == 6 | カメラ数 |
| A5 | shape 不正 | shape (35,) | ValueError | バリデーション |
| A6 | num_cameras=1 | shape (6,) の params | len(cameras) == 1 | 1台対応 |
| A7 | position == look_at | 同一座標 | ValueError | 不正構成 |
| A8 | cameras が空リスト | cameras_to_params([]) | ValueError | 空リスト |
| A9 | カスタム intrinsics | CameraIntrinsics(focal_length=5.0) | cameras[0].intrinsics.focal_length == 5.0 | intrinsics 伝播 |
| A10 | num_cameras=0 | num_cameras=0 | ValueError | バリデーション |

### テストA1の詳細

```
params = [0.2, 0.2, 2.3, 1.4, 1.75, 0.9, 2.6, 0.2, 2.3, 1.4, 1.75, 0.9, ...]  (36 要素)
cameras = params_to_cameras(params)
# cameras[0].position == [0.2, 0.2, 2.3]
# cameras[0].look_at == [1.4, 1.75, 0.9]
# cameras[1].position == [2.6, 0.2, 2.3]
# ...
roundtrip = cameras_to_params(cameras)
np.allclose(params, roundtrip, atol=1e-10) == True
```

### カテゴリB: get_parameter_bounds

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | shape の検証 | default_room, 6 | bounds.shape == (36, 2) | shape |
| B2 | 位置 x 下限 | default_room | bounds[0, 0] == 0.2 | camera_zone min_point[0] |
| B3 | 位置 x 上限 | default_room | bounds[0, 1] == 2.6 | camera_zone max_point[0] |
| B4 | 位置 y バウンド | default_room | bounds[1, 0] == 0.2, bounds[1, 1] == 3.3 | camera_zone y |
| B5 | 位置 z バウンド | default_room | bounds[2, 0] == 0.2, bounds[2, 1] == 2.3 | camera_zone z |
| B6 | 注視点 x バウンド | default_room | bounds[3, 0] == 0.0, bounds[3, 1] == 2.8 | room width |
| B7 | 注視点 y バウンド | default_room | bounds[4, 0] == 0.0, bounds[4, 1] == 3.5 | room depth |
| B8 | 注視点 z バウンド | default_room | bounds[5, 0] == 0.0, bounds[5, 1] == 2.5 | room height |
| B9 | 全カメラ同一バウンド | default_room | bounds[0:6] == bounds[6:12] == bounds[12:18] == ... | 繰り返し |
| B10 | num_cameras=1 | default_room, 1 | bounds.shape == (6, 2) | 1台 |
| B11 | num_cameras=0 | 0 | ValueError | バリデーション |

### カテゴリC: calculate_position_penalty

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | 全カメラ範囲内 | camera_zone 内の6台分の位置 | 0.0 | 制約充足 |
| C2 | x 下限逸脱 0.1m | x=0.1 (zone_min_x=0.2) | 0.01 | 1次元ペナルティ |
| C3 | x 上限逸脱 0.1m | x=2.7 (zone_max_x=2.6) | 0.01 | 上限側 |
| C4 | 複数次元逸脱 | x, y, z 各 0.1m 逸脱 | 0.03 | 複数次元 |
| C5 | 複数カメラ逸脱 | 2台が各1次元 0.1m 逸脱 | 0.02 | 複数カメラ |
| C6 | 大きな逸脱 | x=-1.0 (zone_min=0.2, 差1.2) | 1.44 | 大きな逸脱 |
| C7 | 境界上の位置 | 位置が camera_zone の min/max と完全一致 | 0.0 | 境界は範囲内 |

### テストC2の詳細計算

```
positions = [[0.1, 0.2, 2.3]]  # x が 0.1m 逸脱
camera_zone: min_point=[0.2, 0.2, 0.2], max_point=[2.6, 3.3, 2.3]

lower_violation = max(0, 0.2 - 0.1) = 0.1  (x のみ)
upper_violation = 0 (全次元)
penalty = 0.1^2 = 0.01
```

### カテゴリD: ObjectiveFunction の基本動作

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | コーナー配置の目的関数値 | コーナー配置 params | -1.0 <= value <= 0.0 | 基本動作 |
| D2 | value と quality_score, penalty の関係 | コーナー配置 params | value == -quality_score + penalty (atol=1e-10) | 値の整合性 |
| D3 | is_feasible = True | コーナー配置 params | is_feasible == True | 制約充足 |
| D4 | evaluation が非 None | コーナー配置 params | evaluation is not None | 評価結果保持 |
| D5 | evaluation が EvaluationResult | コーナー配置 params | isinstance(evaluation, EvaluationResult) | 型チェック |
| D6 | __call__ と evaluate_detail の一致 | コーナー配置 params | __call__(params) == evaluate_detail(params).value | 一致性 |
| D7 | bounds の shape | objective | bounds.shape == (36, 2) | bounds |
| D8 | n_params | objective | n_params == 36 | n_params |

### カテゴリE: ペナルティ

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | 範囲内 → penalty=0 | コーナー配置 params | penalty == 0.0 | 制約充足 |
| E2 | 範囲外 → penalty>0 | 位置を範囲外に変更した params | penalty > 0 | 制約違反 |
| E3 | 範囲外の方が目的関数値が大きい | 範囲内 vs 範囲外 | value_inside < value_outside | ペナルティ効果 |
| E4 | position == look_at | 同一座標の params | is_feasible == False, value > 0 | 不正構成 |
| E5 | penalty_weight の影響 | 同一範囲外 params、penalty_weight=10 vs 100 | penalty が 10 倍 | 係数 |
| E6 | 不正カメラの value >= 1.0 | position==look_at の params | value >= 1.0 | 有効解より悪い |

### テストE2の詳細

```
params = _out_of_zone_params()  # 1台目 x = 0.0
position_penalty = (0.2 - 0.0)^2 = 0.04
penalty_weight = 100.0 (ObjectiveFunction のデフォルト)
# ただしテスト fixture では grid_spacing=0.5
total_penalty = 100.0 * 0.04 = 4.0
# penalty > 0 を検証
```

### カテゴリF: エッジケース

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| F1 | num_cameras=1 の ObjectiveFunction | 1台分の params (shape (6,)) | 正常動作、float 値が返る | 最小カメラ数 |
| F2 | num_cameras=0 で初期化 | ObjectiveFunction(room, num_cameras=0) | ValueError | 不正カメラ数 |
| F3 | penalty_weight=0.0 | コーナー配置 + 範囲外 | pos_penalty == 0.0 | ペナルティ無効 |
| F4 | penalty_weight < 0 | ObjectiveFunction(room, penalty_weight=-1) | ValueError | 不正ペナルティ係数 |
| F5 | __call__ は shape 以外の例外を送出しない | position==look_at の params | float 値が返る（ValueError は送出されない） | 例外なし |
| F6 | params の shape 不正で ValueError | shape (35,) | ValueError | shape 検証 |

### カテゴリG: 統合テスト

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| G1 | コーナー配置 vs 密集配置 | 2種の params | コーナー配置の value < 密集配置の value | 弁別力 |
| G2 | プリセットからの変換 | F12 upper_corners → cameras_to_params → params_to_cameras | 変換後のカメラ位置・注視点が元と一致 | プリセット互換 |

### テストG1の詳細

```
# コーナー配置
corner_params = _corner_params()
corner_value = objective(corner_params)

# 密集配置（同一壁面に集中）
target = [1.4, 1.75, 0.9]
clustered_data = [
    [0.2, 0.2, 2.3] + target,
    [0.4, 0.2, 2.3] + target,
    [0.6, 0.2, 2.3] + target,
    [0.8, 0.2, 2.3] + target,
    [1.0, 0.2, 2.3] + target,
    [1.2, 0.2, 2.3] + target,
]
clustered_params = np.array([v for cam in clustered_data for v in cam])
clustered_value = objective(clustered_params)

# コーナー配置の方が良い（value が小さい = quality が高い）
assert corner_value < clustered_value
```

### テスト総数: 43 件

### テスト実行時間の注意

- `evaluate_placement` は計算負荷が高い。テスト用に `grid_spacing=0.5` を使用してグリッド点数を減らし、テスト時間を短縮する
- カテゴリA, B, C のテストは `evaluate_placement` を呼ばないため高速（1秒以内）
- カテゴリD, E, F, G のうち ObjectiveFunction の `__call__` を使用するテストは各数秒かかる
