# 機能設計書: F12 配置パターン定義

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 3. データ構造、4. プリセット定義（全5パターンの座標） |
| FR-02 | 5.1 `get_preset` |
| FR-03 | 5.2 `get_all_presets` |
| FR-04 | 5.3 `list_preset_names` |
| FR-05 | 5.4 `create_cameras` |

## 2. ファイル構成

```
src/camera_placement/
  placement/
    __init__.py             # 新規作成: 公開シンボルのエクスポート
    patterns.py             # 新規作成: F12 メインモジュール
tests/
  test_patterns.py          # 新規作成: F12テスト
tests/results/
  F12_test_result.txt       # テスト結果
```

## 3. データ構造

### 3.1 `CameraConfig`

```python
@dataclass(frozen=True)
class CameraConfig:
    """1台のカメラの位置と注視点の設定。

    Attributes:
        position: カメラ位置 (x, y, z) [m]。
        look_at: 注視点 (x, y, z) [m]。
    """

    position: tuple[float, float, float]
    look_at: tuple[float, float, float]
```

- `frozen=True` で不変オブジェクトとする
- `tuple[float, float, float]` を使用する（`np.ndarray` ではなく）。理由: プリセット定義がリテラルで記述しやすく、ハッシュ可能で `frozen=True` と整合する
- `Camera` 生成時に `create_camera()` で `np.ndarray` に変換される

### 3.2 `PlacementPreset`

```python
@dataclass(frozen=True)
class PlacementPreset:
    """カメラ配置プリセット。

    Attributes:
        name: プリセット名（英語スネークケース）。
        description: プリセットの説明（日本語）。
        camera_configs: 6台のカメラ設定。要素数は必ず6。
    """

    name: str
    description: str
    camera_configs: tuple[CameraConfig, ...]
```

- `frozen=True` で不変オブジェクトとする
- `camera_configs` は `tuple` を使用する（`list` ではなく）。理由: 不変性を保証するため
- `__post_init__` は定義しない。バリデーションは `create_cameras` 関数で行う

### 3.3 モジュールレベル定数

```python
# プリセット定義で使用する注視点の定数
_ROOM_CENTER_TARGET: tuple[float, float, float] = (1.4, 1.75, 0.9)
_BED_CENTER_TARGET: tuple[float, float, float] = (1.4, 2.5, 0.5)
```

- `_ROOM_CENTER_TARGET`: 部屋の活動空間中央。X=1.4（部屋幅の中央）、Y=1.75（部屋奥行の中央）、Z=0.9（歩行時の腰の高さ付近）
- `_BED_CENTER_TARGET`: ベッド上の活動中央。X=1.4（ベッド幅の中央）、Y=2.5（ベッド奥行の中央）、Z=0.5（ベッド面+座位の中間高さ）

## 4. プリセット定義

### 4.1 upper_corners（上部コーナー型）

**配置戦略**: カメラ設置可能領域の上部4隅 + 前後壁中央2箇所。コーナーからの対角視線により広い角度分離を確保する。

```
Y（奥行）
 3.3  C3──────────C6──────────C4
      |                        |
      |                        |
      |                        |
      |                        |
 0.2  C1──────────C5──────────C2
      0.2        1.4         2.6   X（幅）

全カメラ Z = 2.3m
全カメラ → (1.4, 1.75, 0.9)
```

