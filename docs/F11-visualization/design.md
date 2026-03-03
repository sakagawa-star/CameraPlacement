# 機能設計書: F11 3D可視化

## 1. 対応要求マッピング

| 要求ID | 設計セクション |
|--------|--------------|
| FR-01 | 5.1 `create_room_traces`、6.1 AABB ワイヤフレーム座標生成 |
| FR-02 | 5.2 `create_bed_traces`、6.2 AABB Mesh3d 頂点・面定義 |
| FR-03 | 5.3 `create_camera_traces`、6.3 カメラマーカー・方向線 |
| FR-04 | 5.4 `create_frustum_traces`、6.4 視錐台ワイヤフレーム |
| FR-05 | 5.5 `create_coverage_traces`、6.5 カバレッジマップ |
| FR-06 | 5.6 `create_scene`、6.6 シーン組み立てフロー |
| FR-07 | 5.7 `save_html` |
| FR-08 | 5.4 legendgroup, 5.6 レイアウト設定 |

## 2. ファイル構成

```
src/camera_placement/
  visualization/
    __init__.py             # 新規作成: 公開シンボルのエクスポート
    viewer.py               # 新規作成: F11 メインモジュール
tests/
  test_viewer.py            # 新規作成: F11テスト
tests/results/
  F11_test_result.txt       # テスト結果
```

## 3. データ構造

F11 は新たな dataclass を定義しない。plotly の `go.Figure` と各トレースオブジェクト（`go.Scatter3d`, `go.Mesh3d`）を直接使用する。

### 3.1 定数定義

```python
# カメラごとの色（6色のカラーパレット）
CAMERA_COLORS: list[str] = [
    "rgb(31, 119, 180)",   # 青
    "rgb(255, 127, 14)",   # 橙
    "rgb(44, 160, 44)",    # 緑
    "rgb(214, 39, 40)",    # 赤
    "rgb(148, 103, 189)",  # 紫
    "rgb(140, 86, 75)",    # 茶
]

# 部屋ワイヤフレームの色
ROOM_COLOR: str = "rgb(0, 0, 0)"
ROOM_LINE_WIDTH: int = 2

# ベッドの色と不透明度
BED_COLOR: str = "lightblue"
BED_OPACITY: float = 0.3

# カメラマーカー・方向線の設定（マーカーと方向線は同じ色を使用する）
CAMERA_MARKER_SIZE: int = 6
CAMERA_MARKER_COLOR: str = "rgb(0, 0, 0)"
CAMERA_MARKER_SYMBOL: str = "diamond"
CAMERA_DIRECTION_LENGTH: float = 0.3  # [m]
CAMERA_DIRECTION_WIDTH: int = 3

# 視錐台ワイヤフレームの線幅
FRUSTUM_LINE_WIDTH: float = 1.5

# カバレッジマップの設定
COVERAGE_MARKER_SIZE: int = 3
COVERAGE_COLORSCALE: str = "RdYlGn"

# 図のサイズ
FIGURE_WIDTH: int = 1000
FIGURE_HEIGHT: int = 800
```

## 4. 内部ヘルパー関数

### 4.1 `_aabb_wireframe_coords`

```python
def _aabb_wireframe_coords(
    aabb: AABB,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """AABBの12辺のワイヤフレーム座標を生成する。

    Args:
        aabb: 対象のAABB。

    Returns:
        (xs, ys, zs) のタプル。各リストは辺の端点座標を含み、
        辺の区切りとして None を挿入する。
        各リストの長さは 12辺 × 3要素（始点, 終点, None） = 36。
    """
```

この関数はFR-01（部屋）とFR-04（視錐台）で共用しない。部屋はAABBから生成、視錐台は `get_frustum_corners()` の8頂点から生成するため、ロジックが異なる。

### 4.2 `_frustum_wireframe_coords`

```python
def _frustum_wireframe_coords(
    corners: np.ndarray,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """視錐台の8頂点から12辺のワイヤフレーム座標を生成する。

    内部で以下の12辺（インデックスペア）を定義し、座標リストを生成する:
        near面: (0,1), (1,3), (3,2), (2,0)
        far面:  (4,5), (5,7), (7,6), (6,4)
        接続:   (0,4), (1,5), (2,6), (3,7)

    Args:
        corners: shape (8, 3)。FrustumChecker.get_frustum_corners() の戻り値。
            順序: [near_tl, near_tr, near_bl, near_br,
                    far_tl,  far_tr,  far_bl,  far_br]

    Returns:
        (xs, ys, zs) のタプル。各リストの長さは 36。
    """
```

