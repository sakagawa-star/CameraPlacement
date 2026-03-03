# F05: ベッドオクルージョン判定 — 要求仕様書

## 目的

カメラ位置から対象点（キーポイント候補）への視線（レイ）がベッドのAABBと交差するかを判定し、ベッドによるオクルージョン（遮蔽）の有無を返す。この機能はF06（視認性統合）から呼び出され、視錐台判定（F04）と組み合わせて最終的な視認可能性を決定する基盤となる。

## 入力パラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| camera_position | np.ndarray, shape (3,) | カメラの位置座標 [m]。Camera.position から取得 |
| points | np.ndarray, shape (N, 3) または (3,) | 対象点群のワールド座標 [m] |
| bed_aabb | AABB | ベッドの軸平行境界ボックス。Room.bed から取得 |
| eps | float | 端点除外の許容誤差。デフォルト 1e-6 |

## 出力（提供する機能）

### 1. `check_bed_occlusion(camera_position, points, bed_aabb, eps) -> np.ndarray`

- 入力: カメラ位置、対象点群、ベッドAABB
- 出力: shape (N,) のbool配列。True = オクルージョンあり（視認不可）、False = オクルージョンなし
- slab法（Kay-Kajiya法）によるレイ-AABB交差判定
- t ∈ (eps, 1-eps) の範囲でAABBと交差する場合にオクルージョンありと判定

### 2. `check_bed_occlusion_multi_camera(cameras, points, bed_aabb, eps) -> np.ndarray`

- 入力: カメラリスト（M台）、対象点群（N点）、ベッドAABB
- 出力: shape (M, N) のbool配列。occluded[i, j] = True ならカメラiから点jはオクルージョンあり
- 内部で各カメラについて `check_bed_occlusion` を呼ぶ

## 後続機能が必要とするインターフェース

| 後続機能 | F05に必要なもの | 用途 |
|---------|---------------|------|
| F06 視認性統合 | `check_bed_occlusion(camera_position, points, bed_aabb)` | オクルージョン判定。F04の視野内判定と AND 結合 |
| F06 視認性統合 | `check_bed_occlusion_multi_camera(cameras, points, bed_aabb)` | 複数カメラ一括判定 |

F06での使用イメージ:
```python
in_frustum = frustum_checker.is_visible(points)      # F04: (N,) bool
occluded = check_bed_occlusion(cam.position, points, room.bed)  # F05: (N,) bool
visible = in_frustum & ~occluded                      # 最終判定
```

## 制約・品質基準

### 正確性

- slab法によるレイ-AABB交差判定が幾何学的に正しいこと
- 端点（t=0: カメラ位置、t=1: 対象点）を除外して判定すること
- 対象点がベッドAABB境界上（例: Z=0.2）にある場合でも、正しくオクルージョンなしと判定すること
- レイの方向ベクトルの各成分がゼロ（軸平行レイ）の場合も正しく処理すること

### 性能

- N=10,000点程度をバッチ処理できること（NumPyベクトル演算）
- forループではなくベクトル化した実装とすること

### エッジケース

| ケース | 期待動作 |
|---|---|
| レイが完全にAABBを外れる | オクルージョンなし |
| レイがAABBを貫通する（t ∈ (eps, 1-eps) に交差区間がある） | オクルージョンあり |
| 対象点がAABB境界上にある（例: Z=0.2） | オクルージョンなし（t=1-eps以降の交差として除外） |
| カメラがAABB内部にある（通常あり得ない） | t_enter < 0 → 0からの交差として扱う |
| レイが軸に平行（direction成分=0） | 該当軸のスラブ判定をバイパス（常に交差区間 [-inf, +inf] として扱う） |
| カメラ位置と対象点が同一 | direction=0ベクトル → オクルージョンなし |
| 対象点がベッドAABB内部にある | 交差のt値が (eps, 1-eps) 内にあればオクルージョンあり |

### 数値安定性

- ゼロ除算を回避する（方向ベクトルの成分が0の場合の処理）
- eps パラメータで端点付近の誤判定を防ぐ

### スコープ外

- セルフオクルージョン（被験者自身の体節による遮蔽）は扱わない（CLAUDE.mdに「初期段階では簡略化してよい」と記載）
- ベッド以外の家具・機器によるオクルージョンは扱わない
