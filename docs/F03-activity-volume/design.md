# F03: 活動ボリューム・グリッド生成 — 機能設計書

## ファイル構成

```
src/camera_placement/
  models/
    __init__.py       # ActivityType, ActivityVolume, create_activity_volumes, create_merged_grid を追加export
    environment.py    # F01: 既存（変更なし）
    activity.py       # F03: 新規作成
tests/
  test_activity.py    # F03テスト: 新規作成
```

## データ構造

### `ActivityType` (Enum)

```python
from enum import Enum

class ActivityType(Enum):
    """動作パターンの種別。"""
    WALKING = "walking"
    SEATED = "seated"
    SUPINE = "supine"
```

### `ActivityVolume` (dataclass)

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class ActivityVolume:
    """1つの動作パターンの活動ボリューム。

    Attributes:
        activity_type: 動作パターンの種別。
        grid_points: 活動領域内のグリッド点群。shape (N, 3)。dtype=np.float64。
    """
    activity_type: ActivityType
    grid_points: np.ndarray  # shape (N, 3)

    def __post_init__(self) -> None:
        """配列の型とshapeを検証する。"""
        # np.float64に変換
        # ndim == 2 かつ shape[1] == 3 を検証

    @property
    def num_points(self) -> int:
        """グリッド点数を返す。"""
        return self.grid_points.shape[0]
```

### ファクトリ関数

```python
def create_activity_volumes(
    room: Room | None = None,
    grid_spacing: float = 0.2,
) -> list[ActivityVolume]:
    """3つの動作パターンの活動ボリュームを生成する。

    Args:
        room: Roomインスタンス。Noneの場合はデフォルト病室。
        grid_spacing: グリッド間隔 [m]。正の値であること。

    Returns:
        [walking, seated, supine] の順の ActivityVolume リスト。

    Raises:
        ValueError: grid_spacingが0以下の場合。
    """
```

### 統合グリッド関数

```python
def create_merged_grid(
    volumes: list[ActivityVolume],
    decimals: int = 6,
) -> np.ndarray:
    """複数のActivityVolumeのグリッド点を統合し重複を除去する。

    Args:
        volumes: ActivityVolumeのリスト。
        decimals: 重複判定用の丸め桁数。浮動小数点誤差対策。

    Returns:
        shape (M, 3) の統合グリッド点群。重複除去済み。
    """
```

## モジュール定数

CLAUDE.mdの活動ボリューム定義に基づく値。

```python
_WALKING_Z_MAX = 1.8
_SEATED_Z_MIN = 0.2
_SEATED_Z_MAX = 1.1
_SUPINE_Z_MIN = 0.2
_SUPINE_Z_MAX = 0.5
```

## アルゴリズム

### グリッド座標配列の生成（共通処理）

`_grid_1d` ヘルパー関数で1次元グリッドを生成する。

```python
def _grid_1d(start: float, stop: float, spacing: float) -> np.ndarray:
    vals = np.arange(start, stop + spacing / 2, spacing)
    return vals[vals <= stop + 1e-10]
```

- `+ spacing / 2` は浮動小数点誤差で最後の点が欠落するのを防ぐためのガード。
- `vals <= stop + 1e-10` のクリップは、浮動小数点誤差で `stop` を超える値が生成されるオーバーシュートを防止する。例: `np.arange(0.2, 1.2, 0.2)` が `1.2` を含んでしまう問題を回避。

### 歩行領域のグリッド生成

**方法A（部屋全体のグリッドを生成してからベッド上の点を除外）を採用する。**

方法Aの利点:
- 実装がシンプル（AABBを複数に分割する方法Bは分割ロジックが複雑）
- 点数が少ない（0.2m間隔で部屋XYは約270点、うちベッド約50点を除くだけ）ので性能問題なし
- F01の AABB 情報をそのまま活用できる

```python
def _generate_walking_grid(room: Room, spacing: float) -> np.ndarray:
    """歩行領域のグリッド点を生成する。

    部屋のXY全体からベッドXY投影内の点を除外し、
    Z方向 0 ~ 1.8m の範囲でグリッドを生成する。

    手順:
    1. X軸: _grid_1d(0.0, room.width, spacing)
    2. Y軸: _grid_1d(0.0, room.depth, spacing)
    3. Z軸: _grid_1d(0.0, _WALKING_Z_MAX, spacing)
    4. XYの meshgrid を作成
    5. ベッドXY投影内（bed.min_point[:2] <= pt <= bed.max_point[:2]）の点を除外
    6. 残ったXY点とZ軸の全組み合わせで3Dグリッドを構成
    """