## 5. 公開関数設計

### 5.1 `create_room_traces`

```python
def create_room_traces(room: Room) -> list[go.Scatter3d]:
    """部屋のAABBワイヤフレームトレースを生成する。

    Args:
        room: 病室モデル。

    Returns:
        go.Scatter3d トレースのリスト（要素数1）。
    """
```

### 5.2 `create_bed_traces`

```python
def create_bed_traces(room: Room) -> list[go.Mesh3d]:
    """ベッドの半透明ボックストレースを生成する。

    Args:
        room: 病室モデル（room.bed を使用）。

    Returns:
        go.Mesh3d トレースのリスト（要素数1）。
    """
```

### 5.3 `create_camera_traces`

```python
def create_camera_traces(cameras: list[Camera]) -> list[go.Scatter3d]:
    """カメラ位置マーカーと方向線トレースを生成する。

    Args:
        cameras: カメラのリスト。

    Returns:
        go.Scatter3d トレースのリスト。
        cameras が空の場合は空リスト（要素数0）。
        cameras が1台以上の場合は要素数2（位置マーカー + 方向線）。
    """
```

### 5.4 `create_frustum_traces`

```python
def create_frustum_traces(
    cameras: list[Camera],
    near: float = 0.1,
    far: float = 3.0,
) -> list[go.Scatter3d]:
    """視錐台ワイヤフレームトレースを生成する。

    Args:
        cameras: カメラのリスト。
        near: ニアクリップ距離 [m]。
        far: 表示用ファークリップ距離 [m]。

    Returns:
        go.Scatter3d トレースのリスト（カメラ1台につき1トレース）。
        cameras が空の場合は空リスト（要素数0）。

    Raises:
        ValueError: far <= 0 の場合（create_frustum_traces 内で自前検証）。
        ValueError: near < 0 の場合（FrustumChecker.__post_init__ に委譲）。
        ValueError: far <= near の場合（FrustumChecker.__post_init__ に委譲）。
    """
```

### 5.5 `create_coverage_traces`

```python
def create_coverage_traces(
    grid_points: np.ndarray,
    visible_counts: np.ndarray,
    num_cameras: int = 6,
) -> list[go.Scatter3d]:
    """カバレッジマップトレースを生成する。

    Args:
        grid_points: グリッド点群。shape (N, 3)。
        visible_counts: 各点の視認カメラ数。shape (N,)。
        num_cameras: カラースケールの上限値（cmax）。

    Returns:
        go.Scatter3d トレースのリスト（要素数1）。
        N=0 の場合もリスト要素数は1（データなしの Scatter3d）。
    """
```

### 5.6 `create_scene`

```python
def create_scene(
    room: Room,
    cameras: list[Camera],
    coverage_result: CoverageResult | None = None,
    show_frustums: bool = True,
    show_grid: bool = True,
    frustum_far: float = 3.0,
    title: str = "Camera Placement Visualization",
) -> go.Figure:
    """3Dインタラクティブシーンを生成する。

    Args:
        room: 病室モデル。
        cameras: カメラのリスト。
        coverage_result: F07 のカバレッジ計算結果。None の場合はカバレッジマップを表示しない。
        show_frustums: True の場合、視錐台を表示する。
        show_grid: True の場合かつ coverage_result が非 None の場合、カバレッジマップを表示する。
        frustum_far: 視錐台の表示用ファークリップ距離 [m]。
        title: 図のタイトル。

    Returns:
        go.Figure インスタンス。

    Raises:
        ValueError: frustum_far <= 0 の場合。
    """
```

### 5.7 `save_html`

```python
def save_html(fig: go.Figure, filepath: str | Path) -> Path:
    """plotly Figure を HTML ファイルに保存する。

    Args:
        fig: 保存する Figure。
        filepath: 保存先のファイルパス。

    Returns:
        保存先の Path オブジェクト。
    """
```