| カメラ | 位置 (x, y, z) | 注視点 (x, y, z) | 配置意図 |
|--------|---------------|-----------------|---------|
| C1 | (0.2, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前左コーナー |
| C2 | (2.6, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前右コーナー |
| C3 | (0.2, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥左コーナー |
| C4 | (2.6, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥右コーナー |
| C5 | (1.4, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前壁中央 |
| C6 | (1.4, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥壁中央 |

**特徴**: コーナーの4台で対角方向に広い角度分離を確保。前後壁中央の2台で Y方向のカバレッジを補強。

### 4.2 wall_uniform（壁面均等型）

**配置戦略**: 左右壁面に各2台、前後壁面に各1台で周囲に均等分散。コーナーではなく壁面上に分散させることで、視線方向のバリエーションを増やす。

```
Y（奥行）
 3.3  ─────────────C6─────────────
      |                           |
 2.5  C2                         C4
      |                           |
 1.0  C1                         C3
      |                           |
 0.2  ─────────────C5─────────────
      0.2        1.4            2.6   X（幅）

全カメラ Z = 2.3m
全カメラ → (1.4, 1.75, 0.9)
```

| カメラ | 位置 (x, y, z) | 注視点 (x, y, z) | 配置意図 |
|--------|---------------|-----------------|---------|
| C1 | (0.2, 1.0, 2.3) | (1.4, 1.75, 0.9) | 左壁・手前寄り |
| C2 | (0.2, 2.5, 2.3) | (1.4, 1.75, 0.9) | 左壁・奥寄り |
| C3 | (2.6, 1.0, 2.3) | (1.4, 1.75, 0.9) | 右壁・手前寄り |
| C4 | (2.6, 2.5, 2.3) | (1.4, 1.75, 0.9) | 右壁・奥寄り |
| C5 | (1.4, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前壁中央 |
| C6 | (1.4, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥壁中央 |

**特徴**: コーナー型と比較して壁面上の位置が分散しており、室内の各エリアにより均等な視線方向が得られる。

### 4.3 overhead_grid（天井格子型）

**配置戦略**: 天井直下に2列×3行の格子状に配置。上からの俯瞰により、床面全体を均等にカバーする。

```
Y（奥行）
 2.9  C5─────────────────C6
      |                    |
 1.75 C3─────────────────C4
      |                    |
 0.6  C1─────────────────C2
      0.8                2.0   X（幅）

全カメラ Z = 2.3m
全カメラ → (1.4, 1.75, 0.9)
```

| カメラ | 位置 (x, y, z) | 注視点 (x, y, z) | 配置意図 |
|--------|---------------|-----------------|---------|
| C1 | (0.8, 0.6, 2.3) | (1.4, 1.75, 0.9) | 格子・手前左 |
| C2 | (2.0, 0.6, 2.3) | (1.4, 1.75, 0.9) | 格子・手前右 |
| C3 | (0.8, 1.75, 2.3) | (1.4, 1.75, 0.9) | 格子・中央左 |
| C4 | (2.0, 1.75, 2.3) | (1.4, 1.75, 0.9) | 格子・中央右 |
| C5 | (0.8, 2.9, 2.3) | (1.4, 1.75, 0.9) | 格子・奥左 |
| C6 | (2.0, 2.9, 2.3) | (1.4, 1.75, 0.9) | 格子・奥右 |

**特徴**: 全カメラが天井近くにあるため、水平方向のカメラ間角度分離が小さい。床面近くの点（歩行時の足元、臥位）は上方からの視線ばかりになり、三角測量角度が不利になりやすい。一方、床面全体を均等にカバーする利点がある。

**格子位置の選定根拠**: カメラ設置可能領域（X: 0.2〜2.6, Y: 0.2〜3.3）を均等に分割した。X 方向は 0.8, 2.0（間隔 1.2m、領域端からの余白 0.6m）、Y 方向は 0.6, 1.75, 2.9（間隔 1.15m、領域端からの余白 0.4m）とした。壁面境界ではなく内側に配置することで、カメラ直下の床面を効率的にカバーする。

### 4.4 bed_focused（ベッド集中型）

**配置戦略**: 6台全てがベッド中央を注視する。ベッド周囲に配置して座位・臥位のカバレッジと三角測量角度を最大化する。

```
Y（奥行）
 3.3  C5──────────────────C6
      |                    |
      |      ┌────────┐    |
 2.0  |  C3  │  BED   │  C4
      |      └────────┘    |
      |                    |
 0.2  C1──────────────────C2
      0.2                2.6   X（幅）

C1, C2: Z = 2.3m
C3, C4, C5, C6: Z = 2.0m
全カメラ → (1.4, 2.5, 0.5)
```

| カメラ | 位置 (x, y, z) | 注視点 (x, y, z) | 配置意図 |
|--------|---------------|-----------------|---------|
| C1 | (0.2, 0.2, 2.3) | (1.4, 2.5, 0.5) | 手前左・高位置（遠方からの三角測量） |
| C2 | (2.6, 0.2, 2.3) | (1.4, 2.5, 0.5) | 手前右・高位置（遠方からの三角測量） |
| C3 | (0.2, 1.75, 2.0) | (1.4, 2.5, 0.5) | ベッド左側面 |
| C4 | (2.6, 1.75, 2.0) | (1.4, 2.5, 0.5) | ベッド右側面 |
| C5 | (0.2, 3.3, 2.0) | (1.4, 2.5, 0.5) | 奥左・ベッド頭側 |
| C6 | (2.6, 3.3, 2.0) | (1.4, 2.5, 0.5) | 奥右・ベッド頭側 |

**特徴**: ベッド上の座位・臥位に対して多角的な視線を確保。手前2台は高位置で歩行エリアもある程度カバーするが、歩行エリア専用のカメラがないため歩行時のカバレッジは他のパターンより劣る。

### 4.5 hybrid（ハイブリッド型）

**配置戦略**: 上部4隅で広範囲をカバーしつつ、壁面中段の2台でベッド方向からの角度を補う。高さ方向に2段階の配置により、異なる俯角の視線を確保する。

```
Y（奥行）
 3.3  C3──────────────────C4     Z = 2.3m
      |                    |
      |                    |
 1.75 |  C5           C6  |     Z = 1.8m
      |                    |
 0.2  C1──────────────────C2     Z = 2.3m
      0.2                2.6   X（幅）

C1-C4: 上部コーナー → (1.4, 1.75, 0.9)
C5-C6: 壁面中段   → (1.4, 2.5, 0.5)
```

| カメラ | 位置 (x, y, z) | 注視点 (x, y, z) | 配置意図 |
|--------|---------------|-----------------|---------|
| C1 | (0.2, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前左コーナー・広範囲カバレッジ |
| C2 | (2.6, 0.2, 2.3) | (1.4, 1.75, 0.9) | 手前右コーナー・広範囲カバレッジ |
| C3 | (0.2, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥左コーナー・広範囲カバレッジ |
| C4 | (2.6, 3.3, 2.3) | (1.4, 1.75, 0.9) | 奥右コーナー・広範囲カバレッジ |
| C5 | (0.2, 1.75, 1.8) | (1.4, 2.5, 0.5) | 左壁中段・ベッド側面視点 |
| C6 | (2.6, 1.75, 1.8) | (1.4, 2.5, 0.5) | 右壁中段・ベッド側面視点 |

**特徴**: 上部4台は upper_corners の4隅と同一で広範囲カバレッジを確保。中段2台はベッドの側面方向から見るため、臥位時のベッドオクルージョンを低減し三角測量角度も改善する。高さ方向にカメラが分散するため Z 方向の三角測量精度が向上する。

### 4.6 forward ベクトルと up_hint の非平行性の検証

全プリセットの全カメラについて、`forward`（= `look_at - position` の正規化）の Z 成分のみがゼロでないケースが存在しないことを確認済み。以下にすべてのカメラの `forward` ベクトル（正規化前）を示す:

| プリセット | カメラ | forward (正規化前) | 非平行性 |
|-----------|--------|-------------------|---------|
| upper_corners | C1 | (1.2, 1.55, -1.4) | X,Y 成分あり ✓ |
| upper_corners | C2 | (-1.2, 1.55, -1.4) | X,Y 成分あり ✓ |
| upper_corners | C3 | (1.2, -1.55, -1.4) | X,Y 成分あり ✓ |
| upper_corners | C4 | (-1.2, -1.55, -1.4) | X,Y 成分あり ✓ |
| upper_corners | C5 | (0, 1.55, -1.4) | Y 成分あり ✓ |
| upper_corners | C6 | (0, -1.55, -1.4) | Y 成分あり ✓ |
| wall_uniform | C1 | (1.2, 0.75, -1.4) | X,Y 成分あり ✓ |
| wall_uniform | C2 | (1.2, -0.75, -1.4) | X,Y 成分あり ✓ |
| wall_uniform | C3 | (-1.2, 0.75, -1.4) | X,Y 成分あり ✓ |
| wall_uniform | C4 | (-1.2, -0.75, -1.4) | X,Y 成分あり ✓ |
| wall_uniform | C5 | (0, 1.55, -1.4) | Y 成分あり ✓ |
| wall_uniform | C6 | (0, -1.55, -1.4) | Y 成分あり ✓ |
| overhead_grid | C1 | (0.6, 1.15, -1.4) | X,Y 成分あり ✓ |
| overhead_grid | C2 | (-0.6, 1.15, -1.4) | X,Y 成分あり ✓ |
| overhead_grid | C3 | (0.6, 0, -1.4) | X 成分あり ✓ |
| overhead_grid | C4 | (-0.6, 0, -1.4) | X 成分あり ✓ |
| overhead_grid | C5 | (0.6, -1.15, -1.4) | X,Y 成分あり ✓ |
| overhead_grid | C6 | (-0.6, -1.15, -1.4) | X,Y 成分あり ✓ |
| bed_focused | C1 | (1.2, 2.3, -1.8) | X,Y 成分あり ✓ |
| bed_focused | C2 | (-1.2, 2.3, -1.8) | X,Y 成分あり ✓ |
| bed_focused | C3 | (1.2, 0.75, -1.5) | X,Y 成分あり ✓ |
| bed_focused | C4 | (-1.2, 0.75, -1.5) | X,Y 成分あり ✓ |
| bed_focused | C5 | (1.2, -0.8, -1.5) | X,Y 成分あり ✓ |
| bed_focused | C6 | (-1.2, -0.8, -1.5) | X,Y 成分あり ✓ |
| hybrid | C1 | (1.2, 1.55, -1.4) | X,Y 成分あり ✓ |
| hybrid | C2 | (-1.2, 1.55, -1.4) | X,Y 成分あり ✓ |
| hybrid | C3 | (1.2, -1.55, -1.4) | X,Y 成分あり ✓ |
| hybrid | C4 | (-1.2, -1.55, -1.4) | X,Y 成分あり ✓ |
| hybrid | C5 | (1.2, 0.75, -1.3) | X,Y 成分あり ✓ |
| hybrid | C6 | (-1.2, 0.75, -1.3) | X,Y 成分あり ✓ |

全30台のカメラで `forward` ベクトルが `up_hint = [0, 0, 1]` と平行にならないことを確認済み。

## 5. 公開関数設計

### 5.1 `get_preset`

```python
def get_preset(name: str) -> PlacementPreset:
    """名前を指定してプリセットを取得する。

    Args:
        name: プリセット名。

    Returns:
        PlacementPreset インスタンス。

    Raises:
        KeyError: 指定された名前のプリセットが存在しない場合。
            メッセージに利用可能な名前一覧を含む。
    """
```

**処理ロジック**:
```
入力: name (str)
  │
  ├── _PRESETS 辞書から name をキーとして検索
  │
  ├── 見つかった場合 → PlacementPreset を返す
  │
  └── 見つからない場合 → KeyError を送出
          メッセージ: f"Unknown preset name: '{name}'. Available: {list(_PRESETS.keys())}"
```

### 5.2 `get_all_presets`

```python
def get_all_presets() -> list[PlacementPreset]:
    """全プリセットをリストで取得する。

    Returns:
        PlacementPreset のリスト（5要素）。定義順。
    """
```

**処理ロジック**:
```
return list(_PRESETS.values())
```

### 5.3 `list_preset_names`

```python
def list_preset_names() -> list[str]:
    """全プリセット名をリストで取得する。

    Returns:
        プリセット名のリスト（5要素）。定義順。
    """
```

**処理ロジック**:
```
return list(_PRESETS.keys())
```

### 5.4 `create_cameras`

```python
def create_cameras(
    preset: PlacementPreset,
    room: Room | None = None,
) -> list[Camera]:
    """プリセットから Camera オブジェクトのリストを生成する。

    Args:
        preset: カメラ配置プリセット。
        room: 病室モデル。非 None の場合、全カメラ位置が
            room.camera_zone 内にあることを検証する。

    Returns:
        Camera オブジェクトのリスト（6要素）。

    Raises:
        ValueError: room が非 None かつ、1台以上のカメラ位置が
            room.camera_zone の範囲外の場合。
    """
```

**処理ロジック**:
```
入力: preset (PlacementPreset), room (Room | None)
  │
  ├── Step 1: room が非 None の場合のバリデーション
  │     positions = [np.array(cfg.position) for cfg in preset.camera_configs]
  │     positions_array = np.stack(positions)  # shape (6, 3) を明示的に保証
  │     valid = room.is_valid_camera_position(positions_array)  # shape (6,)
  │     if not np.all(valid):
  │         invalid_indices = np.where(~valid)[0]
  │         details = [f"  Camera {i}: position={preset.camera_configs[i].position}"
  │                    for i in invalid_indices]
  │         raise ValueError(
  │             f"Camera positions outside camera zone:\n" + "\n".join(details)
  │         )
  │
  └── Step 2: Camera オブジェクト生成
        cameras = []
        for cfg in preset.camera_configs:
            cam = create_camera(
                position=list(cfg.position),
                look_at=list(cfg.look_at),
            )
            cameras.append(cam)
        return cameras
```

`list(cfg.position)` で tuple を list に変換する理由: `create_camera()` の型ヒントが `np.ndarray | list[float]` であり、型ヒントとの整合性を保つため。`np.asarray()` は tuple も受け付けるため動作上は不要だが、明示的な変換により意図を明確にする。

## 6. モジュール内部構造

### 6.1 プリセット辞書 `_PRESETS`

プリセットはモジュールレベルの `dict[str, PlacementPreset]` に格納する。辞書は挿入順が保持される（Python 3.7+）。

```python
_PRESETS: dict[str, PlacementPreset] = {}

def _register(preset: PlacementPreset) -> None:
    """プリセットを辞書に登録する。同名の重複登録は行わない（テストで検出する）。"""
    _PRESETS[preset.name] = preset
```

同名プリセットの上書き防止チェックは行わない。全プリセットはモジュール内でハードコード定義されており、重複はテスト（カテゴリB: B1 でプリセット数を検証）で検出する。

モジュール読み込み時に5つのプリセットを `_register` で登録する:

```python
_register(PlacementPreset(
    name="upper_corners",
    description="上部コーナー型: カメラ設置可能領域の上部4隅 + 前後壁中央2箇所に配置",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="wall_uniform",
    description="壁面均等型: 左右壁面に各2台 + 前後壁面に各1台で周囲に均等分散",
    camera_configs=(
        CameraConfig(position=(0.2, 1.0, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 2.5, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.0, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 2.5, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(1.4, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="overhead_grid",
    description="天井格子型: 天井直下に2×3の格子状に配置",
    camera_configs=(
        CameraConfig(position=(0.8, 0.6, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 0.6, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.8, 1.75, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 1.75, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.8, 2.9, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.0, 2.9, 2.3), look_at=_ROOM_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="bed_focused",
    description="ベッド集中型: 6台全てがベッド中央を注視。ベッド周囲の座位・臥位カバレッジを重視",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(0.2, 1.75, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.75, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.0), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.0), look_at=_BED_CENTER_TARGET),
    ),
))

_register(PlacementPreset(
    name="hybrid",
    description="ハイブリッド型: 上部4隅で広範囲カバレッジ + 壁面中段2台でベッド角度改善",
    camera_configs=(
        CameraConfig(position=(0.2, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 0.2, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(2.6, 3.3, 2.3), look_at=_ROOM_CENTER_TARGET),
        CameraConfig(position=(0.2, 1.75, 1.8), look_at=_BED_CENTER_TARGET),
        CameraConfig(position=(2.6, 1.75, 1.8), look_at=_BED_CENTER_TARGET),
    ),
))
```

## 7. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| 存在しないプリセット名 | `KeyError` を送出。メッセージに利用可能名一覧を含む | `get_preset` |
| カメラ位置がカメラ設置可能領域外 | `ValueError` を送出。範囲外のカメラインデックスと座標を含む | `create_cameras` |
| position == look_at | `ValueError`（`Camera.__post_init__` 経由） | `create_cameras` |
| forward // up_hint | `ValueError`（`Camera.__post_init__` 経由） | `create_cameras` |

## 8. 境界条件

| ケース | 期待動作 |
|--------|---------|
| `get_preset("upper_corners")` | `PlacementPreset` を返す |
| `get_preset("")` | `KeyError` |
| `get_preset("UPPER_CORNERS")` （大文字） | `KeyError`（大文字小文字を区別する） |
| `get_all_presets()` | 5要素のリスト |
| `list_preset_names()` | 5要素の文字列リスト |
| `create_cameras(preset, room=None)` | バリデーションなしで6台の Camera を返す |
| `create_cameras(preset, room=default_room)` | 全プリセットで正常動作（全位置が範囲内） |
| `create_cameras(preset, room=narrow_room)` | 範囲外があれば `ValueError` |

## 9. 設計判断

### 9.1 CameraConfig の position/look_at に tuple を使用する理由

- **採用案**: `tuple[float, float, float]`
- **却下案**: `np.ndarray`
  - 却下理由: `frozen=True` の dataclass と `np.ndarray` は相性が悪い（`np.ndarray` はハッシュ不可）。プリセット定義時のリテラル記述が冗長になる（`np.array([0.2, 0.2, 2.3])` vs `(0.2, 0.2, 2.3)`）
- `create_camera()` に渡す際は `list(cfg.position)` で tuple を list に変換する。`create_camera()` の型ヒントが `np.ndarray | list[float]` であり、型ヒントとの整合性を保つため明示的に変換する

### 9.2 プリセットをモジュールレベル辞書で管理する理由

- **採用案**: モジュールレベルの `dict[str, PlacementPreset]`（`_PRESETS`）に格納。`_register` 関数で登録
- **却下案1**: Enum で定義
  - 却下理由: Enum はカメラ座標データの格納に不向き。各メンバーの value に PlacementPreset を格納すると取り出しが冗長
- **却下案2**: JSON/TOML ファイルで定義
  - 却下理由: 外部ファイルの読み込みが必要。5パターン程度であればコード内定義が管理しやすい。スキーマのバリデーションも不要
- 辞書は挿入順が保持される（Python 3.7+）ため、`get_all_presets()` と `list_preset_names()` で順序が保証される

### 9.3 全プリセットの注視点を2種類に限定する理由

- **採用案**: `_ROOM_CENTER_TARGET = (1.4, 1.75, 0.9)` と `_BED_CENTER_TARGET = (1.4, 2.5, 0.5)` の2種類
- **却下案**: カメラごとに個別の注視点を計算（例: 担当エリアの中心）
  - 却下理由: F12 はプリセット（手動設計の配置パターン）であり、最適化はF14-F15のスコープ。複雑な注視点計算は不要。2つの代表的な注視点で十分な配置パターンの多様性が得られる
- `_ROOM_CENTER_TARGET`: X=1.4（部屋幅中央）、Y=1.75（部屋奥行中央）、Z=0.9（歩行時腰高さ付近）
- `_BED_CENTER_TARGET`: X=1.4（ベッド幅中央）、Y=2.5（ベッド奥行中央）、Z=0.5（ベッド面+座位中間）

### 9.4 PlacementPreset に `__post_init__` バリデーションを設けない理由

- **採用案**: バリデーションなし。`create_cameras` 関数で room 指定時にバリデーション
- **却下案**: `__post_init__` で `len(camera_configs) == 6` を検証
  - 却下理由: プリセットは全てモジュール内でハードコード定義されており、外部からの生成はスコープ外。コード内の定義ミスはテストで検出できる。ランタイムバリデーションのオーバーヘッドを避ける

### 9.5 5つのプリセットを選定した理由

- **採用案**: upper_corners, wall_uniform, overhead_grid, bed_focused, hybrid の5パターン
- 選定基準: 以下の3つの軸でパターンの多様性を確保した
  1. **XY分布**: コーナー集中（upper_corners）vs 壁面分散（wall_uniform）vs 格子状（overhead_grid）vs 対象物周囲（bed_focused）vs 混合（hybrid）
  2. **Z高さ**: 全高位置（upper_corners, wall_uniform, overhead_grid）vs 混合高さ（bed_focused: 2.3+2.0, hybrid: 2.3+1.8）
  3. **注視戦略**: 部屋全体（upper_corners, wall_uniform, overhead_grid）vs ベッド集中（bed_focused）vs 混合（hybrid）
- この多様性により、F13での比較が有意義になる

## 10. ログ・デバッグ設計

F12 はデータ定義モジュールであり、ログ出力は行わない。バリデーションエラーは例外（`KeyError`, `ValueError`）として呼び出し元に伝搬するため、F12 モジュール自体でのログ出力は不要である。デバッグ時は `preset.camera_configs` を直接参照してカメラ座標を確認すること。

## 10.5. ファイル・ディレクトリ設計

該当なし。F12 は外部ファイルの入出力を行わない。全データはコード内にハードコードされており、設定ファイルも使用しない。

## 11. 技術スタック

- **Python**: 3.12
- **numpy** (>=2.4.2): `create_cameras` 内でのカメラ位置バリデーションに使用（`Room.is_valid_camera_position`）
- **pytest**: テスト用（既存）

## 12. 依存機能との連携

### 12.1 F01（空間モデル）

- `Room.is_valid_camera_position(points)` でカメラ位置のバリデーション。内部で `self.camera_zone.contains(points)` を呼び出し、各点がカメラ設置可能領域 AABB 内に含まれるかを判定する。境界上の点は内側として扱う
- 引数: `points: np.ndarray` shape (N, 3)。戻り値: `np.ndarray` shape (N,) dtype bool
- インポート: `from camera_placement.models.environment import Room`

### 12.2 F02（カメラモデル）

- `create_camera(position, look_at)` で Camera オブジェクトを生成
- `Camera` 型を戻り値の型ヒントに使用
- インポート: `from camera_placement.models.camera import Camera, create_camera`

## 13. 後続機能との接続点

| 後続機能 | 使用する関数/クラス | 用途 |
|---------|-------------------|------|
| F13 配置比較 | `get_all_presets`, `create_cameras`, `PlacementPreset` | 全プリセットを評価・比較 |
| F15 最適化 | `get_preset`, `create_cameras` | 最適化の初期解として使用 |

F13 での使用イメージ:

```python
from camera_placement.placement.patterns import get_all_presets, create_cameras
from camera_placement.evaluation.evaluator import evaluate_placement
from camera_placement.models.environment import create_default_room

room = create_default_room()
for preset in get_all_presets():
    cameras = create_cameras(preset, room)
    result = evaluate_placement(cameras, room)
    print(f"{preset.name}: quality={result.quality.quality_score:.3f}")
```

## 14. `placement/__init__.py` の内容

```python
"""placement パッケージ: カメラ配置パターンの定義。"""

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
    "PlacementPreset",
    "create_cameras",
    "get_all_presets",
    "get_preset",
    "list_preset_names",
]
```

## 15. テスト計画

テストファイル: `tests/test_patterns.py`

### テスト用ヘルパー

```python
import numpy as np
import pytest
from camera_placement.placement.patterns import (
    CameraConfig,
    PlacementPreset,
    create_cameras,
    get_all_presets,
    get_preset,
    list_preset_names,
)
from camera_placement.models.environment import AABB, Room, create_default_room
from camera_placement.models.camera import Camera
```

### カテゴリA: get_preset

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 有効な名前で取得 | `"upper_corners"` | `PlacementPreset` インスタンス。`name == "upper_corners"` | 基本動作 |
| A2 | 全プリセット名で取得可能 | 5つの有効名 | 各名前で `PlacementPreset` が返る | 全プリセットの存在確認 |
| A3 | 存在しない名前 | `"invalid"` | `KeyError` | エラー処理 |
| A4 | 空文字列 | `""` | `KeyError` | 境界値 |
| A5 | 大文字 | `"UPPER_CORNERS"` | `KeyError` | 大文字小文字の区別 |
| A6 | KeyError メッセージに名前一覧 | `"invalid"` | `KeyError` のメッセージに `"Available"` と `"upper_corners"` を含む | エラーメッセージ品質 |

### カテゴリB: get_all_presets

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | リスト長 | なし | 長さ5 | 全プリセット数 |
| B2 | 全要素の型 | なし | 全て `PlacementPreset` | 型チェック |
| B3 | 順序 | なし | 名前順序: `["upper_corners", "wall_uniform", "overhead_grid", "bed_focused", "hybrid"]` | 定義順 |
| B4 | camera_configs の長さ | なし | 全プリセットで `len(camera_configs) == 6` | 6台固定 |

### カテゴリC: list_preset_names

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | 名前一覧 | なし | `["upper_corners", "wall_uniform", "overhead_grid", "bed_focused", "hybrid"]` | 完全一致 |
| C2 | リスト長 | なし | 長さ5 | 要素数 |

### カテゴリD: PlacementPreset / CameraConfig データ検証

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | preset.name が文字列 | 全プリセット | 全て `str` | 型チェック |
| D2 | preset.description が非空文字列 | 全プリセット | 全て `len(description) > 0` | 説明の存在 |
| D3 | camera_configs が tuple | 全プリセット | 全て `isinstance(camera_configs, tuple)` | 不変性 |
| D4 | CameraConfig の position が3要素タプル | 全プリセット | 全て `len(position) == 3` | 形状チェック |
| D5 | CameraConfig の look_at が3要素タプル | 全プリセット | 全て `len(look_at) == 3` | 形状チェック |
| D6 | 全カメラ位置がカメラ設置可能領域内 | 全プリセット | `Room.is_valid_camera_position` で全て True | 設置可能領域制約 |
| D7 | position != look_at | 全プリセット | 全カメラで `position != look_at` | Camera 生成の前提条件 |

### カテゴリE: create_cameras

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | 基本動作（room=None） | upper_corners, None | 長さ6の Camera リスト | Camera 生成 |
| E2 | 全プリセットで生成可能 | 各プリセット, None | 全て長さ6の Camera リストを返す | 全パターンの生成 |
| E3 | Camera の position が一致 | upper_corners, None | 各カメラの position がプリセット定義と一致（`np.allclose`） | 座標の正確性 |
| E4 | Camera の look_at が一致 | upper_corners, None | 各カメラの look_at がプリセット定義と一致（`np.allclose`） | 座標の正確性 |
| E5 | room バリデーション通過 | upper_corners, default_room | 正常動作 | デフォルト Room での検証 |
| E6 | 全プリセットで room バリデーション通過 | 各プリセット, default_room | 全て正常動作 | 全パターンの検証 |
| E7 | room バリデーション失敗 | upper_corners, 狭い camera_zone の Room | `ValueError` | 範囲外検出 |
| E8 | ValueError メッセージに詳細情報 | E7と同じ | メッセージに "Camera" と "position" を含む | エラーメッセージの品質 |

### カテゴリF: プリセット固有の検証

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| F1 | upper_corners の全カメラ Z=2.3 | upper_corners | 全 position の Z 成分が 2.3 | 配置の特性 |
| F2 | wall_uniform の全カメラ Z=2.3 | wall_uniform | 全 position の Z 成分が 2.3 | 配置の特性 |
| F3 | overhead_grid の全カメラ Z=2.3 | overhead_grid | 全 position の Z 成分が 2.3 | 配置の特性 |
| F4 | hybrid の高さ混合 | hybrid | C1-C4 が Z=2.3、C5-C6 が Z=1.8 | 高さ混合の検証 |
| F5 | bed_focused の注視点 | bed_focused | 全カメラの look_at が (1.4, 2.5, 0.5) | ベッド注視の検証 |
| F6 | hybrid の注視点混合 | hybrid | C1-C4 が (1.4, 1.75, 0.9)、C5-C6 が (1.4, 2.5, 0.5) | 注視点混合の検証 |

### テスト総数: 32 件
