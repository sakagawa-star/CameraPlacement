# 機能設計書: F07 カバレッジ計算

## 1. ファイル構成

```
src/camera_placement/
  evaluation/
    __init__.py       # 新規作成: CoverageResult, CoverageStats, VolumeCoverage,
                      #           calculate_coverage, calculate_coverage_stats,
                      #           calculate_volume_coverage を export
    coverage.py       # 新規作成: F07 メインモジュール
tests/
  test_coverage.py    # 新規作成: F07テスト
tests/results/
  F07_test_result.txt # テスト結果
```

`src/camera_placement/evaluation/` ディレクトリは新規作成。

## 2. データ構造

### 2.1 CoverageStats dataclass

```python
@dataclass
class CoverageStats:
    """カバレッジ統計情報。

    visible_counts を唯一の一次データとし、他の統計量は全て property で導出する。

    Attributes:
        visible_counts: 各点の視認カメラ数。shape (N,), dtype=int。
        num_cameras: カメラ総数 M。
        num_points: グリッド点数 N。
    """

    visible_counts: np.ndarray  # shape (N,), dtype=int
    num_cameras: int
    num_points: int

    @property
    def coverage_at_least(self) -> dict[int, float]:
        """k台以上カバー率の辞書。key: k=1,2,...,num_cameras, value: 0.0〜1.0。"""
        if self.num_points == 0:
            return {k: 0.0 for k in range(1, self.num_cameras + 1)}
        return {
            k: float((self.visible_counts >= k).mean())
            for k in range(1, self.num_cameras + 1)
        }

    @property
    def coverage_3plus(self) -> float:
        """3台以上カバー率（最重要指標）。"""
        if self.num_points == 0:
            return 0.0
        return float((self.visible_counts >= 3).mean())

    @property
    def min_visible(self) -> int:
        """最小視認カメラ数。"""
        if self.num_points == 0:
            return 0
        return int(self.visible_counts.min())

    @property
    def max_visible(self) -> int:
        """最大視認カメラ数。"""
        if self.num_points == 0:
            return 0
        return int(self.visible_counts.max())

    @property
    def mean_visible(self) -> float:
        """平均視認カメラ数。"""
        if self.num_points == 0:
            return 0.0
        return float(self.visible_counts.mean())
```

### 2.2 VolumeCoverage dataclass

```python
@dataclass
class VolumeCoverage:
    """単一活動ボリュームのカバレッジ結果。

    Attributes:
        activity_type: 動作パターンの種別。
        visibility_matrix: 視認性行列。shape (M, N_vol), dtype=bool。
        stats: カバレッジ統計。
    """

    activity_type: ActivityType
    visibility_matrix: np.ndarray  # shape (M, N_vol), dtype=bool
    stats: CoverageStats
```

### 2.3 CoverageResult dataclass

```python
@dataclass
class CoverageResult:
    """カバレッジ計算の全体結果。

    Attributes:
        cameras: 使用したカメラリスト。
        merged_grid: 統合グリッド点群。shape (N, 3)。
        visibility_matrix: 統合グリッドの視認性行列。shape (M, N), dtype=bool。
        stats: 統合グリッドのカバレッジ統計。
        volume_coverages: 活動ボリューム別のカバレッジ結果。
    """

    cameras: list[Camera]
    merged_grid: np.ndarray  # shape (N, 3)
    visibility_matrix: np.ndarray  # shape (M, N), dtype=bool
    stats: CoverageStats
    volume_coverages: dict[ActivityType, VolumeCoverage]
```

### 2.4 関数設計