## 6. アルゴリズム

### 6.1 AABB ワイヤフレーム座標生成（`_aabb_wireframe_coords`）

`create_room_traces` は `room.room_aabb` で部屋のAABBを取得し、`_aabb_wireframe_coords` に渡す。

```
入力: aabb (AABB)
  │
  ├── Step 1: 8頂点の座標を取得
  │           min_pt = aabb.min_point  # [x0, y0, z0]
  │           max_pt = aabb.max_point  # [x1, y1, z1]
  │
  │           v0 = (x0, y0, z0)  # 底面 手前左
  │           v1 = (x1, y0, z0)  # 底面 手前右
  │           v2 = (x1, y1, z0)  # 底面 奥右
  │           v3 = (x0, y1, z0)  # 底面 奥左
  │           v4 = (x0, y0, z1)  # 上面 手前左
  │           v5 = (x1, y0, z1)  # 上面 手前右
  │           v6 = (x1, y1, z1)  # 上面 奥右
  │           v7 = (x0, y1, z1)  # 上面 奥左
  │
  ├── Step 2: 12辺をインデックスペアで定義
  │           edges = [
  │               (0,1), (1,2), (2,3), (3,0),  # 底面4辺
  │               (4,5), (5,6), (6,7), (7,4),  # 上面4辺
  │               (0,4), (1,5), (2,6), (3,7),  # 垂直4辺
  │           ]
  │
  └── Step 3: 座標リスト生成
              xs, ys, zs = [], [], []
              for a, b in edges:
                  xs.extend([v[a][0], v[b][0], None])
                  ys.extend([v[a][1], v[b][1], None])
                  zs.extend([v[a][2], v[b][2], None])
              return xs, ys, zs
```

### 6.2 ベッド Mesh3d 頂点・面定義（`create_bed_traces`）

```
入力: room (Room)
  │
  ├── Step 1: ベッドAABBから8頂点を生成
  │           (v0〜v7 は 6.1 と同じ配置。aabb = room.bed)
  │
  │           x = [x0, x1, x1, x0, x0, x1, x1, x0]
  │           y = [y0, y0, y1, y1, y0, y0, y1, y1]
  │           z = [z0, z0, z0, z0, z1, z1, z1, z1]
  │
  ├── Step 2: 12個の三角形面を定義（6面 × 2三角形）
  │           i = [0, 0, 4, 4, 0, 0, 2, 2, 0, 0, 1, 1]
  │           j = [1, 2, 5, 6, 1, 5, 3, 7, 3, 7, 2, 6]
  │           k = [2, 3, 6, 7, 5, 4, 7, 6, 7, 4, 6, 5]
  │
  │           面の対応:
  │           底面 (z=z0): (0,1,2), (0,2,3)
  │           上面 (z=z1): (4,5,6), (4,6,7)
  │           手前 (y=y0): (0,1,5), (0,5,4)
  │           奥   (y=y1): (2,3,7), (2,7,6)
  │           左   (x=x0): (0,3,7), (0,7,4)
  │           右   (x=x1): (1,2,6), (1,6,5)
  │
  └── Step 3: go.Mesh3d トレース生成
              go.Mesh3d(
                  x=x, y=y, z=z,
                  i=i, j=j, k=k,
                  color=BED_COLOR,
                  opacity=BED_OPACITY,
                  name="Bed",
                  showlegend=True,
              )
```

### 6.3 カメラマーカー・方向線（`create_camera_traces`）

```
入力: cameras (list[Camera])
  │
  ├── Guard: len(cameras) == 0 → return []
  │
  ├── Step 1: カメラ位置マーカートレース
  │           positions = [cam.position for cam in cameras]
  │           x = [p[0] for p in positions]
  │           y = [p[1] for p in positions]
  │           z = [p[2] for p in positions]
  │           text = ["C1", "C2", ..., f"C{len(cameras)}"]
  │
  │           go.Scatter3d(
  │               x=x, y=y, z=z,
  │               mode="markers+text",
  │               marker=dict(size=CAMERA_MARKER_SIZE, color=CAMERA_MARKER_COLOR,
  │                           symbol=CAMERA_MARKER_SYMBOL),
  │               text=text,
  │               textposition="top center",
  │               name="Cameras",
  │               showlegend=True,
  │           )
  │
  └── Step 2: 方向線トレース
              xs, ys, zs = [], [], []
              for cam in cameras:
                  start = cam.position
                  end = cam.position + CAMERA_DIRECTION_LENGTH * cam.forward
                  xs.extend([start[0], end[0], None])
                  ys.extend([start[1], end[1], None])
                  zs.extend([start[2], end[2], None])

              go.Scatter3d(
                  x=xs, y=ys, z=zs,
                  mode="lines",
                  line=dict(color=CAMERA_MARKER_COLOR, width=CAMERA_DIRECTION_WIDTH),
                  name="Camera Direction",
                  showlegend=True,
              )
```

