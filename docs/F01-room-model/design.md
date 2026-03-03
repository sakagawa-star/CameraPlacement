# F01: 空間モデル（部屋・ベッド） — 機能設計書

## ファイル構成

```
src/camera_placement/
  __init__.py                  # パッケージ初期化
  models/
    __init__.py                # modelsサブパッケージ初期化
    environment.py             # F01: AABB, Room, create_default_room()
tests/
  test_environment.py          # F01テスト
```

## データ構造

### `AABB` (Axis-Aligned Bounding Box)

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class AABB:
    """軸平行境界ボックス。

    Attributes:
        min_point: 最小座標 [x_min, y_min, z_min]。shape (3,)。
        max_point: 最大座標 [x_max, y_max, z_max]。shape (3,)。
    """
    min_point: np.ndarray  # shape (3,)
    max_point: np.ndarray  # shape (3,)

    def __post_init__(self) -> None:
        """np.float64に変換。"""

    def contains(self, points: np.ndarray) -> np.ndarray:
        """点がAABB内にあるか判定。

        Args:
            points: shape (N,3) または (3,)。

        Returns:
            shape (N,) の bool配列。
        """
```

### `Room`

```python
@dataclass
class Room:
    """病室の3D空間モデル。

    Attributes:
        width: 部屋の幅 X方向 [m]。
        depth: 部屋の奥行 Y方向 [m]。
        height: 部屋の高さ Z方向 [m]。
        bed: ベッドのAABB。
        camera_zone: カメラ設置可能領域のAABB。
    """
    width: float = 2.8
    depth: float = 3.5
    height: float = 2.5
    bed: AABB = field(default_factory=...)     # デフォルト: CLAUDE.md準拠
    camera_zone: AABB = field(default_factory=...)

    @property
    def room_aabb(self) -> AABB:
        """部屋全体のAABBを返す。"""

    def is_inside_room(self, points: np.ndarray) -> np.ndarray:
        """点が部屋内にあるか。"""

    def is_on_bed(self, points: np.ndarray) -> np.ndarray:
        """点がベッド領域内にあるか。"""

    def is_valid_camera_position(self, points: np.ndarray) -> np.ndarray:
        """点がカメラ設置可能領域内か。"""
```

### ファクトリ関数

```python
def create_default_room() -> Room:
    """CLAUDE.mdの仕様に基づくデフォルト病室を生成する。"""
    return Room()  # 全てデフォルト値
```

## アルゴリズム

### AABB.contains（点の包含判定）

```
全ての軸について: min[i] <= point[i] <= max[i]
```

numpyブロードキャストで (N,3) を一括判定し、axis=1 で AND を取る。

## 後続機能との接続点

- **F03（活動ボリューム）**: `Room.bed` のAABBを参照してベッド領域を把握
- **F05（オクルージョン）**: `AABB` クラスに `intersects_ray()` メソッドを追加する（F05で拡張）
- **F11（可視化）**: `Room` の各AABBの座標を使って3D描画
- **F12（配置パターン）**: `Room.camera_zone` を参照してカメラ配置位置を決定

## テスト計画

| # | テストケース | 入力 | 期待値 |
|---|-------------|------|--------|
| 1 | 部屋中央は内部 | (1.4, 1.75, 1.25) | True |
| 2 | 部屋外の点 | (3.0, 0, 0) | False |
| 3 | 境界上の点（原点）は内部 | (0, 0, 0) | True |
| 4 | 境界上の点（最大）は内部 | (2.8, 3.5, 2.5) | True |
| 5 | 負の座標は外部 | (-0.1, 1.0, 1.0) | False |
| 6 | ベッド中央はon_bed | (1.4, 2.5, 0.1) | True |
| 7 | ベッド外はnot on_bed | (0.5, 1.0, 0.1) | False |
| 8 | ベッド上面超過はnot on_bed | (1.4, 2.5, 0.5) | False |
| 9 | ベッド境界はon_bed | (0.9, 1.5, 0.0) | True |
| 10 | 設置領域内 | (1.4, 1.75, 2.0) | True |
| 11 | 設置領域外（壁際） | (0.1, 1.75, 2.0) | False |
| 12 | 設置領域境界（最小） | (0.2, 0.2, 0.2) | True |
| 13 | 設置領域境界（最大） | (2.6, 3.3, 2.3) | True |
| 14 | バッチ処理: is_inside_room | 複数点 (N,3) | 個別結果と一致 |
| 15 | バッチ処理: is_on_bed | 複数点 (N,3) | 個別結果と一致 |
| 16 | バッチ処理: is_valid_camera_position | 複数点 (N,3) | 個別結果と一致 |
| 17 | デフォルトRoom寸法の確認 | create_default_room() | width=2.8, depth=3.5, height=2.5 |
| 18 | デフォルトBedの確認 | create_default_room().bed | min=[0.9,1.5,0.0], max=[1.9,3.5,0.2] |
| 19 | デフォルトCameraZoneの確認 | create_default_room().camera_zone | min=[0.2,0.2,0.2], max=[2.6,3.3,2.3] |

## 依存ライブラリ

- numpy（バッチ演算用） — 追加済み
- dataclasses（標準ライブラリ）
- pytest（テスト用） — 追加済み

## 環境構築メモ

`uv init`, `uv add numpy`, `uv add --dev pytest` は実行済み。
`src/camera_placement/__init__.py` は再作成が必要。
`src/camera_placement/models/` ディレクトリと `__init__.py` の新規作成が必要。