```

ベッドXY除外の判定:
```python
bed_min_xy = room.bed.min_point[:2]  # [0.9, 1.5]
bed_max_xy = room.bed.max_point[:2]  # [1.9, 3.5]
in_bed = np.all((xy_points >= bed_min_xy) & (xy_points <= bed_max_xy), axis=1)
xy_outside_bed = xy_points[~in_bed]
```

XY→3D展開:
```python
n_xy = xy_outside_bed.shape[0]
n_z = len(zs)
grid = np.empty((n_xy * n_z, 3), dtype=np.float64)
grid[:, 0] = np.repeat(xy_outside_bed[:, 0], n_z)
grid[:, 1] = np.repeat(xy_outside_bed[:, 1], n_z)
grid[:, 2] = np.tile(zs, n_xy)
```

### ベッド上（座位・臥位）のグリッド生成

ベッドXY投影範囲内のみで、指定Z範囲のグリッドを生成する。

```python
def _generate_bed_grid(room: Room, spacing: float,
                       z_min: float, z_max: float) -> np.ndarray:
    """ベッド上のグリッド点を生成する。

    手順:
    1. X軸: _grid_1d(bed.min_point[0], bed.max_point[0], spacing)
    2. Y軸: _grid_1d(bed.min_point[1], bed.max_point[1], spacing)
    3. Z軸: _grid_1d(z_min, z_max, spacing)
    4. np.meshgrid で3Dグリッドを構成
    5. reshape して (N, 3) で返す
    """
```

### 統合グリッドの重複除去

座位 Z[0.2〜1.1] と臥位 Z[0.2〜0.5] はXY範囲が同一でZ範囲が重複する。

```python
all_points = np.vstack([v.grid_points for v in volumes])
rounded = np.round(all_points, decimals=decimals)  # 浮動小数点誤差対策
unique = np.unique(rounded, axis=0)
```

## F01との連携方法

- `Room` オブジェクトを引数として受け取り、以下のプロパティを参照する:
  - `room.width`, `room.depth` — 部屋のXY寸法（歩行領域のXY範囲）
  - `room.bed.min_point`, `room.bed.max_point` — ベッドの位置（歩行領域のベッド除外 + 座位/臥位のXY範囲）
- `Room` クラス自体は変更しない

## `models/__init__.py` の更新

```python
"""空間モデル定義サブパッケージ。"""

from camera_placement.models.environment import AABB, Room, create_default_room
from camera_placement.models.activity import (
    ActivityType,
    ActivityVolume,
    create_activity_volumes,
    create_merged_grid,
)