### 6.4 視錐台ワイヤフレーム（`create_frustum_traces`）

```
入力: cameras (list[Camera]), near (float), far (float)
  │
  ├── Guard: len(cameras) == 0 → return []
  │
  ├── バリデーション（自前）: far <= 0 → ValueError
  │   ※ near < 0 および far <= near は FrustumChecker.__post_init__ に委譲
  │
  └── for i, cam in enumerate(cameras):
          Step 1: FrustumChecker でcorners取得
                  checker = FrustumChecker(camera=cam, near=near, far=far)
                  corners = checker.get_frustum_corners()
                  # corners shape (8, 3)
                  # 順序: [near_tl, near_tr, near_bl, near_br,
                  #         far_tl,  far_tr,  far_bl,  far_br]

          Step 2: 12辺のインデックスペアを定義
                  edges = [
                      (0, 1), (1, 3), (3, 2), (2, 0),  # near面: tl-tr, tr-br, br-bl, bl-tl
                      (4, 5), (5, 7), (7, 6), (6, 4),  # far面
                      (0, 4), (1, 5), (2, 6), (3, 7),  # near-far接続
                  ]

          Step 3: _frustum_wireframe_coords で座標リスト生成
                  xs, ys, zs = _frustum_wireframe_coords(corners)

          Step 4: トレース生成
                  color = CAMERA_COLORS[i % len(CAMERA_COLORS)]
                  go.Scatter3d(
                      x=xs, y=ys, z=zs,
                      mode="lines",
                      line=dict(color=color, width=FRUSTUM_LINE_WIDTH),
                      name=f"Frustum C{i + 1}",
                      legendgroup="frustums",
                      showlegend=True,
                  )
```

### 6.5 カバレッジマップ（`create_coverage_traces`）

```
入力: grid_points (N, 3), visible_counts (N,), num_cameras (int)
  │
  ├── Case N == 0:
  │       go.Scatter3d(
  │           x=[], y=[], z=[],
  │           mode="markers",
  │           marker=dict(size=COVERAGE_MARKER_SIZE),
  │           name="Coverage",
  │           showlegend=True,
  │       )
  │
  └── Case N > 0:
          go.Scatter3d(
              x=grid_points[:, 0],
              y=grid_points[:, 1],
              z=grid_points[:, 2],
              mode="markers",
              marker=dict(
                  size=COVERAGE_MARKER_SIZE,
                  color=visible_counts,
                  colorscale=COVERAGE_COLORSCALE,
                  cmin=0,
                  cmax=num_cameras,
                  colorbar=dict(title="Visible Cameras"),
              ),
              name="Coverage",
              showlegend=True,
          )
```

### 6.6 シーン組み立てフロー（`create_scene`）

```
入力: room, cameras, coverage_result, show_frustums, show_grid,
      frustum_far, title
  │
  ├── Step 1: バリデーション
  │           frustum_far <= 0 → ValueError
  │
  ├── Step 2: トレース収集
  │           traces = []
  │
  │           ├── traces.extend(create_room_traces(room))
  │           ├── traces.extend(create_bed_traces(room))
  │           ├── traces.extend(create_camera_traces(cameras))
  │           │
  │           ├── if show_frustums and len(cameras) > 0:
  │           │       traces.extend(create_frustum_traces(cameras, near=0.1, far=frustum_far))
  │           │
  │           └── if show_grid and coverage_result is not None:
  │                   traces.extend(create_coverage_traces(
  │                       coverage_result.merged_grid,
  │                       coverage_result.stats.visible_counts,
  │                       coverage_result.stats.num_cameras,
  │                   ))
  │
  ├── Step 3: Figure 生成
  │           fig = go.Figure(data=traces)
  │
  └── Step 4: レイアウト設定
              fig.update_layout(
                  title=title,
                  scene=dict(
                      xaxis_title="X [m]",
                      yaxis_title="Y [m]",
                      zaxis_title="Z [m]",
                      aspectmode="data",
                  ),
                  width=FIGURE_WIDTH,
                  height=FIGURE_HEIGHT,
              )
              return fig
```

