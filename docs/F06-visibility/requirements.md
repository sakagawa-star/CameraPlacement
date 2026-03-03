# F06: 視認性統合 — 要求仕様書

## 目的

F04（視錐台判定）とF05（ベッドオクルージョン判定）を統合し、1台または複数台のカメラから3D空間内の各点が視認可能かを最終判定する機能を提供する。これはPhase 2（コアモデル）の最終機能であり、後続のF07（カバレッジ計算）が「6台全カメラでの視認カメラ数」を算出する際の基盤となる。

判定ロジック:
```
visible(camera, point) = is_in_frustum(camera, point) AND NOT is_occluded(camera, point)
```

## 入力パラメータ

### `check_visibility` 関数

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| camera | Camera | (必須) | F02のCameraインスタンス。position, look_at, up_hint, intrinsicsを持つ |
| points | np.ndarray, shape (N, 3) または (3,) | (必須) | 対象点群のワールド座標 [m] |
| bed_aabb | AABB | (必須) | ベッドのAABB。Room.bed から取得 |
| near | float | 0.1 | ニアクリップ距離 [m]。FrustumCheckerに渡す |
| far | float | 10.0 | ファークリップ距離 [m]。FrustumCheckerに渡す |
| eps | float | 1e-6 | オクルージョン判定の端点除外許容誤差。check_bed_occlusionに渡す |

### `check_visibility_multi_camera` 関数

| パラメータ | 型 | デフォルト値 | 説明 |
|---|---|---|---|
| cameras | list[Camera] | (必須) | カメラのリスト。len = M |
| points | np.ndarray, shape (N, 3) または (3,) | (必須) | 対象点群のワールド座標 [m] |
| bed_aabb | AABB | (必須) | ベッドのAABB |
| near | float | 0.1 | ニアクリップ距離 [m] |
| far | float | 10.0 | ファークリップ距離 [m] |
| eps | float | 1e-6 | オクルージョン判定の端点除外許容誤差 |

## 出力（提供する機能）

### 1. `check_visibility(camera, points, bed_aabb, near, far, eps) -> np.ndarray`

- 入力: カメラ、対象点群、ベッドAABB、near/far距離、eps
- 出力: shape (N,) のbool配列。True = 視認可能（視錐台内かつオクルージョンなし）
- 内部でFrustumChecker.is_visible()とcheck_bed_occlusion()を統合する
- 単一点 shape (3,) 入力時は shape (1,) で返す（F04/F05と同じ規約）

### 2. `check_visibility_multi_camera(cameras, points, bed_aabb, near, far, eps) -> np.ndarray`

- 入力: カメラリスト（M台）、対象点群（N点）、ベッドAABB、near/far距離、eps
- 出力: shape (M, N) のbool配列。visibility[i, j] = True ならカメラiから点jが視認可能
- 内部で各カメラについて `check_visibility` を呼ぶ

## 機能要件

### FR-01: 単一カメラ視認性判定

`check_visibility(camera, points, bed_aabb)` は以下を内部で実行する:

1. `FrustumChecker(camera=camera, near=near, far=far)` を生成
2. `frustum_checker.is_visible(points)` で視錐台内判定 → (N,) bool
3. `check_bed_occlusion(camera.position, points, bed_aabb, eps)` でオクルージョン判定 → (N,) bool
4. `in_frustum & ~occluded` を返す

### FR-02: 複数カメラ一括判定

`check_visibility_multi_camera(cameras, points, bed_aabb)` は以下を内部で実行する:

1. 各カメラについて `check_visibility` を呼び出し
2. 結果を (M, N) の行列に格納して返す

### FR-03: F07への接続性

F07が以下のように使用することを保証する:
```python
visibility_matrix = check_visibility_multi_camera(cameras, grid_points, bed_aabb)
visible_count = visibility_matrix.sum(axis=0)  # (N,) int: 各点の視認カメラ数
```

### FR-04: 入力形状の柔軟性

- points は shape (N, 3) と (3,) の両方を受け付ける
- 単一点入力時も shape (1,) の結果を返す（F04/F05との一貫性）

### FR-05: パラメータの透過的受け渡し

- near, far は FrustumChecker にそのまま渡す
- eps は check_bed_occlusion にそのまま渡す
- F06自身は near/far/eps のバリデーションを行わない（F04/F05が行う）

## 後続機能が必要とするインターフェース

| 後続機能 | F06に必要なもの | 用途 |
|---------|---------------|------|
| F07 カバレッジ計算 | `check_visibility_multi_camera(cameras, points, bed_aabb)` | 6台全カメラの視認性行列を取得し、各点の視認カメラ数を算出 |

F07での使用イメージ:
```python
visibility_matrix = check_visibility_multi_camera(cameras, grid_points, room.bed)
visible_count = visibility_matrix.sum(axis=0)       # (N,) int
coverage_3plus = (visible_count >= 3).mean()         # 3台以上カバレッジ率
```

## 制約・品質基準

### 正確性

- 視錐台内かつオクルージョンなしの点がTrue、それ以外がFalseであること
- F04単体の結果・F05単体の結果と矛盾しないこと
- 結果が物理的に妥当であること（床面が見え、ベッド裏は見えない等）

### 性能

- N=10,000点、M=6台のカメラで実用的な速度で動作すること
- F04/F05がベクトル化されているため、F06のオーバーヘッドはPythonのforループ（最大6回）のみ

### エッジケース

| ケース | 期待動作 |
|---|---|
| cameras が空リスト | shape (0, N) の結果を返す（正常動作） |
| points が空配列 shape (0, 3) | shape (M, 0) の結果を返す（正常動作） |
| 単一点入力 shape (3,) | shape (1,) または shape (M, 1) の結果を返す |

### スコープ外

- セルフオクルージョン（被験者自身の体節による遮蔽）は扱わない（CLAUDE.mdに「初期段階では簡略化してよい」と記載）
- ベッド以外の家具・機器によるオクルージョンは扱わない
- near/far/eps のバリデーションはF04/F05に委譲する