```python
def calculate_coverage_stats(visibility_matrix: np.ndarray) -> CoverageStats:
    """視認性行列からカバレッジ統計を計算する。

    Args:
        visibility_matrix: shape (M, N) の bool配列。
            M はカメラ数、N はグリッド点数。

    Returns:
        CoverageStats インスタンス。

    Raises:
        ValueError: visibility_matrix が2次元でない場合。
    """


def calculate_volume_coverage(
    cameras: list[Camera],
    volume: ActivityVolume,
    bed_aabb: AABB,
    near: float = 0.1,
    far: float = 10.0,
) -> VolumeCoverage:
    """単一の活動ボリュームに対するカバレッジを計算する。

    Args:
        cameras: カメラのリスト。
        volume: 活動ボリューム。
        bed_aabb: ベッドのAABB。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。

    Returns:
        VolumeCoverage インスタンス。
    """


def calculate_coverage(
    cameras: list[Camera],
    room: Room,
    volumes: list[ActivityVolume] | None = None,
    grid_spacing: float = 0.2,
    near: float = 0.1,
    far: float = 10.0,
) -> CoverageResult:
    """6台全カメラのカバレッジを計算する。

    活動ボリューム別の統計と、統合グリッドの全体統計の両方を返す。

    Args:
        cameras: カメラのリスト。
        room: 病室モデル。
        volumes: 活動ボリューム。Noneの場合は自動生成。
        grid_spacing: volumes=None の場合のグリッド間隔 [m]。
        near: ニアクリップ距離 [m]。
        far: ファークリップ距離 [m]。

    Returns:
        CoverageResult インスタンス。
    """
```

## 3. アルゴリズム

### 3.1 `calculate_coverage_stats` の処理フロー

```
入力: visibility_matrix (M, N) bool
  │
  ├── Step 1: 2D配列のバリデーション
  │
  ├── Step 2: visible_counts = visibility_matrix.sum(axis=0)  → (N,) int
  │
  ├── Step 3: num_cameras = M, num_points = N
  │
  └── Step 4: CoverageStats(visible_counts, num_cameras, num_points) を返す
```

擬似コード:

```python
def calculate_coverage_stats(visibility_matrix):
    vis = np.asarray(visibility_matrix, dtype=bool)
    if vis.ndim != 2:
        raise ValueError(f"visibility_matrix must be 2D, got {vis.ndim}D")
    visible_counts = vis.sum(axis=0).astype(int)
    return CoverageStats(
        visible_counts=visible_counts,
        num_cameras=vis.shape[0],
        num_points=vis.shape[1],
    )
```

### 3.2 `calculate_volume_coverage` の処理フロー

```
入力: cameras, volume, bed_aabb, near, far
  │
  ├── Step 1: vis_matrix = check_visibility_multi_camera(
  │               cameras, volume.grid_points, bed_aabb, near, far
  │           )  → (M, N_vol) bool
  │
  ├── Step 2: stats = calculate_coverage_stats(vis_matrix)
  │
  └── Step 3: VolumeCoverage(volume.activity_type, vis_matrix, stats) を返す
```

### 3.3 `calculate_coverage` の処理フロー

```
入力: cameras, room, volumes, grid_spacing, near, far
  │
  ├── Step 1: volumes が None なら create_activity_volumes(room, grid_spacing)
  │
  ├── Step 2: 各活動ボリュームについて calculate_volume_coverage を呼び出し
  │           volume_coverages = {vol.activity_type: vc for vol in volumes}
  │
  ├── Step 3: merged_grid = create_merged_grid(volumes)
  │
  ├── Step 4: 空グリッドの場合 → shape (len(cameras), 0) の空行列
  │           それ以外 → check_visibility_multi_camera(cameras, merged_grid, room.bed, near, far)
  │
  ├── Step 5: merged_stats = calculate_coverage_stats(merged_vis_matrix)
  │
  └── Step 6: CoverageResult を返す
```

擬似コード:

```python
def calculate_coverage(cameras, room, volumes=None, grid_spacing=0.2, near=0.1, far=10.0):
    if volumes is None:
        volumes = create_activity_volumes(room, grid_spacing)

    # 活動ボリューム別カバレッジ
    volume_coverages = {}
    for vol in volumes:
        vc = calculate_volume_coverage(cameras, vol, room.bed, near, far)
        volume_coverages[vol.activity_type] = vc

    # 統合グリッドカバレッジ
    merged_grid = create_merged_grid(volumes)
    if merged_grid.shape[0] == 0:
        merged_vis_matrix = np.zeros((len(cameras), 0), dtype=bool)
    else:
        merged_vis_matrix = check_visibility_multi_camera(
            cameras, merged_grid, room.bed, near, far
        )
    merged_stats = calculate_coverage_stats(merged_vis_matrix)

    return CoverageResult(
        cameras=cameras,
        merged_grid=merged_grid,
        visibility_matrix=merged_vis_matrix,
        stats=merged_stats,
        volume_coverages=volume_coverages,
    )
```