### 6.7 HTML出力（`save_html`）

```
入力: fig (go.Figure), filepath (str | Path)
  │
  ├── Step 1: Path 変換
  │           path = Path(filepath)
  │
  ├── Step 2: 親ディレクトリ作成
  │           path.parent.mkdir(parents=True, exist_ok=True)
  │
  ├── Step 3: HTML 書き出し
  │           fig.write_html(str(path), include_plotlyjs=True)
  │
  └── Step 4: return path
```

## 7. エラー処理

| エラー状況 | 処理 | 責任元 |
|-----------|------|--------|
| frustum_far <= 0 | `ValueError` を送出 | `create_frustum_traces`, `create_scene` |
| near < 0 | `ValueError` を送出（`FrustumChecker.__post_init__` 経由） | `create_frustum_traces` |
| far <= near | `ValueError` を送出（`FrustumChecker.__post_init__` 経由） | `create_frustum_traces` |
| cameras が空リスト | 正常動作。カメラ・視錐台トレースは空リスト | 各関数 |
| coverage_result が None | カバレッジマップを表示しない | `create_scene` |
| grid_points が空 (0, 3) | データなしの Scatter3d を返す | `create_coverage_traces` |
| filepath の親ディレクトリ不在 | 自動作成 | `save_html` |
| plotly が未インストール | `ImportError`（モジュールインポート時）。`uv add plotly` で解消 | Python ランタイム |

## 8. 境界条件

| ケース | 期待動作 |
|--------|---------|
| cameras = [] | create_camera_traces → [], create_frustum_traces → [] |
| cameras = [1台のみ] | 1台分のマーカー・方向線・視錐台を生成 |
| grid_points shape (0, 3) | create_coverage_traces → データなしの Scatter3d 1個 |
| grid_points shape (1, 3) | 1点のみ表示 |
| show_frustums=False かつ frustum_far <= 0 | ValueError（設計判断9.9参照: show_frustums の値に関わらずバリデーション実施） |
| frustum_far = 0.1 (= near と等しくなる値) | FrustumChecker が far > near を検証。near=0.1 かつ far=0.1 は ValueError |
| frustum_far > 10.0 | 正常動作。実用上は 1.0〜5.0 を推奨 |
| num_cameras = 0 | cmax=0 となりカラースケール幅がゼロ。plotly がフォールバック描画する |
| visible_counts が全て 0 | 全点が赤（RdYlGn の最小値）で表示 |
| visible_counts が全て 6 | 全点が緑（RdYlGn の最大値）で表示 |

## 9. 設計判断

### 9.1 plotly を可視化ライブラリに採用する理由

- **採用案**: plotly（`plotly.graph_objects`）
- **却下案1**: matplotlib 3D（`mpl_toolkits.mplot3d`）
  - 却下理由: 3Dインタラクションが貧弱（回転のみ、ズームが不自然）。HTML 出力が困難
- **却下案2**: open3d
  - 却下理由: インストールが大きく環境依存性が高い。HTML出力がサポートされない
- **却下案3**: pyvista
  - 却下理由: VTK 依存で重い。HTMLエクスポートはあるが plotly の方がシンプル
- 採用理由: `docs/plan.md` で plotly が指定されている。HTML出力がネイティブサポート。ブラウザベースで環境非依存。ライブラリサイズが小さい

### 9.2 トレース生成関数を公開する理由

- **採用案**: 各トレース生成関数を公開 API として提供
- **却下案**: プライベート関数にして `create_scene` のみ公開
  - 却下理由: F13（配置比較）が個別トレースを組み合わせて並列比較図を作成する可能性がある。F15（最適化結果）も最適化前後の比較表示に個別トレースが必要