__all__ = [
    "AABB", "Room", "create_default_room",
    "ActivityType", "ActivityVolume", "create_activity_volumes", "create_merged_grid",
]
```

## 設計判断のまとめ

| 判断項目 | 決定 | 理由 |
|---|---|---|
| グリッド間隔デフォルト | 0.2m | 統合約2,500点。臥位でも2層取れる。精度と計算コストのバランスが良い |
| ベッド除外方法 | 方法A（全体生成後に除外） | シンプル。F01の AABB をそのまま利用。性能問題なし |
| 統合グリッドの重複除去 | np.round + np.unique | 座位/臥位のZ重複を除去。浮動小数点誤差は round で対処 |
| 歩行Z下限 | 0.0m（床面） | 足のキーポイントは床面高さにある |
| 歩行のベッド除外基準 | ベッドのXY投影(2D) | 歩行者はベッドの真上を通過しないため、Z座標に関わらず除外 |
| ActivityType | Enum | 文字列よりも型安全。後続機能でパターン分岐時にも便利 |
| Z範囲の定数 | モジュール定数 | CLAUDE.mdの仕様値。名前付き定数にして可読性と保守性を確保 |

## 後続機能との接続点

| 後続機能 | 使用する機能 | 用途 |
|---------|------------|------|
| F06/F07（視認性・カバレッジ） | `ActivityVolume.grid_points` (N,3) | カバレッジ評価の対象点群としてバッチ入力 |
| F10（統合品質スコア） | `create_merged_grid()` または各 ActivityVolume | 全体/動作パターン別の品質評価 |
| F11（3D可視化） | `ActivityVolume.grid_points` + `activity_type` | 動作パターン別に色分け表示 |
| F13（配置比較） | 各 ActivityVolume | 動作パターン別にカバレッジを算出し比較 |

## テスト計画

テストファイル: `tests/test_activity.py`

| # | カテゴリ | テストケース | 入力 | 期待値 |
|---|---------|-------------|------|--------|
| 1 | ActivityVolume基本 | grid_pointsのshape検証 | 正常な(N,3)配列 | エラーなし、num_points == N |
| 2 | ActivityVolume基本 | 不正なshapeでValueError | shape (N,2) の配列 | ValueError |
| 3 | ActivityVolume基本 | 空の点群(0,3) | shape (0,3) | num_points == 0 |
| 4 | 歩行グリッド | 点群が生成される | デフォルト room, spacing=0.2 | num_points > 0 |
| 5 | 歩行グリッド | 全点がベッドXY投影外 | デフォルト room | ベッド範囲内の点がゼロ |
| 6 | 歩行グリッド | Z範囲が 0〜1.8 | デフォルト room | z_min >= 0.0, z_max <= 1.8 |
| 7 | 歩行グリッド | XY範囲が部屋内 | デフォルト room | 0 <= x <= 2.8, 0 <= y <= 3.5 |
| 8 | 歩行グリッド | 既知の点数と一致 | spacing=0.2 | 試算値と一致 |
| 9 | 座位グリッド | 点群が生成される | デフォルト room, spacing=0.2 | num_points > 0 |
| 10 | 座位グリッド | 全点がベッドXY投影内 | デフォルト room | 0.9 <= x <= 1.9, 1.5 <= y <= 3.5 |
| 11 | 座位グリッド | Z範囲が 0.2〜1.1 | デフォルト room | z_min >= 0.2, z_max <= 1.1 |
| 12 | 座位グリッド | 既知の点数と一致 | spacing=0.2 | 試算値と一致 |
| 13 | 臥位グリッド | 点群が生成される | デフォルト room, spacing=0.2 | num_points > 0 |
| 14 | 臥位グリッド | 全点がベッドXY投影内 | デフォルト room | 0.9 <= x <= 1.9, 1.5 <= y <= 3.5 |
| 15 | 臥位グリッド | Z範囲が 0.2〜0.5 | デフォルト room | z_min >= 0.2, z_max <= 0.5 |
| 16 | 臥位グリッド | 既知の点数と一致 | spacing=0.2 | 試算値と一致 |
| 17 | ファクトリ | 3つの ActivityVolume が返る | デフォルト引数 | len == 3, 順序 [WALKING, SEATED, SUPINE] |
| 18 | ファクトリ | room=None でデフォルト room 使用 | room=None | エラーなし |
| 19 | ファクトリ | grid_spacing=0 で ValueError | grid_spacing=0 | ValueError |
| 20 | ファクトリ | grid_spacing=負 で ValueError | grid_spacing=-0.1 | ValueError |
| 21 | 統合グリッド | 重複除去が行われる | walking + seated + supine | 統合点数 < 個別合算 |
| 22 | 統合グリッド | 具体的な統合点数 | spacing=0.2 | 試算値と一致 |
| 23 | 統合グリッド | 空リストで(0,3)配列 | [] | shape == (0, 3) |
| 24 | グリッド間隔 | spacing=0.1 で点数増加 | spacing=0.1 | 各パターン点数 > spacing=0.2 |
| 25 | グリッド間隔 | spacing=0.3 で点数減少 | spacing=0.3 | 各パターン点数 < spacing=0.2 |
| 26 | カスタムRoom | ベッド位置変更時の除外 | bed X:0.5~1.5 | 歩行グリッドにその範囲の点なし |
| 27 | dtype確認 | 全グリッドが float64 | デフォルト | dtype == np.float64 |

## 依存ライブラリ

- numpy（グリッド生成、配列操作） — 追加済み
- dataclasses, enum（標準ライブラリ）
- pytest（テスト用） — 追加済み
- F01: `Room`, `AABB`, `create_default_room`（`camera_placement.models.environment` からインポート）