### 3.4 データフロー図

```
cameras (list[Camera])     room (Room)     volumes (optional)
    │                        │                 │
    │                        ├── room.bed ──┐  │
    │                        │              │  │
    │                        ▼              │  ▼
    │          create_activity_volumes(room) │  (or use provided)
    │                        │              │
    │                        ▼              │
    │               volumes (3 ActivityVolumes)
    │                  │    │    │          │
    │     ┌────────────┘    │    └────────┐ │
    │     ▼                 ▼             ▼ │
    │  walking          seated        supine │
    │     │                 │             │  │
    ├─────┼─────────────────┼─────────────┤  │
    │     ▼                 ▼             ▼  │
    │  calculate_volume_coverage (×3)     ◄──┘
    │     │                 │             │
    │     ▼                 ▼             ▼
    │  VolumeCoverage   VolumeCoverage  VolumeCoverage
    │     │                 │             │
    │     └────────┬────────┴─────────────┘
    │              │
    │              ▼
    │     create_merged_grid(volumes)
    │              │
    │              ▼
    │        merged_grid (N, 3)
    │              │
    ├──────────────┤
    ▼              ▼
 check_visibility_multi_camera(cameras, merged_grid, room.bed)
                   │
                   ▼
          merged_vis_matrix (M, N) bool
                   │
                   ▼
          calculate_coverage_stats(merged_vis_matrix)
                   │
                   ▼
          CoverageResult
```

## 4. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| cameras が不正なCameraオブジェクト | Camera.__post_init__ で ValueError | F02 |
| grid_spacing <= 0 | create_activity_volumes で ValueError | F03 |
| visibility_matrix が2Dでない | calculate_coverage_stats で ValueError を送出 | F07 |
| cameras が空リスト | `check_visibility_multi_camera` が shape (0, N) を返し、`sum(axis=0)` で全ゼロの visible_counts になる。正常動作 | F07 |
| volumes が空リスト | merged_grid shape (0, 3) → stats はゼロ値。正常動作 | F07 |

## 5. 設計判断

### 5.1 統計量を property で提供する理由

- `visible_counts` が唯一の一次データ。`coverage_at_least`, `coverage_3plus`, `min_visible`, `max_visible`, `mean_visible` は全て `visible_counts` から導出可能
- 冗長なフィールドを持たないことで、データの一貫性が常に保証される
- 計算コストは O(N) で、N=10,000 なら十分軽量

### 5.2 calculate_coverage_stats を独立関数として公開する理由

- F08/F09/F10 が部分的なグリッドに対してカバレッジ統計を計算する可能性がある
- テストで直接 visibility_matrix を渡して統計を検証できる
- 単一責任原則: 統計計算は入力データの取得（F06呼び出し）と分離すべき

### 5.3 活動ボリューム別と統合グリッドの両方を計算する理由

- 全体のカバレッジ率だけでは、臥位（ベッド上の低い点）のカバレッジが悪いことを見逃す可能性がある
- 動作パターンごとのカバレッジを把握することで、配置改善の方向性が明確になる
- F13（配置比較レポート）では活動ボリューム別の比較表を出すことが計画されている

### 5.4 統合グリッドの visibility_matrix を個別ボリュームとは別に計算する理由

- `create_merged_grid` は重複排除するため、個別ボリュームの結合とは異なるインデックスになる
- 後続の F08/F09 は統合グリッドの visibility_matrix を必要とする
- 計算量は `check_visibility_multi_camera` の呼び出しが4回（3ボリューム+統合）になるが、M=6, N=数千の規模では許容範囲

### 5.5 F06の `eps` パラメータを露出しない理由