- トレース生成関数は副作用のない純粋関数であり、公開してもリスクがない

### 9.3 視錐台の表示用 far 距離をデフォルト 3.0m にする理由

- **採用案**: `frustum_far = 3.0` をデフォルト
- **却下案1**: `frustum_far = 10.0`（実際の far 距離）
  - 却下理由: 病室サイズ（2.8 × 3.5 × 2.5m）に対して視錐台が大きすぎ、他の要素が見えなくなる
- **却下案2**: `frustum_far = 1.0`
  - 却下理由: 短すぎて視錐台の形状が分かりにくい
- 3.0m は病室の対角距離（≈3.2m）に近く、視錐台の形状が把握しやすいバランス

### 9.4 カバレッジの色スケールに RdYlGn を使用する理由

- **採用案**: `RdYlGn`（Red → Yellow → Green）
- **却下案1**: `Viridis`
  - 却下理由: 値の大小の直感的な良し悪しの対応が弱い。RdYlGn は「赤=悪い、緑=良い」で直感的
- **却下案2**: カスタム離散カラーマップ
  - 却下理由: plotly の連続カラースケール + cmin/cmax で十分。離散化のコードが不要で簡潔

### 9.5 ベッドを Mesh3d で描画する理由

- **採用案**: `go.Mesh3d` で半透明ボックス
- **却下案**: `go.Scatter3d` でワイヤフレーム
  - 却下理由: ベッドは物理的な遮蔽物であり、面で描画した方がオクルージョンの影響を視覚的に理解しやすい。半透明にすることで背後のグリッド点も確認可能

### 9.6 カメラ方向を線分で表示する理由

- **採用案**: `go.Scatter3d` の `mode='lines'` で0.3mの線分
- **却下案**: `go.Cone` で矢印表示
  - 却下理由: `go.Cone` はベクトル場向けの API で、個別の矢印を描画するには不自然。また cone のサイズ制御が複雑。線分の方がシンプルで十分

### 9.7 視錐台を legendgroup でグルーピングする理由

- **採用案**: 全視錐台に `legendgroup="frustums"` を設定
- **却下案**: グルーピングなし（各視錐台を独立に表示/非表示）
  - 却下理由: 6台の視錐台を個別に切り替える需要は低い。一括で ON/OFF できる方が実用的。個別制御は plotly の凡例ダブルクリックで対応可能

### 9.8 create_scene で near を 0.1 にハードコードする理由

- **採用案**: `create_scene` 内で `create_frustum_traces(cameras, near=0.1, far=frustum_far)` と near を 0.1 固定
- **却下案**: `create_scene` に `frustum_near` パラメータを追加
  - 却下理由: near 面はカメラ近傍のごく狭い矩形であり、可視化上はほぼ見えない。表示品質への影響が極めて小さいため、パラメータを増やして API を複雑化する価値がない。個別制御が必要な場合は `create_frustum_traces` を直接呼べばよい
- `create_frustum_traces` 関数は `near` パラメータを公開しているため、直接呼び出しによるカスタマイズは可能

### 9.9 create_scene で frustum_far のバリデーションを行う理由

- **採用案**: `create_scene` 内で `frustum_far <= 0` の場合に `ValueError` を送出
- **却下案**: `create_frustum_traces` のみでバリデーション
  - 却下理由: `show_frustums=False` の場合は `create_frustum_traces` が呼ばれないため、不正な `frustum_far` がサイレントに無視される。`create_scene` でも早期検出することで一貫性を保つ

## 10. ログ・デバッグ設計

F11 は可視化モジュールであり、ログ出力は行わない。デバッグ時は `fig.to_dict()` で Figure の内部構造を確認すること。

## 11. 技術スタック

- **Python**: 3.12
- **numpy** (>=2.4.2): 既存依存
- **plotly** (>=5.0): 3D可視化。`uv add plotly` で追加する
  - 使用モジュール: `plotly.graph_objects`（`go.Scatter3d`, `go.Mesh3d`, `go.Figure`）
  - 使用メソッド: `fig.write_html()`, `fig.update_layout()`
- **pytest**: テスト用（既存）

## 12. 依存機能との連携

### 12.1 F01（空間モデル）

- `Room` インスタンスから `room_aabb`（部屋境界）と `bed`（ベッドAABB）を取得
- `AABB.min_point`, `AABB.max_point` から座標を取得
- インポート: `from camera_placement.models.environment import Room, AABB`

### 12.2 F02（カメラモデル）

- `Camera.position` （カメラ位置）、`Camera.forward`（前方方向）を取得
- 型ヒントに使用
- インポート: `from camera_placement.models.camera import Camera`

### 12.3 F04（視錐台判定）

- `FrustumChecker(camera, near, far).get_frustum_corners()` で視錐台の8頂点を取得
- インポート: `from camera_placement.core.frustum import FrustumChecker`

### 12.4 F07（カバレッジ計算）

- `CoverageResult.merged_grid` （グリッド点群）、`CoverageResult.stats.visible_counts`（視認カメラ数）、`CoverageResult.stats.num_cameras` を取得
- 型ヒントに使用
- インポート: `from camera_placement.evaluation.coverage import CoverageResult`

## 13. 後続機能との接続点

| 後続機能 | 使用する関数 | 用途 |
|---------|-------------|------|
| F13 配置比較 | `create_scene`, `save_html`, 個別トレース生成関数 | 複数配置パターンの可視化・比較 |
| F15 最適化結果 | `create_scene`, `save_html` | 最適化結果の配置を3D表示 |

F13 での使用イメージ:

```python
from camera_placement.visualization.viewer import create_scene, save_html

# パターンA
fig_a = create_scene(room, cameras_a, coverage_a, title="Pattern A")
save_html(fig_a, "output/pattern_a.html")

# パターンB
fig_b = create_scene(room, cameras_b, coverage_b, title="Pattern B")
save_html(fig_b, "output/pattern_b.html")
```

## 14. `visualization/__init__.py` の内容

```python
"""visualization パッケージ: 3D可視化機能。"""

from camera_placement.visualization.viewer import (
    create_bed_traces,
    create_camera_traces,
    create_coverage_traces,
    create_frustum_traces,
    create_room_traces,
    create_scene,
    save_html,
)

__all__ = [
    "create_bed_traces",
    "create_camera_traces",
    "create_coverage_traces",
    "create_frustum_traces",
    "create_room_traces",
    "create_scene",
    "save_html",
]
```

## 15. テスト計画

テストファイル: `tests/test_viewer.py`

### テスト用ヘルパー

```python
import numpy as np
from camera_placement.models.environment import create_default_room, Room
from camera_placement.models.camera import Camera, create_camera

def _create_test_cameras() -> list[Camera]:
    """テスト用6台カメラ（コーナー配置）。"""
    center = [1.4, 1.75, 0.5]
    return [
        create_camera([0.2, 0.2, 2.3], center),
        create_camera([2.6, 0.2, 2.3], center),
        create_camera([0.2, 3.3, 2.3], center),
        create_camera([2.6, 3.3, 2.3], center),
        create_camera([1.4, 0.2, 2.3], center),
        create_camera([1.4, 3.3, 2.3], center),
    ]
```

### カテゴリA: create_room_traces

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| A1 | 基本動作 | デフォルト Room | リスト長1、型 go.Scatter3d | トレース生成 |
| A2 | トレース名 | デフォルト Room | traces[0].name == "Room" | 名前設定 |
| A3 | 座標データの存在 | デフォルト Room | traces[0].x の長さ == 36（12辺 × 3要素） | ワイヤフレーム辺数 |
| A4 | None 区切りの存在 | デフォルト Room | traces[0].x に None が 12 個含まれる | 辺の分離 |

### カテゴリB: create_bed_traces

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| B1 | 基本動作 | デフォルト Room | リスト長1、型 go.Mesh3d | トレース生成 |
| B2 | トレース名 | デフォルト Room | traces[0].name == "Bed" | 名前設定 |
| B3 | 頂点数 | デフォルト Room | len(traces[0].x) == 8 | 8頂点 |
| B4 | 面数 | デフォルト Room | len(traces[0].i) == 12 | 12三角形 |
| B5 | 不透明度 | デフォルト Room | traces[0].opacity == 0.3 | 半透明設定 |