- `check_visibility_multi_camera` は `eps`（オクルージョン判定の端点除外許容誤差、デフォルト `1e-6`）パラメータを持つ
- F07の公開関数（`calculate_coverage`, `calculate_volume_coverage`）には `eps` を含めず、F06のデフォルト値をそのまま使用する
- 理由: `eps` はオクルージョン判定の内部パラメータであり、カバレッジ計算の利用者が調整する必要がない。F06の責務範囲に属する設定値である

### 5.6 モジュール関数方式を採用する理由

- F06と同じパターン。状態を持つ必要がない
- 呼び出し側が `calculate_coverage(cameras, room)` のワンコールで結果を取得できるシンプルさ

## 6. 依存機能との連携方法

### 6.1 F06（視認性統合）

- `check_visibility_multi_camera(cameras, grid_points, bed_aabb, near, far)` を呼び出し
- 戻り値 (M, N) bool の visibility_matrix を受け取る
- インポート: `from camera_placement.core.visibility import check_visibility_multi_camera`

### 6.2 F03（活動ボリューム）

- `create_activity_volumes(room, grid_spacing)` で活動ボリュームを生成
- `create_merged_grid(volumes)` で統合グリッドを生成
- `ActivityVolume.grid_points`, `ActivityVolume.activity_type` を参照
- インポート: `from camera_placement.models.activity import ActivityType, ActivityVolume, create_activity_volumes, create_merged_grid`

### 6.3 F01（空間モデル）

- `Room.bed` で AABB を取得し、オクルージョン判定に渡す
- インポート: `from camera_placement.models.environment import AABB, Room`

### 6.4 F02（カメラモデル）

- `Camera` を型ヒントに使用
- インポート: `from camera_placement.models.camera import Camera`

## 7. 後続機能との接続点

| 後続機能 | 使用するフィールド | 用途 |
|---------|------------------|------|
| F08 角度スコア | `CoverageResult.visibility_matrix`, `.cameras`, `.merged_grid` | 視認可能なカメラペアの角度分離をグリッド点ごとに計算 |
| F09 投影スコア | `CoverageResult.visibility_matrix`, `.cameras`, `.merged_grid` | 各点の画像上投影サイズを推定 |
| F10 統合スコア | `CoverageResult.stats.coverage_3plus`, 他の統計量 | カバレッジスコアとして統合品質スコアに組み込み |
| F11 可視化 | `CoverageResult.merged_grid`, `.stats.visible_counts` | 各点を視認カメラ数で色分けした3Dカバレッジマップ |
| F13 配置比較 | `CoverageResult.volume_coverages` | 活動ボリューム別の比較表 |

## 8. テスト計画

テストファイル: `tests/test_coverage.py`

### カテゴリA: CoverageStats の統計計算（calculate_coverage_stats）

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 基本統計（全カメラから視認可能） | (3, 4) の全True行列 | visible_counts=[3,3,3,3], coverage_3plus=1.0 | 基本動作 |
| A2 | 部分視認 | (3, 4) の混合行列（手動設定） | 各統計値が手動計算と一致 | 統計の正確性 |
| A3 | 全点視認不可 | (3, 4) の全False行列 | visible_counts=[0,0,0,0], coverage_3plus=0.0 | ゼロカバレッジ |
| A4 | coverage_at_least の各閾値 | (4, 5) の段階的行列 | 各k値のカバー率が正しい | 閾値ごとの計算精度 |
| A5 | min/max/mean_visible | 既知の行列 | 手動計算値と一致 | 個別property検証 |
| A6 | 空の行列 shape (3, 0) | カメラ3台、点0 | coverage_3plus=0.0, min_visible=0 | エッジケース |
| A7 | 単一点 shape (3, 1) | カメラ3台、点1 | 正常計算 | 最小サイズ |
| A8 | 2Dでない入力 | 1D配列 | ValueError | 入力バリデーション |

### カテゴリB: calculate_volume_coverage

| # | テストケース | 詳細 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | 基本動作 | 2台カメラ、小規模ActivityVolume | VolumeCoverage が正しい activity_type, stats を持つ | 基本動作 |
| B2 | visibility_matrix のshape | M台カメラ、N点のボリューム | shape (M, N) | shape の正確性 |
| B3 | stats.num_points == volume.num_points | 任意設定 | 一致 | ポイント数の整合性 |

### カテゴリC: calculate_coverage（メイン関数）

| # | テストケース | 詳細 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | 基本動作（デフォルトvolumes） | 6台カメラ、room、volumes=None | CoverageResult の全フィールドが設定されている | メイン関数の動作 |
| C2 | 指定volumes使用 | 小規模カスタムvolumes | 指定volumesに基づく結果 | volumes引数の反映 |
| C3 | volume_coverages の辞書キー | デフォルト3ボリューム | WALKING, SEATED, SUPINE の3キー | 活動ボリューム別 |
| C4 | cameras リストの保持 | 任意カメラ | result.cameras が入力と同じ | フィールド保持 |
| C5 | merged_grid の保持 | 任意設定 | result.merged_grid.shape[1] == 3 | フィールド保持 |
| C6 | visibility_matrix のshape整合性 | M台カメラ | shape (M, merged_grid.shape[0]) | shape整合性 |
| C7 | near/far パラメータの伝播 | far=1.0 で遠方の点が視認不可になることを確認 | 遠方点のカバレッジ低下 | パラメータ伝播 |

### カテゴリD: エッジケース

| # | テストケース | 詳細 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | カメラ0台 | cameras=[] | stats.coverage_3plus=0.0, visible_counts=全0 | 空カメラ |
| D2 | 全カメラから全点視認可能 | 近距離6台、小グリッド | coverage_3plus=1.0 | 最大カバレッジ |
| D3 | grid_spacing の変更 | grid_spacing=0.5 | ポイント数が減少 | グリッド間隔 |
| D4 | volumes が空リスト | cameras=6台、volumes=[] | merged_grid shape (0, 3)、stats はゼロ値、volume_coverages は空辞書 | 空ボリューム |

### カテゴリE: 実環境シナリオ

| # | テストケース | 詳細 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | コーナー配置6台 | 病室4コーナー上部+中間2台 | coverage_3plus > 0 | 実用的配置での動作 |
| E2 | 活動ボリューム別の差異 | E1の配置で歩行/座位/臥位のカバレッジ比較 | `volume_coverages[SUPINE].stats.coverage_3plus < volume_coverages[WALKING].stats.coverage_3plus`（ベッドオクルージョンにより臥位が低い） | 物理的妥当性 |
| E3 | stats の一貫性 | E1の結果で coverage_at_least[3] == coverage_3plus | 完全一致 | property間の一貫性 |

### テスト総数: 約 25 件

### テスト用ヘルパー

```python
def _create_corner_cameras() -> list[Camera]:
    """テスト用6台コーナー配置カメラ。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([2.6, 0.2, 2.3], center),
        create_camera([0.2, 3.3, 2.3], center),
        create_camera([2.6, 3.3, 2.3], center),
        create_camera([1.4, 0.2, 2.3], center),
        create_camera([1.4, 3.3, 2.3], center),
    ]

def _small_activity_volume(activity_type: ActivityType) -> ActivityVolume:
    """テスト用の小規模活動ボリューム（計算時間短縮）。"""
    grid = np.array([
        [0.5, 0.5, 0.5],
        [1.0, 1.0, 0.5],
        [1.5, 0.5, 1.0],
        [0.5, 1.0, 1.5],
    ])
    return ActivityVolume(activity_type, grid)
```

## 9. 依存ライブラリ

- **numpy**（ベクトル演算）— 追加済み
- **pytest**（テスト用）— 追加済み
- 新規ライブラリの追加は不要

## 10. `evaluation/__init__.py` の内容

```python
"""evaluation パッケージ: カバレッジ・品質評価機能。"""

from camera_placement.evaluation.coverage import (
    CoverageResult,
    CoverageStats,
    VolumeCoverage,
    calculate_coverage,
    calculate_coverage_stats,
    calculate_volume_coverage,
)

__all__ = [
    "CoverageResult",
    "CoverageStats",
    "VolumeCoverage",
    "calculate_coverage",
    "calculate_coverage_stats",
    "calculate_volume_coverage",
]
```