### カテゴリC: create_camera_traces

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| C1 | 基本動作 | 6台カメラ | リスト長2（マーカー + 方向線） | トレース生成 |
| C2 | マーカートレース名 | 6台カメラ | traces[0].name == "Cameras" | 名前設定 |
| C3 | 方向線トレース名 | 6台カメラ | traces[1].name == "Camera Direction" | 名前設定 |
| C4 | マーカー位置数 | 6台カメラ | len(traces[0].x) == 6 | 全カメラの位置 |
| C5 | テキストラベル | 6台カメラ | traces[0].text == ("C1", "C2", ..., "C6") | ラベル |
| C6 | 空カメラリスト | [] | リスト長0 | エッジケース |
| C7 | 1台カメラ | 1台 | リスト長2、マーカー位置数1 | 最小台数 |

### カテゴリD: create_frustum_traces

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| D1 | 基本動作 | 6台カメラ | リスト長6 | カメラ1台1トレース |
| D2 | トレース名 | 6台カメラ | traces[0].name == "Frustum C1" | 名前設定 |
| D3 | legendgroup | 6台カメラ | traces[0].legendgroup == "frustums" | グルーピング |
| D4 | 座標データ長 | 1台カメラ | traces[0].x の長さ == 36 | 12辺 × 3要素 |
| D5 | 空カメラリスト | [] | リスト長0 | エッジケース |
| D6 | far <= 0 | far=0 | ValueError | バリデーション |
| D7 | far <= near | near=1.0, far=0.5 | ValueError | バリデーション |

### カテゴリE: create_coverage_traces

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| E1 | 基本動作 | 10点、counts=[0..9] | リスト長1、型 go.Scatter3d | トレース生成 |
| E2 | トレース名 | 10点 | traces[0].name == "Coverage" | 名前設定 |
| E3 | マーカーサイズ | 10点 | traces[0].marker.size == 3 | サイズ設定 |
| E4 | カラースケール | 10点 | traces[0].marker.colorscale == "RdYlGn" | カラースケール |
| E5 | cmin/cmax | 10点, num_cameras=6 | traces[0].marker.cmin == 0, cmax == 6 | 値範囲 |
| E6 | 空グリッド | shape (0,3), shape (0,) | リスト長1、x/y/z は空 | エッジケース |

### カテゴリF: create_scene

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| F1 | 最小構成（カバレッジなし） | room, cameras, coverage_result=None | Figure のトレース数 = 1(room) + 1(bed) + 2(cam) + 6(frustum) = 10 | 基本構成 |
| F2 | カバレッジ付き | room, cameras, coverage_result | トレース数 = 10 + 1(coverage) = 11 | フル構成 |
| F3 | show_frustums=False | room, cameras, show_frustums=False | トレース数 = 1 + 1 + 2 = 4 | 視錐台非表示 |
| F4 | show_grid=False | room, cameras, coverage_result, show_grid=False | トレース数 = 10 | グリッド非表示 |
| F5 | タイトル設定 | title="Test" | fig.layout.title.text == "Test" | タイトル |
| F6 | 軸ラベル | デフォルト | xaxis_title="X [m]" 等 | ラベル設定 |
| F7 | aspectmode | デフォルト | fig.layout.scene.aspectmode == "data" | 等スケール |
| F8 | frustum_far <= 0 | frustum_far=0 | ValueError | バリデーション |
| F9 | カメラ空リスト | cameras=[] | トレース数 = 1(room) + 1(bed) = 2 | エッジケース |
| F10 | coverage_result=None, show_grid=True | room, cameras | カバレッジトレースなし。トレース数 = 10 | coverage_result がないため非表示 |

### カテゴリG: save_html

| # | テストケース | 入力 | 期待値 | 検証意図 |
|---|-------------|------|--------|---------|
| G1 | 基本動作 | Figure, tmp_path/"test.html" | ファイルが存在すること | ファイル生成 |
| G2 | 戻り値 | Figure, filepath | 戻り値 == Path(filepath) | 戻り値の型 |
| G3 | 親ディレクトリ自動作成 | tmp_path/"sub/dir/test.html" | ファイルが存在すること | ディレクトリ作成 |
| G4 | ファイルサイズ | 空の Figure | ファイルサイズ > 0 | ファイル出力 |

### テスト総数: 43 件
